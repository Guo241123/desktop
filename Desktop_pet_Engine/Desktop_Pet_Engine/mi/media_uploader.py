"""MI 层 — CDN 媒体上传工具

封装微信 CDN 上传的公共逻辑（AES 加密、图片压缩、CDN 上传），
供 mi/channels/wechat.py 和 tools/send_to_wechat.py 复用。
"""

import base64
import hashlib
import io
import logging
import secrets
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


def compress_image(raw_data: bytes, max_size: int = 300 * 1024,
                   max_dim: int = 800, quality: int = 70) -> bytes:
    """压缩图片到指定大小和尺寸以内"""
    if len(raw_data) <= max_size:
        return raw_data
    from PIL import Image
    img = Image.open(io.BytesIO(raw_data))
    if img.mode in ("RGBA", "P"):
        img = img.convert("RGB")
    if max(img.width, img.height) > max_dim:
        ratio = max_dim / max(img.width, img.height)
        img = img.resize((int(img.width * ratio), int(img.height * ratio)), Image.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=quality, optimize=True)
    return buf.getvalue()


def aes_encrypt(raw_data: bytes) -> tuple[bytes, bytes, str]:
    """AES-128-ECB 加密，返回 (ciphertext, aes_key_bytes, raw_md5)"""
    from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
    raw_size = len(raw_data)
    raw_md5 = hashlib.md5(raw_data).hexdigest()
    aes_key = secrets.token_bytes(16)
    pad_len = 16 - (raw_size % 16)
    padded = raw_data + bytes([pad_len] * pad_len)
    encryptor = Cipher(algorithms.AES(aes_key), modes.ECB()).encryptor()
    ciphertext = encryptor.update(padded) + encryptor.finalize()
    return ciphertext, aes_key, raw_md5


def make_filekey() -> str:
    """生成随机的文件 key"""
    return f"uu-{secrets.token_hex(8)}"


def build_upload_url(upload_resp: dict, filekey: str) -> Optional[str]:
    """从 API 返回中提取或拼接 CDN 上传 URL"""
    upload_url = upload_resp.get("upload_full_url", "") or upload_resp.get("upload_url", "")
    if not upload_url:
        upload_param = upload_resp.get("upload_param", "")
        if upload_param:
            from urllib.parse import quote
            upload_url = (
                f"https://novac2c.cdn.weixin.qq.com/c2c/upload"
                f"?encrypted_query_param={quote(upload_param)}&filekey={quote(filekey)}"
            )
    return upload_url or None


def aes_key_to_b64(aes_key: bytes) -> str:
    """将 AES key 转为 base64 编码字符串"""
    return base64.b64encode(aes_key.hex().encode()).decode()
