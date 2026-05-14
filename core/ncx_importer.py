"""
ncx_importer.py
解析 Navicat 导出的 .ncx（XML）连接文件，转换为本工具内部连接格式。

Navicat .ncx 格式示例：
<Connections Ver="1.5">
  <Connection ConnectionName="..." ConnType="MYSQL"
              Host="..." Port="3306" UserName="..."
              Database="..." .../>
</Connections>

注意：Navicat 导出的 .ncx 不包含明文密码，导入后密码字段为空，需用户手动补充。
"""
import xml.etree.ElementTree as ET

# Navicat ConnType → 本工具 db_type 映射
_CONNTYPE_MAP = {
    "MYSQL":      "mysql",
    "POSTGRESQL": "postgresql",
    "PGSQL":      "postgresql",
    "SQLSERVER":  "sqlserver",
    "MSSQL":      "sqlserver",
    "ORACLE":     "oracle",
    "SQLITE":     None,          # 暂不支持
    "MONGODB":    None,          # 暂不支持
    "REDIS":      None,          # 暂不支持
    "MARIADB":    "mysql",       # MariaDB 用 MySQL 驱动
}

_DEFAULT_PORTS = {
    "mysql":      "3306",
    "postgresql": "5432",
    "sqlserver":  "1433",
    "oracle":     "1521",
}


def parse_ncx(filepath: str) -> tuple[list[dict], list[str]]:
    """
    解析 .ncx 文件，返回 (imported_list, skipped_list)。

    imported_list: list[dict] - 成功解析的连接信息列表，格式与 connection_store 一致
    skipped_list:  list[str]  - 因类型不支持而跳过的连接名称列表
    """
    tree = ET.parse(filepath)
    root = tree.getroot()

    imported = []
    skipped = []

    for conn in root.findall("Connection"):
        conn_name = conn.get("ConnectionName", "").strip()
        conn_type = (conn.get("ConnType") or "").upper()

        db_type = _CONNTYPE_MAP.get(conn_type)
        if db_type is None:
            skipped.append(f"{conn_name} (类型 {conn_type} 暂不支持)")
            continue

        host = conn.get("Host", "").strip()
        port = conn.get("Port", "").strip() or _DEFAULT_PORTS.get(db_type, "")
        user = conn.get("UserName", "").strip()

        # SQL Server 使用 Database 字段；其他类型 Navicat 不导出默认 db
        dbname = conn.get("Database", "").strip()

        info = {
            "name":       conn_name,
            "db_type":    db_type,
            "host":       host,
            "port":       port,
            "user":       user,
            "pwd":        "",        # 密码未明文导出
            "dbname":     dbname,
            "jar_path":   "",
            "is_spatial": False,
        }
        imported.append(info)

    return imported, skipped
