#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PPT 截图转 PDF 工具（Agent 可扫描）

默认配置：16:9 比例，1K 分辨率（1920x1080）

依赖：
    pip install playwright Pillow
    playwright install chromium

命令行：
    python ppt_to_pdf_tool.py "D:\furina_ppt"
    python ppt_to_pdf_tool.py "D:\furina_ppt" "D:\output\pangu.pdf"
"""

import sys
import os
import time
import socket
import atexit
import threading
import http.server
import socketserver
from pathlib import Path
from typing import Optional, Dict, Any
from functools import wraps

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    raise ImportError("pip install playwright && playwright install chromium")

try:
    from PIL import Image
except ImportError:
    raise ImportError("pip install Pillow")


def tool(func):
    """工具装饰器，Agent 扫描 @tool 发现可用工具"""
    @wraps(func)
    def wrapper(*args, **kwargs):
        return func(*args, **kwargs)
    wrapper._is_tool = True
    wrapper._tool_name = func.__name__
    return wrapper


# ==================== 内部辅助函数 ====================

def _get_desktop() -> str:
    home = Path.home()
    for name in ["Desktop", "桌面", "Escritorio", "Bureau"]:
        desktop = home / name
        if desktop.exists():
            return str(desktop)
    return str(home)


def _find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _start_http_server(project_dir: str, port: int):
    original_dir = os.getcwd()

    class QuietHandler(http.server.SimpleHTTPRequestHandler):
        def log_message(self, format, *args):
            pass

    os.chdir(project_dir)
    httpd = socketserver.TCPServer(("127.0.0.1", port), QuietHandler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    time.sleep(0.5)

    def shutdown():
        httpd.shutdown()
        httpd.server_close()
        os.chdir(original_dir)

    atexit.register(shutdown)
    return shutdown


def _ensure_ratio(img, ratio: float):
    w, h = img.size
    current = w / h
    if abs(current - ratio) < 0.001:
        return img
    if current > ratio:
        new_w = int(h * ratio)
        left = (w - new_w) // 2
        return img.crop((left, 0, left + new_w, h))
    else:
        new_h = int(w / ratio)
        top = (h - new_h) // 2
        return img.crop((0, top, w, top + new_h))


# ==================== @tool 主函数 ====================

@tool
def ppt_to_pdf(
    project_dir: str,
    output_pdf: Optional[str] = None,
    aspect_ratio: float = 16 / 9,
    width: int = 1920,
    dpi: int = 150,
    wait_animation: int = 1500,
    wait_load: int = 3000
) -> Dict[str, Any]:
    """
    将 PPT 项目（HTML 幻灯片）截图并转为 PDF。

    参数：
        project_dir: PPT 项目文件夹路径，必须包含 index.html
        output_pdf: PDF 输出路径，默认保存到桌面
        aspect_ratio: 页面宽高比，默认 16/9
        width: 截图宽度（像素），默认 1920（1K）
        dpi: PDF 分辨率，默认 150
        wait_animation: 每页动画等待时间（毫秒），默认 1500
        wait_load: 页面初始加载等待时间（毫秒），默认 3000

    返回：
        {"success": bool, "pages": int, "output": str, "size_mb": float, "message": str}
    """

    result = {"success": False, "pages": 0, "output": "", "size_mb": 0.0, "message": ""}

    try:
        # 处理默认输出路径
        if output_pdf is None:
            project_name = Path(project_dir).name or "output"
            output_pdf = os.path.join(_get_desktop(), f"{project_name}.pdf")

        project_path = Path(project_dir).resolve()
        output_path = Path(output_pdf).resolve()
        output_path.parent.mkdir(parents=True, exist_ok=True)

        if not (project_path / "index.html").exists():
            result["message"] = f"项目文件夹缺少 index.html: {project_dir}"
            print(f"[ppt_to_pdf] ❌ {result['message']}")
            return result

        height = int(width / aspect_ratio)
        temp_dir = output_path.parent / f"._temp_{int(time.time())}"
        temp_dir.mkdir(exist_ok=True)

        print(f"[ppt_to_pdf] 项目: {project_path}")
        print(f"[ppt_to_pdf] 输出: {output_path}")
        print(f"[ppt_to_pdf] 尺寸: {width}x{height}px (16:9)")

        # 启动 HTTP 服务器
        port = _find_free_port()
        shutdown = _start_http_server(str(project_path), port)
        url = f"http://127.0.0.1:{port}/index.html"

        screenshots = []

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                viewport={"width": 1920, "height": 1080},
                device_scale_factor=1,
            )
            page = context.new_page()

            print(f"[ppt_to_pdf] 加载页面...")
            page.goto(url, wait_until="networkidle")
            time.sleep(wait_load / 1000)

            # 获取总页数
            total = page.evaluate("""() => {
                return document.querySelectorAll('.slide').length;
            }""")
            print(f"[ppt_to_pdf] 共 {total} 页")

            for i in range(total):
                print(f"[ppt_to_pdf] 第 {i+1}/{total} 页...", end=" ", flush=True)

                # 跳转到指定页
                page.evaluate(f"""(idx) => {{
                    if (window.slideNavigator) {{
                        window.slideNavigator.goTo(idx);
                    }} else {{
                        document.querySelectorAll('.slide').forEach((s, j) => {{
                            s.classList.toggle('active', j === idx);
                        }});
                    }}
                }}""", i)

                time.sleep(wait_animation / 1000)

                # 截图当前 slide 元素
                slide = page.locator(f".slide[data-index=\"{i}\"]")
                shot = temp_dir / f"slide_{i+1:02d}.png"
                slide.screenshot(path=str(shot))

                # 裁剪为 16:9 比例
                img = Image.open(shot)
                img = _ensure_ratio(img, aspect_ratio)
                img = img.resize((width, height), Image.LANCZOS)
                img.save(shot, "PNG", optimize=True)

                screenshots.append(shot)
                print("✓")

            browser.close()

        shutdown()

        # 合成 PDF
        print(f"[ppt_to_pdf] 合成 PDF...")
        images = []
        for p in screenshots:
            img = Image.open(p)
            if img.mode != "RGB":
                img = img.convert("RGB")
            images.append(img)

        first = images[0]
        rest = images[1:] if len(images) > 1 else []

        first.save(
            output_path,
            "PDF",
            resolution=dpi,
            save_all=True,
            append_images=rest
        )

        size_mb = output_path.stat().st_size / 1024 / 1024

        # 清理临时文件
        for p in screenshots:
            p.unlink()
        temp_dir.rmdir()

        result["success"] = True
        result["pages"] = len(images)
        result["output"] = str(output_path)
        result["size_mb"] = round(size_mb, 2)
        result["message"] = f"PDF 生成成功: {len(images)} 页, {size_mb:.2f} MB"
        print(f"[ppt_to_pdf] ✅ {result['message']}")

    except Exception as e:
        result["message"] = f"错误: {str(e)}"
        print(f"[ppt_to_pdf] ❌ {result['message']}")

    return result


# ==================== 命令行入口 ====================

def main():
    if len(sys.argv) < 2:
        print("用法: python ppt_to_pdf_tool.py <项目文件夹路径> [PDF输出路径]")
        print("示例: python ppt_to_pdf_tool.py D:\\furina_ppt")
        print("      python ppt_to_pdf_tool.py D:\\furina_ppt D:\\output\\pangu.pdf")
        sys.exit(1)

    result = ppt_to_pdf(
        project_dir=sys.argv[1],
        output_pdf=sys.argv[2] if len(sys.argv) > 2 else None
    )

    if result["success"]:
        print(f"\n✅ 完成 → {result['output']}")
    else:
        print(f"\n❌ 失败: {result['message']}")
        sys.exit(1)


