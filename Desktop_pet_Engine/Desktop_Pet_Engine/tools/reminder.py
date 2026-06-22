"""提醒工具 — Agent 可调用 set_reminder 设置定时提醒"""

import json
import time
from langchain_core.tools import tool
from config.paths import REMINDERS_FILE


@tool
def set_reminder(delay_seconds: int, message: str) -> str:
    """
    设置一个定时提醒。
    delay_seconds: 多少秒后提醒（如 3600 = 1小时）
    message: 提醒内容（如 "喝水"、"该休息了"）
    """
    try:
        trigger_time = time.time() + delay_seconds
        reminders = []
        if REMINDERS_FILE.exists():
            reminders = json.loads(REMINDERS_FILE.read_text(encoding="utf-8"))

        reminders.append({
            "trigger_time": trigger_time,
            "message": message,
            "created_at": time.time(),
        })
        REMINDERS_FILE.write_text(json.dumps(reminders, ensure_ascii=False, indent=2), encoding="utf-8")

        # 转成可读的时间描述
        if delay_seconds < 60:
            desc = f"{delay_seconds}秒"
        elif delay_seconds < 3600:
            desc = f"{delay_seconds // 60}分钟"
        else:
            desc = f"{delay_seconds // 3600}小时"

        return f"已设置 {desc} 后提醒：{message}"
    except Exception as e:
        return f"设置提醒失败: {e}"
