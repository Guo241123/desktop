from pathlib import Path


_STYLE_CACHE: str | None = None


def style() -> str:
    """
    返回完整的PPT HTML模板CSS（从 assets/ppt_style.css 读取）
    """
    global _STYLE_CACHE
    if _STYLE_CACHE is None:
        path = Path(__file__).resolve().parent.parent / "assets" / "ppt_style.css"
        _STYLE_CACHE = path.read_text(encoding="utf-8")
    return _STYLE_CACHE
