from langchain.tools import tool

try:
    import fitz
except ImportError:
    fitz = None

from pptx import Presentation
from pptx.util import Inches, Emu
from playwright.sync_api import sync_playwright
from pathlib import Path
import re
import shutil
import json
from tools.style import style

# ===================== 基础目录：桌面 =====================
BASE_DIR = Path.home() / "Desktop"


def _sanitize_folder_name(name: str) -> str:
    """清理主题名，生成合法文件夹名"""
    if not name:
        return "未命名主题"
    name = re.sub(r'[\\/*?:"<>|]', "", name).strip()
    return name[:30] if name else "未命名主题"


def _get_workspace(folder_name: str) -> Path:
    """获取主题文件夹路径"""
    return BASE_DIR / _sanitize_folder_name(folder_name)


# =====================================================================
# 工具1：大纲生成（12-30页，明确图片占位格式）
# =====================================================================
@tool
def neirong(user_requirement: str) -> str:
    """
    第一步：根据用户需求生成PPT分页大纲，12-30页。
    如需图片，在对应位置写：【图片占位：具体描述】，例如【图片占位：Blender 3D建模界面截图】
    """
    prompt = f"""
请根据以下用户需求，编写一份专业PPT分页大纲。

【用户需求】
{user_requirement}

【输出规则】
1. 总页数控制在 12-30 页
2. 结构：封面 → 目录 → 过渡页 → 正文（混合版式） → 结尾
3. 正文版式类型：
   - [text]：标题 + 矩形高亮列表
   - [timeline]：时间轴（左侧节点 + 右侧内容块）
   - [card-grid]：2×2 或 3 列矩形卡片（图标+标题+描述）
   - [two-col]：左右双栏对比（带矩形边框）
   - [split]：左文右图（图文混排，可插入真实图片）
   - [data]：大数字矩形卡片 + 图表占位
4. 插入图片写法：在需要图片的位置写 【图片占位：具体描述】
   - 描述要具体，方便后续搜索下载，例如：
     - 【图片占位：Blender 3D建模软件界面截图】
     - 【图片占位：百事可乐蓝色罐装产品图】
     - 【图片占位：2024年全球智能手机市场份额饼图】
   - 图片占位可出现在 split 页的右侧、card-grid 的卡片内、或任何需要配图的位置
5. 每页用 === 第N页 [类型] === 分隔
6. 仅输出纯文本大纲，不生成HTML

【输出格式示例】
=== 第1页 [cover] ===
标题：XXXX
副标题：XXXX

=== 第2页 [toc] ===
1. 第一章 XXX
2. 第二章 XXX

=== 第3页 [transition] ===
章节标题：第一章 概述

=== 第4页 [text] ===
标题：核心优势
- 要点1：XXXX
- 要点2：XXXX

=== 第5页 [split] ===
标题：产品展示
左侧：
- 支持多平台运行
- 实时渲染预览
右侧：【图片占位：软件主界面深色模式截图】

=== 第6页 [timeline] ===
标题：发展历程
- 1998年：公司成立
- 2005年：首款产品发布
- 2012年：完成B轮融资
- 2024年：AI转型

=== 第7页 [card-grid] ===
标题：产品矩阵
- 卡片1：产品A / 企业云服务平台
- 卡片2：产品B / 消费者智能助手
- 卡片3：产品C / 开发者开源框架
- 卡片4：产品D / 教育在线课堂

=== 第8页 [two-col] ===
标题：方案对比
左栏标题：传统方案
- 成本高，部署周期长
- 维护困难，扩展性差
右栏标题：我们的方案
- 低成本，即开即用
- 云端维护，弹性扩展

=== 第9页 [data] ===
标题：核心数据
- 数据1：2,000万+ / 注册用户
- 数据2：99.99% / 服务可用性
- 数据3：150+ / 覆盖国家

=== 第N页 [ending] ===
标题：谢谢观看
副标题：如有疑问欢迎交流
"""
    return prompt


# =====================================================================
# 工具2：提取图片需求（新增）
# =====================================================================
@tool
def extract_image_needs(ppt_outline: str, folder_name: str = "") -> str:
    """
    第二步：分析PPT大纲，提取所有图片占位需求，保存到主题文件夹的 image_needs.txt。
    同时生成 image_mapping.json，供后续下载和HTML生成使用。
    """
    workspace = _get_workspace(folder_name)
    workspace.mkdir(parents=True, exist_ok=True)

    # 提取所有 【图片占位：...】
    pattern = r'【图片占位：([^】]+)】'
    matches = re.findall(pattern, ppt_outline)

    if not matches:
        return "⚠️ 大纲中未检测到图片占位符，无需下载图片。"

    # 去重并保持顺序
    seen = set()
    unique_needs = []
    for m in matches:
        desc = m.strip()
        if desc and desc not in seen:
            seen.add(desc)
            unique_needs.append(desc)

    # 生成建议文件名（安全化）
    mapping = {}
    needs_lines = []
    for i, desc in enumerate(unique_needs, 1):
        safe = re.sub(r'[\\/*?:"<>|]', "", desc).replace(" ", "_").strip()[:25]
        filename = f"img_{i:02d}_{safe}.jpg"
        mapping[desc] = filename
        needs_lines.append(f"{i}. {desc} -> {filename}")

    # 保存需求清单
    needs_file = workspace / "image_needs.txt"
    with open(needs_file, "w", encoding="utf-8") as f:
        f.write(f"# 主题：{folder_name}\n")
        f.write(f"# 共需 {len(unique_needs)} 张图片\n")
        f.write("# 格式：序号. 描述 -> 保存文件名\n\n")
        f.write("\n".join(needs_lines))

    # 保存映射JSON（供HTML生成时替换）
    mapping_file = workspace / "image_mapping.json"
    with open(mapping_file, "w", encoding="utf-8") as f:
        json.dump(mapping, f, ensure_ascii=False, indent=2)

    return (
        f"✅ 已提取 {len(unique_needs)} 个图片需求\n"
        f"📄 需求清单：{needs_file}\n"
        f"📄 映射文件：{mapping_file}\n"
        f"🖼️ 需求列表：\n" + "\n".join(needs_lines)
    )


# =====================================================================
# 工具3：下载图片（新增，需要网络）
# =====================================================================
@tool
def download_images(folder_name: str = "", max_images: int = 10) -> str:
    """
    第三步：读取 image_needs.txt，自动上网搜索并下载图片到主题文件夹。
    依赖：pip install duckduckgo-search requests
    """
    workspace = _get_workspace(folder_name)
    needs_file = workspace / "image_needs.txt"
    mapping_file = workspace / "image_mapping.json"

    if not needs_file.exists():
        return "❌ 未找到 image_needs.txt，请先调用 extract_image_needs"

    # 读取映射
    if mapping_file.exists():
        with open(mapping_file, "r", encoding="utf-8") as f:
            mapping = json.load(f)
    else:
        # 手动解析 txt
        mapping = {}
        with open(needs_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if " -> " in line:
                    # 格式：1. 描述 -> 文件名
                    parts = line.split(" -> ", 1)
                    desc = re.sub(r'^\d+\.\s*', '', parts[0]).strip()
                    filename = parts[1].strip()
                    mapping[desc] = filename

    if not mapping:
        return "⚠️ 图片需求清单为空"

    # 检查依赖
    try:
        from duckduckgo_search import DDGS
        import requests
    except ImportError as e:
        return f"❌ 缺少依赖，请安装：pip install duckduckgo-search requests\n错误：{e}"

    downloaded = []
    failed = []

    with DDGS() as ddgs:
        for desc, filename in list(mapping.items())[:max_images]:
            save_path = workspace / filename
            try:
                # 搜索图片（取第一张）
                results = ddgs.images(desc, max_results=3)
                if not results:
                    failed.append(f"{desc}（无搜索结果）")
                    continue

                # 尝试下载前3个结果，直到成功
                img_saved = False
                for r in results:
                    img_url = r.get("image") or r.get("url") or r.get("thumbnail")
                    if not img_url:
                        continue
                    try:
                        headers = {
                            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                        }
                        resp = requests.get(img_url, headers=headers, timeout=20)
                        if resp.status_code == 200 and len(resp.content) > 1000:
                            with open(save_path, "wb") as f:
                                f.write(resp.content)
                            downloaded.append(f"{desc} -> {filename}")
                            img_saved = True
                            break
                    except Exception:
                        continue

                if not img_saved:
                    failed.append(f"{desc}（下载失败）")

            except Exception as e:
                failed.append(f"{desc}（{str(e)}）")

    # 更新映射文件（只保留成功下载的）
    success_mapping = {}
    for d in downloaded:
        desc = d.split(" -> ")[0]
        filename = d.split(" -> ")[1]
        success_mapping[desc] = filename

    with open(mapping_file, "w", encoding="utf-8") as f:
        json.dump(success_mapping, f, ensure_ascii=False, indent=2)

    return (
        f"✅ 图片下载完成\n"
        f"🟢 成功 {len(downloaded)} 张：\n" + "\n".join(downloaded) + "\n"
        f"🔴 失败 {len(failed)} 张：\n" + "\n".join(failed) if failed else ""
    )


# =====================================================================
# 工具4：HTML生成（自动替换已下载的图片）
# =====================================================================
@tool
def create_ppt_html(ppt_content: str, folder_name: str = "") -> str:
    """
    第四步：根据PPT大纲生成HTML。
    如果主题文件夹中存在 image_mapping.json，会自动将【图片占位：描述】替换为真实图片。
    """
    # 尝试读取图片映射，替换大纲中的占位符
    workspace = _get_workspace(folder_name)
    mapping_file = workspace / "image_mapping.json"

    processed_content = ppt_content
    if mapping_file.exists():
        try:
            with open(mapping_file, "r", encoding="utf-8") as f:
                mapping = json.load(f)
            for desc, filename in mapping.items():
                placeholder = f"【图片占位：{desc}】"
                # 替换为图片标签
                img_tag = f'<div class="img-box"><img src="{filename}" class="slide-img"></div>'
                processed_content = processed_content.replace(placeholder, img_tag)
        except Exception:
            pass


    # 对于未替换的占位符，保留占位样式
    processed_content = re.sub(
        r'【图片占位：([^】]+)】',
        r'<div class="img-placeholder"><span class="ph-icon">🖼️</span>\1</div>',
        processed_content
    )



    html_prompt = f"""
            根据以下PPT分页内容，生成可直接转PDF的专业HTML代码。
            
            【PPT分页内容】
            {processed_content}
            
            【风格选择规则】
            根据主题自动判断CSS主题类：
            - 商务/企业/金融/咨询 → theme-blue
            - 科技/AI/互联网/编程/游戏 → theme-dark
            - 食品/饮料/快消/娱乐 → theme-orange
            - 医疗/健康/环保/农业 → theme-green
            - 党政/红色教育/国企 → theme-red
            - 教育/培训/校园/儿童 → theme-yellow
            
            【强制规则】
            1. 每页 <div class="slide">，尺寸 1920x1080
            2. 必须使用对应版式类：cover / toc / transition / text / timeline / card-grid / two-col / split / data / ending
            3. 封面用 h1；目录用 toc-card 网格；时间轴用 timeline-item；卡片用 card-item；对比用 vs-box
            4. 每页（封面除外）加 <div class="page-num">页码</div>
            5. 内容中的 <div class="img-box"> 和 <img class="slide-img"> 必须原样保留，不要修改
            6. 只输出完整HTML，不要任何说明或markdown标记
            7. 不省略任何页面
            8.{style()}
            

"""
    return html_prompt


# =====================================================================
# 工具5：保存HTML
# =====================================================================
@tool
def save_html_file(html_code: str, file_name: str = "ppt_temp.html", folder_name: str = "") -> str:
    """
    第五步：将HTML保存到桌面【主题文件夹】内。
    """
    workspace = _get_workspace(folder_name)
    workspace.mkdir(parents=True, exist_ok=True)

    file_path = workspace / file_name
    try:
        cleaned = html_code.strip()
        cleaned = re.sub(r'^```html\s*', '', cleaned)
        cleaned = re.sub(r'\s*```$', '', cleaned)

        with open(file_path, "w", encoding="utf-8") as f:
            f.write(cleaned)
        return f" HTML已保存到主题文件夹：{file_path.resolve()}"
    except Exception as e:
        return f" 保存失败：{str(e)}"


# =====================================================================
# 工具6：HTML转PDF
# =====================================================================
@tool
def html_to_pdf(html_path: str) -> str:
    """
    第六步：将本地HTML转PDF，输出到HTML所在文件夹。
    HTML中的<img>会一并渲染进PDF（图片需与HTML同目录）。
    """
    html_file = Path(html_path)
    if not html_file.exists():
        return f" HTML文件不存在：{html_path}"

    pdf_path = str(html_file.with_suffix('.pdf'))

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            try:
                page = browser.new_page(viewport={"width": 1920, "height": 1080})
                page.goto(html_file.absolute().as_uri(), wait_until="networkidle")
                page.wait_for_selector(".slide", timeout=10000)
                # 等待图片加载
                page.wait_for_timeout(2000)
                page.pdf(
                    path=pdf_path,
                    width="1920px", height="1080px",
                    print_background=True,
                    margin={"top": "0", "right": "0", "bottom": "0", "left": "0"},
                    prefer_css_page_size=True
                )
            finally:
                browser.close()

        doc = fitz.open(pdf_path)
        page_count = len(doc)
        doc.close()
        return f" PDF生成成功！共 {page_count} 页，路径：{pdf_path}"
    except Exception as e:
        return f" PDF转换失败：{str(e)}"


# =====================================================================
# 工具7：PDF转PPT
# =====================================================================
@tool
def pdf_to_ppt(pdf_path: str, ppt_name: str = "最终演示文稿.pptx") -> str:
    """
    第七步：PDF转PPT，所有文件都在同一个主题文件夹内。
    """
    pdf_file = Path(pdf_path)
    if not pdf_file.exists():
        return f" PDF文件不存在：{pdf_path}"

    ppt_path = str(pdf_file.parent / ppt_name)
    temp_img_dir = pdf_file.parent / "temp_img"
    temp_img_dir.mkdir(exist_ok=True)
    img_list = []

    try:
        doc = fitz.open(str(pdf_file))
        total_pages = len(doc)
        if total_pages == 0:
            doc.close()
            return " PDF为空"

        zoom = 2.0
        matrix = fitz.Matrix(zoom, zoom)
        for idx, page in enumerate(doc):
            pix = page.get_pixmap(matrix=matrix, alpha=False)
            img_path = temp_img_dir / f"slide_{idx+1:03d}.png"
            pix.save(str(img_path))
            img_list.append(str(img_path))
        doc.close()

        prs = Presentation()
        prs.slide_width = Inches(13.333)
        prs.slide_height = Inches(7.5)
        blank_layout = prs.slide_layouts[6]

        for img_path in img_list:
            slide = prs.slides.add_slide(blank_layout)
            slide.shapes.add_picture(
                img_path, left=Emu(0), top=Emu(0),
                width=prs.slide_width, height=prs.slide_height
            )

        prs.save(ppt_path)
        shutil.rmtree(temp_img_dir, ignore_errors=True)

        return (
            f" PPT制作完成！\n"
            f" 共 {total_pages} 页\n"
            f" 尺寸：16:9 宽屏\n"
            f" 已保存到主题文件夹：{ppt_path}"
        )
    except Exception as e:
        shutil.rmtree(temp_img_dir, ignore_errors=True)
        return f" PPT转换失败：{str(e)}"