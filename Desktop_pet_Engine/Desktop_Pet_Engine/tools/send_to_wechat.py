"""发送文件到微信的工具 — 支持图片/视频/文件"""

import logging
import secrets
from base64 import b64encode
from pathlib import Path
from langchain.tools import tool
import httpx

from mi.media_uploader import (
    compress_image, aes_encrypt, make_filekey,
    build_upload_url, aes_key_to_b64,
)

logger = logging.getLogger(__name__)

# 常量（与 wechat_api.py 保持一致）
CHANNEL_VERSION = "2.1.1"
ILINK_APP_ID = "bot"
_ver = tuple(int(x) for x in CHANNEL_VERSION.split("."))
ILINK_APP_CLIENT_VERSION = str((_ver[0] << 16) | (_ver[1] << 8) | _ver[2])


def _build_headers(bot_token: str) -> dict:
    """构造 API 请求头"""
    random_uin = b64encode(str(secrets.randbelow(2 ** 32)).encode()).decode()
    return {
        "Content-Type": "application/json",
        "AuthorizationType": "ilink_bot_token",
        "X-WECHAT-UIN": random_uin,
        "iLink-App-Id": ILINK_APP_ID,
        "iLink-App-ClientVersion": ILINK_APP_CLIENT_VERSION,
        "Authorization": f"Bearer {bot_token}",
    }


def _send_file_sync(bot_token: str, bot_base_url: str,
                    to_user_id: str, context_token: str,
                    file_path: Path) -> None:
    """同步执行 加密→上传CDN→发送微信，全程不用 asyncio。"""
    import hashlib
    from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

    # ── 1. 读取文件 ──
    raw_data = file_path.read_bytes()
    ext = file_path.suffix.lower()
    headers = _build_headers(bot_token)

    # ── 2. 判断媒体类型 ──
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

    # ── 3. AES 加密 ──
    raw_size = len(raw_data)
    raw_md5 = hashlib.md5(raw_data).hexdigest()
    aes_key = secrets.token_bytes(16)
    pad_len = 16 - (raw_size % 16)
    padded = raw_data + bytes([pad_len] * pad_len)
    encryptor = Cipher(algorithms.AES(aes_key), modes.ECB()).encryptor()
    ciphertext = encryptor.update(padded) + encryptor.finalize()

    filekey = make_filekey()

    # ── 4. 获取上传 URL ──
    base_url = bot_base_url.rstrip("/") + "/"
    with httpx.Client(timeout=15) as client:
        upload_resp = client.post(
            f"{base_url}ilink/bot/getuploadurl",
            json={
                "filekey": filekey,
                "media_type": media_type,
                "to_user_id": to_user_id,
                "rawsize": raw_size,
                "rawfilemd5": raw_md5,
                "filesize": len(ciphertext),
                "aeskey": aes_key.hex(),
                "no_need_thumb": True,
                "base_info": {"channel_version": CHANNEL_VERSION},
            },
            headers=headers,
        )
        upload_resp.raise_for_status()
        upload_data = upload_resp.json()

    upload_full_url = (upload_data.get("upload_full_url") or "").strip()
    upload_param = upload_data.get("upload_param") or ""
    if upload_full_url:
        cdn_url = upload_full_url
    elif upload_param:
        from urllib.parse import quote
        cdn_url = f"https://novac2c.cdn.weixin.qq.com/c2c/upload?encrypted_query_param={quote(upload_param)}&filekey={quote(filekey)}"
    else:
        raise RuntimeError(f"获取上传 URL 失败: {upload_data}")

    # ── 5. 上传到 CDN ──
    download_param = ""
    for attempt in range(3):
        with httpx.Client(timeout=60) as client:
            r = client.post(
                cdn_url,
                content=ciphertext,
                headers={"Content-Type": "application/octet-stream"},
            )
            if 400 <= r.status_code < 500:
                err_msg = r.headers.get("x-error-message", r.text[:200])
                raise RuntimeError(f"CDN 上传拒绝 ({r.status_code}): {err_msg}")
            if r.status_code != 200:
                if attempt < 2:
                    logger.warning("CDN 上传 %d/3 失败 (%d)，重试", attempt + 1, r.status_code)
                    continue
                raise RuntimeError(f"CDN 上传失败 ({r.status_code})")
            download_param = r.headers.get("x-encrypted-param", "")
            if download_param:
                break
            if attempt < 2:
                logger.warning("CDN 响应缺少 x-encrypted-param，重试")
    if not download_param:
        raise RuntimeError("CDN 上传失败，无 download_param")

    # ── 6. 构建媒体 item ──
    aes_key_b64 = aes_key_to_b64(aes_key)
    media_ref = {
        "encrypt_query_param": download_param,
        "aes_key": aes_key_b64,
        "encrypt_type": 1,
    }

    if media_type == 1:
        item = {"type": 2, "image_item": {"media": media_ref, "mid_size": len(ciphertext)}}
    elif media_type == 2:
        item = {"type": 5, "video_item": {"media": media_ref, "video_size": len(ciphertext)}}
    else:
        item = {
            "type": 4,
            "file_item": {"media": media_ref, "file_name": file_path.name, "len": str(raw_size)},
        }

    # ── 7. 发送到微信 ──
    cid = f"uu-{secrets.token_hex(8)}"
    with httpx.Client(timeout=15) as client:
        send_resp = client.post(
            f"{base_url}ilink/bot/sendmessage",
            json={
                "msg": {
                    "from_user_id": "",
                    "to_user_id": to_user_id,
                    "client_id": cid,
                    "message_type": 2,
                    "message_state": 2,
                    "item_list": [item],
                    "context_token": context_token,
                },
                "base_info": {"channel_version": CHANNEL_VERSION},
            },
            headers=headers,
        )
        send_resp.raise_for_status()

    logger.info("文件已发送到微信: %s (类型=%d)", file_path.name, media_type)


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
        _send_file_sync(
            ctx["bot_token"], ctx["bot_base_url"],
            ctx["to_user_id"], ctx["context_token"],
            path,
        )
        return f"已将 {path.name} 发送到你的微信！"
    except Exception as e:
        logger.exception("发送文件到微信失败")
        return f"发送文件失败: {e}"
