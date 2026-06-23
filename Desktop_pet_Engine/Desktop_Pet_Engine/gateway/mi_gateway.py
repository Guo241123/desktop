"""Gateway 层 — MI 通道控制接口

提供通道的启动、停止、状态查询 REST API。
启动时会自动处理扫码登录流程（无阻塞，返回二维码）。
"""

import logging
from fastapi import APIRouter
from pydantic import BaseModel
from mi import channel_manager

logger = logging.getLogger(__name__)

mi_router = APIRouter(prefix="/api/mi", tags=["消息通道"])


class ChannelActionRequest(BaseModel):
    channel: str = "wechat"


async def start_wechat_channel() -> dict:
    """启动微信通道（网关层统一入口，用于 HTTP 和启动事件）"""
    result = await channel_manager.start("wechat")
    logger.info("微信通道启动: %s", result.get("msg", ""))
    return result


def delete_wechat_credentials():
    """删除微信登录凭证（网关层统一入口）"""
    from mi.channels.wechat_api import delete_credentials as _delete
    _delete()


@mi_router.post("/start")
async def start_channel(req: ChannelActionRequest):
    """启动指定消息通道（无凭证时返回二维码信息，不阻塞）"""
    if req.channel == "wechat":
        return await start_wechat_channel()
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
