import os
import requests
from langchain_core.tools import tool
from tavily import TavilyClient

# 密钥配置
os.environ["TAVILY_API_KEY"] = "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"
DEFAULT_IMG_SAVE_DIR = "./search_img"  # 默认图片保存路径
os.makedirs(DEFAULT_IMG_SAVE_DIR, exist_ok=True)

@tool
def web_search(query: str, save_path: str = None) -> str:
    """
    联网实时搜索工具，可获取文字+配图链接，用于查询新闻、资料、配图。
    自动下载 jpg / jpeg / png 图片到指定路径（不指定则用默认）。
    参数:
        query: 搜索关键词/问题
        save_path: 图片保存目录（可选，不传则使用默认路径 ./search_img）
    """
    try:
        # 1. 处理保存路径（没有就用默认）
        if not save_path:
            save_path = DEFAULT_IMG_SAVE_DIR
        os.makedirs(save_path, exist_ok=True)

        # 2. 执行搜索
        client = TavilyClient()
        res = client.search(
            query=query,
            max_results=3,
            include_answer=True,
            include_raw_content=True,
            include_images=True
        )

        text = f"搜索总结：{res.get('answer','无结果')}\n"

        # 3. 图片处理：只下载 jpg / jpeg / png
        img_list = res.get("images", [])[:3]
        if img_list:
            text += "\n【配图链接】\n"
            allow_suffix = (".jpg", ".jpeg", ".png")

            for idx, url in enumerate(img_list):
                # 只保留合法图片格式
                if not url.lower().endswith(allow_suffix):
                    continue

                text += f"{idx+1}: {url}\n"

                try:
                    # 下载图片
                    img_data = requests.get(url, timeout=8).content
                    # 文件名：关键词前8位 + 序号 + 后缀
                    suffix = url.split(".")[-1].lower()
                    suffix = suffix if suffix in ["jpg", "jpeg", "png"] else "jpg"
                    img_name = f"{query[:8]}_{idx}.{suffix}"
                    img_path = os.path.join(save_path, img_name)

                    with open(img_path, "wb") as f:
                        f.write(img_data)

                except Exception as e:
                    continue

        # 4. 搜索来源内容
        for i, item in enumerate(res.get("results", [])):
            text += f"\n【来源{i+1}】{item.get('title', '无标题')}\n"
            text += item.get('raw_content', '')[:500] + "\n"

        return text

    except Exception as e:
        return f"搜索失败: {str(e)}"
