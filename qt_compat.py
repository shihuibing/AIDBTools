"""
Qt 兼容层：优先使用 PySide6（LGPL 许可），备选 PyQt6 / PyQt5。
当系统只有 PyQt5 时，模拟 PySide6 API 让代码无需修改即可运行。
适用场景：银河麒麟 V10 / 统信UOS 等国产系统（默认提供 PyQt5）

加载方式（install_kylin.sh / build_arm_kylin.sh 自动处理）：
  将此文件路径写入虚拟环境的 .pth 文件，Python 启动时自动执行。

注意：代码库已全面改用 PySide6 导入（from PySide6...）。
此兼容层确保在缺少 PySide6 的环境下仍能运行。
"""

import sys
import importlib

# 检测已安装的 Qt 绑定
HAS_PYSIDE6 = False
HAS_PYQT6 = False
HAS_PYQT5 = False

try:
    import PySide6  # noqa
    HAS_PYSIDE6 = True
except ImportError:
    pass

try:
    import PyQt6  # noqa
    HAS_PYQT6 = True
except ImportError:
    pass

try:
    import PyQt5  # noqa
    HAS_PYQT5 = True
except ImportError:
    pass

def _patch_pyside6_to_pyqt6():
    """将 PySide6 模块映射到 PyQt6（用于兼容旧代码导入 PyQt6）"""
    if not HAS_PYQT6:
        return
    # 如果代码中仍有 import PyQt6，将其重定向到 PySide6
    # 但我们已经将代码改为 import PySide6，所以可能不需要
    pass

def _patch_pyside6_to_pyqt5():
    """在只有 PyQt5 的系统上模拟 PySide6"""
    if not HAS_PYQT5:
        return
    
    # 模块别名映射：PySide6 -> PyQt5
    _mod_map = {
        'PySide6':                 'PyQt5',
        'PySide6.QtWidgets':       'PyQt5.QtWidgets',
        'PySide6.QtCore':          'PyQt5.QtCore',
        'PySide6.QtGui':           'PyQt5.QtGui',
        'PySide6.QtNetwork':       'PyQt5.QtNetwork',
        'PySide6.QtSvg':           'PyQt5.QtSvg',
        'PySide6.QtSvgWidgets':    'PyQt5.QtSvgWidgets',
        'PySide6.QtPrintSupport':  'PyQt5.QtPrintSupport',
        'PySide6.sip':             'sip',
    }
    
    for fake, real in _mod_map.items():
        if fake not in sys.modules:
            try:
                mod = importlib.import_module(real)
                sys.modules[fake] = mod
            except ImportError:
                pass
    
    # 为 PyQt5 添加 PySide6 风格的 Signal 和 Slot 别名
    try:
        from PyQt5.QtCore import pyqtSignal, pyqtSlot
        import PyQt5.QtCore
        # 在 PyQt5.QtCore 模块上添加 Signal 和 Slot 别名
        if not hasattr(PyQt5.QtCore, 'Signal'):
            PyQt5.QtCore.Signal = pyqtSignal
        if not hasattr(PyQt5.QtCore, 'Slot'):
            PyQt5.QtCore.Slot = pyqtSlot
        # 同时注入到 PySide6.QtCore 模块（如果已被映射）
        if 'PySide6.QtCore' in sys.modules:
            sys.modules['PySide6.QtCore'].Signal = pyqtSignal
            sys.modules['PySide6.QtCore'].Slot = pyqtSlot
    except Exception:
        pass
    
    # 为 PyQt5 添加 PySide6 风格的枚举命名空间（与原有 pyqt5_compat 相同）
    _add_enum_namespaces()

def _add_enum_namespaces():
    """为 PyQt5 添加 PySide6 风格的枚举命名空间"""
    try:
        from PyQt5 import QtCore, QtWidgets, QtGui

        def _add_enum_ns(cls, ns_name, attrs):
            """在 PyQt5 的类上添加 PySide6 风格的枚举命名空间"""
            if not hasattr(cls, ns_name):
                ns = type(ns_name, (), {})()
                for attr in attrs:
                    if hasattr(cls, attr):
                        setattr(ns, attr, getattr(cls, attr))
                setattr(cls, ns_name, ns)

        # Qt.AlignmentFlag
        _add_enum_ns(QtCore.Qt, 'AlignmentFlag', [
            'AlignLeft', 'AlignRight', 'AlignHCenter', 'AlignVCenter',
            'AlignTop', 'AlignBottom', 'AlignCenter', 'AlignJustify',
        ])
        # Qt.ItemFlag
        _add_enum_ns(QtCore.Qt, 'ItemFlag', [
            'NoItemFlags', 'ItemIsEnabled', 'ItemIsSelectable',
            'ItemIsEditable', 'ItemIsCheckable', 'ItemIsUserCheckable',
        ])
        # Qt.CheckState
        _add_enum_ns(QtCore.Qt, 'CheckState', [
            'Unchecked', 'PartiallyChecked', 'Checked',
        ])
        # Qt.WindowType
        _add_enum_ns(QtCore.Qt, 'WindowType', [
            'Widget', 'Window', 'Dialog', 'Sheet', 'Drawer',
            'Popup', 'Tool', 'ToolTip', 'SplashScreen', 'Desktop',
            'SubWindow', 'ForeignWindow', 'CoverWindow',
            'WindowFlags', 'MSWindowsFixedSizeDialogHint',
            'MSWindowsOwnDC', 'BypassWindowManagerHint',
            'X11BypassWindowManagerHint', 'FramelessWindowHint',
            'NoDropShadowWindowHint', 'CustomizeWindowHint',
        ])
        # Qt.CursorShape
        _add_enum_ns(QtCore.Qt, 'CursorShape', [
            'ArrowCursor', 'UpArrowCursor', 'CrossCursor', 'WaitCursor',
            'IBeamCursor', 'SizeVerCursor', 'SizeHorCursor', 'PointingHandCursor',
            'ForbiddenCursor', 'OpenHandCursor', 'ClosedHandCursor', 'BusyCursor',
        ])
        # QSizePolicy.Policy
        _add_enum_ns(QtWidgets.QSizePolicy, 'Policy', [
            'Fixed', 'Minimum', 'Maximum', 'Preferred', 'Expanding',
            'MinimumExpanding', 'Ignored',
        ])
        # QAbstractItemView.SelectionMode
        _add_enum_ns(QtWidgets.QAbstractItemView, 'SelectionMode', [
            'NoSelection', 'SingleSelection', 'MultiSelection',
            'ExtendedSelection', 'ContiguousSelection',
        ])
        # QAbstractItemView.SelectionBehavior
        _add_enum_ns(QtWidgets.QAbstractItemView, 'SelectionBehavior', [
            'SelectItems', 'SelectRows', 'SelectColumns',
        ])
        # QHeaderView.ResizeMode  (PyQt5 叫 ResizeMode，PyQt6 叫 SectionResizeMode)
        if hasattr(QtWidgets.QHeaderView, 'ResizeMode'):
            _add_enum_ns(QtWidgets.QHeaderView, 'SectionResizeMode', [
                'Interactive', 'Fixed', 'Stretch', 'ResizeToContents',
            ])
        # QMessageBox.StandardButton
        _add_enum_ns(QtWidgets.QMessageBox, 'StandardButton', [
            'Ok', 'Open', 'Save', 'Cancel', 'Close', 'Discard',
            'Apply', 'Reset', 'RestoreDefaults', 'Help',
            'SaveAll', 'Yes', 'YesToAll', 'No', 'NoToAll',
            'Abort', 'Retry', 'Ignore', 'NoButton',
        ])
        # QDialogButtonBox.StandardButton
        _add_enum_ns(QtWidgets.QDialogButtonBox, 'StandardButton', [
            'Ok', 'Open', 'Save', 'Cancel', 'Close', 'Discard',
            'Apply', 'Reset', 'RestoreDefaults', 'Help',
            'SaveAll', 'Yes', 'YesToAll', 'No', 'NoToAll',
            'Abort', 'Retry', 'Ignore', 'NoButton',
        ])

    except Exception:
        pass  # 兼容层打补丁失败不影响主程序启动

def _patch():
    """主补丁函数"""
    # 如果已有 PySide6，无需补丁
    if HAS_PYSIDE6:
        # 但为了兼容可能残留的 PyQt6 导入，可以映射 PyQt6 -> PySide6
        # 不过代码已迁移，所以跳过
        return
    
    # 如果有 PyQt6，确保 Signal 和 Slot 别名
    if HAS_PYQT6:
        try:
            from PyQt6.QtCore import pyqtSignal, pyqtSlot
            import PyQt6.QtCore
            if not hasattr(PyQt6.QtCore, 'Signal'):
                PyQt6.QtCore.Signal = pyqtSignal
            if not hasattr(PyQt6.QtCore, 'Slot'):
                PyQt6.QtCore.Slot = pyqtSlot
        except Exception:
            pass
        # 不需要模块映射，因为代码导入的是 PySide6
        # 但如果代码中仍有 import PyQt6，将其映射到 PyQt6 自身（已经存在）
        return
    
    # 只有 PyQt5 的情况：模拟 PySide6
    if HAS_PYQT5:
        _patch_pyside6_to_pyqt5()

# 应用补丁
_patch()

# 保持向后兼容：如果旧代码导入 pyqt5_compat，此模块仍然可用
# 实际上，我们将 pyqt5_compat.py 重命名为 qt_compat.py，但保留旧文件作为别名
# 建议将 pyqt5_compat.py 替换为：from qt_compat import *