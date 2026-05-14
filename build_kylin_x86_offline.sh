#!/bin/bash
# ============================================================
# AIDBTools x86_64 银河麒麟版 - 完全离线打包脚本
# 适用：银河麒麟 V10 x86_64 / 统信UOS x86_64
# 架构：x86_64
# 
# ⚠️  必须在有网络的 x86_64 机器上执行（用于下载依赖）
# 📌 使用 PyQt5（银河麒麟系统兼容性更好）
# 📦 包含所有系统依赖和 Python 依赖
# 用法：chmod +x build_kylin_x86_offline.sh && ./build_kylin_x86_offline.sh
# ============================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$SCRIPT_DIR/.venv_offline_build"
PYTHON="$VENV_DIR/bin/python"
PIP="$VENV_DIR/bin/pip"
ARCH=$(uname -m)
DEPS_DIR="$SCRIPT_DIR/offline_packages"

# ── 架构检查 ──────────────────────────────────────────────
if [ "$ARCH" != "x86_64" ]; then
    echo "================================================"
    echo "  ❌ 当前架构: $ARCH"
    echo "  此脚本必须在 x86_64 机器上运行！"
    echo "================================================"
    exit 1
fi

# ── 每次打包前自动递增补丁版本号 ─────────────────────────────
VER=$(python3 -c "import sys; sys.path.insert(0,'$SCRIPT_DIR'); from version import bump_patch_version; print(bump_patch_version())" 2>/dev/null)
if [ -z "$VER" ]; then
    echo "  ❌ 生成版本号失败"
    exit 1
fi

DIST_DIR="$SCRIPT_DIR/release/kylin_x86_offline/v${VER}"
mkdir -p "$DIST_DIR"
mkdir -p "$DEPS_DIR"

echo "================================================"
echo "  AIDBTools v${VER} x86_64 完全离线打包"
echo "  工作目录: $SCRIPT_DIR"
echo "  系统架构: $ARCH"
echo "  输出目录: $DIST_DIR"
echo "  依赖缓存: $DEPS_DIR"
echo "================================================"

# ── 写入平台标识 ─────────────────────────────────────────
python3 -c "import sys; sys.path.insert(0,'$SCRIPT_DIR'); from version import set_build_platform; set_build_platform('kylin_x86_offline'); print('  [OK] BUILD_PLATFORM = kylin_x86_offline')"

# ── 检测包管理器 ─────────────────────────────────────────
is_apt() { command -v apt-get &>/dev/null; }
is_dnf() { command -v dnf &>/dev/null; }
is_yum() { command -v yum &>/dev/null; }

# ========== 1. 下载系统依赖包 ==========
echo ""
echo "[1/8] 下载系统依赖包（离线安装包）..."

if is_apt; then
    # Debian/Ubuntu/Kylin 系
    mkdir -p "$DEPS_DIR/deb"
    cd "$DEPS_DIR/deb"
    
    echo "  下载 Qt 运行时库..."
    apt-get download \
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
        fonts-wqy-microhei 2>&1 | grep -v "^Get:" || true
    
    echo "  下载 Java 运行时..."
    apt-get download default-jre-headless 2>&1 | grep -v "^Get:" || true
    
    echo "  下载 ODBC 支持..."
    apt-get download unixodbc odbcinst 2>&1 | grep -v "^Get:" || true
    
    DEB_COUNT=$(ls -1 *.deb 2>/dev/null | wc -l)
    echo "  ✅ 已下载 $DEB_COUNT 个 .deb 包"
    
elif is_dnf; then
    # CentOS/OpenEuler 系
    mkdir -p "$DEPS_DIR/rpm"
    cd "$DEPS_DIR/rpm"
    
    echo "  下载系统依赖 RPM 包..."
    sudo dnf download \
        libxcb \
        libX11 \
        mesa-libGL \
        glib2 \
        java-11-openjdk-headless \
        unixODBC 2>&1 | tail -5 || true
    
    RPM_COUNT=$(ls -1 *.rpm 2>/dev/null | wc -l)
    echo "  ✅ 已下载 $RPM_COUNT 个 .rpm 包"
fi

cd "$SCRIPT_DIR"
echo "  ✅ 系统依赖包下载完成"

# ========== 2. 安装系统依赖（构建用）==========
echo ""
echo "[2/8] 安装系统依赖（用于打包）..."

# 检查编译工具（JPype1 和 Pandas 需要）
if ! command -v gcc &>/dev/null || ! command -v g++ &>/dev/null; then
    echo "  ⚠️  未找到完整的编译工具链（gcc/g++）"
    echo "  正在安装编译工具..."
    
    if is_apt; then
        sudo apt-get install -y -qq build-essential python3-dev 2>&1 | tail -3
    elif is_dnf; then
        sudo dnf install -y -q gcc gcc-c++ python3-devel 2>&1 | tail -3
    elif is_yum; then
        sudo yum install -y -q gcc gcc-c++ python3-devel 2>&1 | tail -3
    fi
    
    if command -v gcc &>/dev/null && command -v g++ &>/dev/null; then
        echo "  ✅ 编译工具安装成功 (gcc $(gcc --version | head -1), g++ $(g++ --version | head -1))"
    else
        echo "  ⚠️  编译工具安装不完整，JPype1 可能无法编译"
        if ! command -v g++ &>/dev/null; then
            echo "  ❌ 缺少 g++（C++ 编译器），请手动安装: sudo yum install gcc-c++"
        fi
    fi
else
    echo "  ✅ 编译工具已就绪 (gcc $(gcc --version | head -1), g++ $(g++ --version | head -1))"
fi

# 检查 Java 构建工具（JPype1 需要 Ant）
if ! command -v ant &>/dev/null; then
    echo "  ⚠️  未找到 Apache Ant，JPype1 编译需要"
    echo "  正在安装 Ant..."
    
    if is_apt; then
        sudo apt-get install -y -qq ant 2>&1 | tail -3
    elif is_dnf; then
        sudo dnf install -y -q ant 2>&1 | tail -3
    elif is_yum; then
        sudo yum install -y -q ant 2>&1 | tail -3
    fi
    
    if command -v ant &>/dev/null; then
        ANT_VER=$(ant -version 2>&1 | head -1)
        echo "  ✅ Ant 安装成功 ($ANT_VER)"
    else
        echo "  ⚠️  Ant 安装失败，JPype1 可能无法编译"
    fi
else
    ANT_VER=$(ant -version 2>&1 | head -1)
    echo "  ✅ Ant 已就绪 ($ANT_VER)"
fi

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
fi
echo "  ✅ 系统依赖就绪"

# ========== 3. 检查 Java ==========
echo ""
echo "[3/8] 检查 Java 环境..."

# 检查是否有完整的 Java JDK（不仅仅是 JRE）
HAS_FULL_JDK=false
if command -v java &>/dev/null && command -v javac &>/dev/null; then
    JAVA_VER=$(java -version 2>&1 | head -1)
    JAVAC_VER=$(javac -version 2>&1 | head -1)
    echo "  ✅ Java JDK 已安装"
    echo "     $JAVA_VER"
    echo "     $JAVAC_VER"
    HAS_FULL_JDK=true
    
    if [ -z "$JAVA_HOME" ]; then
        JAVA_BIN=$(readlink -f $(which java))
        export JAVA_HOME=$(dirname $(dirname $JAVA_BIN))
        echo "  JAVA_HOME = $JAVA_HOME"
    fi
    
    # 检查是否是 Java 8（可能需要特殊处理）
    if echo "$JAVA_VER" | grep -q "1\.8\|version \"8"; then
        echo "  ⚠️  检测到 Java 8，JPype1 可能需要 Java 11+"
        echo "  建议升级到 Java 11 或更高版本"
    fi
elif command -v java &>/dev/null; then
    echo "  ⚠️  只检测到 Java JRE，缺少 JDK 开发工具"
    echo "  JPype1 编译需要 Java JDK（包含 javac）"
    echo "  正在安装 Java JDK..."
    
    if is_apt; then
        sudo apt-get install -y -qq default-jdk 2>&1 | tail -3
    elif is_dnf; then
        sudo dnf install -y -q java-11-openjdk-devel 2>&1 | tail -3
    elif is_yum; then
        sudo yum install -y -q java-11-openjdk-devel 2>&1 | tail -3
    fi
    
    if command -v javac &>/dev/null; then
        echo "  ✅ Java JDK 安装成功"
        JAVA_VER=$(java -version 2>&1 | head -1)
        JAVAC_VER=$(javac -version 2>&1 | head -1)
        echo "     $JAVA_VER"
        echo "     $JAVAC_VER"
        HAS_FULL_JDK=true
        
        if [ -z "$JAVA_HOME" ]; then
            JAVA_BIN=$(readlink -f $(which java))
            export JAVA_HOME=$(dirname $(dirname $JAVA_BIN))
            echo "  JAVA_HOME = $JAVA_HOME"
        fi
    else
        echo "  ❌ Java JDK 安装失败，JPype1 将无法编译"
        echo "  请手动安装: sudo yum install java-11-openjdk-devel"
    fi
else
    echo "  ⚠️  Java 未找到，尝试安装..."
    
    if is_apt; then
        sudo apt-get install -y -qq default-jdk 2>&1 | tail -3
    elif is_dnf; then
        sudo dnf install -y -q java-11-openjdk-devel 2>&1 | tail -3
    elif is_yum; then
        sudo yum install -y -q java-11-openjdk-devel 2>&1 | tail -3
    fi
    
    if command -v java &>/dev/null && command -v javac &>/dev/null; then
        echo "  ✅ Java JDK 安装成功"
        HAS_FULL_JDK=true
    else
        echo "  ⚠️  Java 安装可能不完整"
    fi
fi

if ! $HAS_FULL_JDK; then
    echo ""
    echo "  ⚠️  警告：没有完整的 Java JDK"
    echo "  JPype1（JDBC 支持）将无法编译"
    echo "  其他功能不受影响"
    echo ""
    read -p "是否继续？(y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "请先安装 Java JDK: sudo yum install java-11-openjdk-devel"
        exit 1
    fi
fi

# ========== 4. 虚拟环境 ==========
echo ""
echo "[4/8] 创建打包用虚拟环境..."

PYTHON3_CMD=""
for cmd in python3.11 python3.10 python3.9 python3.8 python3; do
    if command -v "$cmd" &>/dev/null; then
        PYTHON3_CMD="$cmd"
        PY_VER=$(${cmd} --version 2>&1)
        echo "  使用 Python: $PYTHON3_CMD ($PY_VER)"
        
        # 检查 Python 版本是否 >= 3.8
        PY_MAJOR=$(echo $PY_VER | grep -oP '\d+\.\d+' | cut -d. -f1)
        PY_MINOR=$(echo $PY_VER | grep -oP '\d+\.\d+' | cut -d. -f2)
        if [ "$PY_MAJOR" -lt 3 ] || ([ "$PY_MAJOR" -eq 3 ] && [ "$PY_MINOR" -lt 8 ]); then
            echo "  ⚠️  Python 版本过低 (< 3.8)，某些依赖可能不兼容"
            echo "  建议安装 Python 3.8+ 以获得最佳兼容性"
        fi
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

# ========== 5. 下载并安装 Python 依赖 ==========
echo ""
echo "[5/8] 下载 Python 依赖包（离线 whl 文件）..."

# 创建离线包目录
mkdir -p "$DEPS_DIR/python_wheels"
cd "$DEPS_DIR/python_wheels"

# 检测 Python 版本，选择合适的依赖版本
PY_VERSION=$($PYTHON -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
PY_MAJOR=$(echo $PY_VERSION | cut -d. -f1)
PY_MINOR=$(echo $PY_VERSION | cut -d. -f2)

echo "  Python 版本: $PY_VERSION"

# 根据 Python 版本选择依赖版本
if [ "$PY_MAJOR" -eq 3 ] && [ "$PY_MINOR" -ge 9 ]; then
    # Python 3.9+ 可以使用较新版本
    PANDAS_VER="pandas>=2.0"
    PYQT_VER="PyQt5>=5.15.0"
    SQLALCHEMY_VER="sqlalchemy>=2.0"
    echo "  使用新版依赖（Python 3.9+）"
elif [ "$PY_MAJOR" -eq 3 ] && [ "$PY_MINOR" -ge 8 ]; then
    # Python 3.8 使用兼容版本
    PANDAS_VER="pandas>=1.3,<2.0"
    PYQT_VER="PyQt5>=5.15.0"
    SQLALCHEMY_VER="sqlalchemy>=1.4,<2.0"
    echo "  使用兼容版本依赖（Python 3.8）"
elif [ "$PY_MAJOR" -eq 3 ] && [ "$PY_MINOR" -eq 7 ]; then
    # Python 3.7 使用旧版本（最后支持的版本）
    PANDAS_VER="pandas>=1.1,<1.4"
    PYQT_VER="PyQt5==5.14.2"  # PyQt5 5.14.2 是最后一个支持 Python 3.7 的版本
    SQLALCHEMY_VER="sqlalchemy>=1.3,<1.4"
    echo "  ⚠️  Python 3.7 已停止官方支持，使用旧版依赖"
    echo "  强烈建议升级到 Python 3.8+ 以获得更好的兼容性和安全性"
else
    # Python 3.6 及以下
    PANDAS_VER="pandas>=0.25,<1.2"
    PYQT_VER="PyQt5==5.12.3"  # 非常旧的版本
    SQLALCHEMY_VER="sqlalchemy>=1.2,<1.3"
    echo "  ❌ Python 版本过低 ($PY_VERSION)，强烈建议升级到 Python 3.8+"
    echo "  当前配置可能无法正常工作"
fi

# 检查系统是否已有 PyQt5（银河麒麟常见）
SYSTEM_HAS_PYQT5=false
SYS_PYQT5_PATH=""
if python3 -c "import PyQt5" 2>/dev/null; then
    echo "  ✅ 检测到系统已安装 PyQt5"
    SYSTEM_HAS_PYQT5=true
    SYS_PYQT5_PATH=$(python3 -c "import PyQt5, os; print(os.path.dirname(PyQt5.__file__))" 2>/dev/null)
    echo "  系统 PyQt5 位置: $SYS_PYQT5_PATH"
fi

# 下载所有依赖的 wheel 文件
echo "  下载 Python 包到 offline_packages/python_wheels/ ..."
DOWNLOAD_SUCCESS=false

# 尝试多次下载（网络不稳定时重试）
for attempt in 1 2 3; do
    if [ $attempt -gt 1 ]; then
        echo "  第 $attempt 次尝试下载..."
        sleep 2
    fi
    
    $PIP download -q \
        "$PYQT_VER" \
        "$SQLALCHEMY_VER" \
        "pymysql>=1.0" \
        "psycopg2-binary>=2.8" \
        "oracledb>=1.0" \
        "$PANDAS_VER" \
        "requests>=2.25" \
        "openpyxl>=3.0" \
        "pymssql>=2.1" \
        "JPype1>=1.2" \
        "JPype1==1.4.1" \
        "jaydebeapi>=1.1" \
        "pyodbc>=4.0" \
        "pyinstaller==5.13.2" \
        "scikit-build-core>=0.9" \
        "setuptools-scm>=6.0" \
        "setuptools>=65.0,<70" \
        "ninja>=1.10" \
        "cmake>=3.15" \
        -d "$DEPS_DIR/python_wheels" 2>&1 | tail -10
    
    WHEEL_COUNT=$(ls -1 *.whl 2>/dev/null | wc -l)
    if [ "$WHEEL_COUNT" -gt 0 ]; then
        DOWNLOAD_SUCCESS=true
        break
    fi
done

WHEEL_COUNT=$(ls -1 *.whl 2>/dev/null | wc -l)
if [ "$WHEEL_COUNT" -eq 0 ]; then
    echo "  ❌ 未下载到任何 .whl 文件！"
    
    # 如果系统已有 PyQt5，尝试直接使用
    if $SYSTEM_HAS_PYQT5 && [ -n "$SYS_PYQT5_PATH" ]; then
        echo "  ⚠️  网络下载失败，但检测到系统已安装 PyQt5"
        echo "  将使用系统 PyQt5 + 在线安装其他依赖..."
        
        # 复制系统 PyQt5 到虚拟环境
        SITE_PACKAGES=$($PYTHON -c "import site; print(site.getsitepackages()[0])")
        
        if [ -d "$SYS_PYQT5_PATH" ]; then
            echo "  复制系统 PyQt5 到虚拟环境..."
            cp -rf "$SYS_PYQT5_PATH" "$SITE_PACKAGES/"
            
            # 同时处理 sip
            SIP_SYS=$(python3 -c "import sip, os; print(os.path.dirname(sip.__file__))" 2>/dev/null || true)
            if [ -n "$SIP_SYS" ] && [ -d "$SIP_SYS" ]; then
                cp -rf "$SIP_SYS" "$SITE_PACKAGES/" 2>/dev/null || true
            fi
            
            # 复制相关的 .so 文件
            SYS_PYQT5_LIBS=$(dirname "$SYS_PYQT5_PATH")
            for lib_file in "$SYS_PYQT5_LIBS"/PyQt5*.so; do
                if [ -f "$lib_file" ]; then
                    cp -f "$lib_file" "$SITE_PACKAGES/" 2>/dev/null || true
                fi
            done
            
            echo "  ✅ 系统 PyQt5 已复制到虚拟环境"
            
            # 验证是否成功
            if $PYTHON -c "import PyQt5" 2>/dev/null; then
                echo "  ✅ PyQt5 导入测试成功"
            else
                echo "  ⚠️  PyQt5 复制后仍无法导入，可能需要重新编译"
            fi
        fi
        
        # 在线安装其他依赖（不使用 --no-index）
        echo "  在线安装其他 Python 依赖..."
        $PIP install -q \
            "$SQLALCHEMY_VER" \
            "pymysql>=1.0" \
            "psycopg2-binary>=2.8" \
            "oracledb>=1.0" \
            "$PANDAS_VER" \
            "requests>=2.25" \
            "openpyxl>=3.0" \
            "pymssql>=2.1" \
            "JPype1>=1.2" \
            "jaydebeapi>=1.1" \
            "pyodbc>=4.0" \
            "pyinstaller>=5.0" 2>&1 | tail -5
        
        echo "  ⚠️  注意：此方式需要网络连接"
    else
        echo "  可能原因："
        echo "  1. 网络连接问题"
        echo "  2. pip 版本过旧（当前: $($PIP --version)）"
        echo "  3. Python 版本不支持这些依赖"
        echo ""
        echo "  建议解决方案："
        echo "  1. 升级 pip: $PIP install --upgrade pip"
        echo "  2. 检查网络: ping pypi.org"
        echo "  3. 手动下载依赖后放入此目录"
        echo "  4. 或先安装系统 PyQt5: sudo apt-get install python3-pyqt5"
        exit 1
    fi
else
    echo "  ✅ 已下载 $WHEEL_COUNT 个 .whl 文件"
    
    # 从离线包安装
    echo "  从离线包安装 Python 依赖..."
    
    # 先安装构建依赖（JPype1 需要）
    echo "  [步骤 1/3] 安装构建依赖..."
    BUILD_DEPS_OUTPUT=$($PIP install --no-index --find-links="$DEPS_DIR/python_wheels" \
        "scikit-build-core>=0.9" \
        "setuptools-scm>=6.0" \
        "setuptools>=65.0,<70" \
        "wheel>=0.37" \
        "ninja>=1.10" \
        "cmake>=3.15" 2>&1)
    
    if echo "$BUILD_DEPS_OUTPUT" | grep -q "Successfully installed"; then
        echo "  ✅ 构建依赖安装成功"
    else
        echo "  ⚠️  构建依赖安装可能有问题，继续尝试..."
    fi
    
    # 再安装主依赖（分批次安装，避免单次安装太多导致卡住）
    echo "  [步骤 2/3] 安装核心依赖（PyQt5、SQLAlchemy等）..."
    CORE_DEPS_OUTPUT=$($PIP install --no-index --find-links="$DEPS_DIR/python_wheels" \
        "$PYQT_VER" \
        "$SQLALCHEMY_VER" \
        "pymysql>=1.0" \
        "psycopg2-binary>=2.8" \
        "oracledb>=1.0" \
        "requests>=2.25" \
        "openpyxl>=3.0" \
        "pyodbc>=4.0" 2>&1)
    
    echo "$CORE_DEPS_OUTPUT" | tail -5
    
    if echo "$CORE_DEPS_OUTPUT" | grep -q "ERROR"; then
        echo "  ⚠️  核心依赖安装有错误，查看详细输出 above"
    else
        echo "  ✅ 核心依赖安装成功"
    fi
    
    echo "  [步骤 3/3] 安装数据分析和 JDBC 依赖..."
    echo "  （Pandas 和 JPype1 需要编译，可能需要 5-10 分钟，请耐心等待）"
    
    # 逐个安装大型包，显示进度
    echo "    - 安装 Pandas..."
    PANDAS_OUTPUT=$($PIP install --no-index --find-links="$DEPS_DIR/python_wheels" "$PANDAS_VER" 2>&1)
    if echo "$PANDAS_OUTPUT" | grep -q "Successfully installed\|already satisfied"; then
        echo "    ✅ Pandas 安装成功"
    elif echo "$PANDAS_OUTPUT" | grep -q "ERROR"; then
        echo "    ❌ Pandas 安装失败"
        echo "$PANDAS_OUTPUT" | tail -5
    else
        echo "    ✅ Pandas 安装完成"
    fi
    
    echo "    - 安装 JPype1（需要编译，可能较慢）..."
    echo "      （正在编译 C 扩展，请耐心等待 3-5 分钟）"
    # 直接显示输出，不捕获，让用户看到实时进度
    $PIP install --no-index --find-links="$DEPS_DIR/python_wheels" "JPype1>=1.2" 2>&1 | tee /tmp/jpype_install.log
    JPYPE_EXIT_CODE=${PIPESTATUS[0]}
    
    if [ $JPYPE_EXIT_CODE -eq 0 ]; then
        echo "    ✅ JPype1 安装成功"
    else
        echo "    ❌ JPype1 安装失败（退出码: $JPYPE_EXIT_CODE）"
        echo "    查看详细错误: cat /tmp/jpype_install.log"
        echo ""
        
        # 检查是否是 Java 版本问题
        if grep -q "Could NOT find Java" /tmp/jpype_install.log; then
            echo "    ⚠️  Java 配置问题 detected"
            
            # 检查 Java 版本
            if command -v javac &>/dev/null; then
                JAVA_VER_INFO=$(javac -version 2>&1)
                echo "    当前 Java: $JAVA_VER_INFO"
                
                if echo "$JAVA_VER_INFO" | grep -q "1\.8\|version \"8"; then
                    echo ""
                    echo "    原因：Java 8 可能与 JPype1 1.7.0 不兼容"
                    echo "    解决方案："
                    echo "    1. 升级到 Java 11+: sudo yum install java-11-openjdk-devel"
                    echo "    2. 或使用旧版 JPype1: pip install JPype1==1.4.1"
                    echo ""
                    
                    # 尝试使用旧版 JPype1
                    echo "    尝试使用 JPype1 1.4.1（兼容 Java 8）..."
                    $PIP install --no-index --find-links="$DEPS_DIR/python_wheels" "JPype1==1.4.1" 2>&1 | tee /tmp/jpype_install_retry.log
                    
                    if [ ${PIPESTATUS[0]} -eq 0 ]; then
                        echo "    ✅ JPype1 1.4.1 安装成功"
                    else
                        echo "    ❌ JPype1 1.4.1 也失败了"
                        echo "    建议：升级到 Java 11+ 或跳过 JPype1"
                    fi
                else
                    echo "    原因：CMake 无法找到完整的 Java 开发工具"
                    echo "    请确保安装了完整的 JDK（不仅仅是 JRE）"
                    echo "    sudo yum install java-11-openjdk-devel"
                fi
            else
                echo "    原因：未找到 javac（Java 编译器）"
                echo "    请安装 Java JDK: sudo yum install java-11-openjdk-devel"
            fi
        elif grep -q "ANT_EXECUTABLE-NOTFOUND\|ant.*not found" /tmp/jpype_install.log; then
            echo "    ⚠️  检测到缺少 Apache Ant，正在安装..."
            if is_apt; then
                sudo apt-get install -y -qq ant 2>&1 | tail -3
            elif is_dnf; then
                sudo dnf install -y -q ant 2>&1 | tail -3
            elif is_yum; then
                sudo yum install -y -q ant 2>&1 | tail -3
            fi
            
            if command -v ant &>/dev/null; then
                ANT_VER=$(ant -version 2>&1 | head -1)
                echo "    ✅ Ant 安装成功 ($ANT_VER)"
                echo "    重新尝试安装 JPype1..."
                $PIP install --no-index --find-links="$DEPS_DIR/python_wheels" "JPype1>=1.2" 2>&1 | tee /tmp/jpype_install_retry.log
                if [ ${PIPESTATUS[0]} -eq 0 ]; then
                    echo "    ✅ JPype1 重新安装成功"
                else
                    echo "    ❌ JPype1 仍然失败，请查看日志"
                fi
            else
                echo "    ❌ Ant 安装失败"
            fi
        elif grep -q "g++" /tmp/jpype_install.log; then
            echo "    ⚠️  检测到未安装 g++，正在安装..."
            if is_apt; then
                sudo apt-get install -y -qq g++ 2>&1 | tail -3
            elif is_dnf; then
                sudo dnf install -y -q gcc-c++ 2>&1 | tail -3
            elif is_yum; then
                sudo yum install -y -q gcc-c++ 2>&1 | tail -3
            fi
            
            if command -v g++ &>/dev/null; then
                echo "    ✅ g++ 安装成功，重新尝试安装 JPype1..."
                $PIP install --no-index --find-links="$DEPS_DIR/python_wheels" "JPype1>=1.2" 2>&1 | tee /tmp/jpype_install_retry.log
                if [ ${PIPESTATUS[0]} -eq 0 ]; then
                    echo "    ✅ JPype1 重新安装成功"
                else
                    echo "    ❌ JPype1 仍然失败，请查看日志"
                fi
            else
                echo "    ❌ g++ 安装失败"
            fi
        else
            echo "    常见原因："
            echo "    1. 缺少 gcc/g++: sudo yum install gcc gcc-c++"
            echo "    2. 缺少 Java JDK: sudo yum install java-11-openjdk-devel"
            echo "    3. Java 版本不兼容（需要 Java 11+）"
        fi
    fi
    
    echo "    - 安装其他依赖..."
    OTHER_OUTPUT=$($PIP install --no-index --find-links="$DEPS_DIR/python_wheels" \
        "pymssql>=2.1" \
        "jaydebeapi>=1.1" \
        "pyinstaller==5.13.2" 2>&1)
    
    if echo "$OTHER_OUTPUT" | grep -q "ERROR"; then
        echo "    ⚠️  部分依赖安装有警告"
        echo "$OTHER_OUTPUT" | grep "ERROR" | head -3
    else
        echo "    ✅ 其他依赖安装成功"
    fi
    
    # 总体检查
    echo ""
    echo "  检查安装结果..."
    FAILED_DEPS=""
    
    for dep in PyQt5 sqlalchemy pymysql psycopg2 oracledb pandas requests openpyxl jpype jaydebeapi pyodbc pyinstaller; do
        if ! $PYTHON -c "import $dep" 2>/dev/null; then
            # 特殊处理模块名
            case $dep in
                jpype) MODULE_NAME="jpype" ;;
                jaydebeapi) MODULE_NAME="jaydebeapi" ;;
                pyodbc) MODULE_NAME="pyodbc" ;;
                *) MODULE_NAME="$dep" ;;
            esac
            
            if ! $PYTHON -c "import $MODULE_NAME" 2>/dev/null; then
                FAILED_DEPS="$FAILED_DEPS $dep"
            fi
        fi
    done
    
    if [ -z "$FAILED_DEPS" ]; then
        echo "  ✅ 所有依赖安装成功"
    else
        echo "  ❌ 以下依赖安装失败:$FAILED_DEPS"
        echo ""
        echo "  尝试修复..."
        
        # 尝试单独安装失败的依赖
        for dep in $FAILED_DEPS; do
            echo "    重新安装 $dep..."
            case $dep in
                PyQt5) SPEC="$PYQT_VER" ;;
                sqlalchemy) SPEC="$SQLALCHEMY_VER" ;;
                pandas) SPEC="$PANDAS_VER" ;;
                *) SPEC="$dep" ;;
            esac
            
            FIX_OUTPUT=$($PIP install --no-index --find-links="$DEPS_DIR/python_wheels" "$SPEC" 2>&1)
            echo "$FIX_OUTPUT" | tail -3
            
            # 验证
            MODULE_NAME=$dep
            case $dep in
                jpype) MODULE_NAME="jpype" ;;
                jaydebeapi) MODULE_NAME="jaydebeapi" ;;
            esac
            
            if $PYTHON -c "import $MODULE_NAME" 2>/dev/null; then
                echo "    ✅ $dep 修复成功"
            else
                echo "    ❌ $dep 仍然失败"
                echo "       请手动安装: $PIP install $SPEC"
            fi
        done
        
        # 最后再次检查
        echo ""
        echo "  最终检查..."
        STILL_FAILED=""
        for dep in $FAILED_DEPS; do
            MODULE_NAME=$dep
            case $dep in
                jpype) MODULE_NAME="jpype" ;;
                jaydebeapi) MODULE_NAME="jaydebeapi" ;;
            esac
            
            if ! $PYTHON -c "import $MODULE_NAME" 2>/dev/null; then
                STILL_FAILED="$STILL_FAILED $dep"
            fi
        done
        
        if [ -n "$STILL_FAILED" ]; then
            echo "  ❌ 以下依赖仍然失败:$STILL_FAILED"
            echo ""
            echo "  建议："
            echo "  1. 检查是否有编译工具: gcc --version"
            echo "  2. 手动安装失败的包"
            echo "  3. 或查看日志文件获取详细错误信息"
            echo ""
            read -p "是否继续打包？(y/n) " -n 1 -r
            echo
            if [[ ! $REPLY =~ ^[Yy]$ ]]; then
                echo "打包已取消"
                exit 1
            fi
        else
            echo "  ✅ 所有依赖修复成功"
        fi
    fi
fi

# 安装 PyQt5 兼容层（让代码中的 PyQt6 导入自动映射到 PyQt5）
echo "  安装 PyQt5→PyQt6 兼容层..."
SITE_PACKAGES=$($PYTHON -c "import site; print(site.getsitepackages()[0])")
cp "$SCRIPT_DIR/pyqt5_compat.py" "$SITE_PACKAGES/"
echo "import pyqt5_compat" > "$SITE_PACKAGES/pyqt5_compat.pth"
echo "  ✅ 兼容层已安装"

echo "  ✅ Python 依赖安装完成"

# ========== 6. 验证关键依赖 ==========
echo ""
echo "[6/8] 验证关键依赖..."

# 检查虚拟环境中的 site-packages
SITE_PACKAGES=$($PYTHON -c "import site; print(site.getsitepackages()[0])")
echo "  虚拟环境: $VENV_DIR"
echo "  site-packages: $SITE_PACKAGES"

# 列出已安装的包
echo "  已安装的关键包:"
$PIP list 2>/dev/null | grep -iE "pyqt|sqlalchemy|pandas|jpype|pyinstaller" | head -10 || echo "    (无)"
echo ""

# 检查 PyQt5 是否存在
PYQT5_INSTALLED=false
if $PYTHON -c "import PyQt5" 2>/dev/null; then
    PYQT5_VER=$($PYTHON -c "from PyQt5 import QtCore; print(QtCore.PYQT_VERSION_STR)" 2>/dev/null || echo "未知")
    echo "  ✅ PyQt5: $PYQT5_VER"
    PYQT5_INSTALLED=true
else
    echo "  ❌ PyQt5 未安装！"
    echo ""
    echo "  诊断信息："
    
    # 检查是否有 PyQt5 目录
    if [ -d "$SITE_PACKAGES/PyQt5" ]; then
        echo "  - PyQt5 目录存在: $SITE_PACKAGES/PyQt5"
        ls -la "$SITE_PACKAGES/PyQt5" | head -5
    else
        echo "  - PyQt5 目录不存在于: $SITE_PACKAGES/PyQt5"
    fi
    
    # 检查是否下载了 PyQt5 wheel
    PYQT5_WHEEL=$(ls "$DEPS_DIR/python_wheels"/PyQt5*.whl 2>/dev/null | head -1)
    if [ -n "$PYQT5_WHEEL" ]; then
        echo "  - 已下载 PyQt5 wheel: $(basename $PYQT5_WHEEL)"
        echo "  - 尝试手动安装..."
        $PIP install --no-index --find-links="$DEPS_DIR/python_wheels" "$PYQT_VER" 2>&1 | tail -5
        
        # 再次检查
        if $PYTHON -c "import PyQt5" 2>/dev/null; then
            PYQT5_VER=$($PYTHON -c "from PyQt5 import QtCore; print(QtCore.PYQT_VERSION_STR)" 2>/dev/null)
            echo "  ✅ PyQt5 手动安装成功: $PYQT5_VER"
            PYQT5_INSTALLED=true
        else
            echo "  ❌ 手动安装仍然失败"
        fi
    else
        echo "  - 未找到 PyQt5 wheel 文件"
    fi
    
    # 检查系统 PyQt5
    if ! $PYQT5_INSTALLED && python3 -c "import PyQt5" 2>/dev/null; then
        SYS_PYQT5=$(python3 -c "import PyQt5, os; print(os.path.dirname(PyQt5.__file__))" 2>/dev/null)
        echo "  - 系统 PyQt5 位置: $SYS_PYQT5"
        echo "  - 建议: 手动复制系统 PyQt5 到虚拟环境"
        echo "    cp -rf $SYS_PYQT5 $SITE_PACKAGES/"
        
        # 自动复制
        echo "  自动复制系统 PyQt5..."
        cp -rf "$SYS_PYQT5" "$SITE_PACKAGES/"
        
        # 复制 sip
        SIP_SYS=$(python3 -c "import sip, os; print(os.path.dirname(sip.__file__))" 2>/dev/null || true)
        if [ -n "$SIP_SYS" ] && [ -d "$SIP_SYS" ]; then
            cp -rf "$SIP_SYS" "$SITE_PACKAGES/" 2>/dev/null || true
        fi
        
        # 验证
        if $PYTHON -c "import PyQt5" 2>/dev/null; then
            echo "  ✅ 系统 PyQt5 复制成功"
            PYQT5_INSTALLED=true
        fi
    fi
    
    if ! $PYQT5_INSTALLED; then
        echo ""
        echo "  解决方案："
        echo "  1. 手动安装 PyQt5:"
        echo "     $PIP install PyQt5>=5.15.0"
        echo ""
        echo "  2. 或使用系统 PyQt5（如果有）:"
        echo "     SYS_PYQT5=\$(python3 -c 'import PyQt5, os; print(os.path.dirname(PyQt5.__file__))')"
        echo "     cp -rf \$SYS_PYQT5 $SITE_PACKAGES/"
        echo ""
        exit 1
    fi
fi

# 验证其他依赖
if $PYTHON -c "import sqlalchemy" 2>/dev/null; then
    SQLA_VER=$($PYTHON -c "import sqlalchemy; print(sqlalchemy.__version__)" 2>/dev/null || echo "未知")
    echo "  ✅ SQLAlchemy: $SQLA_VER"
else
    echo "  ⚠️  SQLAlchemy 未安装（可能影响数据库功能）"
fi

if $PYTHON -c "import pandas" 2>/dev/null; then
    PANDAS_VER=$($PYTHON -c "import pandas; print(pandas.__version__)" 2>/dev/null || echo "未知")
    echo "  ✅ Pandas: $PANDAS_VER"
else
    echo "  ⚠️  Pandas 未安装（可能影响数据导出功能）"
fi

if $PYTHON -c "import jpype" 2>/dev/null; then
    echo "  ✅ JPype1: 已安装（JDBC 支持）"
else
    echo "  ⚠️  JPype1 未安装（JDBC 功能将不可用）"
fi

if $PYTHON -c "import PyInstaller" 2>/dev/null; then
    echo "  ✅ PyInstaller: 已安装"
else
    echo "  ❌ PyInstaller 未安装，无法继续打包！"
    exit 1
fi

echo ""
echo "  ✅ 依赖验证通过，可以开始打包！"

# ========== 7. PyInstaller 打包 ==========
echo ""
echo "[7/8] 开始 PyInstaller 打包（约 5~15 分钟）..."
cd "$SCRIPT_DIR"

# 检查 Python 共享库
PYTHON_LIB=$(find /usr/lib* /usr/local/lib* -name "libpython3.9*.so*" 2>/dev/null | head -1)
if [ -z "$PYTHON_LIB" ]; then
    echo "  ⚠️  未找到 Python 共享库，尝试安装 python3-devel..."
    if is_apt; then
        sudo apt-get install -y -qq python3-dev 2>&1 | tail -3
    elif is_dnf; then
        sudo dnf install -y -q python3-devel 2>&1 | tail -3
    elif is_yum; then
        sudo yum install -y -q python3-devel 2>&1 | tail -3
    fi
    
    PYTHON_LIB=$(find /usr/lib* /usr/local/lib* -name "libpython3.9*.so*" 2>/dev/null | head -1)
    if [ -n "$PYTHON_LIB" ]; then
        echo "  ✅ Python 共享库已找到: $PYTHON_LIB"
    else
        echo "  ❌ 仍然未找到 Python 共享库"
        echo "  建议：使用 conda 或从源码编译 Python（带 --enable-shared）"
    fi
else
    echo "  ✅ Python 共享库已找到: $PYTHON_LIB"
fi

# 确保 setuptools 已安装（PyInstaller 需要 pkg_resources）
if ! $PYTHON -c "import pkg_resources" 2>/dev/null; then
    echo "  ⚠️  pkg_resources 未找到，正在降级 setuptools..."
    # setuptools 70+ 移除了 pkg_resources，需要降级到 69.x
    $PIP install "setuptools<70" 2>&1 | tail -3
    
    if $PYTHON -c "import pkg_resources" 2>/dev/null; then
        echo "  ✅ setuptools 降级成功"
    else
        echo "  ❌ setuptools 降级失败，尝试重新安装..."
        $PIP uninstall -y setuptools 2>&1 | tail -1
        $PIP install "setuptools==69.5.1" 2>&1 | tail -3
    fi
fi

# 修复驱动文件权限
if [ -d "drivers" ]; then
    chmod -R +r drivers/ 2>/dev/null || true
    find drivers/ -name "*.so" -exec chmod +r {} \; 2>/dev/null || true
fi

rm -rf "$SCRIPT_DIR/dist/AIDBTools" "$SCRIPT_DIR/build" 2>/dev/null || true

# PyInstaller 打包（使用 5.13.2 版本，兼容静态编译的 Python）
$PYTHON -m PyInstaller --clean AIDBTools_linux.spec

if [ $? -eq 0 ]; then
    echo "  ✅ 打包完成"
else
    echo "  ❌ PyInstaller 打包失败"
    echo "  请查看上面的错误信息"
    exit 1
fi

# ========== 8. 创建完全离线交付包 ==========
echo ""
echo "[8/8] 创建完全离线交付包..."

# COLLECT 模式生成的是目录
OUTPUT="$SCRIPT_DIR/dist/AIDBTools"
if [ -d "$OUTPUT" ]; then
    SIZE=$(du -sh "$OUTPUT" | cut -f1)
    FINAL_NAME="AIDBTools_v${VER}_kylin_x86_64_offline"
    
    # 创建交付目录
    PKG_DIR="$DIST_DIR/${FINAL_NAME}"
    mkdir -p "$PKG_DIR"
    
    # 复制可执行文件和依赖（COLLECT 模式生成目录）
    echo "  复制应用文件..."
    cp -r "$OUTPUT"/* "$PKG_DIR/"
    
    # 复制配置文件和驱动
    cp -r "$SCRIPT_DIR/config" "$PKG_DIR/" 2>/dev/null || true
    cp -r "$SCRIPT_DIR/drivers" "$PKG_DIR/" 2>/dev/null || true
    cp "$SCRIPT_DIR/icon.png" "$PKG_DIR/" 2>/dev/null || true
    
    # 复制离线依赖包
    echo "  复制离线依赖包..."
    cp -r "$DEPS_DIR" "$PKG_DIR/offline_packages/"
    
    # 创建离线安装脚本
    cat > "$PKG_DIR/install_offline.sh" << 'INSTALLEOF'
#!/bin/bash
# ============================================================
# AIDBTools 离线安装脚本
# 在目标机器上执行此脚本完成所有依赖安装
# ============================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OFFLINE_DEPS="$SCRIPT_DIR/offline_packages"

echo "================================================"
echo "  AIDBTools 离线安装"
echo "================================================"
echo ""

# 检测包管理器
is_apt() { command -v apt-get &>/dev/null; }
is_dnf() { command -v dnf &>/dev/null; }

# 1. 安装系统依赖
echo "[1/3] 安装系统依赖..."
if is_apt && [ -d "$OFFLINE_DEPS/deb" ]; then
    echo "  安装 .deb 包..."
    sudo dpkg -i "$OFFLINE_DEPS/deb"/*.deb 2>/dev/null || true
    sudo apt-get install -f -y -qq 2>/dev/null || true
    echo "  ✅ 系统依赖安装完成"
elif is_dnf && [ -d "$OFFLINE_DEPS/rpm" ]; then
    echo "  安装 .rpm 包..."
    sudo rpm -ivh --force "$OFFLINE_DEPS/rpm"/*.rpm 2>/dev/null || true
    echo "  ✅ 系统依赖安装完成"
else
    echo "  ⚠️  未找到离线系统依赖包，尝试在线安装..."
    if is_apt; then
        sudo apt-get update -qq
        sudo apt-get install -y -qq \
            libxcb-xinerama0 libxcb-cursor0 libxkbcommon-x11-0 \
            libgl1 default-jre-headless 2>&1 | tail -3
    fi
fi

# 2. 安装 Python 依赖（如果需要重新构建虚拟环境）
if [ -d "$OFFLINE_DEPS/python_wheels" ]; then
    echo ""
    echo "[2/3] 准备 Python 环境..."
    
    # 检查是否已有虚拟环境
    if [ ! -d ".venv" ]; then
        echo "  创建虚拟环境..."
        python3 -m venv .venv
    fi
    
    source .venv/bin/activate
    
    echo "  从离线包安装 Python 依赖..."
    pip install --no-index --find-links="$OFFLINE_DEPS/python_wheels" \
        PyQt6 sqlalchemy pymysql psycopg2-binary oracledb \
        pandas requests openpyxl pymssql JPype1 jaydebeapi pyodbc \
        2>&1 | tail -3
    
    echo "  ✅ Python 依赖安装完成"
fi

# 3. 设置权限
echo ""
echo "[3/3] 设置程序权限..."
chmod +x AIDBTools
chmod +x run.sh 2>/dev/null || true

# 创建桌面快捷方式
if [ -f "AIDBTools.desktop" ]; then
    DESKTOP_FILE="$HOME/Desktop/AIDBTools.desktop"
    cp "AIDBTools.desktop" "$DESKTOP_FILE" 2>/dev/null || true
    chmod +x "$DESKTOP_FILE" 2>/dev/null || true
    echo "  ✅ 桌面快捷方式已创建"
fi

echo ""
echo "================================================"
echo "  ✅ 安装完成！"
echo ""
echo "  启动方式："
echo "  1. 命令行: ./run.sh"
echo "  2. 双击桌面图标 AIDBTools"
echo "================================================"
INSTALLEOF
    chmod +x "$PKG_DIR/install_offline.sh"
    
    # 创建启动脚本
    cat > "$PKG_DIR/run.sh" << 'RUNEOF'
#!/bin/bash
# AIDBTools 启动脚本（银河麒麟 x86_64）
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# 激活虚拟环境（如果存在）
if [ -d ".venv" ]; then
    source .venv/bin/activate
fi

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
    
    # 创建详细 README
    cat > "$PKG_DIR/README_OFFLINE.txt" << READMEEOF
================================================
  AIDBTools v${VER} - 完全离线版
  银河麒麟 x86_64
================================================

📦 本安装包包含：
  ✅ 主程序（AIDBTools）
  ✅ 所有 Python 依赖（已打包）
  ✅ 系统依赖离线包（.deb 或 .rpm）
  ✅ 数据库驱动（星环 JDBC/ODBC）
  ✅ 配置文件模板
  ✅ 离线安装脚本

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🚀 快速开始（目标机器）：

方式一：使用离线安装脚本（推荐）
  1. 解压: tar xzf AIDBTools_v${VER}_kylin_x86_64_offline.tar.gz
  2. 进入: cd AIDBTools_v${VER}_kylin_x86_64_offline
  3. 安装: chmod +x install_offline.sh && ./install_offline.sh
  4. 运行: ./run.sh

方式二：手动安装
  1. 解压压缩包
  2. 安装系统依赖:
     sudo dpkg -i offline_packages/deb/*.deb
  3. 运行程序:
     chmod +x AIDBTools
     ./run.sh

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📋 功能说明：

✅ 可用功能（离线）:
  • 数据库连接管理
  • SQL 编辑器（语法高亮、自动补全）
  • 数据浏览和编辑
  • 数据导入/导出
  • 数据同步
  • 备份恢复
  • 定时任务

❌ 需要网络的功能:
  • AI SQL 生成
  • AI 对话助手

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🗄️ 支持的数据库:
  • MySQL / MariaDB
  • PostgreSQL
  • SQL Server
  • Oracle
  • Transwarp Inceptor（星环）
  • 虚谷数据库
  • OceanBase / TiDB

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

⚙️ 星环数据库连接:

ODBC 模式（推荐）:
  1. 安装驱动:
     sudo dpkg -i drivers/transwarp/odbc/linux/*.deb
  2. 验证: odbcinst -q -d
  3. 连接配置选择 ODBC 方式

JDBC 模式:
  1. 确保 Java 已安装
  2. 连接配置选择 JDBC 方式

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🐛 常见问题:

Q: 启动报错 "cannot connect to X server"
A: export DISPLAY=:0

Q: Qt 插件错误
A: 运行 install_offline.sh 安装系统依赖

Q: 字体显示方块
A: 已包含中文字体包，运行安装脚本即可

Q: 如何更新版本?
A: 备份旧版本，解压新版本，迁移 config/ 目录

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📞 技术支持:
  查看详细文档: DEPLOY_KYLIN_X86.md
  快速参考: QUICK_START_KYLIN_X86.md

================================================
READMEEOF
    
    # 压缩为 tar.gz
    cd "$DIST_DIR"
    tar czf "${FINAL_NAME}.tar.gz" "${FINAL_NAME}/"
    rm -rf "${FINAL_NAME}/"
    
    TAR_SIZE=$(du -sh "${FINAL_NAME}.tar.gz" | cut -f1)
    
    echo ""
    echo "================================================"
    echo "  ✅ 完全离线版打包成功！"
    echo ""
    echo "  版本: v${VER}"
    echo "  平台: 银河麒麟 x86_64"
    echo "  模式: COLLECT（目录模式）"
    echo "  文件: ${FINAL_NAME}.tar.gz"
    echo "  大小: ${TAR_SIZE}"
    echo "  位置: $DIST_DIR/${FINAL_NAME}.tar.gz"
    echo ""
    echo "  ✨ 无需互联网连接，所有依赖已包含！"
    echo "  💡 COLLECT 模式优势：启动更快、避免共享库问题"
    echo ""
    echo "  📦 包含内容："
    echo "  ├── AIDBTools              # 主程序"
    echo "  ├── run.sh                 # 启动脚本"
    echo "  ├── install_offline.sh     # 离线安装脚本"
    echo "  ├── AIDBTools.desktop      # 桌面快捷方式"
    echo "  ├── config/                # 配置目录"
    echo "  ├── drivers/               # 数据库驱动"
    echo "  └── offline_packages/      # 所有离线依赖包"
    echo ""
    echo "  部署方式（目标机器 - 完全离线）："
    echo "  1. 复制 tar.gz 到目标机器（U盘/内网）"
    echo "  2. 解压: tar xzf ${FINAL_NAME}.tar.gz"
    echo "  3. 进入: cd ${FINAL_NAME}"
    echo "  4. 安装: ./install_offline.sh"
    echo "  5. 运行: ./run.sh"
    echo ""
    echo "  ✨ 无需互联网连接，所有依赖已包含！"
    echo "================================================"
else
    echo "  ❌ 未找到输出文件，请检查上方错误信息"
    python3 -c "import sys; sys.path.insert(0,'$SCRIPT_DIR'); from version import set_build_platform; set_build_platform('source')"
    exit 1
fi

# ── 恢复 BUILD_PLATFORM ───────────────────────────────────────
python3 -c "import sys; sys.path.insert(0,'$SCRIPT_DIR'); from version import set_build_platform; set_build_platform('source'); print('  [OK] BUILD_PLATFORM 已恢复为 source')"
