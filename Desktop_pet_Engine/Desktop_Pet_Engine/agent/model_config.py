"""Agent层 — 模型配置

聊天模型（DeepSeek / OpenAI 兼容）和 Embedding 模型（SiliconFlow）的工厂函数。
环境变量通过 config.settings 统一读取。
"""

import ssl
from langchain_openai import OpenAIEmbeddings, ChatOpenAI
from config import get_env

ssl._create_default_https_context = ssl._create_unverified_context


def get_chat_model():
    """获取聊天模型实例"""
    return ChatOpenAI(
        api_key=get_env("DEEPSEEK_API_KEY"),
        base_url=get_env("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1"),
        model=get_env("CHAT_MODEL", "deepseek-v4-pro"),
        temperature=float(get_env("TEMPERATURE", "0.7")),
    )


def get_embedding_model():
    """获取 Embedding 模型实例"""
    return OpenAIEmbeddings(
        api_key=get_env("SILICONFLOW_API_KEY"),
        base_url=get_env("SILICONFLOW_BASE_URL", "https://api.siliconflow.cn/v1/"),
        model=get_env("EMBEDDING_MODEL", "BAAI/bge-m3"),
    )
