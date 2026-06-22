"""Agent层 — AI 核心逻辑

使用 LangChain Agent（DeepSeek 模型 + 工具集）处理用户聊天，
统一返回 {"text", "mood", "emoji", "tool"} 格式。
自动注入用户画像实现个性化回复。
"""

import json
import logging
from langchain.agents import create_agent
from agent.model_config import get_chat_model
from agent.prompts import SYSTEM_PROMPT
from memory.memory_manager import MemoryManager
from memory.user_profile import load_profile, format_profile_for_prompt
from tools import all_tools

logger = logging.getLogger(__name__)

llm = get_chat_model()
_agent_cache: dict[str, any] = {}


def get_agent(system_prompt: str = None):
    """获取 Agent 实例（按提示词缓存）"""
    if system_prompt is None:
        system_prompt = SYSTEM_PROMPT
    if system_prompt not in _agent_cache:
        _agent_cache[system_prompt] = create_agent(
            model=llm,
            tools=all_tools,
            system_prompt=system_prompt,
        )
    return _agent_cache[system_prompt]


def _inject_profile(chat_history: list, session_id: str) -> list:
    """将用户画像注入到对话历史的开头（不保存到文件）"""
    profile = load_profile(session_id)
    profile_text = format_profile_for_prompt(profile)
    if profile_text:
        return [{"role": "system", "content": profile_text}] + chat_history
    return chat_history


def agent_main(message: str, session_id: str = "default", system_prompt: str = None) -> dict:
    """主聊天逻辑（走 Agent，JSON 输出格式）"""
    try:
        from utils.metrics import record_request

        memory = MemoryManager(session_id)
        chat_history = memory.load_chat_history()
        chat_history.append({"role": "user", "content": message})

        enhanced_history = _inject_profile(chat_history, session_id)

        res = get_agent(system_prompt).invoke({"messages": enhanced_history})
        raw_content = res["messages"][-1].content
        ai_content = raw_content.strip() if isinstance(raw_content, str) else str(raw_content).strip()

        # 统计 token 用量
        try:
            meta = res.get("response_metadata", {})
            usage = meta.get("token_usage", {}) or meta.get("usage", {})
            inp = usage.get("prompt_tokens", 0) or usage.get("input_tokens", 0)
            out = usage.get("completion_tokens", 0) or usage.get("output_tokens", 0)
            record_request(input_tokens=inp, output_tokens=out)
        except Exception:
            record_request()

        if not ai_content:
            resp_dict = {"text": "ok了", "mood": "温柔", "emoji": "😊", "tool": ""}
        else:
            try:
                resp_dict = json.loads(ai_content)
                if "text" not in resp_dict:
                    resp_dict = {"text": ai_content, "mood": "assistant", "emoji": "💬"}
            except json.JSONDecodeError:
                resp_dict = {"text": ai_content, "mood": "assistant", "emoji": "📝"}

        reply_text = resp_dict.get("text", "")

        chat_history.append({"role": "assistant", "content": json.dumps(resp_dict, ensure_ascii=False)})
        memory.save_chat_history(chat_history)
        memory.save_record(message, reply_text)

        logger.info("对话成功 | 用户=%s | 回复=%.60s", session_id, reply_text)
        return resp_dict

    except Exception as e:
        logger.exception("服务异常: %s", e)
        return {"text": "服务出错啦，稍后再试~", "mood": "error", "emoji": "⚠️"}


def direct_chat(message: str, system_prompt: str = None) -> str:
    """纯文本聊天 — 不走 Agent/工具/JSON，直接调 LLM 返回文字"""
    try:
        from langchain_core.messages import HumanMessage, SystemMessage

        if system_prompt is None:
            system_prompt = "你是一个口语化的聊天伙伴，像我朋友一样自然聊天就好。"
        msgs = [SystemMessage(content=system_prompt), HumanMessage(content=message)]
        reply = llm.invoke(msgs)
        return reply.content.strip()
    except Exception as e:
        logger.exception("直接聊天出错: %s", e)
        return "服务出错啦，稍后再试~"
