"""Agent层 — AI 核心逻辑

使用 LangChain Agent（DeepSeek 模型 + 工具集）处理用户聊天，
统一返回 {"text", "mood", "emoji", "tool"} 格式。
自动注入用户画像实现个性化回复。
"""

from datetime import datetime
import json
import logging
import re
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


def _parse_ai_response(ai_content: str) -> dict:
    """解析 AI 的 JSON 回复，容错处理"""
    if not ai_content:
        return {"text": "ok了", "mood": "温柔", "emoji": "😊", "tool": ""}

    json_match = re.search(r'\{.*?\}', ai_content, re.DOTALL)
    json_str = json_match.group(0) if json_match else ai_content
    try:
        resp_dict = json.loads(json_str)
        if "text" not in resp_dict:
            resp_dict = {"text": ai_content, "mood": "assistant", "emoji": "💬"}
        return resp_dict
    except json.JSONDecodeError:
        if json_match:
            before_json = ai_content[:json_match.start()].strip()
            if before_json:
                return {"text": before_json, "mood": "assistant", "emoji": "💬"}
            return {"text": "嗯嗯~", "mood": "温柔", "emoji": "😊", "tool": ""}
        else:
            cleaned = re.sub(r'",\s*"[a-z_]+":\s*"[^"]*"\s*,?\s*}?\s*$', '', ai_content)
            cleaned = cleaned.strip().rstrip('}').strip()
            return {"text": cleaned or ai_content, "mood": "assistant", "emoji": "📝"}


def _invoke_llm(chat_history: list, session_id: str, system_prompt: str = None) -> str:
    """调用 LLM 并返回原始回复内容"""
    enhanced = _inject_profile(chat_history, session_id)
    res = get_agent(system_prompt).invoke({"messages": enhanced})
    raw = res["messages"][-1].content
    return raw.strip() if isinstance(raw, str) else str(raw).strip()


def _extract_filepath(text: str) -> str | None:
    """从 '录音已保存: C:\\path\\to\\file.wav（3.5秒）' 中提取路径"""
    m = re.search(r"([A-Za-z]:\\[^\s（）)]+)", text)
    return m.group(1) if m else None


def _run_voice_chain(filepath: str, chat_history: list, session_id: str, system_prompt: str) -> str:
    """语音链：转文字 → LLM 理解 → 文字转语音，返回播放结果"""
    from tools.voice import speech_to_text, text_to_speech

    # Step 1: ASR
    transcribe_result = speech_to_text.invoke({"audio_path": filepath})
    logger.info("语音链·转文字: %.100s", transcribe_result)

    # Step 2: 把识别结果喂给 AI
    chat_history.append({"role": "user", "content": f"[语音识别结果: {transcribe_result}]"})
    ai_reply = _invoke_llm(chat_history, session_id, system_prompt)
    logger.info("语音链·AI回复: %.60s", ai_reply)
    reply_dict = _parse_ai_response(ai_reply)
    reply_text = reply_dict.get("text", "")
    if not reply_text:
        return "嗯嗯~"

    # Step 3: TTS 朗读
    speak_result = text_to_speech.invoke({"text": reply_text})
    logger.info("语音链·TTS: %.60s", speak_result)
    return f"{speak_result}（原话: {reply_text}）"


def agent_main(message: str, session_id: str = "default", system_prompt: str = None) -> dict:
    """主聊天逻辑（走 Agent，JSON 输出格式）"""
    try:
        memory = MemoryManager(session_id)
        chat_history = memory.load_chat_history()
        chat_history.append({"role": "user", "content": message, "time": datetime.now().isoformat(timespec="seconds")})

        ai_content = _invoke_llm(chat_history, session_id, system_prompt)
        resp_dict = _parse_ai_response(ai_content)

        # 解析 tool 字段并执行工具
        tool_name = resp_dict.get("tool", "")
        action = resp_dict.get("action", "")

        if tool_name == "send_file_to_wechat":
            file_path = resp_dict.get("file_path", "")
            if file_path:
                try:
                    from tools.send_to_wechat import send_file_to_wechat
                    result = send_file_to_wechat.invoke({"file_path": file_path})
                    resp_dict = {"text": f"{result}"}
                except Exception as e:
                    logger.warning("执行 send_file_to_wechat 失败: %s", e)
                    resp_dict = {"text": f"发文件失败了: {e}"}

        elif tool_name == "text_to_speech":
            speech_text = resp_dict.get("text", "")
            if speech_text:
                try:
                    from tools.voice import text_to_speech
                    result = text_to_speech.invoke({"text": speech_text})
                    # 保留原回复文字，TTS 播放状态额外记录
                    resp_dict["tool_result"] = str(result)
                    logger.info("TTS 播放完毕: %.60s | %s", speech_text, result)
                except Exception as e:
                    logger.warning("执行 text_to_speech 失败: %s", e)
                    resp_dict["tool_result"] = f"播放语音失败了: {e}"

        elif tool_name:
            try:
                target_tool = next((t for t in all_tools if t.name == tool_name), None)
                if target_tool:
                    tool_args = {k: v for k, v in resp_dict.items()
                                 if k not in ("text", "mood", "emoji", "tool")}
                    result = target_tool.invoke(tool_args)
                    resp_dict["text"] = f"{result}"
                    logger.info("工具 %s 执行结果: %.100s", tool_name, str(result))

                    # ── 语音链：关麦克风后自动转文字 → 思考 → 说话 ──
                    if tool_name == "toggle_microphone" and action == "off":
                        filepath = _extract_filepath(resp_dict["text"])
                        if filepath:
                            chain_result = _run_voice_chain(filepath, chat_history, session_id, system_prompt)
                            resp_dict["text"] = chain_result
                            resp_dict["tool"] = "voice_chain"
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
