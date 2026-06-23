"""发送表情包到微信的工具

AI Agent 可以通过此工具自由选择和发送表情包。
表情包文件存在 data/stickers/ 下，文件名就是表情包的含义。
"""

import logging
from pathlib import Path
from langchain.tools import tool
from config.paths import STICKERS_DIR
from tools.send_to_wechat import _send_file_sync

logger = logging.getLogger(__name__)


def _get_stickers() -> dict[str, Path]:
    """返回 {文件名(不含后缀): 路径} 映射"""
    stickers = {}
    for p in sorted(STICKERS_DIR.glob("*.*")):
        name = p.stem
        stickers[name] = p
    return stickers


@tool
def list_stickers():
    """
    列出 data/stickers 目录下所有可用的表情包名称。
    调用 send_sticker 前可以先看看有哪些表情包可以用。
    """
    stickers = _get_stickers()
    if not stickers:
        return "还没有表情包哦~"
    names = "\n".join(f"- {name}" for name in stickers)
    return f"当前可用的表情包有:\n{names}"


@tool
def send_sticker(sticker_name: str):
    """
    发送一张表情包到用户的微信。
    表情包文件存在 data/stickers 目录下，文件名就是表情包的意思。
    先调用 list_stickers 看看有哪些可用的表情包。
    :param sticker_name: 表情包名称（不带后缀），如"比心"、"乖巧"、"笑麻了"
    """
    stickers = _get_stickers()
    if not stickers:
        return "表情包目录是空的，还没有可用表情包"

    # 精确匹配
    if sticker_name in stickers:
        path = stickers[sticker_name]
    else:
        # 模糊匹配：名称包含关系
        matches = [name for name in stickers
                   if sticker_name in name or name in sticker_name]
        if matches:
            path = stickers[matches[0]]
            logger.info("模糊匹配表情包: %s → %s", sticker_name, matches[0])
        else:
            available = "、".join(stickers.keys())
            return f"没找到叫「{sticker_name}」的表情包。可用表情包: {available}"

    from mi.manager import channel_manager
    channel = channel_manager.get("wechat")
    if not channel:
        return "微信通道未启动"
    ctx = channel.get_send_context()
    if not ctx:
        return "微信通道未连接或还未收到过你的消息，请先在微信上和我聊一句再试"

    try:
        _send_file_sync(
            ctx["bot_token"], ctx["bot_base_url"],
            ctx["to_user_id"], ctx["context_token"],
            path,
        )
        return f"已发送表情包「{path.stem}」到你的微信！"
    except Exception as e:
        logger.exception("发送表情包失败")
        return f"发送表情包失败: {e}"
