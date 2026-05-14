"""
测试代码块增强功能
"""
import sys
from PySide6.QtWidgets import QApplication, QVBoxLayout, QWidget, QScrollArea
from ui.ai_chat_window import _BubbleWidget


def main():
    app = QApplication(sys.argv)
    
    # 创建测试窗口
    window = QWidget()
    window.setWindowTitle("代码块增强功能测试")
    window.resize(800, 600)
    
    layout = QVBoxLayout(window)
    
    # 创建滚动区域
    scroll = QScrollArea()
    scroll.setWidgetResizable(True)
    container = QWidget()
    container_layout = QVBoxLayout(container)
    
    # 测试1: SQL代码块
    sql_text = """这是一个SQL查询示例：

```sql
SELECT u.name, u.email, COUNT(o.id) as order_count
FROM users u
LEFT JOIN orders o ON u.id = o.user_id
WHERE u.created_at > '2024-01-01'
GROUP BY u.id, u.name, u.email
HAVING COUNT(o.id) > 5
ORDER BY order_count DESC;
```

希望这对你有帮助！"""
    
    bubble1 = _BubbleWidget("assistant", sql_text, "10:30", "")
    container_layout.addWidget(bubble1)
    
    # 测试2: Python代码块
    python_text = """这是一个Python函数：

```python
def calculate_sum(numbers: list) -> int:
    '''计算列表中所有数字的总和'''
    total = 0
    for num in numbers:
        if isinstance(num, (int, float)):
            total += num
    return total

# 使用示例
result = calculate_sum([1, 2, 3, 4, 5])
print(f"结果: {result}")
```

这个函数可以处理整数和浮点数。"""
    
    bubble2 = _BubbleWidget("assistant", python_text, "10:31", "")
    container_layout.addWidget(bubble2)
    
    # 测试3: 用户消息中的代码
    user_text = """帮我优化这个查询：

```sql
SELECT * FROM users WHERE id IN (SELECT user_id FROM orders WHERE amount > 100)
```

感觉性能不太好。"""
    
    bubble3 = _BubbleWidget("user", user_text, "10:32", "")
    container_layout.addWidget(bubble3)
    
    # 测试4: 多个代码块
    multi_text = """首先创建表：

```sql
CREATE TABLE test_table (
    id INT PRIMARY KEY,
    name VARCHAR(100),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

然后插入数据：

```sql
INSERT INTO test_table (id, name) VALUES
(1, 'Alice'),
(2, 'Bob'),
(3, 'Charlie');
```

最后查询：

```sql
SELECT * FROM test_table ORDER BY created_at DESC;
```"""
    
    bubble4 = _BubbleWidget("assistant", multi_text, "10:33", "")
    container_layout.addWidget(bubble4)
    
    scroll.setWidget(container)
    layout.addWidget(scroll)
    
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()