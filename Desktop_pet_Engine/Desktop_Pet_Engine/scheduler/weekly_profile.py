"""每周用户画像总结 + 记忆压缩 — 全局后台任务

每周日凌晨 12 点自动触发，调用 AI 总结用户画像 5 个维度，
update_user_profile 工具会自动压缩聊天记忆。
"""

import asyncio
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

_LAST_RUN_DATE: str = ""  # 避免一天内重复触发


async def weekly_profile_loop():
    """全局后台循环，每周日 24:00 触发一次画像总结"""
    global _LAST_RUN_DATE

    while True:
        try:
            now = datetime.now()

            # 周日 23:55 ~ 周一 00:10 窗口
            is_window = (
                (now.weekday() == 6 and now.hour == 23 and now.minute >= 55)
                or (now.weekday() == 0 and now.hour == 0 and now.minute < 10)
            )

            today_str = now.strftime("%Y-%m-%d")
            # 用一个固定 key 判断今天是否已触发过
            check_date = today_str if now.hour == 0 else (
                # 如果是周日 23:55+，记为下周一（避免跨天重复）
                datetime(now.year, now.month, now.day).strftime("%Y-%m-%d")
                if now.weekday() == 0 or (now.weekday() == 6 and now.hour >= 23)
                else today_str
            )

            if is_window and _LAST_RUN_DATE != check_date:
                _LAST_RUN_DATE = check_date
                logger.info("🕐 每周画像总结触发")

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

        except Exception as e:
            logger.warning("每周画像调度器异常: %s", e)

        await asyncio.sleep(60)
