#!/bin/bash
# ============================================================
# AIDBTools ARM 银河麒麟版一键部署脚本（完全离线可用）
# 适用：银河麒麟 V10 ARM / 统信UOS ARM / Ubuntu ARM
# 架构：aarch64 (ARM64)
# 
# 用法：chmod +x deploy_arm_kylin.sh && ./deploy_arm_kylin.sh
# 
# PyInstaller 已将所有 Python 依赖和 Qt6 运行时打包进可执行文件，
# 无需联网安装任何 Python 包。
# ============================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ARCH=$(uname -m)
INSTALL_DIR="/opt/AIDBTools"
MISSING_LIBS=""

echo "=========================================================="
echo "  AIDBTools ARM 银河麒麟版一键部署（离线版）"
echo "=========================================================="
echo ""

# ── 架构检查 ──────────────────────────────────────────────
if [ "$ARCH" != "aarch64" ] && [ "$ARCH" != "arm64" ]; then
    echo "  ❌ 当前架构: $ARCH，需要 ARM aarch64"
    exit 1
fi
echo "  系统架构：$ARCH ✅"

# ── 1. 检查系统运行时库 ──────────────────────────────────
echo ""
echo "[1/4] 检查系统运行时库..."

# 银河麒麟 V10 ARM 默认已包含以下库，这里只做检查不做安装
LIBS_REQUIRED=(
    "libGL.so.1:libgl1|libgl1-mesa-glx"
    "libglib-2.0.so.0:libglib2.0-0"
    "libxcb.so.1:libxcb1"
    "libxcb-xinerama.so.0:libxcb-xinerama0"
    "libxcb-cursor.so.0:libxcb-cursor0"
    "libxkbcommon.so.0:libxkbcommon0"
    "libxkbcommon-x11.so.0:libxkbcommon-x11-0"
    "libdbus-1.so.3:libdbus-1-3"
    "libfontconfig.so.1:libfontconfig1"
    "libfreetype.so.6:libfreetype6"
)

for entry in "${LIBS_REQUIRED[@]}"; do
    lib="${entry%%:*}"
    pkg="${entry##*:}"
    if ldconfig -p | grep -q "$lib" 2>/dev/null || find /usr/lib /lib -name "$lib" 2>/dev/null | grep -q .; then
        echo "  ✅ $lib"
    else
        echo "  ❌ 缺少: $lib (包名: $pkg)"
        MISSING_LIBS="$MISSING_LIBS $pkg"
    fi
done

# 中文字体检查
if fc-list :lang=zh &>/dev/null; then
    echo "  ✅ 中文字体已安装"
else
    echo "  ⚠️  未检测到中文字体，界面中文可能显示为方框"
    echo "      如需修复（需联网）: sudo apt-get install fonts-wqy-zenhei fonts-noto-cjk"
fi

if [ -n "$MISSING_LIBS" ]; then
    echo ""
    echo "  ⚠️  缺少系统库: $MISSING_LIBS"
    echo ""
    echo "  解决方法（二选一）："
    echo "  1. 从有网的机器下载离线包："
    echo "     apt-get download $MISSING_LIBS"
    echo "     复制到本机的 runtime_pkgs/ 目录后执行："
    echo "     sudo dpkg -i runtime_pkgs/*.deb"
    echo "  2. 如果银河麒麟系统已自带这些库（通常都有），可以忽略"
    echo ""
    read -p "  是否继续部署？(y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "  已取消部署"
        exit 1
    fi
else
    echo "  ✅ 所有运行时库就绪"
fi

# ── 2. 部署程序文件 ──────────────────────────────────────
echo ""
echo "[2/4] 部署程序文件到 $INSTALL_DIR ..."

# 查找 tar.gz 包
TAR_FILE=""
if [ -f "$SCRIPT_DIR/AIDBTools"*".tar.gz" ]; then
    TAR_FILE=$(ls -1 "$SCRIPT_DIR"/AIDBTools*".tar.gz" | head -1)
elif [ -f "$SCRIPT_DIR"/*.tar.gz ]; then
    TAR_FILE=$(ls -1 "$SCRIPT_DIR"/*.tar.gz | head -1)
fi

if [ -n "$TAR_FILE" ]; then
    echo "  找到安装包：$(basename $TAR_FILE)"
    
    # 清理旧版本
    sudo rm -rf "$INSTALL_DIR" 2>/dev/null || true
    
    # 解压
    TEMP_DIR=$(mktemp -d)
    tar xzf "$TAR_FILE" -C "$TEMP_DIR"
    
    # 提取内部目录名
    INNER_DIR=$(ls -1 "$TEMP_DIR" | head -1)
    
    # 复制到安装目录
    sudo mkdir -p "$INSTALL_DIR"
    sudo cp -r "$TEMP_DIR/$INNER_DIR/"* "$INSTALL_DIR/"
    sudo cp -r "$TEMP_DIR/$INNER_DIR/."* "$INSTALL_DIR/" 2>/dev/null || true
    rm -rf "$TEMP_DIR"
else
    # 没有 tar.gz，假设当前目录就是解压后的程序目录
    if [ -f "$SCRIPT_DIR/AIDBTools" ] || [ -f "$SCRIPT_DIR/run.sh" ]; then
        echo "  未找到 .tar.gz，使用当前目录作为程序目录"
        sudo rm -rf "$INSTALL_DIR" 2>/dev/null || true
        sudo mkdir -p "$INSTALL_DIR"
        sudo cp -r "$SCRIPT_DIR/"* "$INSTALL_DIR/" 2>/dev/null || true
        sudo cp -r "$SCRIPT_DIR/."* "$INSTALL_DIR/" 2>/dev/null || true
    else
        echo "  ❌ 未找到部署包！"
        echo "  请将 AIDBTools_v*_kylin_arm_aarch64.tar.gz 和此脚本放在同一目录"
        exit 1
    fi
fi

# 设置权限
sudo chown -R root:root "$INSTALL_DIR"
sudo chmod +x "$INSTALL_DIR/AIDBTools" 2>/dev/null || true
sudo chmod +x "$INSTALL_DIR/run.sh" 2>/dev/null || true
echo "  ✅ 程序文件已部署"

# ── 3. 创建启动脚本和桌面快捷方式 ────────────────────────
echo ""
echo "[3/4] 创建桌面快捷方式..."

# 创建 /usr/local/bin 软链接方便命令行启动
sudo ln -sf "$INSTALL_DIR/run.sh" /usr/local/bin/aidbtools 2>/dev/null || true

# 创建桌面快捷方式
DESKTOP_DIR="$HOME/Desktop"
[ ! -d "$DESKTOP_DIR" ] && mkdir -p "$DESKTOP_DIR"
[ -d "$HOME/桌面" ] && DESKTOP_DIR="$HOME/桌面"

ICON="$INSTALL_DIR/icon.png"
[ ! -f "$ICON" ] && ICON=""

cat > "$DESKTOP_DIR/AIDBTools.desktop" << DEOF
[Desktop Entry]
Version=1.0
Type=Application
Name=AIDBTools
GenericName=AI 数据库管理工具
Comment=支持 MySQL/PostgreSQL/Oracle/SQL Server/星环等数据库的 AI 辅助管理工具
Exec=$INSTALL_DIR/run.sh
Icon=$ICON
Terminal=false
StartupWMClass=AIDBTools
Categories=Development;Database;
DEOF
chmod +x "$DESKTOP_DIR/AIDBTools.desktop"

# 麒麟桌面信任
if command -v gio &>/dev/null; then
    gio set "$DESKTOP_DIR/AIDBTools.desktop" metadata::trusted true 2>/dev/null || true
fi

echo "  ✅ 桌面快捷方式已创建"

# ── 4. 创建系统服务（可选） ──────────────────────────────
echo ""
echo "[4/4] 检查运行环境..."

# 检查 Java
if command -v java &>/dev/null; then
    echo "  ✅ Java: $(java -version 2>&1 | head -1)"
else
    echo "  ⚠️  Java 未安装（星环 JDBC 不可用，可手动安装）"
fi

# 检查图形环境
if [ -n "$DISPLAY" ] || [ -n "$WAYLAND_DISPLAY" ]; then
    echo "  ✅ 图形环境就绪"
else
    echo "  ⚠️  未检测到图形环境，请在桌面终端中运行"
fi

# ── 完成 ──────────────────────────────────────────────────
echo ""
echo "=========================================================="
echo "  ✅ 部署完成！"
echo ""
echo "  安装目录：$INSTALL_DIR"
echo ""
echo "  启动方式："
echo "  1. 双击桌面图标 AIDBTools"
echo "  2. 终端执行：$INSTALL_DIR/run.sh"
echo "  3. 命令行执行：aidbtools"
echo ""
echo "  卸载方式："
echo "  sudo rm -rf $INSTALL_DIR /usr/local/bin/aidbtools"
echo "  rm -f ~/Desktop/AIDBTools.desktop ~/桌面/AIDBTools.desktop"
echo "=========================================================="
