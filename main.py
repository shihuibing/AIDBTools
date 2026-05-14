import sys
import os
import traceback
import ctypes
import time
os.environ["PYTHONIOENCODING"] = "utf-8"


# ── Windows 原生启动加载提示（在 PyQt 导入前显示）──────────────────────────────
# 使用 Windows API 创建一个简单的加载窗口，不依赖任何 Python GUI 库
def _show_native_splash(message: str = "正在启动 团子 AIDBTools…"):
    """显示原生 Windows 加载窗口，返回窗口句柄"""
    try:
        import ctypes
        from ctypes import wintypes

        user32 = ctypes.windll.user32

        # 注册窗口类
        wc = wintypes.WNDCLASSEXW()
        wc.cbSize = ctypes.sizeof(wc)
        wc.lpfnWndProc = ctypes.WINFUNCTYPE(
            wintypes.LRESULT, wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM
        )(lambda h, m, w, l: user32.DefWindowProcW(h, m, w, l))
        wc.hInstance = ctypes.c_void_p(ctypes.windll.kernel32.GetModuleHandleW(None))
        wc.lpszClassName = "AIDBToolsSplash"
        wc.hCursor = user32.LoadCursorW(None, 32515)  # IDC_WAIT = 32515
        user32.RegisterClassExW(ctypes.byref(wc))

        # 窗口尺寸和位置（居中）
        screen_w = user32.GetSystemMetrics(0)  # SM_CXSCREEN
        screen_h = user32.GetSystemMetrics(1)  # SM_CYSCREEN
        win_w, win_h = 380, 120
        x = (screen_w - win_w) // 2
        y = (screen_h - win_h) // 2

        # 创建窗口
        hwnd = user32.CreateWindowExW(
            0,  # dwExStyle
            "AIDBToolsSplash",  # lpClassName
            message,  # lpWindowName
            0x00CF0000,  # WS_POPUP | WS_VISIBLE | WS_DLGFRAME = 0x00CF0000
            x, y, win_w, win_h,
            None, None, wc.hInstance, None
        )

        # 设置文字
        memdc = user32.GetDC(hwnd)
        user32.SetBkMode(memdc, 1)  # TRANSPARENT
        user32.SetTextColor(memdc, 0x00333333)  # RGB(51,51,51)
        font = user32.CreateFontW(20, 0, 0, 0, 700, 0, 0, 0, 0, 0, 0, 2, 0, "微软雅黑")
        user32.SelectObject(memdc, font)

        # RECT 结构体
        class RECT(ctypes.Structure):
            _fields_ = [("left", wintypes.LONG), ("top", wintypes.LONG),
                         ("right", wintypes.LONG), ("bottom", wintypes.LONG)]
        rect = RECT(x + 20, y + 20, x + win_w - 20, y + win_h - 20)
        user32.DrawTextW(memdc, message, -1, ctypes.byref(rect), 0x0004 | 0x0100)  # DT_CENTER | DT_VCENTER

        # 释放 DC 和字体
        user32.ReleaseDC(hwnd, memdc)
        user32.DeleteObject(font)

        # 显示窗口
        user32.ShowWindow(hwnd, 5)  # SW_SHOW
        user32.UpdateWindow(hwnd)

        return hwnd
    except Exception:
        return None


def _close_native_splash(hwnd):
    """关闭原生启动窗口"""
    if hwnd:
        try:
            import ctypes
            from ctypes import wintypes
            user32 = ctypes.windll.user32
            user32.ShowWindow(hwnd, 0)  # SW_HIDE
            user32.DestroyWindow(hwnd)
            user32.UnregisterClassW("AIDBToolsSplash", None)
        except Exception:
            pass


# 立即显示原生加载窗口（在任何 PyQt 导入前）
_native_splash_hwnd = _show_native_splash()


# ── PyQt6 加载进度对话框（备用，在 MainWindow 初始化时显示）────────────────────
from PySide6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QProgressBar, QApplication
from PySide6.QtCore import Qt, QTimer, QThread, Signal
from PySide6.QtGui import QIcon, QMovie


class _LoadingDialog(QDialog):
    """启动加载提示对话框"""

    def __init__(self, app_icon=None):
        super().__init__()
        self._app_icon = app_icon
        self._step = 0
        self._steps = [
            "正在初始化组件…",
            "正在加载配置…",
            "正在构建界面…",
            "正在连接数据库…",
            "即将就绪…",
        ]
        self._setup_ui()

    def _setup_ui(self):
        self.setWindowTitle("加载中")
        self.setFixedSize(360, 180)
        self.setWindowFlags(
            Qt.WindowType.Dialog
            | Qt.WindowType.WindowTitleHint
            | Qt.WindowType.CustomizeWindowHint
        )
        self.setModal(True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(12)

        # 图标 + 应用名
        top_row = QHBoxLayout()
        top_row.setSpacing(12)

        if self._app_icon and not self._app_icon.isNull():
            icon_label = QLabel()
            icon_label.setFixedSize(48, 48)
            icon_label.setPixmap(self._app_icon.pixmap(48, 48))
            top_row.addWidget(icon_label)

        title_col = QVBoxLayout()
        title_col.setSpacing(2)

        app_name_label = QLabel("团子 AIDBTools")
        app_name_label.setStyleSheet("font-size: 16px; font-weight: bold; color: #333;")
        title_col.addWidget(app_name_label)

        version_label = QLabel(f"版本 {get_version_string()}")
        version_label.setStyleSheet("font-size: 12px; color: #888;")
        title_col.addWidget(version_label)

        top_row.addLayout(title_col)
        top_row.addStretch()
        layout.addLayout(top_row)

        # 进度条
        self._progress = QProgressBar()
        self._progress.setRange(0, 100)
        self._progress.setValue(0)
        self._progress.setTextVisible(False)
        self._progress.setFixedHeight(6)
        self._progress.setStyleSheet("""
            QProgressBar {
                border: none;
                border-radius: 4px;
                background: #e8e8e8;
            }
            QProgressBar::chunk {
                border-radius: 4px;
                background: #4a90d9;
            }
        """)
        layout.addWidget(self._progress)

        # 状态文本
        self._status_label = QLabel(self._steps[0])
        self._status_label.setStyleSheet("font-size: 13px; color: #666;")
        self._status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._status_label)

        # 底部提示
        tip_label = QLabel("首次启动可能需要几秒钟，请稍候…")
        tip_label.setStyleSheet("font-size: 11px; color: #aaa;")
        tip_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(tip_label)

        # 定时更新进度
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._update_progress)
        self._timer.start(400)  # 每 400ms 更新一次

    def _update_progress(self):
        self._step = (self._step + 1) % len(self._steps)
        # 进度递增
        current = self._progress.value()
        if current < 95:
            self._progress.setValue(current + 2)
        self._status_label.setText(self._steps[self._step])

    def finish(self):
        """完成加载，关闭对话框"""
        self._timer.stop()
        self._progress.setValue(100)
        self._status_label.setText("加载完成，正在启动…")
        QTimer.singleShot(200, self.accept)


# 临时函数：获取版本号（在完整导入前定义）
def get_version_string():
    try:
        from version import VERSION
        return VERSION
    except Exception:
        return "unknown"

# ── Vendored Hermes Agent：加入 sys.path（优先于 pip 安装的 hermes-agent）────────
# 即使打包后没有 pip 环境，只要源码存在就能用
_vendored_hermes = os.path.join(os.path.dirname(__file__), "core", "vendor", "hermes-agent")
if os.path.isdir(_vendored_hermes) and _vendored_hermes not in sys.path:
    sys.path.insert(0, _vendored_hermes)

# ── Windows Server / 无 GPU 环境兼容 ──────────────────────────────────────────
# 必须在 QApplication 实例化之前设置，否则 Qt 加载平台插件时已经太晚
if sys.platform == "win32":
    # ── 1. PyInstaller 单文件模式：把解压目录加入 DLL 搜索路径 ──
    # 解决 "DLL load failed while importing QtWidgets: 找不到指定的模块"
    # 根本原因：单文件 exe 解压到 %TEMP%\_MEIxxxxx 后，系统默认不在该目录找 DLL
    _mei_dir = getattr(sys, "_MEIPASS", None)
    if _mei_dir:
        # 方法 A：加入 PATH（最通用）
        os.environ["PATH"] = _mei_dir + os.pathsep + os.environ.get("PATH", "")
        # 方法 B：调用 Windows API AddDllDirectory（Win8+ 更可靠）
        try:
            import ctypes
            ctypes.windll.kernel32.AddDllDirectory(_mei_dir)
        except Exception:
            pass  # 低版本 Windows Server 可能没有此 API，忽略

    # ── 2. 强制使用 windows QPA 插件（避免 Server 找不到平台插件崩溃）──
    if "QT_QPA_PLATFORM" not in os.environ:
        os.environ["QT_QPA_PLATFORM"] = "windows"

    # ── 3. 无 GPU 时强制软件渲染 OpenGL（Server / 虚拟机 / 远程桌面）──
    if "QT_OPENGL" not in os.environ:
        os.environ["QT_OPENGL"] = "software"

    # ── 4. 禁用 D3D12 后端（Server 版通常没有 D3D12 支持）──
    os.environ.setdefault("QSG_RHI_BACKEND", "opengl")

    # ── 5. 明确设置 Qt platform plugin 路径 ──
    # 单文件模式下 Qt 可能找不到 platforms 插件目录
    if _mei_dir:
        _qt_platform_path = os.path.join(_mei_dir, "PyQt6", "Qt6", "plugins", "platforms")
        if os.path.isdir(_qt_platform_path):
            os.environ["QT_QPA_PLATFORM_PLUGIN_PATH"] = _qt_platform_path
        else:
            # 兼容旧打包结构（直接在 _MEIPASS 根目录）
            _qt_platform_path2 = os.path.join(_mei_dir, "platforms")
            if os.path.isdir(_qt_platform_path2):
                os.environ["QT_QPA_PLATFORM_PLUGIN_PATH"] = _qt_platform_path2
# ─────────────────────────────────────────────────────────────────────────────

# ── PyQt5/PyQt6 兼容层（银河麒麟 ARM 自动使用 PyQt5）──
try:
    import pyqt5_compat  # noqa: F401 - 自动注入 PyQt6 别名
except ImportError:
    pass  # 如果 pyqt5_compat 不存在，直接尝试导入 PyQt6

from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QIcon
from ui.main_window import MainWindow
from ui.theme_manager import load_theme, apply_theme
from core.platform_utils import get_icon_path
from version import APP_NAME, APP_FULL_NAME, get_version_string, AUTHOR, AUTHOR_EMAIL



def _excepthook(exc_type, exc_value, exc_tb):
    """全局未捕获异常处理：写到 crash.log 并弹框"""
    msg = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
    log_path = os.path.join(os.path.dirname(__file__), "crash.log")
    try:
        with open(log_path, "a", encoding="utf-8") as f:
            import datetime
            f.write(f"\n{'='*60}\n{datetime.datetime.now()}\n{msg}\n")
    except Exception:
        pass
    print(msg, file=sys.stderr)
    # 显示错误对话框
    try:
        from PySide6.QtWidgets import QMessageBox
        box = QMessageBox()
        box.setWindowTitle("程序错误")
        box.setText("发生未处理的异常，详情已写入 crash.log")
        box.setDetailedText(msg)
        box.exec()
    except Exception:
        pass


sys.excepthook = _excepthook


def _init_windows_app_identity():
    """为 Windows 设置稳定的 AppUserModelID，避免任务栏图标丢失。"""
    if sys.platform != "win32":
        return
    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("com.tuanzi.aidbtools")
    except Exception:
        pass


if __name__ == "__main__":

    print(f"{'='*50}")
    print(f"  {get_version_string()}")
    print(f"  开发者：{AUTHOR}  <{AUTHOR_EMAIL}>")
    print(f"{'='*50}")

    _init_windows_app_identity()
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationDisplayName(APP_FULL_NAME)

    # ── 应用已保存的主题（在窗口创建前） ──
    apply_theme(app, load_theme())

    icon_path = get_icon_path()
    app_icon = None
    if os.path.exists(icon_path):
        app_icon = QIcon(icon_path)
        if not app_icon.isNull():
            app.setWindowIcon(app_icon)

    # ── 显示启动加载对话框（必须在 MainWindow 导入前显示） ──
    loading = _LoadingDialog(app_icon)
    loading.show()
    app.processEvents()  # 立即刷新显示

    # ── 延迟导入 MainWindow，避免阻塞 UI 响应 ──
    # 使用 QTimer.singleShot 让对话框先渲染出来
    window = None

    def _delayed_init():
        global window
        # 关闭原生加载窗口
        _close_native_splash(_native_splash_hwnd)

        # 显示 PyQt 加载对话框
        loading.show()
        app.processEvents()

        # 导入 MainWindow（这里可能耗时）
        from ui.main_window import MainWindow
        window = MainWindow()
        if app_icon and not app_icon.isNull():
            window.setWindowIcon(app_icon)
        # MainWindow 初始化完成，关闭加载对话框并显示主窗口
        loading.finish()
        window.show()
        # 通知窗口加载已完成，可以显示欢迎对话框等
        window._on_loading_finished()

    QTimer.singleShot(50, _delayed_init)
    sys.exit(app.exec())