from pydantic import BaseModel
class ChatRequest(BaseModel):
    message: str
    session_id: str = "default"  # 必须带上此字段
class ChatResponse(BaseModel):
    text: str
    mood: str
    emoji: str