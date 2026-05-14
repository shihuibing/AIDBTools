# -*- mode: python ; coding: utf-8 -*-
# AIDBTools ARM aarch64 银河麒麟版打包 spec（使用 PySide6，通过 qt_compat.py 兼容 PyQt5）
# 必须在 ARM aarch64 机器上执行：pyinstaller AIDBTools_arm_kylin.spec
# 📌 优先使用 PySide6（LGPL 许可），若系统仅有 PyQt5 则通过兼容层自动适配
# ============================================================
import os
import platform

block_cipher = None
project_root = os.path.abspath('.')

# ── 探测虚谷驱动目录 ───────────────────────────────────────
xugu_pkg_source = None
xugu_pkg_target = None
for source_dir, target_dir in [
    (os.path.join(project_root, 'xg'), 'xg'),
    (os.path.join(project_root, 'xugu'), 'xugu'),
    (os.path.join(project_root, 'drivers', 'xugu'), os.path.join('drivers', 'xugu')),
]:
    if os.path.isdir(os.path.join(source_dir, 'xg')):
        xugu_pkg_source = source_dir
        xugu_pkg_target = target_dir
        break

# ── 数据文件 ──────────────────────────────────────────────
datas = [
    ('config', 'config'),
    ('core', 'core'),
    ('ui', 'ui'),
    ('icon.png', '.'),
    ('icons', 'icons'),
    ('drivers', 'drivers'),       # 星环驱动包
]
if xugu_pkg_source:
    datas.append((xugu_pkg_source, xugu_pkg_target))

# ── 隐含导入（PyQt5）──────────────────────────────────────
hiddenimports = [
    'PySide6',
    'PySide6.QtWidgets',
    'PySide6.QtCore',
    'PySide6.QtGui',
    'PySide6.QtPrintSupport',
    'sqlalchemy',
    'sqlalchemy.dialects.mysql',
    'sqlalchemy.dialects.postgresql',
    'sqlalchemy.dialects.mssql',
    'sqlalchemy.dialects.oracle',
    'pymysql',
    'psycopg2',
    'pymssql',
    'oracledb',
    'jaydebeapi',
    'jpype',
    'core.argo_driver_manager',
    # ── ui 模块 ──
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
    # ── core 模块 ──
    'core.ai_agent',
    'core.ai_chat',
    'core.ai_sql',
    'core.backup_engine',
    'core.connection',
    'core.connection_store',
    'core.mcpma',
    'core.ncx_importer',
    'core.platform_utils',
    'core.query_manager',
    'core.scheduler',
    'core.skill_manager',
    'core.sync_engine',
    'pandas',
    'requests',
    'openpyxl',
    'openpyxl.workbook',
    'openpyxl.worksheet',
    'openpyxl.styles',
    'openpyxl.utils',
    'et_xmlfile',
]
if xugu_pkg_source:
    hiddenimports.extend(['xg', 'xg.xgPython'])

a = Analysis(
    ['main.py'],
    pathex=[project_root],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'pyodbc',        # Windows 专属
        'cx_Oracle',     # 已被 oracledb 取代
        # ── 排除所有旧版 Qt 绑定，仅保留 PySide6（LGPL）──────────────
        'PyQt5',
        'PyQt5.Qt', 'PyQt5.QtCore', 'PyQt5.QtGui', 'PyQt5.QtWidgets',
        'PyQt5.QtNetwork', 'PyQt5.QtOpenGL', 'PyQt5.QtSql', 'PyQt5.QtSvg',
        'PyQt6',
        'PyQt6.Qt', 'PyQt6.QtCore', 'PyQt6.QtGui', 'PyQt6.QtWidgets',
        'PyQt6.QtNetwork', 'PyQt6.QtOpenGL', 'PyQt6.QtSql', 'PyQt6.QtSvg',
        'PyQt6.sip', 'PyQt6_sip',
    ],
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

# ARM aarch64：strip 可能导致 PyQt5 动态库段错误，关闭
ARM_STRIP = platform.machine() not in ('aarch64', 'arm64')

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
    strip=ARM_STRIP,
    upx=False,             # ARM 上 UPX 可能不兼容
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,      # auto-detect
    codesign_identity=None,
    entitlements_file=None,
)
