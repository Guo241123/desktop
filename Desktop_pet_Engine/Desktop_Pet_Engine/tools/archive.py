"""压缩/解压缩工具 — Agent 可调用 compress / decompress"""

import os
import zipfile
from pathlib import Path
from langchain_core.tools import tool


@tool
def compress(folder_path: str, output_path: str = "") -> str:
    """
    将整个文件夹压缩成 ZIP 文件。
    :param folder_path: 要压缩的文件夹路径
    :param output_path: 输出的 ZIP 文件路径（可选，不传则生成在桌面）
    """
    folder = Path(folder_path)
    if not folder.exists() or not folder.is_dir():
        return f"文件夹不存在: {folder_path}"

    if not output_path:
        desktop = Path.home() / "Desktop"
        output_path = str(desktop / f"{folder.name}.zip")

    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)

    try:
        count = 0
        with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zf:
            for file in folder.rglob("*"):
                if file.is_file():
                    arcname = file.relative_to(folder)
                    zf.write(file, arcname)
                    count += 1

        size_mb = out.stat().st_size / (1024 * 1024)
        return f"压缩完成：{folder.name}.zip（{count} 个文件，{size_mb:.1f}MB）→ {out}"
    except Exception as e:
        return f"压缩失败: {e}"


@tool
def decompress(zip_path: str, output_dir: str = "") -> str:
    """
    解压 ZIP 文件到指定目录。
    :param zip_path: ZIP 文件路径
    :param output_dir: 解压到的目录（可选，不传则解压到桌面）
    """
    zpath = Path(zip_path)
    if not zpath.exists():
        return f"文件不存在: {zip_path}"

    if not zipfile.is_zipfile(zpath):
        return f"不是有效的 ZIP 文件: {zip_path}"

    if not output_dir:
        desktop = Path.home() / "Desktop"
        output_dir = str(desktop / zpath.stem)

    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    try:
        with zipfile.ZipFile(zpath, "r") as zf:
            zf.extractall(out)
        count = len(list(out.rglob("*")))
        return f"解压完成：共 {count} 个文件/文件夹 → {out}"
    except Exception as e:
        return f"解压失败: {e}"
