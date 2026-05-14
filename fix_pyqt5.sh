#!/bin/bash
# ============================================================
# PyQt5 快速修复脚本（ARM 银河麒麟）
# 用途：修复虚拟环境中 PyQt5 不可用的问题
# 用法：chmod +x fix_pyqt5.sh && ./fix_pyqt5.sh
# ============================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$SCRIPT_DIR/.venv_arm_build"

echo "================================================"
echo "  PyQt5 快速修复工具"
echo "  工作目录: $SCRIPT_DIR"
echo "================================================"

# 检查虚拟环境
if [ ! -d "$VENV_DIR" ]; then
    echo "❌ 虚拟环境不存在: $VENV_DIR"
    echo "请先运行: ./build_arm_kylin.sh"
    exit 1
fi

PYTHON="$VENV_DIR/bin/python"
SITE_PACKAGES=$($PYTHON -c "import site; print(site.getsitepackages()[0])" 2>/dev/null || true)

if [ -z "$SITE_PACKAGES" ]; then
    echo "❌ 无法获取 site-packages 路径"
    exit 1
fi

echo ""
echo "虚拟环境: $VENV_DIR"
echo "Site-packages: $SITE_PACKAGES"
echo ""

# 检查系统 PyQt5
echo "[1/3] 检查系统 PyQt5..."
SYS_PYQT5=$(python3 -c "import PyQt5, os; print(os.path.dirname(PyQt5.__file__))" 2>/dev/null || true)

if [ -z "$SYS_PYQT5" ]; then
    echo "❌ 系统未安装 PyQt5"
    echo "请运行: sudo dnf install python3-PyQt5"
    exit 1
fi

echo "✅ 系统 PyQt5: $SYS_PYQT5"

# 清理旧的链接/副本
echo ""
echo "[2/3] 清理旧的安装..."
rm -rf "$SITE_PACKAGES/PyQt5" "$SITE_PACKAGES/sip"
rm -f "$SITE_PACKAGES"/PyQt5*.so
echo "✅ 清理完成"

# 复制 PyQt5
echo ""
echo "[3/3] 复制 PyQt5 到虚拟环境（可能需要几分钟）..."
cp -rf "$SYS_PYQT5" "$SITE_PACKAGES/"
echo "✅ PyQt5 复制完成"

# 复制 sip
SIP_SYS=$(python3 -c "import sip, os; print(os.path.dirname(sip.__file__))" 2>/dev/null || true)
if [ -n "$SIP_SYS" ] && [ -d "$SIP_SYS" ]; then
    echo "复制 sip 模块..."
    cp -rf "$SIP_SYS" "$SITE_PACKAGES/"
fi

# 复制 .so 文件
SYS_LIB_DIR=$(dirname "$SYS_PYQT5")
SO_COUNT=0
for lib_file in "$SYS_LIB_DIR"/PyQt5*.so; do
    if [ -f "$lib_file" ]; then
        cp -f "$lib_file" "$SITE_PACKAGES/" 2>/dev/null || true
        SO_COUNT=$((SO_COUNT + 1))
    fi
done
echo "✅ 复制了 $SO_COUNT 个 .so 文件"

# 验证
echo ""
echo "=== 验证安装 ==="
if $PYTHON -c "from PyQt5 import QtCore, QtGui, QtWidgets" 2>/dev/null; then
    PYQT_VER=$($PYTHON -c "from PyQt5.QtCore import PYQT_VERSION_STR; print(PYQT_VERSION_STR)" 2>/dev/null || echo "5.x")
    echo "✅ PyQt5 安装成功！版本: $PYQT_VER"
    echo ""
    echo "现在可以重新运行打包脚本:"
    echo "  ./build_arm_kylin.sh"
else
    echo "❌ 验证失败"
    echo ""
    echo "尝试诊断:"
    $PYTHON -c "import PyQt5" 2>&1 || true
    echo ""
    echo "目录内容:"
    ls -la "$SITE_PACKAGES/PyQt5" 2>/dev/null | head -10 || true
fi

echo ""
echo "================================================"
