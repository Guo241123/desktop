"""mcp_skill_server MCP 服务入口

用法:
    python -m mcp_skill_server          # 通过 stdio 运行 MCP 服务
"""
import asyncio
from .server import main

asyncio.run(main())
