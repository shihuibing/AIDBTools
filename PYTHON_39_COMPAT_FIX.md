# Python 3.9 兼容性修复说明

## 问题描述

在银河麒麟 ARM 系统（Python 3.9.9）上运行打包后的程序时出现错误：

```
TypeError: unsupported operand type(s) for |: 'type' and 'NoneType'
```

## 原因分析

代码中使用了 Python 3.10+ 的联合类型注解语法：
```python
def func(param: str | None = None):  # Python 3.10+ 语法
    pass
```

这种语法在 Python 3.9 中不支持，需要使用 `Optional` 或 `Union`：
```python
from typing import Optional

def func(param: Optional[str] = None):  # Python 3.9 兼容
    pass
```

## 已修复的文件

### 1. core/ai_chat.py
- ✅ 添加 `from __future__ import annotations`
- ✅ 添加 `from typing import Optional`
- ✅ 修复 `get_history(history_key: str | None)` → `Optional[str]`
- ✅ 修复 `clear_history(history_key: str | None)` → `Optional[str]`

### 2. ui/model_config_window.py
- ✅ 添加 `from __future__ import annotations`
- ✅ 添加 `from typing import Optional`
- ✅ 修复 `_make_btn(tokens: dict | None)` → `Optional[dict]`
- ✅ 修复 `_eye_button(tokens: dict | None)` → `Optional[dict]`
- ✅ 修复 `_key_field(tokens: dict | None)` → `Optional[dict]`
- ✅ 修复 `_nav_row_map: list[int | None]` → `list[Optional[int]]`

### 3. ui/main_window.py
- ✅ 添加 `from __future__ import annotations`
- ✅ 添加 `from typing import Optional`
- ✅ 修复 `_sync_ai_chat_context(context: dict | None)` → `Optional[dict]`
- ✅ 修复 `_get_current_schema(history_key: str | None)` → `Optional[str]`
- ✅ 修复 `_get_current_db_info(history_key: str | None)` → `Optional[str]`

### 4. ui/ai_chat_window.py
- ✅ 添加 `from __future__ import annotations`
- ✅ 添加 `from typing import Optional`
- ✅ 修复 `refresh_theme(_theme: str | None)` → `Optional[str]`

### 5. core/skill_manager.py
- ✅ 已有 `from __future__ import annotations`，无需修改

## 重新打包步骤

在 ARM 银河麒麟机器上执行：

```bash
cd /home/AIDBTools1.0.27/AIDBTools

# 确保获取最新代码
# （如果是从 Windows 拷贝，请重新拷贝所有修改过的文件）

# 重新运行打包
chmod +x build_arm_kylin.sh
./build_arm_kylin.sh
```

## 验证方法

打包完成后，在目标机器上测试：

```bash
cd AIDBTools_v1.0.xx_kylin_arm_aarch64
./run.sh
```

如果程序成功启动，说明兼容性修复成功。

## 开发建议

为确保与 Python 3.9 兼容，请遵循以下规范：

### ❌ 避免使用（Python 3.10+）
```python
def func(x: str | None):           # 联合类型运算符
def func(x: int | str):            # 联合类型运算符
items: list[int | str]             # 列表中的联合类型
data: dict[str, int | None]        # 字典值中的联合类型
```

### ✅ 推荐使用（Python 3.9 兼容）
```python
from typing import Optional, Union

def func(x: Optional[str]):        # 可选类型
def func(x: Union[int, str]):      # 联合类型
items: list[Union[int, str]]       # 列表中的联合类型
data: dict[str, Optional[int]]     # 字典值中的可选类型
```

或者在文件开头添加：
```python
from __future__ import annotations
```

这样可以使用新语法，但会在运行时自动转换为兼容格式。

## 相关文件

- [PYTHON_39_COMPAT_FIX.md](PYTHON_39_COMPAT_FIX.md) - 本文档
- [PYQT5_USAGE.md](PYQT5_USAGE.md) - PyQt5 使用指南
- [TROUBLESHOOTING_ARM_BUILD.md](TROUBLESHOOTING_ARM_BUILD.md) - 故障排查指南
