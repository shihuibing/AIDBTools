#!/bin/bash
# 快速检查当前打包环境状态

echo "=== 检查虚拟环境 ==="
VENV="/home/AIDBTools/.venv_offline_build"

if [ -f "$VENV/bin/python" ]; then
    echo "✅ 虚拟环境存在"
    
    # 激活虚拟环境
    source "$VENV/bin/activate"
    
    echo ""
    echo "=== 已安装的包 ==="
    pip list 2>/dev/null | grep -iE "pyqt|sqlalchemy|pandas|jpype|pyinstaller|cryptography"
    
    echo ""
    echo "=== 测试关键模块 ==="
    
    # PyQt5
    if python -c "import PyQt5" 2>/dev/null; then
        VER=$(python -c "from PyQt5 import QtCore; print(QtCore.PYQT_VERSION_STR)" 2>/dev/null)
        echo "✅ PyQt5: $VER"
    else
        echo "❌ PyQt5: 未安装"
    fi
    
    # SQLAlchemy
    if python -c "import sqlalchemy" 2>/dev/null; then
        VER=$(python -c "import sqlalchemy; print(sqlalchemy.__version__)" 2>/dev/null)
        echo "✅ SQLAlchemy: $VER"
    else
        echo "❌ SQLAlchemy: 未安装"
    fi
    
    # Pandas
    if python -c "import pandas" 2>/dev/null; then
        VER=$(python -c "import pandas; print(pandas.__version__)" 2>/dev/null)
        echo "✅ Pandas: $VER"
    else
        echo "❌ Pandas: 未安装（可能正在安装中）"
    fi
    
    # JPype1
    if python -c "import jpype" 2>/dev/null; then
        echo "✅ JPype1: 已安装"
    else
        echo "❌ JPype1: 未安装（可能正在安装中）"
    fi
    
    # PyInstaller
    if python -c "import PyInstaller" 2>/dev/null; then
        echo "✅ PyInstaller: 已安装"
    else
        echo "❌ PyInstaller: 未安装"
    fi
    
    deactivate
else
    echo "❌ 虚拟环境不存在"
fi

echo ""
echo "=== 建议 ==="
if ! python -c "import pandas" 2>/dev/null; then
    echo "Pandas 或 JPype1 可能还在安装中，请等待..."
    echo ""
    echo "或者手动安装剩余的包："
    echo "  source $VENV/bin/activate"
    echo "  pip install --no-index --find-links=/home/AIDBTools/offline_packages/python_wheels pandas>=2.0 JPype1>=1.2 jaydebeapi>=1.1 pymssql>=2.1 pyinstaller>=5.0"
    echo "  deactivate"
    echo ""
    echo "然后重新运行打包脚本"
fi
