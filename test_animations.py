"""
测试动画效果
"""
import sys
from PySide6.QtWidgets import QApplication, QVBoxLayout, QWidget, QPushButton, QLabel
from PySide6.QtCore import QTimer
from ui.ai_chat_window import _BubbleWidget


def main():
    app = QApplication(sys.argv)
    
    # 创建测试窗口
    window = QWidget()
    window.setWindowTitle("动画效果测试")
    window.resize(600, 500)
    
    layout = QVBoxLayout(window)
    
    # 标题
    title = QLabel("气泡淡入动画测试")
    title.setStyleSheet("font-size: 16px; font-weight: bold; padding: 10px;")
    layout.addWidget(title)
    
    # 容器
    container = QWidget()
    container_layout = QVBoxLayout(container)
    container_layout.setSpacing(8)
    
    # 添加按钮
    btn_add_user = QPushButton("添加用户消息（带动画）")
    btn_add_ai = QPushButton("添加AI消息（带动画）")
    btn_add_code = QPushButton("添加代码块消息（带动画）")
    
    message_count = [0]
    
    def add_user_message():
        message_count[0] += 1
        text = f"这是第 {message_count[0]} 条用户消息，测试淡入动画效果。"
        bubble = _BubbleWidget("user", text, "10:30", "")
        container_layout.addWidget(bubble)
        
        # 触发动画（模拟 _add_bubble 中的逻辑）
        from PySide6.QtGraphicsEffects import QGraphicsOpacityEffect
        from PySide6.QtCore import QPropertyAnimation, QEasingCurve
        
        opacity_effect = QGraphicsOpacityEffect(bubble)
        opacity_effect.setOpacity(0.0)
        bubble.setGraphicsEffect(opacity_effect)
        
        animation = QPropertyAnimation(opacity_effect, b"opacity")
        animation.setDuration(200)
        animation.setStartValue(0.0)
        animation.setEndValue(1.0)
        animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        animation.start()
        
        # 滚动到底部
        QTimer.singleShot(50, lambda: container_layout.parentWidget().parentWidget().verticalScrollBar().setValue(
            container_layout.parentWidget().parentWidget().verticalScrollBar().maximum()
        ) if hasattr(container_layout.parentWidget(), 'parentWidget') else None)
    
    def add_ai_message():
        message_count[0] += 1
        text = f"这是第 {message_count[0]} 条AI回复，展示了平滑的淡入动画效果。动画让界面更加生动和专业！"
        bubble = _BubbleWidget("assistant", text, "10:31", "")
        container_layout.addWidget(bubble)
        
        # 触发动画
        from PySide6.QtGraphicsEffects import QGraphicsOpacityEffect
        from PySide6.QtCore import QPropertyAnimation, QEasingCurve
        
        opacity_effect = QGraphicsOpacityEffect(bubble)
        opacity_effect.setOpacity(0.0)
        bubble.setGraphicsEffect(opacity_effect)
        
        animation = QPropertyAnimation(opacity_effect, b"opacity")
        animation.setDuration(200)
        animation.setStartValue(0.0)
        animation.setEndValue(1.0)
        animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        animation.start()
    
    def add_code_message():
        message_count[0] += 1
        text = f"""这是一个SQL示例：

```sql
SELECT u.name, COUNT(o.id) as order_count
FROM users u
LEFT JOIN orders o ON u.id = o.user_id
GROUP BY u.id
ORDER BY order_count DESC;
```

代码块也带有淡入动画！"""
        bubble = _BubbleWidget("assistant", text, "10:32", "")
        container_layout.addWidget(bubble)
        
        # 触发动画
        from PySide6.QtGraphicsEffects import QGraphicsOpacityEffect
        from PySide6.QtCore import QPropertyAnimation, QEasingCurve
        
        opacity_effect = QGraphicsOpacityEffect(bubble)
        opacity_effect.setOpacity(0.0)
        bubble.setGraphicsEffect(opacity_effect)
        
        animation = QPropertyAnimation(opacity_effect, b"opacity")
        animation.setDuration(200)
        animation.setStartValue(0.0)
        animation.setEndValue(1.0)
        animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        animation.start()
    
    btn_add_user.clicked.connect(add_user_message)
    btn_add_ai.clicked.connect(add_ai_message)
    btn_add_code.clicked.connect(add_code_message)
    
    layout.addWidget(btn_add_user)
    layout.addWidget(btn_add_ai)
    layout.addWidget(btn_add_code)
    
    # 添加滚动区域
    from PySide6.QtWidgets import QScrollArea
    scroll = QScrollArea()
    scroll.setWidgetResizable(True)
    scroll.setWidget(container)
    layout.addWidget(scroll)
    
    # 自动添加几条消息演示
    QTimer.singleShot(500, add_user_message)
    QTimer.singleShot(1000, add_ai_message)
    QTimer.singleShot(1500, add_code_message)
    QTimer.singleShot(2000, add_user_message)
    QTimer.singleShot(2500, add_ai_message)
    
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()