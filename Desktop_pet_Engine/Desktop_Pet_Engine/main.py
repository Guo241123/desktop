import sys
import logging

# 统一日志配置
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    datefmt="%H:%M:%S",
)

# 安装日志捕获（拦截 logging 到内存）
from utils.log_capture import install as install_log_capture
#install_log_capture()  # Python 3.14 兼容问题，暂不启用

logger = logging.getLogger(__name__)
logger.info("✅ Guo 助手启动中...")

# ── 每次启动自动清空微信凭证，需要重新扫码登录 ──────────────
from config.paths import WECHAT_CREDENTIALS_FILE
if WECHAT_CREDENTIALS_FILE.exists():
    WECHAT_CREDENTIALS_FILE.unlink()
    logger.info("已清除旧微信凭证，启动后需重新扫码登录")

from fastapi import FastAPI
import uvicorn
import asyncio
from fastapi.middleware.cors import CORSMiddleware
from gateway.router import register_routes

app = FastAPI(title="Guo助手")

# ── 启动时自动调微信登录 ─────────────────────────────────────
@app.on_event("startup")
async def auto_start_channels():
    from mi import channel_manager
    try:
        result = await channel_manager.start("wechat")
        if result.get("qrcode"):
            logger.info("微信二维码已生成，请在浏览器打开扫码登录")
            logger.info("二维码URL: %s", result["qrcode"]["url"])
        else:
            logger.info("微信通道启动结果: %s", result.get("msg"))
    except Exception as e:
        logger.warning("自动启动微信通道失败: %s", e)

# 跨域配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
register_routes(app)

# 管理后台静态文件（仅用于独立 HTML，不覆盖 /admin 路由）
# 访问方式：直接走 admin_gateway.py 的路由

@app.get("/")
def index():
    return {"status": "ok", "msg": "你好啊~"}

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=5432, reload=False)
