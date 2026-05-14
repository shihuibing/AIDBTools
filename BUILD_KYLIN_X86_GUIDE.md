# AIDBTools 银河麒麟 x86_64 打包说明

> 📦 打包后可直接解压使用，无需安装 Python 环境

---

## 🚀 快速开始

### 在银河麒麟 x86_64 系统中打包

```bash
# 1. 赋予执行权限
chmod +x build_kylin_x86.sh

# 2. 运行打包脚本
./build_kylin_x86.sh

# 等待 5-15 分钟...
```

### 打包产物

```
release/kylin_x86/v{版本号}/
└── AIDBTools_v{版本号}_kylin_x86_64.tar.gz
```

---

## 📦 交付包内容

解压后的目录结构：

```
AIDBTools_v{版本号}_kylin_x86_64/
├── AIDBTools              # 主程序（可执行文件）
├── run.sh                 # 启动脚本（自动配置环境）
├── AIDBTools.desktop      # 桌面快捷方式
├── icon.png               # 应用图标
├── config/                # 配置目录
│   └── model_config.json  # AI 模型配置
├── drivers/               # 数据库驱动
│   └── transwarp/         # 星环驱动
│       ├── jdbc/          # JDBC JAR（已内置）
│       └── odbc/linux/    # ODBC 安装包
└── README.txt             # 使用说明
```

---

## 🎯 部署到目标机器

### 步骤 1：传输文件

通过 U 盘、内部网络或其他方式将 `.tar.gz` 文件复制到目标机器。

### 步骤 2：解压

```bash
tar xzf AIDBTools_v{版本号}_kylin_x86_64.tar.gz
cd AIDBTools_v{版本号}_kylin_x86_64
```

### 步骤 3：安装系统依赖（首次运行必需）

```bash
# Qt 运行时库
sudo apt install -y \
    libxcb-xinerama0 \
    libxcb-cursor0 \
    libxkbcommon-x11-0 \
    libgl1 \
    libglib2.0-0

# Java（仅 JDBC 模式需要）
sudo apt install -y default-jre-headless

# 星环 ODBC 驱动（推荐）
sudo dpkg -i drivers/transwarp/odbc/linux/*.deb
```

### 步骤 4：运行程序

**方式一：使用启动脚本**
```bash
./run.sh
```

**方式二：直接运行**
```bash
chmod +x AIDBTools
./AIDBTools
```

**方式三：桌面快捷方式**
```bash
# 复制桌面文件到桌面
cp AIDBTools.desktop ~/Desktop/
chmod +x ~/Desktop/AIDBTools.desktop

# 双击桌面上的图标
```

---

## ✨ 特性说明

### ✅ 已打包的内容

- ✅ Python 3 解释器
- ✅ 所有 Python 包（PyQt6、SQLAlchemy、pandas 等）
- ✅ 星环 JDBC JAR 文件
- ✅ 应用图标和资源配置
- ✅ 配置文件模板

### ⚠️ 需要预先安装的系统依赖

以下依赖是 **Linux 系统库**，无法打包到程序中：

| 依赖 | 用途 | 是否必需 |
|------|------|---------|
| libxcb-* | Qt 图形界面 | ✅ 必需 |
| libgl1 | OpenGL 支持 | ✅ 必需 |
| libglib2.0-0 | GLib 库 | ✅ 必需 |
| default-jre-headless | Java 运行时 | ⚠️ JDBC 需要 |
| unixodbc | ODBC 支持 | ⚠️ ODBC 需要 |

> 💡 **好消息**：银河麒麟 V10 通常已预装大部分 Qt 依赖。

### ❌ 离线环境限制

- ❌ AI SQL 生成（需要 API 访问）
- ❌ AI 对话助手（需要 API 访问）

其他所有功能均可离线使用。

---

## 🔧 启动脚本说明

`run.sh` 会自动完成以下配置：

1. **检测 Qt 平台**
   - 优先使用 XCB（X11）
   - 其次使用 Wayland
   - 自动探测 DISPLAY 变量

2. **配置 Java 环境**
   - 自动查找 JAVA_HOME
   - 支持多个 JVM 版本

3. **设置工作目录**
   - 确保相对路径正确

你可以直接运行 `./AIDBTools`，但推荐使用 `./run.sh`。

---

## 📋 系统要求

### 最低配置

| 项目 | 要求 |
|------|------|
| 操作系统 | 银河麒麟 V10 SP2+ (x86_64) |
| CPU | Intel/AMD x86_64 双核 |
| 内存 | 4GB RAM |
| 磁盘 | 500MB（程序）+ 2GB（数据） |
| 显示 | X11 图形界面 |

### 推荐配置

| 项目 | 要求 |
|------|------|
| CPU | Intel i5 / AMD Ryzen 5 |
| 内存 | 8GB RAM |
| 磁盘 | SSD，5GB 可用空间 |

---

## 🗄️ 数据库连接

### 星环数据库（Transwarp Inceptor）

**ODBC 模式（推荐）**：
```
1. 安装驱动: sudo dpkg -i drivers/transwarp/odbc/linux/*.deb
2. 验证: odbcinst -q -d  # 应显示 [Inceptor]
3. 连接配置:
   - 类型: Transwarp Inceptor
   - 方式: ODBC
   - 驱动: Inceptor
   - 主机: your-host
   - 端口: 10000
```

**JDBC 模式**：
```
1. 确保 Java 已安装: java -version
2. 连接配置:
   - 类型: Transwarp Inceptor
   - 方式: JDBC
   - 主机: your-host
   - 端口: 10000
```

### 其他数据库

| 数据库 | 连接方式 | 备注 |
|--------|---------|------|
| MySQL | 原生 | ✅ 开箱即用 |
| PostgreSQL | 原生 | ✅ 开箱即用 |
| SQL Server | pymssql | ✅ 已包含 |
| Oracle | oracledb | ✅ 已包含 |
| 虚谷 | JDBC/ODBC | ✅ 驱动已包含 |
| OceanBase | 原生 | ✅ 开箱即用 |
| TiDB | 原生 | ✅ 开箱即用 |

---

## 🐛 常见问题

### Q1: 启动报错 "cannot connect to X server"

```bash
export DISPLAY=:0
./run.sh
```

永久生效：
```bash
echo 'export DISPLAY=:0' >> ~/.profile
source ~/.profile
```

### Q2: Qt 插件错误

```bash
sudo apt install -y libxcb-xinerama0 libxcb-cursor0 libxkbcommon-x11-0
```

### Q3: 字体显示方块

```bash
sudo apt install -y fonts-wqy-zenhei fonts-wqy-microhei
fc-cache -fv
```

### Q4: 星环连接失败

检查 Java：
```bash
java -version
```

如果没有安装：
```bash
sudo apt install -y default-jre-headless
```

### Q5: 程序更新

1. 备份旧版本：
   ```bash
   mv AIDBTools_v1.0.18 AIDBTools_v1.0.18.bak
   ```

2. 解压新版本：
   ```bash
   tar xzf AIDBTools_v1.0.19_kylin_x86_64.tar.gz
   ```

3. 保留用户配置：
   ```bash
   cp AIDBTools_v1.0.18.bak/config/* AIDBTools_v1.0.19/config/
   ```

---

## 📊 打包流程说明

### 脚本执行步骤

1. **[1/7] 安装系统依赖** - Qt 库、Java、开发工具
2. **[2/7] 检查 Java 环境** - 用于 JDBC 支持
3. **[3/7] 创建虚拟环境** - 隔离的 Python 环境
4. **[4/7] 安装 Python 依赖** - PyQt6、数据库驱动等
5. **[5/7] 验证关键依赖** - 确保所有模块可用
6. **[6/7] PyInstaller 打包** - 生成可执行文件
7. **[7/7] 整理交付包** - 创建 tar.gz 压缩包

### 打包时间

- 首次打包：10-15 分钟（下载依赖）
- 后续打包：5-8 分钟（使用缓存）

---

## 🎯 最佳实践

### 1. 在干净环境中打包

建议在虚拟机或容器中打包，确保：
- 没有多余的依赖
- 环境可复现
- 产物体积小

### 2. 测试后再发布

打包完成后：
1. 在隔离环境中测试
2. 验证所有功能
3. 检查文件大小

### 3. 版本管理

```
release/kylin_x86/
├── v1.0.18/
│   └── AIDBTools_v1.0.18_kylin_x86_64.tar.gz
├── v1.0.19/
│   └── AIDBTools_v1.0.19_kylin_x86_64.tar.gz
└── latest -> v1.0.19/  # 符号链接指向最新版
```

### 4. 离线部署准备

如果需要完全离线部署：

```bash
# 1. 在有网机器上下载依赖包
mkdir offline_deps
cd offline_deps
apt-get download libxcb-xinerama0 libxcb-cursor0 \
    libxkbcommon-x11-0 libgl1 default-jre-headless

# 2. 连同程序一起打包
tar czf AIDBTools_Offline_Package.tar.gz \
    AIDBTools_v*_kylin_x86_64.tar.gz \
    offline_deps/
```

---

## 📞 技术支持

- 📖 详细文档: `DEPLOY_KYLIN_X86.md`
- ⚡ 快速参考: `QUICK_START_KYLIN_X86.md`
- ✅ 部署清单: `DEPLOYMENT_CHECKLIST_KYLIN.md`

---

**打包愉快！** 🎉
