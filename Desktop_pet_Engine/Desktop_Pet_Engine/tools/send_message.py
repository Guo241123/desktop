"""主动发送消息到微信的工具

AI 可以用此工具在空闲时主动给用户发消息。
"""

import logging
from langchain.tools import tool
from tools.send_to_wechat import _build_headers
import httpx

logger = logging.getLogger(__name__)


@tool
def send_message(text: str):
    """
    主动给用户发送一条微信消息。
    用于长时间没收到用户消息时，主动找用户聊天、问候、提醒等。
    :param text: 要发送的消息内容
    """
    if not text.strip():
        return "消息不能为空"

    from mi.manager import channel_manager
    channel = channel_manager.get("wechat")
    if not channel:
        return "微信通道未启动"
    ctx = channel.get_send_context()
    if not ctx:
        return "微信通道未连接或还未收到过你的消息，请先在微信上和我聊一句再试"

    try:
        from mi.channels.wechat_api import CHANNEL_VERSION
        base_url = ctx["bot_base_url"].rstrip("/") + "/"
        headers = _build_headers(ctx["bot_token"])
        cid = f"uu-{__import__('secrets').token_hex(8)}"

        with httpx.Client(timeout=15) as client:
            resp = client.post(
                f"{base_url}ilink/bot/sendmessage",
                json={
                    "msg": {
                        "from_user_id": "",
                        "to_user_id": ctx["to_user_id"],
                        "client_id": cid,
                        "message_type": 2,
                        "message_state": 2,
                        "item_list": [{
                            "type": 1,
                            "text_item": {"text": text},
                        }],
                        "context_token": ctx["context_token"],
                    },
                    "base_info": {"channel_version": CHANNEL_VERSION},
                },
                headers=headers,
            )
            resp.raise_for_status()

        logger.info("主动消息已发送: %.40s", text)
        return f"✅ 消息已发送给用户"
    except Exception as e:
        logger.exception("发送主动消息失败")
        return f"发送失败: {e}"
