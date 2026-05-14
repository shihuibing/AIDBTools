#!/bin/bash
echo "=== 系统信息 ==="
uname -a
echo ""

echo "=== Python 版本 ==="
python3 --version
which python3
echo ""

echo "=== PyQt5 基础检查 ==="
python3 -c "import PyQt5; print('PyQt5 导入: OK')" 2>&1 || echo "PyQt5 导入: 失败"
echo ""

echo "=== PyQt5 子模块检查 ==="
for mod in QtCore QtGui QtWidgets QtNetwork QtPrintSupport QtSvg; do
    python3 -c "from PyQt5 import $mod; print('PyQt5.$mod: OK')" 2>&1 || echo "PyQt5.$mod: 缺失"
done
echo ""

echo "=== PyQt5 路径信息 ==="
python3 -c "
import PyQt5
print('PyQt5 路径:', PyQt5.__file__)
import os
print('PyQt5 目录:', os.path.dirname(PyQt5.__file__))
" 2>&1
echo ""

echo "=== PyQt5 目录内容 ==="
PYQT5_DIR=$(python3 -c "import PyQt5, os; print(os.path.dirname(PyQt5.__file__))" 2>/dev/null)
if [ -n "$PYQT5_DIR" ]; then
    ls -la "$PYQT5_DIR" | head -20
else
    echo "无法获取 PyQt5 目录"
fi
echo ""

echo "=== Java & Ant ==="
java -version 2>&1 | head -1
ant -version 2>&1 | head -1 || echo "Ant 缺失"
echo ""

echo "=== 系统包检查 ==="
rpm -qa | grep -iE "pyqt5|qt5-qtbase" 2>/dev/null | head -10 || \
dpkg -l | grep -iE "pyqt5|qt5" 2>/dev/null | head -10 || \
echo "无法检查包管理器"
echo ""

echo "=== 磁盘空间 ==="
df -h . | tail -1
