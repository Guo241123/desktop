"""日志捕获器 — 捕获 logging 输出，存内存供前端查看"""

import logging
import threading
from collections import deque
from datetime import datetime


class LogCaptureHandler(logging.Handler):
    """将日志记录存入内存环形缓冲区"""

    def __init__(self, maxlen: int = 2000):
        super().__init__()
        self.buffer: deque[dict] = deque(maxlen=maxlen)
        self.lock = threading.Lock()

    def emit(self, record: logging.LogRecord):
        entry = {
            "time": datetime.fromtimestamp(record.created).strftime("%H:%M:%S"),
            "level": record.levelname,
            "name": record.name,
            "message": record.getMessage(),
        }
        with self.lock:
            self.buffer.append(entry)

    def get_logs(self, level: str = "", keyword: str = "", limit: int = 200):
        with self.lock:
            logs = list(self.buffer)
        if level:
            logs = [r for r in logs if r["level"] == level.upper()]
        if keyword:
            logs = [r for r in logs if keyword.lower() in r["message"].lower()]
        return logs[-limit:]


# ── 全局单例 ──
capture_handler = LogCaptureHandler()


def install():
    """安装日志捕获（添加内存 Handler）"""
    root = logging.getLogger()
    if capture_handler not in root.handlers:
        root.handlers.append(capture_handler)


def get_logs(level: str = "", keyword: str = "", limit: int = 200):
    return capture_handler.get_logs(level, keyword, limit)
