"""发送文件到微信的工具 — 支持图片/视频/文件"""

import asyncio
import logging
import threading
from pathlib import Path
from langchain.tools import tool

from mi.media_uploader import (
    compress_image, aes_encrypt, make_filekey,
    build_upload_url, aes_key_to_b64,
)

logger = logging.getLogger(__name__)


def _run_async_new_loop(coro_fn, *args, **kwargs):
    """在独立线程的新事件环中运行协程函数。

    协程在新线程内部创建，避免跨线程传递协程对象的线程安全问题。
    httpx.AsyncClient 也在新线程的事件环上创建，不会绑定冲突。
    """
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro_fn(*args, **kwargs))

    result = []
    error = []

    def _target():
        try:
            new_loop = asyncio.new_event_loop()
            asyncio.set_event_loop(new_loop)
            result.append(new_loop.run_until_complete(coro_fn(*args, **kwargs)))
            new_loop.close()
        except Exception as e:
            error.append(e)

    t = threading.Thread(target=_target)
    t.start()
    t.join()
    if error:
        raise error[0]
    return result[0] if result else None


async def _upload_and_send(bot_token: str, bot_base_url: str,
                           to_user_id: str, context_token: str,
                           file_path: Path):
    """在新事件环中完整执行 加密→上传CDN→发送微信 流程。"""
    from mi.channels.wechat_api import ILinKAPI

    api = ILinKAPI(bot_token=bot_token, bot_base_url=bot_base_url)
    try:
        raw_data = file_path.read_bytes()
        ext = file_path.suffix.lower()

        image_exts = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp', '.tiff'}
        video_exts = {'.mp4', '.avi', '.mov', '.mkv', '.flv', '.wmv', '.webm'}

        if ext in image_exts:
            media_type = 1
            raw_data = compress_image(raw_data)
            logger.info("图片压缩: %s -> %dKB", file_path.name, len(raw_data) // 1024)
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
            raise RuntimeError("CDN 上传失败，无 download_param")

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
    ctx = channel.get_send_context() if channel else None
    if not ctx:
        return "微信通道未连接或还未收到过你的消息，请先在微信上和我聊一句再试"

    try:
        _run_async_new_loop(
            _upload_and_send,
            ctx["bot_token"], ctx["bot_base_url"],
            ctx["to_user_id"], ctx["context_token"],
            path,
        )
        return f"已将 {path.name} 发送到你的微信！"
    except Exception as e:
        logger.exception("发送文件到微信失败")
        return f"发送文件失败: {e}"
