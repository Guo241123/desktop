"""联网搜索工具（Tavily API）

提供 web_search 工具给 Agent 使用：联网搜索 + 自动下载图片。
"""

import os
import requests
from langchain_core.tools import tool
from tavily import TavilyClient
from config import get_env, SEARCH_IMG_DIR

# 从统一的配置读取 Tavily API Key
os.environ["TAVILY_API_KEY"] = get_env("TAVILYWEB_KEY")

DEFAULT_IMG_SAVE_DIR = str(SEARCH_IMG_DIR)
os.makedirs(DEFAULT_IMG_SAVE_DIR, exist_ok=True)


@tool
def web_search(query: str, save_path: str = None) -> str:
    """
    联网实时搜索工具，可获取文字+配图链接，用于查询新闻、资料、配图。
    自动下载 jpg / jpeg / png 图片到指定路径（不指定则用默认）。
    参数:
        query: 搜索关键词/问题
        save_path: 图片保存目录（可选，不传则使用默认路径）
    """
    try:
        if not save_path:
            save_path = DEFAULT_IMG_SAVE_DIR
        os.makedirs(save_path, exist_ok=True)

        client = TavilyClient()
        res = client.search(
            query=query,
            max_results=3,
            include_answer=True,
            include_raw_content=True,
            include_images=True
        )

        text = f"搜索总结：{res.get('answer', '无结果')}\n"

        img_list = res.get("images", [])[:3]
        if img_list:
            text += "\n【配图链接】\n"
            allow_suffix = (".jpg", ".jpeg", ".png")

            for idx, url in enumerate(img_list):
                if not url.lower().endswith(allow_suffix):
                    continue
                text += f"{idx + 1}: {url}\n"
                try:
                    img_data = requests.get(url, timeout=8).content
                    suffix = url.split(".")[-1].lower()
                    suffix = suffix if suffix in ["jpg", "jpeg", "png"] else "jpg"
                    img_name = f"{query[:8]}_{idx}.{suffix}"
                    img_path = os.path.join(save_path, img_name)
                    with open(img_path, "wb") as f:
                        f.write(img_data)
                except Exception:
                    continue

        for i, item in enumerate(res.get("results", [])):
            text += f"\n【来源{i + 1}】{item.get('title', '无标题')}\n"
            text += item.get('raw_content', '')[:500] + "\n"

        return text

    except Exception as e:
        return f"搜索失败: {str(e)}"
