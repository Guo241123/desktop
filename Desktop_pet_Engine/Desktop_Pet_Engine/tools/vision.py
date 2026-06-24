"""视觉工具 — 调用 Qwen3-VL-Flash 识别图片内容

临时方案，等 DeepSeek 4.1 支持视觉后删掉这个文件即可。
用阿里云 DashScope 的 OpenAI 兼容接口。
"""

import base64
import logging

from langchain.tools import tool

from config.paths import STICKERS_DIR

logger = logging.getLogger(__name__)

# ── 配置 ─────────────────────────────────────────────────
# 从阿里云 DashScope（百炼）获取：https://help.aliyun.com/zh/model-studio/
DASHSCOPE_API_KEY = "sk-ws-H.RYDMIDL.mBpe.MEQCIEV0bs7iFUlKSjhB8EN_yz6RXhxhWwhv7_ZzFH6BADbwAiBLgdK4f0E79GLAj3N9E9bdNdNNImtp_XOr67aKyMbFTw"  # ← 把你的 DashScope API Key 填在这里

VISION_MODEL = "qwen-vl-plus"  # 或 qwen-vl-max、qwen2.5-vl-72b-instruct
VISION_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"

# 微信收到的图片存这里
RECEIVED_DIR = STICKERS_DIR.parent / "received"


@tool
def describe_image(filename: str) -> str:
    """
    识别一张图片的内容并返回文字描述。
    当你收到用户发来的图片（消息中带有 [图片已保存: xxx.jpg]）时，调用此工具查看图片内容。
    传入图片文件名即可，例如 describe_image("img_1712345678_abcd.jpg")。
    """
    if not DASHSCOPE_API_KEY:
        return "⚠️ 视觉工具未配置 API Key，请先在 tools/vision.py 中填写 DASHSCOPE_API_KEY"

    # 查找图片文件
    img_path = RECEIVED_DIR / filename
    if not img_path.exists():
        # 尝试在沙盒目录查找
        from config.paths import SANDBOX_DIR
        alt_path = SANDBOX_DIR / filename
        if alt_path.exists():
            img_path = alt_path
        else:
            return f"⚠️ 找不到图片文件: {filename}"

    try:
        # 读取 + base64 编码
        raw = img_path.read_bytes()
        b64 = base64.b64encode(raw).decode("utf-8")
        mime = _guess_mime(img_path.suffix)

        # 调用 DashScope（OpenAI 兼容格式）
        import httpx

        payload = {
            "model": VISION_MODEL,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{b64}"}},
                        {"type": "text", "text": "请详细描述这张图片的内容，包括：画面中的物体、人物、文字、场景、颜色、布局等。"},
                    ],
                }
            ],
            "max_tokens": 512,
        }
        headers = {
            "Authorization": f"Bearer {DASHSCOPE_API_KEY}",
            "Content-Type": "application/json",
        }

        resp = httpx.post(
            f"{VISION_BASE_URL}/chat/completions",
            json=payload,
            headers=headers,
            timeout=30,
        )
        data = resp.json()

        if resp.status_code != 200:
            error_msg = data.get("error", {}).get("message", str(data))
            return f"⚠️ 视觉识别失败: {error_msg}"

        description = data["choices"][0]["message"]["content"]
        logger.info("图片描述 (%s): %.60s", filename, description)
        return description

    except Exception as e:
        logger.exception("视觉识别异常")
        return f"⚠️ 视觉识别出错: {e}"


def _guess_mime(suffix: str) -> str:
    mime_map = {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".gif": "image/gif",
        ".webp": "image/webp",
        ".bmp": "image/bmp",
    }
    return mime_map.get(suffix.lower(), "image/jpeg")
