# file_utils.py  文件夹工具类（通用）
import os


def create_folder(folder_path: str) -> bool:
    """
    通用创建文件夹工具（支持多级目录）
    :param folder_path: 文件夹路径（相对/绝对都可以）
    :return: True=创建成功/已存在  False=创建失败
    """
    try:
        # 自动创建多层文件夹，已存在不报错
        os.makedirs(folder_path, exist_ok=True)
        print(f"✅ 文件夹就绪：{folder_path}")
        return True
    except Exception as e:
        print(f"❌ 创建文件夹失败：{str(e)}")
        return False


# ------------------- 你的项目专用（快速创建用户记忆文件夹） -------------------
def create_user_vector_folder(session_id: str = "default") -> str:
    """
    为你的宠物项目创建用户向量库文件夹
    """
    base_dir = os.path.dirname(os.path.abspath(__file__))
    # 向量库根目录
    vector_root = os.path.join(base_dir, "../vector_db")
    # 用户专属目录
    user_folder = os.path.join(vector_root, session_id)

    create_folder(user_folder)
    return user_folder