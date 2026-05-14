"""
theme_manager.py
主题管理模块 —— 支持紫罗兰（亮色）/ 柳叶绿（亮色）/ 暗色 三种主题
"""
import json
import os
import sys
from PySide6.QtWidgets import QApplication, QStyleFactory, QDialog, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame
from PySide6.QtGui import QPalette, QColor
from PySide6.QtCore import Qt

# ── 主题名称常量 ────────────────────────────────
THEME_LIGHT = "light"      # 紫罗兰（亮色）
THEME_WILLOW = "willow"    # 柳叶绿（亮色）
THEME_DARK = "dark"        # 暗色
THEME_AUTO = "auto"        # 向后兼容：旧配置可能存有 "auto"


# ── 持久化路径 ──────────────────────────────────
def _pref_path():
    if getattr(sys, "frozen", False):
        base = os.path.dirname(sys.executable)
    else:
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, "ui_prefs.json")


# ── 主题偏好读写 ────────────────────────────────
def load_theme() -> str:
    """读取用户上次选择的主题，默认紫罗兰亮色；旧配置 'auto' 映射为 light"""
    try:
        with open(_pref_path(), "r", encoding="utf-8") as f:
            theme = json.load(f).get("theme", THEME_LIGHT)
            # 向后兼容：旧版 "auto" 映射为紫罗兰亮色
            if theme == THEME_AUTO:
                return THEME_LIGHT
            return theme
    except Exception:
        return THEME_LIGHT


def save_theme(theme: str):
    prefs = {}
    try:
        with open(_pref_path(), "r", encoding="utf-8") as f:
            prefs = json.load(f)
    except Exception:
        pass
    prefs["theme"] = theme
    with open(_pref_path(), "w", encoding="utf-8") as f:
        json.dump(prefs, f, ensure_ascii=False, indent=2)


# ── 配置文件目录 ─────────────────────────────────
def load_config_dir() -> str:
    """读取用户配置的连接文件保存目录，默认返回空字符串（使用默认路径）"""
    try:
        with open(_pref_path(), "r", encoding="utf-8") as f:
            return json.load(f).get("config_dir", "") or ""
    except Exception:
        return ""


def save_config_dir(config_dir: str):
    """保存配置文件目录到 ui_prefs.json（空字符串表示使用默认路径）"""
    prefs = {}
    try:
        with open(_pref_path(), "r", encoding="utf-8") as f:
            prefs = json.load(f)
    except Exception:
        pass
    prefs["config_dir"] = config_dir
    with open(_pref_path(), "w", encoding="utf-8") as f:
        json.dump(prefs, f, ensure_ascii=False, indent=2)


# ── 窗口状态保存 ─────────────────────────────────────
def load_window_state(window_key: str, default: int = 0) -> int:
    """读取窗口状态（如当前选中的导航索引），返回 default 表示无记录"""
    try:
        with open(_pref_path(), "r", encoding="utf-8") as f:
            prefs = json.load(f)
        return prefs.get(f"window_state_{window_key}", default)
    except Exception:
        return default


def save_window_state(window_key: str, value: int):
    """保存窗口状态（如当前选中的导航索引）"""
    prefs = {}
    try:
        with open(_pref_path(), "r", encoding="utf-8") as f:
            prefs = json.load(f)
    except Exception:
        pass
    prefs[f"window_state_{window_key}"] = value
    with open(_pref_path(), "w", encoding="utf-8") as f:
        json.dump(prefs, f, ensure_ascii=False, indent=2)


# ── 系统深色检测 ────────────────────────────────
def _is_system_dark() -> bool:
    """检测系统当前是否为深色模式（Windows / macOS）"""
    try:
        import winreg
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize"
        )
        val, _ = winreg.QueryValueEx(key, "AppsUseLightTheme")
        winreg.CloseKey(key)
        return val == 0
    except Exception:
        pass

    app = QApplication.instance()
    if app:
        bg = app.palette().color(QPalette.ColorRole.Window)
        return bg.lightness() < 128
    return False


# ── 主题 Tokens ─────────────────────────────────
# Cursor 风格配色系统：
# 亮色：极浅背景 + 纯白卡片 + 柔和阴影 + 紫罗兰强调色
# 深色：深空蓝背景 + 悬浮卡片 + 微光边框 + 紫罗兰强调色
_LIGHT_TOKENS = {
    "bg": "#f8f9fb",
    "surface": "#ffffff",
    "surface_alt": "#f1f3f8",
    "surface_muted": "#e8ecf4",
    "surface_hover": "#eaeef7",
    "surface_active": "#dce3f0",
    "border": "#dde2ed",
    "border_strong": "#c4cce0",
    "text": "#1e2235",
    "text_soft": "#3d4461",
    "text_muted": "#7a82a0",
    "accent": "#6366f1",
    "accent_hover": "#818cf8",
    "accent_pressed": "#4f52d0",
    "accent_soft": "#eef0ff",
    "success": "#10b981",
    "success_hover": "#34d399",
    "success_soft": "#ecfdf5",
    "danger": "#f43f5e",
    "danger_hover": "#fb7185",
    "danger_soft": "#fff1f3",
    "warning": "#f59e0b",
    "warning_soft": "#fffbeb",
    "code_bg": "#f4f6fb",
    "log_bg": "#0f1117",
    "log_text": "#e2e8f0",
    "shadow": "rgba(30, 34, 53, 0.07)",
    "shadow_md": "rgba(30, 34, 53, 0.12)",
    "selection_bg": "#eef0ff",
    "selection_text": "#4338ca",
    "table_alt": "#f8fafc",
    "scroll_handle": "#c8cfde",
    "scroll_handle_hover": "#a0a9c0",
    "user_bubble_bg": "#eef0ff",
    "done_bg": "#f0fdf4",
    "info": "#64748b",
}

_DARK_TOKENS = {
    "bg": "#0f1117",
    "surface": "#171a24",
    "surface_alt": "#1e2233",
    "surface_muted": "#252a3a",
    "surface_hover": "#282f42",
    "surface_active": "#2e3550",
    "border": "#2a3050",
    "border_strong": "#3d4666",
    "text": "#e8eaf4",
    "text_soft": "#b4bcd6",
    "text_muted": "#7a84a8",
    "accent": "#818cf8",
    "accent_hover": "#a5b4fc",
    "accent_pressed": "#6366f1",
    "accent_soft": "#312e81",
    "success": "#34d399",
    "success_hover": "#6ee7b7",
    "success_soft": "#0d2e20",
    "danger": "#fb7185",
    "danger_hover": "#fda4af",
    "danger_soft": "#2e1020",
    "warning": "#fbbf24",
    "warning_soft": "#2e2210",
    "code_bg": "#0c0f18",
    "log_bg": "#070910",
    "log_text": "#d4dff0",
    "shadow": "rgba(0, 0, 0, 0.4)",
    "shadow_md": "rgba(0, 0, 0, 0.55)",
    "selection_bg": "#2e3570",
    "selection_text": "#ffffff",
    "table_alt": "#1a1e2e",
    "scroll_handle": "#3d4666",
    "scroll_handle_hover": "#556080",
    "user_bubble_bg": "#2e3570",
    "done_bg": "#0d2e20",
    "info": "#94a3b8",
}

_WILLOW_TOKENS = {
    # 柳叶绿（亮色）：暖白背景 + 自然绿强调色
    "bg": "#f7f9f8",
    "surface": "#ffffff",
    "surface_alt": "#f1f4f2",
    "surface_muted": "#e5ebe8",
    "surface_hover": "#eaf0ec",
    "surface_active": "#dde6e1",
    "border": "#d4ddd8",
    "border_strong": "#b8c8bf",
    "text": "#1a2e22",
    "text_soft": "#3a5244",
    "text_muted": "#6e8a7a",
    "accent": "#5b9a6f",
    "accent_hover": "#4a8a5f",
    "accent_pressed": "#3d7a50",
    "accent_soft": "#e8f5ec",
    "success": "#10b981",
    "success_hover": "#34d399",
    "success_soft": "#ecfdf5",
    "danger": "#f43f5e",
    "danger_hover": "#fb7185",
    "danger_soft": "#fff1f3",
    "warning": "#f59e0b",
    "warning_soft": "#fffbeb",
    "code_bg": "#f2f6f4",
    "log_bg": "#0f1117",
    "log_text": "#e2e8f0",
    "shadow": "rgba(30, 46, 34, 0.07)",
    "shadow_md": "rgba(30, 46, 34, 0.12)",
    "selection_bg": "#e8f5ec",
    "selection_text": "#3d7a50",
    "table_alt": "#f8faf9",
    "scroll_handle": "#b8c8bf",
    "scroll_handle_hover": "#8aa898",
    "user_bubble_bg": "#e8f5ec",
    "done_bg": "#f0fdf4",
    "info": "#64748b",
}


def _resolve_theme() -> str:
    """解析最终使用的主题（auto → light），兼容旧配置"""
    theme = load_theme()  # load_theme() 已内置 auto→light 映射
    return theme


def get_log_box_style(theme: str = None) -> str:
    """获取日志框（QTextEdit）的 QSS，始终深色终端风格。"""
    tokens = get_theme_tokens(theme)
    return f"""
QTextEdit#logBox {{
    background-color: {tokens['log_bg']};
    color: {tokens['log_text']};
    border: 1px solid {tokens['border']};
    border-radius: 2px;
    padding: 6px;
    font-family: Consolas, "Courier New", monospace;
    font-size: 10px;
    selection-background-color: {tokens['selection_bg']};
}}
QTextEdit#logBox QScrollBar:vertical {{
    background: transparent;
    width: 8px;
    margin: 0;
}}
QTextEdit#logBox QScrollBar::handle:vertical {{
    background: {tokens['scroll_handle']};
    border-radius: 2px;
    min-height: 20px;
}}
QTextEdit#logBox QScrollBar::handle:vertical:hover {{
    background: {tokens['scroll_handle_hover']};
}}
QTextEdit#logBox QScrollBar::add-line:vertical,
QTextEdit#logBox QScrollBar::sub-line:vertical {{
    height: 0;
}}
QTextEdit#logBox QScrollBar:horizontal {{
    height: 6px;
}}
QTextEdit#logBox QScrollBar::handle:horizontal {{
    background: {tokens['scroll_handle']};
    border-radius: 2px;
}}
QTextEdit#logBox QScrollBar::handle:horizontal:hover {{
    background: {tokens['scroll_handle_hover']};
}}
"""



def get_table_style(theme: str = None) -> dict:
    """获取表格的完整样式配置（基于 HTML 预览样式），返回包含多种样式字符串的字典。"""
    resolved = _resolve_theme() if theme is None else theme
    is_dark = resolved == THEME_DARK
    is_willow = resolved == THEME_WILLOW
    if is_dark:
        return {
            'table_wrapper': 'QWidget#tableWrapper{background:#1a1c2b;border:1px solid #2a2d3a;border-radius:6px;}',
            'table': 'QTableWidget{background:#13141f;border:none;gridline-color:#2a2d3a;outline:none;font-size:12px;color:#c8cfde;}QTableWidget::item{padding:0px;border:none;border-bottom:1px solid #2a2d3a;color:#c8cfde;}QTableWidget::item:hover{background:#1a2e24;}QTableWidget::item:selected{background:#1a2e24;color:#7bc48e;}QHeaderView{background:#1a1c2b;border:none;border-bottom:1px solid #2a2d3a;}QHeaderView::section{background:#1f2233;color:#94a3b8;font-weight:600;font-size:11px;text-align:left;padding:7px 12px;border:none;border-bottom:1px solid #2a2d3a;border-right:1px solid #2a2d3a;}QHeaderView::section:hover{background:#252839;color:#c8cfde;}QTableWidget::item:alternate{background:#1a1c2b;}QTableWidget QScrollBar:vertical{background:transparent;width:8px;margin:0;}QTableWidget QScrollBar::handle:vertical{background:#4a5568;border-radius:4px;min-height:20px;}QTableWidget QScrollBar::handle:vertical:hover{background:#6b7280;}QTableWidget QScrollBar::add-line:vertical,QTableWidget QScrollBar::sub-line:vertical{height:0;}QTableWidget QScrollBar:horizontal{background:transparent;height:8px;margin:0;}QTableWidget QScrollBar::handle:horizontal{background:#4a5568;border-radius:4px;min-width:20px;}QTableWidget QScrollBar::handle:horizontal:hover{background:#6b7280;}QTableWidget QScrollBar::add-line:horizontal,QTableWidget QScrollBar::sub-line:horizontal{width:0;}',
            'checkbox': {'checked':'#7bc48e','unchecked_bg':'#1f2233','border':'#3b4151','checkmark':'#ffffff'},
            'hover_bg':'#1a2e24',
            'selected_bg':'#1a2e24',
            'null_color':'#4a5568',
        }
    elif is_willow:
        return {
            'table_wrapper': 'QWidget#tableWrapper{background:#ffffff;border:1px solid #d4e0d8;border-radius:6px;}',
            'table': 'QTableWidget{background:#ffffff;border:none;gridline-color:#e8f0eb;outline:none;font-size:12px;color:#2d3a32;}QTableWidget::item{padding:0px;border:none;border-bottom:1px solid #e8f0eb;color:#2d3a32;}QTableWidget::item:hover{background:#e8f5ec;}QTableWidget::item:selected{background:#e8f5ec;color:#5b9a6f;}QHeaderView{background:#f1f4f2;border:none;border-bottom:1px solid #d4e0d8;}QHeaderView::section{background:#f1f4f2;color:#5a7a68;font-weight:600;font-size:11px;text-align:left;padding:7px 12px;border:none;border-bottom:1px solid #d4e0d8;border-right:1px solid #e8f0eb;}QHeaderView::section:hover{background:#e5ebe8;color:#2d3a32;}QTableWidget::item:alternate{background:#f7f9f8;}QTableWidget QScrollBar:vertical{background:transparent;width:8px;margin:0;}QTableWidget QScrollBar::handle:vertical{background:#b0c4b8;border-radius:4px;min-height:20px;}QTableWidget QScrollBar::handle:vertical:hover{background:#8aaa98;}QTableWidget QScrollBar::add-line:vertical,QTableWidget QScrollBar::sub-line:vertical{height:0;}QTableWidget QScrollBar:horizontal{background:transparent;height:8px;margin:0;}QTableWidget QScrollBar::handle:horizontal{background:#b0c4b8;border-radius:4px;min-width:20px;}QTableWidget QScrollBar::handle:horizontal:hover{background:#8aaa98;}QTableWidget QScrollBar::add-line:horizontal,QTableWidget QScrollBar::sub-line:horizontal{width:0;}',
            'checkbox': {'checked':'#5b9a6f','unchecked_bg':'#ffffff','border':'#c4d4ca','checkmark':'#ffffff'},
            'hover_bg':'#e8f5ec',
            'selected_bg':'#e8f5ec',
            'null_color':'#a0b8aa',
        }
    else:
        return {
            'table_wrapper': 'QWidget#tableWrapper{background:#ffffff;border:1px solid #e5e7eb;border-radius:6px;}',
            'table': 'QTableWidget{background:#ffffff;border:none;gridline-color:#f1f3f4;outline:none;font-size:12px;color:#374151;}QTableWidget::item{padding:0px;border:none;border-bottom:1px solid #f1f3f4;color:#374151;}QTableWidget::item:hover{background:#eef0ff;}QTableWidget::item:selected{background:#eef0ff;color:#6366f1;}QHeaderView{background:#f8f9fb;border:none;border-bottom:1px solid #e5e7eb;}QHeaderView::section{background:#f8f9fb;color:#6b7280;font-weight:600;font-size:11px;text-align:left;padding:7px 12px;border:none;border-bottom:1px solid #e5e7eb;border-right:1px solid #f1f3f4;}QHeaderView::section:hover{background:#f1f3f8;color:#374151;}QTableWidget::item:alternate{background:#fafbfc;}QTableWidget QScrollBar:vertical{background:transparent;width:8px;margin:0;}QTableWidget QScrollBar::handle:vertical{background:#c8cfde;border-radius:4px;min-height:20px;}QTableWidget QScrollBar::handle:vertical:hover{background:#a0a9c0;}QTableWidget QScrollBar::add-line:vertical,QTableWidget QScrollBar::sub-line:vertical{height:0;}QTableWidget QScrollBar:horizontal{background:transparent;height:8px;margin:0;}QTableWidget QScrollBar::handle:horizontal{background:#c8cfde;border-radius:4px;min-width:20px;}QTableWidget QScrollBar::handle:horizontal:hover{background:#a0a9c0;}QTableWidget QScrollBar::add-line:horizontal,QTableWidget QScrollBar::sub-line:horizontal{width:0;}',
            'checkbox': {'checked':'#6366f1','unchecked_bg':'#ffffff','border':'#e5e7eb','checkmark':'#ffffff'},
            'hover_bg':'#eef0ff',
            'selected_bg':'#eef0ff',
            'null_color':'#d1d5db',
        }


def get_theme_tokens(theme: str = None) -> dict:
    """获取指定主题的颜色集，None = 自动检测"""
    if theme is None:
        theme = _resolve_theme()
    if theme == THEME_DARK:
        return _DARK_TOKENS.copy()
    if theme == THEME_WILLOW:
        return _WILLOW_TOKENS.copy()
    return _LIGHT_TOKENS.copy()


def get_bubble_colors(theme: str = None) -> dict:
    """获取 AI 气泡及 Agent 执行步骤的气泡背景色集，None = 自动检测。Cursor 风格圆角气泡。"""
    if theme is None:
        theme = _resolve_theme()
    if theme == THEME_DARK:
        return {
            "ai":    "#1e2240",   # AI 气泡（Cursor 深色，柔和紫蓝）
            "think": "#232840",   # 思考中气泡
            "sql":   "#1a2e24",   # SQL 执行气泡（绿色系）
            "obs":   "#232840",   # 观察结果气泡
            "done":  _DARK_TOKENS.get("done_bg", "#0d2e20"),
            "error": "#2e1020",   # 出错气泡（红色系）
        }
    return {
        "ai":    "#f0f2fe",   # AI 气泡（Cursor 亮色，柔和紫白）
        "think": "#f5f6fc",   # 思考中气泡
        "sql":   "#ecfdf5",   # SQL 执行气泡（绿色系）
        "obs":   "#f5f6fc",   # 观察结果气泡
        "done":  _LIGHT_TOKENS.get("done_bg", "#f0fdf4"),
        "error": "#fff1f3",   # 出错气泡（红色系）
    }


# ── 主窗口专用样式（Cursor 风格）─────────────────────────
_MAIN_WINDOW_QSS = """
/* ── 全局根背景 ── */
QWidget#workspaceRoot {{
    background: {bg};
}}
/* ── 工具栏（透明背景、无边框）── */
QWidget#win11Toolbar {{
    background: transparent;
    border: none;
}}
/* 工具栏文字按钮（圆角无边框，透明底） */
QPushButton#tbText {{
    background: transparent;
    color: {text_soft};
    border: none;
    border-radius: 4px;
    padding: 0 12px;
    font-size: 12px;
    font-weight: 500;
}}
QPushButton#tbText:hover {{
    background: {surface_hover};
    color: {text};
}}
QPushButton#tbText:pressed {{
    background: {surface_active};
}}
/* 主要操作按钮（强调色无边框） */
QPushButton#tbText[role="primary"] {{
    background: {accent};
    color: #ffffff;
    border: none;
}}
QPushButton#tbText[role="primary"]:hover {{
    background: {accent_hover};
}}
QPushButton#tbText[role="primary"]:pressed {{
    background: {accent_pressed};
}}
/* 工具栏图标按钮（完全透明无边框） */
QToolButton#tbIcon {{
    background: transparent;
    color: {text_muted};
    border: none;
    border-radius: 4px;
    padding: 2px;
}}
QToolButton#tbIcon:hover {{
    background: {surface_hover};
    color: {text_soft};
}}
QToolButton#tbIcon:pressed {{
    background: transparent;
}}
/* ── 表格工具栏按钮（QToolButton）── */
/* 注：result 数据工具栏按钮由 _tb() 工厂函数内联设置样式 */
/* 此处仅设置通用基础样式（会被内联样式覆盖） */
/* ── 卡片面板（圆角 + 微边框）── */
QWidget#sectionCard {{
    background: {surface};
    border: 1px solid {border};
    border-radius: 2px;
}}
/* ── 面板标题（现代无衬线）── */
QLabel[role="panelTitle"] {{
    color: {text};
    font-size: 13px;
    font-weight: 600;
    background: transparent;
}}
/* ── 状态胶囊标签 ── */
QLabel[role="statusPill"] {{
    color: {text_muted};
    font-size: 11px;
    background: {surface_alt};
    border: 1px solid {border};
    border-radius: 2px;
    padding: 1px 8px;
}}
/* ── 强调胶囊标签 ── */
QLabel[role="statusAccent"] {{
    color: {accent};
    font-size: 11px;
    background: {accent_soft};
    border: 1px solid {accent_soft};
    border-radius: 2px;
    padding: 1px 8px;
    font-weight: 500;
}}
/* ── 专注模式按钮 ── */
QPushButton#btnFocus {{
    background: transparent;
    color: {text_muted};
    border: 1px solid {border};
    border-radius: 5px;
    font-size: 11px;
    padding: 4px 8px;
}}
QPushButton#btnFocus:hover {{
    background: {accent_soft};
    color: {accent};
    border-color: {accent_hover};
}}
QPushButton#btnFocus:checked {{
    background: {accent};
    color: #ffffff;
    border-color: {accent};
}}
/* ── SQL 标签栏（现代风格）── */
QTabBar#sqlTabBar {{
    background: transparent;
    border: none;
}}
QTabBar#sqlTabBar::tab {{
    background: transparent;
    color: {text_soft};
    border: none;
    border-bottom: 3px solid transparent;
    padding: 3px 3px;
    font-size: 13px;
    margin-right: 4px;
    min-width: auto;
}}
QTabBar#sqlTabBar::tab:selected {{
    background: transparent;
    color: {accent};
    font-weight: 500;
    border-bottom: 3px solid {accent};
}}
QTabBar#sqlTabBar::tab:hover:!selected {{
    background: transparent;
    color: {text};
    border-bottom: 3px solid {border};
}}
/* ── 标签工具按钮（新建/保存/导入）── */
QToolButton#newTabBtn, QToolButton#btnSaveQuery, QToolButton#btnImportQuery {{
    background: transparent;
    color: {text_muted};
    border: none;
    border-radius: 4px;
}}
QToolButton#newTabBtn:hover, QToolButton#btnSaveQuery:hover, QToolButton#btnImportQuery:hover {{
    background: {surface_hover};
    color: {text_soft};
}}
/* ── 翻页条 ── */
QWidget#pageBarWidget {{
    background: {surface_alt};
    border-top: 1px solid {border};
    border-bottom-left-radius: 12px;
    border-bottom-right-radius: 12px;
}}
QPushButton[role="page"] {{
    background: {surface};
    color: {text_soft};
    border: none;
    border-radius: 4px;
    font-size: 11px;
    padding: 0;
}}
QPushButton[role="page"]:hover {{
    background: {surface_hover};
    color: {text};
    border-color: {border_strong};
}}
/* ── 表格容器（无边框，融入卡片）── */
QWidget#tableContainer {{
    background: transparent;
    border: none;
}}
/* ── Splitter 拖动条（细线，悬停时主题色）── */
QSplitter::handle {{
    background: {border};
}}
QSplitter::handle:hover {{
    background: {accent};
}}
QSplitter::handle:horizontal {{
    width: 1px;
    margin: 0;
}}
QSplitter::handle:vertical {{
    height: 1px;
    margin: 0;
}}
/* 悬停时扩大拖动区域 */
QSplitter#mainWorkspaceSplitter::handle:horizontal {{
    margin: 0;
}}
QSplitter#workChatSplitter::handle:horizontal {{
    margin: 0;
}}
QSplitter#workVerticalSplitter::handle:vertical {{
    margin: 0;
}}
/* ── SQL 工作台专项样式 ── */
/* SQL 徽章 */
QLabel#sqlBadge {{
    color: {accent};
    background: {accent_soft};
    border: 0px solid {accent_hover};
    border-radius: 4px;
    padding: 1px 7px;
    font-size: 12px;
    font-weight: 700;
    letter-spacing: 0.06em;
}}
/* 工具栏视觉分隔条 */
QWidget#toolbarSep {{
    background: {border};
    min-width: 1px;
    max-width: 1px;
    margin: 0 4px;
}}
/* 统计条（monospace 风格） */
QLabel#statBar {{
    color: {accent};
    background: {accent_soft};
    border: 1px solid {accent_hover};
    border-radius: 4px;
    padding: 2px 8px;
    font-size: 10px;
    font-family: Consolas, "Cascadia Code", monospace;
    font-weight: 500;
    min-width: 80px;
}}
/* 过滤栏容器（独立视觉区）- Web风格 */
QWidget#filterBarContainer {{
    background: {bg};
    border: 1px solid {border};
    border-radius: 15px;
}}
/* 过滤栏 toggle 按钮（Aa / .* 切换）- 无边框简洁风格 */
QToolButton#filterToggle {{
    background: transparent;
    color: {text_muted};
    border: none;
    border-radius: 4px;
    padding: 2px 6px;
    font-family: Consolas, monospace;
    font-size: 11px;
    font-weight: 600;
}}
QToolButton#filterToggle:checked {{
    background: {surface_muted};
    color: {text};
}}
QToolButton#filterToggle:hover:!checked {{
    background: {surface_alt};
    color: {text_soft};
}}
/* AI 输入行 */
QLineEdit#aiInputField {{
    background: {surface_alt};
    border: 0px solid {border};
    border-radius: 6px;
    padding: 0 10px;
    font-size: 12px;
    color: {text};
}}
QLineEdit#aiInputField:focus {{
    border-color: {accent};
    background: {surface};
    outline: none;
}}
/* 标签页修改指示器（橙色圆点） */
QLabel#tabDirtyDot {{
    background: {warning};
    border-radius: 3px;
    min-width: 6px;
    max-width: 6px;
    min-height: 6px;
    max-height: 6px;
}}
/* ── 结果表格专项（已移至 main_window.py 设置）── */
/*
QTableWidget {{
    gridline-color: {border};
    border: none;
    outline: none;
}}
QTableWidget::item {{
    padding: 0 4px;
    border: none;
    outline: none;
}}
QTableWidget::item:selected {{
    background: {accent_soft};
    color: {accent};
}}
QHeaderView::section {{
    background: {surface_alt};
    color: {text_muted};
    border: none;
    border-bottom: 1px solid {border};
    border-right: 1px solid {border};
    padding: 6px 10px;
    font-size: 11px;
    font-weight: 600;
    text-align: left;
}}
QHeaderView::section:hover {{
    background: {surface_hover};
    color: {text};
}}
QTableWidget:item:alternate {{
    background: {surface_alt};
}}
*/
/* ── 日志面板 ── */
QLabel#logEntry {{
    font-size: 11px;
    padding: 1px 0;
    background: transparent;
}}
/* ── 连接状态指示灯 ── */
QLabel#connDot {{
    background: {danger};
    border-radius: 3px;
    min-width: 6px;
    max-width: 6px;
    min-height: 6px;
    max-height: 6px;
}}
QLabel#connDot.connected {{
    background: {success};
}}
/* ── 弹窗/对话框通用控件样式（跟随主题色）── */
QPushButton {{
    background: transparent;
    color: {text};
    border: none;
    border-radius: 4px;
    padding: 2px 6px;
    font-size: 13px;
}}
QPushButton:hover {{
    background: {surface_hover};
    color: {text};
}}
QPushButton:pressed {{
    background: {surface_active};
}}
QPushButton:disabled {{
    background: transparent;
    color: {text_muted};
}}
QPushButton[role="primary"] {{
    background: {accent};
    color: #ffffff;
}}
QPushButton[role="primary"]:hover {{
    background: {accent_hover};
}}
QPushButton[role="primary"]:pressed {{
    background: {accent_pressed};
}}
QPushButton[role="success"] {{
    background: {success};
    color: #ffffff;
}}
QPushButton[role="success"]:hover {{
    background: {success_hover};
}}
QPushButton[role="success"]:pressed {{
    background: {success};
}}
QPushButton[role="danger"] {{
    background: {danger};
    color: #ffffff;
}}
QPushButton[role="danger"]:hover {{
    background: {danger_hover};
}}
QPushButton[role="danger"]:pressed {{
    background: {danger};
}}
QLineEdit, QTextEdit, QPlainTextEdit {{
    background: {surface};
    color: {text};
    border: 1px solid {border};
    border-radius: 10px;
    padding: 1px 10px;
    font-size: 13px;
    selection-background-color: {selection_bg};
    selection-color: {selection_text};
}}
QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus {{
    border-color: {accent};
}}
QComboBox {{
    background: {surface};
    color: {text};
    border: 1px solid {border};
    border-radius: 2px;
    padding: 6px 10px;
    font-size: 13px;
}}
QComboBox:hover {{
    border-color: {border_strong};
}}
QComboBox:focus {{
    border-color: {accent};
}}
QComboBox::dropDown {{
    border: none;
    background: transparent;
    width: 24px;
}}
QComboBox QAbstractItemView {{
    background: {surface};
    border: 1px solid {border};
    border-radius: 2px;
    outline: 0;
    selection-background-color: {accent_soft};
    selection-color: {accent};
    color: {text};
}}
QAbstractItemView::item {{
    color: {text};
    padding: 4px 8px;
}}
QAbstractItemView::item:hover {{
    background: {surface_hover};
    color: {text};
}}
QAbstractItemView::item:selected {{
    background: {accent_soft};
    color: {accent};
}}
QCheckBox {{
    color: {text};
    spacing: 6px;
    font-size: 13px;
}}
QCheckBox::indicator {{
    width: 16px;
    height: 16px;
    border: 1.5px solid {border_strong};
    border-radius: 2px;
    background: {surface};
}}
QCheckBox::indicator:checked {{
    background: {accent};
    border-color: {accent};
}}
QRadioButton {{
    color: {text};
    spacing: 6px;
    font-size: 13px;
}}
QRadioButton::indicator {{
    width: 16px;
    height: 16px;
    border: 1.5px solid {border_strong};
    border-radius: 2px;
    background: {surface};
}}
QRadioButton::indicator:checked {{
    background: {accent};
    border-color: {accent};
}}
QGroupBox {{
    color: {accent};
    border: 1px solid {border};
    border-radius: 2px;
    margin-top: 10px;
    padding-top: 10px;
    font-size: 12px;
    font-weight: 600;
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 10px;
    padding: 0 6px;
}}
QTabWidget::pane {{
    border: 1px solid {border};
    border-radius: 2px;
    background: {surface};
}}
QTabBar::tab {{
    background: {surface_alt};
    color: {text_soft};
    border: 1px solid {border};
    border-bottom: none;
    border-top-left-radius: 4px;
    border-top-right-radius: 4px;
    padding: 3px 10px;
    font-size: 12px;
    margin-right: 2px;
    min-height: 24px;
}}
QTabBar::tab:selected {{
    background: {surface};
    color: {accent};
    font-weight: 600;
    border-bottom: 2px solid {accent};
}}
QTabBar::tab:hover:!selected {{
    background: {surface_hover};
    color: {accent};
}}
QListWidget, QListView {{
    background: {surface};
    color: {text};
    border: 1px solid {border};
    border-radius: 2px;
    outline: 0;
    font-size: 13px;
}}
QListWidget::item:selected, QListView::item:selected {{
    background: {accent_soft};
    color: {accent};
}}
QListWidget::item:hover:!selected, QListView::item:hover:!selected {{
    background: {surface_hover};
}}
"""

# ── 全局主题应用 ──────────────────────────────────
def apply_theme(app: QApplication, theme: str = None):
    """将整个 Qt 应用程序主题切换到 light / dark / auto"""
    if theme is None:
        theme = _resolve_theme()

    tokens = get_theme_tokens(theme)

    # 1. 调色板（控制 QPalette 能覆盖的控件）
    palette = QPalette()
    bg = QColor(tokens["bg"])
    surface = QColor(tokens["surface"])
    surface_alt = QColor(tokens["surface_alt"])
    text = QColor(tokens["text"])
    text_muted = QColor(tokens["text_muted"])
    accent = QColor(tokens["accent"])

    palette.setColor(QPalette.ColorRole.Window, bg)
    palette.setColor(QPalette.ColorRole.WindowText, text)
    palette.setColor(QPalette.ColorRole.Base, surface)
    palette.setColor(QPalette.ColorRole.AlternateBase, surface_alt)
    palette.setColor(QPalette.ColorRole.ToolTipBase, surface)
    palette.setColor(QPalette.ColorRole.ToolTipText, text)
    palette.setColor(QPalette.ColorRole.PlaceholderText, text_muted)
    palette.setColor(QPalette.ColorRole.Text, text)
    palette.setColor(QPalette.ColorRole.Button, surface_alt)
    palette.setColor(QPalette.ColorRole.ButtonText, text)
    palette.setColor(QPalette.ColorRole.BrightText, QColor("#ffffff"))
    palette.setColor(QPalette.ColorRole.Highlight, accent)
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor("#ffffff"))
    palette.setColor(QPalette.ColorRole.Link, accent)
    palette.setColor(QPalette.ColorRole.LinkVisited, QColor("#6366f1"))
    palette.setColor(QPalette.ColorRole.AlternateBase, surface_alt)

    app.setPalette(palette)
    app.setStyle("Fusion")

    # 2. 全局 Stylesheet（覆盖 Fusion 调色板覆盖不到的细节）
    scroll_bar = f"""
    QScrollBar:vertical {{
        background: transparent;
        width: 8px;
        margin: 0;
    }}
    QScrollBar::handle:vertical {{
        background: {tokens['scroll_handle']};
        border-radius: 2px;
        min-height: 30px;
    }}
    QScrollBar::handle:vertical:hover {{
        background: {tokens['scroll_handle_hover']};
    }}
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
        height: 0;
        subcontrol-position: none;
    }}
    QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
        background: none;
    }}
    QScrollBar:horizontal {{
        background: transparent;
        height: 8px;
        margin: 0;
    }}
    QScrollBar::handle:horizontal {{
        background: {tokens['scroll_handle']};
        border-radius: 2px;
        min-width: 30px;
    }}
    QScrollBar::handle:horizontal:hover {{
        background: {tokens['scroll_handle_hover']};
    }}
    QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
        width: 0;
        subcontrol-position: none;
    }}
    QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {{
        background: none;
    }}
    """

    # ── 左侧连接树 + 侧边栏专用样式（Cursor 风格）─────────
    sidebar_qss = f"""
    /* 左侧面板底色 */
    QWidget#leftPanel {{
        background: {tokens['bg']};
    }}
    /* Cursor 风格：左侧卡片带圆角 + 悬浮感 */
    QWidget#sidebarCard {{
        background: {tokens['surface']};
        border: 1px solid {tokens['border']};
        border-radius: 2px;
        /* 柔和阴影效果（PyQt6 有限支持，但 CSS 声明无害） */
    }}
    /* 连接树：无外框、圆角选中背景 */
    QTreeWidget#connectionTree {{
        background: transparent;
        color: {tokens['text']};
        border: none;
        outline: 0;
        font-size: 13px;
    }}
    QTreeWidget#connectionTree::item {{
        padding: 3px 6px;
        border: none;
        border-radius: 2px;
        margin: 1px 2px;
        color: {tokens['text']};
    }}
    QTreeWidget#connectionTree::item:hover {{
        background: {tokens['surface_hover']};
        color: {tokens['text']};
    }}
    QTreeWidget#connectionTree::item:selected {{
        background: {tokens['accent_soft']};
        color: {tokens['accent']};
        border: none;
        outline: 0;
    }}
    QTreeWidget#connectionTree::item:selected:active {{
        background: {tokens['accent_soft']};
        color: {tokens['accent']};
    }}
    QTreeWidget#connectionTree::item:selected:!active {{
        background: {tokens['surface_active']};
        color: {tokens['text']};
    }}
    QTreeWidget#connectionTree::branch {{
        background: transparent;
    }}
    QTreeWidget#connectionTree::branch:selected {{
        background: {tokens['accent_soft']};
    }}
    """

    app.setStyleSheet(scroll_bar + sidebar_qss + _MAIN_WINDOW_QSS.format(**tokens))

    # 强制所有控件重新解析样式（否则 setStyleSheet 后已存在的控件不重绘）
    for widget in app.allWidgets():
        try:
            style = widget.style()
            if style:
                style.unpolish(widget)
                style.polish(widget)
                widget.repaint()
        except RuntimeError:
            pass  # widget 可能已被删除


# ── 弹窗基础样式 ─────────────────────────────────
def build_popup_base_style(theme_or_tokens, extra_qss: str = "") -> str:
    """为各类弹窗/对话框生成统一基础样式。"""
    tokens = get_theme_tokens(theme_or_tokens) if isinstance(theme_or_tokens, str) else dict(theme_or_tokens)
    return f"""
QDialog, QMessageBox {{
    background: {tokens['surface']};
    color: {tokens['text']};
    font-size: 13px;
    border: 1px solid {tokens['accent']};
}}
QWidget {{
    color: {tokens['text']};
}}
QLabel {{
    color: {tokens['text']};
    background: transparent;
}}
QLabel[role="muted"] {{
    color: {tokens['text_muted']};
    font-size: 11px;
}}
QLabel[role="title"] {{
    color: {tokens['text']};
    font-size: 16px;
    font-weight: 700;
}}
QLabel[role="sectionTitle"] {{
    color: {tokens['text']};
    font-size: 15px;
    font-weight: 700;
}}
QLabel[role="sectionHint"] {{
    color: {tokens['text_muted']};
    font-size: 11px;
}}
/* 按钮：Cursor 风格圆角无边框 */
QPushButton {{
    background: transparent;
    color: {tokens['text']};
    border: none;
    border-radius: 4px;
    padding: 2px 6px;
    font-size: 13px;
}}
QPushButton:hover {{
    background: {tokens['surface_hover']};
    color: {tokens['text']};
}}
QPushButton:pressed {{
    background: {tokens['surface_active']};
}}
QPushButton:disabled {{
    background: transparent;
    color: {tokens['text_muted']};
}}
/* 主题色按钮（保存/确认等） */
QPushButton[role="primary"] {{
    background: {tokens['accent']};
    color: #ffffff;
}}
QPushButton[role="primary"]:hover {{
    background: {tokens['accent_hover']};
}}
QPushButton[role="primary"]:pressed {{
    background: {tokens['accent_pressed']};
}}
QPushButton[role="success"] {{
    background: {tokens['success']};
    color: #ffffff;
}}
QPushButton[role="success"]:hover {{
    background: {tokens['success_hover']};
}}
QPushButton[role="success"]:pressed {{
    background: {tokens['success']};
}}
QPushButton[role="danger"] {{
    background: {tokens['danger']};
    color: #ffffff;
}}
QPushButton[role="danger"]:hover {{
    background: {tokens['danger_hover']};
}}
QPushButton[role="danger"]:pressed {{
    background: {tokens['danger']};
}}
/* 输入框 */
QLineEdit, QTextEdit, QPlainTextEdit {{
    background: {tokens['surface']};
    color: {tokens['text']};
    border: 1px solid {tokens['border']};
    border-radius: 10px;
    padding: 1px 10px;
    font-size: 13px;
    selection-background-color: {tokens['selection_bg']};
    selection-color: {tokens['selection_text']};
}}
QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus {{
    border-color: {tokens['accent']};
}}
/* SQL 编辑器 - 底部圆角 */
QTextEdit#sqlEditor {{
    background: {tokens['surface']};
    color: {tokens['text']};
    border: none;
    border-top: 1px solid {tokens['border']};
    border-radius: 4px;
    border-bottom-left-radius: 0;
    border-bottom-right-radius: 0;
    padding: 1px 10px;
    font-size: 13px;
    selection-background-color: {tokens['selection_bg']};
    selection-color: {tokens['selection_text']};
}}
/* 下拉框 */
QComboBox {{
    background: {tokens['surface']};
    color: {tokens['text']};
    border: 1px solid {tokens['border']};
    border-radius: 2px;
    padding: 6px 10px;
    font-size: 13px;
}}
QComboBox:hover {{
    border-color: {tokens['border_strong']};
}}
QComboBox:focus {{
    border-color: {tokens['accent']};
}}
QComboBox::dropDown {{
    border: none;
    background: transparent;
    width: 24px;
}}
QComboBox QAbstractItemView {{
    background: {tokens['surface']};
    border: 1px solid {tokens['border']};
    border-radius: 2px;
    outline: 0;
    selection-background-color: {tokens['accent_soft']};
    selection-color: {tokens['accent']};
    color: {tokens['text']};
}}
QAbstractItemView::item {{
    color: {tokens['text']};
    padding: 4px 8px;
}}
QAbstractItemView::item:hover {{
    background: {tokens['surface_hover']};
    color: {tokens['text']};
}}
QAbstractItemView::item:selected {{
    background: {tokens['accent_soft']};
    color: {tokens['accent']};
}}
/* 复选框 */
QCheckBox {{
    color: {tokens['text']};
    spacing: 6px;
    font-size: 13px;
}}
QCheckBox::indicator {{
    width: 16px;
    height: 16px;
    border: 1.5px solid {tokens['border_strong']};
    border-radius: 2px;
    background: {tokens['surface']};
}}
QCheckBox::indicator:checked {{
    background: {tokens['accent']};
    border-color: {tokens['accent']};
}}
/* 单选框 */
QRadioButton {{
    color: {tokens['text']};
    spacing: 6px;
    font-size: 13px;
}}
QRadioButton::indicator {{
    width: 16px;
    height: 16px;
    border: 1.5px solid {tokens['border_strong']};
    border-radius: 2px;
    background: {tokens['surface']};
}}
QRadioButton::indicator:checked {{
    background: {tokens['accent']};
    border-color: {tokens['accent']};
}}
/* 分组框 */
QGroupBox {{
    color: {tokens['accent']};
    border: 1px solid {tokens['border']};
    border-radius: 2px;
    margin-top: 10px;
    padding-top: 10px;
    font-size: 12px;
    font-weight: 600;
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 10px;
    padding: 0 6px;
}}
/* Tab 部件 */
QTabWidget::pane {{
    border: 1px solid {tokens['border']};
    border-radius: 2px;
    background: {tokens['surface']};
}}
QTabBar::tab {{
    background: {tokens['surface_alt']};
    color: {tokens['text_soft']};
    border: 1px solid {tokens['border']};
    border-bottom: none;
    border-top-left-radius: 4px;
    border-top-right-radius: 4px;
    padding: 3px 10px;
    font-size: 12px;
    margin-right: 2px;
    min-height: 24px;
}}
QTabBar::tab:selected {{
    background: {tokens['surface']};
    color: {tokens['accent']};
    font-weight: 600;
    border-bottom: 2px solid {tokens['accent']};
}}
QTabBar::tab:hover:!selected {{
    background: {tokens['surface_hover']};
    color: {tokens['accent']};
}}
/* 列表 */
QListWidget, QListView {{
    background: {tokens['surface']};
    color: {tokens['text']};
    border: 1px solid {tokens['border']};
    border-radius: 2px;
    outline: 0;
    font-size: 13px;
}}
QListWidget::item:selected, QListView::item:selected {{
    background: {tokens['accent_soft']};
    color: {tokens['accent']};
}}
QListWidget::item:hover:!selected, QListView::item:hover:!selected {{
    background: {tokens['surface_hover']};
}}
/* 表格（已移至 main_window.py 设置） */
/*
QTableWidget, QTableView {{
    background: {tokens['surface']};
    color: {tokens['text']};
    border: 1px solid {tokens['border']};
    border-radius: 2px;
    gridline-color: {tokens['border']};
    font-size: 12px;
    selection-background-color: {tokens['accent_soft']};
}}
QTableWidget::item, QTableView::item {{
    padding: 4px 8px;
}}
QHeaderView::section {{
    background: {tokens['surface_alt']};
    color: {tokens['text_soft']};
    border: none;
    border-bottom: 1px solid {tokens['border']};
    border-right: 1px solid {tokens['border']};
    padding: 6px 10px;
    font-size: 12px;
    font-weight: 600;
}}
*/
/* 滚动条 */
QScrollBar:vertical {{
    background: transparent;
    width: 8px;
    margin: 0;
}}
QScrollBar::handle:vertical {{
    background: {tokens['scroll_handle']};
    border-radius: 2px;
    min-height: 30px;
}}
QScrollBar::handle:vertical:hover {{
    background: {tokens['scroll_handle_hover']};
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0;
    subcontrol-position: none;
}}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
    background: none;
}}
QScrollBar:horizontal {{
    background: transparent;
    height: 8px;
    margin: 0;
}}
QScrollBar::handle:horizontal {{
    background: {tokens['scroll_handle']};
    border-radius: 2px;
    min-width: 30px;
}}
QScrollBar::handle:horizontal:hover {{
    background: {tokens['scroll_handle_hover']};
}}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
    width: 0;
    subcontrol-position: none;
}}
QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {{
    background: none;
}}
/* 工具提示 */
QToolTip {{
    background: {tokens['surface']};
    color: {tokens['text']};
    border: 1px solid {tokens['border']};
    border-radius: 2px;
    padding: 5px 10px;
    font-size: 12px;
}}
/* 进度条 */
QProgressBar {{
    background: {tokens['surface_muted']};
    color: {tokens['text']};
    border: none;
    border-radius: 2px;
    text-align: center;
    font-size: 11px;
}}
QProgressBar::chunk {{
    background: {tokens['accent']};
    border-radius: 2px;
}}
/* 滑块 */
QSlider::groove:horizontal {{
    background: {tokens['border']};
    height: 4px;
    border-radius: 2px;
}}
QSlider::handle:horizontal {{
    background: {tokens['accent']};
    width: 14px;
    height: 14px;
    margin: -5px 0;
    border-radius: 2px;
}}
QSlider::groove:vertical {{
    background: {tokens['border']};
    width: 4px;
    border-radius: 2px;
}}
QSlider::handle:vertical {{
    background: {tokens['accent']};
    width: 14px;
    height: 14px;
    margin: 0 -5px;
    border-radius: 2px;
}}
/* 菜单 */
QMenu {{
    background: {tokens['surface']};
    color: {tokens['text']};
    border: 1px solid {tokens['border']};
    border-radius: 2px;
    padding: 4px;
    font-family: "Microsoft YaHei", "RemixIcon", "Segoe UI", system-ui, sans-serif;
}}
QMenu::item {{
    padding: 7px 24px 7px 14px;
    border-radius: 2px;
    font-size: 13px;
}}
QMenu::item:selected {{
    background: {tokens['accent_soft']};
    color: {tokens['accent']};
}}
QMenu::separator {{
    height: 1px;
    background: {tokens['border']};
    margin: 4px 0;
}}
QMenuBar {{
    background: {tokens['surface']};
    color: {tokens['text']};
    border-bottom: 1px solid {tokens['border']};
    padding: 5px 8px;
    font-size: 13px;
    font-family: "Microsoft YaHei", "RemixIcon", "Segoe UI", system-ui, sans-serif;
}}
QMenuBar::item:selected {{
    background: {tokens['accent_soft']};
    color: {tokens['accent']};
    border-radius: 2px;
}}
/* 状态栏 */
QStatusBar {{
    background: {tokens['surface']};
    color: {tokens['text_muted']};
    border-top: 1px solid {tokens['border']};
    font-size: 12px;
    padding: 2px 8px;
}}
/* 工具栏 */
QToolBar {{
    background: {tokens['surface']};
    border: none;
    spacing: 4px;
    padding: 4px 8px;
}}
QToolBar::separator {{
    background: {tokens['border']};
    width: 1px;
    margin: 4px 8px;
}}
/* 边框窗口 */
QFrame[frameShape="4"], QFrame[frameShape="5"] {{
    color: {tokens['border']};
}}
/* splitter */
QSplitter::handle {{
    background: {tokens['border']};
}}
QSplitter::handle:hover {{
    background: {tokens['accent']};
}}
QSplitter::handle:horizontal {{
    width: 1px;
    margin: 0;
}}
QSplitter::handle:vertical {{
    height: 1px;
    margin: 0;
}}
{extra_qss}
"""


# ── 无边框弹窗样式 ──────────────────────────────────
def build_frameless_dialog_style(theme_or_tokens) -> str:
    """无边框对话框（需要自定义标题栏），统一 2px 圆角边框"""
    tokens = get_theme_tokens(theme_or_tokens) if isinstance(theme_or_tokens, str) else dict(theme_or_tokens)
    return f"""
QDialog {{
    background: {tokens['surface']};
    border: 1px solid {tokens['border']};
    padding: 1px;
}}
"""

def build_dialog_frame(tokens: dict, parent: QDialog, title_bar: QWidget) -> QWidget:
    """创建统一弹窗边框框架（替代 QDialog 的 QSS border）。

    用法（在 _build_ui 开头）：
        frame, frame_layout, inner = build_dialog_frame(tokens, self, self._title_bar)
        # 然后将子控件加到 frame_layout 中
    """
    parent.setStyleSheet(build_popup_base_style(tokens) + """
QDialog { border: none; }
QWidget#dialogContent { background: transparent; }
""")
    root = QVBoxLayout(parent)
    root.setContentsMargins(0, 0, 0, 0)
    root.setSpacing(0)

    frame = QFrame(parent)
    frame.setObjectName("dialogFrame")
    frame.setStyleSheet(
        f"QFrame#dialogFrame {{"
        f"background: {tokens['surface']};"
        f"border: 1px solid {tokens['accent']};"
        f"}}"
    )
    frame_layout = QVBoxLayout(frame)
    frame_layout.setContentsMargins(1, 1, 1, 1)  # 1px 内边距，避免子控件遮挡边框
    frame_layout.setSpacing(0)

    frame_layout.addWidget(title_bar)

    inner = QWidget()
    inner.setObjectName("dialogContent")
    frame_layout.addWidget(inner, stretch=1)

    root.addWidget(frame)
    return frame, frame_layout, inner


# ── 主窗口样式 ─────────────────────────────────────
def build_main_window_style(theme: str = None) -> str:
    """主窗口 QSS"""
    tokens = get_theme_tokens(theme)
    return f"""
/* ── 全局字体 ── */
QWidget, QLabel, QPushButton, QLineEdit, QTextEdit, QMenuBar, QMenu, QToolTip {{
    font-family: "Microsoft YaHei", "RemixIcon", "Segoe UI", system-ui, sans-serif;
}}
/* ── 滚动条 ── */
QScrollBar:vertical {{
    background: transparent;
    width: 8px;
    margin: 0;
}}
QScrollBar::handle:vertical {{
    background: {tokens['scroll_handle']};
    border-radius: 2px;
    min-height: 30px;
}}
QScrollBar::handle:vertical:hover {{
    background: {tokens['scroll_handle_hover']};
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0;
}}
QScrollBar:horizontal {{
    background: transparent;
    height: 8px;
    margin: 0;
}}
QScrollBar::handle:horizontal {{
    background: {tokens['scroll_handle']};
    border-radius: 2px;
    min-width: 30px;
}}
QScrollBar::handle:horizontal:hover {{
    background: {tokens['scroll_handle_hover']};
}}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
    width: 0;
}}
"""


# ── 按钮样式工厂 ─────────────────────────────────────
def build_button_style(theme_or_tokens, variant: str = "default") -> str:
    """生成按钮样式，variant: default | primary | danger | success | ghost"""
    tokens = get_theme_tokens(theme_or_tokens) if isinstance(theme_or_tokens, str) else dict(theme_or_tokens)

    if variant == "primary":
        bg = tokens["accent"]
        hover = tokens["accent_hover"]
        pressed = tokens["accent_pressed"]
        border = tokens["accent"]
        text = "#ffffff"
    elif variant == "danger":
        bg = tokens["danger"]
        hover = tokens["danger_hover"]
        pressed = tokens["danger"]
        border = tokens["danger"]
        text = "#ffffff"
    elif variant == "success":
        bg = tokens["success"]
        hover = tokens["success_hover"]
        pressed = tokens["success"]
        border = tokens["success"]
        text = "#ffffff"
    elif variant == "ghost":
        bg = "transparent"
        hover = tokens["surface_hover"]
        pressed = tokens["surface_active"]
        border = "transparent"
        text = tokens["text"]
    else:
        bg = tokens["surface_alt"]
        hover = tokens["surface_hover"]
        pressed = tokens["surface_active"]
        border = tokens["border"]
        text = tokens["text"]

    return (
        "QPushButton{"
        f"background:{bg};"
        f"color:{text};"
        f"border:none;"
        "border-radius: 4px;"
        "padding:5px 14px;"
        "font-size:13px;"
        "}"
        "QPushButton:hover{"
        f"background:{hover};"
        "}"
        "QPushButton:pressed{"
        f"background:{pressed};"
        "}"
        "QPushButton:disabled{"
        f"background:{tokens['surface_muted']};"
        f"color:{tokens['text_muted']};"
        "}"
    )


# ── 辅助函数 ─────────────────────────────────────────
def is_dark_theme(theme: str = None) -> bool:
    """判断是否为深色主题"""
    if theme is None:
        theme = _resolve_theme()
    return theme == THEME_DARK


def is_willow_theme(theme: str = None) -> bool:
    """判断是否为柳叶绿主题"""
    if theme is None:
        theme = _resolve_theme()
    return theme == THEME_WILLOW






# ── 无边框对话框标题栏辅助 ────────────────────────────────────────────────
def make_frameless_title_bar(
    parent: QDialog,
    title: str,
    tokens: dict,
    title_height: int = 38,
) -> tuple:
    """
    创建统一风格的无边框对话框标题栏（Cursor 风格）。
    返回 (title_bar, title_lbl, close_btn)，方便外部绑定事件。

    用法（标准顺序）:
        title_bar, title_lbl, close_btn = make_frameless_title_bar(
            self, "标题文字", self._tokens)
        close_btn.clicked.connect(self.close)
        # ↓ ↓ ↓ 在 _build_ui() 里先把标题栏加到布局顶 ↓ ↓ ↓
    """
    accent_hover = tokens.get("accent_hover", "#818cf8")
    border = tokens.get("border", "#2a3050")
    surface = tokens.get("surface", "#171a24")
    text = tokens.get("text", "#e8eaf4")
    text_muted = tokens.get("text_muted", "#7a84a8")

    title_bar = QWidget(parent)
    title_bar.setObjectName("dialogTitleBar")
    title_bar.setFixedHeight(title_height)
    title_bar.setStyleSheet(
        f"QWidget#dialogTitleBar {{"
        f"background:{surface};border-bottom:1px solid {border};"
        f"border-radius:0px;"
        f"}}"
    )

    bar_layout = QHBoxLayout(title_bar)
    bar_layout.setContentsMargins(12, 0, 6, 0)
    bar_layout.setSpacing(8)

    # 标题文字
    title_lbl = QLabel(title, title_bar)
    title_lbl.setStyleSheet(
        f"color:{text};font-size:13px;font-weight:600;background:transparent;"
    )
    bar_layout.addWidget(title_lbl)
    bar_layout.addStretch()

    # 关闭按钮
    close_btn = QPushButton("✕", title_bar)
    close_btn.setObjectName("titleBarCloseBtn")
    close_btn.setFixedSize(28, 28)
    close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
    close_btn.setStyleSheet(
        f"QPushButton#titleBarCloseBtn {{"
        f"background:transparent;color:{text_muted};border:none;"
        f"border-radius: 2px;font-size:13px;font-weight:500;"
        f"padding:0px;"
        f"min-width:28px;min-height:28px;"
        f"}}"
        f"QPushButton#titleBarCloseBtn:hover {{"
        f"background:rgba(255,255,255,0.1);color:{text};"
        f"}}"
        f"QPushButton#titleBarCloseBtn:pressed {{"
        f"background:rgba(255,255,255,0.15);"
        f"}}"
    )
    bar_layout.addWidget(close_btn)

    # 拖拽移动
    _drag_pos = None

    def _mousePress(e):
        nonlocal _drag_pos
        if e.button() == Qt.MouseButton.LeftButton:
            _drag_pos = e.globalPosition().toPoint()

    def _mouseMove(e):
        nonlocal _drag_pos
        if _drag_pos is not None and e.buttons() == Qt.MouseButton.LeftButton:
            parent.move(parent.pos() + e.globalPosition().toPoint() - _drag_pos)
            _drag_pos = e.globalPosition().toPoint()

    def _mouseRelease(_):
        nonlocal _drag_pos
        _drag_pos = None

    title_bar.mousePressEvent = _mousePress
    title_bar.mouseMoveEvent = _mouseMove
    title_bar.mouseReleaseEvent = _mouseRelease

    return title_bar, title_lbl, close_btn
