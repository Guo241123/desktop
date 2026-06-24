# Memory层 - 记忆统一管理接口
from memory.chat_memory import load_memory, save_memory, clear_memory
from memory.vector_store import get_session_vector, save_chat_record
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class MemoryManager:
    """记忆管理器 - 统一管理聊天记忆和向量存储"""

    def __init__(self, session_id: str = "default"):
        self.session_id = session_id

    def load_chat_history(self) -> list:
        """加载聊天历史"""
        return load_memory(self.session_id)

    def save_chat_history(self, chat_history: list):
        """保存聊天历史"""
        save_memory(self.session_id, chat_history)

    def add_message(self, role: str, content: str):
        """添加一条消息到历史"""
        chat_history = self.load_chat_history()
        chat_history.append({
            "role": role,
            "content": content,
            "time": datetime.now().isoformat(timespec="seconds"),
        })
        self.save_chat_history(chat_history)

    def save_record(self, user_text: str, ai_text: str):
        """保存对话记录到向量存储"""
        save_chat_record(self.session_id, user_text, ai_text)

    def compress_memory(self) -> str:
        """真正的记忆压缩：读取全段记忆 → 提取画像 → 几百字总结 → 整段替换"""
        chat_history = self.load_chat_history()
        if len(chat_history) < 2:
            return "对话太短，没什么好压缩的"

        # 格式化全部对话为可读文本
        lines = []
        for m in chat_history:
            role = "用户" if m.get("role") == "user" else "AI"
            content = m.get("content", "")
            lines.append(f"[{role}] {content}")
        full_text = "\n".join(lines)

        # 1️⃣ 从全部对话提取用户画像 → 更新 profile
        profile_updates = self._extract_profile(full_text)
        if profile_updates:
            from memory.user_profile import load_profile, save_profile, SECTION_LABELS
            profile = load_profile(self.session_id)
            updated_fields = []
            for key, val in profile_updates.items():
                if val and key in profile:
                    profile[key] = val.strip()
                    updated_fields.append(SECTION_LABELS.get(key, key))
            save_profile(profile, self.session_id)
            profile_msg = "，更新了：" + "、".join(updated_fields) if updated_fields else ""
        else:
            profile_msg = ""

        # 2️⃣ AI 用几百字总结全部对话
        summary = self._summarize(full_text, long=True)

        # 3️⃣ 整段替换：只留一条总结消息
        compressed = [
            {
                "role": "system",
                "content": "📦 以下是对之前全部对话的总结（已压缩）：\n" + summary,
                "time": datetime.now().isoformat(timespec="seconds"),
            }
        ]

        self.save_chat_history(compressed)
        return "✅ 已压缩全部 %d 条对话 → 1 条总结%s" % (len(chat_history), profile_msg)

    def _extract_profile(self, conversation_text: str) -> dict:
        """用 AI 从聊天记录中提取用户画像信息"""
        try:
            from agent.model_config import get_chat_model
            from langchain_core.messages import HumanMessage

            llm = get_chat_model()
            prompt = (
                "阅读以下对话记录，提取关于用户的画像信息，按 JSON 格式返回，"
                '字段：personal_info（个人信息）、personality（性格兴趣）、'
                'mbti（MBTI表现）、habits（喜好雷点）、interaction_tips（相处建议）。'
                "没提到的字段填空字符串，只输出 JSON 不要多余内容。\n\n"
                + conversation_text
            )
            reply = llm.invoke([HumanMessage(content=prompt)])
            import json, re
            text = reply.content.strip()
            # 提取 JSON
            m = re.search(r'\{.*\}', text, re.DOTALL)
            if m:
                data = json.loads(m.group(0))
                return {k: v for k, v in data.items() if k in ("personal_info","personality","mbti","habits","interaction_tips")}
        except Exception as e:
            logger.warning("提取用户画像失败: %s", e)
        return {}

    def _summarize(self, conversation_text: str, long: bool = False) -> str:
        """用 AI 总结对话内容"""
        try:
            from agent.model_config import get_chat_model
            from langchain_core.messages import HumanMessage

            llm = get_chat_model()
            if long:
                prompt = (
                    "请用几百字详细总结以下全部对话内容，包括："
                    "① 聊了什么话题 ② 用户交代过什么事情 ③ 有什么需要记住的信息 ④ 用户的习惯和偏好。"
                    "写成连贯的一段话，不要分点，不要多余格式。\n\n"
                    + conversation_text
                )
            else:
                prompt = (
                    "请用一段话（100字内）总结以下对话的要点：双方聊了什么话题、"
                    "用户交代过什么事情、有什么需要记住的信息。只输出总结文本，不要多余内容。\n\n"
                    + conversation_text
                )
            reply = llm.invoke([HumanMessage(content=prompt)])
            return reply.content.strip()
        except Exception as e:
            logger.warning("AI 总结失败，改用简单截断: %s", e)
            # 兜底：简单截断
            return "共 %d 条历史对话，已归档。" % conversation_text.count("\n")

    def clear(self):
        """清除所有记忆"""
        clear_memory(self.session_id)