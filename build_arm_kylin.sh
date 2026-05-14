#!/bin/bash
# ============================================================
# AIDBTools ARM aarch64 银河麒麟版打包脚本
# 适用：银河麒麟 V10 ARM / 统信UOS ARM / Ubuntu ARM
# 架构：aarch64 (ARM64)
# 
# ⚠️  必须在 ARM 机器上执行！（PyQt5/PyQt6 无法跨架构编译）
# 📌 使用 PyQt5（银河麒麟系统兼容性更好）
# 用法：chmod +x build_arm_kylin.sh && ./build_arm_kylin.sh
# ============================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$SCRIPT_DIR/.venv_arm_build"
PYTHON="$VENV_DIR/bin/python"
PIP="$VENV_DIR/bin/pip"
ARCH=$(uname -m)

# ── 架构检查 ──────────────────────────────────────────────
if [ "$ARCH" != "aarch64" ] && [ "$ARCH" != "arm64" ]; then
    echo "================================================"
    echo "  ❌ 当前架构: $ARCH"
    echo "  此脚本必须在 ARM aarch64 机器上运行！"
    echo ""
    echo "  原因：PyQt6 等 GUI 库包含 C 扩展，无法跨架构编译。"
    echo "  请将源码复制到 ARM 机器后执行此脚本。"
    echo "================================================"
    exit 1
fi

# ── 每次打包前自动递增补丁版本号 ─────────────────────────────
VER=$(python3 -c "import sys; sys.path.insert(0,'$SCRIPT_DIR'); from version import bump_patch_version; print(bump_patch_version())" 2>/dev/null)
if [ -z "$VER" ]; then
    echo "  ❌ 生成版本号失败"
    exit 1
fi

DIST_DIR="$SCRIPT_DIR/release/kylin_arm/v${VER}"
mkdir -p "$DIST_DIR"

echo "================================================"
echo "  AIDBTools v${VER} ARM 银河麒麟打包"
echo "  工作目录: $SCRIPT_DIR"
echo "  系统架构: $ARCH"
echo "  输出目录: $DIST_DIR"
echo "================================================"

# ── 写入平台标识 ─────────────────────────────────────────
python3 -c "import sys; sys.path.insert(0,'$SCRIPT_DIR'); from version import set_build_platform; set_build_platform('kylin_arm'); print('  [OK] BUILD_PLATFORM = kylin_arm')"

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
        default-jre-headless ant \
        build-essential \
        qtbase5-dev qttools5-dev 2>&1 | tail -5
elif is_dnf; then
    sudo dnf install -y -q \
        python3 python3-pip python3-devel \
        mesa-libGL glib2 xcb-util xcb-util-image xcb-util-keysyms \
        xcb-util-renderutil xcb-util-wm \
        postgresql-devel freetds-devel unixODBC-devel \
        java-11-openjdk-devel ant \
        gcc gcc-c++ make \
        qt5-qtbase-devel qt5-qttools-devel 2>&1 | tail -5
elif is_yum; then
    sudo yum install -y -q \
        python3 python3-pip python3-devel \
        mesa-libGL glib2 \
        postgresql-devel freetds-devel unixODBC-devel \
        java-11-openjdk-devel ant \
        gcc gcc-c++ make \
        qt5-qtbase-devel qt5-qttools-devel 2>&1 | tail -5
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
echo "[4/7] 安装 Python 依赖包（ARM aarch64）..."

# ── 先把系统 PyQt6/PyQt5 链接到虚拟环境 ──────────────────
link_sys_pyqt_to_venv() {
    local mod="$1"
    SITE_PACKAGES=$($PYTHON -c "import site; print(site.getsitepackages()[0])" 2>/dev/null || true)
    [ -z "$SITE_PACKAGES" ] && return 1
    
    # 使用系统 python3 查找模块路径
    SYS_MOD=$(python3 -c "import $mod, os; print(os.path.dirname($mod.__file__))" 2>/dev/null || true)
    if [ -n "$SYS_MOD" ] && [ -d "$SYS_MOD" ]; then
        # 对于 PyQt5，直接复制整个目录（银河麒麟需要完整副本）
        if [ "$mod" = "PyQt5" ]; then
            echo "  复制系统 PyQt5 到虚拟环境（可能需几分钟）..."
            cp -rf "$SYS_MOD" "$SITE_PACKAGES/"
            
            # 同时处理 sip 模块
            SIP_SYS=$(python3 -c "import sip, os; print(os.path.dirname(sip.__file__))" 2>/dev/null || true)
            if [ -n "$SIP_SYS" ] && [ -d "$SIP_SYS" ]; then
                cp -rf "$SIP_SYS" "$SITE_PACKAGES/" 2>/dev/null || true
            fi
            
            # 复制相关的 .so 文件
            SYS_PYQT5_LIBS=$(dirname "$SYS_MOD")
            for lib_file in "$SYS_PYQT5_LIBS"/PyQt5*.so; do
                if [ -f "$lib_file" ]; then
                    cp -f "$lib_file" "$SITE_PACKAGES/" 2>/dev/null || true
                fi
            done
            
            echo "  ✅ 系统 ${mod} 已复制到虚拟环境：$SYS_MOD"
        else
            # 其他模块使用符号链接
            ln -sf "$SYS_MOD" "$SITE_PACKAGES/$mod"
            echo "  ✅ 系统 ${mod} 已链接到虚拟环境：$SYS_MOD"
        fi
        return 0
    fi
    return 1
}

# ── PyQt5：先检查系统已有的，再尝试安装（银河麒麟兼容性更好）──
PYQT5_OK=false

# 1. 检查系统是否已有 PyQt5（银河麒麟/统信UOS 常见）
if python3 -c "import PyQt5" 2>/dev/null; then
    echo "  ✅ 检测到系统 PyQt5，链接到虚拟环境..."
    link_sys_pyqt_to_venv PyQt5 && PYQT5_OK=true || true
fi

# 2. 检查虚拟环境中是否已有
if ! $PYQT5_OK && $PYTHON -c "import PyQt5" 2>/dev/null; then
    echo "  ✅ 虚拟环境中已有 PyQt5"
    PYQT5_OK=true
fi

# 3. 都没有 → 尝试 pip 安装
if ! $PYQT5_OK; then
    echo "  安装 PyQt5..."
    
    # 3a. 尝试 ARM 预编译包
    PIP_ERR=$($PIP install -q "PyQt5>=5.15.0" 2>&1)
    if echo "$PIP_ERR" | grep -qE "Successfully installed|already satisfied"; then
        PYQT5_OK=true
        echo "  ✅ PyQt5（pip）安装成功"
    else
        echo "  ⚠️  pip 安装失败，缺少 qmake"
        echo "  尝试安装 Qt5 开发工具..."
        
        # 3b. 安装 Qt5 开发包（openEuler/银河麒麟）
        if is_dnf; then
            sudo dnf install -y -q qt5-qtbase-devel qt5-qttools-devel 2>&1 | tail -3 || true
        elif is_yum; then
            sudo yum install -y -q qt5-qtbase-devel qt5-qttools-devel 2>&1 | tail -3 || true
        elif is_apt; then
            sudo apt-get install -y -qq qtbase5-dev qttools5-dev 2>&1 | tail -3 || true
        fi
        
        # 检查 qmake 是否就绪
        QMAKE_PATH=$(command -v qmake-qt5 || command -v qmake || true)
        if [ -n "$QMAKE_PATH" ]; then
            echo "  ✅ 找到 qmake: $QMAKE_PATH"
            export QT_SELECT=qt5
            PIP_ERR2=$($PIP install "PyQt5>=5.15.0" -i https://mirrors.aliyun.com/pypi/simple/ 2>&1)
            if echo "$PIP_ERR2" | grep -qE "Successfully installed|already satisfied"; then
                PYQT5_OK=true
                echo "  ✅ PyQt5 从源码编译成功"
            else
                echo "  ⚠️  编译仍失败，尝试系统包..."
                # 3c. 尝试系统包
                if is_dnf; then
                    sudo dnf install -y -q python3-PyQt5 python3-qt5 PyQt5 2>/dev/null || true
                elif is_apt; then
                    sudo apt-get install -y -qq python3-pyqt5 python3-qt5 2>/dev/null || true
                fi
                python3 -c "import PyQt5" 2>/dev/null && link_sys_pyqt_to_venv PyQt5 && PYQT5_OK=true || true
            fi
        else
            echo "  ❌ 未找到 qmake，无法编译 PyQt5"
            echo "  请手动安装 Qt5 开发工具："
            if is_dnf; then
                echo "    sudo dnf install qt5-qtbase-devel"
            elif is_yum; then
                echo "    sudo yum install qt5-qtbase-devel"
            fi
            echo "  然后重新运行此脚本"
            exit 1
        fi
    fi
fi

if ! $PYQT5_OK; then
    echo ""
    echo "  ❌ PyQt5 安装失败！请手动解决后重试。"
    exit 1
fi

# 数据库驱动
echo "  安装数据库驱动..."
$PIP install -q -i https://mirrors.aliyun.com/pypi/simple/ \
    "sqlalchemy>=2.0" \
    "pymysql>=1.1" \
    "psycopg2-binary>=2.9" \
    "oracledb>=2.0" \
    "pandas>=2.0" \
    "requests>=2.31" \
    "openpyxl>=3.1"

# pymssql（需要 FreeTDS）
echo "  安装 pymssql（SQL Server 支持）..."
$PIP install -q "pymssql>=2.2" 2>/dev/null || \
    echo "  ⚠️  pymssql 安装失败（SQL Server 连接将不可用）"

# JDBC 支持（需要 Apache Ant）
if command -v java &>/dev/null; then
    echo "  检查 Apache Ant..."
    if ! command -v ant &>/dev/null; then
        echo "  ⚠️  Apache Ant 未找到，尝试安装..."
        if is_dnf; then
            sudo dnf install -y -q apache-ant 2>&1 | tail -3 || true
        elif is_yum; then
            sudo yum install -y -q apache-ant 2>&1 | tail -3 || true
        elif is_apt; then
            sudo apt-get install -y -qq ant 2>&1 | tail -3 || true
        fi
    fi
    
    if command -v ant &>/dev/null; then
        echo "  ✅ Apache Ant: $(ant -version 2>&1 | head -1)"
        echo "  安装 jaydebeapi（JDBC 支持）..."
        $PIP install -q "JPype1>=1.4" "jaydebeapi>=1.2" || \
            echo "  ⚠️  jaydebeapi 安装失败（星环 JDBC 功能将不可用）"
    else
        echo "  ⚠️  Apache Ant 未安装，跳过 jaydebeapi（星环 JDBC 功能将不可用）"
        echo "  如需使用星环数据库，请手动安装: sudo dnf install apache-ant"
    fi
fi

# pyodbc（可选，用于星环 ODBC）
echo "  安装 pyodbc..."
$PIP install -q "pyodbc>=5.0" 2>/dev/null || \
    echo "  ⚠️  pyodbc 安装失败（可忽略）"

# 打包工具
$PIP install -q "pyinstaller>=6.0"

echo "  ✅ Python 依赖安装完成"

# ========== 5. 验证关键依赖 ==========
echo ""
echo "[5/7] 验证关键依赖..."

# 验证 PyQt5（如果失败，尝试重新链接）
if ! $PYTHON -c "import PyQt5" 2>/dev/null; then
    echo "  ⚠️  虚拟环境中 PyQt5 不可用，尝试重新链接..."
    
    # 获取系统 PyQt5 路径
    SYS_PYQT5=$(python3 -c "import PyQt5, os; print(os.path.dirname(PyQt5.__file__))" 2>/dev/null || true)
    SITE_PACKAGES=$($PYTHON -c "import site; print(site.getsitepackages()[0])" 2>/dev/null || true)
    
    if [ -n "$SYS_PYQT5" ] && [ -n "$SITE_PACKAGES" ]; then
        # 删除旧的链接
        rm -f "$SITE_PACKAGES/PyQt5"
        # 创建新的符号链接
        ln -sf "$SYS_PYQT5" "$SITE_PACKAGES/PyQt5"
        
        # 同时链接 sip
        SIP_SYS=$(python3 -c "import sip, os; print(os.path.dirname(sip.__file__))" 2>/dev/null || true)
        if [ -n "$SIP_SYS" ]; then
            rm -f "$SITE_PACKAGES/sip"
            ln -sf "$SIP_SYS" "$SITE_PACKAGES/sip"
        fi
        
        echo "  ✅ PyQt5 重新链接成功"
    else
        echo "  ❌ 无法找到系统 PyQt5，请手动安装："
        echo "     sudo dnf install python3-PyQt5"
        exit 1
    fi
fi

# 验证 PyQt5 子模块（银河麒麟可能需要单独链接）
if ! $PYTHON -c "from PyQt5 import QtCore, QtGui, QtWidgets" 2>/dev/null; then
    echo "  ⚠️  PyQt5 子模块不完整，尝试修复..."
    
    SITE_PACKAGES=$($PYTHON -c "import site; print(site.getsitepackages()[0])" 2>/dev/null || true)
    
    # 检查并链接每个子模块
    for mod in QtCore QtGui QtWidgets QtNetwork QtPrintSupport QtSvg; do
        if ! $PYTHON -c "from PyQt5 import $mod" 2>/dev/null; then
            # 查找系统子模块
            SYS_MOD=$(python3 -c "from PyQt5 import $mod; import os; print(os.path.dirname(getattr(__import__('PyQt5.$mod', fromlist=['$mod']), '$mod').__file__))" 2>/dev/null || true)
            if [ -n "$SYS_MOD" ] && [ -d "$SYS_MOD" ]; then
                TARGET_DIR="$SITE_PACKAGES/PyQt5"
                if [ -d "$TARGET_DIR" ]; then
                    # 复制缺失的子模块
                    cp -rf "$SYS_MOD" "$TARGET_DIR/"
                    echo "    ✅ 已添加 $mod 子模块"
                fi
            fi
        fi
    done
fi

# 使用兼容的方式获取版本
PYQT5_VER=$($PYTHON -c "
try:
    from PyQt5 import QtCore
    print(QtCore.PYQT_VERSION_STR)
except:
    try:
        import PyQt5
        print('5.x (system)')
    except:
        print('unknown')
" 2>/dev/null)

echo "  ✅ PyQt5: $PYQT5_VER"
$PYTHON -c "import sqlalchemy; print('  ✅ SQLAlchemy:', sqlalchemy.__version__)"
echo "  ✅ 依赖验证通过"

# ========== 6. PyInstaller 打包 ==========
echo ""
echo "[6/7] 开始 PyInstaller 打包（约 5~15 分钟）..."
cd "$SCRIPT_DIR"

# 修复驱动文件权限（避免 ldd 警告）
if [ -d "drivers" ]; then
    chmod -R +r drivers/ 2>/dev/null || true
    find drivers/ -name "*.so" -exec chmod +r {} \; 2>/dev/null || true
fi

rm -rf "$SCRIPT_DIR/dist/AIDBTools" "$SCRIPT_DIR/build" 2>/dev/null || true

$PYTHON -m PyInstaller --clean AIDBTools_arm_kylin.spec

echo "  ✅ 打包完成"

# ========== 7. 打包交付物 ==========
echo ""
echo "[7/7] 整理交付包..."

OUTPUT="$SCRIPT_DIR/dist/AIDBTools"
if [ -f "$OUTPUT" ]; then
    SIZE=$(du -sh "$OUTPUT" | cut -f1)
    FINAL_NAME="AIDBTools_v${VER}_kylin_arm_aarch64"
    
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
        /usr/lib/jvm/java-11-openjdk-arm64 \
        /usr/lib/jvm/java-17-openjdk-arm64 \
        /usr/lib/jvm/java-8-openjdk-arm64; do
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
    
    # 压缩为 tar.gz
    cd "$DIST_DIR"
    tar czf "${FINAL_NAME}.tar.gz" "${FINAL_NAME}/"
    rm -rf "${FINAL_NAME}/"
    
    TAR_SIZE=$(du -sh "${FINAL_NAME}.tar.gz" | cut -f1)
    
    echo ""
    echo "================================================"
    echo "  ✅ ARM 银河麒麟版打包成功！"
    echo ""
    echo "  版本: v${VER}"
    echo "  平台: 银河麒麟 ARM aarch64"
    echo "  文件: ${FINAL_NAME}.tar.gz"
    echo "  大小: ${TAR_SIZE}"
    echo "  位置: $DIST_DIR/${FINAL_NAME}.tar.gz"
    echo ""
    echo "  部署方式（目标机器）："
    echo "  1. 解压: tar xzf ${FINAL_NAME}.tar.gz"
    echo "  2. 运行: cd ${FINAL_NAME} && ./run.sh"
    echo "  3. 或双击 AIDBTools.desktop 桌面快捷方式"
    echo "================================================"
else
    echo "  ❌ 未找到输出文件，请检查上方错误信息"
    python3 -c "import sys; sys.path.insert(0,'$SCRIPT_DIR'); from version import set_build_platform; set_build_platform('source')"
    exit 1
fi

# ── 恢复 BUILD_PLATFORM ───────────────────────────────────────
python3 -c "import sys; sys.path.insert(0,'$SCRIPT_DIR'); from version import set_build_platform; set_build_platform('source'); print('  [OK] BUILD_PLATFORM 已恢复为 source')"
