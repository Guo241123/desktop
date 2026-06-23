"""用户画像工具 — AI 用来记录对用户的了解

AI 在聊天中观察用户，把性格、说话风格、兴趣等记成一段话，
每次对话自动注入提示词，让回复更贴合用户。
"""

import logging
from langchain.tools import tool
from memory.user_profile import load_profile, save_profile

logger = logging.getLogger(__name__)


@tool
def update_user_summary(summary: str, session_id: str = "default"):
    """
    记录你对用户的了解——性格、说话风格、兴趣爱好、习惯等。
    写一段通顺的话概括，不用结构化字段。
    每次聊天时这段描述会自动注入提示词，让回复更贴合用户。
    
    例如：「这个用户是个大学生，说话简洁随性爱用网络梗，
    喜欢捣鼓代码和做吃的，早上到晚上都在线，上课也摸鱼。」
    
    :param summary: 用户画像描述文本
    :param session_id: 会话ID（一般不用改）
    :return: 更新结果
    """
    profile = load_profile(session_id)
    profile["summary"] = summary.strip()
    ok = save_profile(profile, session_id)
    if ok:
        return f"✅ 已更新用户画像"
    return "⚠️ 保存失败"
