# -*- coding: utf-8 -*-
"""操作审计：全链路留痕 + SHA-256 哈希链（防篡改），环形缓冲。"""
import hashlib
import json
import time


def _hash_prev(prev_hash, entry_dict):
    """对上一条哈希 + 当前记录内容做 SHA-256，形成链式结构。"""
    s = prev_hash + json.dumps(entry_dict, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(s.encode("utf-8")).hexdigest()[:16]


class Audit:
    def __init__(self, capacity=2000):
        self.buf = []
        self.capacity = capacity
        self.seq = 0
        self.prev_hash = "GENESIS"

    def log(self, session_id, event_type, detail):
        self.seq += 1
        body = {
            "id": self.seq,
            "ts": time.strftime("%Y-%m-%d %H:%M:%S"),
            "session_id": session_id,
            "event": event_type,
            "detail": detail if isinstance(detail, str) else json.dumps(detail, ensure_ascii=False),
        }
        body["hash"] = _hash_prev(self.prev_hash, body)
        self.prev_hash = body["hash"]
        self.buf.append(body)
        if len(self.buf) > self.capacity:
            self.buf.pop(0)
        return body

    def recent(self, limit=50):
        return list(reversed(self.buf[-limit:]))

    def verify_chain(self):
        """校验哈希链完整性：返回 (ok, tampered_count)。"""
        prev = "GENESIS"
        bad = 0
        for e in self.buf:
            expect = _hash_prev(prev, {k: v for k, v in e.items() if k != "hash"})
            if expect != e.get("hash"):
                bad += 1
            prev = e.get("hash", prev)
        return bad == 0, bad
