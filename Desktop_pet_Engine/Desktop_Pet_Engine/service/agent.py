
import os
import json
import re
from langchain.agents import create_agent

from config.ai_config import get_chat_model, SYSTEM_PROMPT
from infra.vector_store import save_chat_record

# 原有工具

from tools.file import del_dir,del_file,move_item,copy_file,copy_dir,scan_dir,make_file,read_file,rename_item,make_dir,batch_change_suffix,write_file,get_desktop_path
from tools.load_prompt import ppt_prompt
from tools.tavilyweb import web_search
from tools.word import create_professional_word,create_essay_word
from tools.PDF import ppt_to_pdf
# from tools.pdf_pptx import pdf_to_pptx

# ======================
# 配置
# ======================
MEMORY_DIR = "chat_memory"
os.makedirs(MEMORY_DIR, exist_ok=True)

# 模型加载
llm = get_chat_model()

tools = [
    del_dir,
    del_file,
    move_item,
    copy_file,
    copy_dir,
    scan_dir,
    make_file,
    rename_item,
    make_dir,
    batch_change_suffix,
    write_file,
    get_desktop_path,
    web_search,
    create_professional_word,
    create_essay_word,
    read_file,
    ppt_prompt,
    ppt_to_pdf,

]

agent = create_agent(
    model=llm,
    tools=tools,
    system_prompt=SYSTEM_PROMPT
)

# ======================
#  安全记忆存储
# ======================
def get_memory_file(session_id):
    return os.path.join(MEMORY_DIR, f"{session_id}.json")

def load_memory(session_id):
    file = get_memory_file(session_id)
    if not os.path.exists(file):
        return []
    try:
        with open(file, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return []

def save_memory(session_id, chat_history):
    file = get_memory_file(session_id)
    try:
        with open(file, "w", encoding="utf-8") as f:
            json.dump(chat_history, f, ensure_ascii=False, indent=2)
    except:
        pass

# ======================
# 主聊天逻辑
# ======================
def agent_main(message: str, session_id: str = "default"):
    try:
        chat_history = load_memory(session_id)
        chat_history.append({"role": "user", "content": message})

        res = agent.invoke({"messages": chat_history})
        raw_content = res["messages"][-1].content
        ai_content = raw_content.strip() if isinstance(raw_content, str) else str(raw_content).strip()

        # 情况1：AI 什么都没返回
        if not ai_content:
            resp_dict = {
                "text": "ok了",
                "mood": "温柔",
                "emoji": "😊",
                "tool": ""
            }
        else:
            # 情况2：尝试解析 JSON
            try:
                resp_dict = json.loads(ai_content)
                # 确保有 text 字段
                if "text" not in resp_dict:
                    resp_dict = {"text": ai_content, "mood": "assistant", "emoji": "💬"}
            except json.JSONDecodeError:
                # 情况3：返回了内容但不是 JSON，当作纯文本
                resp_dict = {"text": ai_content, "mood": "assistant", "emoji": "📝"}

        reply_text = resp_dict.get("text", "")

        # 保存记忆（将 resp_dict 转为 JSON 字符串存储）
        chat_history.append({"role": "assistant", "content": json.dumps(resp_dict, ensure_ascii=False)})
        save_memory(session_id, chat_history)

        save_chat_record(session_id, message, reply_text)
        print(f"对话成功 | 用户={session_id} | 回复={reply_text}")

        return resp_dict

    except Exception as e:
        # 这里只捕获真正的系统级异常（网络、文件读写等）
        print(f"服务异常: {str(e)}")
        return {
            "text": "服务出错啦，稍后再试~",
            "mood": "error",
            "emoji": "⚠️"
        }