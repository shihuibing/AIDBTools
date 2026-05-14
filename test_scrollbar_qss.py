"""测试滚动条样式是否正确生成"""
import sys
sys.path.insert(0, r"D:\Users\bing\Desktop\AIDBTools")

from ui.theme_manager import _build_qss, get_theme_tokens

tokens = get_theme_tokens("dark")
qss = _build_qss(tokens)

# 检查滚动条样式是否存在于 QSS 中
print("=== Check QSS Scrollbar Styles ===")
print()

# 检查关键部分
checks = [
    ("QScrollBar:vertical", "width: 5px"),
    ("QScrollBar:horizontal", "height: 5px"),
    ("border-radius: 5px", "min-height: 30px"),
    ("scroll_handle", "scroll_handle_hover"),
]

for check in checks:
    if all(x in qss for x in check):
        print(f"[OK] Contains: {check}")
    else:
        print(f"[FAIL] Missing: {check}")

print()
print("=== Scrollbar Style Section ===")
# 找到滚动条样式部分
start = qss.find('QScrollBar:vertical')
if start != -1:
    end = qss.find('QSplitter::handle', start)
    if end != -1:
        print(qss[start:end])
