"""MI 层 — 通道基类

所有外部通道（微信、App、飞书等）继承 BaseChannel，
统一注册到 ChannelManager 管理启停和路由。
"""

from abc import ABC, abstractmethod
from typing import Optional


class BaseChannel(ABC):
    """消息通道基类"""

    name: str = ""

    @abstractmethod
    async def start(self):
        """启动通道（开始接收消息）"""
        ...

    @abstractmethod
    async def stop(self):
        """停止通道"""
        ...

    @property
    @abstractmethod
    def is_running(self) -> bool:
        """通道是否正在运行"""
        ...

    @abstractmethod
    async def send_message(self, to_user_id: str, text: str, **kwargs):
        """通过本通道发送消息"""
        ...
