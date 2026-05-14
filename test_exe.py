import subprocess
import time
import sys
import os

exe_path = os.path.join(os.path.dirname(__file__), 'dist', 'AIDBTools.exe')
print(f"Testing {exe_path}")
if not os.path.exists(exe_path):
    print("EXE not found")
    sys.exit(1)

# 尝试运行 exe 并捕获 stderr
try:
    proc = subprocess.Popen(
        [exe_path],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding='utf-8',
        errors='ignore'
    )
    # 等待 5 秒
    time.sleep(5)
    # 终止进程
    proc.terminate()
    try:
        proc.wait(timeout=2)
    except subprocess.TimeoutExpired:
        proc.kill()
    # 读取 stderr
    stderr_output = proc.stderr.read()
    if stderr_output:
        print("Stderr captured:")
        print(stderr_output[:2000])
    else:
        print("No stderr output (good)")
except Exception as e:
    print(f"Error testing exe: {e}")
finally:
    # 确保进程终止
    if proc.poll() is None:
        proc.kill()