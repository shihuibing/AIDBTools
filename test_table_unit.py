#!/usr/bin/env python3
"""
表格排序功能单元测试（不需要 GUI）
"""
import sys
sys.path.insert(0, 'D:\\Users\\bing\\Desktop\\AIDBTools')


def test_number_conversion():
    """测试数值转换"""
    from ui.table_extension import SelectableTableWidget
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])

    table = SelectableTableWidget()

    print("测试 _try_convert_to_number:")
    print(f"  '123' -> {table._try_convert_to_number('123')}")
    print(f"  '45.67' -> {table._try_convert_to_number('45.67')}")
    print(f"  'NULL' -> {table._try_convert_to_number('NULL')}")
    print(f"  'abc' -> {table._try_convert_to_number('abc')}")

    assert table._try_convert_to_number('123') == 123.0
    assert table._try_convert_to_number('45.67') == 45.67
    assert table._try_convert_to_number('NULL') is None
    assert table._try_convert_to_number('abc') is None
    print("[OK] 数值转换测试完成")


def test_sort_header():
    """测试排序表头的状态切换"""
    from ui.table_extension import SortableTableHeader
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])

    header = SortableTableHeader(Qt.Orientation.Horizontal)

    print("\n测试排序状态切换:")

    header._on_header_clicked(1)
    col, order = header.get_sort_state()
    print(f"  第1列第1次点击: 列={col}, 排序={order}")
    assert col == 1 and order == 0, "第1列第1次点击应该是升序"

    header._on_header_clicked(1)
    col, order = header.get_sort_state()
    print(f"  第1列第2次点击: 列={col}, 排序={order}")
    assert col == 1 and order == 1, "第1列第2次点击应该是降序"

    header._on_header_clicked(1)
    col, order = header.get_sort_state()
    print(f"  第1列第3次点击: 列={col}, 排序={order}")
    assert col == 1 and order == -1, "第1列第3次点击应该是原序"

    header._on_header_clicked(2)
    col, order = header.get_sort_state()
    print(f"  第2列第1次点击: 列={col}, 排序={order}")
    assert col == 2 and order == 0, "第2列第1次点击应该是升序"

    header._on_header_clicked(0)
    col, order = header.get_sort_state()
    print(f"  第0列点击(应被忽略): 列={col}, 排序={order}")
    assert col == 2 and order == 0, "第0列点击应该被忽略"

    print("[OK] 排序状态切换测试完成")


def test_actual_sort_behavior():
    """测试字符串排序、数值排序和恢复原序"""
    from ui.table_extension import SelectableTableWidget, ORIGINAL_ORDER_ROLE
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QApplication, QTableWidgetItem

    app = QApplication.instance() or QApplication([])

    table = SelectableTableWidget()
    table.setColumnCount(3)
    table.setRowCount(3)

    headers = ["", "姓名", "年龄"]
    for col, header in enumerate(headers):
        table.setHorizontalHeaderItem(col, QTableWidgetItem(header))

    rows = [
        ("Charlie", "30"),
        ("Alice", "25"),
        ("Bob", "28"),
    ]

    for row_idx, (name, age) in enumerate(rows):
        chk_item = QTableWidgetItem()
        chk_item.setFlags(Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled)
        chk_item.setCheckState(Qt.CheckState.Unchecked)
        chk_item.setData(ORIGINAL_ORDER_ROLE, row_idx)
        table.setItem(row_idx, 0, chk_item)

        name_item = QTableWidgetItem(name)
        name_item.setData(Qt.ItemDataRole.UserRole, name)
        table.setItem(row_idx, 1, name_item)

        age_item = QTableWidgetItem(age)
        age_item.setData(Qt.ItemDataRole.UserRole, age)
        table.setItem(row_idx, 2, age_item)

    table._apply_sort(1, 0)
    name_order = [table.item(row, 1).text() for row in range(table.rowCount())]
    assert name_order == ["Alice", "Bob", "Charlie"], f"字符串升序失败: {name_order}"

    table._apply_sort(2, 1)
    age_order = [table.item(row, 2).text() for row in range(table.rowCount())]
    assert age_order == ["30", "28", "25"], f"数值降序失败: {age_order}"

    table._apply_sort(2, -1)
    restored_order = [table.item(row, 1).text() for row in range(table.rowCount())]
    assert restored_order == ["Charlie", "Alice", "Bob"], f"恢复原序失败: {restored_order}"

    print("[OK] 实际排序行为测试完成")


if __name__ == "__main__":
    print("=" * 50)
    print("表格排序功能单元测试")
    print("=" * 50)
    test_number_conversion()
    test_sort_header()
    test_actual_sort_behavior()
    print("\n" + "=" * 50)
    print("[OK] 所有测试通过！")
    print("=" * 50)