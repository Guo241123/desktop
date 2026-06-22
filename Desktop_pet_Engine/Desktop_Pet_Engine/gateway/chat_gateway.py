# Gateway层 - 聊天入口
import logging
from fastapi import APIRouter
from gateway.schema import ChatRequest, ChatResponse
from agent.agent_core import agent_main

logger = logging.getLogger(__name__)

chat_router = APIRouter(prefix="/api/data", tags=["聊天接口"])


@chat_router.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest):
    logger.info("接收到: %s", req)
    resp_data = agent_main(f"[桌面] {req.message}", req.session_id)
    logger.info("回复: %.100s", resp_data.get("text", ""))
    return resp_data
