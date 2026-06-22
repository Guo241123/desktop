"""tools/__init__.py — 工具自动注册

自动扫描 tools/ 目录下所有 .py 文件，收集 @tool 装饰的函数，
上层只需 `from tools import all_tools` 即可使用全部工具。
"""

import importlib
from pathlib import Path
from langchain_core.tools import BaseTool


def discover_tools() -> list[BaseTool]:
    """自动发现 tools/ 下所有 @tool 装饰的函数"""
    discovered: list[BaseTool] = []
    package_dir = Path(__file__).parent

    for file_path in sorted(package_dir.glob("*.py")):
        if file_path.stem == "__init__":
            continue
        module_name = f"tools.{file_path.stem}"
        try:
            module = importlib.import_module(module_name)
        except Exception as e:
            print(f"[tools] 加载 {module_name} 失败: {e}")
            continue

        for attr_name in dir(module):
            obj = getattr(module, attr_name, None)
            if isinstance(obj, BaseTool):
                discovered.append(obj)

    return discovered


# ── 导出 ──────────────────────────────────────────────────────
all_tools: list[BaseTool] = discover_tools()
