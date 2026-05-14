#!/bin/bash
# ============================================================
# 在 ARM 机器上直接修复 Python 3.9 兼容性问题
# 无需从 Windows 复制文件
# ============================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "================================================"
echo "  AIDBTools - Python 3.9 兼容性自动修复"
echo "  工作目录: $SCRIPT_DIR"
echo "================================================"

# 备份原文件
echo ""
echo "[备份] 创建原文件备份..."
cp core/ai_chat.py core/ai_chat.py.bak 2>/dev/null || true
cp ui/main_window.py ui/main_window.py.bak 2>/dev/null || true
cp ui/model_config_window.py ui/model_config_window.py.bak 2>/dev/null || true
cp ui/ai_chat_window.py ui/ai_chat_window.py.bak 2>/dev/null || true
echo "✅ 备份完成（.bak 文件）"

# 修复 ai_chat.py
echo ""
echo "[修复] core/ai_chat.py..."

# 在文件开头添加 from __future__ import annotations（在第 8 行之后）
if ! grep -q "from __future__ import annotations" core/ai_chat.py; then
    sed -i '8a from __future__ import annotations\n' core/ai_chat.py
    echo "  ✅ 添加 from __future__ import annotations"
fi

# 替换 str | None 为 Optional[str]
sed -i 's/: str | None/: Optional[str]/g' core/ai_chat.py
sed -i 's/-> str | None/-> Optional[str]/g' core/ai_chat.py
echo "  ✅ 替换 str | None → Optional[str]"

# 确保导入 Optional
if ! grep -q "from typing import Optional" core/ai_chat.py; then
    sed -i '/^from __future__/a from typing import Optional' core/ai_chat.py
    echo "  ✅ 添加 from typing import Optional"
fi

# 修复 main_window.py
echo ""
echo "[修复] ui/main_window.py..."

if ! grep -q "from __future__ import annotations" ui/main_window.py; then
    sed -i '1i from __future__ import annotations\n' ui/main_window.py
    echo "  ✅ 添加 from __future__ import annotations"
fi

sed -i 's/: str | None/: Optional[str]/g' ui/main_window.py
sed -i 's/: dict | None/: Optional[dict]/g' ui/main_window.py
sed -i 's/-> str | None/-> Optional[str]/g' ui/main_window.py
sed -i 's/-> dict | None/-> Optional[dict]/g' ui/main_window.py
echo "  ✅ 替换联合类型语法"

if ! grep -q "from typing import Optional" ui/main_window.py; then
    sed -i '/^from __future__/a from typing import Optional' ui/main_window.py
    echo "  ✅ 添加 from typing import Optional"
fi

# 修复 model_config_window.py
echo ""
echo "[修复] ui/model_config_window.py..."

if ! grep -q "from __future__ import annotations" ui/model_config_window.py; then
    sed -i '5a from __future__ import annotations\n' ui/model_config_window.py
    echo "  ✅ 添加 from __future__ import annotations"
fi

sed -i 's/: dict | None/: Optional[dict]/g' ui/model_config_window.py
sed -i 's/: int | None/: Optional[int]/g' ui/model_config_window.py
echo "  ✅ 替换联合类型语法"

if ! grep -q "from typing import Optional" ui/model_config_window.py; then
    sed -i '/^from __future__/a from typing import Optional' ui/model_config_window.py
    echo "  ✅ 添加 from typing import Optional"
fi

# 修复 ai_chat_window.py
echo ""
echo "[修复] ui/ai_chat_window.py..."

if ! grep -q "from __future__ import annotations" ui/ai_chat_window.py; then
    # 找到第一个 """ 结束的位置
    sed -i '/^"""$/a from __future__ import annotations\n' ui/ai_chat_window.py | head -20
    # 更精确的方法：在第 12 行后添加
    sed -i '12a from __future__ import annotations' ui/ai_chat_window.py
    echo "  ✅ 添加 from __future__ import annotations"
fi

sed -i 's/: str | None/: Optional[str]/g' ui/ai_chat_window.py
echo "  ✅ 替换联合类型语法"

if ! grep -q "from typing import Optional" ui/ai_chat_window.py; then
    sed -i '/^from __future__/a from typing import Optional' ui/ai_chat_window.py
    echo "  ✅ 添加 from typing import Optional"
fi

# 验证修复
echo ""
echo "================================================"
echo "[验证] 检查修复结果..."
echo "================================================"

ERRORS=0

if grep -qE "(str|int|dict|list) \| None" core/ai_chat.py; then
    echo "❌ core/ai_chat.py 仍有不兼容语法"
    ERRORS=$((ERRORS+1))
else
    echo "✅ core/ai_chat.py 已修复"
fi

if grep -qE "(str|int|dict|list) \| None" ui/main_window.py; then
    echo "❌ ui/main_window.py 仍有不兼容语法"
    ERRORS=$((ERRORS+1))
else
    echo "✅ ui/main_window.py 已修复"
fi

if grep -qE "(str|int|dict|list) \| None" ui/model_config_window.py; then
    echo "❌ ui/model_config_window.py 仍有不兼容语法"
    ERRORS=$((ERRORS+1))
else
    echo "✅ ui/model_config_window.py 已修复"
fi

if grep -qE "(str|int|dict|list) \| None" ui/ai_chat_window.py; then
    echo "❌ ui/ai_chat_window.py 仍有不兼容语法"
    ERRORS=$((ERRORS+1))
else
    echo "✅ ui/ai_chat_window.py 已修复"
fi

if [ $ERRORS -gt 0 ]; then
    echo ""
    echo "⚠️  有 $ERRORS 个文件修复失败，请手动检查"
    exit 1
fi

echo ""
echo "================================================"
echo "✅ 所有文件修复完成！"
echo "================================================"
echo ""
echo "下一步操作："
echo "1. 清理旧构建: rm -rf build dist .venv_arm_build"
echo "2. 重新打包: ./build_arm_kylin.sh"
echo ""
echo "或者运行: ./rebuild_arm.sh"
echo "================================================"
