# AIDBTools Linux 打包方式对比

> 选择合适的打包方式取决于你的部署场景

---

## 📦 打包脚本对比

| 特性 | build_kylin_x86.sh | build_linux.sh | deploy_kylin_x86.sh |
|------|-------------------|----------------|---------------------|
| **目标架构** | x86_64 | x86_64 / aarch64 | x86_64 |
| **输出格式** | tar.gz 压缩包 | 单一可执行文件 | 源码 + 虚拟环境 |
| **解压即用** | ✅ 是 | ❌ 需要安装依赖 | ❌ 需要运行脚本 |
| **包含配置** | ✅ config/ | ❌ 需单独复制 | ✅ 自动创建 |
| **包含驱动** | ✅ drivers/ | ❌ 需单独复制 | ✅ 自动安装 |
| **启动脚本** | ✅ run.sh | ❌ 无 | ✅ run.sh |
| **桌面快捷** | ✅ .desktop | ❌ 无 | ✅ 自动创建 |
| **适用场景** | 离线部署、分发 | 最小化部署 | 开发环境、测试 |
| **文件大小** | ~150-200MB | ~80-120MB | ~300-500MB |
| **部署复杂度** | ⭐ 简单 | ⭐⭐ 中等 | ⭐ 简单 |

---

## 🎯 使用场景推荐

### 场景一：离线环境部署（推荐 build_kylin_x86.sh）

**特点**：
- ✅ 一次性打包所有内容
- ✅ 传输方便（单个 tar.gz 文件）
- ✅ 解压即可运行
- ✅ 包含完整文档和示例

**适用**：
- 政府、金融等内网环境
- 无法访问互联网的客户现场
- 需要批量部署多个站点

**使用方法**：
```bash
# 打包端（有网机器）
./build_kylin_x86.sh

# 部署端（离线机器）
tar xzf AIDBTools_v*_kylin_x86_64.tar.gz
cd AIDBTools_v*_kylin_x86_64
./run.sh
```

---

### 场景二：最小化部署（推荐 build_linux.sh）

**特点**：
- ✅ 文件体积最小
- ✅ 只包含核心程序
- ❌ 需要预先安装系统依赖
- ❌ 需要单独配置驱动

**适用**：
- 已有统一依赖管理的環境
- 容器化部署（Docker）
- 自动化运维平台

**使用方法**：
```bash
# 打包端
./build_linux.sh

# 部署端
# 1. 安装系统依赖
sudo apt install -y libxcb-xinerama0 libgl1 ...

# 2. 运行程序
chmod +x AIDBTools
./AIDBTools
```

---

### 场景三：开发/测试环境（推荐 deploy_kylin_x86.sh）

**特点**：
- ✅ 快速部署源码
- ✅ 便于调试和修改
- ✅ 自动配置所有依赖
- ❌ 占用空间较大
- ❌ 不是独立可执行文件

**适用**：
- 开发人员本地测试
- QA 测试环境
- 需要频繁更新的场景

**使用方法**：
```bash
# 直接运行
./deploy_kylin_x86.sh

# 后续启动
./run.sh
```

---

## 📊 详细对比

### 1. 打包产物

#### build_kylin_x86.sh
```
release/kylin_x86/v1.0.19/
└── AIDBTools_v1.0.19_kylin_x86_64.tar.gz (180MB)
    解压后:
    ├── AIDBTools          # 主程序
    ├── run.sh             # 启动脚本
    ├── AIDBTools.desktop  # 桌面快捷
    ├── icon.png
    ├── README.txt
    ├── config/            # 配置目录
    └── drivers/           # 数据库驱动
```

#### build_linux.sh
```
release/linux/v1.0.19/
└── AIDBTools_v1.0.19_linux_x86_64 (100MB)
    只有可执行文件，其他需单独准备
```

#### deploy_kylin_x86.sh
```
不生成打包文件，直接在当前目录创建:
├── .venv/                 # Python 虚拟环境 (~300MB)
├── run.sh                 # 启动脚本
├── AIDBTools.desktop      # 桌面快捷
└── 所有源码文件
```

---

### 2. 部署要求

#### build_kylin_x86.sh
```bash
# 目标机器需要安装的系统依赖
sudo apt install -y \
    libxcb-xinerama0 \
    libxcb-cursor0 \
    libxkbcommon-x11-0 \
    libgl1 \
    default-jre-headless  # 可选

# 然后解压即可使用
tar xzf AIDBTools_*.tar.gz
./run.sh
```

#### build_linux.sh
```bash
# 目标机器需要安装更多依赖
sudo apt install -y \
    libxcb-xinerama0 \
    libxcb-cursor0 \
    libxkbcommon-x11-0 \
    libgl1 \
    default-jre-headless \
    unixodbc

# 还需要手动复制配置和驱动
cp -r config/ /opt/AIDBTools/
cp -r drivers/ /opt/AIDBTools/

# 运行
./AIDBTools
```

#### deploy_kylin_x86.sh
```bash
# 自动安装所有依赖，无需手动操作
./deploy_kylin_x86.sh

# 启动
./run.sh
```

---

### 3. 更新维护

#### build_kylin_x86.sh
```bash
# 更新步骤
1. 备份旧版本
   mv AIDBTools_v1.0.18 AIDBTools_v1.0.18.bak

2. 解压新版本
   tar xzf AIDBTools_v1.0.19_kylin_x86_64.tar.gz

3. 迁移配置（可选）
   cp AIDBTools_v1.0.18.bak/config/* AIDBTools_v1.0.19/config/

4. 删除备份
   rm -rf AIDBTools_v1.0.18.bak
```

#### build_linux.sh
```bash
# 更新步骤
1. 替换可执行文件
   cp AIDBTools_v1.0.19_linux_x86_64 /opt/AIDBTools/AIDBTools

2. 重启程序
```

#### deploy_kylin_x86.sh
```bash
# 更新步骤
1. 拉取最新代码
   git pull

2. 重新运行部署脚本
   ./deploy_kylin_x86.sh
```

---

### 4. 离线支持

| 打包方式 | 完全离线 | 部分离线 | 需要网络 |
|---------|---------|---------|---------|
| build_kylin_x86.sh | ✅ 是 | - | - |
| build_linux.sh | ⚠️ 需准备离线包 | - | - |
| deploy_kylin_x86.sh | ❌ 否 | - | ✅ 是 |

**注意**：所有方式的 AI 功能都需要网络访问 API。

---

## 🎯 选择建议

### 选择 build_kylin_x86.sh 如果：

- ✅ 需要在离线环境部署
- ✅ 需要分发给多个客户
- ✅ 希望简化部署流程
- ✅ 需要完整的交付包（含文档、驱动）
- ✅ 目标用户技术水平一般

**典型场景**：
- 政府项目交付
- 金融机构内网部署
- 商业软件分发
- 客户现场实施

---

### 选择 build_linux.sh 如果：

- ✅ 追求最小文件体积
- ✅ 有统一的依赖管理系统
- ✅ 使用容器化部署
- ✅ 自动化运维平台集成
- ✅ 技术人员熟悉 Linux

**典型场景**：
- Docker 镜像构建
- Kubernetes 部署
- CI/CD 流水线
- 内部技术团队使用

---

### 选择 deploy_kylin_x86.sh 如果：

- ✅ 开发和测试环境
- ✅ 需要频繁修改代码
- ✅ 调试和排查问题
- ✅ 快速原型验证
- ✅ 学习和技术研究

**典型场景**：
- 开发人员本地环境
- QA 测试服务器
- 技术演示
- PoC 概念验证

---

## 📝 总结

| 维度 | build_kylin_x86.sh | build_linux.sh | deploy_kylin_x86.sh |
|------|-------------------|----------------|---------------------|
| **易用性** | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ |
| **完整性** | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ |
| **灵活性** | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ |
| **离线支持** | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐ |
| **文件大小** | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐ |
| **部署速度** | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ |

**推荐**：
- 🥇 **生产环境**：`build_kylin_x86.sh`
- 🥈 **技术团队**：`build_linux.sh`
- 🥉 **开发测试**：`deploy_kylin_x86.sh`

---

**根据你的实际需求选择合适的打包方式！** 🎯
