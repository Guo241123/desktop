"""config/paths.py — 项目路径与数据目录配置

所有数据目录统一在此定义，业务模块只需 `from config.paths import ...`。
数据文件统一存放在项目根目录的 data/ 下。
"""

from pathlib import Path
from config.settings import DATA_DIR as _DATA_DIR

# 重新导出，方便 from config.paths import DATA_DIR
DATA_DIR = _DATA_DIR

# ── 数据子目录 ─────────────────────────────────────────────────
CHAT_MEMORY_DIR = DATA_DIR / "chat_memory"
VECTOR_DB_DIR = DATA_DIR / "vector_db"
SEARCH_IMG_DIR = DATA_DIR / "search_img"
WECHAT_CREDENTIALS_DIR = DATA_DIR / "wechat"
WECHAT_CREDENTIALS_FILE = WECHAT_CREDENTIALS_DIR / "credentials.json"
STICKERS_DIR = DATA_DIR / "stickers"
REMINDERS_FILE = DATA_DIR / "reminders.json"
SANDBOX_DIR = DATA_DIR / "sandbox"
USER_PROFILE_DIR = DATA_DIR / "user_profiles"


def ensure_dirs():
    """确保所有数据目录存在"""
    for d in [CHAT_MEMORY_DIR, VECTOR_DB_DIR, SEARCH_IMG_DIR, STICKERS_DIR, SANDBOX_DIR, USER_PROFILE_DIR]:
        d.mkdir(parents=True, exist_ok=True)
