"""MI 层 — 通道管理器

统一注册、启动、停止、查询所有消息通道。
"""

import logging
from typing import Dict, Optional
from mi.base import BaseChannel

logger = logging.getLogger(__name__)


class ChannelManager:
    """通道管理器"""

    def __init__(self):
        self._channels: Dict[str, BaseChannel] = {}

    def register(self, channel: BaseChannel):
        """注册一个通道"""
        if not channel.name:
            raise ValueError("通道必须设置 name")
        self._channels[channel.name] = channel
        logger.info("通道已注册: %s", channel.name)

    def get(self, name: str) -> Optional[BaseChannel]:
        return self._channels.get(name)

    @property
    def all(self) -> Dict[str, BaseChannel]:
        return dict(self._channels)

    async def start(self, name: str) -> dict:
        """启动指定通道，返回通道的启动结果（可能包含 qrcode 等信息）"""
        channel = self._channels.get(name)
        if not channel:
            return {"success": False, "msg": f"通道 '{name}' 未注册"}
        if channel.is_running:
            return {"success": False, "msg": f"通道 '{name}' 已在运行"}
        try:
            extra = await channel.start()
            if extra and isinstance(extra, dict):
                return {"success": True, **extra}
            return {"success": True, "msg": f"通道 '{name}' 已启动"}
        except Exception as e:
            logger.exception("启动通道 %s 失败", name)
            return {"success": False, "msg": str(e)}

    async def stop(self, name: str) -> dict:
        """停止指定通道"""
        channel = self._channels.get(name)
        if not channel:
            return {"success": False, "msg": f"通道 '{name}' 未注册"}
        if not channel.is_running:
            return {"success": False, "msg": f"通道 '{name}' 未在运行"}
        try:
            await channel.stop()
            return {"success": True, "msg": f"通道 '{name}' 已停止"}
        except Exception as e:
            logger.exception("停止通道 %s 失败", name)
            return {"success": False, "msg": str(e)}

    def status(self) -> dict:
        """所有通道状态"""
        return {
            name: {
                "name": name,
                "running": ch.is_running,
            }
            for name, ch in self._channels.items()
        }


# ── 全局单例 ──────────────────────────────────────────────────
channel_manager = ChannelManager()
