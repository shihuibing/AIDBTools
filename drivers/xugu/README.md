# 虚谷驱动集成说明

当前项目的虚谷数据库连接已**彻底切回官方 XuguDB-Python (`xgcondb`) 驱动**，不再走 JDBC 子进程桥接方案。

## 当前方案

- 连接驱动：`xgcondb`
- 连接方式：Python 直连
- 推荐运行时：**Python 3.11**
- 元数据读取：`user_tables` / `user_views` / `user_tab_columns` / `user_objects`
- JDBC 依赖：**虚谷链路不再需要**

## 目录结构

```text
drivers/xugu/
├─ helper/                     # 历史 JDBC 桥接文件，当前虚谷链路不再使用
├─ jdbc/                       # 历史 JDBC jar，保留存档，当前虚谷链路不再使用
├─ odbc/
│  ├─ windows-amd64/
│  ├─ linux-x86_64/
│  ├─ linux-aarch64/
│  └─ macos-arm64/
└─ python/
   ├─ windows-amd64/XuguDB/Driver/python/xgcondb/
   ├─ linux-x86_64/XuguDB/Driver/python/xgcondb/
   ├─ linux-aarch64/XuguDB/Driver/python/xgcondb/
   └─ macos-arm64/XuguDB/Driver/python/xgcondb/
```

## 运行要求

### 1）必须使用 Python 3.11

官方 `XuguDB-Python 2.3.7` 当前提供到 Python 3.11 对应的二进制扩展。
AIDBTools 现在已按 **Python 3.11** 作为虚谷默认运行/打包环境处理。

如果仍用更高版本 Python 运行，虚谷连接会在驱动加载阶段直接失败。

### 2）Windows 下需要完整驱动文件

`xgcondb` 目录下除了 `__init__.py`，还必须包含官方提供的：

- `_pyxgdb311.pyd` 等二进制扩展
- `xugusql.dll`

程序会在运行时自动探测 `drivers/xugu/python/.../xgcondb/`，并在 Windows 下补充 DLL 搜索路径。

## 项目内的行为

`core/connection.py` 当前会：

1. 自动定位当前平台对应的 `xgcondb` 目录
2. 在 Windows 下补充 DLL 搜索路径
3. 动态导入官方 `xgcondb`
4. 使用 `xgcondb.connect(host=..., port=..., database=..., user=..., password=..., charset="UTF8")` 建连
5. 直接读取虚谷系统表完成表/视图/函数/字段/预览数据获取

## 打包说明

- `AIDBTools.spec` 已通过 `datas` 打包整个 `drivers/` 目录
- `build.bat` 已改为默认寻找 **Python 3.11** 解释器
- `run.bat` 也已改为默认寻找 **Python 3.11** 解释器
- 星环 JDBC 仍然保留 `JPype1 + jaydebeapi` 依赖，和虚谷链路无关

## 结论

后续维护虚谷连接时，按下面这条原则处理就行：

> **虚谷只走官方 xgcondb，运行/打包统一使用 Python 3.11。**
