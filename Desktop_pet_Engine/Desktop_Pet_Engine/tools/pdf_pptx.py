#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os
import socket
import threading
import http.server
import atexit
import time
from pathlib import Path
from playwright.sync_api import sync_playwright
from PIL import Image

def get_desktop():
    home = Path.home()
    for name in ["Desktop", "桌面"]:
        desktop = home / name
        if desktop.exists():
            return str(desktop)
    return str(home)

def find_free_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]

def start_http_server(directory, port):
    original_dir = os.getcwd()
    os.chdir(directory)
    class QuietHandler(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *args, **kwargs): pass
    httpd = http.server.HTTPServer(("127.0.0.1", port), QuietHandler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    time.sleep(0.5)
    def shutdown():
        httpd.shutdown()
        httpd.server_close()
        os.chdir(original_dir)
    atexit.register(shutdown)
    return httpd

def crop_to_16_9(img, target_width, target_height):
    w, h = img.size
    target_ratio = target_width / target_height
    current_ratio = w / h
    if current_ratio > target_ratio:
        new_w = int(h * target_ratio)
        left = (w - new_w) // 2
        img = img.crop((left, 0, left + new_w, h))
    else:
        new_h = int(w / target_ratio)
        top = (h - new_h) // 2
        img = img.crop((0, top, w, top + new_h))
    img = img.resize((target_width, target_height), Image.LANCZOS)
    return img

def ppt_to_pdf_consistent(
    project_dir,
    output_pdf=None,
    viewport_width=1920,
    viewport_height=1080,
    scale_factor=3,      # 改为 3 倍，获得 5K 级截图
    dpi=200,             # 降低 DPI，使文字物理尺寸更大
    wait_animation=4000,
    wait_load=4000
):
    project_path = Path(project_dir).resolve()
    if not (project_path / "index.html").exists():
        raise FileNotFoundError(f"未找到 index.html: {project_dir}")

    if output_pdf is None:
        output_pdf = Path(get_desktop()) / f"{project_path.name}.pdf"
    output_pdf = Path(output_pdf).resolve()
    if output_pdf.exists():
        try:
            with open(output_pdf, "ab"):
                pass
        except PermissionError:
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            new_name = output_pdf.stem + f"_{timestamp}" + output_pdf.suffix
            output_pdf = output_pdf.parent / new_name
            print(f"⚠️ 原文件被占用，自动改名为: {output_pdf.name}")

    actual_width = viewport_width * scale_factor
    actual_height = viewport_height * scale_factor
    temp_dir = output_pdf.parent / f"._temp_{int(time.time())}"
    temp_dir.mkdir(exist_ok=True)

    print(f"项目: {project_path}")
    print(f"输出: {output_pdf}")
    print(f"视口尺寸: {viewport_width}×{viewport_height}px (布局基准)")
    print(f"设备缩放: {scale_factor} → 截图分辨率 {actual_width}×{actual_height}px")
    print(f"PDF DPI: {dpi}")

    port = find_free_port()
    httpd = start_http_server(str(project_path), port)
    url = f"http://127.0.0.1:{port}/index.html"

    screenshots = []
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                viewport={"width": viewport_width, "height": viewport_height},
                device_scale_factor=scale_factor
            )
            page = context.new_page()
            page.goto(url, wait_until="networkidle")
            page.wait_for_timeout(wait_load)

            total = page.evaluate("document.querySelectorAll('.slide').length")
            print(f"检测到 {total} 个幻灯片")

            has_go_to_slide = page.evaluate("typeof window.goToSlide === 'function'")
            if not has_go_to_slide:
                print("⚠️ 未找到 window.goToSlide，使用备用翻页")

            for i in range(total):
                print(f"处理 {i+1}/{total}...", end=" ", flush=True)

                if has_go_to_slide:
                    page.evaluate(f"window.goToSlide({i})")
                    try:
                        page.wait_for_function(
                            f"window.getCurrentSlide && window.getCurrentSlide() === {i}",
                            timeout=5000
                        )
                    except:
                        print("索引等待超时", end=" ")
                else:
                    page.evaluate(f"""
                        (idx) => {{
                            const c = document.getElementById('slidesContainer');
                            if (c) c.style.transform = `translateY(${{-idx * window.innerHeight}}px)`;
                        }}
                    """, i)

                page.wait_for_timeout(wait_animation)

                page.evaluate("""
                    () => Promise.all(Array.from(document.images).map(img => {
                        if (img.complete) return Promise.resolve();
                        return new Promise(resolve => { img.onload = img.onerror = resolve; });
                    }))
                """)

                slide = page.locator(".slide").nth(i)
                shot = temp_dir / f"slide_{i+1:02d}.png"
                slide.screenshot(path=str(shot))

                img = Image.open(shot)
                img = crop_to_16_9(img, actual_width, actual_height)
                img.save(shot, "PNG", optimize=True)
                screenshots.append(shot)
                print("✓")

            browser.close()
    finally:
        httpd.shutdown()

    if not screenshots:
        raise RuntimeError("没有生成任何截图")

    print("合成 PDF...")
    images = []
    for p in screenshots:
        img = Image.open(p).convert("RGB")
        if img.size != (actual_width, actual_height):
            img = img.resize((actual_width, actual_height), Image.LANCZOS)
        images.append(img)

    images[0].save(
        output_pdf,
        "PDF",
        resolution=dpi,
        save_all=True,
        append_images=images[1:]
    )

    size_mb = output_pdf.stat().st_size / (1024 * 1024)
    for p in screenshots:
        p.unlink()
    temp_dir.rmdir()

    print(f"✅ 成功生成 {len(images)} 页 PDF: {output_pdf} ({size_mb:.2f} MB)")
    print(f"   布局基于 {viewport_width}×{viewport_height}，截图分辨率 {actual_width}×{actual_height}")
    return str(output_pdf)

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        project = sys.argv[1]
    else:
        project = input("请输入项目文件夹路径: ").strip()
    output = sys.argv[2] if len(sys.argv) > 2 else None

    ppt_to_pdf_consistent(
        project_dir=project,
        output_pdf=output,
        viewport_width=1920,
        viewport_height=1080,
        scale_factor=3,      # 高清晰（5K 级）
        dpi=200,             # 文字物理尺寸更大
        wait_animation=4000
    )