# Gateway层 - 数据模型定义
from pydantic import BaseModel

class ChatRequest(BaseModel):
    message: str
    session_id: str = "default"

class ChatResponse(BaseModel):
    text: str
    mood: str
    emoji: str

class SaveRequest(BaseModel):
    env: dict
    local: dict = {}