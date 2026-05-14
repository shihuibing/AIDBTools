# 星环驱动集成说明

## 目录结构

- `jdbc/`
  - `quark-driver-8.37.3.jar`
  - `inceptor-driver-8.37.3.jar`
- `odbc/win64/`
  - `inceptor-connector-odbc-8.37.3-winx64.exe`
- `odbc/win32/`
  - `inceptor-connector-odbc-8.37.3-win32.exe`
- `odbc/linux/`
  - `inceptor-connector-odbc-8.37-1.el7.i686.rpm`
  - `inceptor-connector-odbc-8.37-1.el7.x86_64.rpm`
  - `inceptor-connector-odbc-8.37.0-1.ky10.ky10.aarch64.rpm`
  - `inceptor-connector-odbc-8.37.0.deb`

## 当前接入策略

- 程序默认优先使用 `JDBC`。
- 原因：当前连接界面是按 `host / port / dbname / user / password` 录入，和 JDBC 模式天然匹配。
- `ODBC` 仅在系统中已经配置好星环 `DSN` 时才启用。
- 这样可以避免 Windows 上只是安装了 `Transwarp Inceptor ODBC Driver`，但没有配置 DSN 时，程序误走 ODBC 并报 `HY000 / 517`。

## 已确认的当前环境现状

- Windows 已安装 ODBC 驱动：`Transwarp Inceptor ODBC Driver`
- 当前系统未配置星环 DSN
- 当前机器已安装 Java 8，可直接使用内置 JDBC JAR

## 维护建议

1. 日常连接星环时，优先保持当前 JDBC 方案。
2. 如果必须走 ODBC，请先在系统的 ODBC 数据源管理器中创建星环 DSN，再让程序使用 ODBC。
3. `drivers/transwarp/` 已被项目打包配置整体带入，无需单独再改星环 spec。
