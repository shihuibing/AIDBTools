# ARM 银河麒麟打包故障排查指南

## 常见问题及解决方案

### 问题 1: JPype1 编译失败 - 缺少 Apache Ant

**错误信息:**
```
CMake Error at CMakeLists.txt:36 (find_program):
  Could not find ANT_EXECUTABLE using the following names: ant
```

**原因:** JPype1 需要 Apache Ant 来构建 Java 组件。

**解决方案:**

方法 1: 自动安装（脚本已更新）
```bash
# 脚本会自动检测并安装 Apache Ant
sudo dnf install apache-ant
```

方法 2: 手动安装
```bash
# openEuler/银河麒麟
sudo dnf install apache-ant

# Ubuntu/Deepin
sudo apt-get install ant
```

方法 3: 跳过 JDBC 支持（如果不需要星环数据库）
```bash
# 编辑 build_arm_kylin.sh，注释掉 JPype1 安装部分
# 或者手动安装时跳过 jaydebeapi
```

---

### 问题 2: PyQt5 验证失败 - ModuleNotFoundError

**错误信息:**
```
Traceback (most recent call last):
  File "<string>", line 1, in <module>
ModuleNotFoundError: No module named 'PyQt5'
```

**原因:** 系统 PyQt5 未正确链接到虚拟环境。

**解决方案:**

方法 1: 重新运行脚本（已修复）
```bash
# 脚本已更新，会自动处理链接问题
./build_arm_kylin.sh
```

方法 2: 手动链接
```bash
cd /home/AIDBTools1.0.27/AIDBTools
source .venv_arm_build/bin/activate

# 获取路径
SYS_PYQT5=$(python3 -c "import PyQt5, os; print(os.path.dirname(PyQt5.__file__))")
SITE_PACKAGES=$(python3 -c "import site; print(site.getsitepackages()[0])")

# 创建符号链接
ln -sf $SYS_PYQT5 $SITE_PACKAGES/PyQt5
ln -sf $(python3 -c "import sip, os; print(os.path.dirname(sip.__file__))") $SITE_PACKAGES/sip

# 验证
python3 -c "import PyQt5; print('OK')"
```

方法 3: 检查系统 PyQt5 是否安装
```bash
# 检查系统 PyQt5
python3 -c "import PyQt5; print(PyQt5.QtCore.PYQT_VERSION_STR)"

# 如果未安装
sudo dnf install python3-PyQt5 qt5-qtbase-devel
```

---

### 问题 3: 虚拟环境创建失败

**错误信息:**
```
Error: venv creation failed
```

**解决方案:**
```bash
# 清理旧的虚拟环境
rm -rf .venv_arm_build

# 重新创建
python3.9 -m venv .venv_arm_build
source .venv_arm_build/bin/activate
pip install --upgrade pip setuptools wheel
```

---

### 问题 4: PyInstaller 打包失败

**错误信息:**
```
PyInstaller failed with exit code 1
```

**解决方案:**

方法 1: 查看详细错误日志
```bash
# 查看 PyInstaller 日志
cat build/AIDBTools/warn-AIDBTools.txt
cat build/AIDBTools/xref-AIDBTools.html
```

方法 2: 清理缓存重新打包
```bash
rm -rf build dist
pyinstaller --clean AIDBTools_arm_kylin.spec
```

方法 3: 检查依赖完整性
```bash
source .venv_arm_build/bin/activate
python3 -c "
import PyQt5
import sqlalchemy
import pymysql
import psycopg2
print('All dependencies OK')
"
```

---

### 问题 5: 打包后程序启动失败

**错误信息:**
```
Segmentation fault (core dumped)
```

**原因:** ARM 架构上 strip 或 UPX 可能导致动态库损坏。

**解决方案:**
```bash
# 已在 spec 文件中禁用 strip 和 UPX
# 如果仍然出现问题，检查：

# 1. 检查缺失的动态库
ldd dist/AIDBTools | grep "not found"

# 2. 检查 Qt 平台插件
export QT_DEBUG_PLUGINS=1
./dist/AIDBTools/run.sh
```

---

### 问题 6: 数据库驱动缺失

**错误信息:**
```
ImportError: No module named 'pymssql'
```

**解决方案:**
```bash
source .venv_arm_build/bin/activate

# 安装缺失的驱动
pip install pymssql    # SQL Server
pip install pyodbc     # ODBC 支持
pip install oracledb   # Oracle
```

---

## 完整的手动打包流程

如果自动脚本失败，可以按以下步骤手动打包：

### 步骤 1: 安装系统依赖
```bash
sudo dnf install -y \
    python3 python3-pip python3-devel \
    mesa-libGL glib2 \
    postgresql-devel freetds-devel unixODBC-devel \
    java-11-openjdk-devel apache-ant \
    gcc gcc-c++ make \
    qt5-qtbase-devel qt5-qttools-devel \
    python3-PyQt5
```

### 步骤 2: 创建虚拟环境
```bash
cd /home/AIDBTools1.0.27/AIDBTools
python3.9 -m venv .venv_arm_build
source .venv_arm_build/bin/activate
pip install --upgrade pip setuptools wheel
```

### 步骤 3: 链接系统 PyQt5
```bash
SITE_PACKAGES=$(python3 -c "import site; print(site.getsitepackages()[0])")
SYS_PYQT5=$(python3 -c "import PyQt5, os; print(os.path.dirname(PyQt5.__file__))")
ln -sf $SYS_PYQT5 $SITE_PACKAGES/PyQt5

# 验证
python3 -c "import PyQt5; print('PyQt5:', PyQt5.QtCore.PYQT_VERSION_STR)"
```

### 步骤 4: 安装 Python 依赖
```bash
pip install \
    sqlalchemy>=2.0 \
    pymysql>=1.1 \
    psycopg2-binary>=2.9 \
    oracledb>=2.0 \
    pandas>=2.0 \
    requests>=2.31 \
    openpyxl>=3.1 \
    pyinstaller>=6.0

# 可选：JDBC 支持
pip install JPype1>=1.4 jaydebeapi>=1.2

# 可选：SQL Server
pip install pymssql>=2.2
```

### 步骤 5: 设置平台标识
```bash
python3 -c "
import sys
sys.path.insert(0, '.')
from version import set_build_platform
set_build_platform('kylin_arm')
print('BUILD_PLATFORM = kylin_arm')
"
```

### 步骤 6: 执行打包
```bash
pyinstaller --clean AIDBTools_arm_kylin.spec
```

### 步骤 7: 验证输出
```bash
ls -lh dist/AIDBTools
./dist/AIDBTools --help  # 如果有命令行参数
```

---

## 诊断脚本

创建 `diagnose.sh` 进行系统检查：

```bash
#!/bin/bash
echo "=== 系统信息 ==="
uname -a
arch

echo ""
echo "=== Python 版本 ==="
python3 --version
which python3

echo ""
echo "=== PyQt5 状态 ==="
python3 -c "import PyQt5; print('PyQt5:', PyQt5.QtCore.PYQT_VERSION_STR)" 2>&1 || echo "PyQt5 未安装"

echo ""
echo "=== Java 环境 ==="
java -version 2>&1 | head -1 || echo "Java 未安装"
ant -version 2>&1 | head -1 || echo "Ant 未安装"

echo ""
echo "=== 系统依赖 ==="
rpm -qa | grep -E "qt5|PyQt5|java|ant" 2>/dev/null || \
dpkg -l | grep -E "qt5|pyqt5|java|ant" 2>/dev/null || \
echo "无法检查包管理器"

echo ""
echo "=== 磁盘空间 ==="
df -h . | tail -1
```

使用方法：
```bash
chmod +x diagnose.sh
./diagnose.sh > diagnosis.txt 2>&1
cat diagnosis.txt
```

---

## 联系支持

如果以上方法都无法解决问题，请提供以下信息：

1. **系统信息**: `uname -a`
2. **Python 版本**: `python3 --version`
3. **完整错误日志**: `build_arm_kylin.sh` 的完整输出
4. **诊断报告**: 运行上面的 `diagnose.sh`

联系方式：
- 开发者：石慧兵
- 邮箱：1795794877@qq.com
