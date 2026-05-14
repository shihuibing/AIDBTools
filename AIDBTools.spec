# -*- mode: python ; coding: utf-8 -*-
import os
import sys

block_cipher = None
_project_root = r'D:\Users\bing\Desktop\AIDBTools'

# ── 收集 app_config 包的所有子模块 ──────────────────────────────────────────────────
# 直接读取项目根目录的 app_config 目录
_app_config_pkg_path = os.path.join(_project_root, 'app_config')

# 手动收集 app_config 包中的 .py 文件
_app_config_files = []
if os.path.isdir(_app_config_pkg_path):
    for f in os.listdir(_app_config_pkg_path):
        if f.endswith('.py') or f == '__init__.py':
            _app_config_files.append(f)
_app_config_submodules = [f'app_config.{f[:-3]}' for f in _app_config_files if f.endswith('.py') and f != '__init__.py']
_app_config_submodules.append('app_config')  # 包含 app_config 本身
print(f"[AIDBTools.spec] app_config files: {_app_config_files}")
print(f"[AIDBTools.spec] app_config submodules: {_app_config_submodules}")

project_root   = r'D:\Users\bing\Desktop\AIDBTools'

# ── 自动探测 PySide6 插件目录 ────────────────────────────────────────────────────
# 注意：PySide6（pip 安装）的 .dll 和 plugins/ 都直接在包根目录下，
# 不像 PyQt6/Qt6 有额外的 Qt6/bin/ 和 Qt6/plugins/ 子目录。
import PySide6 as _pyside6_pkg
_pyside6_dir    = os.path.dirname(_pyside6_pkg.__file__)
_pyside6_plugins = os.path.join(_pyside6_dir, 'plugins')
# DLL（VC++ Runtime + Qt6 核心 + OpenGL）全部在 PySide6 根目录下
_pyside6_bin    = _pyside6_dir

def _pyside6_plugin(subdir):
    """返回插件子目录的 (src, dest) 元组"""
    src = os.path.join(_pyside6_plugins, subdir)
    dst = f'PySide6/plugins/{subdir}'
    return (src, dst) if os.path.isdir(src) else None

def _pyside6_dll(name):
    """返回 PySide6 根目录下某个 DLL 的 (src, dest) 元组"""
    src = os.path.join(_pyside6_bin, name)
    dst = '.'
    return (src, dst) if os.path.isfile(src) else None

# ── 数据资源 ──────────────────────────────────────────────────────────────────
datas = [
    ('app_config', 'app_config'),
    ('icon.ico', '.'),
    ('icons', 'icons'),
    ('drivers', 'drivers'),
]



# ── Qt 插件（Windows Server 兼容：必须打入 platforms 目录）────────────────────
_platform_dir = os.path.join(_pyside6_plugins, 'platforms')
_styles_dir   = os.path.join(_pyside6_plugins, 'styles')
_imgfmt_dir   = os.path.join(_pyside6_plugins, 'imageformats')

if os.path.isdir(_platform_dir):
    datas.append((_platform_dir, 'PySide6/plugins/platforms'))
if os.path.isdir(_styles_dir):
    datas.append((_styles_dir, 'PySide6/plugins/styles'))
if os.path.isdir(_imgfmt_dir):
    datas.append((_imgfmt_dir, 'PySide6/plugins/imageformats'))

# ── 必须打包的 DLL（Windows Server / 无独立显卡必需）────────────────────────────
# 核心原则：Windows Server 上通常没有安装 Visual C++ Redistributable，
# 也没有独立显卡驱动，需要把所有依赖 DLL 显式打进 exe。
_binaries = []

def _find_dll(name, sources=None):
    # 在多个路径下查找 DLL，返回 (src, dst) 或 None
    if sources is None:
        sources = [_pyside6_bin]  # 默认在 PySide6 根目录
    if isinstance(sources, str):
        sources = [sources]
    for base in sources:
        path = os.path.join(base, name)
        if os.path.isfile(path):
            return (path, '.')
    return None

# 后备搜索路径（系统目录，用于 PySide6 目录中没有的 DLL）
_system_dirs = [
    r'C:\Windows\System32',
    os.path.join(os.environ.get('SystemRoot', r'C:\Windows'), 'System32'),
]

# 1. VC++ Runtime DLL（QtWidgets ImportError 的根本原因）
_vcruntime_dlls = [
    'vcruntime140.dll',
    'vcruntime140_1.dll',
    'vcruntime140_threads.dll',
    'msvcp140.dll',
    'msvcp140_1.dll',
    'msvcp140_2.dll',
    'msvcp140_atomic_wait.dll',
    'msvcp140_codecvt_ids.dll',
    'concrt140.dll',
    'vccorlib140.dll',
]
for _dll in _vcruntime_dlls:
    _entry = _find_dll(_dll, _pyside6_bin) or _find_dll(_dll, _system_dirs)
    if _entry:
        _binaries.append(_entry)
    else:
        print(f"[AIDBTools.spec] 警告：未找到 {_dll}，跳过")

# 2. 软件渲染 OpenGL（无 GPU 时必需）
for _dll in ['opengl32sw.dll', 'd3dcompiler_47.dll']:
    _entry = _find_dll(_dll, _pyside6_bin) or _find_dll(_dll, _system_dirs)
    if _entry:
        _binaries.append(_entry)
    else:
        print(f"[AIDBTools.spec] 警告：未找到 {_dll}，跳过")

# 3. Qt6 核心 DLL（确保不被 PyInstaller 漏掉）
_qt6_core_dlls = [
    'Qt6Core.dll',
    'Qt6Gui.dll',
    'Qt6Widgets.dll',
    'Qt6Network.dll',
    'Qt6Svg.dll',
    'Qt6SvgWidgets.dll',
    'Qt6OpenGL.dll',
    'Qt6OpenGLWidgets.dll',
    'Qt6PrintSupport.dll',
    'Qt6Xml.dll',
]
for _dll in _qt6_core_dlls:
    _entry = _find_dll(_dll, _pyside6_bin)
    if _entry:
        _binaries.append(_entry)
    else:
        print(f"[AIDBTools.spec] 警告：未找到 {_dll}，跳过")
# ─────────────────────────────────────────────────────────────────────────────

hiddenimports = [
    # ── PySide6 ──
    'PySide6',
    'PySide6.QtWidgets',
    'PySide6.QtCore',
    'PySide6.QtGui',
    # ── SQLAlchemy ──
    'sqlalchemy',
    'sqlalchemy.dialects.mysql',
    'sqlalchemy.dialects.postgresql',
    'sqlalchemy.dialects.mssql',
    'sqlalchemy.dialects.oracle',
    # ── 数据库驱动 ──
    'pymysql',
    'psycopg2',
    'pyodbc',
    'oracledb',
    'jaydebeapi',
    'jpype',
    # ── 数据处理 ──
    'pandas',
    'requests',
    'openpyxl',
    'openpyxl.workbook',
    'openpyxl.worksheet',
    'openpyxl.styles',
    'openpyxl.utils',
    'et_xmlfile',
    # ── ui 模块（全部显式声明，防止打包遗漏） ──
    'ui.ai_chat_window',
    'ui.backup_window',
    'ui.export_import_window',
    'ui.main_window',
    'ui.model_config_window',
    'ui.scheduler_window',
    'ui.skill_manager_window',
    'ui.sync_window',
    'ui.table_extension',
    'ui.theme_manager',
    'ui.icon_manager',
    'ui.iconfont_loader',
    'ui.sql_editor_helper',
    # ── core 模块（全部显式声明） ──
    'core.ai_agent',
    'core.ai_chat',
    'core.ai_sql',
    'core.argo_driver_manager',
    'core.backup_engine',
    'core.connection',
    'core.connection_store',
    'core.mcpma',
    'core.ncx_importer',
    'core.query_manager',
    'core.platform_utils',
    'core.scheduler',
    'core.skill_manager',
    'core.sync_engine',
    # ── AI SDK 依赖 ──
    'openai',
    'openai._base_client',
    'anthropic',
    'tiktoken',
    'anyio',
    'httpx',
    # openai 的完整依赖链
    'distro',
    'jiter',
    'sniffio',
    'tqdm',
    'typing_extensions',
    'fire',
    'dotenv',          # python-dotenv 包内部模块（pip 包名是 python-dotenv，但 import 名是 dotenv）
    'dotenv.cli',      # dotenv 子模块
    'dotenv.main',     # dotenv 子模块
    'dotenv.parser',   # dotenv 子模块
    'rich',
    'tenacity',
    'yaml',
    'pydantic',
    'jinja2',
    'prompt_toolkit',
    
    # ── 修复 config 包名冲突（避免匹配 Python 内置 config 模块）───
    'app_config.model_config',
] + _app_config_submodules




a = Analysis(
    ['main.py'],
    pathex=[project_root],
    binaries=_binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=['hooks'],
    hooksconfig={
        # 禁用 PyInstaller 内置的 PyQt5/PyQt6 hooks
        # 避免 "attempting to run hook for PyQt6 while PySide6 is already loaded" 错误
        'PYZ-Archived-PyInstaller-hooks': 'PYZ-Archived-PyInstaller-hooks',
    },
    runtime_hooks=[],
    excludes=[
        # ── 排除 xugu 驱动（仅支持 Python 3.4-3.10，不支持 3.11，跳过分析避免 pythonNN.dll 警告）───
        'xgcondb',         # 虚谷驱动（xugu/xgcondb）
        'xgcondb._pyxgdb34',
        'xgcondb._pyxgdb36',
        'xgcondb._pyxgdb37',
        'xgcondb._pyxgdb38',
        'xgcondb._pyxgdb39',
        'xgcondb._pyxgdb310',
        'xgcondb._pyxgdb311',
        # ── 排除所有旧版 Qt 绑定，仅保留 PySide6 ──────────────────────
        'PyQt5',           # Qt5 商业授权
        'PyQt5.Qt',        # Qt5 主模块
        'PyQt5.QtCore',
        'PyQt5.QtGui',
        'PyQt5.QtWidgets',
        'PyQt5.QtNetwork',
        'PyQt5.QtOpenGL',
        'PyQt5.QtSql',
        'PyQt5.QtSvg',
        'PyQt6',           # Qt6 商业授权（替换为 LGPL 的 PySide6）
        'PyQt6.Qt',
        'PyQt6.QtCore',
        'PyQt6.QtGui',
        'PyQt6.QtWidgets',
        'PyQt6.QtNetwork',
        'PyQt6.QtOpenGL',
        'PyQt6.QtSql',
        'PyQt6.QtSvg',
        'PyQt6.sip',       # PyQt6 专用 SIP 绑定
        'PyQt6_sip',       # 同上（不同包名）
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)




pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='AIDBTools',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[
        # 不压缩以下 DLL，避免某些 Windows Server 环境 UPX 解压失败导致崩溃
        # Qt6 核心
        'Qt6Core.dll', 'Qt6Gui.dll', 'Qt6Widgets.dll',
        'Qt6Network.dll', 'Qt6Svg.dll', 'Qt6OpenGL.dll',
        'Qt6OpenGLWidgets.dll',
        # Qt6 平台插件
        'qwindows.dll', 'qmodernwindowsstyle.dll',
        # 软件渲染
        'opengl32sw.dll', 'd3dcompiler_47.dll',
        # VC++ Runtime（Server 上 UPX 压缩后可能无法正确加载）
        'vcruntime140.dll', 'vcruntime140_1.dll', 'vcruntime140_threads.dll',
        'msvcp140.dll', 'msvcp140_1.dll', 'msvcp140_2.dll',
        'concrt140.dll', 'vccorlib140.dll',
    ],
    runtime_tmpdir=None,
    console=False,
    icon='icon.ico',
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)


