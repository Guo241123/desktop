"""tools/__init__.py — 工具自动注册

自动扫描 tools/ 目录下所有 .py 文件，收集 @tool 装饰的函数，
并集成 MCP 标准协议工具（如配置了 MCP 服务器）。
上层只需 `from tools import all_tools` 即可使用全部工具。
"""

import importlib
import logging
from pathlib import Path
from langchain_core.tools import BaseTool

logger = logging.getLogger(__name__)


def discover_tools() -> list[BaseTool]:
    """自动发现 tools/ 下所有 @tool 装饰的函数 + MCP 工具"""
    discovered: list[BaseTool] = []
    package_dir = Path(__file__).parent

    for file_path in sorted(package_dir.glob("*.py")):
        if file_path.stem == "__init__":
            continue
        if file_path.stem.startswith("_"):
            continue
        if file_path.stem == "mcp_bridge":
            continue  # MCP 工具单独处理，避免重复导入
        module_name = f"tools.{file_path.stem}"
        try:
            module = importlib.import_module(module_name)
        except Exception as e:
            logger.warning("加载 %s 失败: %s", module_name, e)
            continue

        for attr_name in dir(module):
            obj = getattr(module, attr_name, None)
            if isinstance(obj, BaseTool):
                discovered.append(obj)

    # ── 集成 MCP 标准协议工具 ──────────────────────────────
    try:
        from tools.mcp_bridge import discover_mcp_tools
        mcp_tools = discover_mcp_tools()
        discovered.extend(mcp_tools)
        if mcp_tools:
            logger.info("已集成 %d 个 MCP 工具", len(mcp_tools))
    except ImportError:
        pass  # mcp 依赖未安装时静默跳过
    except Exception as e:
        logger.warning("MCP 工具加载异常: %s", e)

    return discovered


# ── 导出 ──────────────────────────────────────────────────────
all_tools: list[BaseTool] = discover_tools()
