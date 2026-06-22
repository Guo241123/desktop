"""Memory层 - 聊天记忆管理（JSON文件存储）"""

import json
from config.paths import CHAT_MEMORY_DIR, ensure_dirs

ensure_dirs()


def get_memory_file(session_id: str) -> str:
    """获取指定 session 的记忆文件路径"""
    return str(CHAT_MEMORY_DIR / f"{session_id}.json")


def load_memory(session_id: str) -> list:
    """加载指定 session 的聊天历史"""
    file = get_memory_file(session_id)
    if not CHAT_MEMORY_DIR.joinpath(f"{session_id}.json").exists():
        return []
    try:
        with open(file, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []


def save_memory(session_id: str, chat_history: list):
    """保存指定 session 的聊天历史"""
    file = get_memory_file(session_id)
    try:
        with open(file, "w", encoding="utf-8") as f:
            json.dump(chat_history, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"Save memory error: {e}")


def clear_memory(session_id: str):
    """清除指定 session 的聊天历史"""
    file = get_memory_file(session_id)
    if CHAT_MEMORY_DIR.joinpath(f"{session_id}.json").exists():
        CHAT_MEMORY_DIR.joinpath(f"{session_id}.json").unlink()
