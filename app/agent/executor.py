# -*- coding: utf-8 -*-
"""
执行状态机：会话状态 = plan / idx / awaiting / clarify / human。
门禁前零副作用：付款/挂失只在确认+验证后才真正调用银行核心。
"""
import re
from ..security import policy, guard, mfa as mfa_mod, audit
from ..bank import service
from ..sandbox import data_sandbox as ds
from . import intent as intent_mod
from . import planner
from . import nlp


def ds_query_cards():
    return ds.query("SELECT id,card_no,card_type,daily_limit,status FROM cards WHERE customer_id=1")


class Session:
    def __init__(self):
        self.plan = []
        self.idx = 0
        self.awaiting = None
        self.clarify_for = None
        self.human = False
        self.daily_transfer_total = 0.0
        self.pending_slots = {}
        self.pending_rest = []
        self.mfa_approved = False   # 本批次MFA是否已通过（同批后续红色节点不再重复验证）
        # 多轮上下文记忆
        self.last_payee = None
        self.last_payee_phone = None
        self.last_amount = None
        self.last_intent = None


class Engine:
    def __init__(self):
        self.mfa = mfa_mod.MFA()
        self.audit = audit.Audit()
        self.breaker = guard.CircuitBreaker()
        self.sessions = {}

    def _sess(self, sid):
        if sid not in self.sessions:
            self.sessions[sid] = Session()
        return self.sessions[sid]

    def _contacts(self):
        from ..sandbox import data_sandbox as ds
        rows = ds.query("SELECT name,phone,relation_alias,spouse_name FROM customers")
        contacts = {}
        for r in rows:
            contacts[r["name"]] = r
        return contacts

    def handle(self, sid, message):
        result = self._handle_inner(sid, message)
        # 追加临近生日/纪念日提醒
        try:
            from ..bank.service import upcoming_reminders
            rems = upcoming_reminders()
            if rems:
                result["reply"] = result.get("reply","") + "\n\n🔔 温馨提醒：\n" + "\n".join("· " + r for r in rems)
        except Exception:
            pass
        return result

    def _handle_inner(self, sid, message):
        s = self._sess(sid)
        self.audit.log(sid, "user", message)

        # 0) 熔断检查
        locked, secs = self.breaker.is_locked()
        if locked:
            self.audit.log(sid, "blocked", f"安全锁定中，剩余 {secs}s")
            return {"reply": f"⚠️ 出于安全，账户已临时锁定（连续失败过多），请 {secs} 秒后再试。",
                    "ui": [], "locked": True}

        # 1) 注入检测
        inj = guard.detect_injection(message)
        if inj:
            self.audit.log(sid, "injection", {"hit": inj, "input": message})
            self.breaker.record_failure()
            return {"reply": "🚫 检测到越权指令注入，已拒绝并记录审计。正常业务请直接说明。", "ui": []}

        # 2) 人工接管
        if s.human:
            ctrl, _ = intent_mod.parse_intent(message, self._contacts())
            if ctrl == "ai_back":
                s.human = False
                return {"reply": "✅ 已切回 AI 助手，请问需要办理什么业务？", "ui": []}
            return {"reply": "（人工客服接入中，AI 已暂停执行任何操作…）", "ui": []}

        # 3) MFA 校验中？用户输入的是验证码（但"取消"可中止）
        if s.awaiting == "mfa_sms":
            if re.match(r"^(取消|算了|不要了|别办了|先不|中止|退出)\s*$", message.strip()):
                s.plan, s.idx, s.awaiting = [], 0, None
                self.audit.log(sid, "cancel", "MFA阶段用户取消")
                return {"reply": "已取消该操作，未完成任何转账。", "ui": []}
            ok, msg = self.mfa.verify_sms(sid, message)
            self.audit.log(sid, "mfa", {"verify": "sms", "ok": ok, "msg": msg})
            if not ok:
                self.breaker.record_failure()
                return {"reply": f"❌ {msg}，请重新输入 6 位验证码。", "ui": []}
            self.breaker.record_success()
            s.awaiting = None
            return self._resume_after_mfa(sid)

        # 4) 槽位补全（clarify）
        if s.awaiting == "clarify":
            return self._fill_slot(sid, message)

        # 5) 控制词（若正在等待确认，"确认，转500"这种也按确认处理）
        ctrl, _ = intent_mod.parse_intent(message, self._contacts())
        if ctrl == "human":
            s.human = True
            self.audit.log(sid, "takeover", "转人工")
            return {"reply": "已为您转接人工客服，AI 已暂停自动操作。输入「恢复AI」可切回。", "ui": []}
        if ctrl == "cancel":
            s.plan, s.idx, s.awaiting = [], 0, None
            self.audit.log(sid, "cancel", "用户取消")
            return {"reply": "已取消当前操作，资金未发生任何变动。", "ui": []}
        if ctrl == "confirm" or (s.awaiting == "confirm" and re.match(r"^(确认|好的?|OK|嗯|行|可以|就这么办)[!。,.，\s]", message)):
            return self._on_confirm(sid)

        # 6) 多轮上下文：再转X / 同样再来一次 / 还是刚才那个金额 / 给他再转X
        import re as _re
        found = None
        m = _re.match(r"^\s*(再|又|追加|继续|同样|一样|还是刚才那个)\s*(转|打|汇)?\s*(给)?\s*([0-9一二三四五六七八九十百千万]+)?\s*(块|元|块钱)?\s*$", message)
        if m and s.last_payee and not s.awaiting:
            amt = nlp.parse_amount(m.group(4)) if m.group(4) else s.last_amount
            if amt:
                self.audit.log(sid, "ctx_followup", {"payee": s.last_payee, "amount": amt})
                found = [("transfer", {"to": s.last_payee, "to_phone": s.last_payee_phone,
                                       "amount": amt, "note": "追加转账"})]
        # "给他再转X" / "还是刚才那个金额"
        if found is None and s.last_payee and not s.awaiting:
            m3 = _re.match(r"^\s*(给他|给她|再给他|再给她|还是刚才那个金额|同样的|一样的)\s*(转|打|汇)?\s*([0-9一二三四五六七八九十百千万]+)?\s*(块|元)?\s*$", message)
            if m3:
                amt = nlp.parse_amount(m3.group(3)) if m3.group(3) else s.last_amount
                if amt:
                    self.audit.log(sid, "ctx_followup", {"payee": s.last_payee, "amount": amt})
                    found = [("transfer", {"to": s.last_payee, "to_phone": s.last_payee_phone,
                                           "amount": amt, "note": "追加转账"})]
        # AA 计算：680四个人AA -> 每人170
        m2 = _re.match(r"^\s*([0-9]+)\s*(块|元)?\s*([一二三四五六七八九十\d]+)\s*个人?\s*AA\s*$", message)
        if m2 and not s.awaiting and found is None:
            total = float(m2.group(1))
            nmap = {"一":1,"二":2,"三":3,"四":4,"五":5,"六":6,"七":7,"八":8,"九":9,"十":10}
            n = nmap.get(m2.group(3), int(m2.group(3)) if m2.group(3).isdigit() else 4)
            per = round(total / n, 2)
            return {"reply": f"🧮 {total:.0f}元 / {n}人 AA = 每人 ¥{per:,.2f}。需要我把这笔钱转给谁吗？", "ui": []}

        # 7) 解析意图
        if found is None:
            _, found = intent_mod.parse_intent(message, self._contacts())
        if not found:
            return {"reply": "抱歉，我还没太理解。您可以试试：\n· 查询余额 / 最近交易\n· 给妈妈转500\n· 申购理财 / 我的订阅有哪些\n· 银行卡挂失\n· 我爱人生日快到了",
                    "ui": []}

        self.audit.log(sid, "intent", {"intents": found})

        # 7) 槽位完整性检查：转账缺收款人/金额 -> clarify
        for idx, (intent, slots) in enumerate(found):
            if intent == "transfer":
                # 同姓模糊候选（老张/小李）：单人确认，多人列出选择
                if not slots.get("to") and slots.get("candidates"):
                    cands = slots["candidates"]
                    s.awaiting = "clarify"
                    s.clarify_for = ("transfer", "choose_payee")
                    s.pending_slots = dict(slots)
                    s.pending_rest = found[:idx] + found[idx+1:]   # 保存全部其他意图
                    self.audit.log(sid, "clarify", {"need": "choose_payee", "candidates": cands})
                    if len(cands) == 1:
                        nm, ph = cands[0]
                        return {"reply": f"您是要转给 「{nm}」（{ph}）吗？回复「确认」继续，或直接告诉我具体姓名。", "ui": []}
                    lines = "\n".join([f"  {i+1}. {nm}（{ph}）" for i, (nm, ph) in enumerate(cands)])
                    return {"reply": f"找到 {len(cands)} 位同姓联系人，请回复序号或姓名：\n{lines}", "ui": []}
                if not slots.get("to"):
                    s.awaiting = "clarify"
                    s.clarify_for = ("transfer", "to")
                    s.pending_slots = dict(slots)
                    s.pending_rest = found[:idx] + found[idx+1:]
                    self.audit.log(sid, "clarify", {"need": "to"})
                    return {"reply": "请问这笔转账要转给谁？（可说姓名、手机号或称谓，如「我爱人」）", "ui": []}
                if not slots.get("amount"):
                    s.awaiting = "clarify"
                    s.clarify_for = ("transfer", "amount")
                    s.pending_slots = dict(slots)
                    s.pending_rest = found[:idx] + found[idx+1:]
                    self.audit.log(sid, "clarify", {"need": "amount"})
                    return {"reply": f"好的，转给 {slots.get('to')}。请问转多少金额？（如 两千五 / 800）", "ui": []}
            # 挂失未指定哪张卡 -> 列出卡片让用户选
            if intent == "report_loss" and not slots.get("card_hint"):
                cards = ds_query_cards()
                active = [c for c in cards if c["status"] == "正常"]
                if len(active) > 1:
                    s.awaiting = "clarify"
                    s.clarify_for = ("report_loss", "choose_card")
                    s.pending_slots = dict(slots)
                    lines = "\n".join([f"  {i+1}. {c['card_type']} {c['card_no']}（日限¥{c['daily_limit']:,.0f}）"
                                       for i, c in enumerate(active)])
                    return {"reply": f"您要挂失哪张卡？请回复序号或卡类型：\n{lines}", "ui": []}

            # 转账日限额预检（别让用户走完MFA才被拒）
            if intent == "transfer" and slots.get("amount"):
                card = ds.query_one("SELECT daily_limit l FROM cards WHERE customer_id=1 AND is_default=1")
                if card and slots["amount"] > card["l"]:
                    self.audit.log(sid, "rejected", {"op": intent, "reason": "over_daily_limit"})
                    return {"reply": f"❌ 超过日限额：默认卡单日限额 ¥{card['l']:,.0f}，本次 ¥{slots['amount']:,.2f}。请先调高日限额或分笔转账。", "ui": []}
            # 理财起购金额预检（别让用户走完MFA才被拒）
            if intent == "wealth_purchase":
                from ..bank.service import product_info
                pname = slots.get("product") or ""
                amt = slots.get("amount")
                p = product_info(pname)
                if p and amt and amt < p["min"]:
                    self.audit.log(sid, "rejected", {"op": intent, "reason": "below_min"})
                    return {"reply": f"❌ {p['code']} 起购金额为 ¥{p['min']:,.0f}，您输入的 ¥{amt:,.0f} 未达起购门槛，请提高金额。", "ui": []}
                if not amt:
                    return {"reply": f"请问要买 {pname or '理财'} 多少金额？（如 五千 / 5000）", "ui": []}

        # 8) 规划 DAG
        state = {"daily_transfer_total": s.daily_transfer_total}
        nodes = planner.plan(found, state)
        # 实时计算每个节点风险
        for n in nodes:
            n["risk"] = policy.risk_of(n["op"], n["args"], state)
            n["risk_label"] = policy.label(n["risk"])
        s.plan, s.idx = nodes, 0
        s.mfa_approved = False
        self.audit.log(sid, "plan", {"nodes": [{"op": n["op"], "risk": n["risk"]} for n in nodes]})

        return self._execute_until_gate(sid)

    def _fill_slot(self, sid, message):
        s = self._sess(sid)
        intent, field = s.clarify_for
        contacts = self._contacts()
        if field == "to":
            payee, how = intent_mod._extract_payee(message, contacts)
            if not payee:
                return {"reply": f"通讯录里没找到「{message}」，请换一个姓名或手机号。", "ui": []}
            s.pending_slots["to"] = payee
            s.awaiting = "clarify"
            s.clarify_for = (intent, "amount")
            self.audit.log(sid, "clarify", {"filled": {"to": payee}})
            return {"reply": f"收款人已记为 {payee}。请问转多少？", "ui": []}
        if field == "choose_card":
            cards = [c for c in ds_query_cards() if c["status"] == "正常"]
            chosen = None
            if re.match(r"^\d+$", message.strip()):
                idx = int(message.strip()) - 1
                if 0 <= idx < len(cards):
                    chosen = cards[idx]
            if not chosen:
                for c in cards:
                    if c["card_type"] in message or message.strip() in (c["card_no"] or ""):
                        chosen = c; break
            if not chosen:
                lines = "\n".join([f"  {i+1}. {c['card_type']} {c['card_no']}" for i, c in enumerate(cards)])
                return {"reply": f"没选清楚，请回复序号或卡类型：\n{lines}", "ui": []}
            s.pending_slots["card_hint"] = chosen["card_type"]
            self.audit.log(sid, "clarify", {"filled": {"card": chosen["card_no"]}})
            # 直接规划执行挂失（红色，会走MFA）
            return self._replan_after_fill(sid)
        if field == "choose_payee":
            cands = s.pending_slots.get("candidates") or []
            chosen = None
            # 单个候选：用户说确认/是/对 -> 选中
            if len(cands) == 1 and re.match(r"^(确认|是|对|嗯|好的|可以|没问题)$", message.strip()):
                chosen = cands[0][0]
            # 按序号选
            elif re.match(r"^\d+$", message.strip()):
                idx = int(message.strip()) - 1
                if 0 <= idx < len(cands):
                    chosen = cands[idx][0]
            # 按姓名选
            else:
                for nm, ph in cands:
                    if nm in message or message.strip() in nm:
                        chosen = nm
                        break
                # 也可能用户直接给了完整新姓名
                if not chosen:
                    payee, how = intent_mod._extract_payee(message, contacts)
                    if payee:
                        chosen = payee
            if not chosen:
                lines = "\n".join([f"  {i+1}. {nm}（{ph}）" for i, (nm, ph) in enumerate(cands)])
                return {"reply": f"没选清楚，请回复序号或姓名：\n{lines}", "ui": []}
            s.pending_slots["to"] = chosen
            s.pending_slots["candidates"] = []
            self.audit.log(sid, "clarify", {"filled": {"to": chosen}})
            # 选完人后若金额缺失则追问金额
            if not s.pending_slots.get("amount"):
                s.awaiting = "clarify"
                s.clarify_for = (intent, "amount")
                return {"reply": f"好的，转给 {chosen}。请问转多少金额？（如 两千五 / 800）", "ui": []}
            # 金额已有，直接规划执行
            return self._replan_after_fill(sid)
        if field == "amount":
            from . import nlp
            amt = nlp.parse_amount(message)
            if not amt:
                return {"reply": "没识别到金额，请说具体数字，如 500 或 两千五。", "ui": []}
            s.pending_slots["amount"] = amt
            self.audit.log(sid, "clarify", {"filled": {"amount": amt}})
            return self._replan_after_fill(sid)
        return {"reply": "?", "ui": []}

    def _replan_after_fill(self, sid):
        """补完槽位后，把当前意图 + pending_rest 一起重规划（不丢多意图）。"""
        s = self._sess(sid)
        remaining = s.pending_rest or []
        # 保持原顺序：其余意图在前，刚补完的意图插在合适位置（简单起见放最后）
        full = list(remaining) + [(s.clarify_for[0], s.pending_slots)]
        s.pending_rest = []
        state = {"daily_transfer_total": s.daily_transfer_total}
        nodes = planner.plan(full, state)
        for n in nodes:
            n["risk"] = policy.risk_of(n["op"], n["args"], state)
            n["risk_label"] = policy.label(n["risk"])
        s.plan, s.idx = nodes, 0
        s.awaiting = None
        return self._execute_until_gate(sid)

    def _execute_until_gate(self, sid):
        """顺序执行节点，绿的直接跑，遇到黄/红停下出确认卡。
        每个节点执行前用最新 daily_transfer_total 重算风险（防拆分绕过）。"""
        s = self._sess(sid)
        replies, ui = [], []
        while s.idx < len(s.plan):
            node = s.plan[s.idx]
            if node["status"] != "pending":
                s.idx += 1
                continue
            # 实时重算风险（关键：第一笔转账执行后 daily_transfer_total 已变，第二笔要重算）
            fresh_state = {"daily_transfer_total": s.daily_transfer_total}
            fresh_risk = policy.risk_of(node["op"], node["args"], fresh_state)
            node["risk"] = fresh_risk
            node["risk_label"] = policy.label(fresh_risk)
            risk = fresh_risk
            if risk == "green":
                self._run_node(sid, node)
                replies.append(node.get("_result_msg", ""))
                s.idx += 1
                continue
            # 红色且本批已做过MFA → 直接执行（一次人脸确认多笔）
            if risk == "red" and s.mfa_approved:
                self._run_node(sid, node)
                replies.append(node.get("_result_msg", ""))
                s.idx += 1
                continue
            # 黄/红：停
            s.awaiting = "confirm"
            self.audit.log(sid, "gate", {"node": node["id"], "op": node["op"], "risk": risk, "desc": node["description"]})
            ui.append({
                "type": "confirm",
                "risk": risk,
                "risk_label": node["risk_label"],
                "title": node["description"],
                "need_mfa": risk == "red",
            })
            need = "强验证（短信/人脸）" if risk == "red" else "确认"
            reply = "\n".join([r for r in replies if r]) + \
                    f"\n\n⚠️ 上述操作需要您{need}：\n  → {node['description']}"
            return {"reply": reply, "ui": ui}
        # 全部完成
        s.plan, s.idx, s.awaiting = [], 0, None
        return {"reply": "\n".join([r for r in replies if r]) or "已完成。", "ui": ui}

    def _on_confirm(self, sid):
        s = self._sess(sid)
        if s.awaiting != "confirm" or not s.plan:
            return {"reply": "当前没有待确认的操作。", "ui": []}
        node = s.plan[s.idx]
        self.audit.log(sid, "confirm", {"op": node["op"]})
        if node["risk"] == "red":
            # 进入强验证：发短信
            code = self.mfa.send_sms(sid)
            s.awaiting = "mfa_sms"
            self.audit.log(sid, "mfa", {"send": "sms", "demo_code": code})
            return {"reply": f"🔐 该操作为高风险，已向您手机发送 6 位验证码（演示码：{code}）。请输入验证码完成验证。",
                    "ui": [{"type": "mfa_sms", "demo_code": code},
                           {"type": "mfa_face_button"}]}
        # 黄色：直接执行
        self._run_node(sid, node)
        msg = node.get("_result_msg", "")
        s.idx += 1
        return self._after_step(sid, msg)

    def _resume_after_mfa(self, sid):
        s = self._sess(sid)
        s.mfa_approved = True   # 本批MFA通过，后续红色节点直接执行
        node = s.plan[s.idx]
        self._run_node(sid, node)
        msg = node.get("_result_msg", "")
        s.idx += 1
        return self._after_step(sid, msg)

    def _after_step(self, sid, prev_msg):
        s = self._sess(sid)
        if s.idx >= len(s.plan):
            s.plan, s.idx, s.awaiting = [], 0, None
            self.breaker.record_success()
            return {"reply": (prev_msg + "\n✅ 全部操作已完成。").strip(), "ui": []}
        # 继续下一个节点
        return self._execute_until_gate(sid)

    def _run_node(self, sid, node):
        op = node["op"]
        args = node["args"]
        fn = service.DISPATCH.get(op)
        if fn is None:
            node["_result_msg"] = f"未知操作 {op}"
            node["status"] = "failed"
            return
        try:
            ok, msg, data = fn(args)
        except Exception as e:
            ok, msg, data = False, f"执行异常：{e}", None
        node["_result_msg"] = ("✅ " if ok else "❌ ") + msg
        node["status"] = "done" if ok else "failed"
        self.audit.log(sid, "execute", {"op": op, "risk": node["risk"], "ok": ok, "msg": msg})
        if ok and op == "transfer" and args.get("amount"):
            s = self._sess(sid)
            s.daily_transfer_total += args["amount"]
            # 记住收款人/金额，支持"再转200"多轮跟随
            s.last_payee = args.get("to") or s.last_payee
            s.last_payee_phone = args.get("to_phone") or s.last_payee_phone
            s.last_amount = args["amount"]
            s.last_intent = "transfer"

    def overview(self):
        c = service.query_balance()
        return {"balance": c[2]}

    def reset(self):
        from ..sandbox import data_sandbox as ds
        ds.reset()
        self.sessions.clear()
        self.audit.log("system", "reset", "数据已重置")
