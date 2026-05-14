"""
测试加载状态指示器
"""
import sys
from PySide6.QtWidgets import QApplication, QVBoxLayout, QWidget, QPushButton
from ui.ai_chat_window import _LoadingBubble


def main():
    app = QApplication(sys.argv)
    
    # 创建测试窗口
    window = QWidget()
    window.setWindowTitle("加载指示器测试")
    window.resize(400, 300)
    
    layout = QVBoxLayout(window)
    
    # 创建加载指示器
    loading_bubble = _LoadingBubble("AI 正在思考中")
    layout.addWidget(loading_bubble)
    
    # 添加控制按钮
    btn_stop = QPushButton("停止动画")
    btn_stop.clicked.connect(loading_bubble.stop_animation)
    layout.addWidget(btn_stop)
    
    def create_new():
        # 移除旧的
        layout.removeWidget(loading_bubble)
        loading_bubble.deleteLater()
        # 创建新的
        new_bubble = _LoadingBubble("处理中")
        layout.insertWidget(0, new_bubble)
    
    btn_new = QPushButton("新建加载指示器")
    btn_new.clicked.connect(create_new)
    layout.addWidget(btn_new)
    
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()