# Agent层 - 模型配置
import os
import ssl
from pathlib import Path
from langchain_openai import OpenAIEmbeddings, ChatOpenAI

ssl._create_default_https_context = ssl._create_unverified_context

# ── Load .env ──────────────────────────────────────────────────
_env_path = Path(__file__).resolve().parent.parent / ".env"
_env_vars = {}
if _env_path.exists():
    for line in _env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, _, value = line.partition("=")
            _env_vars[key.strip()] = value.strip()

def _get_env(key: str, default: str = "") -> str:
    return os.environ.get(key, _env_vars.get(key, default))

# ── Models ──────────────────────────────────────────────────────

def get_chat_model():
    """获取聊天模型"""
    return ChatOpenAI(
        api_key=_get_env("DEEPSEEK_API_KEY"),
        base_url=_get_env("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1"),
        model=_get_env("CHAT_MODEL", "deepseek-v4-pro"),
        temperature=0.7,
    )

def get_embedding_model():
    """获取 Embedding 模型"""
    return OpenAIEmbeddings(
        api_key=_get_env("SILICONFLOW_API_KEY"),
        base_url=_get_env("SILICONFLOW_BASE_URL", "https://api.siliconflow.cn/v1/"),
        model=_get_env("EMBEDDING_MODEL", "BAAI/bge-m3"),
    )