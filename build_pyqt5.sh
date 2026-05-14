#!/bin/bash
# build_pyqt5.sh
# 在 openEuler / 麒麟 ARM (aarch64) 上从源码编译安装 PyQt5
# 适用场景：pip 安装失败、系统源无预编译包
# 用法：chmod +x build_pyqt5.sh && ./build_pyqt5.sh
# 约需 15~30 分钟（视 CPU 性能）

set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "======================================================"
echo "  PyQt5 源码编译安装脚本"
echo "  适用：openEuler / 麒麟 ARM aarch64"
echo "======================================================"
echo ""

# ── 检测包管理器 ───────────────────────────────────────────
is_dnf() { command -v dnf &>/dev/null; }
is_yum() { command -v yum &>/dev/null; }
is_apt() { command -v apt-get &>/dev/null; }

PKG_MGR=""
if is_dnf;      then PKG_MGR="dnf"
elif is_yum;    then PKG_MGR="yum"
elif is_apt;    then PKG_MGR="apt-get"
else
    echo "❌ 未找到支持的包管理器（dnf/yum/apt-get）"
    exit 1
fi

echo "[1/6] 安装编译依赖..."
if [ "$PKG_MGR" = "dnf" ] || [ "$PKG_MGR" = "yum" ]; then
    sudo $PKG_MGR install -y \
        python3-devel \
        qt5-qtbase-devel \
        qt5-qtwebchannel-devel \
        sip5 sip \
        gcc gcc-c++ make \
        openssl-devel \
        dbus-devel \
        libX11-devel \
        libxcb-devel \
        xcb-util-devel \
        xcb-util-image-devel \
        xcb-util-keysyms-devel \
        xcb-util-renderutil-devel \
        xcb-util-wm-devel \
        libxkbcommon-devel \
        libxkbcommon-x11-devel \
        mesa-libGL-devel \
        fontconfig-devel \
        freetype-devel \
        2>/dev/null || true
    # Qt5 开发包
    sudo $PKG_MGR install -y qt5-devel 2>/dev/null || \
    sudo $PKG_MGR install -y qt5-qtbase-devel 2>/dev/null || true
elif [ "$PKG_MGR" = "apt-get" ]; then
    sudo apt-get install -y \
        python3-dev \
        python3-sip-dev \
        qtbase5-dev \
        qttools5-dev \
        libqt5webkit5-dev \
        libdbus-1-dev \
        libgl-dev \
        build-essential \
        2>/dev/null || true
fi
echo "   ✅ 编译依赖安装完成"

# ── 检测 Python 和 pip ────────────────────────────────────
VENV_PYTHON="$SCRIPT_DIR/.venv/bin/python"
if [ -f "$VENV_PYTHON" ]; then
    PYTHON="$VENV_PYTHON"
    PIP="$SCRIPT_DIR/.venv/bin/pip"
    echo "[2/6] 使用虚拟环境 Python：$PYTHON"
else
    PYTHON="$(command -v python3.9 || command -v python3.10 || command -v python3.11 || command -v python3 || echo '')"
    PIP="$(command -v pip3 || echo '')"
    if [ -z "$PYTHON" ]; then
        echo "❌ 未找到 Python3，请先运行 install_kylin.sh"
        exit 1
    fi
    echo "[2/6] 使用系统 Python：$PYTHON（建议先运行 install_kylin.sh 创建虚拟环境）"
fi

PYTHON_VER=$($PYTHON --version 2>&1 | grep -oP '\d+\.\d+' | head -1)
echo "   Python 版本：$PYTHON_VER"

PIP_MIRROR="https://mirrors.aliyun.com/pypi/simple/"
PIP_OPTS="-i $PIP_MIRROR --trusted-host mirrors.aliyun.com"

# ── 安装 sip（PyQt5 编译必须）────────────────────────────
echo "[3/6] 安装 sip..."
# 先尝试 pip 安装
if $PIP install $PIP_OPTS "sip>=6.0" 2>/dev/null; then
    echo "   ✅ sip（pip）安装成功"
else
    # 尝试旧版 sip4
    if $PIP install $PIP_OPTS "sip==4.19.25" 2>/dev/null; then
        echo "   ✅ sip4 安装成功"
    else
        echo "   ⚠️  sip pip 安装失败，尝试系统包..."
        if [ "$PKG_MGR" = "dnf" ] || [ "$PKG_MGR" = "yum" ]; then
            sudo $PKG_MGR install -y python3-sip python3-sip-devel sip 2>/dev/null || true
            # openEuler 可能叫 python3-PyQt5-sip
            sudo $PKG_MGR install -y python3-PyQt5-sip 2>/dev/null || true
        fi
        echo "   ✅ sip 系统包安装"
    fi
fi

# ── 尝试直接 pip 安装 PyQt5（最后机会）──────────────────
echo "[4/6] 尝试 pip 安装 PyQt5..."
if $PIP install $PIP_OPTS "PyQt5>=5.15" 2>&1 | tee /tmp/pyqt5_pip.log | grep -qE "Successfully installed|already satisfied"; then
    echo "   ✅ PyQt5（pip）安装成功！不需要源码编译"
    echo ""
    echo "   现在可以运行：./install_kylin.sh"
    exit 0
fi

echo "   ℹ️  pip 安装失败，转向源码编译..."
echo "   错误摘要："
grep -E "ERROR|error|Cannot|No matching" /tmp/pyqt5_pip.log | head -3 | sed 's/^/   /'

# ── 检测 Qt5 版本 ─────────────────────────────────────────
echo "[5/6] 检测 Qt5 环境..."
QT5_VERSION=$(qmake-qt5 --version 2>/dev/null | grep -oP 'Qt version \K[\d.]+' || \
              qmake --version 2>/dev/null | grep -oP 'Qt version \K[\d.]+' || echo "")

if [ -z "$QT5_VERSION" ]; then
    echo "   ❌ 未找到 Qt5 开发环境（qmake 未安装）"
    echo ""
    echo "   请先安装 Qt5 开发包："
    if [ "$PKG_MGR" = "dnf" ] || [ "$PKG_MGR" = "yum" ]; then
        echo "   sudo $PKG_MGR install qt5-devel"
        echo "   或"
        echo "   sudo $PKG_MGR install qt5-qtbase-devel"
    elif [ "$PKG_MGR" = "apt-get" ]; then
        echo "   sudo apt-get install qtbase5-dev"
    fi
    echo ""
    exit 1
fi
echo "   ✅ Qt $QT5_VERSION"

# ── 下载并编译 PyQt5 ─────────────────────────────────────
echo "[6/6] 下载并编译 PyQt5..."
WORK_DIR="/tmp/pyqt5_build_$$"
mkdir -p "$WORK_DIR"
cd "$WORK_DIR"

PYQT5_VER="5.15.10"
PYQT5_URL="https://files.pythonhosted.org/packages/source/P/PyQt5/PyQt5-${PYQT5_VER}.tar.gz"
PYQT5_ALIYUN="https://mirrors.aliyun.com/pypi/packages/source/P/PyQt5/PyQt5-${PYQT5_VER}.tar.gz"

echo "   下载 PyQt5 源码（$PYQT5_VER）..."
if ! wget -q "$PYQT5_ALIYUN" -O "PyQt5-${PYQT5_VER}.tar.gz" 2>/dev/null; then
    if ! wget -q "$PYQT5_URL" -O "PyQt5-${PYQT5_VER}.tar.gz" 2>/dev/null; then
        if ! curl -sL "$PYQT5_ALIYUN" -o "PyQt5-${PYQT5_VER}.tar.gz" 2>/dev/null; then
            curl -sL "$PYQT5_URL" -o "PyQt5-${PYQT5_VER}.tar.gz"
        fi
    fi
fi

echo "   解压源码..."
tar xzf "PyQt5-${PYQT5_VER}.tar.gz"
cd "PyQt5-${PYQT5_VER}"

echo "   配置编译（这可能需要 2~3 分钟）..."
# 找 qmake
QMAKE=$(command -v qmake-qt5 || command -v qmake5 || command -v qmake || echo '')
if [ -z "$QMAKE" ]; then
    echo "   ❌ 未找到 qmake，请安装 qt5-qtbase-devel"
    exit 1
fi

$PYTHON setup.py --qmake="$QMAKE" configure 2>&1 | tail -5

echo "   编译中（这可能需要 10~20 分钟）..."
make -j$(nproc) 2>&1 | tail -3

echo "   安装中..."
if [ -f "$VENV_PYTHON" ]; then
    make install DESTDIR="$SCRIPT_DIR/.venv/lib/$($PYTHON --version 2>&1 | grep -oP 'Python \K\d+\.\d+')/site-packages" 2>&1 | tail -3
    # 更可靠的方式：直接安装到虚拟环境
    $PIP install --no-build-isolation --no-deps . 2>/dev/null || make install 2>&1 | tail -3
else
    sudo make install 2>&1 | tail -3
fi

echo ""
echo "======================================================"
echo "  ✅ PyQt5 编译安装完成！"
echo "======================================================"
echo ""
echo "  现在回到项目目录运行："
echo "  cd $SCRIPT_DIR && ./install_kylin.sh"
echo ""

# 清理
cd /
rm -rf "$WORK_DIR"
