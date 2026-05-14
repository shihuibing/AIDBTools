"""
PyQt5 兼容层（已升级为统一的 Qt 兼容层）
优先使用 PySide6（LGPL 许可），备选 PyQt6 / PyQt5。
当系统只有 PyQt5 时，模拟 PySide6 API 让代码无需修改即可运行。

此文件现在作为 qt_compat.py 的别名，保持向后兼容。
实际功能由 qt_compat.py 提供。
"""

# 直接导入 qt_compat 以应用补丁
from qt_compat import *
# 导出 qt_compat 的所有公有符号，确保 pyqt5_compat 模块对象可用
import qt_compat as _qt_compat
import sys
sys.modules[__name__] = _qt_compat

# 保持原有模块属性
__doc__ = _qt_compat.__doc__
__file__ = _qt_compat.__file__ if hasattr(_qt_compat, '__file__') else __file__
__version__ = "1.1"  # 标记为升级版