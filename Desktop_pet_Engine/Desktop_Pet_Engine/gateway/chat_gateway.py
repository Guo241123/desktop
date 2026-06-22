# Gateway层 - 聊天入口
from fastapi import APIRouter
from gateway.schema import ChatRequest, ChatResponse
from agent.agent_core import agent_main

chat_router = APIRouter(prefix="/api/data", tags=["聊天接口"])

@chat_router.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest):
    print(f"接收到：{req}")
    resp_data = agent_main(f"[桌面] {req.message}", req.session_id)
    print(f"回复：{resp_data}\n\n\n")
    return resp_data