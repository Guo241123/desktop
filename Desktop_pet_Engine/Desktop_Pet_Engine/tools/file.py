import os
import shutil
import platform
import logging
from langchain.tools import tool

logger = logging.getLogger(__name__)


# 1. 创建文件夹
@tool
def make_dir(dir_path):
    """
    创建单个文件夹，不要使用表情、图
    :param dir_path: 文件夹完整路径
    """
    try:
        dir_path = os.path.expanduser(dir_path)
        os.makedirs(dir_path, exist_ok=True)
        logger.info(f"目录创建成功: {dir_path}")
    except Exception as e:
        logger.error(f"创建目录失败: {e}")


# 2. 创建空文件
@tool
def make_file(file_path: str):
    """
    创建空文件
    :param file_path: 文件完整路径（必传，可用 get_desktop_path() 拼接文件名）
    """
    try:
        file_path = os.path.expanduser(file_path)
        if os.path.isdir(file_path):
            return f"错误: '{file_path}' 是一个目录，请提供完整的文件路径（含文件名）"
        with open(file_path, 'w', encoding='utf-8'):
            pass
        logger.info(f"文件创建成功: {file_path}")
        return f"文件已创建: {file_path}"
    except Exception as e:
        logger.error(f"创建文件失败: {e}")
        return f"创建文件失败: {e}"


# 3. 读取文本文件
@tool
def read_file(file_path):
    """
    读取文件内容
    :param file_path: 文件路径
    :return: 文件字符串内容
    """
    try:
        file_path = os.path.expanduser(file_path)
        if os.path.isdir(file_path):
            return f"错误: '{file_path}' 是一个目录，请提供文件路径"
        if not os.path.isfile(file_path):
            return f"错误: 文件不存在 '{file_path}'"
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        logger.info(f"读取成功: {file_path}")
        return content
    except Exception as e:
        logger.error(f"读取失败: {e}")
        return f"读取失败: {e}"


# 4. 删除单个文件
@tool
def del_file(file_path):
    """
    删除单个文件
    :param file_path: 文件路径
    """
    try:
        file_path = os.path.expanduser(file_path)
        os.remove(file_path)
        logger.info(f"文件已删除: {file_path}")
    except Exception as e:
        logger.error(f"删除文件失败: {e}")


# 5. 递归删除文件夹
@tool
def del_dir(dir_path):
    """
    递归删除整个文件夹(含内部所有内容)
    :param dir_path: 目录路径
    """
    try:
        dir_path = os.path.expanduser(dir_path)
        shutil.rmtree(dir_path)
        logger.info(f"文件夹已删除: {dir_path}")
    except Exception as e:
        logger.error(f"删除目录失败: {e}")


# 6. 扫描目录所有文件名
@tool
def scan_dir(dir_path):
    """
    列出文件夹内所有名称（文件+文件夹）
    :param dir_path: 目标目录
    :return: 名称列表
    """
    try:
        dir_path = os.path.expanduser(dir_path)
        name_list = os.listdir(dir_path)
        logger.info(f"扫描完成，共{len(name_list)}项")
        for name in name_list:
            logger.info(name)
        return name_list
    except Exception as e:
        logger.error(f"扫描失败: {e}")
        return []


# 7. 移动【文件/文件夹通用】
@tool
def move_item(source, target_dir):
    """
    移动文件或整个文件夹
    :param source: 源完整路径(文件/目录)
    :param target_dir: 目标存放目录
    """
    try:
        source = os.path.expanduser(source)
        target_dir = os.path.expanduser(target_dir)
        base_name = os.path.basename(source)
        # 拼接目标完整路径
        dst = os.path.join(target_dir, base_name)

        # 优化：如果目标目录不存在，自动创建（避免移动失败）
        if not os.path.exists(target_dir):
            os.makedirs(target_dir)

        # 执行移动
        shutil.move(source, dst)
        logger.info(f"移动完成: {source} → {dst}")
    except Exception as e:
        logger.error(f"移动失败: {e}")
# 8. 复制单个文件
@tool
def copy_file(source_path, target_dir):
    """
    复制文件到目标目录
    :param source_path: 源文件路径
    :param target_dir: 目标文件夹
    """
    try:
        source_path = os.path.expanduser(source_path)
        target_dir = os.path.expanduser(target_dir)
        fname = os.path.basename(source_path)
        dst = os.path.join(target_dir, fname)
        shutil.copy2(source_path, dst)
        logger.info(f"文件复制: {source_path} → {dst}")
    except Exception as e:
        logger.error(f"复制失败: {e}")


# 9. 完整复制文件夹
@tool
def copy_dir(source_path, target_dir):
    """
    完整复制目录及内部所有文件
    :param source_path: 源目录
    :param target_dir: 目标父目录
    """
    try:
        source_path = os.path.expanduser(source_path)
        target_dir = os.path.expanduser(target_dir)
        dirname = os.path.basename(source_path)
        dst = os.path.join(target_dir, dirname)
        shutil.copytree(source_path, dst)
        logger.info(f"目录复制: {source_path} → {dst}")
    except Exception as e:
        logger.error(f"复制失败: {e}")


# 10. 文件/文件夹重命名
@tool
def rename_item(old_path, new_name):
    """
    重命名文件或文件夹
    :param old_path: 原完整路径
    :param new_name: 新名称(带后缀)
    """
    try:
        old_path = os.path.expanduser(old_path)
        parent = os.path.dirname(old_path)
        new_full = os.path.join(parent, new_name)
        os.rename(old_path, new_full)
        logger.info(f"重命名: {old_path} → {new_full}")
    except Exception as e:
        logger.error(f"重命名失败: {e}")


# 11. 批量修改文件后缀
@tool
def batch_change_suffix(folder, old_suf, new_suf):
    """
    批量改目录内文件后缀，例：.txt→.md
    :param folder: 目标文件夹
    :param old_suf: 原后缀 .txt
    :param new_suf: 新后缀 .md
    """
    try:
        folder = os.path.expanduser(folder)
        cnt = 0
        for name in os.listdir(folder):
            full = os.path.join(folder, name)
            if os.path.isfile(full) and name.endswith(old_suf):
                new_name = name.replace(old_suf, new_suf)
                new_full = os.path.join(folder, new_name)
                os.rename(full, new_full)
                cnt += 1
        logger.info(f"批量修改完成，共改{cnt}个文件")
    except Exception as e:
        logger.error(f"批量改名失败: {e}")

 # 12. 向文件写入内容（覆盖写入）
@tool
def write_file(file_path, content):
    """
        向文件写入内容（如果文件不存在会自动创建，存在则覆盖）
        :param file_path: 文件路径
        :param content: 要写入的内容
    """
    try:
        file_path = os.path.expanduser(file_path)
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content)
        logger.info(f"文件写入成功: {file_path}")
    except Exception as e:
        logger.error(f"写入失败: {e}")






@tool
def get_desktop_path():
    """
    自动获取当前用户的桌面路径（跨平台支持 Windows/Mac/Linux，含中文等本地化桌面名）
    :return: 桌面绝对路径字符串
    """
    home = os.path.expanduser("~")
    # 尝试多种本地化桌面名
    for name in ["Desktop", "桌面", "Escritorio", "Bureau"]:
        desktop = os.path.join(home, name)
        if os.path.isdir(desktop):
            return desktop
    # 兜底：返回 Desktop 并自动创建
    desktop = os.path.join(home, "Desktop")
    os.makedirs(desktop, exist_ok=True)
    return desktop


