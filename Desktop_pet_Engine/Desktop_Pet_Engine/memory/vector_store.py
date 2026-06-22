"""Memory层 - 向量存储（FAISS）

将对话记录转为向量存入 FAISS 索引，用于长期记忆检索。
"""

import os
from langchain_community.vectorstores import FAISS
from agent.model_config import get_embedding_model
from config.paths import VECTOR_DB_DIR, ensure_dirs

ensure_dirs()


def get_session_vector(session_id: str = "default"):
    """获取指定 session 的向量存储"""
    try:
        user_dir = os.path.join(VECTOR_DB_DIR, session_id)
        emb = get_embedding_model()

        if os.path.exists(user_dir):
            store = FAISS.load_local(user_dir, emb, allow_dangerous_deserialization=True)
        else:
            store = FAISS.from_texts(["初始会话：用户和UU助手开始聊天"], emb)
            store.save_local(user_dir)

        return store
    except Exception as e:
        print(f"Vector store error: {e}")
        return None


def save_chat_record(session_id: str, user_text: str, ai_text: str):
    """保存对话记录到向量存储"""
    try:
        user_dir = os.path.join(VECTOR_DB_DIR, session_id)
        vec_store = get_session_vector(session_id)
        if vec_store:
            content = f"用户：{user_text}\n助手：{ai_text}"
            vec_store.add_texts([content])
            vec_store.save_local(user_dir)
    except Exception as e:
        print(f"Save chat record error: {e}")
