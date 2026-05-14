# 银河麒麟 V10 (x86_64) 部署检查清单

## 📋 部署前准备

- [ ] 确认目标系统为银河麒麟 V10 x86_64 架构
  ```bash
  uname -m  # 应输出: x86_64
  cat /etc/kylin-release
  ```

- [ ] 确认有足够的磁盘空间（至少 2GB）
  ```bash
  df -h /
  ```

- [ ] 确认有网络连接或已准备好离线安装包

---

## 🚀 部署步骤

### 阶段一：选择部署方式

- [ ] **方式 A**: 使用预打包的可执行文件
  - [ ] 已在 Linux x86_64 环境打包完成
  - [ ] 产物文件: `release/linux/v{版本}/AIDBTools_v{版本}_linux_x86_64`

- [ ] **方式 B**: 在目标机器上从源码部署
  - [ ] 已复制完整项目到目标机器
  - [ ] 准备运行 `deploy_kylin_x86.sh`

- [ ] **方式 C**: 在目标机器上打包
  - [ ] 已复制完整项目到目标机器
  - [ ] 准备运行 `build_linux.sh`

---

### 阶段二：安装系统依赖

- [ ] Qt 运行时库
  ```bash
  sudo apt install -y libxcb-xinerama0 libxcb-cursor0 \
      libxkbcommon-x11-0 libgl1
  ```

- [ ] Java 环境（用于 JDBC）
  ```bash
  sudo apt install -y default-jre-headless
  java -version  # 验证安装
  ```

- [ ] ODBC 支持（可选，推荐）
  ```bash
  sudo apt install -y unixodbc odbcinst
  ```

- [ ] 中文字体
  ```bash
  sudo apt install -y fonts-wqy-zenhei fonts-wqy-microhei
  ```

---

### 阶段三：安装星环驱动（如需要）

- [ ] 安装 ODBC 驱动
  ```bash
  sudo dpkg -i drivers/transwarp/odbc/linux/inceptor-connector-odbc-8.37.0.deb
  ```

- [ ] 验证驱动注册
  ```bash
  odbcinst -q -d  # 应显示 [Inceptor]
  ```

---

### 阶段四：部署应用程序

#### 如果使用预打包文件：

- [ ] 复制可执行文件到目标位置
  ```bash
  cp AIDBTools /opt/AIDBTools/
  chmod +x /opt/AIDBTools/AIDBTools
  ```

- [ ] 复制驱动目录
  ```bash
  cp -r drivers/ /opt/AIDBTools/
  ```

#### 如果使用一键脚本：

- [ ] 运行部署脚本
  ```bash
  chmod +x deploy_kylin_x86.sh
  ./deploy_kylin_x86.sh
  ```

- [ ] 验证虚拟环境创建成功
  ```bash
  ls -la .venv/bin/python
  ```

#### 如果从源码打包：

- [ ] 运行打包脚本
  ```bash
  chmod +x build_linux.sh
  ./build_linux.sh
  ```

- [ ] 验证打包产物
  ```bash
  ls -lh release/linux/v*/AIDBTools_*
  ```

---

### 阶段五：启动测试

- [ ] 首次启动
  ```bash
  ./AIDBTools
  # 或
  ./run.sh
  ```

- [ ] 检查界面是否正常显示
  - [ ] 主窗口正常打开
  - [ ] 字体显示正常（无方块）
  - [ ] 菜单和按钮可点击

- [ ] 测试数据库连接
  - [ ] 新建一个测试连接
  - [ ] 测试连接成功
  - [ ] 可以浏览数据库对象

- [ ] 测试 SQL 执行
  - [ ] 执行简单查询
  - [ ] 结果正确显示

---

### 阶段六：配置优化

- [ ] 配置 AI 模型（如需要）
  - [ ] 打开 AI 设置
  - [ ] 配置 API Key
  - [ ] 测试 AI 对话

- [ ] 创建常用连接
  - [ ] 添加生产数据库连接
  - [ ] 添加测试数据库连接

- [ ] 创建桌面快捷方式（如果没有自动创建）
  ```bash
  ls -l ~/Desktop/AIDBTools.desktop
  ```

---

## ✅ 验收测试

### 功能测试

- [ ] **连接管理**
  - [ ] 新建连接
  - [ ] 编辑连接
  - [ ] 删除连接
  - [ ] 导入/导出连接

- [ ] **SQL 编辑器**
  - [ ] 语法高亮正常
  - [ ] 自动补全工作
  - [ ] 执行 SQL 成功
  - [ ] 结果显示正确

- [ ] **数据浏览**
  - [ ] 双击表名加载数据
  - [ ] 数据分页正常
  - [ ] 导出数据功能

- [ ] **AI 功能**（如配置）
  - [ ] AI 生成 SQL
  - [ ] AI 优化 SQL
  - [ ] AI 对话助手

- [ ] **其他功能**
  - [ ] 数据同步
  - [ ] 定时任务
  - [ ] 备份恢复

---

### 性能测试

- [ ] 启动时间 < 5 秒
- [ ] SQL 执行响应正常
- [ ] 大数据量查询不卡顿
- [ ] 内存占用合理 (< 500MB)

---

## 🐛 问题记录

如果在部署过程中遇到问题，请记录：

### 问题 1
- **现象**: 
- **错误信息**: 
- **解决方案**: 

### 问题 2
- **现象**: 
- **错误信息**: 
- **解决方案**: 

---

## 📝 部署信息记录

- **部署日期**: _______________
- **部署人员**: _______________
- **系统版本**: _______________
- **AIDBTools 版本**: _______________
- **部署方式**: □ 预打包  □ 一键脚本  □ 源码打包
- **连接方式**: □ ODBC  □ JDBC  □ 两者都有

---

## 🎯 交付清单

部署完成后，应交付以下内容：

- [ ] 可执行程序或启动脚本
- [ ] 部署文档（DEPLOY_KYLIN_X86.md）
- [ ] 快速参考（QUICK_START_KYLIN_X86.md）
- [ ] 用户手册（如有）
- [ ] 技术支持联系方式

---

**部署完成签名**: _______________  **日期**: _______________
