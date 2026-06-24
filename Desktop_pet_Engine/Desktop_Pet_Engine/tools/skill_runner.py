"""tools/skill_runner.py — 通用 Skill 运行器

让桌面宠物 Agent 可以像 Codex/Cursor 一样，
直接加载和执行 GitHub 上下载的 skill。

标准 skill 结构（推荐）：
  skills/{skill_name}/SKILL.md

也支持单文件：
  skills/{skill_name}.md
  skills/{skill_name}.py
"""

import importlib.util
import logging
from pathlib import Path
from langchain_core.tools import tool
from config.paths import ROOT_DIR

logger = logging.getLogger(__name__)

# Skill 存放目录（与 tools/ 同级）
SKILLS_DIR = ROOT_DIR / "skills"
SKILLS_DIR.mkdir(parents=True, exist_ok=True)


def _find_entry_file(skill_dir: Path) -> Path | None:
    """在 skill 目录中查找入口文件，优先级：SKILL.md > skill.md > main.py > run.py"""
    for candidate in ["SKILL.md", "skill.md", "main.py", "run.py"]:
        fp = skill_dir / candidate
        if fp.exists():
            return fp
    return None


def _resolve_skill_path(skill_name: str) -> Path | None:
    """按优先级查找 skill"""
    p = Path(skill_name)

    # 1. 绝对路径
    if p.is_absolute() and p.exists():
        return p

    base = SKILLS_DIR / skill_name

    # 2. skills/{name}/ 目录（标准 skill 文件夹）
    if base.is_dir():
        return base

    # 3. skills/{name}.md / skills/{name}.py（单文件）
    for ext in (".md", ".py"):
        fp = base.with_suffix(ext)
        if fp.exists():
            return fp

    return None


def _list_skills() -> list[str]:
    """列出所有可用 skill 名称"""
    names: set[str] = set()
    for entry in SKILLS_DIR.iterdir():
        if entry.is_dir():
            names.add(entry.name)
        elif entry.suffix in (".md", ".py"):
            names.add(entry.stem)
    return sorted(names)


def _run_md_skill(filepath: Path, params: str) -> str:
    """把 .md skill 交给 Pro LLM 执行"""
    content = filepath.read_text(encoding="utf-8")
    prompt = f"""请按照以下 skill 指令完成任务。

===== SKILL 指令 =====
{content}
=====================

任务参数：{params if params else "（无额外参数，按 skill 默认行为执行）"}

请严格遵循 skill 中的指令执行，完成后输出结果。"""
    from tools.delegate import delegate_task
    return delegate_task.invoke({"task_description": prompt})


def _run_py_skill(filepath: Path, function: str, args: str) -> str:
    """把 .py skill 作为模块导入并调用"""
    if not filepath.is_relative_to(SKILLS_DIR):
        return f"安全限制：只能运行 {SKILLS_DIR} 目录下的脚本"

    logger.info("加载 skill 脚本: %s", filepath)
    try:
        spec = importlib.util.spec_from_file_location("_skill_runner", filepath)
        if spec is None or spec.loader is None:
            return f"无法加载脚本: {filepath.name}"
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)

        func = getattr(mod, function, None)
        if func is None:
            available = [n for n in dir(mod) if not n.startswith("_")]
            return f"脚本中没有找到函数 '{function}'。可用函数: {', '.join(available)}"

        if not callable(func):
            return f"'{function}' 不是可调用的函数"

        result = func(args) if args else func()
        return str(result)
    except Exception as e:
        logger.exception("执行 skill 脚本失败")
        return f"执行失败: {e}"


@tool
def run_skill(skill_name: str, function: str = "main", params: str = "") -> str:
    """运行一个 skill（从 skills/ 目录加载）。

    skills/ 下每个 skill 是一个文件夹，里面放 SKILL.md 或 .py 文件。
    从 GitHub 下载的标准 skill 直接解压到 skills/ 目录就能用。

    Args:
        skill_name: skill 文件夹名或文件名（不带路径），
                    例如 "weather" 会找 skills/weather/SKILL.md
        function: 当 skill 是 .py 时，要调用的函数名（默认 main）
        params: 传递给 skill 的参数
    """
    resolved = _resolve_skill_path(skill_name)
    if resolved is None:
        available = _list_skills()
        hint = f"可用的 skills: {', '.join(available)}" if available else "skills 目录为空"
        return f"未找到 skill '{skill_name}'。{hint}"

    logger.info("运行 skill: %s → %s", skill_name, resolved)

    if resolved.is_dir():
        entry = _find_entry_file(resolved)
        if entry is None:
            files = [f.name for f in resolved.iterdir() if f.is_file()]
            return (f"skill 目录 '{skill_name}' 中没有找到 SKILL.md 或 main.py。"
                    f"目录内容: {', '.join(files[:10])}")
        resolved = entry

    if resolved.suffix == ".md":
        return _run_md_skill(resolved, params)
    elif resolved.suffix == ".py":
        return _run_py_skill(resolved, function, params)
    else:
        return f"不支持的文件格式: {resolved.suffix}"
