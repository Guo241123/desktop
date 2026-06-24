"""用户画像工具 — 记录用户 + 压缩聊天记忆

AI 在聊天中观察用户，用此工具把了解记成 5 段画像，
同时会自动压缩聊天历史（只保留最近的对话）。
"""

import logging
from langchain.tools import tool
from memory.user_profile import (
    load_profile, save_profile,
    SECTION_LABELS,
)
from memory.memory_manager import MemoryManager

logger = logging.getLogger(__name__)


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
    记录你对用户的了解，按 5 个维度保存，同时自动压缩聊天记忆。
    传入的字段会覆盖旧值，空的字段保持不变，想记什么就记什么。
    建议定期使用此工具回顾聊天记录，更新画像。

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
    :return: 更新结果
    """
    profile = load_profile(session_id)

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

    # 自动压缩聊天记忆（读取全段 → 提取画像 → 几百字总结 → 整段替换）
    mm = MemoryManager(session_id)
    compress_result = mm.compress_memory()

    parts = [f"✅ 已更新用户画像（第 {profile['update_count']} 次）"]
    if updated:
        parts.append(f"更新了：{'、'.join(updated)}")
    parts.append("📦 " + compress_result)
    return " | ".join(parts)
