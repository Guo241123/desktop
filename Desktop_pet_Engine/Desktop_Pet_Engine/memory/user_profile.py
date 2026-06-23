"""用户画像管理 — 精简版：只有一段文本摘要

AI 通过工具记录一段话描述用户特征（性格、说话风格、兴趣等），
每次对话时注入到提示词中实现个性化回复。
"""

import json
import logging
from datetime import datetime
from config.paths import USER_PROFILE_DIR

logger = logging.getLogger(__name__)

DEFAULT_PROFILE = {
    "summary": "",
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


def format_profile_for_prompt(profile: dict) -> str:
    """将用户画像格式化为提示词片段"""
    summary = profile.get("summary", "").strip()
    if not summary:
        return ""
    return f"【用户画像】{summary}"
