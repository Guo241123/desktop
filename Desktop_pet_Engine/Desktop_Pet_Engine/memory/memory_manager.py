# Memory层 - 记忆统一管理接口
from memory.chat_memory import load_memory, save_memory, clear_memory
from memory.vector_store import get_session_vector, save_chat_record
from datetime import datetime


class MemoryManager:
    """记忆管理器 - 统一管理聊天记忆和向量存储"""

    def __init__(self, session_id: str = "default"):
        self.session_id = session_id

    def load_chat_history(self) -> list:
        """加载聊天历史"""
        return load_memory(self.session_id)

    def save_chat_history(self, chat_history: list):
        """保存聊天历史"""
        save_memory(self.session_id, chat_history)

    def add_message(self, role: str, content: str):
        """添加一条消息到历史"""
        chat_history = self.load_chat_history()
        chat_history.append({
            "role": role,
            "content": content,
            "time": datetime.now().isoformat(timespec="seconds"),
        })
        self.save_chat_history(chat_history)

    def save_record(self, user_text: str, ai_text: str):
        """保存对话记录到向量存储"""
        save_chat_record(self.session_id, user_text, ai_text)

    def compress_memory(self, keep_last: int = 20):
        """压缩聊天历史，只保留最近 keep_last 条消息，减少 token 消耗"""
        chat_history = self.load_chat_history()
        if len(chat_history) <= keep_last:
            return False
        chat_history = chat_history[-keep_last:]
        self.save_chat_history(chat_history)
        return True

    def clear(self):
        """清除所有记忆"""
        clear_memory(self.session_id)