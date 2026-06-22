# 配置模块
from config.settings import get_env, read_env_file, ENV_PATH, ROOT_DIR
from config.paths import (
    DATA_DIR, CHAT_MEMORY_DIR, VECTOR_DB_DIR, SEARCH_IMG_DIR, ensure_dirs,
)
