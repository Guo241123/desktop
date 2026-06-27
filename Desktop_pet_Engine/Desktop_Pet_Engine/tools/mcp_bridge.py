"""tools/mcp_bridge.py — MCP 标准协议工具桥接

将 MCP 标准服务器暴露的工具注册为 LangChain @tool，让宠物 Agent
可以直接使用 MCP 生态中的任何 skill。

配置方式：
  在 data/mcp_servers.json 中定义 MCP 服务器列表，支持三种传输方式：
  - stdio: 本地子进程 (command + args)
  - streamable-http: HTTP 远程服务
  - sse: Server-Sent Events 远程服务

用法：
  from tools.mcp_bridge import discover_mcp_tools
  mcp_tools = discover_mcp_tools()  # 返回 list[BaseTool]
"""

import asyncio
import json
import logging
import os
from pathlib import Path
from typing import Any

from langchain_core.tools import BaseTool, StructuredTool
from pydantic import BaseModel, Field, create_model

from config import get_env
from config.paths import DATA_DIR

logger = logging.getLogger(__name__)

# ── 配置 ──────────────────────────────────────────────────────
MCP_CONFIG_PATH = Path(get_env("MCP_SERVERS_PATH", str(DATA_DIR / "mcp_servers.json")))

# 全局缓存
_mcp_tools: list[BaseTool] | None = None
_mcp_server_configs: list[dict] | None = None


# ═══════════════════════════════════════════════════════════════
# 配置加载
# ═══════════════════════════════════════════════════════════════

def load_mcp_config() -> list[dict]:
    """加载 MCP 服务器配置列表"""
    global _mcp_server_configs
    if _mcp_server_configs is not None:
        return _mcp_server_configs

    if not MCP_CONFIG_PATH.exists():
        logger.info("MCP 配置文件不存在: %s（跳过，无 MCP 工具）", MCP_CONFIG_PATH)
        _mcp_server_configs = []
        return _mcp_server_configs

    try:
        with open(MCP_CONFIG_PATH, encoding="utf-8") as f:
            config = json.load(f)
        servers = config.get("servers", [])
        # 过滤掉注释示例（仅保留有实际命令或 url 的条目）
        active_servers = [
            s for s in servers
            if s.get("command") or s.get("url")
        ]
        logger.info("MCP 配置加载: 共 %d 个服务器（%d 有效）", len(servers), len(active_servers))
        _mcp_server_configs = active_servers
        return active_servers
    except Exception as e:
        logger.warning("加载 MCP 配置失败: %s", e)
        _mcp_server_configs = []
        return _mcp_server_configs


def _resolve_env(value: dict[str, str] | None) -> dict[str, str] | None:
    """解析值中的 ${VAR_NAME} 占位符（使用 get_env 兼容 .env 文件）"""
    import re
    if not value:
        return None
    resolved = {}
    for k, v in value.items():
        resolved[k] = re.sub(r'\$\{(\w+)\}', lambda m: get_env(m.group(1), m.group(0)), v)
    return resolved or None


# ═══════════════════════════════════════════════════════════════
# JSON Schema → Pydantic Model 转换
# ═══════════════════════════════════════════════════════════════

_TYPE_MAP = {
    "string": str,
    "integer": int,
    "number": float,
    "boolean": bool,
    "array": list,
    "object": dict,
}


def _json_schema_to_pydantic(schema: dict, model_name: str = "MCPToolArgs") -> type[BaseModel]:
    """将 JSON Schema 转为 Pydantic 模型，用于 StructuredTool 的 args_schema"""
    properties = schema.get("properties", {})
    required_set = set(schema.get("required", []))

    fields: dict[str, tuple[type, Any]] = {}
    for name, prop in properties.items():
        json_type = prop.get("type", "string")
        py_type = _TYPE_MAP.get(json_type, str)
        description = prop.get("description", "")

        # 提取 schema 中的默认值
        schema_default = prop.get("default")
        
        if name in required_set:
            # 必填字段：无默认值
            fields[name] = (py_type, Field(default=..., description=description))
        elif schema_default is not None:
            # 可选字段但有默认值：使用该默认值
            fields[name] = (py_type, Field(default=schema_default, description=description))
        else:
            # 纯可选字段：允许 None
            fields[name] = (py_type | None, Field(default=None, description=description))

    return create_model(model_name, **fields)


# ═══════════════════════════════════════════════════════════════
# MCP 工具调用（异步核心）
# ═══════════════════════════════════════════════════════════════

async def _call_mcp_tool_async(server_cfg: dict, tool_name: str, arguments: dict) -> str:
    """异步调用 MCP 工具（每次调用建立新连接，避免会话管理问题）"""
    from mcp import ClientSession
    from mcp.client.stdio import stdio_client, StdioServerParameters
    from mcp.client.sse import sse_client
    from mcp.client.streamable_http import streamablehttp_client

    transport = server_cfg.get("transport", "stdio")

    try:
        if transport == "stdio":
            params = StdioServerParameters(
                command=server_cfg["command"],
                args=server_cfg.get("args", []),
                env=_resolve_env(server_cfg.get("env")),
            )
            async with stdio_client(params) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    result = await session.call_tool(tool_name, arguments=arguments)
                    return _format_mcp_result(result)

        elif transport == "streamable-http":
            async with streamablehttp_client(
                url=server_cfg["url"],
                headers=_resolve_env(server_cfg.get("headers")),
            ) as (read, write, *_):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    result = await session.call_tool(tool_name, arguments=arguments)
                    return _format_mcp_result(result)

        elif transport == "sse":
            async with sse_client(
                url=server_cfg["url"],
                headers=_resolve_env(server_cfg.get("headers")),
            ) as (read, write, *_):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    result = await session.call_tool(tool_name, arguments=arguments)
                    return _format_mcp_result(result)

        else:
            return f"不支持的 MCP 传输方式: {transport}（支持: stdio, streamable-http, sse）"

    except Exception as e:
        logger.error("MCP 调用 %s/%s 失败: %s", server_cfg.get("name", "?"), tool_name, e)
        return f"MCP 工具 [{server_cfg.get('name', '?')}/{tool_name}] 调用失败: {e}"


def _format_mcp_result(result) -> str:
    """将 MCP CallToolResult 格式化为文本"""
    if hasattr(result, "content") and result.content:
        parts = []
        for item in result.content:
            if hasattr(item, "type"):
                if item.type == "text":
                    parts.append(getattr(item, "text", ""))
                elif item.type == "image":
                    mime = getattr(item, "mimeType", "image/unknown")
                    data = getattr(item, "data", "")
                    parts.append(f"[图片: {mime} ({len(data)} 字节)]")
                elif item.type == "resource":
                    parts.append(f"[资源: {getattr(item, 'uri', '?')}]")
                else:
                    parts.append(str(item))
            else:
                parts.append(str(item))
        text = "\n".join(parts)
    else:
        text = str(result)

    # 检查是否错误
    if hasattr(result, "isError") and result.isError:
        text = f"[MCP 错误] {text}"

    return text


# ═══════════════════════════════════════════════════════════════
# 异步兼容辅助
# ═══════════════════════════════════════════════════════════════

def _run_async(coro):
    """安全运行异步协程，兼容 uvicorn 下已有运行中事件循环的情况"""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        # 没有运行中的事件循环 → 直接 run
        return asyncio.run(coro)

    # 已有运行中事件循环 → 用 run_coroutine_threadsafe
    import concurrent.futures
    import threading

    result: list = []
    exception: list = []

    def _run():
        try:
            # 注意：asyncio.run 会自动创建新事件循环并关闭，比手动 new_event_loop 更安全
            r = asyncio.run(coro)
            result.append(r)
        except BaseException as e:
            import traceback
            traceback.print_exc()
            exception.append(e)

    t = threading.Thread(target=_run, daemon=True)
    t.start()
    t.join(timeout=120)

    if exception:
        raise exception[0]
    return result[0]


# ═══════════════════════════════════════════════════════════════
# 工具发现与包装
# ═══════════════════════════════════════════════════════════════

async def _discover_server_tools(server_cfg: dict) -> list:
    """获取单个 MCP 服务器的工具列表"""
    from mcp import ClientSession
    from mcp.client.stdio import stdio_client, StdioServerParameters
    from mcp.client.sse import sse_client
    from mcp.client.streamable_http import streamablehttp_client

    transport = server_cfg.get("transport", "stdio")

    try:
        if transport == "stdio":
            params = StdioServerParameters(
                command=server_cfg["command"],
                args=server_cfg.get("args", []),
                env=_resolve_env(server_cfg.get("env")),
            )
            async with stdio_client(params) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    result = await session.list_tools()
                    return result.tools

        elif transport == "streamable-http":
            async with streamablehttp_client(
                url=server_cfg["url"],
                headers=_resolve_env(server_cfg.get("headers")),
            ) as (read, write, *_):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    result = await session.list_tools()
                    return result.tools

        elif transport == "sse":
            async with sse_client(
                url=server_cfg["url"],
                headers=_resolve_env(server_cfg.get("headers")),
            ) as (read, write, *_):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    result = await session.list_tools()
                    return result.tools

        else:
            logger.warning("不支持的传输方式: %s", transport)
            return []

    except Exception as e:
        import traceback
        logger.warning("发现 MCP 服务器 '%s' 工具失败: %s\n%s", server_cfg.get("name", "?"), e, traceback.format_exc())
        return []


def _create_langchain_tool(server_cfg: dict, mcp_tool) -> BaseTool:
    """将单个 MCP Tool 包装为 LangChain StructuredTool"""
    server_name = server_cfg["name"]
    tool_name = mcp_tool.name
    tool_desc = mcp_tool.description or f"MCP 工具 ({server_name}/{tool_name})"

    # 包装函数：同步外壳 + 异步内核
    def tool_func(**kwargs: Any) -> str:
        try:
            # 过滤掉 None 值，避免 MCP 服务端 schema 校验失败
            clean_args = {k: v for k, v in kwargs.items() if v is not None}
            return _run_async(_call_mcp_tool_async(server_cfg, tool_name, clean_args))
        except Exception as e:
            logger.error("MCP 工具 %s/%s 执行异常: %s", server_name, tool_name, e)
            return f"MCP 工具执行失败: {e}"

    # 用工具名做函数名（LangChain 用函数名作为 tool name）
    tool_func.__name__ = tool_name
    tool_func.__doc__ = tool_desc

    # 构建 Pydantic args schema
    input_schema = mcp_tool.inputSchema or {"type": "object", "properties": {}}
    try:
        args_schema = _json_schema_to_pydantic(input_schema, model_name=f"{server_name}_{tool_name}_args")
    except Exception as e:
        logger.warning("为 %s/%s 生成 schema 失败: %s，使用兜底 schema", server_name, tool_name, e)
        args_schema = None

    return StructuredTool(
        name=tool_name,
        description=tool_desc,
        args_schema=args_schema,
        func=tool_func,
    )


def discover_mcp_tools() -> list[BaseTool]:
    """发现所有 MCP 服务器提供的工具并包装为 LangChain 工具

    首次调用连接所有 MCP 服务器获取工具列表，结果缓存。
    后的调用直接返回缓存列表。
    """
    global _mcp_tools
    if _mcp_tools is not None:
        return _mcp_tools

    servers = load_mcp_config()
    if not servers:
        _mcp_tools = []
        return _mcp_tools

    discovered: list[BaseTool] = []

    for server_cfg in servers:
        name = server_cfg.get("name", "unknown")
        try:
            mcp_tools = _run_async(_discover_server_tools(server_cfg))
            for mt in mcp_tools:
                langchain_tool = _create_langchain_tool(server_cfg, mt)
                discovered.append(langchain_tool)
                logger.info("✅ 注册 MCP 工具: %s/%s — %s", name, mt.name, mt.description or "")
        except Exception as e:
            logger.warning("跳过 MCP 服务器 '%s': %s", name, e)

    _mcp_tools = discovered
    logger.info("MCP 工具发现完成: 共 %d 个工具", len(discovered))
    return discovered


def clear_cache():
    """清除 MCP 工具缓存（重新发现）"""
    global _mcp_tools, _mcp_server_configs
    _mcp_tools = None
    _mcp_server_configs = None
