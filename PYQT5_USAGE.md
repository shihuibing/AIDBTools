# Qt 兼容层使用指南（PySide6 / PyQt5 / PyQt6）

## 📌 概述

AIDBTools 现在优先使用 **PySide6**（LGPL 许可，避免法律风险），在国产操作系统上备选 **PyQt5**。项目已内置统一的 Qt 兼容层，确保代码在不同 Qt 绑定下都能正常运行。

## 🔄 自动兼容机制

项目已内置 `qt_compat.py` 兼容层，代码中使用的是 `PySide6` 的导入方式，但在没有 PySide6 的系统上会自动映射到 PyQt6 或 PyQt5。

```python
# 代码中统一使用 PySide6 风格
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt

# pyqt5_compat 会自动将其映射到 PyQt5
```

## 🛠️ ARM 银河麒麟打包

### 前置条件

1. **必须在 ARM aarch64 机器上执行**
2. 系统需安装 Qt5 开发工具

### 打包步骤

```bash
# 1. 赋予执行权限
chmod +x build_arm_kylin.sh

# 2. 执行打包脚本（自动使用 PyQt5）
./build_arm_kylin.sh
```

### 打包脚本功能

`build_arm_kylin.sh` 会自动：

1. ✅ 检测系统架构（必须为 aarch64/arm64）
2. ✅ 安装 Qt5 系统依赖（`qt5-qtbase-devel`）
3. ✅ 创建虚拟环境
4. ✅ 安装 PyQt5（优先使用系统包，其次 pip）
5. ✅ 链接系统 PyQt5 到虚拟环境
6. ✅ 验证 PyQt5 安装
7. ✅ 使用 PyInstaller 打包
8. ✅ 生成 tar.gz 交付包

### 手动安装 PyQt5

如果自动安装失败，可以手动安装：

#### 方法1：使用系统包管理器

```bash
# openEuler/银河麒麟 (dnf)
sudo dnf install -y python3-PyQt5 qt5-qtbase-devel

# Ubuntu/Deepin (apt)
sudo apt-get install -y python3-pyqt5 qtbase5-dev
```

#### 方法2：使用 pip

```bash
pip install PyQt5>=5.15.0
```

## 📦 依赖配置

### requirements_linux.txt

```txt
# UI（银河麒麟/统信UOS 推荐使用 PyQt5）
PyQt5>=5.15.0

# 如果需要 PyQt6，注释掉上面一行，取消注释下面一行
# PyQt6>=6.6.0
```

### AIDBTools_arm_kylin.spec

spec 文件已配置为使用 PyQt5 的隐含导入：

```python
hiddenimports = [
    'PyQt5',
    'PyQt5.QtWidgets',
    'PyQt5.QtCore',
    'PyQt5.QtGui',
    'PyQt5.QtPrintSupport',
    # ... 其他模块
]
```

## 🔧 兼容性说明

### PySide6 → PyQt5/PyQt6 映射

`qt_compat.py` 会自动处理以下映射：

| PySide6 | PyQt5 / PyQt6 |
|---------|---------------|
| `PySide6.QtWidgets` | `PyQt5.QtWidgets` / `PyQt6.QtWidgets` |
| `PySide6.QtCore` | `PyQt5.QtCore` / `PyQt6.QtCore` |
| `PySide6.QtGui` | `PyQt5.QtGui` / `PyQt6.QtGui` |
| `Qt.AlignmentFlag.AlignLeft` | `Qt.AlignLeft` |
| `Qt.ItemFlag.ItemIsEnabled` | `Qt.ItemIsEnabled` |
| `QHeaderView.SectionResizeMode` | `QHeaderView.ResizeMode` |

### 枚举兼容性

PySide6 将枚举移到命名空间下，兼容层会自动添加 PySide6 风格的枚举访问方式：

```python
# PySide6 风格（代码中使用）
Qt.AlignmentFlag.AlignLeft
Qt.ItemFlag.ItemIsEnabled
Qt.CheckState.Checked

# PyQt5 原生风格（兼容层会自动映射）
Qt.AlignLeft
Qt.ItemIsEnabled
Qt.Checked
```

## ⚠️ 注意事项

1. **不要同时安装 PyQt5 和 PyQt6** - 可能导致冲突
2. **ARM 架构限制** - PyQt5/PyQt6 无法跨架构编译，必须在目标架构机器上打包
3. **strip 选项** - ARM 上打包时已关闭 strip，避免动态库段错误
4. **UPX 压缩** - ARM 上已禁用 UPX，可能存在兼容性问题

## 🐛 故障排查

### 问题1：ImportError: No module named 'PySide6'

**解决方案**：确保 `pyqt5_compat.py` 被正确加载

```python
# 在 main.py 开头添加
try:
    import qt_compat
except ImportError:
    pass
```

### 问题2：AttributeError: type object 'Qt' has no attribute 'AlignmentFlag'

**解决方案**：检查 `pyqt5_compat.py` 是否成功加载

```python
python3 -c "import pyqt5_compat; from PyQt6.QtCore import Qt; print(Qt.AlignmentFlag.AlignLeft)"
```

### 问题3：打包后程序启动失败

**可能原因**：
- 缺少系统依赖
- PyQt5 动态库未正确打包

**解决方案**：
```bash
# 检查系统依赖
ldd dist/AIDBTools | grep "not found"

# 安装缺失的依赖
sudo dnf install -y qt5-qtbase
```

## 📚 相关文档

- [build_arm_kylin.sh](build_arm_kylin.sh) - ARM 银河麒麟打包脚本
- [AIDBTools_arm_kylin.spec](AIDBTools_arm_kylin.spec) - PyInstaller 配置文件
- [pyqt5_compat.py](pyqt5_compat.py) - PyQt5/PyQt6 兼容层
- [requirements_linux.txt](requirements_linux.txt) - Linux 依赖列表

## 📞 技术支持

如有问题，请联系：
- 开发者：石慧兵
- 邮箱：1795794877@qq.com
