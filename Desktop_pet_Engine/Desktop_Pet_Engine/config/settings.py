"""config/settings.py — 统一环境变量与路径配置

所有模块统一从此处读取 .env 配置，消除重复代码。
"""

import os
from pathlib import Path

# ── 项目路径 ──────────────────────────────────────────────────
ROOT_DIR = Path(__file__).resolve().parent.parent          # Desktop_Pet_Engine/
ENV_PATH = ROOT_DIR / ".env"
DATA_DIR = ROOT_DIR.parent / "data"                        # 项目根 data/ 目录

# ── .env 加载缓存 ─────────────────────────────────────────────
_env_vars: dict[str, str] | None = None


def _ensure_loaded():
    """按需加载 .env 文件（仅首次调用时解析）"""
    global _env_vars
    if _env_vars is not None:
        return
    _env_vars = {}
    if not ENV_PATH.exists():
        return
    for line in ENV_PATH.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, _, value = line.partition("=")
            _env_vars[key.strip()] = value.strip()


def get_env(key: str, default: str = "") -> str:
    """获取环境变量（优先 OS 环境变量，其次 .env 文件）"""
    _ensure_loaded()
    return os.environ.get(key, _env_vars.get(key, default))


def read_env_file() -> dict[str, str]:
    """读取 .env 文件全部键值对（用于设置页面）"""
    result: dict[str, str] = {}
    if not ENV_PATH.exists():
        return result
    for line in ENV_PATH.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, _, value = line.partition("=")
            result[key.strip()] = value.strip()
    return result
