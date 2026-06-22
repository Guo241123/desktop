"""
RAG 检索链（旧版模块路径，暂不可用）
保留此文件避免自动注册时报错。
"""

from langchain_core.tools import tool

# 旧模块路径已废弃，加载失败时静默跳过
try:
    from config.ai_config import get_chat_model, SYSTEM_PROMPT
    from infra.vector_store import get_session_vector, save_chat_record
    from langchain_classic.chains import ConversationalRetrievalChain
    _HAS_DEPS = True
except ImportError:
    _HAS_DEPS = False
