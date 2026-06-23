"""用户画像工具 — 每周一次的记忆压缩

AI 定期（建议每周一次）回顾聊天记录，总结用户特征到 5 个维度。
画像会自动注入每次对话的提示词中，让回复更贴心。
"""

import logging
from langchain.tools import tool
from memory.user_profile import (
    load_profile, save_profile,
    DEFAULT_PROFILE, SECTION_LABELS,
)

logger = logging.getLogger(__name__)

_WEEK_SECONDS = 7 * 24 * 3600


@tool
def update_user_profile(
    personal_info: str = "",
    personality: str = "",
    mbti: str = "",
    habits: str = "",
    interaction_tips: str = "",
    session_id: str = "default",
):
    """
    【每周记忆压缩】回顾你和用户的聊天记录，把对用户的了解总结成 5 段画像。
    建议每周执行一次（距上次更新超过 7 天时），让画像持续更新。
    传入的字段会覆盖旧值，空的字段保持不变。

    各字段说明：
    - personal_info: ① 个人信息（姓名、年龄、职业、所在地等）
    - personality:   ② 性格特点、说话风格、兴趣爱好
    - mbti:          ③ MBTI 各维度表现（E/I, S/N, T/F, J/P）
    - habits:        ④ 习惯、喜欢什么、讨厌什么（雷点）
    - interaction_tips: ⑤ 以后怎么和你相处最愉快、避开哪些雷

    :param personal_info: 个人信息描述
    :param personality: 性格·风格·兴趣描述
    :param mbti: MBTI 维度描述
    :param habits: 喜好·雷点描述
    :param interaction_tips: 相处建议
    :param session_id: 会话ID（一般不用改）
    :return: 更新结果 + 距上次更新天数
    """
    profile = load_profile(session_id)

    # 只覆盖有传值的字段
    fields_map = {
        "personal_info": personal_info,
        "personality": personality,
        "mbti": mbti,
        "habits": habits,
        "interaction_tips": interaction_tips,
    }
    updated = []
    for key, val in fields_map.items():
        if val:
            profile[key] = val.strip()
            updated.append(SECTION_LABELS.get(key, key))

    ok = save_profile(profile, session_id)
    if not ok:
        return "⚠️ 保存失败"

    # 计算距上次更新的天数
    from datetime import datetime
    days_since = 0
    if profile.get("last_updated"):
        try:
            last = datetime.fromisoformat(profile["last_updated"])
            days_since = (datetime.now() - last).days
        except Exception:
            pass

    parts = [f"✅ 已更新用户画像（第 {profile['update_count']} 次）"]
    if updated:
        parts.append(f"更新了：{'、'.join(updated)}")
    if days_since > 0:
        parts.append(f"距上次更新 {days_since} 天")
    return " | ".join(parts)
