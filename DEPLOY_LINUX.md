# AIDBTools 国产系统部署指南

> 适用：银河麒麟 V10 / 统信UOS / Deepin / Ubuntu 22.04+ / CentOS 7+  
> 架构：x86_64 / aarch64（ARM，鲲鹏/飞腾/龙芯）

---

## 一、快速部署（推荐）

### 方案①：源码 + 一键安装（最简单）

1. 将整个项目目录复制到目标机器（U 盘 / scp / rsync 均可）
2. 在项目目录下执行：

```bash
chmod +x install_kylin.sh
./install_kylin.sh
```

安装完成后双击桌面图标或运行 `./run.sh` 启动。

**脚本自动完成：**
- 检测 Python 版本（需 ≥3.9）
- 安装 Qt 运行库、字体、ODBC 运行库、Java JRE
- 尝试自动安装星环 ODBC 驱动（`drivers/transwarp/odbc/linux/`）
- 创建 Python 虚拟环境并安装所有依赖
- 生成桌面快捷方式

---

### 方案②：已打包可执行文件

> 需在 **与目标机器同架构** 的 Linux 上先打包（用 `build_linux.sh`）。

**打包步骤（在 WSL2 / 同架构 Linux 上）：**
```bash
chmod +x build_linux.sh
./build_linux.sh
```

**部署到目标机器（复制以下内容）：**
```
dist/AIDBTools          ← 可执行文件
config/                 ← 配置目录
drivers/transwarp/      ← 星环驱动包（用于 ODBC 安装）
```

**目标机器启动：**
```bash
chmod +x AIDBTools
./AIDBTools
```

> ⚠️ 单文件 exe 已内嵌 JAR，无需额外配置 JAR 路径。

---

## 二、星环数据库驱动说明

### 驱动优先级

| 优先级 | 方式 | 条件 |
|--------|------|------|
| 1 | **ODBC**（性能最佳） | 已安装星环 ODBC 驱动 |
| 2 | **JDBC**（内置）| Java JRE ≥ 8 可用 |
| - | 均不可用 | 界面提示安装步骤 |

### 手动安装 ODBC 驱动

项目内置安装包位于 `drivers/transwarp/odbc/linux/`：

| 文件 | 适用 |
|------|------|
| `inceptor-connector-odbc-8.37.0.deb` | 麒麟/UOS/Deepin/Ubuntu（deb 系，x86） |
| `inceptor-connector-odbc-8.37.0-1.ky10.ky10.aarch64.rpm` | 银河麒麟 V10 ARM（鲲鹏/飞腾） |
| `inceptor-connector-odbc-8.37-1.el7.x86_64.rpm` | CentOS 7 / OpenEuler x86 |
| `inceptor-connector-odbc-8.37-1.el7.i686.rpm` | CentOS 7 i686 |

```bash
# deb 系
sudo dpkg -i drivers/transwarp/odbc/linux/inceptor-connector-odbc-8.37.0.deb

# rpm 系
sudo rpm -ivh drivers/transwarp/odbc/linux/inceptor-connector-odbc-8.37-1.el7.x86_64.rpm

# openEuler / 较新 CentOS
sudo dnf install drivers/transwarp/odbc/linux/inceptor-connector-odbc-8.37-1.el7.x86_64.rpm
```

### 手动安装 Java（JDBC 模式）

```bash
# deb 系（麒麟/UOS/Ubuntu）
sudo apt install default-jre-headless

# rpm 系（CentOS/OpenEuler）
sudo yum install java-11-openjdk-headless
# 或
sudo dnf install java-11-openjdk-headless
```

安装后重新启动 AIDBTools，JDBC 模式会自动激活。

---

## 三、系统架构兼容性

| 架构 | 麒麟V10 | 统信UOS | Deepin | Ubuntu | CentOS7 |
|------|---------|---------|--------|--------|---------|
| x86_64 | ✅ | ✅ | ✅ | ✅ | ✅ |
| aarch64（鲲鹏/飞腾） | ✅ | ✅ | ✅ | ✅ | ⚠️¹ |
| loongarch64（龙芯） | ⚠️² | ⚠️² | - | - | - |

> ¹ CentOS 7 aarch64 无内置 ODBC 包，使用 JDBC 模式  
> ² 龙芯架构未测试，理论上源码运行可用，打包需在龙芯机器上执行

---

## 四、常见问题

### Q1：启动时报 `cannot connect to X server`

```bash
# 检查 DISPLAY 变量
echo $DISPLAY

# 如果为空，尝试
export DISPLAY=:0
./run.sh
```

### Q2：Qt 报 `Could not find the Qt platform plugin "xcb"`

```bash
# 麒麟/UOS
sudo apt install libxcb-xinerama0 libxcb-cursor0 libxkbcommon-x11-0

# CentOS
sudo yum install xcb-util xcb-util-image xcb-util-keysyms xcb-util-renderutil xcb-util-wm
```

### Q3：星环连接报 `No suitable driver` / `ClassNotFoundException`

原因：JPype 找不到 JVM。解决：

```bash
# 设置 JAVA_HOME 后再启动
export JAVA_HOME=$(dirname $(dirname $(readlink -f $(which java))))
./run.sh
```

或在 `/etc/environment` 中永久设置：
```
JAVA_HOME=/usr/lib/jvm/default-java
```

### Q4：ODBC 安装后驱动名不识别

查看已注册驱动名：
```bash
odbcinst -q -d
```

将实际驱动名填入连接配置的"ODBC 驱动"字段，或联系管理员确认驱动名称。

### Q5：字体显示方块 / 乱码

```bash
sudo apt install fonts-wqy-zenhei fonts-wqy-microhei fonts-noto-cjk
fc-cache -fv
```

---

## 五、卸载

```bash
# 删除虚拟环境
rm -rf .venv

# 删除桌面快捷方式
rm ~/Desktop/AIDBTools.desktop

# 如需卸载星环 ODBC
sudo dpkg -r inceptor-connector-odbc     # deb 系
sudo rpm -e inceptor-connector-odbc      # rpm 系
```
