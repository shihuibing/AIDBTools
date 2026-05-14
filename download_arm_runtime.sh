#!/bin/bash
# ============================================================
# 下载 ARM 银河麒麟运行时依赖（在有网络的机器上执行）
# 下载后会把 .deb 包放入 build_arm_kylin.sh 所在目录的 runtime_pkgs/
# ============================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PKG_DIR="$SCRIPT_DIR/runtime_pkgs"
ARCH="arm64"

mkdir -p "$PKG_DIR"

echo "=========================================================="
echo "  下载 ARM 银河麒麟运行时依赖包"
echo "  输出目录：$PKG_DIR"
echo "=========================================================="
echo ""

# ── 需要下载的 .deb 包 ────────────────────────────────────
# 这些是 Qt6 应用运行所需的系统级共享库（不含 Python）
# 银河麒麟 V10 ARM 基于 Debian/Ubuntu，用 apt-get download
DEPS=(
    # Qt6 核心运行时
    qt6-base-runtime
    libqt6core6
    libqt6gui6
    libqt6widgets6
    libqt6dbus6
    libqt6network6
    libqt6printsupport6
    libqt6svg6
    # X11 / Wayland 图形库
    libxcb-xinerama0
    libxcb-cursor0
    libxcb-icccm4
    libxcb-image0
    libxcb-keysyms1
    libxcb-randr0
    libxcb-render-util0
    libxcb-shape0
    libxcb-xkb1
    libxkbcommon-x11-0
    libxkbcommon0
    # OpenGL / 图形
    libgl1-mesa-glx
    libglx0
    libopengl0
    libegl1
    # 其他依赖
    libglib2.0-0
    libdbus-1-3
    libfontconfig1
    libfreetype6
    # 中文字体
    fonts-wqy-zenhei
    fonts-wqy-microhei
    fonts-noto-cjk
)

echo "[1/2] 下载依赖包..."
FAILED=0
for pkg in "${DEPS[@]}"; do
    echo "  下载: $pkg"
    cd "$PKG_DIR"
    apt-get download --print-uris "$pkg" 2>/dev/null | \
        grep -oP "http\S+" | while read -r url; do
        filename=$(basename "$url")
        if [ ! -f "$PKG_DIR/$filename" ]; then
            wget -q -O "$PKG_DIR/$filename" "$url" 2>/dev/null || \
                curl -sL -o "$PKG_DIR/$filename" "$url" 2>/dev/null || \
                echo "    ⚠️  $pkg 下载失败"
        fi
    done
done

echo ""
echo "[2/2] 下载依赖包的依赖（递归）..."
cd "$PKG_DIR"
for deb in *.deb; do
    [ -f "$deb" ] || continue
    apt-get download "$(dpkg-deb -f "$deb" Depends 2>/dev/null | \
        tr ',' '\n' | grep -oP '^\S+' | head -5)" 2>/dev/null || true
done

# 去重
cd "$PKG_DIR"
rm -f ./*.dsc ./Packages* ./Release* ./InRelease 2>/dev/null || true

TOTAL=$(ls -1 "$PKG_DIR"/*.deb 2>/dev/null | wc -l)
SIZE=$(du -sh "$PKG_DIR" | cut -f1)

echo ""
echo "=========================================================="
echo "  ✅ 下载完成！"
echo "  共 $TOTAL 个 .deb 包，大小：$SIZE"
echo "  目录：$PKG_DIR"
echo ""
echo "  将此目录复制到离线 ARM 机器上，执行："
echo "  sudo dpkg -i runtime_pkgs/*.deb"
echo "=========================================================="
