#!/bin/bash
# ============================================================
# AIDBTools 银河麒麟 V10 (x86_64) 快速部署脚本
# 用法: chmod +x deploy_kylin_x86.sh && ./deploy_kylin_x86.sh
# ============================================================

set -e

echo "================================================"
echo "  AIDBTools 银河麒麟 V10 (x86_64) 部署脚本"
echo "================================================"
echo ""

# 检查是否为 x86_64 架构
ARCH=$(uname -m)
if [ "$ARCH" != "x86_64" ]; then
    echo "❌ 错误: 当前架构为 $ARCH，此脚本仅支持 x86_64"
    echo "   ARM 架构请使用 install_kylin.sh"
    exit 1
fi

echo "✅ 检测到 x86_64 架构"
echo ""

# ---------- 1. 安装系统依赖 ----------
echo "[1/5] 安装系统依赖..."
sudo apt update -qq

# Qt 运行时依赖
sudo apt install -y -qq \
    libxcb-xinerama0 \
    libxcb-cursor0 \
    libxcb-icccm4 \
    libxcb-image0 \
    libxcb-keysyms1 \
    libxcb-randr0 \
    libxcb-render-util0 \
    libxcb-shape0 \
    libxkbcommon-x11-0 \
    libgl1 \
    libglib2.0-0 \
    fonts-wqy-zenhei \
    fonts-wqy-microhei \
    fonts-noto-cjk \
    unixodbc \
    odbcinst 2>&1 | tail -3

echo "  ✅ Qt 依赖安装完成"

# ---------- 2. 安装 Java ----------
echo ""
echo "[2/5] 安装 Java 环境（用于星环 JDBC 连接）..."
if command -v java &>/dev/null; then
    JAVA_VER=$(java -version 2>&1 | head -1)
    echo "  ✅ Java 已安装: $JAVA_VER"
else
    sudo apt install -y -qq default-jre-headless 2>&1 | tail -3
    echo "  ✅ Java 安装完成"
fi

# 设置 JAVA_HOME
if [ -z "$JAVA_HOME" ]; then
    JAVA_BIN=$(readlink -f $(which java))
    export JAVA_HOME=$(dirname $(dirname $JAVA_BIN))
    echo "  JAVA_HOME = $JAVA_HOME"
    echo "export JAVA_HOME=$JAVA_HOME" >> ~/.profile
fi

# ---------- 3. 安装星环 ODBC 驱动 ----------
echo ""
echo "[3/5] 安装星环 ODBC 驱动..."
ODBC_DEB="drivers/transwarp/odbc/linux/inceptor-connector-odbc-8.37.0.deb"

if [ -f "$ODBC_DEB" ]; then
    sudo dpkg -i "$ODBC_DEB" 2>&1 | tail -3
    echo "  ✅ ODBC 驱动安装完成"
    
    # 验证驱动
    if odbcinst -q -d | grep -q "Inceptor"; then
        echo "  ✅ 驱动注册成功: Inceptor"
    else
        echo "  ⚠️  驱动注册可能失败，请手动检查"
    fi
else
    echo "  ⚠️  未找到 ODBC 安装包: $ODBC_DEB"
    echo "  ℹ️  将使用 JDBC 模式连接星环数据库"
fi

# ---------- 4. 检查 Python 环境 ----------
echo ""
echo "[4/5] 检查 Python 环境..."

PYTHON_CMD=""
for cmd in python3.11 python3.10 python3.9 python3.8 python3; do
    if command -v "$cmd" &>/dev/null; then
        PYTHON_CMD="$cmd"
        break
    fi
done

if [ -z "$PYTHON_CMD" ]; then
    echo "  ❌ 未找到 Python 3，请先安装 Python 3.8+"
    echo "  执行: sudo apt install python3 python3-pip python3-venv"
    exit 1
fi

PY_VER=$($PYTHON_CMD --version 2>&1)
echo "  ✅ Python: $PY_VER"

# ---------- 5. 创建虚拟环境并安装依赖 ----------
echo ""
echo "[5/5] 创建虚拟环境并安装依赖..."

VENV_DIR=".venv"
if [ ! -d "$VENV_DIR" ]; then
    $PYTHON_CMD -m venv "$VENV_DIR"
    echo "  ✅ 虚拟环境创建完成"
else
    echo "  ℹ️  虚拟环境已存在"
fi

# 激活虚拟环境
source "$VENV_DIR/bin/activate"

# 升级 pip
pip install --upgrade pip setuptools wheel -q

# 安装核心依赖
echo "  安装 Python 包（这可能需要几分钟）..."
pip install -q \
    "PyQt6>=6.6.0" \
    "sqlalchemy>=2.0" \
    "pymysql>=1.1" \
    "psycopg2-binary>=2.9" \
    "oracledb>=2.0" \
    "pandas>=2.0" \
    "requests>=2.31" \
    "openpyxl>=3.1" 2>&1 | tail -3

# 安装可选依赖
pip install -q "pyodbc>=5.0" 2>/dev/null || echo "  ⚠️  pyodbc 安装失败（可忽略）"
pip install -q "JPype1>=1.4" "jaydebeapi>=1.2" 2>/dev/null || echo "  ⚠️  jaydebeapi 安装失败（JDBC 功能将不可用）"

echo "  ✅ Python 依赖安装完成"

# ---------- 6. 创建启动脚本 ----------
echo ""
echo "创建启动脚本..."

cat > run.sh << 'EOF'
#!/bin/bash
# AIDBTools 启动脚本
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# 激活虚拟环境
if [ -d ".venv" ]; then
    source .venv/bin/activate
fi

# 设置环境变量
export QT_QPA_PLATFORM=xcb
export DISPLAY=${DISPLAY:-:0}

# 运行程序
python3 main.py "$@"
EOF

chmod +x run.sh
echo "  ✅ 启动脚本: run.sh"

# ---------- 7. 创建桌面快捷方式 ----------
echo ""
echo "创建桌面快捷方式..."

DESKTOP_FILE="$HOME/Desktop/AIDBTools.desktop"
cat > "$DESKTOP_FILE" << EOF
[Desktop Entry]
Version=1.0
Type=Application
Name=AIDBTools
Comment=AI Database Tools - 智能数据库管理工具
Exec=$(pwd)/run.sh
Icon=$(pwd)/icon.png
Terminal=false
Categories=Development;Database;
StartupNotify=true
EOF

chmod +x "$DESKTOP_FILE"
echo "  ✅ 桌面快捷方式已创建"

# ---------- 完成 ----------
echo ""
echo "================================================"
echo "  🎉 部署完成！"
echo ""
echo "  启动方式："
echo "  1. 双击桌面图标 'AIDBTools'"
echo "  2. 命令行: ./run.sh"
echo ""
echo "  配置目录: $(pwd)/config/"
echo "  日志文件: 首次运行后自动生成"
echo ""
echo "  如需重新部署，删除 .venv 目录后重新运行此脚本"
echo "================================================"
