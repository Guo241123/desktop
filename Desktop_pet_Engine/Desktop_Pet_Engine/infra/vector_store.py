from langchain_community.vectorstores import FAISS
from config.ai_config import get_embedding_model
import os

# 存储到本地文件夹：vector_db/ 目录下
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PERSIST_DIR = os.path.join(BASE_DIR, "../vector_db")


def get_session_vector(session_id: str = "default"):
    # 每个用户一个独立文件夹
    user_dir = os.path.join(PERSIST_DIR, session_id)

    if os.path.exists(user_dir):
        # 加载本地已有的记忆 → 【修复点：增加安全参数】
        emb = get_embedding_model()
        store = FAISS.load_local(user_dir, emb, allow_dangerous_deserialization=True)
    else:
        # 新建记忆
        emb = get_embedding_model()
        store = FAISS.from_texts(["初始会话：用户和UU助手开始聊天"], emb)
        store.save_local(user_dir)

    return store


# 保存对话（自动同步到本地文件）
def save_chat_record(session_id: str, user_text: str, ai_text: str):
    user_dir = os.path.join(PERSIST_DIR, session_id)
    vec_store = get_session_vector(session_id)
    content = f"用户：{user_text}\n助手：{ai_text}"
    vec_store.add_texts([content])
    vec_store.save_local(user_dir)