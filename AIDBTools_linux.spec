# -*- mode: python ; coding: utf-8 -*-
# Linux 版打包 spec（银河麒麟 / 统信UOS x86_64）
# 在 WSL2 / Linux 环境中执行：pyinstaller AIDBTools_linux.spec
import os

block_cipher = None
project_root = os.path.abspath('.')
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

datas = [
    ('app_config', 'app_config'),   # 原 config/ 已更名为 app_config/
    ('core', 'core'),
    ('ui', 'ui'),
    ('icon.png', '.'),
    ('icons', 'icons'),
    ('drivers', 'drivers'),   # 星环驱动（JDBC jar + Linux ODBC rpm/deb）
]
if xugu_pkg_source:
    datas.append((xugu_pkg_source, xugu_pkg_target))


hiddenimports = [
    'PySide6',
    'PySide6.QtWidgets',
    'PySide6.QtCore',
    'PySide6.QtGui',
    'PySide6.QtNetwork',
    'PySide6.QtPrintSupport',
    'PySide6.QtSvg',
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
    'pandas',
    'requests',
    'openpyxl',
    'openpyxl.workbook',
    'openpyxl.worksheet',
    'openpyxl.styles',
    'openpyxl.utils',
    'et_xmlfile',
    'ipaddress',
    'urllib.parse',
    'pathlib',
    # ── ui 模块（全部显式声明） ──
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
    'core.platform_utils',
    'core.query_manager',
    'core.scheduler',
    'core.skill_manager',
    'core.sync_engine',
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
        'pyodbc',        # Windows 专属，Linux 用 pymssql 替代
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

# 使用 COLLECT 模式（目录模式），避免共享库问题
coll = COLLECT(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=True,
    upx=True,
    upx_exclude=[],
    name='AIDBTools',
)
