# AIDBTools 银河麒麟 V10 (x86_64) 部署指南

> 本文档专门针对 **银河麒麟 V10 SP2/SP3 x86_64** 架构系统

---

## 一、快速开始（推荐方案）

### 方案①：使用预打包的可执行文件（最简单）

如果你已经有在 Linux x86_64 环境下打包好的 `AIDBTools` 可执行文件：

#### 1. 复制文件到目标机器

通过 U 盘或网络传输以下文件到银河麒麟系统：

```
AIDBTools              ← 主程序（可执行文件）
config/                ← 配置目录（可选，首次运行会自动创建）
drivers/               ← 驱动目录（包含星环 JDBC/ODBC 驱动）
```

#### 2. 安装系统依赖

打开终端，执行：

```bash
# 更新软件源
sudo apt update

# 安装 Qt 运行时依赖
sudo apt install -y \
    libxcb-xinerama0 \
    libxcb-cursor0 \
    libxcb-icccm4 \
    libxcb-image0 \
    libxcb-keysyms1 \
    libxcb-randr0 \
    libxcb-render-util0 \
    libxcb-shape0 \
    libxkbcommon-x11-0 \
    libgl1 \
    libglib2.0-0 \
    fonts-wqy-zenhei \
    fonts-wqy-microhei

# 安装 Java（用于星环 JDBC 连接）
sudo apt install -y default-jre-headless

# 安装 ODBC 支持（可选，性能更好）
sudo apt install -y unixodbc odbcinst
```

#### 3. 安装星环 ODBC 驱动（可选，推荐）

```bash
# 进入驱动目录
cd drivers/transwarp/odbc/linux/

# 安装 ODBC 驱动（x86_64 版本）
sudo dpkg -i inceptor-connector-odbc-8.37.0.deb

# 验证驱动安装
odbcinst -q -d
```

应该能看到类似输出：
```
[Inceptor]
```

#### 4. 启动程序

```bash
# 赋予执行权限
chmod +x AIDBTools

# 运行
./AIDBTools
```

---

### 方案②：从源码部署（适合开发调试）

#### 1. 准备 Python 环境

银河麒麟 V10 通常预装 Python 3.8+，检查版本：

```bash
python3 --version
```

如果版本 < 3.9，需要升级或安装新版本。

#### 2. 克隆/复制项目

将整个 AIDBTools 项目目录复制到目标机器。

#### 3. 运行一键安装脚本

```bash
cd AIDBTools
chmod +x install_kylin.sh
./install_kylin.sh
```

脚本会自动完成：
- ✅ 检测并安装系统依赖
- ✅ 创建 Python 虚拟环境
- ✅ 安装所有 Python 包
- ✅ 配置桌面快捷方式

#### 4. 启动

```bash
# 方式1：使用桌面图标
# 双击桌面上的 "AIDBTools" 图标

# 方式2：命令行启动
cd AIDBTools
./run.sh
```

---

## 二、从 Windows 打包 Linux 版本

由于 PyInstaller 需要在**目标平台**上打包，你需要：

### 方法①：在银河麒麟系统中直接打包（推荐）

1. 将整个项目复制到银河麒麟系统
2. 按照"方案②：从源码部署"的步骤操作
3. 执行打包脚本：

```bash
chmod +x build_linux.sh
./build_linux.sh
```

打包完成后，产物位于：
```
release/linux/v{版本号}/AIDBTools_v{版本号}_linux_x86_64
```

### 方法②：使用 WSL2 / Docker 打包

如果你有 Windows 机器，可以使用 WSL2 Ubuntu 来打包：

```bash
# 在 WSL2 Ubuntu 中
cd /mnt/d/Users/bing/Desktop/AIDBTools
chmod +x build_linux.sh
./build_linux.sh
```

然后将生成的可执行文件复制到银河麒麟系统。

---

## 三、星环数据库连接配置

### 连接方式选择

| 方式 | 优点 | 缺点 | 适用场景 |
|------|------|------|----------|
| **ODBC** | 性能最佳，稳定 | 需要安装驱动 | 生产环境推荐 |
| **JDBC** | 无需额外安装，内置 JAR | 需要 Java，稍慢 | 快速测试/开发 |

### ODBC 连接配置示例

在 AIDBTools 中新建连接时：

```
连接名称: 星环测试
数据库类型: Transwarp Inceptor
连接方式: ODBC
ODBC 驱动: Inceptor          ← 与 odbcinst -q -d 输出一致
主机: 192.168.1.100
端口: 10000
数据库: default
用户名: admin
密码: ******
```

### JDBC 连接配置示例

```
连接名称: 星环测试
数据库类型: Transwarp Inceptor
连接方式: JDBC
主机: 192.168.1.100
端口: 10000
数据库: default
用户名: admin
密码: ******
```

> ⚠️ JDBC 模式需要确保 Java 已安装：`java -version`

---

## 四、常见问题排查

### Q1: 启动报错 `cannot connect to X server`

**原因**: 图形界面环境变量未设置

**解决**:
```bash
echo $DISPLAY
# 如果为空，设置
export DISPLAY=:0
./AIDBTools
```

永久生效，编辑 `~/.profile`：
```bash
echo 'export DISPLAY=:0' >> ~/.profile
source ~/.profile
```

---

### Q2: Qt 插件错误 `Could not find the Qt platform plugin "xcb"`

**原因**: 缺少 Qt XCB 依赖库

**解决**:
```bash
sudo apt install -y \
    libxcb-xinerama0 \
    libxcb-cursor0 \
    libxkbcommon-x11-0 \
    libxcb-icccm4 \
    libxcb-image0 \
    libxcb-keysyms1 \
    libxcb-randr0 \
    libxcb-render-util0 \
    libxcb-shape0
```

---

### Q3: 字体显示方块或乱码

**解决**:
```bash
# 安装中文字体
sudo apt install -y \
    fonts-wqy-zenhei \
    fonts-wqy-microhei \
    fonts-noto-cjk

# 刷新字体缓存
fc-cache -fv
```

---

### Q4: 星环连接失败 `No suitable driver`

**检查 Java**:
```bash
java -version
```

如果没有安装：
```bash
sudo apt install -y default-jre-headless
```

**设置 JAVA_HOME**:
```bash
export JAVA_HOME=$(dirname $(dirname $(readlink -f $(which java))))
echo "JAVA_HOME=$JAVA_HOME" >> ~/.profile
```

---

### Q5: ODBC 驱动找不到

**检查驱动注册**:
```bash
odbcinst -q -d
```

如果没有输出，重新安装：
```bash
sudo dpkg -i drivers/transwarp/odbc/linux/inceptor-connector-odbc-8.37.0.deb
```

**手动配置 ODBC** (如果自动安装失败):

编辑 `/etc/odbcinst.ini`:
```ini
[Inceptor]
Description = Transwarp Inceptor ODBC Driver
Driver      = /opt/transwarp/inceptor-connector/lib/libinceptor_odbc.so
Setup       = /opt/transwarp/inceptor-connector/lib/libinceptor_odbc.so
FileUsage   = 1
```

---

### Q6: 程序启动很慢

**可能原因**:
1. 首次启动需要初始化配置
2. 加载大量驱动
3. 磁盘 I/O 较慢

**优化建议**:
- 确保使用 SSD
- 关闭不必要的后台程序
- 检查是否有杀毒软件扫描

---

## 五、卸载

```bash
# 删除程序
rm -rf /opt/AIDBTools
rm ~/Desktop/AIDBTools.desktop

# 删除虚拟环境（如果是源码部署）
cd AIDBTools
rm -rf .venv

# 卸载星环 ODBC 驱动（可选）
sudo dpkg -r inceptor-connector-odbc

# 卸载 Java（可选）
sudo apt remove default-jre-headless
```

---

## 六、技术支持

如遇到问题，请提供以下信息：

1. **系统版本**:
   ```bash
   cat /etc/kylin-release
   uname -a
   ```

2. **Python 版本**:
   ```bash
   python3 --version
   ```

3. **Java 版本** (如果使用 JDBC):
   ```bash
   java -version
   ```

4. **错误日志**:
   - 终端输出的完整错误信息
   - 或者截图

5. **连接配置**:
   - 数据库类型
   - 连接方式 (ODBC/JDBC)
   - 驱动名称

---

## 七、附录：银河麒麟常用命令

```bash
# 查看系统版本
cat /etc/kylin-release
cat /etc/os-release

# 查看架构
uname -m

# 查看已安装的包
dpkg -l | grep xxx

# 搜索软件包
apt search xxx

# 查看服务状态
systemctl status xxx

# 查看端口占用
netstat -tlnp | grep 10000
```

---

**祝使用愉快！** 🎉
