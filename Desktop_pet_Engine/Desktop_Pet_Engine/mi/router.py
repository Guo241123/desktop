"""MI 层 — 消息路由

接收外部通道的消息，调用 Gateway 处理，返回回复。
"""

import json
import logging

logger = logging.getLogger(__name__)


async def route_to_agent(
    session_id: str,
    message: str,
    user_id: str = "",
    system_prompt: str = None,
) -> str:
    """将消息路由到 Gateway（再转发到 Agent），返回回复文本"""
    try:
        # 懒加载避免循环导入（tools → mi → router → gateway → agent → tools）
        from gateway.chat_gateway import chat_with_agent
        result = chat_with_agent(message, session_id=session_id, system_prompt=system_prompt)
        return result
    except Exception as e:
        logger.exception("路由消息到 Agent 失败: %s", e)
        return f"服务出错啦，稍后再试~"
