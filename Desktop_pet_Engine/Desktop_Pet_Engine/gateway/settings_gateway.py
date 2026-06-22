# Gateway层 - 设置入口
import os
from pathlib import Path
from fastapi import APIRouter
from gateway.schema import SaveRequest

settings_router = APIRouter(prefix="/api/settings", tags=["设置接口"])

ENV_PATH = Path(__file__).resolve().parent.parent / ".env"

# .env 中允许前端读写的白名单字段
ALLOWED_KEYS = [
    "DEEPSEEK_API_KEY", "DEEPSEEK_BASE_URL", "CHAT_MODEL", "TEMPERATURE",
    "SILICONFLOW_API_KEY", "SILICONFLOW_BASE_URL", "EMBEDDING_MODEL",
    "TAVILYWEB_KEY",
    "MIMO_API_KEY", "MIMO_BASE_URL", "MODEL_ASR", "MODEL_TTS",
    "WAKE_WORD", "WAKE_REPLY", "CONVERSATION_TIMEOUT", "VOICE_SAMPLE_PATH",
]


def _read_env() -> dict:
    result = {}
    if ENV_PATH.exists():
        for line in ENV_PATH.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, value = line.partition("=")
                result[key.strip()] = value.strip()
    return result


# .env 模板（保留注释结构）
_ENV_TEMPLATE = """# ========================
# DeepSeek LLM 配置
# ========================
DEEPSEEK_API_KEY={DEEPSEEK_API_KEY}
DEEPSEEK_BASE_URL={DEEPSEEK_BASE_URL}
CHAT_MODEL={CHAT_MODEL}
TEMPERATURE={TEMPERATURE}

# ========================
# SiliconFlow Embedding 配置
# ========================
SILICONFLOW_API_KEY={SILICONFLOW_API_KEY}
SILICONFLOW_BASE_URL={SILICONFLOW_BASE_URL}
EMBEDDING_MODEL={EMBEDDING_MODEL}

# ========================
# Tavily 搜索配置
# ========================
TAVILYWEB_KEY={TAVILYWEB_KEY}

# ========================
# Mimo 语音服务配置
# ========================
MIMO_API_KEY={MIMO_API_KEY}
MIMO_BASE_URL={MIMO_BASE_URL}
MODEL_ASR={MODEL_ASR}
MODEL_TTS={MODEL_TTS}

# ========================
# 语音唤醒配置
# ========================
WAKE_WORD={WAKE_WORD}
WAKE_REPLY={WAKE_REPLY}
CONVERSATION_TIMEOUT={CONVERSATION_TIMEOUT}
VOICE_SAMPLE_PATH={VOICE_SAMPLE_PATH}
"""


def _write_env(data: dict):
    existing = _read_env()
    existing.update(data)
    content = _ENV_TEMPLATE.format(**{k: existing.get(k, "") for k in ALLOWED_KEYS})
    ENV_PATH.write_text(content, encoding="utf-8")


@settings_router.get("/load")
def load_settings():
    env = _read_env()
    return {"success": True, "env": env}


@settings_router.post("/save")
def save_settings(req: SaveRequest):
    try:
        env_data = {k: v for k, v in req.env.items() if k in ALLOWED_KEYS}
        _write_env(env_data)
        return {"success": True, "msg": "保存成功"}
    except Exception as e:
        return {"success": False, "msg": str(e)}