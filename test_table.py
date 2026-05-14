#!/usr/bin/env python3
"""
测试表格排序和列选中功能
"""
import sys
sys.path.insert(0, 'D:\\Users\\bing\\Desktop\\AIDBTools')

from PySide6.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QWidget
from PySide6.QtCore import Qt
from ui.table_extension import SelectableTableWidget

def test_table():
    app = QApplication(sys.argv)
    
    # 创建主窗口
    main_win = QMainWindow()
    main_win.setWindowTitle("表格排序和列选中测试")
    main_win.setGeometry(100, 100, 800, 600)
    
    # 创建表格
    table = SelectableTableWidget()
    table.setColumnCount(4)
    table.setRowCount(5)
    
    # 设置表头
    headers = ["姓名", "年龄", "城市", "职位"]
    for col, header in enumerate(headers):
        from PySide6.QtWidgets import QTableWidgetItem
        table.setHorizontalHeaderItem(col, QTableWidgetItem(header))
    
    # 填充测试数据
    test_data = [
        ["Alice", "25", "北京", "工程师"],
        ["Bob", "30", "上海", "设计师"],
        ["Charlie", "28", "深圳", "产品经理"],
        ["David", "32", "杭州", "测试"],
        ["Eve", "26", "成都", "运维"],
    ]
    
    for row, data in enumerate(test_data):
        for col, value in enumerate(data):
            from PySide6.QtWidgets import QTableWidgetItem
            item = QTableWidgetItem(value)
            table.setItem(row, col, item)
    
    # 连接信号
    table.selectedColumnsChanged.connect(lambda cols: print(f"[OK] 选中列: {cols}"))
    
    # 设置主窗口
    widget = QWidget()
    layout = QVBoxLayout(widget)
    layout.addWidget(table)
    main_win.setCentralWidget(widget)
    
    main_win.show()
    print("[OK] 测试窗口已打开")
    print("提示：")

    print("  - 点击表头排序（点击多次切换升序/降序/原序）")
    print("  - Ctrl+点击表头选中多列")
    print("  - Shift+点击表头范围选择")
    
    sys.exit(app.exec())

if __name__ == "__main__":
    test_table()