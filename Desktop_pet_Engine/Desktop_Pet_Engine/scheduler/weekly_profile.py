"""每周用户画像总结 + 记忆压缩 — 全局后台任务

触发时机：
1. 启动时：如果距上次更新超过 7 天，启动后 5 分钟触发
2. 运行时：每周日凌晨 12 点自动触发

调用 AI 总结用户画像 5 个维度，update_user_profile 工具会自动压缩聊天记忆。
"""

import asyncio
import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

_LAST_RUN_DATE: str = ""  # 避免一天内重复触发


async def _run_profile_summary():
    """执行一次用户画像总结"""
    global _LAST_RUN_DATE
    today_str = datetime.now().strftime("%Y-%m-%d")
    if _LAST_RUN_DATE == today_str:
        return  # 今天已经跑过了
    _LAST_RUN_DATE = today_str

    logger.info("🕐 触发用户画像总结")
    try:
        from agent.agent_core import agent_main

        trigger_msg = (
            "【每周总结】回顾一下最近的聊天记录，"
            "用 update_user_profile 工具总结用户画像到 5 个维度"
            "（个人信息、性格风格兴趣、MBTI 维度、喜好雷点、相处建议）。"
        )
        result = agent_main(trigger_msg, session_id="default")
        reply_text = result.get("text", "")
        logger.info("每周画像总结完成: %.50s", reply_text)

        # 如果微信通道在线，通知用户
        try:
            from mi.manager import channel_manager
            ch = channel_manager.get("wechat")
            if ch and ch._api and ch._last_user_id:
                await ch._api.send_message(
                    ch._last_user_id, ch._last_context_token,
                    "📋 本周的用户画像已经总结好啦~"
                )
        except Exception:
            pass

    except Exception as e:
        logger.exception("每周画像总结失败: %s", e)


def _days_since_last_update() -> int:
    """返回距上次画像更新过了多少天"""
    try:
        from memory.user_profile import load_profile
        profile = load_profile()
        last_str = profile.get("last_updated", "")
        if not last_str:
            return 999
        last = datetime.fromisoformat(last_str)
        return (datetime.now() - last).days
    except Exception:
        return 999


async def weekly_profile_loop():
    """全局后台循环"""
    # ── 启动延迟，等通道初始化 ──
    await asyncio.sleep(10)

    # ── 启动时检查：距上次更新超过 7 天则触发 ──
    days_since = _days_since_last_update()
    if days_since >= 7:
        logger.info("距上次画像更新 %d 天，启动后触发总结", days_since)
        await asyncio.sleep(300)  # 等 5 分钟让一切就绪
        await _run_profile_summary()

    # ── 正常循环：周日 24:00 窗口 + 定时检查 ──
    while True:
        try:
            now = datetime.now()

            # 周日 23:55 ~ 周一 00:10 窗口
            is_window = (
                (now.weekday() == 6 and now.hour == 23 and now.minute >= 55)
                or (now.weekday() == 0 and now.hour == 0 and now.minute < 10)
            )

            if is_window:
                await _run_profile_summary()

        except Exception as e:
            logger.warning("每周画像调度器异常: %s", e)

        await asyncio.sleep(60)
