# -*- coding: utf-8 -*-
"""
数据沙箱：
- 所有银行核心读写都经过此处，业务代码不得裸连 SQLite。
- 全部参数化查询，天然防 SQL 注入。
- dry_run=True 时只校验不落库（用于"待确认"阶段预演）。
- 与生产系统物理隔离：本库是独立演示库，可一键重置。
"""
import sqlite3
import threading
from ..bank import db

_lock = threading.Lock()


def query(sql, params=()):
    conn = db.get_conn()
    try:
        rows = conn.execute(sql, params).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def query_one(sql, params=()):
    rows = query(sql, params)
    return rows[0] if rows else None


def execute(sql, params=(), dry_run=False):
    """写操作。dry_run=True 时只做事务回滚，不落库。
    始终返回 (ok: bool, rowcount: int)——失败时 rowcount=0。"""
    # 禁止 DDL / 危险语句（数据沙箱只允许 DML）
    _u = sql.strip().upper()
    if any(_u.startswith(k) for k in ("DROP", "ALTER", "CREATE", "PRAGMA", "ATTACH", "DETACH")):
        return False, 0
    if dry_run:
        conn = db.get_conn()
        try:
            conn.execute("BEGIN")
            cur = conn.execute(sql, params)
            conn.rollback()
            return True, cur.rowcount
        except Exception:
            conn.rollback()
            return False, 0
        finally:
            conn.close()
    with _lock:
        conn = db.get_conn()
        try:
            cur = conn.execute(sql, params)
            conn.commit()
            return True, cur.rowcount
        except Exception:
            conn.rollback()
            return False, 0
        finally:
            conn.close()


def reset():
    db.init_db(force=True)
