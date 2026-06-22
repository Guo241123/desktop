# Gateway层 - 路由注册
from fastapi import APIRouter
from gateway.chat_gateway import chat_router
from gateway.settings_gateway import settings_router
from gateway.mi_gateway import mi_router


# 统一注册所有路由
def register_routes(app):
    app.include_router(chat_router)
    app.include_router(settings_router)
    app.include_router(mi_router)
