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
    for name, info in channels.items():
        ch = channel_manager.get(name)
        if ch and hasattr(ch, "login_status"):
            info["login"] = ch.login_status
    return {"success": True, "channels": channels}


@mi_router.get("/debug-send")
def debug_send():
    """调试：检查微信发送上下文，可选测试发送"""
    ch = channel_manager.get("wechat")
    if not ch:
        return {"error": "通道不存在"}
    
    info = {
        "running": ch._running,
        "has_api": ch._api is not None,
        "last_user_id": ch._last_user_id or "(空)",
        "last_context_token": ch._last_context_token[:20] + "..." if ch._last_context_token else "(空)",
    }
    if ch._api:
        info["bot_base_url"] = ch._api.base_url
        info["bot_token"] = ch._api.bot_token[:20] + "..." if ch._api.bot_token else None
    
    ctx = ch.get_send_context() if hasattr(ch, "get_send_context") else None
    info["send_context"] = ctx is not None
    
    # 尝试发测试文件
    import tempfile, os
    tmp = tempfile.NamedTemporaryFile(suffix='.txt', delete=False, mode='w', encoding='utf-8')
    tmp.write("Hello from bot debug test!")
    tmp.close()
    
    from tools.send_to_wechat import send_file_to_wechat
    try:
        # 模拟 agent 调用方式：invoke
        result = send_file_to_wechat.invoke({"file_path": tmp.name})
        info["test_result"] = result
    except Exception as e:
        info["test_error"] = str(e)
    finally:
        os.unlink(tmp.name)
    
    return info
