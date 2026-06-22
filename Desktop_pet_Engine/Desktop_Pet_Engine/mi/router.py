"""MI 层 — 消息路由

接收外部通道的消息，调用 Agent 处理，返回回复。
"""

import json
import logging
from agent.agent_core import agent_main

logger = logging.getLogger(__name__)


async def route_to_agent(
    session_id: str,
    message: str,
    user_id: str = "",
    system_prompt: str = None,
) -> str:
    """将消息路由到 Agent 处理，返回回复文本"""
    try:
        result = agent_main(message, session_id=session_id, system_prompt=system_prompt)
        # result 是 {"text": "...", "mood": "...", "emoji": "...", "tool": "..."}
        return result.get("text", "")
    except Exception as e:
        logger.exception("路由消息到 Agent 失败: %s", e)
        return f"服务出错啦，稍后再试~"
