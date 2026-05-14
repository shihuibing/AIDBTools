# AIDBTools 离线打包 - 快速开始指南

## 🚀 一键打包

```bash
cd /home/AIDBTools
chmod +x build_kylin_x86_offline.sh
./build_kylin_x86_offline.sh
```

**预计时间**：15-30 分钟
- 下载依赖：2-5 分钟
- 安装依赖：5-10 分钟（Pandas 和 JPype1 需要编译）
- PyInstaller 打包：5-15 分钟

---

## 📋 前置要求

### 打包机器（需要）
- ✅ x86_64 架构
- ✅ Python 3.8/3.9+
- ✅ 网络连接（首次下载依赖）
- ✅ gcc 编译工具（自动检测并安装）

### 目标机器（不需要）
- ❌ 不需要 Python
- ❌ 不需要任何依赖
- ✅ 只需要 x86_64 架构和图形界面

---

## 🔧 常见问题解决

### 问题 1：卡在"安装数据分析和 JDBC 依赖"

**原因**：Pandas 或 JPype1 正在编译，需要 5-10 分钟

**解决**：耐心等待，不要中断！

如果超过 15 分钟还没完成：
```bash
# 按 Ctrl+C 中断

# 检查是否有 gcc
gcc --version

# 如果没有，安装编译工具
sudo yum install gcc gcc-c++ python3-devel

# 手动安装剩余的包
source .venv_offline_build/bin/activate
pip install --no-index --find-links=offline_packages/python_wheels pandas>=2.0 JPype1>=1.2 pyinstaller>=5.0
deactivate

# 重新运行脚本
./build_kylin_x86_offline.sh
```

---

### 问题 2：JPype1 安装失败

**错误信息**：
```
ERROR: Failed building wheel for JPype1
```

**解决**：
```bash
# 安装编译工具
sudo yum install gcc gcc-c++ python3-devel
# 或
sudo apt-get install build-essential python3-dev

# 重新安装
source .venv_offline_build/bin/activate
pip install --no-index --find-links=offline_packages/python_wheels "JPype1>=1.2"
deactivate
```

---

### 问题 3：PyQt5 未找到

**解决**：脚本会自动处理，但如果仍然失败：

```bash
# 方法 1：使用系统 PyQt5
sudo yum install python3-PyQt5
# 或
sudo apt-get install python3-pyqt5

# 方法 2：手动安装
source .venv_offline_build/bin/activate
pip install --no-index --find-links=offline_packages/python_wheels "PyQt5>=5.15.0"
deactivate
```

---

### 问题 4：网络下载失败

**解决**：
```bash
# 脚本会自动重试 3 次

# 如果还是失败，使用国内镜像
export PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple
./build_kylin_x86_offline.sh
```

---

## 📊 打包流程说明

```
[1/8] 下载系统依赖包          ← 下载 .deb/.rpm 包
[2/8] 安装系统依赖            ← 安装 Qt、Java 等
[3/8] 检查 Java 环境          ← JDBC 功能需要
[4/8] 创建虚拟环境            ← Python 3.9
[5/8] 下载 Python 依赖        ← 65 个 .whl 文件
       ├─ [步骤 1/3] 构建依赖
       ├─ [步骤 2/3] 核心依赖 (PyQt5, SQLAlchemy)
       └─ [步骤 3/3] 数据分析 (Pandas, JPype1) ⚠️ 较慢
[6/8] 验证关键依赖            ← 逐个验证
[7/8] PyInstaller 打包        ← 5-15 分钟
[8/8] 创建离线交付包          ← 压缩为 tar.gz
```

---

## ✅ 成功标志

看到以下输出表示打包成功：

```
================================================
  ✅ 完全离线版打包成功！

  版本: v1.0.xx
  平台: 银河麒麟 x86_64
  文件: AIDBTools_v1.0.xx_kylin_x86_64_offline.tar.gz
  大小: 350M
  位置: /home/AIDBTools/release/kylin_x86_offline/v1.0.xx/
  
  ✨ 无需互联网连接，所有依赖已包含！
================================================
```

---

## 📦 部署到目标机器

```bash
# 1. 复制 tar.gz 到目标机器
scp AIDBTools_v*.tar.gz user@target-server:/home/

# 2. 在目标服务器上解压
ssh user@target-server
cd /home
tar xzf AIDBTools_v*.tar.gz
cd AIDBTools_v*

# 3. 运行（无需安装任何东西！）
chmod +x run.sh
./run.sh
```

---

## 🔍 诊断工具

### 检查当前状态
```bash
chmod +x check_status.sh
./check_status.sh
```

### 检查虚拟环境
```bash
source .venv_offline_build/bin/activate
pip list | grep -iE "pyqt|pandas|jpype|pyinstaller"
python -c "import PyQt5, pandas, jpype; print('✅ OK')"
deactivate
```

### 查看日志
```bash
# 打包时保存日志
./build_kylin_x86_offline.sh 2>&1 | tee build.log

# 查看日志
tail -100 build.log
```

---

## 💡 优化建议

### 加速打包
```bash
# 1. 使用 SSD 硬盘
# 2. 确保有足够的内存（建议 4GB+）
# 3. 关闭其他占用资源的程序
# 4. 使用多线程编译
export MAKEFLAGS="-j$(nproc)"
```

### 减小包体积
```bash
# 编辑 AIDBTools_linux.spec
# 设置 strip=True 和 upx=True（已默认启用）
```

---

## 📞 获取帮助

如果遇到问题：

1. **运行诊断脚本**
   ```bash
   ./check_status.sh
   ```

2. **查看详细错误**
   ```bash
   ./build_kylin_x86_offline.sh 2>&1 | tee build.log
   ```

3. **检查关键文件**
   - `BUILD_SCRIPT_IMPROVEMENTS.md` - 脚本改进说明
   - `FIX_PYQT5_INSTALL.md` - PyQt5 安装指南
   - `OFFLINE_DEPLOY_GUIDE.md` - 离线部署指南

---

## 🎯 快速参考

| 命令 | 说明 |
|------|------|
| `./build_kylin_x86_offline.sh` | 开始打包 |
| `./check_status.sh` | 检查状态 |
| `./diagnose_build.sh` | 详细诊断 |
| `source .venv/bin/activate` | 激活虚拟环境 |
| `pip list` | 查看已安装的包 |

---

**祝打包顺利！** 🎉
