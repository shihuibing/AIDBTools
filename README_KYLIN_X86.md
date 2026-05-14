# AIDBTools 银河麒麟 V10 (x86_64) 部署总览

> 📅 更新时间: 2024年  
> 🎯 目标平台: 银河麒麟 V10 SP2/SP3 x86_64

---

## 📚 文档导航

| 文档 | 用途 | 适用人群 |
|------|------|----------|
| **[QUICK_START_KYLIN_X86.md](QUICK_START_KYLIN_X86.md)** | 快速参考，常用命令速查 | 所有用户 |
| **[DEPLOY_KYLIN_X86.md](DEPLOY_KYLIN_X86.md)** | 详细部署指南，故障排查 | 系统管理员、运维人员 |
| **[DEPLOYMENT_CHECKLIST_KYLIN.md](DEPLOYMENT_CHECKLIST_KYLIN.md)** | 部署检查清单，验收测试 | 项目经理、实施人员 |
| **[DEPLOY_LINUX.md](DEPLOY_LINUX.md)** | 通用 Linux 部署指南 | 其他 Linux 发行版用户 |

---

## 🚀 快速开始（3 步部署）

### 方法一：使用一键脚本（最简单）

```bash
# 1. 进入项目目录
cd AIDBTools

# 2. 运行部署脚本
chmod +x deploy_kylin_x86.sh
./deploy_kylin_x86.sh

# 3. 启动程序
./run.sh
# 或双击桌面图标
```

✅ **自动完成**：
- 安装所有系统依赖
- 配置 Java 环境
- 安装星环 ODBC 驱动
- 创建 Python 虚拟环境
- 生成桌面快捷方式

---

### 方法二：使用预打包文件

```bash
# 1. 安装依赖
sudo apt update
sudo apt install -y libxcb-xinerama0 libxcb-cursor0 \
    libxkbcommon-x11-0 libgl1 default-jre-headless

# 2. 启动程序
chmod +x AIDBTools
./AIDBTools
```

---

## 📦 打包说明

### 在银河麒麟系统中打包

```bash
chmod +x build_linux.sh
./build_linux.sh
```

产物位置：`release/linux/v{版本}/AIDBTools_v{版本}_linux_x86_64`

### 从 Windows 交叉打包

⚠️ **注意**: PyInstaller 不支持跨平台打包，必须在 Linux 环境中进行。

推荐方案：
1. 使用 WSL2 Ubuntu
2. 使用 Docker 容器
3. 直接在银河麒麟系统中打包

---

## 🔧 系统要求

### 最低配置

| 项目 | 要求 |
|------|------|
| 操作系统 | 银河麒麟 V10 SP2+ (x86_64) |
| CPU | Intel/AMD x86_64 双核 |
| 内存 | 4GB RAM |
| 磁盘 | 2GB 可用空间 |
| 显示 | 支持 X11 图形界面 |

### 推荐配置

| 项目 | 要求 |
|------|------|
| CPU | Intel i5 / AMD Ryzen 5 或更高 |
| 内存 | 8GB RAM |
| 磁盘 | SSD，5GB 可用空间 |
| 网络 | 用于 AI 功能和数据库连接 |

---

## 🗄️ 数据库支持

### 已支持的数据库

| 数据库 | 连接方式 | 备注 |
|--------|---------|------|
| MySQL / MariaDB | 原生 | ✅ 完全支持 |
| PostgreSQL | 原生 | ✅ 完全支持 |
| SQL Server | pymssql/pyodbc | ✅ 完全支持 |
| Oracle | oracledb | ✅ 完全支持 |
| **Transwarp Inceptor** | ODBC/JDBC | ✅ 内置驱动 |
| 虚谷数据库 | JDBC/ODBC | ✅ 内置驱动 |
| 达梦数据库 | ODBC | 需单独安装驱动 |
| 人大金仓 | ODBC | 需单独安装驱动 |
| OceanBase | 原生 | ✅ 完全支持 |
| TiDB | 原生 | ✅ 完全支持 |

### 星环数据库特别说明

**驱动优先级**：
1. **ODBC**（推荐）- 性能最佳，需要安装驱动
2. **JDBC** - 无需额外安装，需要 Java

**ODBC 驱动安装**：
```bash
sudo dpkg -i drivers/transwarp/odbc/linux/inceptor-connector-odbc-8.37.0.deb
odbcinst -q -d  # 验证
```

**JDBC 模式**：
```bash
sudo apt install -y default-jre-headless
java -version   # 验证
```

---

## 🎨 功能特性

### 核心功能

- ✅ 多数据库连接管理
- ✅ SQL 编辑器（语法高亮、自动补全）
- ✅ 数据浏览和编辑
- ✅ 数据导入/导出（Excel、CSV、SQL）
- ✅ AI SQL 生成和优化
- ✅ AI 对话助手
- ✅ 数据同步（表级/库级）
- ✅ 定时任务调度
- ✅ 数据库备份/恢复

### 新增功能（v1.0.x）

- ✅ SQL 安全提醒（危险操作警告）
- ✅ 查询管理（保存/加载 SQL）
- ✅ 现代化图标系统
- ✅ 优化的树形结构样式
- ✅ SQL Server 临时表支持

---

## 🔍 故障排查

### 常见问题速查

| 问题 | 可能原因 | 解决方案 |
|------|---------|---------|
| 无法启动 | 缺少 Qt 依赖 | 安装 libxcb-* 包 |
| 字体方块 | 缺少中文字体 | 安装 fonts-wqy-zenhei |
| 显示错误 | DISPLAY 未设置 | `export DISPLAY=:0` |
| JDBC 失败 | 未安装 Java | `apt install default-jre-headless` |
| ODBC 失败 | 驱动未注册 | 重新安装 .deb 包 |
| 连接超时 | 网络/防火墙 | 检查网络和端口 |

### 获取帮助

1. 查看详细日志：
   ```bash
   ./AIDBTools 2>&1 | tee debug.log
   ```

2. 检查系统信息：
   ```bash
   cat /etc/kylin-release
   uname -a
   python3 --version
   java -version
   ```

3. 联系技术支持，提供：
   - 系统版本
   - 错误日志
   - 复现步骤

---

## 📞 技术支持

### 资源链接

- 📖 完整文档: [DEPLOY_KYLIN_X86.md](DEPLOY_KYLIN_X86.md)
- ⚡ 快速参考: [QUICK_START_KYLIN_X86.md](QUICK_START_KYLIN_X86.md)
- ✅ 部署清单: [DEPLOYMENT_CHECKLIST_KYLIN.md](DEPLOYMENT_CHECKLIST_KYLIN.md)

### 反馈渠道

- 🐛 Bug 报告: 提交 Issue
- 💡 功能建议: 提交 Feature Request
- 📧 邮件支持: support@example.com

---

## 📝 更新日志

### v1.0.x (当前版本)

**新增**：
- SQL 查询管理功能
- SQL 语法高亮和自动补全
- SQL 安全提醒（危险操作警告）
- 现代化图标系统
- 优化的 UI 样式

**修复**：
- SQL Server 临时表会话问题
- 关闭连接后显示"正在加载"的问题
- 树形结构选中样式

**改进**：
- 银河麒麟 x86_64 专用部署脚本
- 完善的部署文档和检查清单

---

## 📄 许可证

本项目遵循 [LICENSE](LICENSE) 协议。

---

**祝使用愉快！** 🎉

如有问题，请查阅详细文档或联系技术支持。
