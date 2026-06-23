"""主动聊天调度器 — 用户长时间不说话时，触发 AI 主动发消息

逻辑：
1. 每隔一段时间（默认 5 分钟）检查聊天记录
2. 如果距上条消息超过空闲阈值（默认 2 小时），调用 AI
3. AI 决定是否主动发消息（用 send_message 工具）
4. 如果超过 7 天没聊，同时触发用户画像总结
"""

import asyncio
import json
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

# 配置
IDLE_HOURS = 2          # 空闲超过 N 小时触发 AI
CHECK_INTERVAL = 300    # 每 300 秒（5 分钟）检查一次
PROFILE_DAYS = 7        # 超过 N 天触发画像总结

_LAST_CHECK: dict[str, str] = {}  # 避免重复触发


def _get_last_msg_time() -> datetime | None:
    """从聊天历史中获取最后一条消息的时间"""
    try:
        from memory.chat_memory import get_memory_file
        path = get_memory_file("default")
        with open(path, "r", encoding="utf-8") as f:
            history = json.load(f)
        if not history:
            return None
        # 从后往前找有 time 字段的消息
        for msg in reversed(history):
            t = msg.get("time")
            if t:
                return datetime.fromisoformat(t)
        return None
    except Exception:
        return None


def _hours_since_last_msg() -> float:
    """返回距上条消息过去了多少小时"""
    last = _get_last_msg_time()
    if last is None:
        return float("inf")
    return (datetime.now() - last).total_seconds() / 3600


async def proactive_loop():
    """后台循环：检查空闲时间，触发 AI"""
    # 启动等一会
    await asyncio.sleep(15)

    if _hours_since_last_msg() > 24:
        logger.info("距上次聊天已超过 24 小时，缩短首次检查间隔")
        await asyncio.sleep(30)
    else:
        await asyncio.sleep(CHECK_INTERVAL)

    while True:
        try:
            today = datetime.now().strftime("%Y-%m-%d")
            hours = _hours_since_last_msg()
            logger.debug("距上条消息 %.1f 小时", hours)

            if hours >= IDLE_HOURS:
                # 检查今天是否已经触发过
                check_key = f"proactive_{today}"
                already = _LAST_CHECK.get(check_key, "")

                if not already:
                    _LAST_CHECK[check_key] = "done"
                    logger.info("用户已空闲 %.1f 小时，触发 AI 主动对话", hours)

                    from agent.agent_core import agent_main

                    trigger = (
                        f"【主动触发】用户已经 {int(hours)} 小时没说话了。"
                        f"如果你想找用户聊聊天，可以用 send_message 工具发消息。"
                    )
                    if hours >= PROFILE_DAYS * 24:
                        trigger += (
                            f" 另外已经超过 {PROFILE_DAYS} 天没总结画像了，"
                            f"也可以用 update_user_profile 总结一下。"
                        )

                    try:
                        result = agent_main(trigger, session_id="default")
                        logger.info("AI 主动回应: %.50s", result.get("text", ""))
                    except Exception as e:
                        logger.exception("AI 主动对话失败: %s")

        except Exception as e:
            logger.warning("主动调度器异常: %s", e)

        await asyncio.sleep(CHECK_INTERVAL)
