# MI 层 — 消息接口（Message Interface）
# 统一管理所有外部消息通道（微信、App、飞书等）

from mi.base import BaseChannel
from mi.manager import ChannelManager, channel_manager
from mi.router import route_to_agent

# ── 自动注册已知通道 ──────────────────────────────────────────
from mi.channels.wechat import WeChatChannel
channel_manager.register(WeChatChannel())
