#!/bin/bash
# ============================================================
# 在银河麒麟 x86_64 上安装 Python 3.9
# 用于 AIDBTools 打包环境
# ============================================================

set -e

echo "================================================"
echo "  安装 Python 3.9 for AIDBTools"
echo "================================================"
echo ""

# 检测包管理器
is_apt() { command -v apt-get &>/dev/null; }
is_dnf() { command -v dnf &>/dev/null; }
is_yum() { command -v yum &>/dev/null; }

# ========== 方法 1: 从系统仓库安装（推荐）==========
install_from_repo() {
    echo "[方法 1] 尝试从系统仓库安装 Python 3.9..."
    
    if is_apt; then
        sudo apt-get update -qq
        sudo apt-get install -y -qq python3.9 python3.9-venv python3.9-dev 2>&1 | tail -5
        
        if command -v python3.9 &>/dev/null; then
            echo "  ✅ Python 3.9 安装成功"
            python3.9 --version
            return 0
        fi
        
        # 如果 3.9 不可用，尝试 3.8
        echo "  ⚠️  Python 3.9 不可用，尝试 Python 3.8..."
        sudo apt-get install -y -qq python3.8 python3.8-venv python3.8-dev 2>&1 | tail -5
        
        if command -v python3.8 &>/dev/null; then
            echo "  ✅ Python 3.8 安装成功"
            python3.8 --version
            return 0
        fi
        
    elif is_dnf; then
        sudo dnf install -y -q python39 python39-devel 2>&1 | tail -5
        
        if command -v python3.9 &>/dev/null; then
            echo "  ✅ Python 3.9 安装成功"
            python3.9 --version
            return 0
        fi
        
    elif is_yum; then
        sudo yum install -y -q python39 python39-devel 2>&1 | tail -5
        
        if command -v python3.9 &>/dev/null; then
            echo "  ✅ Python 3.9 安装成功"
            python3.9 --version
            return 0
        fi
    fi
    
    return 1
}

# ========== 方法 2: 从源码编译 ==========\ninstall_from_source() {
    echo ""
    echo "[方法 2] 从源码编译安装 Python 3.9..."
    echo "  这可能需要 10-20 分钟，请耐心等待..."
    
    # 安装编译依赖
    if is_apt; then
        sudo apt-get install -y -qq \
            build-essential zlib1g-dev libncurses5-dev \
            libgdbm-dev libnss3-dev libssl-dev libreadline-dev \
            libffi-dev libsqlite3-dev wget libbz2-dev 2>&1 | tail -3
    elif is_dnf || is_yum; then
        sudo dnf install -y -q \
            gcc make zlib-devel bzip2-devel openssl-devel \
            ncurses-devel sqlite-devel readline-devel \
            tk-devel libffi-devel xz-devel 2>&1 | tail -3
    fi
    
    # 下载 Python 3.9.18（最新的 3.9.x）
    PYTHON_VERSION="3.9.18"
    PYTHON_SRC="Python-${PYTHON_VERSION}"
    PYTHON_TAR="${PYTHON_SRC}.tgz"
    DOWNLOAD_URL="https://www.python.org/ftp/python/${PYTHON_VERSION}/${PYTHON_TAR}"
    
    cd /tmp
    echo "  下载 Python 源码..."
    wget -q "$DOWNLOAD_URL" || curl -sO "$DOWNLOAD_URL"
    
    echo "  解压源码..."
    tar xzf "$PYTHON_TAR"
    cd "$PYTHON_SRC"
    
    echo "  配置编译选项..."
    ./configure --enable-optimizations --prefix=/usr/local
    
    echo "  编译（这可能需要几分钟）..."
    make -j$(nproc) 2>&1 | tail -5
    
    echo "  安装..."
    sudo make altinstall 2>&1 | tail -3
    
    # 清理
    cd /tmp
    rm -rf "$PYTHON_SRC" "$PYTHON_TAR"
    
    # 验证
    if command -v python3.9 &>/dev/null; then
        echo "  ✅ Python 3.9 编译安装成功"
        python3.9 --version
        return 0
    else
        echo "  ❌ 安装失败"
        return 1
    fi
}

# ========== 方法 3: 使用 pyenv ==========\ninstall_via_pyenv() {
    echo ""
    echo "[方法 3] 使用 pyenv 安装 Python 3.9..."
    
    # 安装 pyenv 依赖
    if is_apt; then
        sudo apt-get install -y -qq \
            make build-essential libssl-dev zlib1g-dev \
            libbz2-dev libreadline-dev libsqlite3-dev \
            wget curl llvm libncurses5-dev libncursesw5-dev \
            xz-utils tk-dev libffi-dev liblzma-dev git 2>&1 | tail -3
    fi
    
    # 安装 pyenv
    curl https://pyenv.run | bash
    
    # 配置环境变量
    export PYENV_ROOT="$HOME/.pyenv"
    export PATH="$PYENV_ROOT/bin:$PATH"
    eval "$(pyenv init -)"
    
    # 安装 Python 3.9
    pyenv install 3.9.18
    pyenv global 3.9.18
    
    if command -v python3.9 &>/dev/null; then
        echo "  ✅ Python 3.9 通过 pyenv 安装成功"
        python3.9 --version
        return 0
    fi
    
    return 1
}

# ========== 主流程 ==========\necho "当前 Python 版本:"
python3 --version 2>/dev/null || echo "  (未找到 python3)"
echo ""

# 尝试方法 1
if install_from_repo; then
    echo ""
    echo "================================================"
    echo "  ✅ Python 3.8/3.9 安装成功！"
    echo ""
    echo "  现在可以重新运行打包脚本："
    echo "  cd /home/AIDBTools"
    echo "  ./build_kylin_x86_offline.sh"
    echo "================================================"
    exit 0
fi

echo "  ⚠️  系统仓库中没有 Python 3.8/3.9"
echo ""

# 询问用户选择
echo "请选择安装方式："
echo "  1. 从源码编译（推荐，需要 10-20 分钟）"
echo "  2. 使用 pyenv（灵活，但配置稍复杂）"
echo "  3. 继续使用 Python 3.7（不推荐，兼容性差）"
echo ""
read -p "请输入选择 [1/2/3]: " choice

case $choice in
    1)
        if install_from_source; then
            echo ""
            echo "================================================"
            echo "  ✅ Python 3.9 编译安装成功！"
            echo ""
            echo "  现在可以重新运行打包脚本："
            echo "  cd /home/AIDBTools"
            echo "  ./build_kylin_x86_offline.sh"
            echo "================================================"
        else
            echo ""
            echo "  ❌ 编译安装失败，请检查错误信息"
            exit 1
        fi
        ;;
    2)
        if install_via_pyenv; then
            echo ""
            echo "================================================"
            echo "  ✅ Python 3.9 通过 pyenv 安装成功！"
            echo ""
            echo "  注意：需要重启终端或执行："
            echo "  export PYENV_ROOT=\"\$HOME/.pyenv\""
            echo "  export PATH=\"\$PYENV_ROOT/bin:\$PATH\""
            echo "  eval \"\$(pyenv init -)\""
            echo ""
            echo "  然后重新运行打包脚本"
            echo "================================================"
        else
            echo ""
            echo "  ❌ pyenv 安装失败"
            exit 1
        fi
        ;;
    3)
        echo ""
        echo "================================================"
        echo "  ⚠️  您选择了继续使用 Python 3.7"
        echo ""
        echo "  警告："
        echo "  - Python 3.7 已于 2023 年停止官方支持"
        echo "  - PyQt5 只能使用非常旧的版本 (5.14.2)"
        echo "  - 某些功能可能无法正常工作"
        echo "  - 存在安全风险"
        echo ""
        echo "  建议尽快升级到 Python 3.8+"
        echo "================================================"
        ;;
    *)
        echo "  ❌ 无效选择"
        exit 1
        ;;
esac
