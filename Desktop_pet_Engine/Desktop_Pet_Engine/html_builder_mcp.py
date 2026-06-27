"""html_builder_mcp.py — HTML 网页生成 MCP 服务器

芙芙可以用这个工具创建漂亮的 HTML 网页文件。
"""

import logging
from datetime import datetime
from pathlib import Path

from mcp.server import Server
from mcp.server.models import InitializationOptions
import mcp.server.stdio
import mcp.types as types
from mcp.types import ServerCapabilities, ToolsCapability

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("html-builder")

server = Server("html-builder-server")

# 默认输出目录（桌面）
DESKTOP_DIR = Path.home() / "Desktop"
OUTPUT_DIR = Path(__file__).resolve().parent.parent / "data" / "html_output"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


@server.list_tools()
async def list_tools() -> list[types.Tool]:
    return [
        types.Tool(
            name="create_html",
            description="创建一个漂亮的 HTML 网页文件并保存到本地。支持标题、正文、列表、链接等",
            inputSchema={
                "type": "object",
                "properties": {
                    "title": {"type": "string", "description": "网页标题"},
                    "content": {"type": "string", "description": "网页正文内容（支持 Markdown 风格：标题用##、列表用-、加粗用**）"},
                    "filename": {"type": "string", "description": "文件名（不含路径，如 mypage.html），不传则自动生成"},
                    "theme": {
                        "type": "string",
                        "description": "主题风格",
                        "enum": ["light", "dark", "cute"],
                        "default": "light",
                    },
                },
                "required": ["title", "content"],
            },
        ),
        types.Tool(
            name="list_pages",
            description="列出已生成的所有 HTML 页面",
            inputSchema={
                "type": "object",
                "properties": {},
            },
        ),
    ]


_THEMES = {
    "light": {
        "bg": "#ffffff",
        "text": "#1a1a2e",
        "accent": "#4a6fa5",
        "card": "#f8f9fa",
        "border": "#e8e8e8",
    },
    "dark": {
        "bg": "#1a1a2e",
        "text": "#e0e0e0",
        "accent": "#7b9fd4",
        "card": "#16213e",
        "border": "#2a2a4a",
    },
    "cute": {
        "bg": "#fff5f5",
        "text": "#5a4a4a",
        "accent": "#ff8a8a",
        "card": "#ffffff",
        "border": "#ffd4d4",
    },
}


def _markdown_to_html(md_text: str) -> str:
    """简单的 Markdown → HTML 转换"""
    lines = md_text.split("\n")
    html_parts = []
    in_list = False
    
    for line in lines:
        stripped = line.strip()
        
        # 标题
        if stripped.startswith("### "):
            if in_list: html_parts.append("</ul>"); in_list = False
            html_parts.append(f"<h3>{stripped[4:]}</h3>")
        elif stripped.startswith("## "):
            if in_list: html_parts.append("</ul>"); in_list = False
            html_parts.append(f"<h2>{stripped[3:]}</h2>")
        elif stripped.startswith("# "):
            if in_list: html_parts.append("</ul>"); in_list = False
            html_parts.append(f"<h1>{stripped[2:]}</h1>")
        # 列表
        elif stripped.startswith("- ") or stripped.startswith("* "):
            if not in_list:
                html_parts.append("<ul>")
                in_list = True
            text = stripped[2:]
            html_parts.append(f"<li>{text}</li>")
        elif stripped.startswith("1. "):
            if not in_list:
                html_parts.append("<ol>")
                in_list = True
            html_parts.append(f"<li>{stripped[3:]}</li>")
        # 空行
        elif not stripped:
            if in_list: html_parts.append("</ul>"); in_list = False
            html_parts.append("<br>")
        # 段落
        else:
            if in_list: html_parts.append("</ul>"); in_list = False
            # 加粗
            text = stripped.replace("**", "<strong>", 1).replace("**", "</strong>", 1) if stripped.count("**") >= 2 else stripped
            html_parts.append(f"<p>{text}</p>")
    
    if in_list:
        html_parts.append("</ul>")
    
    return "\n".join(html_parts)


def _generate_html(title: str, content_html: str, theme_name: str) -> str:
    """生成完整 HTML 页面"""
    theme = _THEMES.get(theme_name, _THEMES["light"])
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    
    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            background: {theme['bg']};
            color: {theme['text']};
            line-height: 1.8;
            padding: 40px 20px;
        }}
        .container {{ max-width: 800px; margin: 0 auto; }}
        .header {{
            text-align: center;
            padding: 40px 0;
            border-bottom: 2px solid {theme['border']};
            margin-bottom: 30px;
        }}
        .header h1 {{ font-size: 2em; color: {theme['accent']}; margin-bottom: 10px; }}
        .header .date {{ color: #999; font-size: 0.9em; }}
        .content {{ padding: 20px 0; }}
        .content h2 {{ color: {theme['accent']}; margin: 25px 0 10px; font-size: 1.4em; }}
        .content h3 {{ color: {theme['text']}; margin: 20px 0 8px; font-size: 1.1em; }}
        .content p {{ margin: 10px 0; }}
        .content ul, .content ol {{ padding-left: 25px; margin: 10px 0; }}
        .content li {{ margin: 5px 0; }}
        .content strong {{ color: {theme['accent']}; }}
        .footer {{
            text-align: center;
            padding: 30px 0;
            color: #aaa;
            font-size: 0.85em;
            border-top: 1px solid {theme['border']};
            margin-top: 40px;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>{title}</h1>
            <div class="date">生成于 {now}</div>
        </div>
        <div class="content">
            {content_html}
        </div>
        <div class="footer">
            <p>由 芙芙助手 · MCP HTML Builder 生成</p>
        </div>
    </div>
</body>
</html>"""


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[types.TextContent]:
    if name == "create_html":
        title = arguments.get("title", "无标题")
        content = arguments.get("content", "")
        filename = arguments.get("filename", "")
        theme = arguments.get("theme", "light")
        
        if theme not in _THEMES:
            theme = "light"
        
        # 生成文件名
        if not filename:
            safe_title = "".join(c if c.isalnum() or c in " _-" else "_" for c in title)[:30]
            filename = f"{safe_title}.html"
        if not filename.endswith(".html"):
            filename += ".html"
        
        # 转换内容
        content_html = _markdown_to_html(content)
        full_html = _generate_html(title, content_html, theme)
        
        # 保存文件
        output_path = OUTPUT_DIR / filename
        output_path.write_text(full_html, encoding="utf-8")
        
        return [types.TextContent(
            type="text",
            text=f"✅ 网页已生成！\n📄 文件: {output_path}\n🌐 标题: {title}\n🎨 主题: {theme}\n💾 大小: {len(full_html)} 字节\n\n可在浏览器中打开查看。"
        )]
    
    elif name == "list_pages":
        files = sorted(OUTPUT_DIR.glob("*.html"))
        if not files:
            return [types.TextContent(type="text", text="📂 还没有生成过网页哦，试试用 create_html 创建一个吧！")]
        
        lines = ["📂 已生成的 HTML 页面：\n"]
        for f in files:
            size = f.stat().st_size
            mtime = datetime.fromtimestamp(f.stat().st_mtime).strftime("%m-%d %H:%M")
            lines.append(f"  • {f.name}  ({size} bytes, {mtime})")
        lines.append(f"\n共 {len(files)} 个文件，保存在: {OUTPUT_DIR}")
        
        return [types.TextContent(type="text", text="\n".join(lines))]
    
    raise ValueError(f"未知工具: {name}")


async def main():
    caps = ServerCapabilities(tools=ToolsCapability(listChanged=False))
    async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            InitializationOptions(
                server_name="html-builder-server",
                server_version="1.0.0",
                capabilities=caps,
            ),
        )


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
