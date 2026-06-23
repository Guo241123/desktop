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
    result = await channel_manager.start("wechat")
    logger.info("微信通道启动: %s", result.get("msg", ""))
    return result


def delete_wechat_credentials():
    from mi.channels.wechat_api import delete_credentials as _delete
    _delete()


@mi_router.post("/start")
async def start_channel(req: ChannelActionRequest):
    if req.channel == "wechat":
        return await start_wechat_channel()
    result = await channel_manager.start(req.channel)
    return result


@mi_router.post("/stop")
async def stop_channel(req: ChannelActionRequest):
    result = await channel_manager.stop(req.channel)
    return result


@mi_router.get("/status")
def channel_status():
    channels = channel_manager.status()
    for name, info in channels.items():
        ch = channel_manager.get(name)
        if ch and hasattr(ch, "login_status"):
            info["login"] = ch.login_status
    return {"success": True, "channels": channels}


@mi_router.get("/debug-send")
def debug_send(file_path: str = None):
    """调试发送文件。传 file_path 参数则发指定文件，否则自动测"""
    ch = channel_manager.get("wechat")
    if not ch:
        return {"error": "通道不存在"}

    from tools.send_to_wechat import send_file_to_wechat

    info = {
        "running": ch._running,
        "has_api": ch._api is not None,
        "last_user_id": ch._last_user_id or "(空)",
    }
    if ch._api:
        info["bot_base_url"] = ch._api.base_url

    ctx = ch.get_send_context() if hasattr(ch, "get_send_context") else None
    if not ctx:
        return {**info, "send_context": False}

    if file_path:
        try:
            r = send_file_to_wechat.invoke({"file_path": file_path})
            info["send_result"] = r
        except Exception as e:
            info["send_error"] = str(e)
        return info

    # 无 file_path 时自动测
    import tempfile, os
    tmp = tempfile.NamedTemporaryFile(suffix='.txt', delete=False, mode='w', encoding='utf-8')
    tmp.write("test")
    tmp.close()
    try:
        info["test_func"] = send_file_to_wechat.func(tmp.name)
    except Exception as e:
        info["test_func_error"] = str(e)
    try:
        info["test_invoke"] = send_file_to_wechat.invoke({"file_path": tmp.name})
    except Exception as e:
        info["test_invoke_error"] = str(e)
    os.unlink(tmp.name)
    return info
