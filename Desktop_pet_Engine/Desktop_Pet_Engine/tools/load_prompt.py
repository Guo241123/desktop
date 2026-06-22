from pathlib import Path
from langchain_core.tools import tool


_PROMPT_CACHE: str | None = None


def _load_prompt() -> str:
    global _PROMPT_CACHE
    if _PROMPT_CACHE is None:
        path = Path(__file__).resolve().parent.parent / "assets" / "ppt_prompt.txt"
        _PROMPT_CACHE = path.read_text(encoding="utf-8")
    return _PROMPT_CACHE


@tool
def ppt_prompt() -> str:
    """
    网页ppt生成标准化提示词，用于指导AI生成12页及以上全屏网页PPT，采用文字疏密交替排版，多文字页面多于少文字页面，搭配 anime.js代码动画与全维度交互效果，版式全部不重复、视觉层次高级舒适。
    :return: 完整规范提示词文本
    """
    return _load_prompt()
