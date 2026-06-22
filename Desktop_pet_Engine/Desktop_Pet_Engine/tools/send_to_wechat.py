"""发送文件到微信的工具 — 支持图片/视频/文件"""

import asyncio
import logging
from pathlib import Path
from langchain.tools import tool

from mi.media_uploader import (
    compress_image, aes_encrypt, make_filekey,
    build_upload_url, aes_key_to_b64,
)

logger = logging.getLogger(__name__)


async def _send_file_async(bot_token: str, to_user_id: str, context_token: str, file_path: Path):
    """上传本地文件到 CDN 并通过微信发送（自动识别类型）"""
    from mi.channels.wechat_api import ILinKAPI

    api = ILinKAPI(bot_token=bot_token)
    try:
        raw_data = file_path.read_bytes()
        ext = file_path.suffix.lower()

        # 判断媒体类型
        image_exts = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp', '.tiff'}
        video_exts = {'.mp4', '.avi', '.mov', '.mkv', '.flv', '.wmv', '.webm'}
        file_exts = {'.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx',
                     '.zip', '.rar', '.7z', '.txt', '.md', '.csv', '.json'}

        if ext in image_exts:
            media_type = 1  # IMAGE
            raw_data = compress_image(raw_data)
            logger.info("图片压缩: %s -> %dKB", file_path.name, len(raw_data) // 1024)
        elif ext in video_exts:
            media_type = 2  # VIDEO
        else:
            media_type = 3  # FILE

        ciphertext, aes_key, raw_md5 = aes_encrypt(raw_data)
        filekey = make_filekey()

        upload_resp = await api.get_upload_url(
            filekey=filekey,
            to_user_id=to_user_id,
            file_size=len(ciphertext),
            aes_key=aes_key.hex(),
            raw_size=len(raw_data),
            raw_md5=raw_md5,
            media_type=media_type,
        )
        upload_url = build_upload_url(upload_resp, filekey)
        if not upload_url:
            raise RuntimeError(f"获取上传 URL 失败: {upload_resp}")

        download_param = await api.upload_cdn(upload_url, ciphertext)
        if not download_param:
            raise RuntimeError("CDN 上传失败，无 download_param")

        aes_key_b64 = aes_key_to_b64(aes_key)

        if media_type == 1:  # IMAGE
            item = {
                "media": {"encrypt_query_param": download_param, "aes_key": aes_key_b64, "encrypt_type": 1},
                "mid_size": len(ciphertext),
            }
        elif media_type == 2:  # VIDEO
            item = {
                "media": {"encrypt_query_param": download_param, "aes_key": aes_key_b64, "encrypt_type": 1},
                "video_size": len(ciphertext),
            }
        else:  # FILE
            item = {
                "media": {"encrypt_query_param": download_param, "aes_key": aes_key_b64, "encrypt_type": 1},
                "file_name": file_path.name,
                "len": str(len(raw_data)),
            }

        await api.send_media(
            to_user_id=to_user_id,
            context_token=context_token,
            media_type=media_type,
            item=item,
        )
        logger.info("文件已发送到微信: %s (类型=%d)", file_path.name, media_type)
    finally:
        await api.close()


@tool
def send_file_to_wechat(file_path: str):
    """
    将本地文件通过微信发送给用户（支持图片/视频/文档/压缩包等常见格式）。
    当用户要求你把电脑上的文件/图片/视频发到他们的微信时，使用此工具。
    :param file_path: 要发送的文件的完整路径
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

    bot_token = channel._api.bot_token
    to_user_id = channel._last_user_id
    context_token = channel._last_context_token

    try:
        asyncio.run(_send_file_async(
            bot_token=bot_token, to_user_id=to_user_id,
            context_token=context_token, file_path=path,
        ))
        return f"已将 {path.name} 发送到你的微信！"
    except Exception as e:
        logger.exception("发送文件到微信失败")
        return f"发送文件失败: {e}"
