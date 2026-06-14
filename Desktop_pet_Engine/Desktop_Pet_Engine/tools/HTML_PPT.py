import asyncio
from playwright.async_api import async_playwright
from bs4 import BeautifulSoup
from PIL import Image
import base64
import os
import re


async def generate_editable_pdf(html_path, output_pdf_path="output.pdf"):
    """
    将包含 SVG 的 HTML 转为：
      背景 + 装饰 → 单张 PNG 图片
      所有文字 → 可编辑 HTML 文本层
    最终生成一个可直接打印为 PDF 的 HTML 文件。

    参数:
        html_path: 原始 HTML 文件路径（或直接传入 HTML 字符串）
        output_pdf_path: 最终输出的 PDF 路径（实际我们会生成一个中间 HTML）
    """
    # 1. 读取原始 HTML
    with open(html_path, 'r', encoding='utf-8') as f:
        original_html = f.read()

    soup = BeautifulSoup(original_html, 'lxml')

    # 2. 提取所有 SVG 内 <text> 元素的位置与样式
    svg_tag = soup.find('svg')
    if not svg_tag:
        raise ValueError("未找到 SVG 标签")

    texts_info = []
    for text_elem in svg_tag.find_all('text', recursive=True):
        # 获取坐标与样式（内联属性优先）
        x = text_elem.get('x')
        y = text_elem.get('y')
        if x is None or y is None:
            continue
        # 处理可能的多个坐标（例如 x="10 20"），只取第一个
        x = str(x).split()[0]
        y = str(y).split()[0]

        font_size = text_elem.get('font-size', '16px')
        font_family = text_elem.get('font-family', 'sans-serif')
        fill = text_elem.get('fill', '#ffffff')
        font_weight = text_elem.get('font-weight', 'normal')
        letter_spacing = text_elem.get('letter-spacing', 'normal')
        text_anchor = text_elem.get('text-anchor', 'start')
        transform = text_elem.get('transform', '')
        content = text_elem.get_text(strip=True)
        if not content:
            continue

        # 记录文字信息
        texts_info.append({
            'x': int(float(x)),
            'y': int(float(y)),
            'font_size': font_size,
            'font_family': font_family,
            'fill': fill,
            'font_weight': font_weight,
            'letter_spacing': letter_spacing,
            'text_anchor': text_anchor,
            'transform': transform,
            'content': content
        })

    # 3. 生成“无文字背景图”
    # 克隆 SVG，删除所有 <text> 节点及其包含的子孙文本元素
    svg_without_text = svg_tag.clone()
    for text_node in svg_without_text.find_all('text'):
        text_node.decompose()

    # 将修改后的 SVG 重新注入 HTML（保持其他元素不变）
    svg_tag.replace_with(svg_without_text)
    html_without_text = str(soup)

    # 保存为临时文件，用于截图背景
    bg_html_path = "temp_bg.html"
    with open(bg_html_path, 'w', encoding='utf-8') as f:
        f.write(html_without_text)

    # 4. 使用 Playwright 渲染背景并截图（1920x1080）
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page(viewport={'width': 1920, 'height': 1080})
        await page.goto(f'file://{os.path.abspath(bg_html_path)}')
        # 等待所有资源加载完成
        await page.wait_for_load_state('networkidle')
        # 截图并转为 base64
        screenshot_bytes = await page.screenshot(full_page=True)
        await browser.close()

    # 保存背景图片到磁盘（可选）
    bg_image_path = "background.png"
    with open(bg_image_path, 'wb') as f:
        f.write(screenshot_bytes)

    # 将图片转为 base64 内嵌到 HTML
    with open(bg_image_path, 'rb') as img_file:
        bg_base64 = base64.b64encode(img_file.read()).decode('utf-8')

    # 5. 生成最终 HTML：背景图片 + 绝对定位的文字层
    final_html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <title>Blendr - 可编辑文字版</title>
        <style>
            * {{
                margin: 0;
                padding: 0;
                box-sizing: border-box;
            }}
            body {{
                width: 1920px;
                height: 1080px;
                position: relative;
                overflow: hidden;
                background: #000; /* fallback */
                font-family: 'Segoe UI', 'Inter', system-ui, sans-serif;
            }}
            .bg {{
                position: absolute;
                top: 0;
                left: 0;
                width: 1920px;
                height: 1080px;
                z-index: 1;
            }}
            .text-layer {{
                position: absolute;
                top: 0;
                left: 0;
                width: 1920px;
                height: 1080px;
                z-index: 2;
                pointer-events: none;  /* 让文字不干扰点击，但打印时可见 */
            }}
            .text-item {{
                position: absolute;
                white-space: nowrap;
                /* 默认样式，会被具体属性覆盖 */
            }}
        </style>
    </head>
    <body>
        <img class="bg" src="data:image/png;base64,{bg_base64}" alt="background" />
        <div class="text-layer">
    """

    # 为每个文字生成绝对定位的 span
    for info in texts_info:
        # 根据 text_anchor 调整 left 位置
        left = info['x']
        # 如果是居中对齐，需要减去文字宽度的一半，但我们不知道宽度，可以通过 CSS 的 transform: translateX(-50%)
        if info['text_anchor'] == 'middle':
            transform_css = f"transform: translateX(-50%);"
            left_style = f"left: {left}px;"
        else:
            transform_css = ""
            left_style = f"left: {left}px;"

        # 处理 transform 属性（简单旋转）
        rotate_css = ""
        if info['transform']:
            # 提取 rotate(deg) 部分
            match = re.search(r'rotate\(([-\d.]+)', info['transform'])
            if match:
                deg = match.group(1)
                rotate_css = f"transform: rotate({deg}deg); " + transform_css
            else:
                rotate_css = transform_css
        else:
            rotate_css = transform_css

        # 组装样式
        style = f"""
            position: absolute;
            top: {info['y']}px;
            {left_style}
            font-size: {info['font_size']};
            font-family: {info['font_family']}, sans-serif;
            color: {info['fill']};
            font-weight: {info['font_weight']};
            letter-spacing: {info['letter_spacing']};
            white-space: nowrap;
            {rotate_css}
        """
        final_html += f'<div class="text-item" style="{style}">{info["content"]}</div>\n'

    final_html += """
        </div>
        <script>
            // 可选：确保打印时文字清晰，不做额外处理
            window.onload = () => {
                console.log('可编辑文字 PDF 准备就绪');
            };
        </script>
    </body>
    </html>
    """

    # 保存最终 HTML
    final_html_path = "final_editable.html"
    with open(final_html_path, 'w', encoding='utf-8') as f:
        f.write(final_html)

    print(f"✅ 生成成功！")
    print(f"   中间背景图片：{bg_image_path}")
    print(f"   最终可编辑 HTML：{final_html_path}")
    print(f"📄 请用 Chrome 打开 {final_html_path}，然后按 Ctrl+P 保存为 PDF，并设置：")
    print("   - 边距：无")
    print("   - 缩放：100%")
    print("   - 取消页眉/页脚")
    print("   - 目标：另存为 PDF")
    print("   这样得到的 PDF 中，所有文字均可复制、搜索，且背景特效完美保留。")

    # 清理临时背景 HTML
    if os.path.exists(bg_html_path):
        os.remove(bg_html_path)


# 使用示例
if __name__ == "__main__":
    # 请将之前的 blendr 首页代码保存为 "blendr_home.html" 再运行
    asyncio.run(generate_editable_pdf("blendr_home.html"))