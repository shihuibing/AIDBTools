# AIDBTools 完全离线部署指南

> 📦 所有依赖已集成，无需互联网连接

---

## 🎯 适用场景

- ✅ 政府内网环境
- ✅ 金融隔离网络
- ✅ 军工涉密系统
- ✅ 无任何外网访问权限的环境
- ✅ 需要严格安全控制的场景

---

## 📋 打包准备（在有网机器上）

### 1. 系统要求

```bash
# 必须是 x86_64 架构
uname -m  # 应输出: x86_64

# 必须有网络连接（仅用于下载依赖）
ping -c 1 mirrors.aliyun.com
```

### 2. 执行打包

```bash
chmod +x build_kylin_x86_offline.sh
./build_kylin_x86_offline.sh
```

**打包过程**（约 10-20 分钟）：
1. [1/8] 下载系统依赖包（.deb 或 .rpm）
2. [2/8] 安装系统依赖（构建用）
3. [3/8] 检查 Java 环境
4. [4/8] 创建虚拟环境
5. [5/8] 下载 Python 依赖包（.whl 文件）
6. [6/8] 验证关键依赖
7. [7/8] PyInstaller 打包
8. [8/8] 创建完全离线交付包

### 3. 打包产物

```
release/kylin_x86_offline/v{版本号}/
└── AIDBTools_v{版本号}_kylin_x86_64_offline.tar.gz
    大小: ~300-500MB（包含所有依赖）
```

---

## 📦 离线包内容

```
AIDBTools_v{版本号}_kylin_x86_64_offline/
├── AIDBTools                    # 主程序
├── run.sh                       # 启动脚本
├── install_offline.sh           # ⭐ 离线安装脚本
├── AIDBTools.desktop            # 桌面快捷方式
├── icon.png                     # 应用图标
├── README_OFFLINE.txt           # 使用说明
├── config/                      # 配置目录
│   └── model_config.json        # AI 模型配置
├── drivers/                     # 数据库驱动
│   └── transwarp/
│       ├── jdbc/                # JDBC JAR
│       └── odbc/linux/          # ODBC 安装包
└── offline_packages/            # ⭐ 所有离线依赖
    ├── deb/                     # 系统依赖（.deb）
    │   ├── libxcb-*.deb
    │   ├── libgl1*.deb
    │   ├── default-jre*.deb
    │   └── ...
    ├── rpm/                     # 系统依赖（.rpm，如果是 CentOS）
    └── python_wheels/           # Python 依赖（.whl）
        ├── PyQt6-*.whl
        ├── sqlalchemy-*.whl
        └── ...
```

---

## 🚀 离线部署步骤

### 步骤 1：传输到目标机器

通过以下方式将 `.tar.gz` 文件复制到目标机器：
- U 盘/移动硬盘
- 内部网络共享
- 光盘刻录
- 安全文件交换系统

### 步骤 2：解压

```bash
# 选择安装目录
mkdir -p /opt/AIDBTools
cd /opt/AIDBTools

# 解压
tar xzf /path/to/AIDBTools_v*_kylin_x86_64_offline.tar.gz
cd AIDBTools_v*_kylin_x86_64_offline
```

### 步骤 3：运行离线安装脚本

```bash
# 赋予执行权限
chmod +x install_offline.sh

# 执行安装（需要 sudo 权限）
sudo ./install_offline.sh
```

**安装脚本会自动完成**：
- ✅ 安装所有系统依赖（从离线包）
- ✅ 创建 Python 虚拟环境（如需要）
- ✅ 安装所有 Python 依赖（从离线包）
- ✅ 设置程序权限
- ✅ 创建桌面快捷方式

### 步骤 4：启动程序

```bash
# 方式一：使用启动脚本
./run.sh

# 方式二：直接运行
chmod +x AIDBTools
./AIDBTools

# 方式三：双击桌面图标
# 桌面上会出现 AIDBTools 图标
```

---

## 🔍 验证安装

### 检查系统依赖

```bash
# Qt 库
dpkg -l | grep libxcb
dpkg -l | grep libgl1

# Java
java -version

# ODBC
odbcinst -q -d
```

### 检查 Python 环境

```bash
# 如果使用虚拟环境
source .venv/bin/activate
pip list | grep -i pyqt
pip list | grep -i sqlalchemy
```

### 测试程序

```bash
./run.sh

# 应该能看到：
# 1. 主窗口正常打开
# 2. 字体显示正常
# 3. 可以新建数据库连接
```

---

## 🗄️ 数据库连接配置

### 星环数据库（Transwarp Inceptor）

#### ODBC 模式（推荐）

```bash
# 1. 安装 ODBC 驱动
sudo dpkg -i drivers/transwarp/odbc/linux/*.deb

# 2. 验证驱动
odbcinst -q -d
# 应输出: [Inceptor]

# 3. 在程序中配置连接
类型: Transwarp Inceptor
方式: ODBC
驱动: Inceptor
主机: your-host
端口: 10000
数据库: default
用户名: admin
密码: ******
```

#### JDBC 模式

```bash
# 1. 确保 Java 已安装
java -version

# 2. 在程序中配置连接
类型: Transwarp Inceptor
方式: JDBC
主机: your-host
端口: 10000
数据库: default
用户名: admin
密码: ******
```

### 其他数据库

| 数据库 | 连接方式 | 说明 |
|--------|---------|------|
| MySQL | 原生 | ✅ 已包含驱动 |
| PostgreSQL | 原生 | ✅ 已包含驱动 |
| SQL Server | pymssql | ✅ 已包含 |
| Oracle | oracledb | ✅ 已包含 |
| 虚谷 | JDBC/ODBC | ✅ 驱动已包含 |
| OceanBase | 原生 | ✅ 已包含 |
| TiDB | 原生 | ✅ 已包含 |

---

## 📊 文件大小参考

| 组件 | 大小 |
|------|------|
| 主程序（AIDBTools） | ~100MB |
| 系统依赖包（deb/rpm） | ~50-100MB |
| Python 依赖包（whl） | ~150-250MB |
| 数据库驱动 | ~20-50MB |
| **总计（压缩前）** | ~320-500MB |
| **总计（压缩后）** | ~200-350MB |

---

## 🔄 版本更新

### 更新步骤

```bash
# 1. 备份旧版本
mv /opt/AIDBTools/AIDBTools_v1.0.18_offline \
   /opt/AIDBTools/AIDBTools_v1.0.18_offline.bak

# 2. 解压新版本
cd /opt/AIDBTools
tar xzf AIDBTools_v1.0.19_kylin_x86_64_offline.tar.gz
cd AIDBTools_v1.0.19_kylin_x86_64_offline

# 3. 迁移用户配置
cp ../AIDBTools_v1.0.18_offline.bak/config/* config/

# 4. 重新安装（可选，如果依赖有变化）
sudo ./install_offline.sh

# 5. 测试新版本
./run.sh

# 6. 确认无误后删除备份
rm -rf ../AIDBTools_v1.0.18_offline.bak
```

---

## 🐛 常见问题

### Q1: install_offline.sh 执行失败

**现象**：提示权限不足或命令找不到

**解决**：
```bash
# 确保使用 sudo
sudo chmod +x install_offline.sh
sudo ./install_offline.sh

# 检查 bash 版本
bash --version
```

### Q2: dpkg 安装 .deb 包失败

**现象**：依赖冲突或缺失

**解决**：
```bash
# 修复依赖
sudo apt-get install -f -y

# 或者逐个安装
sudo dpkg -i offline_packages/deb/libxcb-xinerama0_*.deb
sudo dpkg -i offline_packages/deb/libxcb-cursor0_*.deb
# ... 依次安装
```

### Q3: 启动后界面空白

**现象**：程序启动但窗口无内容

**解决**：
```bash
# 检查 DISPLAY 变量
echo $DISPLAY

# 如果为空，设置
export DISPLAY=:0
./run.sh

# 检查 Qt 平台
echo $QT_QPA_PLATFORM
# 应该是 xcb
```

### Q4: 字体显示方块

**现象**：中文显示为方块

**解决**：
```bash
# 离线包已包含字体，重新安装
sudo dpkg -i offline_packages/deb/fonts-wqy-*.deb

# 刷新字体缓存
fc-cache -fv

# 重启程序
```

### Q5: 星环连接失败

**现象**：提示驱动找不到

**解决**：
```bash
# 检查 ODBC 驱动
odbcinst -q -d

# 如果没有输出，重新安装
sudo dpkg -i drivers/transwarp/odbc/linux/*.deb

# 验证
odbcinst -q -d
# 应显示: [Inceptor]
```

### Q6: Java 找不到

**现象**：JDBC 模式连接失败

**解决**：
```bash
# 检查 Java
java -version

# 如果没有，从离线包安装
sudo dpkg -i offline_packages/deb/default-jre-headless_*.deb

# 设置 JAVA_HOME
export JAVA_HOME=$(dirname $(dirname $(readlink -f $(which java))))
echo "JAVA_HOME=$JAVA_HOME" >> ~/.profile
```

---

## 💡 最佳实践

### 1. 测试环境验证

在正式部署前：
```bash
# 1. 在虚拟机中测试
# 2. 验证所有功能
# 3. 测试数据库连接
# 4. 记录问题和解决方案
```

### 2. 批量部署

```bash
# 创建批量部署脚本
cat > deploy_batch.sh << 'EOF'
#!/bin/bash
TARGET_HOSTS="host1 host2 host3"

for host in $TARGET_HOSTS; do
    echo "部署到 $host ..."
    scp AIDBTools_*.tar.gz user@$host:/tmp/
    ssh user@$host << 'SSH_EOF'
        cd /opt
        tar xzf /tmp/AIDBTools_*.tar.gz
        cd AIDBTools_*
        sudo ./install_offline.sh
    SSH_EOF
done
EOF
```

### 3. 文档归档

保留以下文档：
- ✅ 打包日志
- ✅ 依赖清单
- ✅ 部署记录
- ✅ 问题解决方案

### 4. 安全管理

```bash
# 设置合适的权限
sudo chown -R root:root /opt/AIDBTools
sudo chmod 755 /opt/AIDBTools/AIDBTools
sudo chmod 644 /opt/AIDBTools/config/*

# 定期备份配置
tar czf config_backup_$(date +%Y%m%d).tar.gz config/
```

---

## 📞 技术支持

### 离线环境诊断信息收集

如需技术支持，请收集以下信息：

```bash
# 系统信息
uname -a
cat /etc/kylin-release

# 已安装的包
dpkg -l | grep -E "libxcb|libgl|java" > installed_packages.txt

# 错误日志
./run.sh 2>&1 | tee error.log

# 依赖检查
ldd AIDBTools | grep "not found" > missing_libs.txt

# 打包以上文件
tar czf diagnostic_info.tar.gz \
    installed_packages.txt \
    error.log \
    missing_libs.txt
```

---

## 📝 总结

### ✅ 完全离线版优势

- ✅ **零网络依赖** - 所有依赖已包含
- ✅ **一键安装** - install_offline.sh 自动处理
- ✅ **完整交付** - 包含文档、驱动、配置
- ✅ **易于分发** - 单个 tar.gz 文件
- ✅ **安全可靠** - 无需外网访问

### ⚠️ 注意事项

- ⚠️ 打包需要在**有网机器**上进行
- ⚠️ 文件大小较大（~300-500MB）
- ⚠️ AI 功能仍需要网络（或部署本地大模型）
- ⚠️ 首次安装需要 sudo 权限

### 🎯 适用场景

- 政府内网
- 金融机构
- 军工单位
- 隔离网络
- 安全要求高的环境

---

**祝部署顺利！** 🎉
