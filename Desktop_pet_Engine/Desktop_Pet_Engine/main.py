import sys, io
import logging

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# 统一日志配置
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    datefmt="%H:%M:%S",
)

from fastapi import FastAPI
import uvicorn
from fastapi.middleware.cors import CORSMiddleware
from gateway.router import register_routes

app = FastAPI(title="芙芙助手")

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

# 每次启动时清除微信登录凭证，确保重新扫码登录
from gateway.mi_gateway import delete_wechat_credentials
delete_wechat_credentials()

logger = logging.getLogger(__name__)

# 启动时自动拉起微信登录流程（无凭证则弹出二维码）
@app.on_event("startup")
async def auto_start_wechat():
    from gateway.mi_gateway import start_wechat_channel
    result = await start_wechat_channel()
    logger.info("微信通道自动启动: %s", result.get("msg", ""))

    # 启动每周画像总结后台任务
    from scheduler.weekly_profile import weekly_profile_loop
    asyncio.create_task(weekly_profile_loop())
    logger.info("每周画像定时器已启动")

@app.get("/")
def index():
    return {"status": "ok", "msg": "你好啊~"}

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=5432, reload=False)