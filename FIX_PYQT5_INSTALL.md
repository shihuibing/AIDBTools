# PyQt5 安装问题快速修复指南

## 问题现象

运行 `build_kylin_x86_offline.sh` 时出现：
```
ModuleNotFoundError: No module named 'PyQt5'
```

## 原因分析

1. **网络问题**：pip 无法从 PyPI 下载 PyQt5
2. **Python 版本不匹配**：系统 Python 版本与 PyQt5 要求的版本不兼容
3. **架构问题**：下载的 wheel 文件与系统架构（x86_64）不匹配

## 解决方案

### 方案一：使用系统 PyQt5（推荐，最快）

如果银河麒麟系统已经安装了 PyQt5：

```bash
# 1. 检查系统是否有 PyQt5
python3 -c "import PyQt5; print('✅ 系统有 PyQt5')"

# 2. 如果有，手动复制到虚拟环境
VENV_DIR="/home/AIDBTools/.venv_offline_build"
SITE_PACKAGES="$VENV_DIR/lib/python3.x/site-packages"  # 根据实际 Python 版本调整

# 获取系统 PyQt5 路径
SYS_PYQT5=$(python3 -c "import PyQt5, os; print(os.path.dirname(PyQt5.__file__))")

# 复制到虚拟环境
cp -rf "$SYS_PYQT5" "$SITE_PACKAGES/"

# 复制 sip（如果需要）
SIP_SYS=$(python3 -c "import sip, os; print(os.path.dirname(sip.__file__))" 2>/dev/null)
if [ -n "$SIP_SYS" ]; then
    cp -rf "$SIP_SYS" "$SITE_PACKAGES/"
fi

# 验证
source "$VENV_DIR/bin/activate"
python -c "import PyQt5; print('✅ PyQt5 导入成功')"
```

### 方案二：先安装系统 PyQt5

如果系统没有 PyQt5，先安装它：

```bash
# 对于 apt 系统（银河麒麟/Ubuntu/Debian）
sudo apt-get update
sudo apt-get install python3-pyqt5 python3-pyqt5.qtcore python3-pyqt5.qtgui python3-pyqt5.qtwidgets

# 对于 dnf/yum 系统（CentOS/OpenEuler）
sudo dnf install python3-PyQt5 python3-qt5
# 或
sudo yum install python3-PyQt5 python3-qt5

# 然后重新运行打包脚本
./build_kylin_x86_offline.sh
```

### 方案三：手动下载 wheel 文件

在有网络的机器上下载，然后复制到目标机器：

```bash
# 1. 在有网的机器上下载
pip download PyQt5>=5.15.0 -d ./pyqt5_wheels

# 2. 复制到目标机器的 offline_packages/python_wheels/ 目录
cp pyqt5_wheels/*.whl /home/AIDBTools/offline_packages/python_wheels/

# 3. 重新运行打包脚本
./build_kylin_x86_offline.sh
```

### 方案四：升级 pip 后重试

```bash
# 激活虚拟环境
source /home/AIDBTools/.venv_offline_build/bin/activate

# 升级 pip
pip install --upgrade pip setuptools wheel

# 尝试直接安装 PyQt5
pip install PyQt5>=5.15.0

# 如果成功，继续运行打包脚本
deactivate
./build_kylin_x86_offline.sh
```

## 诊断命令

运行以下命令帮助诊断问题：

```bash
# 1. 检查 Python 版本
python3 --version

# 2. 检查 pip 版本
pip --version

# 3. 检查系统是否有 PyQt5
python3 -c "import PyQt5; print(PyQt5.__file__)" 2>&1

# 4. 检查网络连接
ping -c 3 pypi.org

# 5. 查看虚拟环境 site-packages
ls -la /home/AIDBTools/.venv_offline_build/lib/python3*/site-packages/ | grep -i pyqt

# 6. 查看已下载的 wheel 文件
ls -lh /home/AIDBTools/offline_packages/python_wheels/*.whl 2>/dev/null | head -10
```

## 常见错误及解决

### 错误 1：`Could not find a version that satisfies the requirement PyQt5`

**原因**：Python 版本太低或 pip 太旧

**解决**：
```bash
# 升级 pip
pip install --upgrade pip

# 或使用兼容版本
pip install "PyQt5>=5.12,<5.15"
```

### 错误 2：`No matching distribution found for PyQt5`

**原因**：没有适合当前架构的 wheel 文件

**解决**：
```bash
# 从源码编译（需要 Qt5 开发工具）
sudo apt-get install qtbase5-dev qttools5-dev
pip install PyQt5>=5.15.0 --no-binary :all:
```

### 错误 3：`ModuleNotFoundError: No module named 'sip'`

**原因**：缺少 sip 模块

**解决**：
```bash
pip install PyQt5-sip
# 或
sudo apt-get install python3-sip
```

## 验证安装

安装完成后，运行以下命令验证：

```bash
source /home/AIDBTools/.venv_offline_build/bin/activate

# 测试 PyQt5
python -c "from PyQt5 import QtCore, QtGui, QtWidgets; print('PyQt5:', QtCore.PYQT_VERSION_STR)"

# 测试其他依赖
python -c "import sqlalchemy; print('SQLAlchemy:', sqlalchemy.__version__)"
python -c "import pandas; print('Pandas:', pandas.__version__)"

deactivate
```

## 联系支持

如果以上方法都无法解决问题，请提供以下信息：

1. `python3 --version` 的输出
2. `pip --version` 的输出
3. `uname -m` 的输出（系统架构）
4. `/etc/os-release` 的内容（系统版本）
5. 完整的错误日志

---

**提示**：银河麒麟 V10 通常预装了 PyQt5，优先使用**方案一**或**方案二**可以快速解决问题。
