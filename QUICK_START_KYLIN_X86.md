# 银河麒麟 V10 (x86_64) 部署快速参考

## 📦 部署方式选择

### 方式一：使用预打包文件（推荐生产环境）

```bash
# 1. 复制文件到目标机器
AIDBTools          # 可执行文件
drivers/           # 驱动目录

# 2. 安装依赖
sudo apt update
sudo apt install -y libxcb-xinerama0 libxcb-cursor0 libxkbcommon-x11-0 \
    libgl1 default-jre-headless unixodbc

# 3. 安装星环 ODBC（可选）
sudo dpkg -i drivers/transwarp/odbc/linux/inceptor-connector-odbc-8.37.0.deb

# 4. 启动
chmod +x AIDBTools
./AIDBTools
```

---

### 方式二：一键脚本部署（推荐开发环境）

```bash
# 在项目目录下执行
chmod +x deploy_kylin_x86.sh
./deploy_kylin_x86.sh

# 启动
./run.sh
# 或双击桌面图标
```

---

### 方式三：从源码打包

```bash
# 在银河麒麟系统中
chmod +x build_linux.sh
./build_linux.sh

# 产物位置
release/linux/v{版本}/AIDBTools_v{版本}_linux_x86_64
```

---

## 🔧 常用命令

### 系统信息
```bash
cat /etc/kylin-release     # 查看系统版本
uname -m                   # 查看架构（应为 x86_64）
python3 --version          # Python 版本
java -version              # Java 版本
```

### 驱动检查
```bash
odbcinst -q -d             # 查看已注册的 ODBC 驱动
dpkg -l | grep inceptor    # 查看已安装的星环包
```

### 故障排查
```bash
echo $DISPLAY              # 检查显示环境变量
export DISPLAY=:0          # 设置显示变量

fc-cache -fv               # 刷新字体缓存

# 查看详细错误
./AIDBTools 2>&1 | tee error.log
```

---

## ⚙️ 星环数据库连接

### ODBC 模式（推荐）
```
类型: Transwarp Inceptor
方式: ODBC
驱动: Inceptor
主机: your-host
端口: 10000
```

### JDBC 模式
```
类型: Transwarp Inceptor
方式: JDBC
主机: your-host
端口: 10000
```

> 需要确保 `java -version` 有输出

---

## ❓ 常见问题速查

| 问题 | 解决 |
|------|------|
| cannot connect to X server | `export DISPLAY=:0` |
| Qt plugin "xcb" not found | `sudo apt install libxcb-xinerama0 libxcb-cursor0` |
| 字体显示方块 | `sudo apt install fonts-wqy-zenhei` |
| No suitable driver | 安装 Java: `sudo apt install default-jre-headless` |
| ODBC 驱动找不到 | `sudo dpkg -i drivers/transwarp/odbc/linux/*.deb` |

---

## 📁 重要路径

```
/opt/AIDBTools/              # 程序安装目录（如果安装）
~/.config/AIDBTools/         # 用户配置
~/Desktop/AIDBTools.desktop  # 桌面快捷方式
drivers/transwarp/           # 星环驱动
config/model_config.json     # AI 模型配置
connections.json             # 数据库连接配置
```

---

## 🗑️ 卸载

```bash
# 删除程序
rm -rf /opt/AIDBTools
rm ~/Desktop/AIDBTools.desktop

# 删除虚拟环境
cd AIDBTools && rm -rf .venv

# 卸载驱动（可选）
sudo dpkg -r inceptor-connector-odbc
sudo apt remove default-jre-headless
```

---

**详细文档**: 查看 `DEPLOY_KYLIN_X86.md`
