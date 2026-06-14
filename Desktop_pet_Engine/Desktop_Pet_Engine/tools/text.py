#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
HTML 幻灯片项目 -> 矢量 PDF（原生打印，文字清晰）
用法：
    1. 直接运行，输入项目文件夹路径（必须包含 index.html）
    2. 可选：输入输出 PDF 路径（默认保存到桌面，文件名为文件夹名.pdf）
"""

import os
import socket
import threading
import http.server
import atexit
from pathlib import Path
from playwright.sync_api import sync_playwright

# ==================== 内部辅助函数 ====================
def _get_desktop():
    home = Path.home()
    for name in ["Desktop", "桌面", "Escritorio", "Bureau"]:
        desktop = home / name
        if desktop.exists():
            return str(desktop)
    return str(home)

def _find_free_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]

def _start_http_server(directory, port):
    """在 directory 启动一个简单的 HTTP 服务器，监听 127.0.0.1:port"""
    original_dir = os.getcwd()
    os.chdir(directory)

    class QuietHandler(http.server.SimpleHTTPRequestHandler):
        def log_message(self, format, *args):
            pass  # 减少控制台噪音

    httpd = http.server.TCPServer(("127.0.0.1", port), QuietHandler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    time.sleep(0.5)  # 确保服务器启动

    def shutdown():
        httpd.shutdown()
        httpd.server_close()
        os.chdir(original_dir)

    atexit.register(shutdown)
    return httpd

# ==================== 主要转换函数 ====================
def html_to_pdf_vector(project_dir: str, output_pdf: str = None, wait_load: int = 3000):
    """
    将 HTML 幻灯片项目直接打印为矢量 PDF（原生打印，文字无限清晰）

    参数：
        project_dir: 项目文件夹路径（必须包含 index.html）
        output_pdf:   输出 PDF 路径，默认保存在桌面，文件名为文件夹名.pdf
        wait_load:    页面加载等待时间（毫秒），默认 3000
    """
    project_path = Path(project_dir).resolve()
    index_html = project_path / "index.html"
    if not index_html.exists():
        raise FileNotFoundError(f"❌ 项目文件夹缺少 index.html: {project_dir}")

    # 默认输出路径：桌面/文件夹名.pdf
    if output_pdf is None:
        folder_name = project_path.name
        output_pdf = Path(_get_desktop()) / f"{folder_name}.pdf"
    else:
        output_pdf = Path(output_pdf).resolve()
    output_pdf.parent.mkdir(parents=True, exist_ok=True)

    print(f"📁 项目目录: {project_path}")
    print(f"📄 输出 PDF: {output_pdf}")

    # 启动本地 HTTP 服务器，确保 CSS/JS/图片正常加载
    port = _find_free_port()
    httpd = _start_http_server(str(project_path), port)
    url = f"http://127.0.0.1:{port}/index.html"
    print(f"🌐 启动本地服务器: {url}")

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(viewport={"width": 1920, "height": 1080})
            page.goto(url, wait_until="networkidle")
            page.wait_for_timeout(wait_load)

            # 【可选】注入打印分页样式，防止内容被截断（根据你的实际 slide 容器类名修改）
            # 假设每个 slide 的 class 是 "slide"，如果不是请改成你的类名
            page.add_style_tag(content="""
                @media print {
                    /* 强制每个 .slide 单独成页 */
                    .slide {
                        page-break-after: always;
                        break-after: page;
                        height: auto;
                        min-height: 100%;
                        margin: 0;
                        padding: 0;
                    }
                    .slide:last-child {
                        page-break-after: auto;
                    }
                    body {
                        margin: 0;
                        padding: 0;
                    }
                    /* 隐藏导航栏等干扰元素 */
                    .nav, .controls, .pagination {
                        display: none;
                    }
                    /* 保证背景色/背景图打印 */
                    * {
                        -webkit-print-color-adjust: exact;
                        print-color-adjust: exact;
                    }
                }
            """)

            # 生成矢量 PDF（原生打印）
            page.pdf(
                path=str(output_pdf),
                print_background=True,          # 保留背景颜色/图片
                margin={"top": "0", "bottom": "0", "left": "0", "right": "0"},
                width="10in",                   # 10 英寸宽
                height="5.625in",               # 16:9 高度 = 10 * 9/16
                # 若想用 A4 纸，可改为 format="A4" 并注释 width/height
            )
            browser.close()

    finally:
        httpd.shutdown()

    size_mb = output_pdf.stat().st_size / (1024 * 1024)
    print(f"✅ 矢量 PDF 生成成功！")
    print(f"   路径: {output_pdf}")
    print(f"   大小: {size_mb:.2f} MB")
    return str(output_pdf)

# ==================== 命令行入口 ====================
def main():
    import sys
    import time  # 用于 sleep

    print("=" * 50)
    print("HTML 幻灯片 → 矢量 PDF 工具（原生打印，清晰文字）")
    print("=" * 50)

    # 获取项目文件夹路径
    if len(sys.argv) > 1:
        project_dir = sys.argv[1]
    else:
        project_dir = input("请输入项目文件夹路径（包含 index.html）: ").strip()
        if not project_dir:
            print("❌ 未输入路径，退出")
            return

    # 获取输出 PDF 路径（可选）
    if len(sys.argv) > 2:
        output_pdf = sys.argv[2]
    else:
        output_pdf = input(f"请输入输出 PDF 路径（直接回车则保存到桌面）: ").strip()
        if not output_pdf:
            output_pdf = None

    try:
        html_to_pdf_vector(project_dir, output_pdf)
    except Exception as e:
        print(f"❌ 转换失败: {e}")
        raise

if __name__ == "__main__":
    main()