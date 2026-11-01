# -*- coding: utf-8 -*-
"""FastAPI 主路由：对话、MFA、审计、概览、重置。"""
import os
from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel

from .agent.executor import Engine
from .bank import db
from .sandbox import code_sandbox

STATIC_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "static")

app = FastAPI(title="智银 · AI Banking Agent")
engine = Engine()


@app.on_event("startup")
def _startup():
    db.init_db(force=False)


class ChatReq(BaseModel):
    session_id: str = "demo"
    message: str


class CodeReq(BaseModel):
    code: str


@app.post("/chat")
def chat(req: ChatReq):
    result = engine.handle(req.session_id, req.message)
    return JSONResponse(result)


@app.post("/mfa/face")
def mfa_face(req: ChatReq):
    s = engine._sess(req.session_id)
    # 红线：仅当会话正处于等待 MFA 验证状态时才允许继续，否则拒绝
    if getattr(s, "awaiting", None) not in ("mfa_sms", "mfa_face"):
        engine.audit.log(req.session_id, "blocked", "人脸旁路：会话未处于MFA待验态")
        return {"reply": "⚠️ 当前没有待人脸验证的操作，门禁已拒绝本次请求。", "ui": []}
    ok, msg = engine.mfa.verify_face()
    engine.audit.log(req.session_id, "mfa", {"verify": "face", "ok": ok})
    if ok:
        engine.breaker.record_success()
        s.awaiting = None
        s.mfa_approved = True   # 本批MFA通过，后续红色节点直接执行
        if s.plan and s.idx < len(s.plan):
            node = s.plan[s.idx]
            engine._run_node(req.session_id, node)
            node_msg = node.get("_result_msg", "")
            s.idx += 1
            out = engine._after_step(req.session_id, node_msg)
            out["reply"] = f"✅ {msg}\n" + out["reply"]
            return out
    return {"reply": f"❌ {msg}", "ui": []}


@app.get("/audit")
def audit(limit: int = 50):
    return {"logs": engine.audit.recent(limit)}


@app.get("/overview")
def overview():
    from .sandbox import data_sandbox as ds
    from .bank.service import get_sim_now
    c = ds.query_one("SELECT name,balance,risk_level FROM customers WHERE id=1")
    cards = ds.query("SELECT card_no,status,daily_limit FROM cards WHERE customer_id=1")
    locks = ds.query_one("SELECT COALESCE(SUM(amount),0) s FROM funds_locks WHERE customer_id=1 AND status='锁定中'")
    dlim = ds.query_one("SELECT daily_limit l FROM cards WHERE customer_id=1 AND is_default=1")
    return {"name": c["name"], "balance": c["balance"], "risk_level": c["risk_level"],
            "locked": locks["s"], "cards": cards, "today": get_sim_now(),
            "daily_limit": dlim["l"] if dlim else 0}


@app.post("/reset")
def reset():
    engine.reset()
    return {"ok": True}


@app.post("/sandbox/run")
def sandbox_run(req: CodeReq):
    """代码沙箱接口：演示受限代码执行。"""
    ok, out, err = code_sandbox.run_code(req.code)
    return {"ok": ok, "stdout": out, "stderr": err}


@app.get("/")
def index():
    return FileResponse(
        os.path.join(STATIC_DIR, "index.html"),
        headers={"Cache-Control": "no-cache, no-store, must-revalidate",
                 "Pragma": "no-cache", "Expires": "0"})
