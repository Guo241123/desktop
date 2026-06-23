# Gateway层 - 聊天入口
import logging
from fastapi import APIRouter
from gateway.schema import ChatRequest, ChatResponse
from agent.agent_core import agent_main

logger = logging.getLogger(__name__)

chat_router = APIRouter(prefix="/api/data", tags=["聊天接口"])


def chat_with_agent(message: str, session_id: str = "001", system_prompt: str = None) -> str:
    """聊天入口（网关层统一函数，HTTP 和内部通道都走这里）"""
    result = agent_main(message, session_id=session_id, system_prompt=system_prompt)
    return result.get("text", "")


@chat_router.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest):
    logger.info("接收到: %s", req)
    resp_data = agent_main(f"[桌面] {req.message}", req.session_id)
    logger.info("回复: %.100s", resp_data.get("text", ""))
    return resp_data
