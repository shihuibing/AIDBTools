#!/bin/bash
# ============================================================
# AIDBTools Linux 版打包脚本
# 适用：银河麒麟 V10 / 统信UOS / Deepin / Ubuntu / CentOS
# 架构：x86_64 / aarch64 (ARM)
# 用法：chmod +x build_linux.sh && ./build_linux.sh
# ============================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$SCRIPT_DIR/.venv_build"
PYTHON="$VENV_DIR/bin/python"
PIP="$VENV_DIR/bin/pip"
ARCH=$(uname -m)

# ── 每次打包前自动递增补丁版本号 ────────────────────────────────
VER=$(python3 -c "import sys; sys.path.insert(0,'$SCRIPT_DIR'); from version import bump_patch_version; print(bump_patch_version())" 2>/dev/null)
if [ -z "$VER" ]; then
    echo "  ❌ 生成版本号失败"
    exit 1
fi
DIST_DIR="$SCRIPT_DIR/release/linux/v${VER}"
mkdir -p "$DIST_DIR"

echo "================================================"
echo "  AIDBTools v${VER} Linux 打包脚本"
echo "  工作目录: $SCRIPT_DIR"
echo "  系统架构: $ARCH"
echo "  输出目录: $DIST_DIR"
echo "================================================"

# ── 写入平台标识 ──────────────────────────────────────────────
python3 -c "import sys; sys.path.insert(0,'$SCRIPT_DIR'); from version import set_build_platform; set_build_platform('linux'); print('  [OK] BUILD_PLATFORM = linux')"

# ---------- 1. 系统依赖 ----------
echo ""
echo "[1/6] 安装系统依赖..."

is_apt() { command -v apt-get &>/dev/null; }
is_dnf() { command -v dnf &>/dev/null; }
is_yum() { command -v yum &>/dev/null; }

if is_apt; then
    sudo apt-get update -qq
    sudo apt-get install -y -qq \
        python3 python3-pip python3-venv \
        libxcb-xinerama0 libxcb-cursor0 libxcb-icccm4 libxcb-image0 \
        libxcb-keysyms1 libxcb-randr0 libxcb-render-util0 libxcb-shape0 \
        libxkbcommon-x11-0 libgl1 libglib2.0-0 \
        libpq-dev freetds-dev unixodbc-dev \
        patchelf upx-ucl \
        default-jre-headless 2>&1 | tail -5
elif is_dnf; then
    sudo dnf install -y -q \
        python3 python3-pip python3-devel \
        mesa-libGL glib2 xcb-util xcb-util-image xcb-util-keysyms \
        xcb-util-renderutil xcb-util-wm \
        postgresql-devel freetds-devel unixODBC-devel \
        patchelf upx \
        java-11-openjdk-headless 2>&1 | tail -5
elif is_yum; then
    sudo yum install -y -q \
        python3 python3-pip python3-devel \
        mesa-libGL glib2 \
        postgresql-devel freetds-devel unixODBC-devel \
        java-11-openjdk-headless 2>&1 | tail -5
fi
echo "  ✅ 系统依赖就绪"

# ---------- 2. 检查 Java ----------
echo ""
echo "[2/6] 检查 Java 环境..."
if command -v java &>/dev/null; then
    JAVA_VER=$(java -version 2>&1 | head -1)
    echo "  ✅ $JAVA_VER"
    # 导出 JAVA_HOME 供 JPype 使用
    if [ -z "$JAVA_HOME" ]; then
        JAVA_BIN=$(readlink -f $(which java))
        export JAVA_HOME=$(dirname $(dirname $JAVA_BIN))
        echo "  JAVA_HOME = $JAVA_HOME"
    fi
else
    echo "  ⚠️  Java 未找到，jaydebeapi 将不被安装（星环 JDBC 功能需要 Java）"
fi

# ---------- 3. 虚拟环境 ----------
echo ""
echo "[3/6] 创建打包用虚拟环境..."

# 尝试找到可用的 python3（优先 3.10/3.9/3.8，最后 python3）
PYTHON3_CMD=""
for cmd in python3.11 python3.10 python3.9 python3.8 python3; do
    if command -v "$cmd" &>/dev/null; then
        PYTHON3_CMD="$cmd"
        echo "  使用 Python: $PYTHON3_CMD ($(${cmd} --version 2>&1))"
        break
    fi
done

if [ -z "$PYTHON3_CMD" ]; then
    echo "  ❌ 未找到 python3，请先安装 Python 3.8+"
    exit 1
fi

# 确保 venv 模块可用
if ! $PYTHON3_CMD -m venv --help &>/dev/null; then
    echo "  ⚠️  venv 模块不可用，尝试安装..."
    if is_apt; then
        PY_VER=$($PYTHON3_CMD -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
        sudo apt-get install -y -qq "python${PY_VER}-venv" python3-venv 2>/dev/null || true
    fi
fi

# 删除旧的损坏的 venv
rm -rf "$VENV_DIR"

$PYTHON3_CMD -m venv "$VENV_DIR"
$PIP install --upgrade pip setuptools wheel -q
echo "  ✅ 虚拟环境: $VENV_DIR"

# ---------- 4. 安装依赖 ----------
echo ""
echo "[4/6] 安装 Python 依赖包..."
# ── 核心依赖（必须成功）──────────────────────────────────────
$PIP install -q \
    "PySide6>=6.6.0" \
    "sqlalchemy>=2.0" \
    "pymysql>=1.1" \
    "psycopg2-binary>=2.9" \
    "oracledb>=2.0" \
    "pandas>=2.0" \
    "requests>=2.31" \
    "openpyxl>=3.1" \
    "pyinstaller>=6.0"

# ── pymssql（SQL Server，需要 FreeTDS，可能编译失败）─────────
echo "  安装 pymssql（SQL Server 支持）..."
# 先尝试安装 FreeTDS 开发库
if is_apt; then
    sudo apt-get install -y -qq libfreetds-dev freetds-dev 2>/dev/null || true
elif is_dnf; then
    sudo dnf install -y -q freetds-devel 2>/dev/null || true
elif is_yum; then
    sudo yum install -y -q freetds-devel 2>/dev/null || true
fi
# 先尝试预编译二进制包，再尝试从源码编译，都失败就跳过
$PIP install -q --only-binary :all: "pymssql>=2.2" 2>/dev/null || \
    $PIP install -q "pymssql>=2.2" 2>/dev/null || \
    echo "  ⚠️  pymssql 安装失败（SQL Server 连接将不可用，可手动安装: sudo apt install libfreetds-dev && pip install pymssql）"

# ── JDBC 支持（需要 Java）────────────────────────────────────
if command -v java &>/dev/null; then
    $PIP install -q "JPype1>=1.4" "jaydebeapi>=1.2" || \
        echo "  ⚠️  jaydebeapi 安装失败，JDBC 功能将不可用"
fi

# ── ODBC 支持（可选）─────────────────────────────────────────
$PIP install -q "pyodbc>=5.0" 2>/dev/null || \
    echo "  ⚠️  pyodbc 安装失败（可忽略，JDBC 模式仍可用）"

echo "  ✅ Python 依赖安装完成"

# ---------- 5. 打包 ----------
echo ""
echo "[5/6] 开始 PyInstaller 打包（约 3~10 分钟）..."
cd "$SCRIPT_DIR"

rm -rf "$SCRIPT_DIR/dist/AIDBTools" "$SCRIPT_DIR/build" 2>/dev/null || true

$VENV_DIR/bin/pyinstaller --clean AIDBTools_linux.spec

echo "  ✅ 打包完成"

# ---------- 6. 验证 ----------
echo ""
echo "[6/6] 验证输出..."
OUTPUT="$SCRIPT_DIR/dist/AIDBTools"
if [ -f "$OUTPUT" ]; then
    SIZE=$(du -sh "$OUTPUT" | cut -f1)
    FINAL_NAME="AIDBTools_v${VER}_linux_${ARCH}"
    cp "$OUTPUT" "$DIST_DIR/${FINAL_NAME}"
    echo "  ✅ 输出文件: $OUTPUT"
    echo "  📦 文件大小: $SIZE ($ARCH)"
    echo "  📁 发布副本: $DIST_DIR/${FINAL_NAME}"
    echo ""
    echo "================================================"
    echo "  打包成功！"
    echo ""
    echo "  交付清单（复制到目标机器）："
    echo "  ├── dist/AIDBTools          ← 可执行文件"
    echo "  ├── config/                 ← 配置目录"
    echo "  └── drivers/transwarp/      ← 星环驱动包"
    echo ""
    echo "  目标机器运行："
    echo "  chmod +x AIDBTools && ./AIDBTools"
    echo "================================================"
else
    echo "  ❌ 未找到输出文件，请检查上方错误信息"
    # 恢复 BUILD_PLATFORM
    python3 -c "import sys; sys.path.insert(0,'$SCRIPT_DIR'); from version import set_build_platform; set_build_platform('source')"
    exit 1
fi

# ── 恢复 BUILD_PLATFORM ───────────────────────────────────────
python3 -c "import sys; sys.path.insert(0,'$SCRIPT_DIR'); from version import set_build_platform; set_build_platform('source'); print('  [OK] BUILD_PLATFORM 已恢复为 source')"
