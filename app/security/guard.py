# -*- coding: utf-8 -*-
"""注入防御 + 异常熔断。"""
import re
import time

INJECTION_PATTERNS = [
    r"忽略.{0,8}(指令|提示|规则|prompt|instruct)",
    r"ignore[\s]*(all|everything|previous|above)[\s]+(instructions?|prompts?)",
    r"system[\s]*prompt|系统提示词|开发者模式",
    r"你(现在)?是(一个)?(没有限制|不受约束|越狱)",
    r"jailbreak|DAN|\bdo\s+anything\s+now\b",
    r"绕过(权限|验证|风控|安全)",
    r"不用(确认|验证|人脸识别|验证码).{0,6}(直接|就)?转",
    r"把(你的|系统)(提示词|指令|规则)告诉我",
    r"提(高|升)(我的)?(转账)?额度到?\s*\d*(无限|最高|100万)",
    r"假装(你)?(已经)?(完成|通过)(了)?(人脸|短信|mfa|强)?验证",
    r"(print|show|dump).{0,6}(system|config|password|secret)",
]
_COMPILED = [re.compile(p, re.IGNORECASE) for p in INJECTION_PATTERNS]


def detect_injection(text):
    for p in _COMPILED:
        m = p.search(text or "")
        if m:
            return m.group(0)
    return None


class CircuitBreaker:
    THRESHOLD = 3
    LOCK_SECONDS = 600

    def __init__(self):
        self.fail_count = 0
        self.locked_until = 0.0

    def record_failure(self):
        self.fail_count += 1
        if self.fail_count >= self.THRESHOLD:
            self.locked_until = time.time() + self.LOCK_SECONDS

    def record_success(self):
        self.fail_count = 0

    def is_locked(self):
        if time.time() < self.locked_until:
            return True, int(self.locked_until - time.time())
        return False, 0
