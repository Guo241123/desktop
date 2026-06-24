"""tools/skill_runner.py — 通用 Skill 运行器

让桌面宠物 Agent 可以像 Codex/Cursor 一样，
直接加载和执行 GitHub 上下载的 skill 文件。

支持格式：
  .md  — 读取内容后交给 LLM 理解和执行
  .py  — 作为 Python 模块导入并调用指定函数
  目录 — 自动查找 main.py 或 SKILL.md
"""

import importlib.util
import logging
from pathlib import Path
from langchain_core.tools import tool
from config.paths import DATA_DIR

logger = logging.getLogger(__name__)

# Skill 文件存放目录（data/skills/）
SKILLS_DIR = DATA_DIR / "skills"
SKILLS_DIR.mkdir(parents=True, exist_ok=True)

# 允许 .py skill 调用的内置函数白名单
_BUILTIN_ALLOW = {
    "print": print,
    "len": len,
    "str": str,
    "int": int,
    "float": float,
    "list": list,
    "dict": dict,
    "tuple": tuple,
    "range": range,
    "enumerate": enumerate,
    "zip": zip,
    "sorted": sorted,
    "reversed": reversed,
    "open": open,
    "Path": Path,
    "__import__": __import__,
}


def _resolve_skill_path(skill_name: str) -> Path | None:
    """按优先级查找 skill 文件/目录"""
    # 1. 传的是绝对路径
    p = Path(skill_name)
    if p.is_absolute() and p.exists():
        return p

    # 2. data/skills/{skill_name} 目录
    dir_path = SKILLS_DIR / skill_name
    if dir_path.is_dir():
        for candidate in ["main.py", "SKILL.md", "skill.md", "run.py"]:
            if (dir_path / candidate).exists():
                return dir_path / candidate
        return dir_path  # 返回目录本身，让调用方决定

    # 3. data/skills/{skill_name}.md
    md_path = SKILLS_DIR / f"{skill_name}.md"
    if md_path.exists():
        return md_path

    # 4. data/skills/{skill_name}.py
    py_path = SKILLS_DIR / f"{skill_name}.py"
    if py_path.exists():
        return py_path

    return None


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
    """运行一个 skill（从 data/skills/ 目录加载）。

    支持格式：
    - 目录（自动找 main.py / SKILL.md）
    - .md 文件（让 AI 理解并执行指令）
    - .py 文件（导入并调用指定函数）

    Args:
        skill_name: skill 的名称（不带后缀）或路径，
                    例如 "search" 会找 data/skills/search.md 或 data/skills/search/main.py
        function: 当 skill 是 .py 时，要调用的函数名（默认 main）
        params: 传递给 skill 的参数
    """
    resolved = _resolve_skill_path(skill_name)
    if resolved is None:
        available = [p.stem for p in SKILLS_DIR.iterdir() if p.suffix in (".md", ".py") or p.is_dir()]
        available.extend(p.stem for p in SKILLS_DIR.iterdir() if p.is_dir())
        available = sorted(set(available))
        hint = f"可用的 skills: {', '.join(available)}" if available else "skills 目录为空"
        return f"未找到 skill '{skill_name}'。{hint}"

    logger.info("运行 skill: %s → %s", skill_name, resolved)

    if resolved.suffix == ".md":
        return _run_md_skill(resolved, params)
    elif resolved.suffix == ".py":
        return _run_py_skill(resolved, function, params)
    elif resolved.is_dir():
        # 目录：递归查找
        for candidate in ["main.py", "run.py", "SKILL.md", "skill.md"]:
            fp = resolved / candidate
            if fp.exists():
                if fp.suffix == ".py":
                    return _run_py_skill(fp, function, params)
                else:
                    return _run_md_skill(fp, params)
        files = [f.name for f in resolved.iterdir() if f.is_file()]
        return f"skill 目录 '{skill_name}' 中没有找到 main.py / SKILL.md。目录内容: {', '.join(files[:10])}"
    else:
        return f"不支持的文件格式: {resolved.suffix}"
