# -*- coding: utf-8 -*-
"""
代码沙箱：用户/Agent 生成的任何 Python 代码都在此受限环境执行。
- 独立子进程、超时强杀
- 禁止 import os / subprocess / socket / open 系统文件
- 完全替换 __builtins__，仅暴露白名单函数（防 getattr(__builtins__,'eval') 逃逸）
返回 (ok, stdout, stderr)。
"""
import os
import sys
import re
import shutil
import tempfile
import subprocess
import textwrap

_BLOCKED_IMPORTS = ("os", "subprocess", "socket", "shutil", "requests", "urllib",
                    "ctypes", "multiprocessing", "threading", "importlib", "sys",
                    "builtins", "importlib", "pickle", "ctypes")

# 静态扫描：直接出现在源码里就拒绝的危险词
_BLOCKED_TOKENS = (
    "__import__", "eval(", "exec(", "compile(", "open(", "input(",
    "globals(", "locals(", "vars(", "getattr(", "setattr(", "delattr(",
    "__builtins__", "__class__", "__bases__", "__subclasses__",
    "__mro__", "__dict__", "__reduce__", "breakpoint(", "help(",
    "memoryview(", "breakpoint", "compile",
)

# 给沙箱内暴露的受限 builtins —— 完全重建，不继承全局
_SAFE_BUILTINS = """
import math as _math
_safe = {}
for name in ['print','len','range','int','float','str','round','abs','sum','min','max',
             'sorted','enumerate','zip','map','filter','list','dict','tuple','set',
             'bool','isinstance','type','repr','divmod','hash','chr','ord','hex',
             'oct','bin','repr','slice','reversed','iter','next','all','any',
             'True','False','None','Exception','ValueError','TypeError',
             'KeyError','IndexError','ZeroDivisionError','ArithmeticError']:
    try:
        _safe[name] = eval('__builtins__.' + name) if isinstance(__builtins__, dict) else getattr(__builtins__, name)
    except Exception:
        pass
for n in ['sqrt','pow','sin','cos','pi','e','floor','ceil','log','log10','exp']:
    _safe[n] = getattr(_math, n)
# 关键：把当前全局命名空间的 __builtins__ 整个替换成受限字典
import builtins as _b
import sys as _sys
# 屏蔽危险模块
for _m in ['os','subprocess','socket','shutil','sys','importlib','builtins',
           'ctypes','multiprocessing','threading','pickle','io']:
    _sys.modules[_m] = None
# 直接重写 __builtins__
__builtins__ = _safe
"""


def run_code(code: str, timeout: int = 5):
    """在沙箱里执行一段用户/Agent 生成的代码。"""
    # 静态扫描 1：禁止危险 import
    for mod in _BLOCKED_IMPORTS:
        if re.search(rf"^\s*(import|from)\s+{mod}\b", code, re.MULTILINE):
            return False, "", f"代码沙箱拒绝：禁止 import 模块 '{mod}'（安全隔离）"
    # 静态扫描 2：禁止危险 dunder / 内建函数名（防 __import__('os')、eval(...) 等）
    for tok in _BLOCKED_TOKENS:
        if tok in code:
            return False, "", f"代码沙箱拒绝：源码包含受限标识符 '{tok}'（安全隔离）"
    workdir = tempfile.mkdtemp(prefix="code_sandbox_")
    script = os.path.join(workdir, "user_code.py")
    full = _SAFE_BUILTINS + "\n" + textwrap.dedent(code)
    with open(script, "w", encoding="utf-8") as f:
        f.write(full)
    try:
        proc = subprocess.run(
            [sys.executable, "-I", script],
            capture_output=True, text=True, timeout=timeout, cwd=workdir,
            env={"PATH": os.environ.get("PATH", ""), "PYTHONIOENCODING": "utf-8"},
        )
        ok = proc.returncode == 0
        return ok, proc.stdout[-4000:], (proc.stderr[-2000:] if not ok else "")
    except subprocess.TimeoutExpired:
        return False, "", f"代码沙箱超时：执行超过 {timeout}s，已强制终止"
    finally:
        shutil.rmtree(workdir, ignore_errors=True)
