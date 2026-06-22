"""用户画像管理 — 记录用户的性格、习惯、口头禅、说话语气

AI 智能体通过工具持续观察和记录用户特征，
并在对话时注入到系统提示词中，实现个性化回复。
"""

import json
import logging
from datetime import datetime
from typing import Optional
from config.paths import USER_PROFILE_DIR

logger = logging.getLogger(__name__)

DEFAULT_PROFILE = {
    # 基本信息
    "user_name": "",
    "summary": "",
    # 性格特征
    "traits": [],
    "speaking_style": "",
    "emotional_tone": "",
    "emotional_stability": "",
    "social_orientation": "",
    "humor_type": [],
    # 语言习惯
    "catchphrases": [],
    "habits": [],
    "message_length": "",
    "question_frequency": "",
    "emoji_usage": "",
    "punctuation_style": "",
    "language_style": "",
    # 行为模式
    "active_hours": [],
    "active_days": [],
    "conversation_frequency": "",
    "response_speed": "",
    "interaction_type": "",
    "initiative": "",
    # 认知特征
    "learning_style": "",
    "decision_style": "",
    "attention_span": "",
    "detail_orientation": "",
    # 专业领域
    "expertise_areas": [],
    "knowledge_level": "",
    "technical_background": False,
    "industry": "",
    # 偏好设置
    "preferences": {
        "topics": [],
        "response_style": "",
        "core_values": [],
        "goal_orientation": "",
    },
    # 元数据
    "last_updated": "",
    "update_count": 0,
    "data_quality": "low",
}


def _profile_path(session_id: str = "default") -> str:
    """获取用户画像文件路径"""
    USER_PROFILE_DIR.mkdir(parents=True, exist_ok=True)
    return str(USER_PROFILE_DIR / f"{session_id}.json")


def load_profile(session_id: str = "default") -> dict:
    """加载用户画像"""
    path = _profile_path(session_id)
    try:
        if not __import__("os").path.exists(path):
            return dict(DEFAULT_PROFILE)
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        # 补全缺失的默认字段
        profile = dict(DEFAULT_PROFILE)
        profile.update(data)
        return profile
    except Exception as e:
        logger.warning("加载用户画像失败: %s", e)
        return dict(DEFAULT_PROFILE)


def save_profile(profile: dict, session_id: str = "default"):
    """保存用户画像"""
    path = _profile_path(session_id)
    try:
        profile["last_updated"] = datetime.now().isoformat(timespec="seconds")
        profile["update_count"] = profile.get("update_count", 0) + 1
        with open(path, "w", encoding="utf-8") as f:
            json.dump(profile, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        logger.error("保存用户画像失败: %s", e)
        return False


def format_profile_for_prompt(profile: dict) -> str:
    """将用户画像格式化为提示词片段"""
    parts = []

    # 基本信息
    if profile.get("summary"):
        parts.append(f"【用户画像摘要】{profile['summary']}")

    # 性格特征
    if profile.get("traits"):
        parts.append(f"【性格特点】{'、'.join(profile['traits'])}")
    if profile.get("speaking_style"):
        parts.append(f"【说话风格】{profile['speaking_style']}")
    if profile.get("emotional_tone"):
        parts.append(f"【情感倾向】{profile['emotional_tone']}")
    if profile.get("emotional_stability"):
        parts.append(f"【情绪稳定性】{profile['emotional_stability']}")
    if profile.get("social_orientation"):
        parts.append(f"【社交倾向】{profile['social_orientation']}")
    if profile.get("humor_type"):
        parts.append(f"【幽默类型】{'、'.join(profile['humor_type'])}")

    # 语言习惯
    if profile.get("catchphrases"):
        parts.append(f"【常用口头禅】{'、'.join(profile['catchphrases'])}")
    if profile.get("habits"):
        parts.append(f"【使用习惯】{'、'.join(profile['habits'])}")
    if profile.get("message_length"):
        parts.append(f"【消息长度】{profile['message_length']}")
    if profile.get("question_frequency"):
        parts.append(f"【提问频率】{profile['question_frequency']}")
    if profile.get("emoji_usage"):
        parts.append(f"【表情包使用】{profile['emoji_usage']}")
    if profile.get("punctuation_style"):
        parts.append(f"【标点使用】{profile['punctuation_style']}")
    if profile.get("language_style"):
        parts.append(f"【语言风格】{profile['language_style']}")

    # 行为模式
    if profile.get("active_hours"):
        parts.append(f"【活跃时段】{'、'.join(profile['active_hours'])}")
    if profile.get("active_days"):
        parts.append(f"【活跃日期】{'、'.join(profile['active_days'])}")
    if profile.get("conversation_frequency"):
        parts.append(f"【对话频率】{profile['conversation_frequency']}")
    if profile.get("response_speed"):
        parts.append(f"【回复速度】{profile['response_speed']}")
    if profile.get("interaction_type"):
        parts.append(f"【互动类型】{profile['interaction_type']}")
    if profile.get("initiative"):
        parts.append(f"【主动性】{profile['initiative']}")

    # 认知特征
    if profile.get("learning_style"):
        parts.append(f"【学习方式】{profile['learning_style']}")
    if profile.get("decision_style"):
        parts.append(f"【决策风格】{profile['decision_style']}")
    if profile.get("attention_span"):
        parts.append(f"【注意力跨度】{profile['attention_span']}")
    if profile.get("detail_orientation"):
        parts.append(f"【细节关注】{profile['detail_orientation']}")

    # 专业领域
    if profile.get("expertise_areas"):
        parts.append(f"【专业领域】{'、'.join(profile['expertise_areas'])}")
    if profile.get("knowledge_level"):
        parts.append(f"【知识水平】{profile['knowledge_level']}")
    if profile.get("technical_background"):
        parts.append(f"【技术背景】{'有' if profile['technical_background'] else '无'}")
    if profile.get("industry"):
        parts.append(f"【行业】{profile['industry']}")

    # 偏好设置
    prefs = profile.get("preferences", {})
    pref_parts = []
    if prefs.get("topics"):
        pref_parts.append(f"感兴趣话题：{'、'.join(prefs['topics'])}")
    if prefs.get("response_style"):
        pref_parts.append(f"偏好回复风格：{prefs['response_style']}")
    if prefs.get("core_values"):
        pref_parts.append(f"核心价值观：{'、'.join(prefs['core_values'])}")
    if prefs.get("goal_orientation"):
        pref_parts.append(f"目标导向：{prefs['goal_orientation']}")
    if pref_parts:
        parts.append(f"【偏好】{'；'.join(pref_parts)}")

    if not parts:
        return ""

    return "你正在和以下用户聊天，请根据画像调整回复风格：\n" + "\n".join(parts)


def update_profile_field(profile: dict, field: str, value) -> dict:
    """更新画像的某个字段"""
    field = field.strip().lower()

    # 支持嵌套字段: "preferences.topics"
    if "." in field:
        parts = field.split(".", 1)
        main_field = parts[0]
        sub_field = parts[1]
        if main_field in profile and isinstance(profile[main_field], dict):
            if isinstance(value, str) and "," in value:
                value = [v.strip() for v in value.split(",") if v.strip()]
            profile[main_field][sub_field] = value
        return profile

    # 列表字段：追加而非覆盖
    list_fields = {"traits", "catchphrases", "habits", "humor_type", "active_hours", "active_days", "expertise_areas"}
    if field in list_fields:
        if isinstance(value, str):
            items = [v.strip() for v in value.split(",") if v.strip()]
        elif isinstance(value, list):
            items = value
        else:
            items = [str(value)]

        existing = set(profile.get(field, []))
        for item in items:
            if item and item not in existing:
                existing.add(item)
        profile[field] = sorted(existing)
        return profile

    # 字符串/其他字段
    if field in profile:
        profile[field] = value

    return profile
