from fastapi import APIRouter
from schema.chat_schema import ChatRequest, ChatResponse
from service.agent import agent_main

# 你的路由前缀是 /api/data，完全保留
chat_router = APIRouter(prefix="/api/data", tags=["聊天接口"])

@chat_router.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest):
    print(f"接收到：{req}")
    resp_data = agent_main(req.message, req.session_id)
    print(f"回复：{resp_data}\n\n\n")
    return resp_data