#!/bin/bash
# ============================================================
# AIDBTools x86_64 银河麒麟版打包脚本
# 适用：银河麒麟 V10 x86_64 / 统信UOS x86_64 / Ubuntu x86_64
# 架构：x86_64
# 
# ⚠️  必须在 x86_64 机器上执行！（PySide6 无法跨架构编译）
# 📌 打包后可直接解压使用，无需安装
# 用法：chmod +x build_kylin_x86.sh && ./build_kylin_x86.sh
# ============================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$SCRIPT_DIR/.venv_x86_build"
PYTHON="$VENV_DIR/bin/python"
PIP="$VENV_DIR/bin/pip"
ARCH=$(uname -m)

# ── 架构检查 ──────────────────────────────────────────────
if [ "$ARCH" != "x86_64" ]; then
    echo "================================================"
    echo "  ❌ 当前架构: $ARCH"
    echo "  此脚本必须在 x86_64 机器上运行！"
    echo ""
    echo "  原因：PySide6 等 GUI 库包含 C 扩展，无法跨架构编译。"
    echo "  请将源码复制到 x86_64 机器后执行此脚本。"
    echo "================================================"
    exit 1
fi

# ── 每次打包前自动递增补丁版本号 ─────────────────────────────
VER=$(python3 -c "import sys; sys.path.insert(0,'$SCRIPT_DIR'); from version import bump_patch_version; print(bump_patch_version())" 2>/dev/null)
if [ -z "$VER" ]; then
    echo "  ❌ 生成版本号失败"
    exit 1
fi

DIST_DIR="$SCRIPT_DIR/release/kylin_x86/v${VER}"
mkdir -p "$DIST_DIR"

echo "================================================"
echo "  AIDBTools v${VER} x86_64 银河麒麟打包"
echo "  工作目录: $SCRIPT_DIR"
echo "  系统架构: $ARCH"
echo "  输出目录: $DIST_DIR"
echo "================================================"

# ── 写入平台标识 ─────────────────────────────────────────
python3 -c "import sys; sys.path.insert(0,'$SCRIPT_DIR'); from version import set_build_platform; set_build_platform('kylin_x86'); print('  [OK] BUILD_PLATFORM = kylin_x86')"

# ── 检测包管理器 ─────────────────────────────────────────
is_apt() { command -v apt-get &>/dev/null; }
is_dnf() { command -v dnf &>/dev/null; }
is_yum() { command -v yum &>/dev/null; }

# ========== 1. 系统依赖 ==========
echo ""
echo "[1/7] 安装系统依赖..."

if is_apt; then
    sudo apt-get update -qq
    sudo apt-get install -y -qq \
        python3 python3-pip python3-venv \
        libxcb-xinerama0 libxcb-cursor0 libxcb-icccm4 libxcb-image0 \
        libxcb-keysyms1 libxcb-randr0 libxcb-render-util0 libxcb-shape0 \
        libxkbcommon-x11-0 libgl1 libglib2.0-0 \
        libpq-dev freetds-dev unixodbc-dev \
        patchelf \
        default-jre-headless 2>&1 | tail -5
elif is_dnf; then
    sudo dnf install -y -q \
        python3 python3-pip python3-devel \
        mesa-libGL glib2 xcb-util xcb-util-image xcb-util-keysyms \
        xcb-util-renderutil xcb-util-wm \
        postgresql-devel freetds-devel unixODBC-devel \
        java-11-openjdk-headless 2>&1 | tail -5
elif is_yum; then
    sudo yum install -y -q \
        python3 python3-pip python3-devel \
        mesa-libGL glib2 \
        postgresql-devel freetds-devel unixODBC-devel \
        java-11-openjdk-headless 2>&1 | tail -5
fi
echo "  ✅ 系统依赖就绪"

# ========== 2. 检查 Java ==========
echo ""
echo "[2/7] 检查 Java 环境..."
if command -v java &>/dev/null; then
    JAVA_VER=$(java -version 2>&1 | head -1)
    echo "  ✅ $JAVA_VER"
    if [ -z "$JAVA_HOME" ]; then
        JAVA_BIN=$(readlink -f $(which java))
        export JAVA_HOME=$(dirname $(dirname $JAVA_BIN))
        echo "  JAVA_HOME = $JAVA_HOME"
    fi
else
    echo "  ⚠️  Java 未找到，jaydebeapi 将不被安装（星环 JDBC 功能需要 Java）"
fi

# ========== 3. 虚拟环境 ==========
echo ""
echo "[3/7] 创建打包用虚拟环境..."

PYTHON3_CMD=""
for cmd in python3.11 python3.10 python3.9 python3; do
    if command -v "$cmd" &>/dev/null; then
        PYTHON3_CMD="$cmd"
        echo "  使用 Python: $PYTHON3_CMD ($(${cmd} --version 2>&1))"
        break
    fi
done

if [ -z "$PYTHON3_CMD" ]; then
    echo "  ❌ 未找到 python3"
    exit 1
fi

rm -rf "$VENV_DIR"
$PYTHON3_CMD -m venv "$VENV_DIR"
$PIP install --upgrade pip setuptools wheel -q
echo "  ✅ 虚拟环境: $VENV_DIR"

# ========== 4. 安装 Python 依赖 ==========
echo ""
echo "[4/7] 安装 Python 依赖包（x86_64）..."

# PySide6
echo "  安装 PySide6..."
$PIP install -q -i https://mirrors.aliyun.com/pypi/simple/ "PySide6>=6.6.0" || \
    $PIP install -q "PySide6>=6.6.0"

# 核心依赖
echo "  安装核心依赖..."
$PIP install -q -i https://mirrors.aliyun.com/pypi/simple/ \
    "sqlalchemy>=2.0" \
    "pymysql>=1.1" \
    "psycopg2-binary>=2.9" \
    "oracledb>=2.0" \
    "pandas>=2.0" \
    "requests>=2.31" \
    "openpyxl>=3.1"

# pymssql（SQL Server）
echo "  安装 pymssql（SQL Server 支持）..."
$PIP install -q "pymssql>=2.2" 2>/dev/null || \
    echo "  ⚠️  pymssql 安装失败（SQL Server 连接将不可用）"

# JDBC 支持
if command -v java &>/dev/null; then
    echo "  安装 jaydebeapi（JDBC 支持）..."
    $PIP install -q "JPype1>=1.4" "jaydebeapi>=1.2" || \
        echo "  ⚠️  jaydebeapi 安装失败（星环 JDBC 功能将不可用）"
fi

# pyodbc（可选）
echo "  安装 pyodbc..."
$PIP install -q "pyodbc>=5.0" 2>/dev/null || \
    echo "  ⚠️  pyodbc 安装失败（可忽略）"

# 打包工具
$PIP install -q "pyinstaller>=6.0"

echo "  ✅ Python 依赖安装完成"

# ========== 5. 验证关键依赖 ==========
echo ""
echo "[5/7] 验证关键依赖..."

$PYTHON -c "import PySide6; from PySide6 import QtCore, QtGui, QtWidgets; print('  ✅ PySide6:', PySide6.__version__)"
$PYTHON -c "import sqlalchemy; print('  ✅ SQLAlchemy:', sqlalchemy.__version__)"
echo "  ✅ 依赖验证通过"

# ========== 6. PyInstaller 打包 ==========
echo ""
echo "[6/7] 开始 PyInstaller 打包（约 5~15 分钟）..."
cd "$SCRIPT_DIR"

# 修复驱动文件权限
if [ -d "drivers" ]; then
    chmod -R +r drivers/ 2>/dev/null || true
    find drivers/ -name "*.so" -exec chmod +r {} \; 2>/dev/null || true
fi

rm -rf "$SCRIPT_DIR/dist/AIDBTools" "$SCRIPT_DIR/build" 2>/dev/null || true

$PYTHON -m PyInstaller --clean AIDBTools_linux.spec

echo "  ✅ 打包完成"

# ========== 7. 打包交付物 ==========
echo ""
echo "[7/7] 整理交付包..."

OUTPUT="$SCRIPT_DIR/dist/AIDBTools"
if [ -f "$OUTPUT" ]; then
    SIZE=$(du -sh "$OUTPUT" | cut -f1)
    FINAL_NAME="AIDBTools_v${VER}_kylin_x86_64"
    
    # 创建交付目录
    PKG_DIR="$DIST_DIR/${FINAL_NAME}"
    mkdir -p "$PKG_DIR"
    
    # 复制可执行文件
    cp "$OUTPUT" "$PKG_DIR/"
    
    # 复制配置文件和驱动
    cp -r "$SCRIPT_DIR/config" "$PKG_DIR/" 2>/dev/null || true
    cp -r "$SCRIPT_DIR/drivers" "$PKG_DIR/" 2>/dev/null || true
    cp "$SCRIPT_DIR/icon.png" "$PKG_DIR/" 2>/dev/null || true
    
    # 创建启动脚本
    cat > "$PKG_DIR/run.sh" << 'RUNEOF'
#!/bin/bash
# AIDBTools 启动脚本（银河麒麟 x86_64）
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# 自动探测 Qt 平台
if [ -z "$QT_QPA_PLATFORM" ]; then
    if [ -n "$DISPLAY" ]; then
        export QT_QPA_PLATFORM="xcb"
    elif [ -n "$WAYLAND_DISPLAY" ]; then
        export QT_QPA_PLATFORM="wayland"
    else
        for d in :0 :1 :2; do
            if xdpyinfo -display "$d" &>/dev/null 2>&1; then
                export DISPLAY="$d"
                export QT_QPA_PLATFORM="xcb"
                break
            fi
        done
        [ -z "$QT_QPA_PLATFORM" ] && export QT_QPA_PLATFORM="xcb"
    fi
fi

# 自动探测 JAVA_HOME
if [ -z "$JAVA_HOME" ] && command -v java &>/dev/null; then
    for jvm_dir in \
        /usr/lib/jvm/default-java \
        /usr/lib/jvm/java-11-openjdk-amd64 \
        /usr/lib/jvm/java-17-openjdk-amd64 \
        /usr/lib/jvm/java-8-openjdk-amd64; do
        [ -d "$jvm_dir" ] && export JAVA_HOME="$jvm_dir" && break
    done
    [ -z "$JAVA_HOME" ] && export JAVA_HOME=$(dirname $(dirname $(readlink -f $(which java))))
fi

exec "$SCRIPT_DIR/AIDBTools" "$@"
RUNEOF
    chmod +x "$PKG_DIR/run.sh"
    
    # 创建桌面快捷方式
    cat > "$PKG_DIR/AIDBTools.desktop" << DEOF
[Desktop Entry]
Version=1.0
Type=Application
Name=AIDBTools
GenericName=AI 数据库管理工具
Comment=支持 MySQL/PostgreSQL/Oracle/SQL Server/星环等数据库的 AI 辅助管理工具
Exec=${PKG_DIR}/run.sh
Icon=${PKG_DIR}/icon.png
Terminal=false
Categories=Development;Database;
DEOF
    
    # 创建 README
    cat > "$PKG_DIR/README.txt" << READMEEOF
================================================
  AIDBTools v${VER} - 银河麒麟 x86_64 版
================================================

快速开始：
  1. 确保已安装系统依赖：
     sudo apt install -y libxcb-xinerama0 libxcb-cursor0 \\
         libxkbcommon-x11-0 libgl1 default-jre-headless

  2. （可选）安装星环 ODBC 驱动：
     sudo dpkg -i drivers/transwarp/odbc/linux/*.deb

  3. 运行程序：
     ./run.sh
     
     或双击 AIDBTools.desktop 桌面快捷方式

功能特性：
  ✅ 多数据库连接管理
  ✅ SQL 编辑器（语法高亮、自动补全）
  ✅ 数据浏览和编辑
  ✅ 数据导入/导出
  ✅ AI SQL 生成和优化（需要网络）
  ✅ 数据同步
  ✅ 备份恢复

支持的数据库：
  - MySQL / MariaDB
  - PostgreSQL
  - SQL Server
  - Oracle
  - Transwarp Inceptor（星环）
  - 虚谷数据库
  - OceanBase / TiDB
  - 达梦 / 人大金仓（需单独安装驱动）

离线使用：
  ✅ 本程序已打包所有 Python 依赖
  ✅ 可在无互联网环境下运行
  ⚠️  AI 功能需要网络访问 API
  ⚠️  首次运行需在目标机器安装系统依赖

技术支持：
  查看详细文档：DEPLOY_KYLIN_X86.md
================================================
READMEEOF
    
    # 压缩为 tar.gz
    cd "$DIST_DIR"
    tar czf "${FINAL_NAME}.tar.gz" "${FINAL_NAME}/"
    rm -rf "${FINAL_NAME}/"
    
    TAR_SIZE=$(du -sh "${FINAL_NAME}.tar.gz" | cut -f1)
    
    echo ""
    echo "================================================"
    echo "  ✅ x86_64 银河麒麟版打包成功！"
    echo ""
    echo "  版本: v${VER}"
    echo "  平台: 银河麒麟 x86_64"
    echo "  文件: ${FINAL_NAME}.tar.gz"
    echo "  大小: ${TAR_SIZE}"
    echo "  位置: $DIST_DIR/${FINAL_NAME}.tar.gz"
    echo ""
    echo "  部署方式（目标机器）："
    echo "  1. 解压: tar xzf ${FINAL_NAME}.tar.gz"
    echo "  2. 进入目录: cd ${FINAL_NAME}"
    echo "  3. 运行: ./run.sh"
    echo "  4. 或双击 AIDBTools.desktop 桌面快捷方式"
    echo ""
    echo "  注意：首次运行前请安装系统依赖（见 README.txt）"
    echo "================================================"
else
    echo "  ❌ 未找到输出文件，请检查上方错误信息"
    python3 -c "import sys; sys.path.insert(0,'$SCRIPT_DIR'); from version import set_build_platform; set_build_platform('source')"
    exit 1
fi

# ── 恢复 BUILD_PLATFORM ───────────────────────────────────────
python3 -c "import sys; sys.path.insert(0,'$SCRIPT_DIR'); from version import set_build_platform; set_build_platform('source'); print('  [OK] BUILD_PLATFORM 已恢复为 source')"
