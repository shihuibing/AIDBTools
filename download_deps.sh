#!/bin/bash
# ============================================================
# AIDBTools - 依赖包离线下载脚本
# 在【能联网的目标机器（或同架构机器）】上运行一次
# 把所有依赖（含传递依赖）下载到 offline_pkgs/
# 之后可以完全离线安装，也可拷给同架构机器使用
#
# 用法：
#   chmod +x download_deps.sh
#   ./download_deps.sh
#
# 可选参数：
#   --arch aarch64   强制指定架构（默认自动检测）
#   --python 3.9     强制指定 Python 版本（默认自动检测）
# ============================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OFFLINE_DIR="$SCRIPT_DIR/offline_pkgs"
LOG="$SCRIPT_DIR/download_deps.log"
ARCH=$(uname -m)
FORCE_PYTHON=""

# 解析参数
while [[ $# -gt 0 ]]; do
    case "$1" in
        --arch) ARCH="$2"; shift 2 ;;
        --python) FORCE_PYTHON="$2"; shift 2 ;;
        *) shift ;;
    esac
done

echo "=========================================================="
echo "  AIDBTools 依赖包离线下载"
echo "  架构：$ARCH"
echo "  下载目录：$OFFLINE_DIR"
echo "=========================================================="
echo ""

# ── 检查 Python ──────────────────────────────────────────────
PY=""
if [ -n "$FORCE_PYTHON" ]; then
    PY=$(command -v "python$FORCE_PYTHON" 2>/dev/null || command -v python3 2>/dev/null)
else
    for candidate in python3.12 python3.11 python3.10 python3.9 python3; do
        if command -v "$candidate" &>/dev/null; then
            PY=$(command -v "$candidate")
            break
        fi
    done
fi
[ -z "$PY" ] && { echo "❌ 未找到 python3"; exit 1; }
PY_VER=$($PY --version 2>&1)
PY_MINOR=$($PY -c "import sys; print(sys.version_info.minor)")
PY_MAJOR=$($PY -c "import sys; print(sys.version_info.major)")
echo "  Python：$PY ($PY_VER)"

# ── 检查 pip ─────────────────────────────────────────────────
PIP="$PY -m pip"
echo "  pip：$PIP"
echo ""

# ── 创建下载目录 ─────────────────────────────────────────────
mkdir -p "$OFFLINE_DIR"
> "$LOG"  # 清空旧日志

# 国内镜像
MIRROR="https://mirrors.aliyun.com/pypi/simple/"
MIRROR_HOST="mirrors.aliyun.com"

# ── 下载函数（含传递依赖，自动按当前架构）──────────────────
download_pkg() {
    local desc="$1"
    shift
    local pkgs=("$@")
    echo "  ▶ $desc"
    for pkg in "${pkgs[@]}"; do
        echo "    下载：$pkg"
        # 先尝试只下 wheel（快，架构匹配）
        if $PIP download \
            -d "$OFFLINE_DIR" \
            -i "$MIRROR" \
            --trusted-host "$MIRROR_HOST" \
            --prefer-binary \
            "$pkg" >> "$LOG" 2>&1; then
            echo "      ✅ OK"
        else
            echo "      ⚠️  wheel 下载失败，尝试源码包..."
            # 降级：允许下源码包（tar.gz）
            $PIP download \
                -d "$OFFLINE_DIR" \
                -i "$MIRROR" \
                --trusted-host "$MIRROR_HOST" \
                --no-binary :none: \
                "$pkg" >> "$LOG" 2>&1 && echo "      ✅ 源码包 OK" || \
            echo "      ❌ $pkg 下载失败（见 download_deps.log）"
        fi
    done
}

# ── pip/setuptools/wheel 自身（最先下，后续安装需要）────────
echo "  [0/7] 基础工具..."
$PIP download \
    -d "$OFFLINE_DIR" \
    -i "$MIRROR" \
    --trusted-host "$MIRROR_HOST" \
    "pip>=23" "setuptools>=68" "wheel>=0.40" >> "$LOG" 2>&1 && \
    echo "    ✅ pip/setuptools/wheel" || echo "    ⚠️  工具包下载失败（跳过）"
echo ""

# ── UI 框架 ──────────────────────────────────────────────────
echo "  [1/7] UI 框架..."
PYQT_OK=false
echo "    下载：PyQt6>=6.6.0"
if $PIP download \
    -d "$OFFLINE_DIR" \
    -i "$MIRROR" \
    --trusted-host "$MIRROR_HOST" \
    --prefer-binary \
    "PyQt6>=6.6.0" "PyQt6-Qt6" "PyQt6-sip" >> "$LOG" 2>&1; then
    echo "    ✅ PyQt6 下载成功"
    PYQT_OK=true
fi
if ! $PYQT_OK; then
    echo "    ⚠️  PyQt6 下载失败（ARM 无预编译 wheel 属正常），尝试 PyQt5..."
    if $PIP download \
        -d "$OFFLINE_DIR" \
        -i "$MIRROR" \
        --trusted-host "$MIRROR_HOST" \
        --prefer-binary \
        "PyQt5>=5.15" "PyQt5-sip" >> "$LOG" 2>&1; then
        echo "    ✅ PyQt5（备选）下载成功"
        PYQT_OK=true
    else
        echo "    ⚠️  PyQt5/PyQt6 均无预编译 wheel（ARM 架构）"
        echo "       → 目标机器需要手动运行 ./build_pyqt5.sh 从源码编译"
    fi
fi
echo ""

# ── 数据库驱动 ───────────────────────────────────────────────
download_pkg "[2/7] 数据库核心（SQLAlchemy）" \
    "sqlalchemy>=2.0" \
    "greenlet>=3.0"     # sqlalchemy 的关键依赖
echo ""

download_pkg "[3/7] MySQL / MariaDB 驱动" \
    "pymysql>=1.1" \
    "cryptography>=41"  # pymysql 加密依赖
echo ""

download_pkg "[4/7] PostgreSQL 驱动" \
    "psycopg2-binary>=2.9"
echo ""

download_pkg "[5/7] SQL Server / Oracle 驱动" \
    "pymssql>=2.2" \
    "oracledb>=2.0"
echo ""

# ── JDBC 支持 ────────────────────────────────────────────────
echo "  [6/7] JDBC 支持（JPype + jaydebeapi）..."
if $PIP download \
    -d "$OFFLINE_DIR" \
    -i "$MIRROR" \
    --trusted-host "$MIRROR_HOST" \
    --prefer-binary \
    "JPype1>=1.4" "jaydebeapi>=1.2" >> "$LOG" 2>&1; then
    echo "    ✅ JPype1 / jaydebeapi"
else
    echo "    ⚠️  JPype1 无预编译 wheel，需在目标机器联网安装或从源码编译"
fi
echo ""

# ── 数据处理 & 其他 ──────────────────────────────────────────
download_pkg "[7/7] 数据处理 & 工具库" \
    "pandas>=2.0" \
    "numpy>=1.24" \
    "python-dateutil>=2.8" \
    "pytz>=2023" \
    "six>=1.16" \
    "openpyxl>=3.1" \
    "et-xmlfile>=1.1" \
    "requests>=2.31" \
    "urllib3>=2.0" \
    "certifi>=2023" \
    "charset-normalizer>=3.0" \
    "idna>=3.4"
echo ""

# ── ODBC 支持（仅 x86_64 有预编译 wheel）────────────────────
if [ "$ARCH" = "x86_64" ]; then
    echo "  [+] ODBC 支持（x86_64）..."
    $PIP download \
        -d "$OFFLINE_DIR" \
        -i "$MIRROR" \
        --trusted-host "$MIRROR_HOST" \
        --prefer-binary \
        "pyodbc>=5.0" >> "$LOG" 2>&1 && echo "    ✅ pyodbc" || echo "    ⚠️  pyodbc 下载失败"
    echo ""
fi

# ── 统计结果 ─────────────────────────────────────────────────
WHL_COUNT=$(ls "$OFFLINE_DIR"/*.whl 2>/dev/null | wc -l)
TGZ_COUNT=$(ls "$OFFLINE_DIR"/*.tar.gz 2>/dev/null | wc -l)
TOTAL_SIZE=$(du -sh "$OFFLINE_DIR" 2>/dev/null | cut -f1)

echo "=========================================================="
echo "  ✅ 下载完成！"
echo "     wheel 包：$WHL_COUNT 个"
echo "     源码包：  $TGZ_COUNT 个"
echo "     总大小：  $TOTAL_SIZE"
echo "     路径：    $OFFLINE_DIR"
echo ""
echo "  下载日志：$LOG"
echo ""
echo "  后续步骤："
echo "  1. 把整个 AIDBTools 目录（含 offline_pkgs/）拷贝到目标机器"
echo "  2. 在目标机器上运行：./install_kylin.sh"
echo "     （会自动检测 offline_pkgs/ 并离线安装，无需联网）"
echo ""
echo "  注意：PyQt6/PyQt5/JPype1 在 ARM 架构无预编译 wheel"
echo "  → 目标机器需先运行 ./build_pyqt5.sh 编译 PyQt5"
echo "=========================================================="
