"""主动聊天调度器 — 用户长时间不说话时，触发 AI 主动发消息

逻辑：
1. 每隔一段时间（默认 5 分钟）检查聊天记录
2. 如果距上条消息超过 (2小时 + 随机0~60分钟)，调用 AI
3. AI 决定是否主动发消息（用 send_message 工具）
4. 凌晨 12 点到 5 点不触发
5. 如果超过 7 天没聊，同时触发用户画像总结
"""

import asyncio
import json
import logging
import random
from datetime import datetime

logger = logging.getLogger(__name__)

# 配置
BASE_IDLE_MINUTES = 120    # 基础空闲时间 2 小时（分钟）
RANDOM_EXTRA_MINUTES = 60  # 额外随机 0~60 分钟
CHECK_INTERVAL = 300       # 每 300 秒（5 分钟）检查一次
PROFILE_DAYS = 7           # 超过 N 天触发画像总结
SILENT_START = 0           # 凌晨 0 点
SILENT_END = 5             # 到早上 5 点

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
        for msg in reversed(history):
            t = msg.get("time")
            if t:
                return datetime.fromisoformat(t)
        return None
    except Exception:
        return None


def _minutes_since_last_msg() -> float:
    """返回距上条消息过去了多少分钟"""
    last = _get_last_msg_time()
    if last is None:
        return float("inf")
    return (datetime.now() - last).total_seconds() / 60


def _is_silent_hours() -> bool:
    """当前是否在免打扰时段（凌晨 0~5 点）"""
    hour = datetime.now().hour
    return SILENT_START <= hour < SILENT_END


async def proactive_loop():
    """后台循环：检查空闲时间，触发 AI"""
    await asyncio.sleep(15)

    if _minutes_since_last_msg() > 24 * 60:
        logger.info("距上次聊天已超过 24 小时，缩短首次检查间隔")
        await asyncio.sleep(30)
    else:
        await asyncio.sleep(CHECK_INTERVAL)

    while True:
        try:
            now = datetime.now()

            # 免打扰时段跳过
            if _is_silent_hours():
                await asyncio.sleep(60)
                continue

            today = now.strftime("%Y-%m-%d")
            minutes = _minutes_since_last_msg()
            logger.debug("距上条消息 %.1f 分钟", minutes)

            # 每次检查时重新生成阈值，避免固定值
            idle_threshold = BASE_IDLE_MINUTES + random.randint(0, RANDOM_EXTRA_MINUTES)

            if minutes >= idle_threshold:
                check_key = f"proactive_{today}_{now.hour}"
                already = _LAST_CHECK.get(check_key, "")

                if not already:
                    _LAST_CHECK[check_key] = "done"
                    logger.info(
                        "用户已空闲 %.1f 分钟（阈值 %d 分钟），触发 AI 主动对话",
                        minutes, idle_threshold,
                    )

                    from agent.agent_core import agent_main

                    trigger = (
                        f"【主动触发】用户已经 {int(minutes)} 分钟没说话了。"
                        f"如果你想找用户聊聊天，可以用 send_message 工具发消息。"
                    )
                    if minutes >= PROFILE_DAYS * 24 * 60:
                        trigger += (
                            f" 另外已经超过 {PROFILE_DAYS} 天没总结画像了，"
                            f"也可以用 update_user_profile 总结一下。"
                        )

                    try:
                        result = agent_main(trigger, session_id="default")
                        logger.info("AI 主动回应: %.50s", result.get("text", ""))
                    except Exception as e:
                        logger.exception("AI 主动对话失败")

        except Exception as e:
            logger.warning("主动调度器异常: %s", e)

        await asyncio.sleep(CHECK_INTERVAL)
