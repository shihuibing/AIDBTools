"""
iconfont_loader.py
Remix Icon 图标字体加载器 —— 提供统一的 iconfont 图标系统

用法：
    from ui.iconfont_loader import iconfont, Icon

    # 在 QLabel / QPushButton 上显示图标
    label = Icon.label("database", size=16)
    btn = Icon.button("play", "执行", size=14)

    # 获取图标 Unicode 字符
    char = Icon.char("settings")   # 返回 '\uf0e6'

    # 获取 QFont 对象（用于自定义渲染）
    font = iconfont(size=12)

    # 在 QSS / setStyleSheet 中使用
    # font-family 自动跟随主题颜色（color 属性）
"""
from __future__ import annotations

import os
import re
import sys

from PySide6.QtCore import QByteArray, Qt
from PySide6.QtGui import QFont, QFontDatabase, QIcon, QPixmap, QPainter
from PySide6.QtWidgets import QLabel, QPushButton, QToolButton


# ═══════════════════════════════════════════════════════════════════════
#  图标 Unicode 映射表（Remix Icon v4.9.0, 3227 icons）
# ═══════════════════════════════════════════════════════════════════════

ICON_MAP: dict[str, str] = {
    # ── 数据库 / 连接 ──
    'database': '\uec16',
    'database_fill': '\uec15',
    'server': '\uf0e0',
    'server_fill': '\uf0df',
    'plug': '\uf019',
    'plug_fill': '\uf018',
    'link': '\ueeaf',
    'link_unlink': '\ueeb1',
    'links': '\ueeb8',
    'links_fill': '\ueeb7',

    # ── 箭头 / 方向 ──
    'arrow_right': '\uea6e',
    'arrow_down': '\uea4e',
    'arrow_up': '\uea78',
    'arrow_left': '\uea64',
    'arrow_right_line': '\uea6c',
    'arrow_left_line': '\uea60',
    'arrow_up_line': '\uea76',
    'arrow_down_line': '\uea4c',
    'expand_down': '\uea4e',
    'expand_up': '\uea78',
    'expand_left': '\uf321',
    'expand_right': '\uf325',
    'contract_left': '\uf2fd',
    'contract_right': '\uf301',

    # ── 媒体 / 播放 ──
    'play': '\uf00b',
    'play_fill': '\uf00a',
    'play_circle': '\uf009',
    'play_circle_fill': '\uf008',
    'stop': '\uf1a1',
    'stop_fill': '\uf1a0',
    'pause': '\uefd8',
    'pause_fill': '\uefd7',

    # ── 传输 / 同步 ──
    'send': '\uf0da',
    'send_fill': '\uf0d9',
    'download': '\uec5a',
    'download_fill': '\uec59',
    'download_2': '\uec54',
    'upload': '\uf250',
    'upload_fill': '\uf24f',
    'upload_2': '\uf24a',
    'import': '\uf446',
    'import_fill': '\uf445',
    'export': '\uf436',
    'export_fill': '\uf435',
    'file_upload': '\ued15',
    'file_upload_fill': '\ued14',
    'file_download': '\uecd9',
    'file_download_fill': '\uecd8',
    'refresh': '\uf064',
    'refresh_fill': '\uf063',
    'restart': '\uf080',
    'swap': '\uf1cb',
    'swap_fill': '\uf1ca',
    'exchange': '\uecad',
    'exchange_fill': '\uecaa',
    'sync': '\uecad',
    'clockwise': '\ueb95',

    # ── 编辑 / 操作 ──
    'add': '\uea13',
    'add_fill': '\uea12',
    'add_circle': '\uea11',
    'add_circle_fill': '\uea10',
    'add_box': '\uea0f',
    'add_box_fill': '\uea0e',
    'subtract': '\uf1af',
    'delete': '\uec2a',
    'delete_fill': '\uec29',
    'delete_back': '\uec1a',
    'edit': '\uec86',
    'edit_fill': '\uec85',
    'edit_box': '\uec82',
    'check': '\ueb7b',
    'check_fill': '\ueb7a',
    'check_double': '\ueb79',
    'close': '\ueb99',
    'close_fill': '\ueb98',
    'close_circle': '\ueb97',
    'close_circle_fill': '\ueb96',
    'copy': '\uecd5',
    'copy_fill': '\uecd4',
    'clipboard': '\ueb91',
    'clipboard_fill': '\ueb90',
    'paste': '\ueb90',
    'cut': '\uf0c3',
    'cut_fill': '\uf0c2',
    'scissors': '\uf0c3',
    'scissors_fill': '\uf0c2',
    'undo': '\uea58',
    'redo': '\uea5a',
    'eraser': '\uec9f',
    'find_replace': '\ued2b',

    # ── 搜索 / 过滤 ──
    'search': '\uf0d1',
    'search_fill': '\uf0d0',
    'search_2': '\uf0cd',
    'search_eye': '\uf0cf',
    'filter': '\ued27',
    'filter_fill': '\ued26',
    'filter_2': '\ued23',
    'filter_2_fill': '\ued22',
    'filter_3': '\ued25',
    'filter_3_fill': '\ued24',
    'sort_asc': '\uf15f',
    'sort_desc': '\uf160',

    # ── 视图 / 布局 ──
    'eye': '\uecb5',
    'eye_fill': '\uecb4',
    'eye_off': '\uecb7',
    'zoom_in': '\uf2db',
    'zoom_out': '\uf2dd',
    'focus': '\ued4c',
    'fullscreen': '\ued9c',
    'fullscreen_exit': '\ued9a',
    'layout_right': '\uee9b',
    'layout_left': '\uee94',
    'layout_bottom': '\uee8b',
    'layout_top': '\ueea1',
    'layout_column': '\uee8d',
    'layout_grid': '\uee90',
    'layout_row': '\uee9d',
    'sidebar': '\uf45d',

    # ── 菜单 / 导航 ──
    'menu': '\uef3e',
    'menu_fill': '\uef3b',
    'more': '\uef79',
    'more_fill': '\uef78',
    'more_2': '\uef76',
    'apps': '\uea44',
    'apps_fill': '\uea43',

    # ── AI / 聊天 ──
    'robot': '\uf092',
    'robot_fill': '\uf091',
    'chat': '\ueb4d',
    'chat_fill': '\ueb4c',
    'chat_smile': '\ueb73',
    'chat_smile_fill': '\ueb72',
    'chat_new': '\ueb63',
    'chat_new_fill': '\ueb62',
    'sparkling': '\uf36d',
    'sparkling_fill': '\uf36c',
    'sparkling_2': '\uf36a',
    'magic': '\ueeea',
    'magic_fill': '\ueee9',

    # ── 状态 / 提示 ──
    'info': '\uee59',
    'info_fill': '\uee58',
    'warning': '\uea21',
    'warning_fill': '\uea20',
    'error': '\ueca1',
    'error_fill': '\ueca0',
    'success': '\ueb81',
    'success_fill': '\ueb80',
    'loader': '\ueec6',
    'loader_fill': '\ueec5',
    'notification': '\uef9a',
    'notification_fill': '\uef99',
    'notification_2': '\uef92',
    'notification_2_fill': '\uef91',
    'question': '\uf045',
    'question_fill': '\uf044',
    'lightbulb': '\ueea9',
    'lightbulb_fill': '\ueea6',

    # ── 文件 / 文件夹 ──
    'file': '\ueceb',
    'file_fill': '\uece0',
    'file_text': '\ued0f',
    'file_list': '\uecf1',
    'file_add': '\uecc9',
    'file_add_fill': '\uecc8',
    'folder': '\ued6a',
    'folder_fill': '\ued61',
    'folder_open': '\ued70',
    'folder_add': '\ued5a',
    'save': '\uf0b3',
    'save_fill': '\uf0b2',
    'save_2': '\uf0af',
    'save_3': '\uf0b1',
    'archive': '\uea48',
    'archive_fill': '\uea47',
    'archive_2': '\uf3a6',
    'archive_2_fill': '\uf3a5',
    'box': '\uf2f5',
    'box_fill': '\uf2f4',
    'attachment': '\uea86',

    # ── 设置 / 偏好 ──
    'settings': '\uf0e6',
    'settings_fill': '\uf0e5',
    'palette': '\uefc5',
    'tools': '\uf21b',
    'hammer': '\uedef',

    # ── 主题 ──
    'sun': '\uf1bf',
    'moon': '\uef72',
    'moon_line': '\uef75',
    'leaf': '\ueea3',
    'leaf_fill': '\ueea2',
    'theme': '\uebd4',

    # ── 时间 / 日历 ──
    'time': '\uf20f',
    'time_fill': '\uf20e',
    'clock': '\uf215',
    'clock_fill': '\uf212',
    'calendar': '\ueb27',
    'calendar_fill': '\ueb26',
    'schedule': '\uf3f2',

    # ── 收藏 / 社交 ──
    'star': '\uf18b',
    'star_fill': '\uf186',
    'star_s': '\uf18c',
    'star_s_line': '\uf18d',
    'bookmark': '\ueae5',
    'bookmark_fill': '\ueae4',
    'heart': '\uee0f',
    'heart_fill': '\uee0e',
    'thumb_up': '\uf207',
    'thumb_up_fill': '\uf206',
    'like': '\uf206',

    # ── 安全 ──
    'shield': '\uf108',
    'shield_fill': '\uf103',
    'key': '\uee71',
    'key_fill': '\uee70',
    'lock': '\ueece',
    'lock_fill': '\ueecd',

    # ── 用户 / 团队 ──
    'user': '\uf264',
    'user_fill': '\uf25f',
    'team': '\uf1ee',
    'user_add': '\uf25e',
    'user_settings': '\uf26e',

    # ── 代码 / 开发 ──
    'code': '\ueba9',
    'code_fill': '\ueba8',
    'code_box': '\ueba7',
    'code_s_slash': '\uebad',
    'terminal': '\uf1f6',
    'terminal_line': '\uf1f8',
    'braces': '\ueae9',
    'bug': '\ueb07',
    'bug_fill': '\ueb06',
    'cpu': '\uebf0',
    'command': '\uebb8',
    'git_branch': '\uedbd',
    'git_commit': '\uedbf',
    'git_repo': '\uedc7',
    'git_pull': '\uedc3',

    # ── 图表 / 数据 ──
    'bar_chart': '\uea96',
    'pie_chart': '\ueff6',
    'line_chart': '\ueeab',
    'table': '\uf1de',
    'table_fill': '\uf1dd',
    'dashboard': '\uec12',

    # ── 设备 / 系统 ──
    'computer': '\uebca',
    'global': '\uedcf',
    'earth': '\uec7a',
    'wifi': '\uf2c0',
    'wifi_off': '\uf2c2',
    'hard_drive': '\uedf9',
    'cloud': '\ueb9d',
    'cloud_fill': '\ueb9c',
    'cloud_off': '\ueb9f',

    # ── 其他 ──
    'image': '\uee4b',
    'text': '\uf201',
    'window': '\uf2c4',
    'window_fill': '\uf2c3',
    'cursor': '\uec0a',
    'pushpin': '\uf039',
    'pushpin_fill': '\uf038',
    'share': '\uf0fd',
    'share_fill': '\uf0fc',
    'printer': '\uf029',
    'external_link': '\uecaf',
    'flag': '\ued3b',
    'flag_fill': '\ued3a',
    'speed': '\uf177',
    'speed_fill': '\uf176',
    'emotion': '\uec90',
    'emotion_fill': '\uec8b',
    'gift': '\uedbb',
    'trophy': '\uf22f',
    'medal': '\uef28',
    'fire': '\ued33',
    'bold': '\uead1',
    'italic': '\uee6b',
    'underline': '\uf244',
    'strikethrough': '\uf1ab',

    # ── 专注模式 ──
    'focus': '\uf2d6',      # 聚焦/专注图标
    'fullscreen': '\uf2d5',   # 全屏
    'fullscreen-exit': '\uf2d4',  # 退出全屏
    'home': '\uee1f',
    'home_fill': '\uee1e',
    'book': '\uead7',
    'book_fill': '\uead6',
    'book_open': '\ueadb',
    'mail': '\ueef6',
    'mail_fill': '\ueef3',
    'phone': '\uefec',
    'translate': '\uf226',
}


# ═══════════════════════════════════════════════════════════════════════
#  字体加载
# ═══════════════════════════════════════════════════════════════════════

_FONT_FAMILY = "RemixIcon"
_font_loaded = False


def _find_font_path() -> str | None:
    """按优先级查找 remixicon.ttf"""
    # 1. PyInstaller 单文件模式：_MEIPASS
    if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
        p = os.path.join(sys._MEIPASS, 'icons', 'remixicon.ttf')
        if os.path.isfile(p):
            return p

    # 2. 项目 icons/ 目录
    candidates = [
        os.path.join(os.path.dirname(os.path.dirname(__file__)), 'icons', 'remixicon.ttf'),
        os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'icons', 'remixicon.ttf'),
    ]
    for c in candidates:
        if os.path.isfile(c):
            return c

    return None


def _load_font() -> str:
    """加载 TTF 字体，返回字体族名

    必须在 QApplication 实例创建后才能调用 addApplicationFont，
    否则字体无法注册到 Qt 字体系统。
    """
    global _font_loaded, _FONT_FAMILY

    # frozen 调试：写日志到临时文件
    _is_frozen = getattr(sys, 'frozen', False)
    _debug_lines = []
    _debug_lines.append(f"_load_font called, _font_loaded={_font_loaded}, _FONT_FAMILY={repr(_FONT_FAMILY)}, frozen={_is_frozen}")

    if _font_loaded:
        _debug_lines.append("already loaded, returning early")
        _write_debug(_debug_lines)
        return _FONT_FAMILY

    # QFontDatabase.addApplicationFont 需要在 QApplication 创建后调用
    from PySide6.QtWidgets import QApplication
    if QApplication.instance() is None:
        # QApplication 尚未创建，保留 _font_loaded=False，下次调用时重试
        _debug_lines.append("QApplication.instance() is None, returning early (will retry later)")
        _write_debug(_debug_lines)
        return _FONT_FAMILY

    from PySide6.QtGui import QFontDatabase

    # 检查 Qt 字体系统中是否已有此字体（包括大小写不匹配的情况）
    # RemixIcon.ttf 注册为 "remixicon" (小写)，但代码里 _FONT_FAMILY = "RemixIcon"
    _all_families = QFontDatabase.families()
    _debug_lines.append(f"QFontDatabase.families() has {len(_all_families)} entries, remix in names: {[f for f in _all_families if 'remix' in f.lower()]}")
    _matched = next((f for f in _all_families if f.lower() == _FONT_FAMILY.lower()), None)
    if _matched:
        _debug_lines.append(f"Found case-insensitive match: {repr(_matched)}, setting _font_loaded=True")
        _FONT_FAMILY = _matched
        _font_loaded = True
        _write_debug(_debug_lines)
        return _FONT_FAMILY

    path = _find_font_path()
    _debug_lines.append(f"_find_font_path() = {repr(path)}")
    if path:
        font_id = QFontDatabase.addApplicationFont(path)
        _debug_lines.append(f"addApplicationFont font_id={font_id}")
        if font_id >= 0:
            families = QFontDatabase.applicationFontFamilies(font_id)
            _debug_lines.append(f"applicationFontFamilies = {families}")
            if families:
                _FONT_FAMILY = families[0]
                _debug_lines.append(f"Updated _FONT_FAMILY to {repr(_FONT_FAMILY)}")
    else:
        _debug_lines.append("ERROR: _find_font_path returned None - icons/ folder NOT found in frozen bundle!")
        _write_debug(_debug_lines)
        return _FONT_FAMILY

    _font_loaded = True
    _debug_lines.append(f"Final _FONT_FAMILY={repr(_FONT_FAMILY)}")
    _write_debug(_debug_lines)
    return _FONT_FAMILY


def _write_debug(lines):
    """frozen 模式下写调试日志到临时文件"""
    if getattr(sys, 'frozen', False):
        try:
            import tempfile as _tmp
            log_path = os.path.join(_tmp.gettempdir(), 'aidbtools_font_debug.log')
            with open(log_path, 'a', encoding='utf-8') as _f:
                for _line in lines:
                    _f.write(_line + '\n')
                _f.write('---\n')
        except Exception:
            pass


# 模块加载时自动加载字体
_load_font()

# 预编译 PUA 字符正则（用于 log 等文本场景自动包裹 font-family）
_PUA_RE = re.compile(r'[\ue000-\uf8ff]')


def wrap_pua(text: str) -> str:
    """将文本中的 Unicode PUA 字符（iconfont 图标）自动包裹 font-family span，
    使其在 QTextEdit / QLabel 等富文本控件中正确渲染。"""
    return _PUA_RE.sub(
        lambda m: f'<span style="font-family:{_FONT_FAMILY}">{m.group()}</span>',
        text
    )


# ═══════════════════════════════════════════════════════════════════════
#  公开 API
# ═══════════════════════════════════════════════════════════════════════

def iconfont(size: int = 16) -> QFont:
    """返回配置好的图标字体 QFont 对象"""
    # 确保字体已加载（模块导入时 QApplication 可能还未创建）
    _load_font()

    # frozen 调试：验证 QFont 可以正确匹配
    f = QFont(_FONT_FAMILY)
    f.setPixelSize(size)
    # 不使用 NoFontMerging，以便 Qt 对 remixicon 中不存在的字符（如中文）自动回退到系统字体
    if getattr(sys, 'frozen', False):
        _write_debug([f"iconfont({size}): _FONT_FAMILY={repr(_FONT_FAMILY)}, exactMatch={f.exactMatch()}"])
    return f


class Icon:
    """图标工厂 —— 生成可直接用在 PyQt 控件上的图标元素"""

    @staticmethod
    def char(name: str) -> str:
        """获取图标 Unicode 字符；找不到返回空字符串"""
        return ICON_MAP.get(name, '')

    @staticmethod
    def styled_char(name: str) -> str:
        """获取带字体样式的图标 HTML 片段，用于 setText() 且无法单独 setFont 的场景"""
        char = ICON_MAP.get(name, '')
        if not char:
            return ''
        return f'<span style="font-family:{_FONT_FAMILY}">{char}</span>'

    @staticmethod
    def text(name: str) -> str:
        """获取图标的可显示文本（带图标字符，用于 setText）"""
        c = ICON_MAP.get(name, '')
        return c if c else ''

    @staticmethod
    def font(size: int = 16) -> QFont:
        """获取图标字体"""
        return iconfont(size)

    @staticmethod
    def label(name: str, size: int = 16, parent=None) -> QLabel:
        """创建一个只显示图标的 QLabel"""
        lbl = QLabel(ICON_MAP.get(name, ''), parent)
        lbl.setFont(iconfont(size))
        lbl.setFixedSize(size, size)
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        return lbl

    @staticmethod
    def toolbutton(name: str, size: int = 16, parent=None) -> QToolButton:
        """创建一个只显示图标的 QToolButton"""
        btn = QToolButton(parent)
        btn.setText(ICON_MAP.get(name, ''))
        btn.setFont(iconfont(size))
        btn.setFixedSize(size, size)
        btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
        return btn

    @staticmethod
    def qicon(name: str, size: int = 16, color: str | None = None) -> QIcon:
        """
        创建 QIcon（用于 QAction / setIcon 等）
        通过渲染到 QPixmap 实现，color 可选指定颜色。
        若不指定 color，图标会通过 QSS color 属性自动适配主题。
        """
        char = ICON_MAP.get(name, '')
        if not char:
            return QIcon()

        pix = QPixmap(size, size)
        pix.fill(Qt.GlobalColor.transparent)

        painter = QPainter(pix)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        f = iconfont(size)
        if color:
            from PySide6.QtGui import QColor
            f.setStyleStrategy(QFont.StyleStrategy.NoFontMerging)
            painter.setPen(QColor(color))
        painter.setFont(f)
        painter.drawText(pix.rect(), Qt.AlignmentFlag.AlignCenter, char)
        painter.end()

        return QIcon(pix)

    @staticmethod
    def prefixed_text(name: str, label: str, gap: str = ' ') -> str:
        """生成 "图标 + 文字" 组合字符串，用于按钮/菜单的 setText。
        图标字符依赖全局 QSS font-family 中包含 remixicon 字体。"""
        char = ICON_MAP.get(name, '')
        if not char:
            return label
        return f'{char}{gap}{label}'

    @staticmethod
    def svg_icon(filename: str, size: int = 16) -> QIcon:
        """
        从 icons/ 目录下的 SVG 文件加载 QIcon。
        用于需要自定义彩色图标（而非 iconfont 单色图标）的场景。
        """
        _is_frozen = getattr(sys, 'frozen', False)
        _dbg = [f"svg_icon({filename!r}) frozen={_is_frozen}"]

        # 1. PyInstaller 单文件模式
        if _is_frozen and hasattr(sys, '_MEIPASS'):
            p = os.path.join(sys._MEIPASS, 'icons', filename)
            _dbg.append(f"  frozen path: {p} isfile={os.path.isfile(p)}")
            if os.path.isfile(p):
                icon = QIcon(p)
                _dbg.append(f"  QIcon isNull={icon.isNull()}")
                _write_debug(_dbg)
                return icon

        # 2. 项目 icons/ 目录
        candidates = [
            os.path.join(os.path.dirname(os.path.dirname(__file__)), 'icons', filename),
            os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'icons', filename),
        ]
        for c in candidates:
            _dbg.append(f"  candidate: {c} isfile={os.path.isfile(c)}")
            if os.path.isfile(c):
                icon = QIcon(c)
                _dbg.append(f"  QIcon isNull={icon.isNull()}")
                _write_debug(_dbg)
                return icon

        _dbg.append(f"  WARNING: SVG file not found in any path!")
        _write_debug(_dbg)
        return QIcon()