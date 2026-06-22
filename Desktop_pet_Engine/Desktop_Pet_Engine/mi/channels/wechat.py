"""MI 通道 — 微信（iLink Bot API）

支持扫码登录、长轮询接收消息、自动回复。
基于 @tencent-weixin/openclaw-weixin 源码分析实现。
"""

import asyncio
import base64
import hashlib
import json
import logging
import os
import random
import secrets
import time
import webbrowser
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx
import qrcode

from mi.base import BaseChannel
from mi.router import route_to_agent
from agent.prompts import WECHAT_SYSTEM_PROMPT
from config.paths import WECHAT_CREDENTIALS_DIR, WECHAT_CREDENTIALS_FILE, STICKERS_DIR

logger = logging.getLogger(__name__)

# ==============================================================
# 常量定义
# ==============================================================

CHANNEL_VERSION = "2.1.1"
ILINK_APP_ID = "bot"
_ver = tuple(int(x) for x in CHANNEL_VERSION.split("."))
ILINK_APP_CLIENT_VERSION = str((_ver[0] << 16) | (_ver[1] << 8) | _ver[2])

class MsgDirection:
    """消息方向"""
    USER = 1       # 用户发来
    BOT = 2        # Bot 发出

class MsgState:
    """消息状态"""
    PENDING = 1
    FINISH = 2

class UploadMediaType:
    """CDN 上传媒体类型（官方 SDK UploadMediaType）"""
    IMAGE = 1
    VIDEO = 2
    FILE = 3
    VOICE = 4


class MessageItemType:
    """消息条目类型"""
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
        """获取登录二维码"""
        resp = await self.client.get(
            f"{self.BASE_URL}/ilink/bot/get_bot_qrcode",
            params={"bot_type": "3"}
        )
        resp.raise_for_status()
        result = resp.json()
        logger.info("get_bot_qrcode 返回: %s", result)
        return result

    async def get_qrcode_status(self, qrcode_id: str) -> Dict[str, Any]:
        """检查二维码扫描状态"""
        resp = await self.client.get(
            f"{self.BASE_URL}/ilink/bot/get_qrcode_status",
            params={"qrcode": qrcode_id}
        )
        resp.raise_for_status()
        result = resp.json()
        logger.info("get_qrcode_status 返回: %s", result)
        return result

    async def get_updates(self) -> Dict[str, Any]:
        """长轮询获取消息更新"""
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
        """发送消息回复"""
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
        result = resp.json()
        logger.info("send_message 状态=%s 返回=%s", resp.status_code, result)
        return result

    async def get_config(self, ilink_user_id: str, context_token: str = "") -> Dict[str, Any]:
        """获取配置信息（含 typing_ticket）"""
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
        """发送正在输入状态（1=输入中, 2=取消）"""
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
        """获取 CDN 上传地址"""
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
        """上传加密数据到 CDN，返回 download_param（含重试）"""
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
                        logger.warning("CDN 上传 %d/%d 失败 (%d)，%.1fs 后重试: %s", attempt + 1, max_retries, resp.status_code, wait, err_msg)
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
        """发送图片消息"""
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

    # ── CDN 下载 & 解密（接收媒体） ─────────────────────────────

    async def download_cdn(self, encrypt_query_param: str) -> bytes:
        """从 CDN 下载加密的媒体数据"""
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
        """AES-128-ECB 解密媒体数据"""
        from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
        key = bytes.fromhex(aes_key_hex)
        decryptor = Cipher(algorithms.AES(key), modes.ECB()).decryptor()
        plaintext = decryptor.update(data) + decryptor.finalize()
        # PKCS7 去填充
        pad = plaintext[-1]
        if 1 <= pad <= 16 and all(b == pad for b in plaintext[-pad:]):
            plaintext = plaintext[:-pad]
        return plaintext

    async def send_media(self, to_user_id: str, context_token: str,
                         media_type: int, item: dict):
        """发送媒体消息（通用：图片=1, 视频=2, 文件=3）"""
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


def _load_credentials() -> Optional[Dict[str, Any]]:
    if not CREDENTIALS_FILE.exists():
        return None
    try:
        with open(CREDENTIALS_FILE, "r") as f:
            return json.load(f)
    except Exception:
        return None


def _save_credentials(data: Dict[str, Any]):
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    with open(CREDENTIALS_FILE, "w") as f:
        json.dump(data, f, indent=2)
    os.chmod(CREDENTIALS_FILE, 0o600)


def _ensure_credentials() -> tuple[str, Optional[str]]:
    """确保有有效凭证，优先使用已保存的"""
    creds = _load_credentials()
    if creds and creds.get("bot_token"):
        logger.info("使用已保存的微信 Bot 登录凭证")
        return creds["bot_token"], creds.get("bot_base_url")
    return "", None


# ==============================================================
# 微信通道
# ==============================================================

class WeChatChannel(BaseChannel):
    """微信消息通道"""

    name = "wechat"

    def __init__(self):
        self._api: Optional[ILinKAPI] = None
        self._running = False
        self._task: Optional[asyncio.Task] = None
        self._login_task: Optional[asyncio.Task] = None
        self._last_qrcode: Optional[dict] = None
        # 用于定时提醒
        self._last_user_id: str = ""
        self._last_context_token: str = ""
        self._reminder_task: Optional[asyncio.Task] = None

    @staticmethod
    def _split_text(text: str, max_len: int = 600) -> list[str]:
        """按句子拆成多条消息发送"""
        import re
        sentences = re.split(r"(?<=[~。！？.!?])", text)
        chunks = [s.strip() for s in sentences if s.strip()]
        return chunks if chunks else [text]

    # ── 表情包 ──────────────────────────────────────────────────

    @staticmethod
    def _pick_sticker(text: str) -> Optional[Path]:
        """根据回复内容关键词匹配最合适的表情包"""
        stickers = sorted(STICKERS_DIR.glob("*.*"))
        if not stickers:
            return None
        # 按文件名包含的字在回复中出现的次数打分
        scores = []
        for s in stickers:
            name = s.stem
            score = sum(1 for ch in name if ch in text)
            # 加一点随机扰动，不会总选同一个
            score += random.random() * 0.5
            scores.append((score, s))
        scores.sort(key=lambda x: -x[0])
        return scores[0][1]

    async def _send_sticker(self, to_user_id: str, context_token: str, reply_text: str):
        """以 1/4 概率上传并发送一张匹配的表情包"""
        if random.random() > 0.25:
            return
        sticker_path = self._pick_sticker(reply_text)
        if not sticker_path:
            return
        try:
            from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
            from PIL import Image
            import io

            # 读取图片并压缩
            raw_data = sticker_path.read_bytes()
            MAX_SIZE = 300 * 1024  # 300KB
            if len(raw_data) > MAX_SIZE:
                img = Image.open(sticker_path)
                # 转 RGB（兼容 PNG/WebP）
                if img.mode in ("RGBA", "P"):
                    img = img.convert("RGB")
                # 长边不超过 800px
                if max(img.width, img.height) > 800:
                    ratio = 800 / max(img.width, img.height)
                    img = img.resize((int(img.width * ratio), int(img.height * ratio)), Image.LANCZOS)
                buf = io.BytesIO()
                img.save(buf, format="JPEG", quality=70, optimize=True)
                raw_data = buf.getvalue()
                logger.info("表情包压缩: %s → %dKB", sticker_path.name, len(raw_data) // 1024)
            raw_size = len(raw_data)
            raw_md5 = hashlib.md5(raw_data).hexdigest()

            # AES-128-ECB 加密
            aes_key = secrets.token_bytes(16)
            pad_len = 16 - (raw_size % 16)
            padded = raw_data + bytes([pad_len] * pad_len)
            encryptor = Cipher(algorithms.AES(aes_key), modes.ECB()).encryptor()
            ciphertext = encryptor.update(padded) + encryptor.finalize()

            filekey = f"uu-{secrets.token_hex(8)}"

            # 获取上传地址
            upload_resp = await self._api.get_upload_url(
                filekey=filekey,
                to_user_id=to_user_id,
                file_size=len(ciphertext),
                aes_key=aes_key.hex(),
                raw_size=raw_size,
                raw_md5=raw_md5,
            )
            logger.info("getuploadurl 返回: %s", upload_resp)
            upload_url = upload_resp.get("upload_full_url", "") or upload_resp.get("upload_url", "")
            if not upload_url:
                upload_param = upload_resp.get("upload_param", "")
                if upload_param:
                    from urllib.parse import quote
                    upload_url = f"https://novac2c.cdn.weixin.qq.com/c2c/upload?encrypted_query_param={quote(upload_param)}&filekey={quote(filekey)}"
            if not upload_url:
                logger.warning("获取上传 URL 失败: %s", upload_resp)
                return

            # 上传到 CDN
            download_param = await self._api.upload_cdn(upload_url, ciphertext)
            if not download_param:
                logger.warning("CDN 上传失败，无 download_param")
                return

            # 发送图片消息
            aes_key_b64 = base64.b64encode(aes_key.hex().encode()).decode()
            await self._api.send_image(
                to_user_id=to_user_id,
                context_token=context_token,
                download_param=download_param,
                aes_key_b64=aes_key_b64,
                file_size=len(ciphertext),
            )
            logger.info("  -> 表情包: %s", sticker_path.name)
        except Exception as e:
            logger.warning("发送表情包失败: %s", e)

    async def send_image_file(self, to_user_id: str, context_token: str, file_path: Path):
        """发送本地图片文件到微信（完整的 CDN 上传+发送流程）"""
        from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
        from PIL import Image
        import io

        raw_data = file_path.read_bytes()
        MAX_SIZE = 300 * 1024
        if len(raw_data) > MAX_SIZE:
            img = Image.open(file_path)
            if img.mode in ("RGBA", "P"):
                img = img.convert("RGB")
            if max(img.width, img.height) > 800:
                ratio = 800 / max(img.width, img.height)
                img = img.resize((int(img.width * ratio), int(img.height * ratio)), Image.LANCZOS)
            buf = io.BytesIO()
            img.save(buf, format="JPEG", quality=70, optimize=True)
            raw_data = buf.getvalue()
            logger.info("图片压缩: %s -> %dKB", file_path.name, len(raw_data) // 1024)
        raw_size = len(raw_data)
        raw_md5 = hashlib.md5(raw_data).hexdigest()

        aes_key = secrets.token_bytes(16)
        pad_len = 16 - (raw_size % 16)
        padded = raw_data + bytes([pad_len] * pad_len)
        encryptor = Cipher(algorithms.AES(aes_key), modes.ECB()).encryptor()
        ciphertext = encryptor.update(padded) + encryptor.finalize()

        filekey = f"uu-{secrets.token_hex(8)}"

        upload_resp = await self._api.get_upload_url(
            filekey=filekey,
            to_user_id=to_user_id,
            file_size=len(ciphertext),
            aes_key=aes_key.hex(),
            raw_size=raw_size,
            raw_md5=raw_md5,
        )
        upload_url = upload_resp.get("upload_full_url", "")
        if not upload_url:
            upload_param = upload_resp.get("upload_param", "")
            if upload_param:
                from urllib.parse import quote
                upload_url = f"https://novac2c.cdn.weixin.qq.com/c2c/upload?encrypted_query_param={quote(upload_param)}&filekey={quote(filekey)}"
        if not upload_url:
            raise RuntimeError(f"获取上传 URL 失败: {upload_resp}")

        download_param = await self._api.upload_cdn(upload_url, ciphertext)
        if not download_param:
            raise RuntimeError("CDN 上传失败，无 download_param")

        aes_key_b64 = base64.b64encode(aes_key.hex().encode()).decode()
        await self._api.send_image(
            to_user_id=to_user_id,
            context_token=context_token,
            download_param=download_param,
            aes_key_b64=aes_key_b64,
            file_size=len(ciphertext),
        )
        logger.info("图片已发送到微信: %s", file_path.name)

    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def login_status(self) -> dict:
        """登录状态（二维码信息等）"""
        return {
            "running": self._running,
            "has_credentials": bool(_load_credentials()),
            "qrcode": self._last_qrcode,
        }

    async def start(self) -> dict:
        """
        启动微信通道。

        已有凭证 → 直接启动长轮询，返回 {"started": True}
        无凭证   → 获取二维码并启动后台登录，
                   返回 {"started": False, "qrcode": {...}}
        """
        if self._running:
            return {"started": False, "msg": "已在运行"}

        bot_token, bot_base_url = _ensure_credentials()
        if bot_token:
            # ── 有凭证，直接启动 ──────────────────────────────
            self._api = ILinKAPI(bot_token=bot_token, bot_base_url=bot_base_url)
            self._running = True
            self._task = asyncio.create_task(self._poll_loop())
            self._reminder_task = asyncio.create_task(self._reminder_loop())
            logger.info("微信通道已启动（使用已保存凭证）")
            return {"started": True, "msg": "微信通道已启动"}
        else:
            # ── 无凭证，获取二维码，后台等扫码 ────────────────
            logger.info("无凭证，获取登录二维码...")

            # 获取二维码
            api = ILinKAPI()
            try:
                qr_data = await api.get_bot_qrcode()
                if qr_data.get("ret") != 0:
                    raise Exception(f"获取二维码失败: {qr_data}")
                qrcode_id = qr_data.get("qrcode", "")
                qrcode_url = qr_data.get("qrcode_img_content", "")
                if not qrcode_id:
                    raise Exception(f"未找到 qrcode 字段: {qr_data}")
            finally:
                await api.close()

            self._last_qrcode = {
                "qrcode_id": qrcode_id,
                "qrcode_url": qrcode_url,
            }

            # ── 显示二维码到终端 ────────────────────────────
            print("")
            print("=" * 60)
            print("  请使用微信扫描下方二维码登录 Bot")
            print("=" * 60)
            if qrcode_url:
                # 自动打开浏览器
                webbrowser.open(qrcode_url)
                print(f"  二维码图片: {qrcode_url}")
            # 终端 ASCII 二维码
            qr = qrcode.QRCode(version=3, error_correction=qrcode.constants.ERROR_CORRECT_H, box_size=1, border=1)
            qr.add_data(qrcode_url or qrcode_id)
            qr.make(fit=True)
            qr.print_ascii(invert=True)
            print("=" * 60)
            print("")

            # 启动后台登录任务
            self._login_task = asyncio.create_task(
                self._wait_login_background(qrcode_id)
            )

            logger.info("二维码已获取，等待扫码登录")
            return {
                "started": False,
                "msg": "请在微信中扫描二维码登录",
                "qrcode": {
                    "id": qrcode_id,
                    "url": qrcode_url,
                },
            }

    async def _wait_login_background(self, qrcode_id: str):
        """后台等待扫码确认，登录成功后自动启动长轮询"""
        api = ILinKAPI()
        try:
            while True:
                status_data = await api.get_qrcode_status(qrcode_id)
                status = status_data.get("status")
                logger.info("扫码状态: %s", status)

                if status == "confirmed":
                    bot_token = status_data.get("bot_token")
                    bot_base_url = status_data.get("baseurl")
                    if not bot_token:
                        logger.error("登录成功但未返回 bot_token")
                        return
                    _save_credentials({
                        "bot_token": bot_token,
                        "bot_base_url": bot_base_url,
                        "bot_info": status_data.get("bot_info", {}),
                    })
                    logger.info("微信 Bot 登录成功，凭证已保存")
                    # 启动通道
                    self._api = ILinKAPI(bot_token=bot_token, bot_base_url=bot_base_url)
                    self._running = True
                    self._task = asyncio.create_task(self._poll_loop())
                    self._reminder_task = asyncio.create_task(self._reminder_loop())
                    self._last_qrcode = None
                    logger.info("微信通道已正式启动")
                    return

                elif status in ("expired", "cancelled", "timeout"):
                    logger.warning("扫码状态: %s，请重新 start", status)
                    self._last_qrcode = None
                    return

                await asyncio.sleep(2)
        except asyncio.CancelledError:
            logger.info("登录任务被取消")
        finally:
            await api.close()

    async def stop(self):
        """停止微信通道"""
        self._running = False
        # 取消登录任务
        if self._login_task:
            self._login_task.cancel()
            try:
                await self._login_task
            except asyncio.CancelledError:
                pass
            self._login_task = None
        # 取消长轮询任务
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        # 取消提醒任务
        if self._reminder_task:
            self._reminder_task.cancel()
            try:
                await self._reminder_task
            except asyncio.CancelledError:
                pass
            self._reminder_task = None
        if self._api:
            await self._api.close()
            self._api = None
        self._last_qrcode = None
        logger.info("微信通道已停止")

    async def send_message(self, to_user_id: str, text: str, **kwargs):
        """通过微信发送消息"""
        if not self._api:
            raise RuntimeError("微信通道未启动")
        context_token = kwargs.get("context_token", "")
        await self._api.send_message(to_user_id, context_token, text)

    async def _poll_loop(self):
        """长轮询主循环"""
        logger.info("微信 Bot 长轮询已开始")
        while self._running:
            try:
                data = await self._api.get_updates()
                msgs = data.get("msgs", [])
                for msg in msgs:
                    await self._process_message(msg)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.warning("获取微信消息出错: %s", e)
                await asyncio.sleep(5)

    async def _reminder_loop(self):
        """后台定时检查提醒，到期通过微信推送"""
        import json
        from config.paths import REMINDERS_FILE

        while self._running:
            try:
                if REMINDERS_FILE.exists() and self._api and self._last_user_id:
                    data = json.loads(REMINDERS_FILE.read_text(encoding="utf-8"))
                    now = time.time()
                    due = [r for r in data if r["trigger_time"] <= now]
                    if due:
                        pending = [r for r in data if r["trigger_time"] > now]
                        REMINDERS_FILE.write_text(json.dumps(pending, ensure_ascii=False, indent=2), encoding="utf-8")
                        for r in due:
                            msg = f"⏰ 提醒：{r['message']}"
                            try:
                                await self._api.send_message(
                                    self._last_user_id,
                                    self._last_context_token,
                                    msg,
                                )
                                logger.info("提醒已发送: %s", r['message'])
                            except Exception as e:
                                logger.warning("发送提醒失败: %s", e)
            except Exception as e:
                logger.warning("提醒检查出错: %s", e)
            await asyncio.sleep(5)

    async def _process_message(self, msg: dict):
        """处理单条消息"""
        try:
            if msg.get("message_type") != MsgDirection.USER:
                return

            from_user_id = msg.get("from_user_id", "unknown")
            context_token = msg.get("context_token", "")

            # 记下最新的用户信息（用于定时提醒推送）
            self._last_user_id = from_user_id
            self._last_context_token = context_token

            # 处理消息内容（支持文本+图片+文件+视频）
            text = ""
            media_desc = ""
            media_dir = STICKERS_DIR.parent / "received"
            media_dir.mkdir(parents=True, exist_ok=True)

            for item in msg.get("item_list", []):
                t = item.get("type", 0)

                if t == MessageItemType.TEXT:
                    text = item.get("text_item", {}).get("text", "")

                elif t == MessageItemType.IMAGE:
                    try:
                        img = item.get("image_item", {})
                        ref = img.get("media", {})
                        param = ref.get("encrypt_query_param", "")
                        if not param:
                            continue

                        # 解析 AES 密钥（兼容多种编码）
                        from base64 import b64decode, b64encode
                        # 1) 优先取 image_item.aeskey（32位hex字符串）
                        raw_hex = img.get("aeskey", "")
                        if raw_hex:
                            aes_key_b64 = b64encode(bytes.fromhex(raw_hex)).decode()
                        else:
                            aes_key_b64 = ref.get("aes_key", "")

                        if not aes_key_b64:
                            continue

                        # 2) base64解码，兼容两种编码：
                        #    - base64(原始16字节) → 16字节
                        #    - base64(hex字符串)  → 32字节hex字符串
                        decoded = b64decode(aes_key_b64)
                        if len(decoded) == 16:
                            aes_key_hex = decoded.hex()
                        elif len(decoded) == 32:
                            aes_key_hex = decoded.decode("ascii")
                        else:
                            continue

                        data = await self._api.download_cdn(param)
                        plain = self._api.decrypt_media(data, aes_key_hex)
                        fname = f"img_{int(time.time())}_{secrets.token_hex(4)}.jpg"
                        fpath = media_dir / fname
                        fpath.write_bytes(plain)
                        media_desc += f"\n[图片已保存: {fpath.name}]"
                        logger.info("收到图片 → %s (%dKB)", fpath, len(plain) // 1024)
                    except Exception as e:
                        logger.warning("接收图片失败: %s", e)
                        media_desc += "\n[图片（接收失败）]"

                elif t == MessageItemType.VOICE:
                    try:
                        voice = item.get("voice_item", {})
                        voice_text = voice.get("text", "")
                        if voice_text:
                            text += f"\n[语音消息: {voice_text}]"
                            logger.info("收到语音（已转文字）: %s", voice_text)
                        else:
                            # 无转文字，下载语音文件
                            ref = voice.get("media", {})
                            param = ref.get("encrypt_query_param", "")
                            if param:
                                from base64 import b64decode
                                aes_key_b64 = ref.get("aes_key", "")
                                if aes_key_b64:
                                    decoded = b64decode(aes_key_b64)
                                    aes_key_hex = decoded.hex() if len(decoded) == 16 else decoded.decode()
                                    data = await self._api.download_cdn(param)
                                    plain = self._api.decrypt_media(data, aes_key_hex)
                                    fname = f"voice_{int(time.time())}_{secrets.token_hex(4)}.silk"
                                    fpath = media_dir / fname
                                    fpath.write_bytes(plain)
                                    media_desc += f"\n[语音已保存: {fname}]"
                                    logger.info("收到语音 → %s", fpath)
                            else:
                                text += "\n[语音消息（无转文字）]"
                    except Exception as e:
                        logger.warning("接收语音失败: %s", e)
                        media_desc += "\n[语音（接收失败）]"

                elif t == 4:
                    try:
                        fi = item.get("file_item", {})
                        ref = fi.get("media", {})
                        param = ref.get("encrypt_query_param", "")
                        aes_key_b64 = ref.get("aes_key", "")
                        fname = fi.get("file_name", f"file_{secrets.token_hex(4)}")
                        if param and aes_key_b64:
                            from base64 import b64decode
                            aes_key_hex = b64decode(aes_key_b64).decode()
                            data = await self._api.download_cdn(param)
                            plain = self._api.decrypt_media(data, aes_key_hex)
                            fpath = media_dir / fname
                            fpath.write_bytes(plain)
                            media_desc += f"\n[文件已保存: {fname} ({len(plain)//1024}KB)]"
                            logger.info("收到文件 → %s", fpath)
                    except Exception as e:
                        logger.warning("接收文件失败: %s", e)
                        media_desc += "\n[文件（接收失败）]"

            # 组合消息内容
            full_text = text + media_desc
            if not full_text.strip():
                return

            logger.info("[微信 %s] %s", from_user_id, full_text)

            # 显示"对方正在输入..."
            typing_ticket = ""
            try:
                cfg = await self._api.get_config(from_user_id, context_token)
                typing_ticket = cfg.get("typing_ticket", "")
                if typing_ticket:
                    await self._api.send_typing(from_user_id, typing_ticket, status=1)
            except Exception as e:
                logger.debug("typing 指示器失败: %s", e)

            # 路由到 Agent（能调工具，口语化回复）
            reply = await route_to_agent(
                session_id="default",
                message=f"[微信] {full_text}",
                user_id=from_user_id,
                system_prompt=WECHAT_SYSTEM_PROMPT,
            )

            # 取消"正在输入..."
            if typing_ticket:
                try:
                    await self._api.send_typing(from_user_id, typing_ticket, status=2)
                except Exception:
                    pass

            # 回复（长文本拆成多条发送）
            if context_token and self._api:
                for chunk in self._split_text(reply, max_len=600):
                    await self._api.send_message(from_user_id, context_token, chunk)
                    logger.info("  -> 回复: %.50s", chunk)

            # 以 1/4 概率发一张表情包
            if context_token and self._api:
                await self._send_sticker(from_user_id, context_token, reply)

        except Exception as e:
            logger.exception("处理微信消息出错: %s", e)
