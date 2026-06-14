
from langchain_core.tools import tool
from config.ai_config import get_chat_model, SYSTEM_PROMPT
from infra.vector_store import get_session_vector, save_chat_record
from langchain_classic.chains import ConversationalRetrievalChain
import json

# ------------------------------
# 1. 你原来的 chain 原封不动！
# ------------------------------
def get_rag_chain(session_id="default"):
    llm = get_chat_model()
    vec_store = get_session_vector(session_id)
    retriever = vec_store.as_retriever(search_kwargs={"k": 5})

    # 你的 chain 完好保留！！！
    chain = ConversationalRetrievalChain.from_llm(
        llm=llm,
        retriever=retriever,
        return_source_documents=False
    )
    return chain

# ------------------------------
# 2. 把 chain 包装成工具
# ------------------------------
@tool
def rag_tool(question: str, session_id: str = "default"):
    """
    用于查询知识库、历史聊天记录的工具
    只有需要检索资料时才调用这个工具
    """
    chain = get_rag_chain(session_id)
    result = chain.invoke({
        "question": question,
        "chat_history": []
    })
    return result["answer"]