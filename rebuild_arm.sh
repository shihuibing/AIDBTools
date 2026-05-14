#!/bin/bash
# ============================================================
# ARM 银河麒麟 - 更新代码并重新打包脚本
# 用途：修复 Python 3.9 兼容性问题后重新打包
# ============================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "================================================"
echo "  AIDBTools ARM 版 - 更新并重新打包"
echo "  工作目录: $SCRIPT_DIR"
echo "================================================"

# 1. 清理旧的构建
echo ""
echo "[1/4] 清理旧的构建文件..."
rm -rf build dist .venv_arm_build
echo "  ✅ 清理完成"

# 2. 验证关键文件的兼容性修复
echo ""
echo "[2/4] 验证 Python 3.9 兼容性修复..."

check_file() {
    local file="$1"
    local pattern="$2"
    if grep -q "$pattern" "$file" 2>/dev/null; then
        echo "  ❌ $file 仍包含不兼容语法: $pattern"
        return 1
    else
        echo "  ✅ $file 已修复"
        return 0
    fi
}

ERRORS=0
check_file "core/ai_chat.py" "str | None" || ERRORS=$((ERRORS+1))
check_file "ui/main_window.py" "str | None" || ERRORS=$((ERRORS+1))
check_file "ui/model_config_window.py" "dict | None" || ERRORS=$((ERRORS+1))
check_file "ui/ai_chat_window.py" "str | None" || ERRORS=$((ERRORS+1))

if [ $ERRORS -gt 0 ]; then
    echo ""
    echo "  ⚠️  发现 $ERRORS 个文件仍有兼容性问题"
    echo "  请确保从 Windows 复制了所有修复后的文件"
    exit 1
fi

echo "  ✅ 所有文件已通过兼容性检查"

# 3. 运行打包脚本
echo ""
echo "[3/4] 开始打包..."
chmod +x build_arm_kylin.sh
./build_arm_kylin.sh

# 4. 验证输出
echo ""
echo "[4/4] 验证打包结果..."

# 查找最新的打包文件
LATEST_TAR=$(ls -t release/kylin_arm/*/AIDBTools_v*_kylin_arm_aarch64.tar.gz 2>/dev/null | head -1)

if [ -n "$LATEST_TAR" ]; then
    TAR_SIZE=$(du -sh "$LATEST_TAR" | cut -f1)
    echo ""
    echo "================================================"
    echo "  ✅ 打包成功！"
    echo ""
    echo "  文件: $(basename $LATEST_TAR)"
    echo "  大小: $TAR_SIZE"
    echo "  位置: $LATEST_TAR"
    echo ""
    echo "  测试运行："
    echo "  1. 解压: tar xzf $LATEST_TAR"
    echo "  2. 进入目录并运行: cd AIDBTools_* && ./run.sh"
    echo "================================================"
else
    echo "  ❌ 未找到打包输出文件"
    exit 1
fi
