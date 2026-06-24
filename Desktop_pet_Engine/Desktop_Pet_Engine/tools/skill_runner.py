"""tools/skill_runner.py — 通用 Skill 运行器

让桌面宠物 Agent 可以像 Codex/Cursor 一样，
直接加载和执行 GitHub 下载的标准 skill。

标准 skill 结构（ComposioHQ / wondelai 格式）：
  skills/{skill_name}/
    ├── SKILL.md          # 指令文件（必需）
    ├── main.py           # Python 实现（可选）
    ├── requirements.txt  # 依赖（可选）
    └── assets/           # 资源文件（可选）
"""

import importlib.util
import logging
import subprocess
import sys
from pathlib import Path
from langchain_core.tools import tool
from config.paths import ROOT_DIR

logger = logging.getLogger(__name__)

# Skill 存放目录（与 tools/ 同级）
SKILLS_DIR = ROOT_DIR / "skills"
SKILLS_DIR.mkdir(parents=True, exist_ok=True)


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

    # 3. skills/{name}.md / skills/{name}.py（单文件兼容）
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


def _get_skill_description(skill_dir: Path) -> str:
    """从 SKILL.md 取第一行描述（用于列表展示）"""
    for name in ("SKILL.md", "skill.md"):
        fp = skill_dir / name
        if fp.exists():
            for line in fp.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if line and not line.startswith("#") and not line.startswith("---"):
                    return line[:80]
    return ""


def _run_md_skill(skill_dir: Path, params: str) -> str:
    """运行一个标准 skill 文件夹

    处理策略：
    - 有 SKILL.md → 读取指令喂给 LLM 执行
    - 有 SKILL.md + main.py → 把两份内容都喂给 LLM，LLM 决定用哪个
    - 有 assets/ → 把目录结构也告知 LLM，LLM 按需使用
    """
    # 读取 SKILL.md
    md_path = skill_dir / "SKILL.md"
    if not md_path.exists():
        md_path = skill_dir / "skill.md"
    instructions = md_path.read_text(encoding="utf-8") if md_path.exists() else ""

    # 读取 main.py（如果有）
    py_path = skill_dir / "main.py"
    py_code = py_path.read_text(encoding="utf-8") if py_path.exists() else ""

    # 扫描目录结构
    dir_tree = []
    for child in sorted(skill_dir.iterdir()):
        if child.is_dir():
            files = [f.name for f in child.iterdir() if f.is_file()]
            dir_tree.append(f"  {child.name}/ ({', '.join(files)})")
        elif child.name not in ("SKILL.md", "skill.md", "main.py"):
            size = child.stat().st_size
            dir_tree.append(f"  {child.name} ({size} bytes)")
    dir_info = "\n".join(dir_tree) if dir_tree else "（无额外文件）"

    # 组装完整的 skill 上下文
    parts = [f"请按照以下 skill 指令完成任务。\n"]
    if instructions:
        parts.append(f"===== SKILL 指令 (SKILL.md) =====\n{instructions}\n")
    if py_code:
        parts.append(f"===== Python 实现 (main.py) =====\n```python\n{py_code}\n```\n"
                      "如果你需要运行 Python 代码，先用 execute_command 执行，不要自己假装运行。\n")
    parts.append(f"===== skill 目录文件 ====\n{dir_info}\n")
    parts.append(f"===== 任务参数 =====\n{params if params else '（无额外参数，按 skill 默认行为执行）'}\n")
    parts.append("请严格遵循 skill 中的指令执行，完成后输出结果。")

    prompt = "\n".join(parts)
    from tools.delegate import delegate_task
    return delegate_task.invoke({"task_description": prompt})


def _install_deps(skill_dir: Path) -> str:
    """安装 skill 的依赖（如果有 requirements.txt）"""
    req_path = skill_dir / "requirements.txt"
    if not req_path.exists():
        return ""
    logger.info("安装 skill 依赖: %s", req_path)
    try:
        result = subprocess.run(
            [sys.executable, "-m", "pip", "install", "-r", str(req_path)],
            capture_output=True, text=True, timeout=60,
        )
        if result.returncode == 0:
            return ""
        else:
            return f"依赖安装警告:\n{result.stderr[:500]}"
    except Exception as e:
        return f"依赖安装失败: {e}"


@tool
def run_skill(skill_name: str, params: str = "") -> str:
    """运行一个 skill（从 skills/ 目录加载）。

    从 GitHub 下载的标准 skill 直接解压到 skills/ 目录就能用。
    支持完整的 skill 文件夹（含 SKILL.md + main.py + assets）。

    Args:
        skill_name: skill 文件夹名，例如 "weather" 会找 skills/weather/
        params: 传递给 skill 的参数
    """
    resolved = _resolve_skill_path(skill_name)
    if resolved is None:
        available = _list_skills()
        if available:
            descs = []
            for name in available:
                d = _get_skill_description(SKILLS_DIR / name) if (SKILLS_DIR / name).is_dir() else ""
                descs.append(f"  {name}" + (f" — {d}" if d else ""))
            hint = "可用的 skills:\n" + "\n".join(descs)
        else:
            hint = "skills 目录为空"
        return f"未找到 skill '{skill_name}'。\n{hint}"

    logger.info("运行 skill: %s → %s", skill_name, resolved)

    # 单文件兼容
    if resolved.is_file():
        folder = resolved.parent
        if resolved.suffix == ".md":
            return _run_md_skill(folder, params)
        elif resolved.suffix == ".py":
            return _run_py_skill(resolved, "main", params)
        else:
            return f"不支持的文件格式: {resolved.suffix}"

    # 标准文件夹 skill
    dep_warn = _install_deps(resolved)
    result = _run_md_skill(resolved, params)
    if dep_warn:
        result = dep_warn + "\n\n" + result
    return result


# 也导出为独立的工具名方便 Agent 理解（run_skill 是主入口）
tools = [run_skill]
