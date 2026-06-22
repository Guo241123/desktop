"""Gateway 层 — MI 通道控制接口

提供通道的启动、停止、状态查询 REST API。
启动时会自动处理扫码登录流程（无阻塞，返回二维码）。
"""

from fastapi import APIRouter
from pydantic import BaseModel
from mi import channel_manager

mi_router = APIRouter(prefix="/api/mi", tags=["消息通道"])


class ChannelActionRequest(BaseModel):
    channel: str = "wechat"


@mi_router.post("/start")
async def start_channel(req: ChannelActionRequest):
    """启动指定消息通道（无凭证时返回二维码信息，不阻塞）"""
    result = await channel_manager.start(req.channel)
    return result


@mi_router.post("/stop")
async def stop_channel(req: ChannelActionRequest):
    """停止指定消息通道"""
    result = await channel_manager.stop(req.channel)
    return result


@mi_router.get("/status")
def channel_status():
    """查看所有通道状态（含登录二维码等详情）"""
    channels = channel_manager.status()
    # 如果通道有额外登录信息（如二维码），一并返回
    for name, info in channels.items():
        ch = channel_manager.get(name)
        if ch and hasattr(ch, "login_status"):
            info["login"] = ch.login_status
    return {"success": True, "channels": channels}
