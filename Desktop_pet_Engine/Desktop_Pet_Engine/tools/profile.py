"""用户画像工具 — AI 智能体用来记录和了解用户

AI 通过观察用户的聊天内容，主动记录用户的性格特点、
口头禅、说话风格、兴趣爱好等，实现个性化回复。
"""

import logging
from langchain.tools import tool
from memory.user_profile import (
    load_profile,
    save_profile,
    format_profile_for_prompt,
    update_profile_field,
)

logger = logging.getLogger(__name__)


@tool
def get_user_profile(session_id: str = "default"):
    """
    查看当前用户画像内容。
    用于了解你已经记录了用户的哪些特征。
    :param session_id: 会话ID（一般不用改）
    :return: 用户画像的概要描述
    """
    profile = load_profile(session_id)
    formatted = format_profile_for_prompt(profile)
    if not formatted:
        return "目前还没有记录这个用户的信息，你可以通过聊天慢慢了解他/她~"
    return formatted


@tool
def update_user_profile(field: str, value: str, session_id: str = "default"):
    """
    记录或更新用户的某个特征信息。
    在聊天过程中观察到用户的性格、习惯、口头禅等时调用此工具记录。
    
    可用字段：
    - summary: 用户整体画像摘要
    - traits: 性格特点（多个用逗号分隔）
    - catchphrases: 常用口头禅（多个用逗号分隔）
    - habits: 使用习惯（多个用逗号分隔）
    - speaking_style: 说话风格描述
    - preferences.topics: 感兴趣的话题（多个用逗号分隔）
    - preferences.response_style: 偏好的回复风格
    
    :param field: 字段名，如 "traits"、"catchphrases"、"speaking_style"
    :param value: 字段值，如 "幽默, 直爽" 或 "喜欢说"笑死""
    :param session_id: 会话ID（一般不用改）
    :return: 更新结果
    """
    profile = load_profile(session_id)
    profile = update_profile_field(profile, field, value)
    ok = save_profile(profile, session_id)
    if ok:
        return f"✅ 已记录用户特征 [{field}]：{value}"
    return "⚠️ 保存用户画像失败"


@tool
def summarize_user_profile(session_id: str = "default"):
    """
    根据已记录的画像字段，生成一段完整的用户画像摘要。
    当你对用户有了足够了解后，调用此工具让AI总结一份完整的用户画像。
    :param session_id: 会话ID（一般不用改）
    :return: 生成的画像摘要
    """
    profile = load_profile(session_id)
    formatted = format_profile_for_prompt(profile)
    if not formatted:
        return "目前还没有记录这个用户的信息哦，多聊聊天再让我总结吧~"
    
    # 把已记录的字段都聚合到 summary 中
    profile["summary"] = formatted.replace("你正在和以下用户聊天，请根据画像调整回复风格：\n", "")
    save_profile(profile, session_id)
    return f"📋 已生成用户画像摘要：\n{profile['summary']}"
