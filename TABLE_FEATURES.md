# 表格排序和列选中功能说明

## 功能概述

本版本在数据表格中新增了两个主要功能：
1. **表头排序** - 点击表头按列排序
2. **列选中** - 点击表头选中整列，支持多选和范围选择

---

## 功能详解

### 1️⃣ 表头排序功能

#### 使用方法
- **第1次点击表头** → 升序排列
- **第2次点击同一表头** → 降序排列
- **第3次点击同一表头** → 恢复原始顺序
- **点击其他表头** → 按新列升序排列（同时取消前一列的排序）

#### 排序规则
- **数值列**：优先按数值排序，NULL 值排在最前面
- **文本列**：按字母顺序排序（不区分大小写），NULL 值排在最前面
- **特殊处理**：如果列中混有数值和文本，系统会自动智能识别

#### 注意事项
- 第 0 列（复选框列）**不支持排序**，点击无效
- 排序后的表格仍然保持复选框的正确对应关系
- 翻页后排序状态会自动重置

### 2️⃣ 列选中功能

#### 使用方法

**单列选中**
```
直接点击表头 → 选中整列（蓝色高亮背景）
```

**多列选中**
```
Ctrl + 点击表头 → 添加/删除列到选中集合
```

**范围选中**
```
Shift + 点击表头 → 选中从上次选中列到当前列的范围
```

#### 视觉反馈
- 被选中的列会以**浅蓝色**（RGB: 200, 220, 240）高亮显示
- 整列的所有行都会被高亮，包括复选框列

#### 示例

假设表格有 5 列：`姓名`、`年龄`、`城市`、`职位`、`工资`

| 操作 | 结果 |
|------|------|
| 点击「姓名」表头 | 选中「姓名」列 |
| 再 Ctrl+点击「城市」表头 | 同时选中「姓名」和「城市」列 |
| 再 Ctrl+点击「姓名」表头 | 取消选中「姓名」列，只保留「城市」 |
| 点击「职位」表头 | 清空之前的选中，仅选中「职位」列 |
| 点击「姓名」表头 | 选中「姓名」列 |
| Shift+点击「城市」表头 | 选中「姓名」、「年龄」、「城市」三列（范围） |

#### 日志输出
选中列变化时，日志区会显示：
```
📌 选中列：姓名, 城市
```

### 3️⃣ 排序与列选中的组合

排序和列选中是**完全独立**的功能，可以自由组合：

```
场景 1: 先排序后选中
- 点击「年龄」表头 (升序)
- 再点击「年龄」表头 (降序)
- Ctrl+点击「工资」表头 (同时选中年龄和工资列)

场景 2: 先选中后排序
- Ctrl+点击「姓名」
- Ctrl+点击「城市」(同时选中)
- 点击「年龄」表头 (排序，同时清空之前的列选中)
```

---

## 技术实现

### 核心文件
- **`ui/table_extension.py`** - 扩展模块，包含两个类：
  - `SortableTableHeader` - 可排序的表头
  - `SelectableTableWidget` - 支持排序和列选中的表格

### 类设计

#### SortableTableHeader(QHeaderView)
```python
# 信号
sortChanged = pyqtSignal(int, int)  # (col_idx, sort_order)
                                     # sort_order: 0=升序, 1=降序, -1=原序

# 关键方法
_on_header_clicked(col_idx)  # 处理表头点击
get_sort_state()              # 获取当前排序状态
reset_sort()                  # 重置排序状态
```

#### SelectableTableWidget(QTableWidget)
```python
# 信号
selectedColumnsChanged = pyqtSignal(list)  # 列索引列表

# 关键方法
_on_header_section_clicked(col_idx)    # 处理列选中
_update_column_highlight()              # 更新高亮显示
clear_column_selection()                # 清空列选中
get_selected_columns()                  # 获取选中列
```

### 排序算法
1. 收集表格所有数据（行 × 列的 item 对象）
2. 尝试按数值排序，如果失败则按字符串排序
3. 使用 `blockSignals()` 防止信号干扰
4. 直接调用 `setItem()` 重新设置整个表格

### 高亮显示
使用 PyQt6 的 `QTableWidgetItem.setBackground(QColor)` 方法：
```python
# 清除高亮
item.setBackground(QColor(255, 255, 255, 0))

# 应用高亮
item.setBackground(QColor(200, 220, 240))
```

---

## 限制和注意事项

### ⚠️ 已知限制
1. **排序后无法恢复到"第三次点击"后的顺序** - 第3次点击会显示原序，但如果有新数据后排序状态会丢失
2. **大数据量性能** - 排序 10+ 万行数据时会有延迟，建议使用分页
3. **复选框列** - 第 0 列专为复选框保留，无法排序或高亮

### ✅ 优化建议
1. 对于超大数据集，考虑在 SQL 层面排序（ORDER BY）而不是 UI 层
2. 可添加排序指示符（▲▼）到表头，提示当前排序列
3. 可添加"清空选中"快捷按钮

---

## 集成步骤（已完成）

### 1. 创建扩展模块
```bash
ui/table_extension.py  # 新文件
```

### 2. 修改 main_window.py
```python
# 导入
from ui.table_extension import SelectableTableWidget

# 替换表格类
# self.table = QTableWidget()  # 旧代码
self.table = SelectableTableWidget()  # 新代码

# 连接列选中信号
self.table.selectedColumnsChanged.connect(self._on_selected_columns_changed)

# 添加列选中处理函数
def _on_selected_columns_changed(self, selected_cols):
    if selected_cols:
        col_names = []
        for col_idx in selected_cols:
            header_item = self.table.horizontalHeaderItem(col_idx)
            if header_item:
                col_names.append(header_item.text())
        if col_names:
            self.log(f"📌 选中列：{', '.join(col_names)}")

# 在 _render_table 中重置排序和列选中
self.table._sortable_header.reset_sort()
self.table.clear_column_selection()
```

### 3. 验证
```bash
python -m py_compile ui/table_extension.py  # 语法检查
```

---

## 测试

### 快速测试（GUI）
```bash
python test_table.py
```

### 单元测试（无 GUI）
```bash
python test_table_unit.py
```

---

## 常见问题

**Q: 为什么排序后复选框状态没有改变？**
A: 复选框的 checked 状态存储在每个 item 对象中，排序是直接调用 `setItem()` 重新设置 item，state 会保持不变。

**Q: 排序时出现数据混乱怎么办？**
A: 这通常是因为表格中存在未设置的 item (None)。确保每个单元格都有对应的 QTableWidgetItem。

**Q: 能否按多列排序？**
A: 当前版本不支持多列排序。如需此功能，可在 SQL 层面使用 ORDER BY col1, col2 实现。

**Q: 高亮颜色能否自定义？**
A: 可以。编辑 `table_extension.py` 第 183 行的 `highlight_color = QColor(200, 220, 240)` 即可。

---

## 后续改进方向

- [ ] 添加排序指示符（▲▼ 标记）
- [ ] 支持多列排序
- [ ] 添加"全选列"快捷按钮
- [ ] 排序性能优化（考虑 SQL 级排序）
- [ ] 自定义高亮颜色配置
- [ ] 排序记忆（保存排序状态）
- [ ] 导出选中列数据功能

---

**最后更新**: 2026-03-31 16:46
**开发者**: 小Q
