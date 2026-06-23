"""MI 通道 — 微信（iLink Bot API）

依赖 wechat_api（API 客户端）和 media_uploader（CDN 上传）两个子模块。
"""

import asyncio
import json
import logging
import random
import time
import webbrowser
from pathlib import Path
from typing import Optional

import qrcode

from mi.base import BaseChannel
from mi.router import route_to_agent
from mi.channels.wechat_api import (
    ILinKAPI, MsgDirection, MessageItemType,
    load_credentials, save_credentials,
)
from mi.media_uploader import (
    compress_image, aes_encrypt, make_filekey,
    build_upload_url, aes_key_to_b64,
)
from agent.prompts import WECHAT_SYSTEM_PROMPT
from config.paths import WECHAT_CREDENTIALS_DIR, WECHAT_CREDENTIALS_FILE, STICKERS_DIR, REMINDERS_FILE

logger = logging.getLogger(__name__)

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
        self._last_user_id: str = ""
        self._last_context_token: str = ""
        self._reminder_task: Optional[asyncio.Task] = None

    # ── 文本处理 ──────────────────────────────────────────────

    @staticmethod
    def _split_text(text: str, max_len: int = 600) -> list[str]:
        import re
        sentences = re.split(r"(?<=[~～。！？!?])", text)
        chunks = [s.strip() for s in sentences if s.strip()]
        return chunks if chunks else [text]

    # ── 表情包 ──────────────────────────────────────────────────

    @staticmethod
    def _pick_sticker(text: str) -> Optional[Path]:
        stickers = sorted(STICKERS_DIR.glob("*.*"))
        if not stickers:
            return None
        scores = []
        for s in stickers:
            name = s.stem
            score = sum(1 for ch in name if ch in text)
            score += random.random() * 0.5
            scores.append((score, s))
        scores.sort(key=lambda x: -x[0])
        return scores[0][1]

    async def _send_sticker(self, to_user_id: str, context_token: str, reply_text: str):
        """以 1/4 概率上传并发送一张表情包"""
        if random.random() > 0.25:
            return
        sticker_path = self._pick_sticker(reply_text)
        if not sticker_path:
            return
        try:
            raw_data = sticker_path.read_bytes()
            compressed = compress_image(raw_data)
            if compressed is not raw_data:
                logger.info("表情包压缩: %s → %dKB", sticker_path.name, len(compressed) // 1024)

            ciphertext, aes_key, raw_md5 = aes_encrypt(compressed)
            filekey = make_filekey()
            upload_resp = await self._api.get_upload_url(
                filekey=filekey, to_user_id=to_user_id,
                file_size=len(ciphertext), aes_key=aes_key.hex(),
                raw_size=len(compressed), raw_md5=raw_md5,
            )
            upload_url = build_upload_url(upload_resp, filekey)
            if not upload_url:
                logger.warning("获取上传 URL 失败: %s", upload_resp)
                return

            download_param = await self._api.upload_cdn(upload_url, ciphertext)
            if not download_param:
                logger.warning("CDN 上传失败，无 download_param")
                return

            aes_key_b64 = aes_key_to_b64(aes_key)
            await self._api.send_image(
                to_user_id=to_user_id, context_token=context_token,
                download_param=download_param, aes_key_b64=aes_key_b64,
                file_size=len(ciphertext),
            )
            logger.info("  -> 表情包: %s", sticker_path.name)
        except Exception as e:
            logger.warning("发送表情包失败: %s", e)

    async def send_image_file(self, to_user_id: str, context_token: str, file_path: Path):
        """发送本地图片文件到微信"""
        raw_data = file_path.read_bytes()
        compressed = compress_image(raw_data)
        if compressed is not raw_data:
            logger.info("图片压缩: %s -> %dKB", file_path.name, len(compressed) // 1024)

        ciphertext, aes_key, raw_md5 = aes_encrypt(compressed)
        filekey = make_filekey()
        upload_resp = await self._api.get_upload_url(
            filekey=filekey, to_user_id=to_user_id,
            file_size=len(ciphertext), aes_key=aes_key.hex(),
            raw_size=len(compressed), raw_md5=raw_md5,
        )
        upload_url = build_upload_url(upload_resp, filekey)
        if not upload_url:
            raise RuntimeError(f"获取上传 URL 失败: {upload_resp}")

        download_param = await self._api.upload_cdn(upload_url, ciphertext)
        if not download_param:
            raise RuntimeError("CDN 上传失败，无 download_param")

        aes_key_b64 = aes_key_to_b64(aes_key)
        await self._api.send_image(
            to_user_id=to_user_id, context_token=context_token,
            download_param=download_param, aes_key_b64=aes_key_b64,
            file_size=len(ciphertext),
        )
        logger.info("图片已发送到微信: %s", file_path.name)

    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def login_status(self) -> dict:
        return {
            "running": self._running,
            "has_credentials": bool(load_credentials()),
            "qrcode": self._last_qrcode,
        }

    def get_send_context(self) -> Optional[dict]:
        """获取发送微信消息所需的上下文（公开接口，避免外部直接访问私有属性）"""
        if not self._api or not self._running:
            return None
        if not self._last_user_id:
            return None
        return {
            "bot_token": self._api.bot_token,
            "bot_base_url": self._api.base_url,
            "to_user_id": self._last_user_id,
            "context_token": self._last_context_token,
        }

    async def start(self) -> dict:
        if self._running:
            return {"started": False, "msg": "已在运行"}

        bot_token, bot_base_url = self._ensure_credentials()
        if bot_token:
            self._api = ILinKAPI(bot_token=bot_token, bot_base_url=bot_base_url)
            self._running = True
            # 恢复上次的发送上下文
            if creds := load_credentials():
                self._last_user_id = creds.get("last_user_id", "")
                self._last_context_token = creds.get("last_context_token", "")
            self._task = asyncio.create_task(self._poll_loop())
            self._reminder_task = asyncio.create_task(self._reminder_loop())
            logger.info("微信通道已启动（使用已保存凭证）")
            return {"started": True, "msg": "微信通道已启动"}
        else:
            logger.info("无凭证，获取登录二维码...")
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

            self._last_qrcode = {"qrcode_id": qrcode_id, "qrcode_url": qrcode_url}

            print("")
            print("=" * 60)
            print("  请使用微信扫描下方二维码登录 Bot")
            print("=" * 60)
            if qrcode_url:
                webbrowser.open(qrcode_url)
                print(f"  二维码图片: {qrcode_url}")
            qr = qrcode.QRCode(version=3, error_correction=qrcode.constants.ERROR_CORRECT_H, box_size=1, border=1)
            qr.add_data(qrcode_url or qrcode_id)
            qr.make(fit=True)
            qr.print_ascii(invert=True)
            print("=" * 60)
            print("")

            self._login_task = asyncio.create_task(self._wait_login_background(qrcode_id))
            logger.info("二维码已获取，等待扫码登录")
            return {
                "started": False, "msg": "请在微信中扫描二维码登录",
                "qrcode": {"id": qrcode_id, "url": qrcode_url},
            }

    @staticmethod
    def _ensure_credentials() -> tuple[str, Optional[str]]:
        creds = load_credentials()
        if creds and creds.get("bot_token"):
            logger.info("使用已保存的微信 Bot 登录凭证")
            return creds["bot_token"], creds.get("bot_base_url")
        return "", None

    async def _wait_login_background(self, qrcode_id: str):
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
                    save_credentials({
                        "bot_token": bot_token, "bot_base_url": bot_base_url,
                        "bot_info": status_data.get("bot_info", {}),
                    })
                    logger.info("微信 Bot 登录成功，凭证已保存")
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
        self._running = False
        for task_name in ("_login_task", "_task", "_reminder_task"):
            task = getattr(self, task_name, None)
            if task:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
                setattr(self, task_name, None)
        if self._api:
            await self._api.close()
            self._api = None
        self._last_qrcode = None
        logger.info("微信通道已停止")

    async def send_message(self, to_user_id: str, text: str, **kwargs):
        if not self._api:
            raise RuntimeError("微信通道未启动")
        context_token = kwargs.get("context_token", "")
        await self._api.send_message(to_user_id, context_token, text)

    async def _poll_loop(self):
        logger.info("微信 Bot 长轮询已开始")
        while self._running:
            try:
                data = await self._api.get_updates()
                for msg in data.get("msgs", []):
                    await self._process_message(msg)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.warning("获取微信消息出错: %s", e)
                await asyncio.sleep(5)

    async def _reminder_loop(self):
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
                                await self._api.send_message(self._last_user_id, self._last_context_token, msg)
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

            self._last_user_id = from_user_id
            self._last_context_token = context_token

            # 保存到凭证文件，重启后可恢复
            save_credentials({
                "bot_token": self._api.bot_token,
                "bot_base_url": self._api.base_url,
                "last_user_id": from_user_id,
                "last_context_token": context_token,
            })

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

                        from base64 import b64decode, b64encode
                        raw_hex = img.get("aeskey", "")
                        if raw_hex:
                            aes_key_b64 = b64encode(bytes.fromhex(raw_hex)).decode()
                        else:
                            aes_key_b64 = ref.get("aes_key", "")
                        if not aes_key_b64:
                            continue

                        decoded = b64decode(aes_key_b64)
                        aes_key_hex = decoded.hex() if len(decoded) == 16 else decoded.decode("ascii") if len(decoded) == 32 else ""

                        if not aes_key_hex:
                            continue

                        import secrets
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
                            ref = voice.get("media", {})
                            param = ref.get("encrypt_query_param", "")
                            if param:
                                from base64 import b64decode
                                import secrets
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

            reply = await route_to_agent(
                session_id="default",
                message=f"[微信] {full_text}",
                user_id=from_user_id,
                system_prompt=WECHAT_SYSTEM_PROMPT,
            )

            if typing_ticket:
                try:
                    await self._api.send_typing(from_user_id, typing_ticket, status=2)
                except Exception:
                    pass

            if context_token and self._api:
                for chunk in self._split_text(reply, max_len=600):
                    await self._api.send_message(from_user_id, context_token, chunk)
                    logger.info("  -> 回复: %.50s", chunk)

            if context_token and self._api:
                await self._send_sticker(from_user_id, context_token, reply)

        except Exception as e:
            logger.exception("处理微信消息出错: %s", e)
