#!/bin/bash
# ============================================================
# 诊断 AIDBTools 打包环境
# ============================================================

echo "================================================"
echo "  AIDBTools 打包环境诊断"
echo "================================================"
echo ""

VENV_DIR="/home/AIDBTools/.venv_offline_build"
DEPS_DIR="/home/AIDBTools/offline_packages"

# 1. 检查虚拟环境
echo "[1/6] 检查虚拟环境..."
if [ -d "$VENV_DIR" ]; then
    echo "  ✅ 虚拟环境存在: $VENV_DIR"
    
    # 检查 Python
    if [ -f "$VENV_DIR/bin/python" ]; then
        PY_VER=$("$VENV_DIR/bin/python" --version 2>&1)
        echo "  ✅ Python: $PY_VER"
    else
        echo "  ❌ Python 不存在"
    fi
    
    # 检查 pip
    if [ -f "$VENV_DIR/bin/pip" ]; then
        PIP_VER=$("$VENV_DIR/bin/pip" --version 2>&1)
        echo "  ✅ pip: $PIP_VER"
    else
        echo "  ❌ pip 不存在"
    fi
else
    echo "  ❌ 虚拟环境不存在"
    exit 1
fi

echo ""

# 2. 检查已下载的 wheel 文件
echo "[2/6] 检查离线依赖包..."
if [ -d "$DEPS_DIR/python_wheels" ]; then
    WHEEL_COUNT=$(ls -1 "$DEPS_DIR/python_wheels"/*.whl 2>/dev/null | wc -l)
    echo "  ✅ 已下载 $WHEEL_COUNT 个 .whl 文件"
    
    # 检查关键包
    echo ""
    echo "  关键依赖包:"
    for pkg in PyQt5 sqlalchemy pandas JPype1 pyinstaller; do
        FOUND=$(ls "$DEPS_DIR/python_wheels"/${pkg}*.whl 2>/dev/null | head -1)
        if [ -n "$FOUND" ]; then
            echo "    ✅ $(basename $FOUND)"
        else
            echo "    ❌ $pkg (未找到)"
        fi
    done
else
    echo "  ❌ 离线依赖目录不存在"
fi

echo ""

# 3. 检查已安装的包
echo "[3/6] 检查已安装的 Python 包..."
source "$VENV_DIR/bin/activate"

INSTALLED=$("$VENV_DIR/bin/pip" list 2>/dev/null)
echo "$INSTALLED" | grep -iE "pyqt|sqlalchemy|pandas|jpype|pyinstaller" | head -10

if echo "$INSTALLED" | grep -qi "PyQt5"; then
    echo "  ✅ PyQt5 已安装"
else
    echo "  ❌ PyQt5 未安装"
fi

echo ""

# 4. 测试导入
echo "[4/6] 测试关键模块导入..."

if python -c "import PyQt5" 2>/dev/null; then
    PYQT5_VER=$(python -c "from PyQt5 import QtCore; print(QtCore.PYQT_VERSION_STR)" 2>/dev/null)
    echo "  ✅ PyQt5: $PYQT5_VER"
else
    echo "  ❌ PyQt5 导入失败"
fi

if python -c "import sqlalchemy" 2>/dev/null; then
    SQLA_VER=$(python -c "import sqlalchemy; print(sqlalchemy.__version__)" 2>/dev/null)
    echo "  ✅ SQLAlchemy: $SQLA_VER"
else
    echo "  ❌ SQLAlchemy 导入失败"
fi

if python -c "import jpype" 2>/dev/null; then
    echo "  ✅ JPype1 已安装"
else
    echo "  ❌ JPype1 导入失败"
fi

echo ""

# 5. 检查 site-packages
echo "[5/6] 检查 site-packages 目录..."
SITE_PACKAGES=$(python -c "import site; print(site.getsitepackages()[0])")
echo "  位置: $SITE_PACKAGES"

if [ -d "$SITE_PACKAGES/PyQt5" ]; then
    echo "  ✅ PyQt5 目录存在"
    ls -lh "$SITE_PACKAGES/PyQt5" | head -5
else
    echo "  ❌ PyQt5 目录不存在"
fi

echo ""

# 6. 检查系统库
echo "[6/6] 检查系统 Qt 库..."
if ldconfig -p | grep -q libQt5Core; then
    echo "  ✅ 系统 Qt5 库已安装"
else
    echo "  ⚠️  系统 Qt5 库未安装（可能影响运行）"
    echo "  建议: sudo apt-get install qtbase5-dev"
fi

echo ""
echo "================================================"
echo "  诊断完成"
echo "================================================"
echo ""

# 提供建议
if ! python -c "import PyQt5" 2>/dev/null; then
    echo "⚠️  PyQt5 未正确安装，建议："
    echo ""
    echo "方案 1: 手动从 wheel 安装"
    echo "  source $VENV_DIR/bin/activate"
    echo "  pip install --no-index --find-links=$DEPS_DIR/python_wheels PyQt5>=5.15.0"
    echo ""
    echo "方案 2: 检查系统是否有 PyQt5"
    echo "  python3 -c 'import PyQt5; print(PyQt5.__file__)'"
    echo ""
    echo "方案 3: 重新运行打包脚本（会尝试自动修复）"
    echo "  cd /home/AIDBTools"
    echo "  ./build_kylin_x86_offline.sh"
    echo ""
else
    echo "✅ 环境正常，可以继续打包！"
    echo ""
    echo "运行打包命令："
    echo "  cd /home/AIDBTools"
    echo "  ./build_kylin_x86_offline.sh"
fi

deactivate
