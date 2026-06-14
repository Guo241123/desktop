import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')
from fastapi import FastAPI
import uvicorn
from fastapi.middleware.cors import CORSMiddleware
from controller.chat_controller import chat_router

app = FastAPI(title="芙芙助手")

# 跨域配置（必须加，解决前端跨域报错）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(chat_router)

@app.get("/")
def index():
    return {"status": "ok", "msg": "你好啊~ 同学！"}

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=5432, reload=False)