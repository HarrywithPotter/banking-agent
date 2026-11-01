# -*- coding: utf-8 -*-
"""强验证（MFA）：短信验证码 + 人脸，模拟实现，演示用。"""
import random
import time


class MFA:
    def __init__(self):
        self._codes = {}   # session_id -> {code, exp, step_id}

    def send_sms(self, session_id):
        code = f"{random.randint(100000, 999999)}"
        self._codes[session_id] = {"code": code, "exp": time.time() + 300}
        return code  # 演示回显（生产移除）

    def verify_sms(self, session_id, code):
        rec = self._codes.get(session_id)
        if not rec:
            return False, "无待校验验证码"
        if time.time() > rec["exp"]:
            return False, "验证码已过期"
        if rec["code"] != str(code).strip():
            return False, "验证码错误"
        del self._codes[session_id]
        return True, "短信验证通过"

    def verify_face(self):
        # 模拟人脸识别（总是成功，演示用）
        return True, "人脸识别通过（演示模拟）"
