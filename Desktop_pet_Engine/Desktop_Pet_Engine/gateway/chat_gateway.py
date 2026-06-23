# Gateway层 - 统一聊天入口
import logging
import asyncio
from fastapi import APIRouter, HTTPException
from gateway.schema import ChatRequest, ChatResponse
from agent.agent_core import agent_main

logger = logging.getLogger("gateway_chat")
chat_router = APIRouter(prefix="/api/data", tags=["统一消息网关"])


@chat_router.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest):
    logger.info(f"渠道:{req.channel} 会话:{req.session_id} 消息片段:{req.message[:80]}")
    try:
        full_input = f"[{req.channel}] {req.message}"
        ai_result = await asyncio.to_thread(agent_main, full_input, req.session_id)
        reply_text = ai_result.get("text", "")
        logger.info(f"渠道{req.channel} AI回复片段:{reply_text[:100]}")
        return ChatResponse(
            text=ai_result.get("text", ""),
            mood=ai_result.get("mood", ""),
            emoji=ai_result.get("emoji", "")
        )
    except Exception as e:
        logger.exception("AI处理消息异常")
        raise HTTPException(status_code=500, detail=f"服务异常：{str(e)}")
