"""mcp_skill_server/server.py — MCP Skill 管理器核心

通过 MCP 标准协议暴露 4 个工具，让宠物 Agent 可以直接：
  • install_skill(url)    — 从 GitHub 安装 skill 包
  • list_skills()         — 查看已安装技能
  • uninstall_skill(name) — 卸载技能
  • get_skill_readme(name) — 读取 SKILL.md 全文（给 Pro 子代理用）
"""

import asyncio
import json
import logging
import re
import shutil
import subprocess
import sys
from pathlib import Path

from mcp.server.fastmcp import FastMCP

logger = logging.getLogger(__name__)

# ── 路径配置 ──────────────────────────────────────────────────
# 技能包存放在项目根 data/skills/ 下
SERVER_DIR = Path(__file__).resolve().parent                # mcp_skill_server/
ENGINE_DIR = SERVER_DIR.parent                               # Desktop_Pet_Engine/
PROJECT_DIR = ENGINE_DIR.parent                              # Desktop_pet_Engine/
SKILLS_DIR = ENGINE_DIR / "skills"                           # Desktop_Pet_Engine/skills/
REGISTRY_PATH = SKILLS_DIR / "registry.json"

SKILLS_DIR.mkdir(parents=True, exist_ok=True)

# ── MCP 服务器 ────────────────────────────────────────────────
mcp = FastMCP(
    name="Skill Manager",
    instructions="管理 AI 技能包（Skill Package）：安装、卸载、查询、读取说明书。",
)


# ══════════════════════════════════════════════════════════════
# 内部工具函数
# ══════════════════════════════════════════════════════════════

def _load_registry() -> dict:
    """读取已安装技能清单"""
    if not REGISTRY_PATH.exists():
        return {}
    try:
        return json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def _save_registry(registry: dict):
    """保存技能清单"""
    REGISTRY_PATH.write_text(
        json.dumps(registry, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _parse_skill_frontmatter(skill_dir: Path) -> dict | None:
    """解析 SKILL.md 的 YAML frontmatter，提取 name 和 description"""
    skill_md = skill_dir / "SKILL.md"
    if not skill_md.exists():
        return None

    content = skill_md.read_text(encoding="utf-8")
    # 匹配 --- ... --- 格式的 frontmatter
    m = re.match(r"^---\s*\n(.*?)\n(?:---|\.\.\.)", content, re.DOTALL)
    if not m:
        return None

    meta = {}
    for line in m.group(1).splitlines():
        if ":" in line:
            key, _, val = line.partition(":")
            meta[key.strip()] = val.strip()
    return {
        "name": meta.get("name", skill_dir.name),
        "description": meta.get("description", ""),
    }


def _extract_repo_slug(url: str) -> str:
    """从 GitHub URL 提取 owner/name"""
    # https://github.com/user/repo
    # https://github.com/user/repo.git
    # git@github.com:user/repo.git
    m = re.search(r"github\.com[:/]([^/]+/[^/]+?)(?:\.git)?$", url)
    if m:
        return m.group(1).rstrip("/")
    raise ValueError(f"无法解析 GitHub 仓库地址: {url}")


# ══════════════════════════════════════════════════════════════
# MCP 工具
# ══════════════════════════════════════════════════════════════

@mcp.tool(
    name="install_skill",
    description="从 GitHub 安装 AI 技能包。提供 GitHub 仓库 URL，自动 git clone 并注册。",
)
def install_skill(url: str) -> str:
    """从 GitHub 安装一个 AI 技能包"""
    try:
        repo_slug = _extract_repo_slug(url)
    except ValueError as e:
        return f"❌ {e}"

    skill_name = repo_slug.split("/")[-1]
    skill_dir = SKILLS_DIR / skill_name

    if skill_dir.exists():
        return (
            f"⚠️ 技能 '{skill_name}' 已经安装在 {skill_dir}。\n"
            f"如需重新安装，请先 uninstall_skill('{skill_name}') 再重试。"
        )

    # ── git clone ──
    clone_url = f"https://github.com/{repo_slug}.git"
    try:
        result = subprocess.run(
            ["git", "clone", clone_url, str(skill_dir)],
            capture_output=True, text=True, timeout=120,
        )
        if result.returncode != 0:
            return f"❌ git clone 失败:\n{result.stderr[:1000]}"
    except FileNotFoundError:
        return "❌ 未找到 git 命令。请确保已安装 Git（https://git-scm.com）并加入 PATH。"
    except subprocess.TimeoutExpired:
        return "❌ git clone 超时（120 秒）。请检查网络连接或仓库大小。"

    # ── 验证 frontmatter ──
    meta = _parse_skill_frontmatter(skill_dir)
    if meta is None:
        # 没有根 SKILL.md → 检查是否是 multi-skill 包（skills/ 下含多个子技能）
        sub_skills_dir = skill_dir / "skills"
        if sub_skills_dir.is_dir():
            sub_skills = [d for d in sub_skills_dir.iterdir() if d.is_dir() and (d / "SKILL.md").exists()]
            if sub_skills:
                registered = []
                for sub in sub_skills:
                    sm = _parse_skill_frontmatter(sub)
                    name = sm["name"] if sm else sub.name
                    desc = sm["description"] if sm else f"(来自 miniMax-AI/skills 的多技能包)"
                    skill_entry = {
                        "name": name,
                        "description": desc,
                        "source": url,
                        "path": str(sub.resolve()),
                        "repo": repo_slug,
                    }
                    registry = _load_registry()
                    registry[name] = skill_entry
                    _save_registry(registry)
                    registered.append(name)

                summary = "\n".join(f"  • **{n}**" for n in registered)
                return (
                    f"✅ 多技能包 **{skill_name}** 安装成功！共注册 {len(registered)} 个技能：\n\n"
                    f"{summary}\n\n"
                    f"📂 位置: {skill_dir.resolve()}\n\n"
                    f"可用命令：\n"
                    f"  • list_skills() — 查看所有已安装技能\n"
                    f"  • get_skill_readme('xxx') — 阅读某个技能的说明书"
                )

        # 真的没有 frontmatter
        meta = {"name": skill_name, "description": "(未找到标准 SKILL.md frontmatter)"}

    # ── 注册 ──
    registry = _load_registry()
    registry[meta["name"]] = {
        "name": meta["name"],
        "description": meta["description"],
        "source": url,
        "path": str(skill_dir.resolve()),
        "repo": repo_slug,
    }
    _save_registry(registry)

    return (
        f"✅ 技能 **{meta['name']}** 安装成功！\n\n"
        f"📖 名称: {meta['name']}\n"
        f"📝 说明: {meta['description']}\n"
        f"📂 位置: {skill_dir.resolve()}\n\n"
        f"可用命令：\n"
        f"  • list_skills() — 查看所有已安装技能\n"
        f"  • get_skill_readme('{meta['name']}') — 阅读完整说明书\n"
        f"  • uninstall_skill('{meta['name']}') — 卸载"
    )


@mcp.tool(
    name="list_skills",
    description="列出所有已安装的 AI 技能包",
)
def list_skills() -> str:
    """列出所有已安装技能"""
    registry = _load_registry()
    if not registry:
        return (
            "📭 还没有安装任何技能。\n"
            "使用 install_skill(url) 从 GitHub 安装，例如：\n"
            "  install_skill('https://github.com/archlizheng/frontend-slides-editable')"
        )

    lines = ["📦 **已安装技能（{n} 个）**\n".format(n=len(registry))]
    for skill in registry.values():
        lines.append(f"  • **{skill['name']}**: {skill['description']}")
    return "\n".join(lines)


@mcp.tool(
    name="uninstall_skill",
    description="卸载一个已安装的 AI 技能包",
)
def uninstall_skill(name: str) -> str:
    """卸载指定技能"""
    registry = _load_registry()
    if name not in registry:
        return f"⚠️ 未找到技能 '{name}'。使用 list_skills() 查看已安装的技能。"

    skill_info = registry[name]
    skill_path = Path(skill_info["path"])

    if skill_path.exists():
        shutil.rmtree(skill_path)

    del registry[name]
    _save_registry(registry)

    return f"🗑️ 技能 **{name}** 已卸载。"


@mcp.tool(
    name="get_skill_readme",
    description="读取已安装技能的 SKILL.md 完整说明书。返回内容可喂给 AI 模型作为指令。",
)
def get_skill_readme(name: str) -> str:
    """读取技能说明书全文"""
    registry = _load_registry()
    if name not in registry:
        return f"⚠️ 未找到技能 '{name}'。使用 list_skills() 查看已安装的技能。"

    skill_path = Path(registry[name]["path"])
    skill_md = skill_path / "SKILL.md"

    if not skill_md.exists():
        return f"⚠️ 技能 '{name}' 的 SKILL.md 文件不存在。"

    content = skill_md.read_text(encoding="utf-8")
    return content


# ══════════════════════════════════════════════════════════════
# 入口
# ══════════════════════════════════════════════════════════════

async def main():
    """通过 stdio 运行 MCP 服务器"""
    await mcp.run_stdio_async()


if __name__ == "__main__":
    asyncio.run(main())
