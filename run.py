# -*- coding: utf-8 -*-
"""启动入口：初始化数据库 -> 启动 Web 服务 -> 自动打开浏览器。"""
import os
import sys
import threading
import time
import webbrowser

import uvicorn

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

HOST = "127.0.0.1"
PORT = 8000


def open_browser():
    time.sleep(1.2)
    webbrowser.open(f"http://{HOST}:{PORT}/")


if __name__ == "__main__":
    from app.bank import db
    db.init_db(force=False)
    print("=" * 50)
    print("  智银 · AI Banking Agent 已启动")
    print(f"  访问地址: http://{HOST}:{PORT}/")
    print("  按 Ctrl+C 停止")
    print("=" * 50)
    threading.Thread(target=open_browser, daemon=True).start()
    uvicorn.run(app="app.main:app", host=HOST, port=PORT, log_level="warning")
