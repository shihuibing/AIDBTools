#!/bin/bash
# ============================================================
# AIDBTools 国产系统版 —— 源码包打包脚本
# 在 Windows（WSL2）或任意 Linux 机器上运行
# 生成：release/domestic/v{VER}/AIDBTools_v{VER}_domestic.tar.gz
# ============================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# ── 每次打包前自动递增补丁版本号 ────────────────────────────────
VER=$(python3 -c "import sys; sys.path.insert(0,'$SCRIPT_DIR'); from version import bump_patch_version; print(bump_patch_version())" 2>/dev/null)
if [ -z "$VER" ]; then
    echo "  ❌ 生成版本号失败"
    exit 1
fi
PKG_NAME="AIDBTools_v${VER}_domestic"
DIST_DIR="$SCRIPT_DIR/release/domestic/v${VER}"
TMP_DIR="/tmp/${PKG_NAME}"

echo "================================================"
echo "  AIDBTools v${VER} 国产系统源码包"
echo "  输出目录: $DIST_DIR"
echo "================================================"

mkdir -p "$DIST_DIR"

# ── 写入平台标识 ──────────────────────────────────────────────
python3 -c "import sys; sys.path.insert(0,'$SCRIPT_DIR'); from version import set_build_platform; set_build_platform('domestic'); print('  [OK] BUILD_PLATFORM = domestic')"

# ── 组织临时打包目录 ──────────────────────────────────────────
rm -rf "$TMP_DIR"
mkdir -p "$TMP_DIR"

# 复制核心文件
rsync -av --exclude='__pycache__' \
         --exclude='*.pyc' \
         --exclude='.venv*' \
         --exclude='build/' \
         --exclude='dist/' \
         --exclude='release/' \
         --exclude='build_log.txt' \
         "$SCRIPT_DIR/" "$TMP_DIR/"

# ── 压缩 ──────────────────────────────────────────────────────
cd /tmp
tar -czf "$DIST_DIR/${PKG_NAME}.tar.gz" "${PKG_NAME}/"
echo "  ✅ 打包完成：$DIST_DIR/${PKG_NAME}.tar.gz"
SIZE=$(du -sh "$DIST_DIR/${PKG_NAME}.tar.gz" | cut -f1)
echo "  📦 文件大小：$SIZE"

# ── 恢复 BUILD_PLATFORM ───────────────────────────────────────
python3 -c "import sys; sys.path.insert(0,'$SCRIPT_DIR'); from version import set_build_platform; set_build_platform('source'); print('  [OK] BUILD_PLATFORM 已恢复为 source')"

echo ""
echo "  国产系统版源码包已生成："
echo "  $DIST_DIR/${PKG_NAME}.tar.gz"
echo ""
echo "  部署到目标机器："
echo "  1. 解压：tar -xzf ${PKG_NAME}.tar.gz"
echo "  2. 安装：cd ${PKG_NAME} && ./install_kylin.sh"
echo "================================================"
