"""发送文件到微信的工具 — 支持图片/视频/文件"""

import asyncio
import logging
from pathlib import Path
from langchain.tools import tool

logger = logging.getLogger(__name__)


@tool
def send_file_to_wechat(file_path: str):
    """
    将本地图片/文件/视频发送到用户的微信上。
    当用户说"把这个发给我""发图片""发文件""发到微信"时，使用此工具。
    注意：必须传入电脑上真实存在的文件路径。
    :param file_path: 要发送的文件的完整路径，如 C:\\Users\\xxx\\Desktop\\图片.jpg
    """
    path = Path(file_path)
    if not path.exists():
        return f"文件不存在: {file_path}"

    from mi.manager import channel_manager
    channel = channel_manager.get("wechat")
    if not channel or not channel._api:
        return "微信通道未连接，请先在微信上扫码登录"
    if not channel._last_user_id:
        return "没有找到微信用户，请先在微信上给我发一条消息"

    try:
        asyncio.run(_send_async(
            bot_token=channel._api.bot_token,
            bot_base_url=channel._api.base_url,
            to_user_id=channel._last_user_id,
            context_token=channel._last_context_token,
            file_path=path,
        ))
        return f"已将 {path.name} 发送到你的微信！"
    except Exception as e:
        logger.exception("发送文件到微信失败")
        return f"发送文件失败: {e}"


async def _send_async(bot_token: str, bot_base_url: str,
                      to_user_id: str, context_token: str, file_path: Path):
    """上传本地文件到 CDN 并通过微信发送（import 全在函数内，避免循环导入）"""
    from mi.channels.wechat_api import ILinKAPI
    from mi.media_uploader import (
        compress_image, aes_encrypt, make_filekey,
        build_upload_url, aes_key_to_b64,
    )

    api = ILinKAPI(bot_token=bot_token, bot_base_url=bot_base_url)
    try:
        raw_data = file_path.read_bytes()
        ext = file_path.suffix.lower()

        image_exts = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp', '.tiff'}
        video_exts = {'.mp4', '.avi', '.mov', '.mkv', '.flv', '.wmv', '.webm'}

        if ext in image_exts:
            media_type = 1
            raw_data = compress_image(raw_data)
        elif ext in video_exts:
            media_type = 2
        else:
            media_type = 3

        ciphertext, aes_key, raw_md5 = aes_encrypt(raw_data)
        filekey = make_filekey()

        upload_resp = await api.get_upload_url(
            filekey=filekey, to_user_id=to_user_id,
            file_size=len(ciphertext), aes_key=aes_key.hex(),
            raw_size=len(raw_data), raw_md5=raw_md5,
            media_type=media_type,
        )
        upload_url = build_upload_url(upload_resp, filekey)
        if not upload_url:
            raise RuntimeError(f"获取上传 URL 失败: {upload_resp}")

        download_param = await api.upload_cdn(upload_url, ciphertext)
        if not download_param:
            raise RuntimeError("CDN 上传失败")

        aes_key_b64 = aes_key_to_b64(aes_key)

        if media_type == 1:
            item = {
                "media": {"encrypt_query_param": download_param, "aes_key": aes_key_b64, "encrypt_type": 1},
                "mid_size": len(ciphertext),
            }
        elif media_type == 2:
            item = {
                "media": {"encrypt_query_param": download_param, "aes_key": aes_key_b64, "encrypt_type": 1},
                "video_size": len(ciphertext),
            }
        else:
            item = {
                "media": {"encrypt_query_param": download_param, "aes_key": aes_key_b64, "encrypt_type": 1},
                "file_name": file_path.name,
                "len": str(len(raw_data)),
            }

        await api.send_media(
            to_user_id=to_user_id, context_token=context_token,
            media_type=media_type, item=item,
        )
        logger.info("文件已发送到微信: %s (类型=%d)", file_path.name, media_type)
    finally:
        await api.close()
