from pydantic import BaseModel

class ChatRequest(BaseModel):
    session_id: str
    message: str
    channel: str

class ChatResponse(BaseModel):
    text: str
    mood: str
    emoji: str

class SaveRequest(BaseModel):
    env: dict
    local: dict = {}