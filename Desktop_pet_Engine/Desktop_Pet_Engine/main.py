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

@app.get("/")
def index():
    return {"status": "ok", "msg": "你好啊~"}

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=5432, reload=False)