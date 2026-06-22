"""MI 通道 — 微信 API 客户端 + 认证管理

从 wechat.py 拆分出：API 客户端、常量、认证管理。
"""

import asyncio
import base64
import json
import logging
import random
import secrets
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx

from config.paths import WECHAT_CREDENTIALS_DIR, WECHAT_CREDENTIALS_FILE

logger = logging.getLogger(__name__)

# ==============================================================
# 常量
# ==============================================================

CHANNEL_VERSION = "2.1.1"
ILINK_APP_ID = "bot"
_ver = tuple(int(x) for x in CHANNEL_VERSION.split("."))
ILINK_APP_CLIENT_VERSION = str((_ver[0] << 16) | (_ver[1] << 8) | _ver[2])


class MsgDirection:
    USER = 1
    BOT = 2


class MsgState:
    PENDING = 1
    FINISH = 2


class UploadMediaType:
    IMAGE = 1
    VIDEO = 2
    FILE = 3
    VOICE = 4


class MessageItemType:
    TEXT = 1
    IMAGE = 2
    VOICE = 3
    FILE = 4
    VIDEO = 5


# ==============================================================
# API 客户端
# ==============================================================

class ILinKAPI:
    """iLink Bot API 客户端"""

    BASE_URL = "https://ilinkai.weixin.qq.com"

    def __init__(self, bot_token: Optional[str] = None, bot_base_url: Optional[str] = None):
        self.bot_token = bot_token
        self.base_url = bot_base_url or self.BASE_URL
        self.client = httpx.AsyncClient(timeout=httpx.Timeout(70.0, connect=10.0))
        self.get_updates_buf = ""

    def _get_headers(self) -> Dict[str, str]:
        headers = {
            "Content-Type": "application/json",
            "AuthorizationType": "ilink_bot_token",
            "iLink-App-Id": ILINK_APP_ID,
            "iLink-App-ClientVersion": ILINK_APP_CLIENT_VERSION,
        }
        if self.bot_token:
            headers["Authorization"] = f"Bearer {self.bot_token}"
            random_uin = random.randint(0, 2 ** 32 - 1)
            headers["X-WECHAT-UIN"] = base64.b64encode(str(random_uin).encode()).decode()
        return headers

    async def get_bot_qrcode(self) -> Dict[str, Any]:
        resp = await self.client.get(
            f"{self.BASE_URL}/ilink/bot/get_bot_qrcode",
            params={"bot_type": "3"}
        )
        resp.raise_for_status()
        return resp.json()

    async def get_qrcode_status(self, qrcode_id: str) -> Dict[str, Any]:
        resp = await self.client.get(
            f"{self.BASE_URL}/ilink/bot/get_qrcode_status",
            params={"qrcode": qrcode_id}
        )
        resp.raise_for_status()
        return resp.json()

    async def get_updates(self) -> Dict[str, Any]:
        payload = {
            "get_updates_buf": self.get_updates_buf,
            "base_info": {"channel_version": CHANNEL_VERSION}
        }
        resp = await self.client.post(
            f"{self.base_url}/ilink/bot/getupdates",
            json=payload,
            headers=self._get_headers()
        )
        resp.raise_for_status()
        data = resp.json()
        if "get_updates_buf" in data:
            self.get_updates_buf = data["get_updates_buf"]
        return data

    async def send_message(self, to_user_id: str, context_token: str, text: str) -> Dict[str, Any]:
        cid = f"uu-{secrets.token_hex(8)}"
        payload = {
            "msg": {
                "from_user_id": "",
                "to_user_id": to_user_id,
                "client_id": cid,
                "message_type": MsgDirection.BOT,
                "message_state": MsgState.FINISH,
                "item_list": [
                    {
                        "type": MessageItemType.TEXT,
                        "text_item": {"text": text}
                    }
                ],
                "context_token": context_token,
            },
            "base_info": {"channel_version": CHANNEL_VERSION},
        }
        resp = await self.client.post(
            f"{self.base_url}/ilink/bot/sendmessage",
            json=payload,
            headers=self._get_headers()
        )
        resp.raise_for_status()
        return resp.json()

    async def get_config(self, ilink_user_id: str, context_token: str = "") -> Dict[str, Any]:
        payload = {
            "ilink_user_id": ilink_user_id,
            "context_token": context_token,
            "base_info": {"channel_version": CHANNEL_VERSION},
        }
        resp = await self.client.post(
            f"{self.base_url}/ilink/bot/getconfig",
            json=payload,
            headers=self._get_headers()
        )
        resp.raise_for_status()
        return resp.json()

    async def send_typing(self, ilink_user_id: str, typing_ticket: str, status: int = 1):
        payload = {
            "ilink_user_id": ilink_user_id,
            "typing_ticket": typing_ticket,
            "status": status,
            "base_info": {"channel_version": CHANNEL_VERSION},
        }
        resp = await self.client.post(
            f"{self.base_url}/ilink/bot/sendtyping",
            json=payload,
            headers=self._get_headers()
        )
        resp.raise_for_status()

    # ── CDN 上传 & 发送图片 ─────────────────────────────────────

    async def get_upload_url(self, filekey: str, to_user_id: str, file_size: int,
                             aes_key: str, raw_size: int, raw_md5: str,
                             media_type: int = UploadMediaType.IMAGE) -> Dict[str, Any]:
        payload = {
            "filekey": filekey,
            "media_type": media_type,
            "to_user_id": to_user_id,
            "rawsize": raw_size,
            "rawfilemd5": raw_md5,
            "filesize": file_size,
            "aeskey": aes_key,
            "no_need_thumb": True,
            "base_info": {"channel_version": CHANNEL_VERSION},
        }
        resp = await self.client.post(
            f"{self.base_url}/ilink/bot/getuploadurl",
            json=payload,
            headers=self._get_headers()
        )
        resp.raise_for_status()
        return resp.json()

    async def upload_cdn(self, upload_url: str, data: bytes, max_retries: int = 3) -> str:
        for attempt in range(max_retries):
            try:
                async with httpx.AsyncClient(timeout=30) as c:
                    resp = await c.post(
                        upload_url,
                        content=data,
                        headers={"Content-Type": "application/octet-stream"}
                    )
                    if resp.is_success:
                        return resp.headers.get("x-encrypted-param", "")
                    if 400 <= resp.status_code < 500:
                        err_msg = resp.headers.get("x-error-message", resp.text[:200])
                        raise RuntimeError(f"CDN 上传请求被拒绝 ({resp.status_code}): {err_msg}")
                    err_msg = resp.headers.get("x-error-message", resp.text[:200])
                    if attempt < max_retries - 1:
                        wait = 2 ** attempt
                        logger.warning("CDN 上传 %d/%d 失败 (%d)，%.1fs 后重试: %s",
                                       attempt + 1, max_retries, resp.status_code, wait, err_msg)
                        await asyncio.sleep(wait)
                    else:
                        raise RuntimeError(f"CDN 上传失败 ({resp.status_code}) 已重试 {max_retries} 次: {err_msg}")
            except (httpx.TimeoutException, httpx.ConnectError) as e:
                if attempt < max_retries - 1:
                    wait = 2 ** attempt
                    logger.warning("CDN 上传网络错误 %d/%d，%.1fs 后重试: %s", attempt + 1, max_retries, wait, e)
                    await asyncio.sleep(wait)
                else:
                    raise RuntimeError(f"CDN 上传网络错误，已重试 {max_retries} 次: {e}")
        return ""

    async def send_image(self, to_user_id: str, context_token: str,
                         download_param: str, aes_key_b64: str, file_size: int):
        cid = f"uu-{secrets.token_hex(8)}"
        payload = {
            "msg": {
                "from_user_id": "",
                "to_user_id": to_user_id,
                "client_id": cid,
                "message_type": MsgDirection.BOT,
                "message_state": MsgState.FINISH,
                "item_list": [{
                    "type": MessageItemType.IMAGE,
                    "image_item": {
                        "media": {
                            "encrypt_query_param": download_param,
                            "aes_key": aes_key_b64,
                            "encrypt_type": 1,
                        },
                        "mid_size": file_size,
                    }
                }],
                "context_token": context_token,
            },
            "base_info": {"channel_version": CHANNEL_VERSION},
        }
        resp = await self.client.post(
            f"{self.base_url}/ilink/bot/sendmessage",
            json=payload,
            headers=self._get_headers()
        )
        resp.raise_for_status()

    # ── CDN 下载 & 解密 ─────────────────────────────────────────

    async def download_cdn(self, encrypt_query_param: str) -> bytes:
        from urllib.parse import quote
        url = f"https://novac2c.cdn.weixin.qq.com/c2c/download?encrypted_query_param={quote(encrypt_query_param)}"
        async with httpx.AsyncClient(timeout=30, follow_redirects=True) as c:
            resp = await c.get(url, headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            })
            resp.raise_for_status()
            return resp.content

    @staticmethod
    def decrypt_media(data: bytes, aes_key_hex: str) -> bytes:
        from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
        key = bytes.fromhex(aes_key_hex)
        decryptor = Cipher(algorithms.AES(key), modes.ECB()).decryptor()
        plaintext = decryptor.update(data) + decryptor.finalize()
        pad = plaintext[-1]
        if 1 <= pad <= 16 and all(b == pad for b in plaintext[-pad:]):
            plaintext = plaintext[:-pad]
        return plaintext

    async def send_media(self, to_user_id: str, context_token: str,
                         media_type: int, item: dict):
        type_map = {1: "image_item", 2: "video_item", 3: "file_item"}
        type_id = {1: 2, 2: 5, 3: 4}
        cid = f"uu-{secrets.token_hex(8)}"
        payload = {
            "msg": {
                "from_user_id": "",
                "to_user_id": to_user_id,
                "client_id": cid,
                "message_type": MsgDirection.BOT,
                "message_state": MsgState.FINISH,
                "item_list": [{
                    "type": type_id.get(media_type, 2),
                    type_map.get(media_type, "image_item"): item,
                }],
                "context_token": context_token,
            },
            "base_info": {"channel_version": CHANNEL_VERSION},
        }
        resp = await self.client.post(
            f"{self.base_url}/ilink/bot/sendmessage",
            json=payload,
            headers=self._get_headers()
        )
        resp.raise_for_status()

    async def close(self):
        await self.client.aclose()


# ==============================================================
# 认证管理
# ==============================================================

STATE_DIR = WECHAT_CREDENTIALS_DIR
CREDENTIALS_FILE = WECHAT_CREDENTIALS_FILE


def load_credentials() -> Optional[Dict[str, Any]]:
    if not CREDENTIALS_FILE.exists():
        return None
    try:
        with open(CREDENTIALS_FILE, "r") as f:
            return json.load(f)
    except Exception:
        return None


def save_credentials(data: Dict[str, Any]):
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    with open(CREDENTIALS_FILE, "w") as f:
        json.dump(data, f, indent=2)
