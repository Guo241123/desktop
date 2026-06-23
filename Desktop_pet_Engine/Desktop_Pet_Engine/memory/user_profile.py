"""用户画像管理 — 5段式结构化画像

每周执行一次的记忆压缩工具，AI 通过聊天记录总结用户特征。
每次对话自动注入提示词，让回复更贴合用户。
"""

import json
import logging
from datetime import datetime
from config.paths import USER_PROFILE_DIR

logger = logging.getLogger(__name__)

DEFAULT_PROFILE = {
    "personal_info": "",        # ① 个人信息（姓名、年龄、职业等）
    "personality": "",          # ② 性格、说话风格、兴趣爱好
    "mbti": "",                 # ③ MBTI 各维度表现
    "habits": "",               # ④ 习惯、喜欢什么、讨厌什么（雷点）
    "interaction_tips": "",     # ⑤ 和用户相处建议、避开雷点
    "last_updated": "",
    "update_count": 0,
}


def _profile_path(session_id: str = "default") -> str:
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


SECTION_LABELS = {
    "personal_info": "📋 个人信息",
    "personality": "🎭 性格·风格·兴趣",
    "mbti": "🧠 MBTI 维度",
    "habits": "❤️ 喜好·雷点",
    "interaction_tips": "💡 相处建议",
}


def format_profile_for_prompt(profile: dict) -> str:
    """将用户画像格式化为提示词片段"""
    parts = []
    for key, label in SECTION_LABELS.items():
        val = profile.get(key, "").strip()
        if val:
            parts.append(f"【{label}】{val}")

    if not parts:
        return ""

    return "【用户画像】（基于过往聊天总结，帮助你更好地回复）\n" + "\n".join(parts)
