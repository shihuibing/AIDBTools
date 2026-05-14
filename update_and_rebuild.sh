#!/bin/bash
# ============================================================
# 在 ARM 机器上执行此脚本，自动验证并重新打包
# 前提：已从 Windows 复制了所有修复后的文件
# ============================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "========================================================"
echo "  AIDBTools ARM 版 - 自动验证并重新打包"
echo "  时间: $(date '+%Y-%m-%d %H:%M:%S')"
echo "========================================================"

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 验证函数
verify_fix() {
    local file="$1"
    local desc="$2"

    if [ ! -f "$file" ]; then
        echo -e "${RED}❌ 文件不存在: $file${NC}"
        return 1
    fi

    # 检查是否有 from __future__ import annotations
    if grep -q "from __future__ import annotations" "$file"; then
        echo -e "${GREEN}✅ $desc - 已包含兼容性导入${NC}"
        return 0
    else
        echo -e "${YELLOW}⚠️  $desc - 未找到兼容性导入，继续检查...${NC}"

        # 检查是否还有 str | None 或 dict | None
        if grep -qE "(str|int|dict|list) \| None" "$file"; then
            echo -e "${RED}❌ $desc - 仍包含 Python 3.10+ 语法${NC}"
            grep -nE "(str|int|dict|list) \| None" "$file" | head -3
            return 1
        else
            echo -e "${GREEN}✅ $desc - 未发现不兼容语法${NC}"
            return 0
        fi
    fi
}

echo ""
echo "[步骤 1/3] 验证源代码修复..."
echo "--------------------------------------------------------"

ERRORS=0

verify_fix "core/ai_chat.py" "core/ai_chat.py" || ERRORS=$((ERRORS+1))
verify_fix "ui/main_window.py" "ui/main_window.py" || ERRORS=$((ERRORS+1))
verify_fix "ui/model_config_window.py" "ui/model_config_window.py" || ERRORS=$((ERRORS+1))
verify_fix "ui/ai_chat_window.py" "ui/ai_chat_window.py" || ERRORS=$((ERRORS+1))

if [ $ERRORS -gt 0 ]; then
    echo ""
    echo -e "${RED}========================================================${NC}"
    echo -e "${RED}❌ 验证失败！发现 $ERRORS 个文件仍有问题${NC}"
    echo ""
    echo "请从 Windows 复制以下修复后的文件到 ARM 机器："
    echo "  - core/ai_chat.py"
    echo "  - ui/main_window.py"
    echo "  - ui/model_config_window.py"
    echo "  - ui/ai_chat_window.py"
    echo ""
    echo "可以使用 scp 或 rsync 命令复制，然后重新运行此脚本。"
    echo -e "${RED}========================================================${NC}"
    exit 1
fi

echo ""
echo -e "${GREEN}✅ 所有文件验证通过！${NC}"

# 清理旧构建
echo ""
echo "[步骤 2/3] 清理旧的构建文件..."
rm -rf build dist .venv_arm_build
echo -e "${GREEN}✅ 清理完成${NC}"

# 执行打包
echo ""
echo "[步骤 3/3] 开始打包（这可能需要 5-15 分钟）..."
echo "--------------------------------------------------------"

chmod +x build_arm_kylin.sh
./build_arm_kylin.sh

# 查找输出
LATEST_TAR=$(ls -t release/kylin_arm/*/AIDBTools_v*_kylin_arm_aarch64.tar.gz 2>/dev/null | head -1)

if [ -n "$LATEST_TAR" ]; then
    TAR_SIZE=$(du -sh "$LATEST_TAR" | cut -f1)
    echo ""
    echo -e "${GREEN}========================================================${NC}"
    echo -e "${GREEN}✅ 打包成功！${NC}"
    echo ""
    echo "  文件: $(basename $LATEST_TAR)"
    echo "  大小: $TAR_SIZE"
    echo "  位置: $LATEST_TAR"
    echo ""
    echo "  下一步操作："
    echo "  1. 解压: cd $(dirname $LATEST_TAR) && tar xzf $(basename $LATEST_TAR)"
    echo "  2. 测试: cd AIDBTools_*_kylin_arm_aarch64 && ./run.sh"
    echo -e "${GREEN}========================================================${NC}"
else
    echo ""
    echo -e "${RED}========================================================${NC}"
    echo -e "${RED}❌ 打包失败！未找到输出文件${NC}"
    echo "请查看上方的错误信息。"
    echo -e "${RED}========================================================${NC}"
    exit 1
fi
