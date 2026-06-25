"""tools/voice.py — 语音工具集：麦克风录音、语音转文字（ASR）、文字转语音（TTS）

所有工具自动被 tools/__init__.py 发现并注册到 Agent。
共享模块级录音状态（_recording 等变量），支持跨多次工具调用录一段音频。

Mimo API 格式（通过 /v1/chat/completions 调用）：
  - TTS: model=mimo-v2.5-tts,  assistant content=要朗读的文字 → message.audio.data(base64)
  - ASR: model=mimo-v2.5-asr,  user content=[{type:input_audio, input_audio:{data:...}}] → message.content
"""

import base64
import io
import json
import logging
import threading
import time
from pathlib import Path

import httpx
import numpy as np
import sounddevice as sd
import wave

from config.settings import get_env, DATA_DIR
from langchain.tools import tool

logger = logging.getLogger(__name__)

# ── 常量 ────────────────────────────────────────────────────────────
SAMPLE_RATE = 16000         # ASR 常用采样率
AUDIO_DIR = DATA_DIR / "voice"
AUDIO_DIR.mkdir(parents=True, exist_ok=True)

# ── 模块级录音状态（跨多次工具调用保持） ────────────────────────
_recording = False
_recorded_frames: list[np.ndarray] = []
_recording_thread: threading.Thread | None = None
_current_output_path: str = ""
_mic_device: int | None = None  # None = 默认输入设备


# ═══════════════════════════════════════════════════════════════════
# 内部帮助函数
# ═══════════════════════════════════════════════════════════════════

def _record_loop():
    """后台录音循环 — 每次采集 ~1 秒的音频块"""
    try:
        with sd.InputStream(
            samplerate=SAMPLE_RATE,
            channels=1,
            dtype="float32",
            device=_mic_device,
        ) as stream:
            while _recording:
                chunk, _ = stream.read(SAMPLE_RATE)
                _recorded_frames.append(chunk.copy())
    except Exception as e:
        logger.exception("录音循环异常退出: %s", e)


def _save_recording() -> str:
    """将 _recorded_frames 拼接并保存为 16-bit WAV 文件"""
    global _recorded_frames, _current_output_path
    if not _recorded_frames:
        return "没有录制到任何音频数据"

    audio_data = np.concatenate(_recorded_frames, axis=0)
    # float32 [-1,1] → int16
    audio_int16 = (audio_data * 32767).clip(-32768, 32767).astype(np.int16)

    if not _current_output_path:
        ts = time.strftime("%Y%m%d_%H%M%S")
        _current_output_path = str(AUDIO_DIR / f"recording_{ts}.wav")

    with wave.open(_current_output_path, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)  # int16 = 2 bytes
        wf.setframerate(SAMPLE_RATE)
        wf.writeframes(audio_int16.tobytes())

    duration = len(audio_data) / SAMPLE_RATE
    filepath = _current_output_path
    _recorded_frames = []
    _current_output_path = ""
    return f"录音已保存: {filepath}（{duration:.1f} 秒，{len(audio_int16) // 1024}KB）"


def _build_mimo_headers() -> dict:
    """构造 Mimo API 请求头（JSON 格式）"""
    return {
        "Authorization": f"Bearer {get_env('MIMO_API_KEY')}",
        "Content-Type": "application/json",
    }


def _mimo_api_key_ok() -> bool:
    return bool(get_env("MIMO_API_KEY"))


def _get_latest_recording() -> Path | None:
    """返回 data/voice/ 下最新的 recording_*.wav 文件"""
    wav_files = sorted(
        AUDIO_DIR.glob("recording_*.wav"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    return wav_files[0] if wav_files else None


# ═══════════════════════════════════════════════════════════════════
# Tool 1 — 开/关麦克风
# ═══════════════════════════════════════════════════════════════════

@tool
def toggle_microphone(action: str) -> str:
    """
    打开或关闭电脑麦克风进行录音。
    当用户说「打开麦克风」「开始录音」「听一下」时传 action='on' 开始录制；
    当用户说「关闭麦克风」「停」「结束录音」时传 action='off' 停止并保存。
    录音文件保存在 data/voice/ 目录下，16kHz 单声道 WAV 格式，适合后续语音识别。
    :param action: "on" 打开麦克风开始录音, "off" 关闭麦克风停止录音并保存文件
    :return: 操作结果描述。关闭时返回音频文件路径和时长
    """
    global _recording, _recorded_frames, _recording_thread, _current_output_path

    action = action.strip().lower()

    if action == "on":
        if _recording:
            return "麦克风已经在录音中了，可以对它说话。想停止就说「关闭麦克风」"
        _recording = True
        _recorded_frames = []
        ts = time.strftime("%Y%m%d_%H%M%S")
        _current_output_path = str(AUDIO_DIR / f"recording_{ts}.wav")
        _recording_thread = threading.Thread(target=_record_loop, daemon=True)
        _recording_thread.start()
        return "🎤 麦克风已开启，正在录音... 请说话，说完告诉我「关闭麦克风」"

    if action == "off":
        if not _recording:
            return "麦克风当前没有在录音"
        _recording = False
        if _recording_thread:
            _recording_thread.join(timeout=3)
        return _save_recording()

    return f"未知操作: {action}，请使用 'on' 打开或 'off' 关闭"


# ═══════════════════════════════════════════════════════════════════
# Tool 2 — 语音转文字（ASR / STT）
# ═══════════════════════════════════════════════════════════════════

@tool
def speech_to_text(audio_path: str = "") -> str:
    """
    将语音音频文件转换为文字（语音识别 / ASR）。
    调用 Mimo ASR 服务（mimo-v2.5-asr 模型）将语音转为文字，支持中文。
    如果不传 audio_path，自动使用最近一次通过 toggle_microphone 录制的音频文件。
    :param audio_path: 音频文件路径（可选，默认使用最近的麦克风录音）
    :return: 识别出的文字内容
    """
    # ── 1. 确定音频文件路径 ──────────────────────────────────
    path_str = audio_path.strip() if audio_path else ""

    if not path_str:
        latest = _get_latest_recording()
        if not latest:
            return "没有找到录音文件，请先使用 toggle_microphone('on') 录制一段语音"
        path_str = str(latest)

    audio_file = Path(path_str)
    if not audio_file.exists():
        return f"音频文件不存在: {audio_path}"

    # ── 2. 基本检查 ──────────────────────────────────────────
    file_size = audio_file.stat().st_size
    if file_size > 25 * 1024 * 1024:
        return f"音频文件过大（{file_size // 1024 // 1024}MB），Mimo ASR 限制 25MB"
    if file_size < 100:
        return "音频文件过短（不足 100 字节），请录制更长一些"

    if not _mimo_api_key_ok():
        return "MIMO_API_KEY 未配置，请在设置中填写 Mimo API Key"

    # ── 3. 读取音频并编码为 base64 ────────────────────────────
    try:
        audio_b64 = base64.b64encode(audio_file.read_bytes()).decode()
    except Exception as e:
        return f"读取音频文件失败: {e}"

    # ── 4. 调用 Mimo ASR（通过 chat/completions） ─────────────
    base_url = get_env("MIMO_BASE_URL", "https://api.xiaomimimo.com/v1").rstrip("/")
    model = get_env("MODEL_ASR", "mimo-v2.5-asr")

    try:
        with httpx.Client(timeout=120) as client:
            resp = client.post(
                f"{base_url}/chat/completions",
                headers=_build_mimo_headers(),
                json={
                    "model": model,
                    "messages": [
                        {
                            "role": "user",
                            "content": [
                                {
                                    "type": "input_audio",
                                    "input_audio": {
                                        "data": f"data:audio/wav;base64,{audio_b64}",
                                    },
                                },
                            ],
                        },
                    ],
                    "max_tokens": 1000,
                },
            )

        if resp.status_code == 401:
            return "Mimo API Key 无效或已过期，请在设置中更新"
        if resp.status_code != 200:
            return f"Mimo ASR 请求失败（{resp.status_code}）: {resp.text[:300]}"

        result = resp.json()
        text = (result.get("choices") or [{}])[0].get("message", {}).get("content", "").strip()
        if not text:
            return "未能识别出文字，请尝试重新录制（说话清晰一些）"
        return f"识别结果: {text}"

    except httpx.TimeoutException:
        return "Mimo ASR 请求超时，请检查网络或稍后重试"
    except Exception as e:
        logger.exception("ASR 请求异常")
        return f"语音识别失败: {e}"


# ═══════════════════════════════════════════════════════════════════
# Tool 3 — 文字转语音（TTS）
# ═══════════════════════════════════════════════════════════════════

@tool
def text_to_speech(text: str, voice: str = "") -> str:
    """
    将文字转换为语音并播放（文字转语音 / TTS）。
    调用 Mimo TTS 服务（mimo-v2.5-tts 模型）合成语音，
    保存为 WAV 文件并通过电脑扬声器播放。
    默认使用配置的音色（TTS_VOICE），也可以临时指定音色。
    可用音色：nova（元气女声）、shimmer（清亮女声）、female（标准女声）、
    alloy（柔和自然）、male（低沉男声）、echo（浑厚男声）、onyx（叙事男声）。
    :param text: 要转为语音的文字内容
    :param voice: 音色名称（可选），如 "nova"、"shimmer"、"male" 等，不传则用默认音色
    :return: 生成的语音文件路径和播放状态
    """
    text = text.strip()
    if not text:
        return "请输入要转换为语音的文字"

    if len(text) > 2000:
        return "文字过长（超过 2000 字），请分段处理"

    if not _mimo_api_key_ok():
        return "MIMO_API_KEY 未配置，请在设置中填写"

    base_url = get_env("MIMO_BASE_URL", "https://api.xiaomimimo.com/v1").rstrip("/")
    model = get_env("MODEL_TTS", "mimo-v2.5-tts")
    default_voice = get_env("TTS_VOICE", "nova")
    selected_voice = voice.strip() or default_voice

    # ── 1. 调用 Mimo TTS（通过 chat/completions） ─────────────
    try:
        with httpx.Client(timeout=120) as client:
            resp = client.post(
                f"{base_url}/chat/completions",
                headers=_build_mimo_headers(),
                json={
                    "model": model,
                    "messages": [
                        {"role": "user", "content": f"用{selected_voice}音色朗读"},
                        {"role": "assistant", "content": text},
                    ],
                },
            )

        if resp.status_code == 401:
            return "Mimo API Key 无效或已过期，请在设置中更新"
        if resp.status_code != 200:
            return f"Mimo TTS 请求失败（{resp.status_code}）: {resp.text[:300]}"

        result = resp.json()
        audio_b64 = (
            (result.get("choices") or [{}])[0]
            .get("message", {})
            .get("audio", {})
            .get("data", "")
        )
        if not audio_b64:
            return "TTS 返回数据中没有找到音频"

        wav_bytes = base64.b64decode(audio_b64)

        # ── 2. 保存音频文件 ──────────────────────────────────
        ts = time.strftime("%Y%m%d_%H%M%S")
        output_path = AUDIO_DIR / f"tts_{ts}.wav"
        output_path.write_bytes(wav_bytes)

        file_size_kb = len(wav_bytes) // 1024
        logger.info("TTS 音频已保存: %s (%dKB)", output_path, file_size_kb)

        # ── 3. 播放声音 ──────────────────────────────────────
        try:
            with wave.open(io.BytesIO(wav_bytes), "rb") as wf:
                frames = wf.getnframes()
                audio_data = (
                    np.frombuffer(wf.readframes(frames), dtype=np.int16).astype(np.float32)
                    / 32767.0
                )
                sr = wf.getframerate()

            sd.play(audio_data, sr)
            sd.wait()

            duration = frames / sr if sr > 0 else 0
            return f"已生成并播放语音: {output_path.name}（{file_size_kb}KB，{duration:.1f}秒）"
        except Exception as play_err:
            logger.warning("TTS 播放失败（文件已保存）: %s", play_err)
            return f"语音文件已生成: {output_path.name}（{file_size_kb}KB，播放失败: {play_err}）"

    except httpx.TimeoutException:
        return "Mimo TTS 请求超时，文字较长时请耐心等待"
    except Exception as e:
        logger.exception("TTS 请求异常")
        return f"文字转语音失败: {e}"
