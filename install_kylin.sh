#!/bin/bash
# ============================================================
# AIDBTools - 国产系统一键安装脚本
# 适用：银河麒麟 V10 / 统信UOS / Deepin / Ubuntu / CentOS
# 架构：x86_64 / aarch64 (ARM)
# 用法：chmod +x install_kylin.sh && ./install_kylin.sh
# ============================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$SCRIPT_DIR/.venv"
LOG="$SCRIPT_DIR/install.log"
ARCH=$(uname -m)   # x86_64 / aarch64 / i686
DISTRO=""          # kylin / uos / deepin / ubuntu / centos / other

# ── 检测发行版 ────────────────────────────────────────────────
detect_distro() {
    if [ -f /etc/kylin-release ] || grep -qi "kylin" /etc/os-release 2>/dev/null; then
        DISTRO="kylin"
    elif grep -qi "uos\|uniontech" /etc/os-release 2>/dev/null; then
        DISTRO="uos"
    elif grep -qi "deepin" /etc/os-release 2>/dev/null; then
        DISTRO="deepin"
    elif grep -qi "ubuntu\|debian" /etc/os-release 2>/dev/null; then
        DISTRO="ubuntu"
    elif grep -qi "centos\|rhel\|redhat\|anolis\|openeuler" /etc/os-release 2>/dev/null; then
        DISTRO="centos"
    else
        DISTRO="other"
    fi
}

# ── 包管理器判断 ──────────────────────────────────────────────
is_apt() { command -v apt-get &>/dev/null; }
is_yum() { command -v yum &>/dev/null; }
is_dnf() { command -v dnf &>/dev/null; }

echo "=========================================================="
echo "  AIDBTools 安装程序（国产操作系统适配版）"
echo "=========================================================="
echo ""

detect_distro
echo "  系统发行版：$DISTRO"
echo "  系统架构  ：$ARCH"
echo ""

# ---------- 1. 检查 Python ----------
echo "[1/6] 检查 Python 版本..."
PY=""
for candidate in python3.12 python3.11 python3.10 python3.9 python3; do
    if command -v "$candidate" &>/dev/null; then
        PY=$(command -v "$candidate")
        break
    fi
done

if [ -z "$PY" ]; then
    echo "❌ 未找到 python3，请先安装："
    if is_apt; then
        echo "   sudo apt install python3 python3-pip python3-venv"
    else
        echo "   sudo yum install python3 python3-pip"
    fi
    exit 1
fi

PY_VER=$($PY --version 2>&1 | awk '{print $2}')
PY_MINOR=$($PY -c "import sys; print(sys.version_info.minor)")
PY_MAJOR=$($PY -c "import sys; print(sys.version_info.major)")
echo "      找到 Python: $PY ($PY_VER)"

if [ "$PY_MAJOR" -lt 3 ] || ([ "$PY_MAJOR" -eq 3 ] && [ "$PY_MINOR" -lt 9 ]); then
    echo "❌ 需要 Python 3.9+，当前版本 $PY_VER"
    exit 1
fi

# ---------- 2. 安装系统依赖 ----------
echo "[2/6] 安装系统依赖（需要 sudo）..."

if is_apt; then
    sudo apt-get update -qq 2>&1 | tail -2
    # Qt / 字体 / ODBC / PostgreSQL 客户端 / Java
    sudo apt-get install -y -qq \
        python3-venv python3-pip \
        libxcb-xinerama0 libxcb-cursor0 libxcb-icccm4 libxcb-image0 \
        libxcb-keysyms1 libxcb-randr0 libxcb-render-util0 libxcb-shape0 \
        libxkbcommon-x11-0 libgl1 libglib2.0-0 libdbus-1-3 \
        unixodbc unixodbc-dev \
        libpq5 \
        fonts-wqy-zenhei fonts-wqy-microhei fonts-noto-cjk \
        default-jre-headless 2>&1 | tail -5 || \
    sudo apt-get install -y -qq \
        python3-venv python3-pip \
        libxcb-xinerama0 libxcb-cursor0 libxcb-icccm4 libxcb-image0 \
        libxcb-keysyms1 libxcb-randr0 libxcb-render-util0 libxcb-shape0 \
        libxkbcommon-x11-0 libgl1-mesa-glx libglib2.0-0 \
        unixodbc unixodbc-dev \
        fonts-wqy-zenhei fonts-wqy-microhei \
        default-jre-headless 2>&1 | tail -5
elif is_dnf; then
    sudo dnf install -y -q \
        python3 python3-pip python3-devel \
        xcb-util xcb-util-image xcb-util-keysyms xcb-util-renderutil xcb-util-wm \
        mesa-libGL glib2 dbus-libs \
        unixODBC unixODBC-devel \
        wqy-zenhei-fonts \
        java-11-openjdk-headless 2>&1 | tail -5
elif is_yum; then
    sudo yum install -y -q \
        python3 python3-pip python3-devel \
        xcb-util xcb-util-image xcb-util-keysyms xcb-util-renderutil xcb-util-wm \
        mesa-libGL glib2 dbus-libs \
        unixODBC unixODBC-devel \
        wqy-zenhei-fonts \
        java-11-openjdk-headless 2>&1 | tail -5
fi

# 检查 Java 是否可用
JAVA_HOME_AUTO=""
if command -v java &>/dev/null; then
    JAVA_VER=$(java -version 2>&1 | head -1)
    echo "      Java: $JAVA_VER"
    # 尝试获取 JAVA_HOME（JPype 需要）
    JAVA_HOME_AUTO=$(dirname $(dirname $(readlink -f $(which java))))
else
    echo "      ⚠️  未找到 Java，星环 JDBC 将不可用（ODBC 模式仍可使用）"
fi
echo "      系统依赖安装完成"

# ---------- 3. 安装星环 ODBC 驱动（可选）----------
echo "[3/6] 检查星环 ODBC 驱动..."
ARGO_DRIVERS_DIR="$SCRIPT_DIR/drivers/transwarp/odbc/linux"
ODBC_INSTALLED=false

# 检查是否已安装
if odbcinst -q -d 2>/dev/null | grep -qi "inceptor\|transwarp\|quark"; then
    echo "      ✅ 星环 ODBC 驱动已安装，跳过"
    ODBC_INSTALLED=true
else
    echo "      未检测到星环 ODBC 驱动，尝试安装..."
    ODBC_PKG=""

    if [ "$ARCH" = "aarch64" ]; then
        # ARM：优先 kylin10 专用 rpm
        ODBC_PKG="$ARGO_DRIVERS_DIR/inceptor-connector-odbc-8.37.0-1.ky10.ky10.aarch64.rpm"
    elif is_apt; then
        # deb 系
        ODBC_PKG="$ARGO_DRIVERS_DIR/inceptor-connector-odbc-8.37.0.deb"
    elif is_yum || is_dnf; then
        # rpm 系 x86_64
        ODBC_PKG="$ARGO_DRIVERS_DIR/inceptor-connector-odbc-8.37-1.el7.x86_64.rpm"
    fi

    if [ -n "$ODBC_PKG" ] && [ -f "$ODBC_PKG" ]; then
        echo "      安装 ODBC 包：$(basename $ODBC_PKG)"
        if echo "$ODBC_PKG" | grep -q "\.deb$"; then
            sudo dpkg -i "$ODBC_PKG" 2>&1 | tail -3 && ODBC_INSTALLED=true || \
                echo "      ⚠️  ODBC .deb 安装失败，将使用 JDBC 模式"
        elif echo "$ODBC_PKG" | grep -q "\.rpm$"; then
            if is_dnf; then
                sudo dnf install -y "$ODBC_PKG" 2>&1 | tail -3 && ODBC_INSTALLED=true || \
                    echo "      ⚠️  ODBC .rpm 安装失败，将使用 JDBC 模式"
            else
                sudo rpm -ivh --nodeps "$ODBC_PKG" 2>&1 | tail -3 && ODBC_INSTALLED=true || \
                    echo "      ⚠️  ODBC .rpm 安装失败，将使用 JDBC 模式"
            fi
        fi
        if $ODBC_INSTALLED; then
            echo "      ✅ 星环 ODBC 驱动安装成功"
        fi
    else
        echo "      ⚠️  未找到适合 $ARCH 的 ODBC 安装包，将使用 JDBC 模式"
    fi
fi

# ---------- 4. 创建虚拟环境 ----------
echo "[4/6] 创建 Python 虚拟环境..."
if [ ! -d "$VENV_DIR" ]; then
    $PY -m venv "$VENV_DIR"
    echo "      虚拟环境创建于：$VENV_DIR"
else
    echo "      虚拟环境已存在，跳过创建"
fi

PIP="$VENV_DIR/bin/pip"
PYTHON="$VENV_DIR/bin/python"

# ---------- 5. 安装 Python 依赖 ----------
OFFLINE_DIR="$SCRIPT_DIR/offline_pkgs"
OFFLINE_MODE=false
if [ -d "$OFFLINE_DIR" ] && [ "$(ls "$OFFLINE_DIR"/*.whl "$OFFLINE_DIR"/*.tar.gz 2>/dev/null | wc -l)" -gt 5 ]; then
    OFFLINE_MODE=true
fi

if $OFFLINE_MODE; then
    echo "[5/6] 安装 Python 依赖包（离线模式，从 offline_pkgs/ 安装）..."
    PIP_OPTS="-q --no-index --find-links=$OFFLINE_DIR"
else
    echo "[5/6] 安装 Python 依赖包（联网模式，首次约需 3~8 分钟）..."
fi

# 使用国内 pip 镜像（联网模式用）
PIP_MIRROR="https://mirrors.aliyun.com/pypi/simple/"
PIP_ONLINE_OPTS="-q -i $PIP_MIRROR --trusted-host mirrors.aliyun.com"

# 升级 pip
if $OFFLINE_MODE; then
    $PIP install --upgrade pip $PIP_OPTS 2>&1 | tail -1 || true
else
    $PIP install --upgrade pip $PIP_ONLINE_OPTS 2>&1 | tail -1
fi

# ── 把系统 PyQt 链接到虚拟环境的公共函数 ──────────────────────
link_sys_pyqt_to_venv() {
    local mod="$1"   # PyQt6 or PyQt5
    SITE_PACKAGES=$($PYTHON -c "import site; print(site.getsitepackages()[0])" 2>/dev/null || true)
    if [ -z "$SITE_PACKAGES" ]; then return 1; fi
    SYS_MOD=$(python3 -c "import $mod, os; print(os.path.dirname($mod.__file__))" 2>/dev/null || true)
    if [ -n "$SYS_MOD" ]; then
        echo "$SYS_MOD" > "$SITE_PACKAGES/${mod,,}.pth"
        echo "      ✅ ${mod}（系统包）链接到虚拟环境：$SYS_MOD"
        return 0
    fi
    return 1
}

# ── PyQt6/PyQt5：先检查已有，再按需安装 ────────────────────────
PYQT6_OK=false

# ★ 预检查前：把系统已有的 PyQt5/PyQt6 链接到虚拟环境（若系统有但 venv 还没链接）
if ! $PYTHON -c "import PyQt6" 2>/dev/null && python3 -c "import PyQt6" 2>/dev/null; then
    link_sys_pyqt_to_venv PyQt6 || true
fi
if ! $PYTHON -c "import PyQt5" 2>/dev/null && python3 -c "import PyQt5" 2>/dev/null; then
    link_sys_pyqt_to_venv PyQt5 || true
fi

# ★ 预检查：虚拟环境中已有 PyQt6 或 PyQt5，直接跳过安装
if $PYTHON -c "import PyQt6" 2>/dev/null; then
    echo "      ✅ PyQt6 已安装，跳过"
    PYQT6_OK=true
elif $PYTHON -c "import PyQt5" 2>/dev/null; then
    echo "      ✅ PyQt5 已安装，注入兼容适配层..."
    SITE_PACKAGES=$($PYTHON -c "import site; print(site.getsitepackages()[0])" 2>/dev/null || true)
    if [ -n "$SITE_PACKAGES" ] && [ -f "$SCRIPT_DIR/pyqt5_compat.py" ]; then
        cp "$SCRIPT_DIR/pyqt5_compat.py" "$SITE_PACKAGES/pyqt5_compat.py"
        echo "import pyqt5_compat" > "$SITE_PACKAGES/pyqt6_compat.pth"
        echo "      ✅ 兼容适配层已注入（pyqt5_compat.py）"
    fi
    PYQT6_OK=true
else
    # 没有可用的 PyQt，开始安装 PyQt6
    echo "      安装 PyQt6..."

    # 尝试 pip 安装
    if $OFFLINE_MODE; then
        echo "        离线安装（offline_pkgs/）..."
        PIP_ERR=$($PIP install $PIP_OPTS "PyQt6" 2>&1)
    else
        echo "        联网安装（镜像：$PIP_MIRROR）..."
        PIP_ERR=$($PIP install $PIP_ONLINE_OPTS "PyQt6>=6.6.0" 2>&1)
    fi

    if echo "$PIP_ERR" | grep -qE "Successfully installed|already satisfied"; then
        PYQT6_OK=true
        echo "      ✅ PyQt6（pip）安装成功"
    else
        # 打印失败原因
        echo "      ⚠️  pip 安装 PyQt6 失败"
        if $OFFLINE_MODE; then
            echo "         offline_pkgs/ 中未找到 PyQt6 包"
            echo "         请在联网机器上先运行：./download_deps.sh"
        else
            echo "$PIP_ERR" | grep -E "ERROR|error|No matching|not find|Cannot" | head -3 | sed 's/^/        /'
        fi
        echo "      尝试系统包..."

        if is_apt; then
            for pkg in python3-pyqt6 python3-qt6 python3-pyqt6-sip; do
                sudo apt-get install -y -qq "$pkg" 2>/dev/null && true || true
            done
            link_sys_pyqt_to_venv PyQt6 && PYQT6_OK=true || true
        elif is_dnf || is_yum; then
            PKG_MGR="dnf"; is_yum && ! is_dnf && PKG_MGR="yum"
            # 银河麒麟 / openEuler / CentOS Stream 常见包名
            for pkg in python3-pyqt6 python3-qt6 python36-PyQt6 python3-PyQt6 PyQt6; do
                sudo $PKG_MGR install -y -q "$pkg" 2>/dev/null && true || true
            done
            link_sys_pyqt_to_venv PyQt6 && PYQT6_OK=true || true
        fi

        # ── 如果 PyQt6 彻底装不上，尝试 PyQt5 降级 ──────────────────
        if ! $PYQT6_OK; then
            echo "      ⚠️  PyQt6 系统包也不可用，尝试 PyQt5..."
            PYQT5_INSTALLED=false

            # 先尝试 pip（离线包 / 联网两条路）
            if $OFFLINE_MODE; then
                PIP5_ERR=$($PIP install $PIP_OPTS "PyQt5" 2>&1)
            else
                PIP5_ERR=$($PIP install $PIP_ONLINE_OPTS "PyQt5>=5.15" 2>&1)
            fi
            if echo "$PIP5_ERR" | grep -qE "Successfully installed|already satisfied"; then
                PYQT5_INSTALLED=true
                echo "      ✅ PyQt5（pip）安装成功"
            fi

            # pip 失败 → 尝试系统包（apt 有 python3-pyqt5，dnf/yum 一般没有，跳过无效包名）
            if ! $PYQT5_INSTALLED; then
                if is_apt; then
                    sudo apt-get install -y -qq python3-pyqt5 2>/dev/null && true || true
                    link_sys_pyqt_to_venv PyQt5 && PYQT5_INSTALLED=true || true
                elif is_dnf || is_yum; then
                    # openEuler/麒麟 DNF 仓库没有 PyQt5 二进制包，提示用编译脚本
                    echo "      ℹ️  DNF 仓库无 PyQt5 预编译包，需从源码编译"
                    echo "         可运行 ./build_pyqt5.sh 一键编译安装（约需 15~30 分钟）"
                fi
            fi

            # 注入 PyQt5 兼容适配层
            if $PYQT5_INSTALLED; then
                echo "      ✅ 使用 PyQt5 + 兼容适配层 替代 PyQt6"
                SITE_PACKAGES=$($PYTHON -c "import site; print(site.getsitepackages()[0])" 2>/dev/null || true)
                if [ -n "$SITE_PACKAGES" ] && [ -f "$SCRIPT_DIR/pyqt5_compat.py" ]; then
                    cp "$SCRIPT_DIR/pyqt5_compat.py" "$SITE_PACKAGES/pyqt5_compat.py"
                    echo "import pyqt5_compat" > "$SITE_PACKAGES/pyqt6_compat.pth"
                    echo "        ✅ 兼容适配层已注入虚拟环境"
                fi
                PYQT6_OK=true
            fi
        fi

        if ! $PYQT6_OK; then
            echo ""
            echo "  ❌ PyQt6/PyQt5 均安装失败！"
            echo ""
            echo "  ── 解决方案（根据你的系统选一种）──────────────────────"
            echo ""
            if is_apt; then
                echo "  方案A：系统包（推荐）"
                echo "    sudo apt-get install python3-pyqt6"
                echo "    或"
                echo "    sudo apt-get install python3-pyqt5"
            elif is_dnf || is_yum; then
                echo "  方案A：从源码编译 PyQt5（推荐）"
                echo "    chmod +x build_pyqt5.sh && ./build_pyqt5.sh"
                echo "    （约需 15~30 分钟，编译完成后重新运行 install_kylin.sh）"
                echo ""
                echo "  方案B：pip 联网安装"
                echo "    $PIP install PyQt5 -i $PIP_MIRROR"
            fi
            echo ""
            echo "  安装完成后重新运行：./install_kylin.sh"
            echo ""
            exit 1
        fi
    fi
fi  # end of else (no PyQt pre-installed)

# ── 其他基础包 ───────────────────────────────────────────────
echo "      安装数据库驱动和依赖包..."

BASE_PKGS="sqlalchemy>=2.0 pymysql>=1.1 psycopg2-binary>=2.9 pymssql>=2.2 oracledb>=2.0 pandas>=2.0 requests>=2.31 openpyxl>=3.1"

install_pkgs() {
    local opts="$1"; shift
    local pkgs="$*"
    OUT=$($PIP install $opts $pkgs 2>&1)
    echo "$OUT" | grep -E "Successfully installed|already satisfied|WARNING|ERROR" || true
    # 检查是否有包安装失败
    if echo "$OUT" | grep -qE "^ERROR|No matching distribution|Could not find"; then
        return 1
    fi
    return 0
}

if $OFFLINE_MODE; then
    # 离线先试，失败的包再切联网补装
    echo "        离线安装（offline_pkgs/）..."
    if ! install_pkgs "$PIP_OPTS" $BASE_PKGS; then
        echo "      ⚠️  部分包离线安装失败，切换联网补装..."
        install_pkgs "$PIP_ONLINE_OPTS" $BASE_PKGS || true
    fi
else
    install_pkgs "$PIP_ONLINE_OPTS" $BASE_PKGS || true
fi

# JDBC 支持（需要 Java）
if command -v java &>/dev/null; then
    echo "      安装 jaydebeapi（JDBC 支持）..."
    JDBC_PKGS="JPype1>=1.4 jaydebeapi>=1.2"
    if $OFFLINE_MODE; then
        install_pkgs "$PIP_OPTS" $JDBC_PKGS || install_pkgs "$PIP_ONLINE_OPTS" $JDBC_PKGS || true
    else
        install_pkgs "$PIP_ONLINE_OPTS" $JDBC_PKGS || true
    fi
else
    echo "      跳过 jaydebeapi（无 Java 环境）"
fi

# 安装后验证关键包
echo "      验证关键依赖..."
MISSING=""
for pkg in sqlalchemy PyQt5 PyQt6; do
    if ! $PYTHON -c "import ${pkg,,}" 2>/dev/null && ! $PYTHON -c "import $pkg" 2>/dev/null; then
        # sqlalchemy 特殊处理
        if [ "$pkg" = "sqlalchemy" ]; then
            $PYTHON -c "import sqlalchemy" 2>/dev/null || MISSING="$MISSING $pkg"
        fi
    fi
done
# 只检查最关键的
for pkg in sqlalchemy; do
    if ! $PYTHON -c "import $pkg" 2>/dev/null; then
        MISSING="$MISSING $pkg"
    fi
done
if [ -n "$MISSING" ]; then
    echo "      ⚠️  以下包仍未安装：$MISSING"
    echo "      手动安装命令："
    echo "        source venv/bin/activate && pip install$MISSING -i $PIP_MIRROR"
else
    echo "      ✅ 关键依赖验证通过"
fi

# ODBC 支持（已装 ODBC 驱动时）
if $ODBC_INSTALLED || odbcinst -q -d 2>/dev/null | grep -qi "inceptor\|transwarp"; then
    echo "      安装 pyodbc（ODBC 支持）..."
    $PIP install $ACTIVE_PIP_OPTS "pyodbc>=5.0" \
        2>&1 | grep -E "Successfully installed|already satisfied|ERROR" || true
fi

echo "      Python 依赖安装完成"

# ---------- 6. 创建启动脚本 ----------
echo "[6/6] 创建启动脚本..."

cat > "$SCRIPT_DIR/run.sh" << RUNEOF
#!/bin/bash
SCRIPT_DIR="\$(cd "\$(dirname "\${BASH_SOURCE[0]}")" && pwd)"

# 优先使用虚拟环境，回退到系统 python3
PYTHON=""
if [ -f "\$SCRIPT_DIR/.venv/bin/python" ]; then
    PYTHON="\$SCRIPT_DIR/.venv/bin/python"
else
    echo "⚠️  未找到虚拟环境（.venv），尝试使用系统 Python..."
    echo "    建议先运行：cd \$SCRIPT_DIR && ./install_kylin.sh"
    for candidate in python3.12 python3.11 python3.10 python3.9 python3; do
        if command -v "\$candidate" &>/dev/null; then
            PYTHON=\$(command -v "\$candidate")
            echo "    使用系统 Python：\$PYTHON"
            break
        fi
    done
fi

if [ -z "\$PYTHON" ]; then
    echo "❌ 未找到可用的 Python 解释器"
    echo "   请先运行：chmod +x install_kylin.sh && ./install_kylin.sh"
    exit 1
fi

# 检查 PyQt6 是否可用
if ! "\$PYTHON" -c "import PyQt6" 2>/dev/null; then
    echo "❌ PyQt6 未安装！请运行以下命令修复："
    echo ""
    echo "   cd \$SCRIPT_DIR"
    echo "   ./install_kylin.sh"
    echo ""
    echo "   或手动安装："
    echo "   sudo apt-get install python3-pyqt6   # Ubuntu/Kylin/UOS"
    echo "   sudo dnf install python3-qt6          # CentOS/RHEL"
    exit 1
fi

# ── Qt 显示环境自动检测 ──────────────────────────────────────
export QT_FONT_DPI="\${QT_FONT_DPI:-96}"
export PYTHONPATH="\$SCRIPT_DIR:\$PYTHONPATH"

if [ -z "\$QT_QPA_PLATFORM" ]; then
    # 1. 已有 DISPLAY → 用 xcb
    if [ -n "\$DISPLAY" ]; then
        export QT_QPA_PLATFORM="xcb"
    # 2. Wayland 会话
    elif [ -n "\$WAYLAND_DISPLAY" ]; then
        export QT_QPA_PLATFORM="wayland"
    else
        # 3. 尝试找桌面会话的 DISPLAY（root 通过终端启动时常见）
        FOUND_DISPLAY=""
        for uid_dir in /run/user/*/; do
            uid=\$(basename "\$uid_dir")
            # 跳过 root（uid=0）自身
            [ "\$uid" = "0" ] && continue
            if [ -S "\$uid_dir/wayland-0" ]; then
                export WAYLAND_DISPLAY="\$uid_dir/wayland-0"
                export QT_QPA_PLATFORM="wayland"
                FOUND_DISPLAY="wayland:\$uid_dir/wayland-0"
                break
            fi
        done
        if [ -z "\$FOUND_DISPLAY" ]; then
            # 尝试 :0 ~ :2
            for d in :0 :1 :2; do
                if xdpyinfo -display "\$d" &>/dev/null 2>&1; then
                    export DISPLAY="\$d"
                    export QT_QPA_PLATFORM="xcb"
                    FOUND_DISPLAY="xcb:\$d"
                    break
                fi
            done
        fi
        if [ -z "\$FOUND_DISPLAY" ]; then
            # 最后兜底：强制 xcb，让 Qt 自己报错提示
            export DISPLAY="\${DISPLAY:-:0}"
            export QT_QPA_PLATFORM="xcb"
            echo "⚠️  未检测到图形显示环境，尝试 DISPLAY=:0"
            echo "   如果启动失败，请在桌面终端中运行，或先执行："
            echo "   export DISPLAY=:0 && ./run.sh"
        fi
    fi
fi
echo "  Qt 平台：\$QT_QPA_PLATFORM  DISPLAY=\${DISPLAY:-（wayland）}"

# JDBC 支持：自动探测 JAVA_HOME
if [ -z "\$JAVA_HOME" ]; then
    for jvm_dir in \
        /usr/lib/jvm/default-java \
        /usr/lib/jvm/java-11-openjdk-amd64 \
        /usr/lib/jvm/java-11-openjdk-arm64 \
        /usr/lib/jvm/java-17-openjdk-amd64 \
        /usr/lib/jvm/java-17-openjdk-arm64 \
        /usr/lib/jvm/java-8-openjdk-amd64 \
        /usr/lib/jvm/java-8-openjdk-arm64; do
        if [ -d "\$jvm_dir" ]; then
            export JAVA_HOME="\$jvm_dir"
            break
        fi
    done
    # 通用方式：从 java 二进制反推
    if [ -z "\$JAVA_HOME" ] && command -v java &>/dev/null; then
        export JAVA_HOME=\$(dirname \$(dirname \$(readlink -f \$(which java))))
    fi
fi

cd "\$SCRIPT_DIR"
exec "\$PYTHON" main.py "\$@"
RUNEOF
chmod +x "$SCRIPT_DIR/run.sh"

# ── 创建桌面快捷方式 ──────────────────────────────────────────
ICON="$SCRIPT_DIR/icon.png"
[ ! -f "$ICON" ] && ICON=""   # 无图标时不报错

DESKTOP_FILE="$HOME/Desktop/AIDBTools.desktop"
# 麒麟桌面目录可能叫"桌面"
[ ! -d "$HOME/Desktop" ] && mkdir -p "$HOME/Desktop"

cat > "$DESKTOP_FILE" << DEOF
[Desktop Entry]
Version=1.0
Type=Application
Name=AIDBTools
GenericName=AI 数据库管理工具
Comment=支持 MySQL/PostgreSQL/Oracle/SQL Server/星环等数据库的 AI 辅助管理工具
Exec=$SCRIPT_DIR/run.sh
Icon=$ICON
Terminal=false
StartupWMClass=AIDBTools
Categories=Development;Database;
Keywords=database;sql;ai;db;
DEOF
chmod +x "$DESKTOP_FILE"

# 麒麟/UOS 桌面信任
if command -v gio &>/dev/null; then
    gio set "$DESKTOP_FILE" metadata::trusted true 2>/dev/null || true
fi
# Deepin 文件管理器信任
if command -v dbus-send &>/dev/null; then
    dbus-send --session --dest=com.deepin.filemanager.filedialog \
        /com/deepin/filemanager/filedialog \
        com.deepin.filemanager.filedialog.setFileDialogFilter \
        string:"$DESKTOP_FILE" 2>/dev/null || true
fi

# ── 完成 ─────────────────────────────────────────────────────
# 写入国产系统平台标识到 version.py
if [ -f "$SCRIPT_DIR/version.py" ]; then
    python3 -c "
import re, pathlib
f = pathlib.Path('$SCRIPT_DIR/version.py')
txt = f.read_text(encoding='utf-8')
txt = re.sub(r'BUILD_PLATFORM\s*=\s*\"[^\"]*\"', 'BUILD_PLATFORM = \"domestic\"', txt)
f.write_text(txt, encoding='utf-8')
" 2>/dev/null || true
fi

echo ""
echo "=========================================================="
echo "  ✅ 安装完成！"
echo ""
echo "  驱动状态："
if command -v java &>/dev/null; then
    echo "  ✅ Java（JDBC）：$(java -version 2>&1 | head -1)"
else
    echo "  ⚠️  Java 未安装（星环 JDBC 不可用）"
fi
if $ODBC_INSTALLED; then
    echo "  ✅ 星环 ODBC：已安装"
else
    echo "  ⚠️  星环 ODBC：未安装（将使用 JDBC 模式）"
fi
echo ""
echo "  启动方式："
echo "  1. 双击桌面图标 AIDBTools"
echo "  2. 或在终端执行：./run.sh"
echo "  3. 或直接执行  ：$SCRIPT_DIR/run.sh"
echo "=========================================================="
