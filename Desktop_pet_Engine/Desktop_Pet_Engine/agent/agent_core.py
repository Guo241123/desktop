"""Agent层 — AI 核心逻辑

使用 LangChain Agent（DeepSeek 模型 + 工具集）处理用户聊天，
统一返回 {"text", "mood", "emoji", "tool"} 格式。
自动注入用户画像实现个性化回复。
"""

from datetime import datetime
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
        memory = MemoryManager(session_id)
        chat_history = memory.load_chat_history()
        chat_history.append({"role": "user", "content": message, "time": datetime.now().isoformat(timespec="seconds")})

        enhanced_history = _inject_profile(chat_history, session_id)

        res = get_agent(system_prompt).invoke({"messages": enhanced_history})
        raw_content = res["messages"][-1].content
        ai_content = raw_content.strip() if isinstance(raw_content, str) else str(raw_content).strip()

        if not ai_content:
            resp_dict = {"text": "ok了", "mood": "温柔", "emoji": "😊", "tool": ""}
        else:
            import re
            # 尝试从 ai_content 中提取第一个 JSON 对象（非贪婪匹配）
            json_match = re.search(r'\{.*?\}', ai_content, re.DOTALL)
            json_str = json_match.group(0) if json_match else ai_content
            try:
                resp_dict = json.loads(json_str)
                if "text" not in resp_dict:
                    resp_dict = {"text": ai_content, "mood": "assistant", "emoji": "💬"}
            except json.JSONDecodeError:
                # JSON 解析失败：如果正则找到了 {} 但解析失败，
                # 尝试取 {} 前面的文本（AI 经常在 JSON 前写闲聊）
                if json_match:
                    before_json = ai_content[:json_match.start()].strip()
                    if before_json:
                        resp_dict = {"text": before_json, "mood": "assistant", "emoji": "💬"}
                    else:
                        # 整个内容就是残缺 JSON，保底回复
                        resp_dict = {"text": "嗯嗯~", "mood": "温柔", "emoji": "😊", "tool": ""}
                else:
                    # 没找到 {}：清洗可能泄漏的 JSON 尾部（如 `😎", "mood": "开心"`）
                    cleaned = re.sub(r'",\s*"[a-z_]+":\s*"[^"]*"\s*,?\s*}?\s*$', '', ai_content)
                    # 去掉首尾可能残留的引号花括号
                    cleaned = cleaned.strip().rstrip('}').strip()
                    resp_dict = {"text": cleaned or ai_content, "mood": "assistant", "emoji": "📝"}
        
        # 解析 tool 字段并执行工具
        tool_name = resp_dict.get("tool", "")
        if tool_name == "send_file_to_wechat":
            file_path = resp_dict.pop("file_path", "")
            if file_path:
                try:
                    from tools.send_to_wechat import send_file_to_wechat
                    result = send_file_to_wechat.invoke({"file_path": file_path})
                    resp_dict = {"text": f"{result}"}
                except Exception as e:
                    logger.warning("执行 send_file_to_wechat 失败: %s", e)
                    resp_dict = {"text": f"发文件失败了: {e}"}
        elif tool_name == "text_to_speech":
            # 特殊处理：把 AI 回复的 text 内容作为朗读内容传给工具
            speech_text = resp_dict.get("text", "")
            if speech_text:
                try:
                    from tools.voice import text_to_speech
                    result = text_to_speech.invoke({"text": speech_text})
                    resp_dict["text"] = f"{result}"
                    logger.info("TTS 播放: %.60s", speech_text)
                except Exception as e:
                    logger.warning("执行 text_to_speech 失败: %s", e)
                    resp_dict["text"] = f"播放语音失败了: {e}"
        elif tool_name:
            # 通用工具调用：查找 all_tools 并执行
            try:
                from tools import all_tools as _all_tools
                target_tool = next((t for t in _all_tools if t.name == tool_name), None)
                if target_tool:
                    # 从 response 中提取除 text/mood/emoji/tool 外的参数
                    tool_args = {k: v for k, v in resp_dict.items()
                                 if k not in ("text", "mood", "emoji", "tool")}
                    result = target_tool.invoke(tool_args)
                    resp_dict["text"] = f"{result}"
                    resp_dict["tool"] = tool_name
                    logger.info("工具 %s 执行结果: %.100s", tool_name, str(result))
                else:
                    logger.debug("未找到工具: %s", tool_name)
            except Exception as e:
                logger.warning("执行工具 %s 失败: %s", tool_name, e)

        reply_text = resp_dict.get("text", "")

        chat_history.append({"role": "assistant", "content": reply_text, "time": datetime.now().isoformat(timespec="seconds")})
        memory.save_chat_history(chat_history)
        memory.save_record(message, reply_text)

        logger.info("对话成功 | 用户=%s | 回复=%.60s", session_id, reply_text)
        return resp_dict

    except Exception as e:
        logger.exception("服务异常: %s", e)
        return {"text": "服务出错啦，稍后再试~", "mood": "error", "emoji": "⚠️"}



