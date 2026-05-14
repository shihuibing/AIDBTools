"""
platform_utils.py
跨平台工具函数，统一管理 Windows / Linux 差异。

所有平台相关的判断、路径、系统调用均在此处理，
业务代码只需 import 本模块，无需散落各处写 sys.platform。
"""
import sys
import os
import subprocess

# ── 平台标识 ──────────────────────────────────────
IS_WINDOWS = sys.platform == "win32"
IS_LINUX   = sys.platform.startswith("linux")
IS_MACOS   = sys.platform == "darwin"

# ── SQL Server 驱动 URL 模板 ───────────────────────
MSSQL_URL_TEMPLATE = (
    "mssql+pymssql://{}:{}@{}:{}/{}"
    if IS_LINUX
    else "mssql+pyodbc://{}:{}@{}:{}/{}?driver=ODBC+Driver+17+for+SQL+Server"
)

# ── 应用图标文件名 ─────────────────────────────────
APP_ICON_FILENAMES = ["icon.ico", "icon.png"] if IS_WINDOWS else ["icon.png", "icon.ico"]


def get_project_root_dir() -> str:
    """返回源码项目根目录。"""
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def get_app_base_dir() -> str:
    """获取运行时资源根目录，兼容源码 / PyInstaller 单文件模式。"""
    if getattr(sys, "frozen", False):
        meipass = getattr(sys, "_MEIPASS", "")
        if meipass and os.path.isdir(meipass):
            return meipass
        return os.path.dirname(sys.executable)
    return get_project_root_dir()


def get_icon_path() -> str:
    """返回首个可用的应用图标路径；打包模式优先从运行时解包目录读取。"""
    search_roots = [get_app_base_dir()]
    exe_dir = os.path.dirname(sys.executable) if getattr(sys, "frozen", False) else ""
    if exe_dir:
        search_roots.append(exe_dir)
    search_roots.append(get_project_root_dir())

    checked = set()
    for root in search_roots:
        if not root:
            continue
        norm_root = os.path.normcase(os.path.abspath(root))
        if norm_root in checked:
            continue
        checked.add(norm_root)
        for filename in APP_ICON_FILENAMES:
            path = os.path.join(root, filename)
            if os.path.isfile(path):
                return path

    return os.path.join(get_project_root_dir(), APP_ICON_FILENAMES[0])



def get_default_backup_dir() -> str:
    """返回备份默认目录，兼容 Windows Server（无 Desktop 目录）"""
    home = os.path.expanduser("~")
    if IS_LINUX:
        # ~/Documents 在无桌面的 Linux 上更可靠
        docs = os.path.join(home, "Documents")
        return os.path.join(docs if os.path.isdir(docs) else home, "AIDBTools_Backup")
    else:
        # Windows：优先 Desktop，Server 上没有 Desktop 则用 Documents，再退到用户主目录
        desktop = os.path.join(home, "Desktop")
        if os.path.isdir(desktop):
            return os.path.join(desktop, "AIDBTools_Backup")
        docs = os.path.join(home, "Documents")
        if os.path.isdir(docs):
            return os.path.join(docs, "AIDBTools_Backup")
        return os.path.join(home, "AIDBTools_Backup")


def open_folder(folder: str) -> bool:
    """
    用系统文件管理器打开指定文件夹。
    Windows: explorer
    Linux:   xdg-open（麒麟/UOS/Deepin 均支持）
    返回 True 表示成功启动，False 表示失败。
    """
    if not os.path.exists(folder):
        return False
    try:
        if IS_WINDOWS:
            subprocess.Popen(f'explorer "{folder}"')
        elif IS_LINUX:
            subprocess.Popen(["xdg-open", folder])
        else:
            subprocess.Popen(["open", folder])  # macOS
        return True
    except Exception:
        return False
