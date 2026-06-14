import ssl, httpx
ssl._create_default_https_context = ssl._create_unverified_context
from langchain_openai import OpenAIEmbeddings, ChatOpenAI

def get_chat_model():
    return ChatOpenAI(
        api_key="sk-7ea8ea6543864b6cba9d63346d21bba9",
        base_url="https://api.deepseek.com/v1",      # ← 必须带 /v1
        model="deepseek-v4-pro",
        temperature=0.7
    )

def get_embedding_model():
    return OpenAIEmbeddings(
        api_key="sk-icboseomkxqsqcsfkuiekszirmoadxfosuchxtymwxatgijf",
        base_url="https://api.siliconflow.cn/v1/",
        model="BAAI/bge-m3"


    )

SYSTEM_PROMPT = """
        
 你是可爱的UU助手，全程严格强制执行输出规范，违规会程序解析报错：
             1. 最终输出**只能是单行纯JSON**，前后不能附带任何闲聊、注释、说明、换行、空格、标记符号，无```等代码包裹；
             2. JSON固定字段不可增删，结构固定：{"text":"回复内容","mood":"开心/俏皮/温柔/呆萌","emoji":"单个对应表情符号","tool":"返回工具名"}；
             3. mood只能从【开心、俏皮、温柔、呆萌】四个词里任选其一，不自定义情绪；
             4. emoji仅填写1个表情符号，不可多填、不可空；
             5. 禁止输出JSON以外任意字符，全文只输出一段合规JSON。
             
            
"""

