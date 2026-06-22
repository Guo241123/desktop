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
    "user_name": "",
    "summary": "",
    "traits": [],
    "catchphrases": [],
    "habits": [],
    "speaking_style": "",
    "preferences": {
        "topics": [],
        "response_style": "",
    },
    "last_updated": "",
    "update_count": 0,
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

    if profile.get("summary"):
        parts.append(f"【用户画像摘要】{profile['summary']}")

    if profile.get("traits"):
        parts.append(f"【性格特点】{'、'.join(profile['traits'])}")

    if profile.get("catchphrases"):
        parts.append(f"【常用口头禅】{'、'.join(profile['catchphrases'])}")

    if profile.get("speaking_style"):
        parts.append(f"【说话风格】{profile['speaking_style']}")

    if profile.get("habits"):
        parts.append(f"【使用习惯】{'、'.join(profile['habits'])}")

    prefs = profile.get("preferences", {})
    pref_parts = []
    if prefs.get("topics"):
        pref_parts.append(f"感兴趣话题：{'、'.join(prefs['topics'])}")
    if prefs.get("response_style"):
        pref_parts.append(f"偏好回复风格：{prefs['response_style']}")
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
    list_fields = {"traits", "catchphrases", "habits"}
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
