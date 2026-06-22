"""命令行执行 & 沙盒工具

让 AI 智能体可以在本地执行命令行操作，
并在隔离的沙盒目录中安全地工作。
"""

import os
import subprocess
import logging
from pathlib import Path
from langchain.tools import tool
from config.paths import SANDBOX_DIR

logger = logging.getLogger(__name__)

# 命令执行超时（秒）
CMD_TIMEOUT = 30


@tool
def get_sandbox_path():
    """
    获取沙盒目录的路径。
    沙盒是一个隔离的工作目录，位于 data/sandbox/ 下，
    用于安全地存放临时文件、测试脚本等，不会影响系统文件。
    :return: 沙盒目录的绝对路径
    """
    SANDBOX_DIR.mkdir(parents=True, exist_ok=True)
    return str(SANDBOX_DIR.resolve())


@tool
def execute_command(command: str, work_dir: str = ""):
    """
    在本地电脑上执行命令行命令（PowerShell / cmd）。
    适合用来运行脚本、查看系统信息、编译代码等操作。
    默认在沙盒目录中执行，避免影响系统文件。
    注意：不要执行可能损坏系统的危险命令（如格式化、删除系统目录等）。
    :param command: 要执行的命令，例如 "dir"、"python --version"、"git status"
    :param work_dir: 工作目录（可选，留空则使用沙盒目录）
    :return: 命令的标准输出和标准错误
    """
    # 确定工作目录
    if work_dir and work_dir.strip():
        cwd = Path(work_dir.strip()).resolve()
        if not cwd.exists():
            return f"⚠️ 工作目录不存在: {work_dir}"
    else:
        SANDBOX_DIR.mkdir(parents=True, exist_ok=True)
        cwd = SANDBOX_DIR.resolve()

    # 安全检查：禁止的危险命令
    dangerous = ["format ", "mkfs", "dd if=", "rd /s /q c:", "rm -rf /", "rm -rf ~"]
    for d in dangerous:
        if d in command.lower():
            return f"⚠️ 命令被安全策略拦截：包含危险指令「{d}」"

    try:
        result = subprocess.run(
            command,
            shell=True,
            cwd=str(cwd),
            capture_output=True,
            text=True,
            timeout=CMD_TIMEOUT,
            encoding="utf-8",
            errors="replace",
        )

        output_parts = []
        if result.stdout:
            output_parts.append(f"【标准输出】\n{result.stdout.strip()}")
        if result.stderr:
            output_parts.append(f"【标准错误】\n{result.stderr.strip()}")
        if result.returncode != 0:
            output_parts.append(f"【退出码】{result.returncode}")

        output = "\n\n".join(output_parts) if output_parts else "(命令执行完毕，无输出)"

        # 输出太长时截断
        MAX_LEN = 4000
        if len(output) > MAX_LEN:
            output = output[:MAX_LEN] + f"\n\n...（输出过长，已截断至 {MAX_LEN} 字符）"

        return output

    except subprocess.TimeoutExpired:
        return f"⚠️ 命令执行超时（{CMD_TIMEOUT}秒），请简化操作或拆分成多条命令"
    except Exception as e:
        logger.exception("命令执行失败")
        return f"⚠️ 命令执行失败: {e}"
