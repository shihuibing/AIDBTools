"""
connection.py
数据库连接核心模块。
支持：
  - 常规 SQLAlchemy 系列（MySQL/PG/MSSQL/Oracle/达梦/金仓/GaussDB 等）
  - 星环科技 ArgoDB / Inceptor
      Windows / Linux：优先 JDBC（quark-driver / inceptor-driver）
      若系统已配置星环 ODBC DSN，再回退 ODBC

"""
import os
import platform
import sys
import urllib.parse

from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL



from core.platform_utils import (
    MSSQL_URL_TEMPLATE as _MSSQL_DRIVER,
    get_app_base_dir,
    get_project_root_dir,
)
from core.argo_driver_manager import ArgoDriverManager, DriverInfo



# 保留向后兼容的别名
_IS_LINUX = sys.platform.startswith("linux")


# ─────────────────────────────────────────────────────────
# 星环 JayDeBeApi 伪引擎包装器
# 用于让星环连接复用 get_databases/get_tables/execute 等接口
# ─────────────────────────────────────────────────────────
class _ArgoCursor:
    """包装 DBAPI cursor，让调用方可以用 result.keys()/fetch*()/scalar()。"""
    def __init__(self, cursor, description, rows):
        self._description = description
        self._rows = list(rows or [])
        self._cursor = cursor
        self._index = 0

    def keys(self):
        if self._description:
            return [d[0] for d in self._description]
        return []

    def fetchall(self):
        if self._index <= 0:
            self._index = len(self._rows)
            return list(self._rows)
        remain = self._rows[self._index:]
        self._index = len(self._rows)
        return list(remain)

    def fetchone(self):
        if self._index < len(self._rows):
            row = self._rows[self._index]
            self._index += 1
            return row
        return None

    def scalar(self):
        row = self.fetchone()
        if row is None:
            return None
        return row[0] if len(row) > 0 else None

    def close(self):
        try:
            self._cursor.close()
        except Exception:
            pass

    @property
    def returns_rows(self):
        return self._description is not None and len(self._description) > 0



class _ArgoConnection:
    """包装 jaydebeapi connection，提供 execute / commit"""
    def __init__(self, conn):
        self._conn = conn

    def execute(self, stmt, params=None):
        cur = self._conn.cursor()
        sql = stmt if isinstance(stmt, str) else str(stmt)
        # 替换 SQLAlchemy :param 风格参数为 ? (JDBC 风格)
        if params:
            import re
            for k, v in params.items():
                sql = re.sub(r':' + k + r'\b', '?', sql)
            cur.execute(sql, list(params.values()))
        else:
            cur.execute(sql)
        try:
            rows = cur.fetchall()
            desc = cur.description
        except Exception:
            rows = []
            desc = None
        return _ArgoCursor(cur, desc, rows)

    def commit(self):
        try:
            self._conn.commit()
        except Exception:
            pass

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass


class _ArgoEngine:
    """模拟 SQLAlchemy engine 接口，内部用 jaydebeapi 连接"""
    def __init__(self, jdbc_url, driver_class, user, pwd, jar_path):
        self._jdbc_url = jdbc_url
        self._driver_class = driver_class
        self._user = user
        self._pwd = pwd
        self._jar_path = jar_path
        self._raw_conn = None
        self._connect()

    def _connect(self):
        java_ok, java_hint = ArgoDriverManager._check_java()
        if not java_ok:
            raise RuntimeError(f'缺少可用的 Java 11+ 运行环境：{java_hint}')

        try:
            import jaydebeapi
        except ModuleNotFoundError as exc:
            missing_name = getattr(exc, 'name', 'jaydebeapi') or 'jaydebeapi'
            raise RuntimeError(
                '缺少 JDBC 运行依赖：'
                f'{missing_name}。请在打包/运行环境安装 jaydebeapi 和 JPype1 后重试。'
            ) from exc

        self._raw_conn = jaydebeapi.connect(
            self._driver_class,
            self._jdbc_url,
            [self._user, self._pwd],
            self._jar_path,
        )



    def connect(self):
        # 检查连接是否还活着，断了就重连
        try:
            cur = self._raw_conn.cursor()
            cur.execute("SELECT 1")
        except Exception:
            self._connect()
        return _ArgoConnection(self._raw_conn)

    def dispose(self):
        try:
            self._raw_conn.close()
        except Exception:
            pass


class _ArgoPyodbcEngine:
    """
    模拟 SQLAlchemy engine 接口，内部用原生 pyodbc 连接星环 ODBC 驱动。
    SQLAlchemy 不存在 hive+pyodbc 方言，必须绕开直连。
    """
    def __init__(self, conn_str: str):
        self._conn_str = conn_str
        self._raw_conn = None
        self._connect()

    def _connect(self):
        import pyodbc
        self._raw_conn = pyodbc.connect(self._conn_str, autocommit=False)

    def connect(self):
        # 心跳检测，断线重连
        try:
            cur = self._raw_conn.cursor()
            cur.execute("SELECT 1")
            cur.close()
        except Exception:
            self._connect()
        return _ArgoConnection(self._raw_conn)

    def dispose(self):
        try:
            self._raw_conn.close()
        except Exception:
            pass


class _XuguPythonConnection:
    """包装官方 xgcondb 连接，暴露接近 SQLAlchemy 的 execute/commit 接口。"""
    def __init__(self, conn):
        self._conn = conn

    def execute(self, stmt, params=None):
        cur = self._conn.cursor()
        sql = stmt if isinstance(stmt, str) else str(stmt)
        if params is None:
            cur.execute(sql)
        else:
            cur.execute(sql, params)
        try:
            rows = cur.fetchall()
            desc = cur.description
        except Exception:
            rows = []
            desc = None
        return _ArgoCursor(cur, desc, rows)

    def commit(self):
        try:
            self._conn.commit()
        except Exception:
            pass

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass


class _XuguPythonEngine:
    """模拟 SQLAlchemy engine 接口，内部使用虚谷官方 xgcondb 驱动。"""
    def __init__(self, xgcondb_module, host, port, user, pwd, dbname):
        self._xgcondb = xgcondb_module
        self._host = str(host or "127.0.0.1").strip() or "127.0.0.1"
        self._port = str(port or "5138").strip() or "5138"
        self._user = user or ""
        self._pwd = pwd or ""
        self._dbname = (dbname or "").strip()
        self._raw_conn = None
        self._connect()

    def _connect(self):
        if not self._dbname:
            raise RuntimeError("虚谷连接必须指定数据库名，例如 SYSTEM。")
        self._raw_conn = self._xgcondb.connect(
            host=self._host,
            port=self._port,
            database=self._dbname,
            user=self._user,
            password=self._pwd,
            charset="UTF8",
        )

    def connect(self):
        try:
            cur = self._raw_conn.cursor()
            cur.execute("SELECT 1")
            cur.close()
        except Exception:
            self._connect()
        return _XuguPythonConnection(self._raw_conn)

    def dispose(self):
        try:
            self._raw_conn.close()
        except Exception:
            pass


# _XuguEngine 现改为官方 XuguDB-Python（xgcondb）驱动



# ─────────────────────────────────────────────────────────
# 主连接器
# ─────────────────────────────────────────────────────────

class DatabaseConnector:

    def __init__(self):
        self.engine = None
        self.db_type = None
        self.host = None
        self.port = None
        self.user = None
        self.pwd = None
        self.dbname = None        # 当前连接的库名
        self.jar_path = None      # 星环 JDBC jar / 特殊驱动显式路径（虚谷可留空自动探测）
        self.is_spatial = False   # 是否为空间数据库（UI 标识）
        self._argo_driver_info = None  # 缓存的 DriverInfo
        self._xugu_driver_dir = None   # 当前使用的虚谷 xgcondb 模块目录
        self._xugu_dll_handles = []    # Windows 下保留 DLL 搜索目录句柄



    DRIVER_MAP = {
        "mysql":      "mysql+pymysql://{}:{}@{}:{}/{}",
        "postgresql": "postgresql+psycopg2://{}:{}@{}:{}/{}",
        "sqlserver":  _MSSQL_DRIVER,
        "oracle":     "oracle+oracledb://{}:{}@{}:{}/{}",
        "xugu":       "xg://{}:{}@{}:{}/{}",
        "dameng":     "dm+dmPython://{}:{}@{}:{}/{}",

        "kingbase":   "kingbase+kingbase://{}:{}@{}:{}/{}",
        "gaussdb":    "postgresql+psycopg2://{}:{}@{}:{}/{}",
        "opengauss":  "postgresql+psycopg2://{}:{}@{}:{}/{}",
        "oceanbase":  "mysql+pymysql://{}:{}@{}:{}/{}",
        "polardb":    "mysql+pymysql://{}:{}@{}:{}/{}",
        "tdsql":      "mysql+pymysql://{}:{}@{}:{}/{}",
        "gbase":      "mysql+pymysql://{}:{}@{}:{}/{}",
        "tidb":       "mysql+pymysql://{}:{}@{}:{}/{}",
        "shentong":   "oracle+oracledb://{}:{}@{}:{}/{}",
    }

    TIMEOUT_ARGS = {
        "mysql":      {"connect_timeout": 5},
        "postgresql": {"connect_timeout": 5},
        "sqlserver":  {"timeout": 5},
        "oracle":     {},
        "xugu":       {},
        "gaussdb":    {"connect_timeout": 5},

        "opengauss":  {"connect_timeout": 5},
        "oceanbase":  {"connect_timeout": 5},
        "polardb":    {"connect_timeout": 5},
        "tdsql":      {"connect_timeout": 5},
        "gbase":      {"connect_timeout": 5},
        "tidb":       {"connect_timeout": 5},
    }

    # 获取当前连接下所有数据库/Schema 列表
    DATABASES_SQL = {
        "mysql":      "SHOW DATABASES",
        "postgresql": "SELECT datname FROM pg_database WHERE datistemplate=false ORDER BY datname",
        "sqlserver":  "SELECT name FROM sys.databases WHERE state=0 ORDER BY name",
        "oracle":     None,   # Oracle 不区分数据库，使用 PDB 或 schema
        "xugu":       None,   # 虚谷按当前连接数据库工作
        "gaussdb":    "SELECT datname FROM pg_database WHERE datistemplate=false ORDER BY datname",

        "opengauss":  "SELECT datname FROM pg_database WHERE datistemplate=false ORDER BY datname",
        "oceanbase":  "SHOW DATABASES",
        "polardb":    "SHOW DATABASES",
        "tdsql":      "SHOW DATABASES",
        "gbase":      "SHOW DATABASES",
        "tidb":       "SHOW DATABASES",
        # 星环：查所有 schema（Hive 兼容语法）
        "argodb":     "SHOW DATABASES",
        "inceptor":   "SHOW DATABASES",
    }

    # 获取指定数据库下所有表
    TABLES_SQL = {
        "mysql":      "SELECT table_name FROM information_schema.tables WHERE table_schema=:db AND table_type='BASE TABLE' ORDER BY table_name",
        "postgresql": "SELECT tablename FROM pg_catalog.pg_tables WHERE schemaname='public' ORDER BY tablename",
        "sqlserver":  "SELECT name FROM sys.tables ORDER BY name",
        "oracle":     "SELECT table_name FROM user_tables ORDER BY table_name",
        "xugu":       None,
        "gaussdb":    "SELECT tablename FROM pg_catalog.pg_tables WHERE schemaname='public' ORDER BY tablename",

        "opengauss":  "SELECT tablename FROM pg_catalog.pg_tables WHERE schemaname='public' ORDER BY tablename",
        "oceanbase":  "SELECT table_name FROM information_schema.tables WHERE table_schema=:db AND table_type='BASE TABLE' ORDER BY table_name",
        "polardb":    "SELECT table_name FROM information_schema.tables WHERE table_schema=:db AND table_type='BASE TABLE' ORDER BY table_name",
        "tdsql":      "SELECT table_name FROM information_schema.tables WHERE table_schema=:db AND table_type='BASE TABLE' ORDER BY table_name",
        "gbase":      "SHOW TABLES",
        "tidb":       "SELECT table_name FROM information_schema.tables WHERE table_schema=:db AND table_type='BASE TABLE' ORDER BY table_name",
        "shentong":   "SELECT table_name FROM user_tables ORDER BY table_name",
        # 星环：SHOW TABLES（连接后已切换到目标库）
        "argodb":     "SHOW TABLES",
        "inceptor":   "SHOW TABLES",
    }

    # Schema 信息（列信息）
    COLUMNS_SQL = {
        "mysql":      "SELECT table_name, column_name, column_type, column_comment FROM information_schema.columns WHERE table_schema=:db ORDER BY table_name, ordinal_position",
        "postgresql": "SELECT c.table_name, c.column_name, c.data_type, '' FROM information_schema.columns c WHERE c.table_schema='public' ORDER BY c.table_name, c.ordinal_position",
        "sqlserver":  "SELECT t.name, c.name, tp.name, '' FROM sys.tables t JOIN sys.columns c ON t.object_id=c.object_id JOIN sys.types tp ON c.user_type_id=tp.user_type_id ORDER BY t.name, c.column_id",
        "oracle":     "SELECT table_name, column_name, data_type, '' FROM user_tab_columns ORDER BY table_name, column_id",
        "xugu":       None,
        "gaussdb":    "SELECT c.table_name, c.column_name, c.data_type, '' FROM information_schema.columns c WHERE c.table_schema='public' ORDER BY c.table_name, c.ordinal_position",

        "opengauss":  "SELECT c.table_name, c.column_name, c.data_type, '' FROM information_schema.columns c WHERE c.table_schema='public' ORDER BY c.table_name, c.ordinal_position",
        "oceanbase":  "SELECT table_name, column_name, column_type, column_comment FROM information_schema.columns WHERE table_schema=:db ORDER BY table_name, ordinal_position",
        "polardb":    "SELECT table_name, column_name, column_type, column_comment FROM information_schema.columns WHERE table_schema=:db ORDER BY table_name, ordinal_position",
        "tdsql":      "SELECT table_name, column_name, column_type, column_comment FROM information_schema.columns WHERE table_schema=:db ORDER BY table_name, ordinal_position",
        "tidb":       "SELECT table_name, column_name, column_type, column_comment FROM information_schema.columns WHERE table_schema=:db ORDER BY table_name, ordinal_position",
        "gbase":      "SELECT table_name, column_name, column_type, '' FROM information_schema.columns WHERE table_schema=:db ORDER BY table_name, ordinal_position",
        "shentong":   "SELECT table_name, column_name, data_type, '' FROM user_tab_columns ORDER BY table_name, column_id",
        # 星环：用 information_schema（ArgoDB/Inceptor 均支持）
        "argodb":     "SELECT table_name, column_name, data_type, comment FROM information_schema.columns WHERE table_schema=:db ORDER BY table_name, ordinal_position",
        "inceptor":   "SELECT table_name, column_name, data_type, comment FROM information_schema.columns WHERE table_schema=:db ORDER BY table_name, ordinal_position",
    }

    # ── 星环类型常量 ──────────────────────────────────
    _ARGO_TYPES = ("argodb", "inceptor")
    _XUGU_DEFAULT_PORT = "5138"
    _XUGU_DEFAULT_DB = "SYSTEM"

    def _is_argo(self):
        return self.db_type in self._ARGO_TYPES

    _MSSQL_DRIVER_CANDIDATES = [
        "ODBC Driver 17 for SQL Server",
        "ODBC Driver 18 for SQL Server",
        "SQL Server Native Client 11.0",
        "SQL Server",
    ]

    def _list_odbc_drivers(self):
        try:
            import pyodbc
            return list(pyodbc.drivers())
        except Exception:
            return []

    @staticmethod
    def _normalize_odbc_driver_name(name: str) -> str:
        text = str(name or "")
        text = text.replace("{", " ").replace("}", " ").strip().lower()
        return " ".join(text.split())

    def _find_sqlserver_driver(self, installed):
        normalized_map = {
            self._normalize_odbc_driver_name(name): name
            for name in installed
            if str(name).strip()
        }

        for candidate in self._MSSQL_DRIVER_CANDIDATES:
            hit = normalized_map.get(self._normalize_odbc_driver_name(candidate))
            if hit:
                return hit

        for candidate in self._MSSQL_DRIVER_CANDIDATES:
            normalized_candidate = self._normalize_odbc_driver_name(candidate)
            for normalized_name, original_name in normalized_map.items():
                if normalized_candidate in normalized_name or normalized_name in normalized_candidate:
                    return original_name

        for name in installed:
            if "sql server" in self._normalize_odbc_driver_name(name):
                return name
        return ""

    @staticmethod
    def _clean_error_message(err_msg: str) -> str:
        marker = "(Background on this error at:"
        idx = err_msg.find(marker)
        if idx != -1:
            err_msg = err_msg[:idx]
        return err_msg.rstrip().rstrip("(").rstrip()

    def _pick_sqlserver_driver(self) -> str:
        installed = self._list_odbc_drivers()
        if not installed:
            raise RuntimeError("未检测到任何已注册的 ODBC 驱动")

        hit = self._find_sqlserver_driver(installed)
        if hit:
            return hit

        raise RuntimeError(
            "未检测到可用的 SQL Server ODBC 驱动。当前系统已注册："
            + "、".join(installed)
        )

    @staticmethod
    def _split_sqlserver_host_port(host: str, port: str):
        host_text = str(host or "").strip()
        port_text = str(port or "").strip()

        if host_text and not port_text and "," in host_text:
            maybe_host, maybe_port = host_text.rsplit(",", 1)
            if maybe_port.strip().isdigit():
                host_text = maybe_host.strip()
                port_text = maybe_port.strip()

        if (
            host_text
            and not port_text
            and host_text.count(":") == 1
            and "\\" not in host_text
        ):
            maybe_host, maybe_port = host_text.rsplit(":", 1)
            if maybe_port.strip().isdigit():
                host_text = maybe_host.strip()
                port_text = maybe_port.strip()

        return host_text, port_text

    def _build_sqlserver_server_value(self) -> str:
        host_text, port_text = self._split_sqlserver_host_port(self.host, self.port)
        if not host_text:
            return ""
        if port_text:
            return f"{host_text},{port_text}"
        return host_text

    def _build_sqlserver_odbc_connect_string(self, dbname):
        driver_name = self._pick_sqlserver_driver()
        server_value = self._build_sqlserver_server_value()
        database_name = (dbname or "").strip() or "master"

        parts = [f"DRIVER={{{driver_name}}}"]
        if server_value:
            parts.append(f"SERVER={server_value}")
        if database_name:
            parts.append(f"DATABASE={database_name}")
        if self.user:
            parts.append(f"UID={self.user}")
        parts.append(f"PWD={self.pwd or ''}")
        if self._normalize_odbc_driver_name(driver_name) == self._normalize_odbc_driver_name("ODBC Driver 18 for SQL Server"):
            parts.append("TrustServerCertificate=yes")

        return ";".join(parts) + ";", driver_name, server_value, database_name

    def _format_sqlserver_connect_error(self, err_msg: str):
        cleaned = self._clean_error_message(err_msg)
        lower_msg = cleaned.lower()
        if (
            "im002" in lower_msg
            or "未发现数据源名称" in cleaned
            or "data source name not found" in lower_msg
            or "未检测到任何已注册的 odbc 驱动" in lower_msg
            or "未检测到可用的 sql server odbc 驱动" in lower_msg
        ):
            installed = self._list_odbc_drivers()
            installed_text = "、".join(installed) if installed else "（未检测到任何已注册 ODBC 驱动）"
            matched_driver = self._find_sqlserver_driver(installed)
            if matched_driver:
                server_value = self._build_sqlserver_server_value()
                database_name = (self.dbname or "").strip() or "master"
                return (
                    "[FAIL] 连接失败：已检测到 SQL Server ODBC 驱动，但 ODBC 初始化仍返回 IM002。\n\n"
                    f"当前选用驱动：{matched_driver}\n"
                    f"当前目标服务器：{server_value or '（未填写）'}\n"
                    f"当前默认数据库：{database_name}\n"
                    f"当前系统已注册驱动：{installed_text}\n\n"
                    "这通常不是“没装驱动”，更可能是服务器写法或连接参数组合不兼容。\n"
                    "请优先检查：\n"
                    "• 主机是否填写为 IP / 主机名 / 主机\\实例名\n"
                    "• 如果主机里已经写了 host,port，端口框可留空\n"
                    "• 命名实例（如 .\\SQLEXPRESS）可先不填端口\n"
                    "• 默认数据库可先留空，由程序自动回退到 master\n"
                    "• 若服务器启用了加密，是否需要使用 Driver 18 并允许证书信任"
                )
            return (
                "[FAIL] 连接失败：未检测到可用的 SQL Server ODBC 驱动。\n\n"
                "请先安装以下驱动之一：\n"
                "• ODBC Driver 17 for SQL Server（推荐）\n"
                "• ODBC Driver 18 for SQL Server\n"
                "• SQL Server Native Client 11.0\n\n"
                f"当前系统已注册驱动：{installed_text}\n"
                "下载地址：https://learn.microsoft.com/zh-cn/sql/connect/odbc/download-odbc-driver-for-sql-server"
            )
        return None

    # ─────────────────────────────────────────────────
    # 连接建立
    # ─────────────────────────────────────────────────
    def connect(self, db_type, host, port, user, pwd, dbname,
                jar_path=None, is_spatial=False):
        """建立连接并测试，成功后缓存连接参数"""
        try:
            self.db_type = db_type
            self.host = host
            self.port = port
            self.user = user
            self.pwd = pwd
            self.dbname = dbname
            if db_type == "xugu":
                self.port = self._normalize_xugu_port(port)
                self.dbname = self._normalize_xugu_dbname(dbname)
            self.jar_path = jar_path or ""
            self.is_spatial = is_spatial
            self._argo_driver_info = None
            self._build_engine(self.dbname)
            # 测试连通
            with self.engine.connect() as conn:
                if self._is_argo() or self._is_xugu():
                    conn.execute("SELECT 1")
                else:
                    conn.execute(text("SELECT 1"))

            mode_desc = ""
            if self._is_argo() and self._argo_driver_info:
                mode_desc = f"（{self._argo_driver_info.description}）"
            elif self._is_xugu():
                mode_desc = "（官方 XuguDB-Python / xgcondb）"
            return True, f"[OK] 连接成功{mode_desc}"

        except Exception as e:
            err_msg = self._clean_error_message(str(e))
            if db_type == "sqlserver":
                pretty_msg = self._format_sqlserver_connect_error(err_msg)
                if pretty_msg:
                    return False, pretty_msg
            return False, f"[FAIL] 连接失败：{err_msg}"

    def _build_engine(self, dbname):
        """根据 dbname 重建 engine（用于切换库）"""
        if self.engine:
            try:
                self.engine.dispose()
            except Exception:
                pass

        if self._is_argo():
            self._build_argo_engine(dbname)
        elif self._is_xugu():
            self._build_xugu_engine(dbname)
        elif self.db_type == "sqlserver" and not _IS_LINUX:

            conn_str, driver_name, server_value, database_name = self._build_sqlserver_odbc_connect_string(dbname)

            self._sqlserver_driver_name = driver_name
            self._sqlserver_server_value = server_value
            self._sqlserver_database_name = database_name
            url = URL.create(
                "mssql+pyodbc",
                query={"odbc_connect": conn_str},
            )
            connect_args = self.TIMEOUT_ARGS.get(self.db_type, {})
            self.engine = create_engine(url, pool_pre_ping=True, connect_args=connect_args)
        else:
            pwd_enc = urllib.parse.quote_plus(self.pwd)
            url = self.DRIVER_MAP[self.db_type].format(
                self.user, pwd_enc, self.host, self.port, dbname
            )
            connect_args = self.TIMEOUT_ARGS.get(self.db_type, {})
            self.engine = create_engine(url, pool_pre_ping=True, connect_args=connect_args)

    @staticmethod
    def _quote_sqlserver_identifier(name: str) -> str:
        value = (name or "").strip().strip("[]")
        return f"[{value.replace(']', ']]')}]"

    def _sqlserver_db_ref(self, dbname=None) -> str:
        return self._quote_sqlserver_identifier(dbname or self.dbname or "master")

    def _resolve_sqlserver_table_ref(self, dbname, table_name: str) -> str:
        raw_name = (table_name or "").strip()
        if not raw_name:
            return ""
        # SQL Server 临时表（#开头）不能使用数据库/架构前缀
        if raw_name.startswith('#'):
            return self._quote_sqlserver_identifier(raw_name)
        db_ref = self._sqlserver_db_ref(dbname)
        parts = [part.strip().strip("[]") for part in raw_name.split(".") if part.strip()]

        if len(parts) >= 3:
            return ".".join(self._quote_sqlserver_identifier(part) for part in parts[-3:])

        if len(parts) == 2:
            schema_name, object_name = parts
            return f"{db_ref}.{self._quote_sqlserver_identifier(schema_name)}.{self._quote_sqlserver_identifier(object_name)}"

        object_name = parts[0]
        schema_name = "dbo"
        schema_sql = (
            f"SELECT TOP 1 s.name "
            f"FROM {db_ref}.sys.tables t "
            f"JOIN {db_ref}.sys.schemas s ON t.schema_id = s.schema_id "
            f"WHERE t.name = :table_name "
            f"ORDER BY CASE WHEN s.name = 'dbo' THEN 0 ELSE 1 END, s.name"
        )
        try:
            with self.engine.connect() as conn:
                detected_schema = conn.execute(text(schema_sql), {"table_name": object_name}).scalar()
                if detected_schema:
                    schema_name = detected_schema
        except Exception:
            pass

        return f"{db_ref}.{self._quote_sqlserver_identifier(schema_name)}.{self._quote_sqlserver_identifier(object_name)}"

    # 各星环 JAR 版本对应的优先驱动类（按新→旧顺序尝试）

    _ARGO_DRIVER_CANDIDATES = [
        "io.transwarp.jdbc.QuarkDriver",
        "io.transwarp.jdbc.InceptorDriver",
        "io.transwarp.hadoop.hive.jdbc.HiveDriver",
        "org.apache.hive.jdbc.HiveDriver",
    ]

    def _build_argo_engine(self, dbname):
        """
        构建星环引擎：
          默认优先 JDBC（和当前 UI 的 host/port/dbname 输入方式一致）
          若系统已显式配置星环 ODBC DSN，再尝试 ODBC

        """
        info = ArgoDriverManager.detect(jar_path=self.jar_path or "")
        self._argo_driver_info = info

        if info.mode == "odbc":
            try:
                self._build_argo_engine_odbc(dbname, info)
                return
            except Exception as odbc_exc:
                jdbc_info = ArgoDriverManager.detect_jdbc(jar_path=self.jar_path or "")
                if jdbc_info.mode == "jdbc":
                    self._build_argo_engine_jdbc(dbname, jdbc_info)
                    self._argo_driver_info = DriverInfo(
                        mode="jdbc",
                        param=jdbc_info.param,
                        driver_class=jdbc_info.driver_class,
                        description=f"{jdbc_info.description}（ODBC 失败后自动回退）",
                        odbc_installer=jdbc_info.odbc_installer,
                        jdbc_jar=jdbc_info.jdbc_jar,
                        extra={"odbc_error": str(odbc_exc)},
                    )
                    return
                fallback_hint = jdbc_info.description if jdbc_info.description else "未检测到额外可用说明"
                raise RuntimeError(
                    f"星环 ODBC 连接失败：{odbc_exc}\nJDBC 回退也不可用：{fallback_hint}"
                ) from odbc_exc

        elif info.mode == "jdbc":
            self._build_argo_engine_jdbc(dbname, info)
        else:
            # 没有任何驱动：给出安装提示后抛异常
            installer = info.odbc_installer
            hint = (
                f"\n请安装星环 ODBC 驱动：{installer}"
                if installer else
                "\n请将 quark-driver-*.jar 放入 drivers/transwarp/jdbc/ 目录，或在连接配置中指定 JAR 路径。"
            )
            raise RuntimeError(f"未找到可用的星环驱动（JDBC/ODBC）。{hint}")


    def _build_argo_engine_jdbc(self, dbname, info):
        """JDBC 模式（jaydebeapi）"""
        jdbc_url = ArgoDriverManager.build_jdbc_url(self.host, self.port, dbname)
        self.engine = _ArgoEngine(
            jdbc_url=jdbc_url,
            driver_class=info.driver_class,
            user=self.user,
            pwd=self.pwd,
            jar_path=info.jdbc_jar or None,
        )

    def _build_argo_engine_odbc(self, dbname, info):
        """ODBC 模式：优先复用系统已配置的星环 DSN，再用 pyodbc 直连。"""
        conn_str = ArgoDriverManager.build_odbc_conn_str(
            driver_name=info.extra.get("driver_name", info.param),
            host=self.host,
            port=self.port,
            user=self.user,
            pwd=self.pwd,
            dbname=dbname,
            dsn_name=info.extra.get("dsn_name", ""),
        )
        self.engine = _ArgoPyodbcEngine(conn_str)


    def _detect_argo_driver(self, jar_path: str) -> str:
        """兼容旧调用：委托给 ArgoDriverManager"""
        info = ArgoDriverManager.detect(jar_path=jar_path)
        return info.driver_class or self._ARGO_DRIVER_CANDIDATES[-1]

    def _is_xugu(self) -> bool:
        return self.db_type == "xugu"

    def _normalize_xugu_dbname(self, dbname=None) -> str:
        raw_value = self.dbname if dbname is None else dbname
        return (raw_value or "").strip()

    def _normalize_xugu_port(self, port=None) -> str:
        raw_value = self.port if port is None else port
        return str(raw_value or "").strip() or self._XUGU_DEFAULT_PORT

    def _get_xugu_search_roots(self):
        roots = []
        seen = set()
        for base in [
            get_app_base_dir(),
            os.path.dirname(sys.executable) if getattr(sys, "frozen", False) else "",
            os.getcwd(),
            get_project_root_dir(),
        ]:
            if not base:
                continue
            abs_base = os.path.abspath(base)
            norm_base = os.path.normcase(abs_base)
            if norm_base not in seen:
                seen.add(norm_base)
                roots.append(abs_base)
        return roots

    def _build_xugu_candidate_paths(self, rel_paths):
        candidates = []
        seen = set()
        for base in self._get_xugu_search_roots():
            for rel_path in rel_paths:
                parent = os.path.abspath(os.path.join(base, rel_path))
                norm_parent = os.path.normcase(parent)
                if norm_parent not in seen:
                    seen.add(norm_parent)
                    candidates.append(parent)
        return candidates

    def _get_xugu_platform_tags(self):
        system_name = platform.system().lower()
        machine = platform.machine().lower()
        if system_name == "windows":
            return ["windows-amd64"]
        if system_name == "linux":
            if "aarch64" in machine or "arm64" in machine:
                return ["linux-aarch64"]
            return ["linux-x86_64"]
        if system_name == "darwin":
            if "arm64" in machine or "aarch64" in machine:
                return ["macos-arm64"]
            return ["macos-x86_64"]
        return []

    @staticmethod
    def _normalize_xugu_python_parent(path):
        if not path:
            return None
        abs_path = os.path.abspath(path)
        if os.path.isfile(abs_path):
            abs_path = os.path.dirname(abs_path)
        if os.path.basename(abs_path).lower() == "xgcondb":
            abs_path = os.path.dirname(abs_path)
        module_dir = os.path.join(abs_path, "xgcondb")
        if os.path.isfile(os.path.join(module_dir, "__init__.py")):
            return abs_path
        return None

    def _get_xugu_python_driver_parents(self):
        candidates = []
        seen = set()

        def add_candidate(path):
            parent = self._normalize_xugu_python_parent(path)
            if not parent:
                return
            norm_parent = os.path.normcase(parent)
            if norm_parent not in seen:
                seen.add(norm_parent)
                candidates.append(parent)

        if self.jar_path:
            add_candidate(self.jar_path)

        rel_paths = [
            os.path.join("XuguDB", "Driver", "python"),
            os.path.join("xugu", "XuguDB", "Driver", "python"),
        ]
        for tag in self._get_xugu_platform_tags():
            rel_paths.append(
                os.path.join("drivers", "xugu", "python", tag, "XuguDB", "Driver", "python")
            )

        for candidate in self._build_xugu_candidate_paths(rel_paths):
            add_candidate(candidate)

        return candidates

    @staticmethod
    def _purge_xugu_modules():
        for mod_name in list(sys.modules.keys()):
            if mod_name == "xgcondb" or mod_name.startswith("xgcondb."):
                sys.modules.pop(mod_name, None)

    def _prepare_xugu_python_runtime(self, driver_parent):
        module_dir = os.path.join(driver_parent, "xgcondb")
        current_path = os.environ.get("PATH", "")
        path_parts = current_path.split(os.pathsep) if current_path else []
        for candidate in [module_dir, driver_parent]:
            if not os.path.isdir(candidate):
                continue
            if not any(os.path.normcase(part) == os.path.normcase(candidate) for part in path_parts):
                os.environ["PATH"] = candidate + os.pathsep + os.environ.get("PATH", "")
                path_parts.insert(0, candidate)
            if os.name == "nt" and hasattr(os, "add_dll_directory"):
                try:
                    existing = getattr(self, "_xugu_dll_handles", [])
                    if not any(getattr(handle, "path", None) == candidate for handle in existing):
                        self._xugu_dll_handles.append(os.add_dll_directory(candidate))
                except (OSError, AttributeError):
                    pass
        return module_dir

    def _import_xugu_python_driver(self):
        if sys.version_info.major != 3 or sys.version_info.minor > 11:
            current_ver = f"{sys.version_info.major}.{sys.version_info.minor}"
            raise RuntimeError(
                f"当前运行时 Python {current_ver} 不受虚谷官方 xgcondb 支持，请改用 Python 3.11 运行或重新打包。"
            )

        import importlib

        last_error = None
        search_dirs = self._get_xugu_python_driver_parents()

        for driver_parent in search_dirs:
            module_dir = self._prepare_xugu_python_runtime(driver_parent)
            if not os.path.isdir(module_dir):
                continue

            normalized_parent = os.path.normcase(driver_parent)
            if not any(os.path.normcase(os.path.abspath(path or os.getcwd())) == normalized_parent for path in sys.path):
                sys.path.insert(0, driver_parent)

            existing = sys.modules.get("xgcondb")
            existing_file = os.path.abspath(getattr(existing, "__file__", "") or "") if existing else ""
            if existing_file and not os.path.normcase(existing_file).startswith(os.path.normcase(module_dir)):
                self._purge_xugu_modules()

            importlib.invalidate_caches()
            try:
                xgcondb_module = importlib.import_module("xgcondb")
                self._xugu_driver_dir = module_dir
                return xgcondb_module
            except Exception as exc:
                self._purge_xugu_modules()
                last_error = exc
                continue

        checked = "；".join(search_dirs)
        if search_dirs:
            raise RuntimeError(
                "虚谷官方 xgcondb 驱动加载失败，请确认 drivers/xugu/python/.../xgcondb 目录完整，且运行时已切到 Python 3.11。"
                + (f" 已检查：{checked}" if checked else "")
            ) from last_error
        raise RuntimeError("未检测到可用的虚谷 xgcondb 驱动目录，请确认已集成官方 XuguDB-Python 包。")

    def _build_xugu_engine(self, dbname):
        xgcondb_module = self._import_xugu_python_driver()
        target_db = self._normalize_xugu_dbname(dbname)
        self.dbname = target_db
        self.port = self._normalize_xugu_port(self.port)
        self.engine = _XuguPythonEngine(
            xgcondb_module=xgcondb_module,
            host=self.host,
            port=self.port,
            user=self.user or "",
            pwd=self.pwd or "",
            dbname=target_db,
        )



    def _get_xugu_schema_name(self):
        return (self.user or "").strip().upper() or None

    @staticmethod
    def _quote_xugu_identifier(name: str) -> str:
        value = (name or "").strip().strip('"')
        return f'"{value.replace(chr(34), chr(34) * 2)}"'

    def _resolve_xugu_table_ref(self, table_name: str) -> str:
        raw_name = (table_name or "").strip()
        if not raw_name:
            return ""
        parts = [part.strip().strip('"') for part in raw_name.split(".") if part.strip()]
        return ".".join(self._quote_xugu_identifier(part) for part in parts)

    def _execute_xugu_sql(self, sql):
        """执行单条虚谷查询，返回 fetchall 结果；失败返回 []。"""
        try:
            with self.engine.connect() as conn:
                result = conn.execute(sql)
                return result.fetchall()
        except Exception:
            return []

    def _execute_xugu_candidates(self, candidates):
        """按优先级依次尝试候选 SQL，第一条成功即返回；全败则 raise 最后一个异常。"""
        last_error = None
        for sql in candidates:
            try:
                with self.engine.connect() as conn:
                    result = conn.execute(sql)
                    return result.fetchall()
            except Exception as exc:
                last_error = exc
                continue
        if last_error:
            raise last_error
        return []

    def _get_xugu_tables(self):
        rows = self._execute_xugu_candidates([
            "SELECT table_name FROM user_tables ORDER BY table_name",
            "SELECT object_name FROM user_objects WHERE object_type='TABLE' ORDER BY object_name",
        ])
        return sorted({str(row[0]) for row in rows if row and row[0]})

    def _get_xugu_views(self):
        rows = self._execute_xugu_candidates([
            "SELECT view_name FROM user_views ORDER BY view_name",
            "SELECT object_name FROM user_objects WHERE object_type='VIEW' ORDER BY object_name",
        ])
        return sorted({str(row[0]) for row in rows if row and row[0]})

    def _get_xugu_columns(self):
        return self._execute_xugu_candidates([
            "SELECT t.table_name, c.col_name, c.type_name, c.comments FROM all_columns c JOIN all_tables t ON c.table_id = t.table_id ORDER BY t.table_name, c.col_no",
            "SELECT t.table_name, c.col_name, c.type_name, c.comments FROM dba_columns c JOIN dba_tables t ON c.table_id = t.table_id ORDER BY t.table_name, c.col_no",
            "SELECT c.table_name, c.column_name, c.data_type, '' FROM user_tab_columns c ORDER BY c.table_name, c.column_id",
            "SELECT table_name, column_name, data_type, '' FROM user_tab_columns ORDER BY table_name, column_id",
        ])


    def _get_xugu_functions(self):
        rows = self._execute_xugu_candidates([
            "SELECT object_name FROM user_objects WHERE object_type='FUNCTION' ORDER BY object_name",
            "SELECT ROUTINE_NAME FROM INFORMATION_SCHEMA.ROUTINES WHERE ROUTINE_TYPE='FUNCTION' ORDER BY ROUTINE_NAME",
        ])
        return sorted({str(row[0]) for row in rows if row and row[0]})

    def _get_xugu_table_data(self, table_name, limit_num):
        table_ref = self._resolve_xugu_table_ref(table_name)
        if not table_ref:
            return [], []
        candidates = [
            f"SELECT * FROM {table_ref} WHERE ROWNUM <= {limit_num}",
            f"SELECT * FROM {table_ref} LIMIT {limit_num}",
        ]
        last_error = None
        for sql in candidates:
            try:
                with self.engine.connect() as conn:
                    result = conn.execute(sql)
                    return list(result.keys()), result.fetchall()
            except Exception as exc:
                last_error = exc
                continue
        if last_error:
            raise last_error
        return [], []


    # ─────────────────────────────────────────────────
    # 数据库列表

    # ─────────────────────────────────────────────────
    def get_databases(self):
        """获取当前服务器下的所有数据库列表"""
        try:
            if self._is_xugu():
                return [self.dbname] if self.dbname else []
            sql = self.DATABASES_SQL.get(self.db_type)
            if sql is None:
                # Oracle 等返回当前 schema 名作为唯一项
                return [self.dbname]
            with self.engine.connect() as conn:
                res = conn.execute(text(sql) if not self._is_argo() else sql)
                return [row[0] for row in res.fetchall()]
        except Exception:
            return [self.dbname]


    # ─────────────────────────────────────────────────
    # 表列表
    # ─────────────────────────────────────────────────
    def get_tables(self, dbname=None):
        """获取指定数据库下的所有表，需要时切换连接"""
        try:
            target_db = dbname or self.dbname

            if self._is_argo():
                # 星环通过 USE db 切换，然后 SHOW TABLES
                if target_db and target_db != self.dbname:
                    with self.engine.connect() as conn:
                        conn.execute(f"USE {target_db}")
                    self.dbname = target_db
                with self.engine.connect() as conn:
                    res = conn.execute("SHOW TABLES")
                    # SHOW TABLES 返回单列
                    return [row[0] for row in res.fetchall()]

            if self._is_xugu():
                return self._get_xugu_tables()

            if self.db_type == "sqlserver":
                db_ref = self._sqlserver_db_ref(target_db)
                sql = f"SELECT name FROM {db_ref}.sys.tables ORDER BY name"
                with self.engine.connect() as conn:
                    res = conn.execute(text(sql))
                    return [row[0] for row in res.fetchall()]

            # MySQL / PostgreSQL 系列跨库时需要重建连接
            if self.db_type in ("mysql", "postgresql", "gaussdb", "opengauss", "kingbase", "oceanbase", "polardb", "tdsql", "tidb") and target_db != self.dbname:
                self._build_engine(target_db)
                self.dbname = target_db

            sql_tpl = self.TABLES_SQL.get(self.db_type, "SHOW TABLES")

            with self.engine.connect() as conn:
                if ":db" in sql_tpl:
                    res = conn.execute(text(sql_tpl), {"db": target_db})
                else:
                    res = conn.execute(text(sql_tpl))
                return [row[0] for row in res.fetchall()]
        except Exception:
            return []



    # 各数据库获取视图列表 SQL
    VIEWS_SQL = {
        "mysql":      "SELECT table_name FROM information_schema.views WHERE table_schema=:db ORDER BY table_name",
        "postgresql": "SELECT viewname FROM pg_catalog.pg_views WHERE schemaname='public' ORDER BY viewname",
        "sqlserver":  "SELECT name FROM sys.views ORDER BY name",
        "oracle":     "SELECT view_name FROM user_views ORDER BY view_name",
        "xugu":       None,
        "gaussdb":    "SELECT viewname FROM pg_catalog.pg_views WHERE schemaname='public' ORDER BY viewname",

        "opengauss":  "SELECT viewname FROM pg_catalog.pg_views WHERE schemaname='public' ORDER BY viewname",
        "oceanbase":  "SELECT table_name FROM information_schema.views WHERE table_schema=:db ORDER BY table_name",
        "polardb":    "SELECT table_name FROM information_schema.views WHERE table_schema=:db ORDER BY table_name",
        "tdsql":      "SELECT table_name FROM information_schema.views WHERE table_schema=:db ORDER BY table_name",
        "tidb":       "SELECT table_name FROM information_schema.views WHERE table_schema=:db ORDER BY table_name",
        "gbase":      "SELECT table_name FROM information_schema.views WHERE table_schema=:db ORDER BY table_name",
        "shentong":   "SELECT view_name FROM user_views ORDER BY view_name",
        "dameng":     "SELECT view_name FROM user_views ORDER BY view_name",
        "kingbase":   "SELECT viewname FROM pg_catalog.pg_views WHERE schemaname='public' ORDER BY viewname",
    }

    # 各数据库获取函数列表 SQL
    FUNCTIONS_SQL = {
        "mysql":      "SELECT routine_name FROM information_schema.routines WHERE routine_schema=:db AND routine_type='FUNCTION' ORDER BY routine_name",
        "postgresql": "SELECT proname FROM pg_proc p JOIN pg_namespace n ON p.pronamespace=n.oid WHERE n.nspname='public' ORDER BY proname",
        "sqlserver":  "SELECT name FROM sys.objects WHERE type IN ('FN','IF','TF') ORDER BY name",
        "oracle":     "SELECT object_name FROM user_objects WHERE object_type='FUNCTION' ORDER BY object_name",
        "xugu":       None,
        "gaussdb":    "SELECT proname FROM pg_proc p JOIN pg_namespace n ON p.pronamespace=n.oid WHERE n.nspname='public' ORDER BY proname",

        "opengauss":  "SELECT proname FROM pg_proc p JOIN pg_namespace n ON p.pronamespace=n.oid WHERE n.nspname='public' ORDER BY proname",
        "oceanbase":  "SELECT routine_name FROM information_schema.routines WHERE routine_schema=:db AND routine_type='FUNCTION' ORDER BY routine_name",
        "polardb":    "SELECT routine_name FROM information_schema.routines WHERE routine_schema=:db AND routine_type='FUNCTION' ORDER BY routine_name",
        "tdsql":      "SELECT routine_name FROM information_schema.routines WHERE routine_schema=:db AND routine_type='FUNCTION' ORDER BY routine_name",
        "tidb":       "SELECT routine_name FROM information_schema.routines WHERE routine_schema=:db AND routine_type='FUNCTION' ORDER BY routine_name",
        "kingbase":   "SELECT proname FROM pg_proc p JOIN pg_namespace n ON p.pronamespace=n.oid WHERE n.nspname='public' ORDER BY proname",
    }

    def get_views(self, dbname=None):
        """获取指定数据库下的所有视图"""
        try:
            target_db = dbname or self.dbname
            if self._is_xugu():
                return self._get_xugu_views()
            if self.db_type == "sqlserver":
                db_ref = self._sqlserver_db_ref(target_db)
                sql = f"SELECT name FROM {db_ref}.sys.views ORDER BY name"
                with self.engine.connect() as conn:
                    res = conn.execute(text(sql))
                    return [row[0] for row in res.fetchall()]
            if self.db_type in ("mysql", "postgresql", "gaussdb", "opengauss", "kingbase", "oceanbase", "polardb", "tdsql", "tidb") and target_db != self.dbname:
                self._build_engine(target_db)
                self.dbname = target_db
            sql_tpl = self.VIEWS_SQL.get(self.db_type)
            if not sql_tpl:
                return []
            with self.engine.connect() as conn:
                if ":db" in sql_tpl:
                    res = conn.execute(text(sql_tpl), {"db": target_db})
                else:
                    res = conn.execute(text(sql_tpl))
                return [row[0] for row in res.fetchall()]
        except Exception:
            return []



    def get_functions(self, dbname=None):
        """获取指定数据库下的所有函数"""
        try:
            target_db = dbname or self.dbname
            if self._is_xugu():
                return self._get_xugu_functions()
            if self.db_type == "sqlserver":
                db_ref = self._sqlserver_db_ref(target_db)
                sql = f"SELECT name FROM {db_ref}.sys.objects WHERE type IN ('FN','IF','TF') ORDER BY name"
                with self.engine.connect() as conn:
                    res = conn.execute(text(sql))
                    return [row[0] for row in res.fetchall()]
            if self.db_type in ("mysql", "postgresql", "gaussdb", "opengauss", "kingbase", "oceanbase", "polardb", "tdsql", "tidb") and target_db != self.dbname:
                self._build_engine(target_db)
                self.dbname = target_db
            sql_tpl = self.FUNCTIONS_SQL.get(self.db_type)
            if not sql_tpl:
                return []
            with self.engine.connect() as conn:
                if ":db" in sql_tpl:
                    res = conn.execute(text(sql_tpl), {"db": target_db})
                else:
                    res = conn.execute(text(sql_tpl))
                return [row[0] for row in res.fetchall()]
        except Exception:
            return []



    # 各数据库获取索引列表 SQL
    INDEXES_SQL = {
        "mysql":      "SELECT index_name FROM information_schema.statistics WHERE table_schema=:db ORDER BY index_name",
        "postgresql": "SELECT indexname FROM pg_indexes WHERE schemaname='public' ORDER BY indexname",
        "sqlserver":  "SELECT name FROM sys.indexes WHERE type > 0 AND is_primary_key=0 AND is_unique_constraint=0 ORDER BY name",
        "oracle":     "SELECT index_name FROM user_indexes ORDER BY index_name",
        "xugu":       None,
        "gaussdb":    "SELECT indexname FROM pg_indexes WHERE schemaname='public' ORDER BY indexname",
        "opengauss":  "SELECT indexname FROM pg_indexes WHERE schemaname='public' ORDER BY indexname",
        "oceanbase":  "SELECT index_name FROM information_schema.statistics WHERE table_schema=:db ORDER BY index_name",
        "polardb":    "SELECT index_name FROM information_schema.statistics WHERE table_schema=:db ORDER BY index_name",
        "tdsql":      "SELECT index_name FROM information_schema.statistics WHERE table_schema=:db ORDER BY index_name",
        "tidb":       "SELECT index_name FROM information_schema.statistics WHERE table_schema=:db ORDER BY index_name",
        "kingbase":   "SELECT indexname FROM pg_indexes WHERE schemaname='public' ORDER BY indexname",
    }

    # 各数据库获取存储过程列表 SQL
    PROCEDURES_SQL = {
        "mysql":      "SELECT routine_name FROM information_schema.routines WHERE routine_schema=:db AND routine_type='PROCEDURE' ORDER BY routine_name",
        "postgresql": "SELECT proname FROM pg_proc p JOIN pg_namespace n ON p.pronamespace=n.oid WHERE n.nspname='public' AND pg_proc_is_visible(p.oid) ORDER BY proname",
        "sqlserver":  "SELECT name FROM sys.objects WHERE type='P' ORDER BY name",
        "oracle":     "SELECT object_name FROM user_objects WHERE object_type='PROCEDURE' ORDER BY object_name",
        "xugu":       None,
        "gaussdb":    "SELECT proname FROM pg_proc p JOIN pg_namespace n ON p.pronamespace=n.oid WHERE n.nspname='public' AND pg_proc_is_visible(p.oid) ORDER BY proname",
        "opengauss":  "SELECT proname FROM pg_proc p JOIN pg_namespace n ON p.pronamespace=n.oid WHERE n.nspname='public' AND pg_proc_is_visible(p.oid) ORDER BY proname",
        "oceanbase":  "SELECT routine_name FROM information_schema.routines WHERE routine_schema=:db AND routine_type='PROCEDURE' ORDER BY routine_name",
        "polardb":    "SELECT routine_name FROM information_schema.routines WHERE routine_schema=:db AND routine_type='PROCEDURE' ORDER BY routine_name",
        "tdsql":      "SELECT routine_name FROM information_schema.routines WHERE routine_schema=:db AND routine_type='PROCEDURE' ORDER BY routine_name",
        "tidb":       "SELECT routine_name FROM information_schema.routines WHERE routine_schema=:db AND routine_type='PROCEDURE' ORDER BY routine_name",
        "kingbase":   "SELECT proname FROM pg_proc p JOIN pg_namespace n ON p.pronamespace=n.oid WHERE n.nspname='public' AND pg_proc_is_visible(p.oid) ORDER BY proname",
    }

    def get_indexes(self, dbname=None):
        """获取指定数据库下的所有索引"""
        try:
            target_db = dbname or self.dbname
            if self.db_type == "sqlserver":
                db_ref = self._sqlserver_db_ref(target_db)
                sql = f"SELECT name FROM {db_ref}.sys.indexes WHERE type > 0 AND is_primary_key=0 AND is_unique_constraint=0 ORDER BY name"
                with self.engine.connect() as conn:
                    res = conn.execute(text(sql))
                    return [row[0] for row in res.fetchall()]
            if self.db_type in ("mysql", "postgresql", "gaussdb", "opengauss", "kingbase", "oceanbase", "polardb", "tdsql", "tidb") and target_db != self.dbname:
                self._build_engine(target_db)
                self.dbname = target_db
            sql_tpl = self.INDEXES_SQL.get(self.db_type)
            if not sql_tpl:
                return []
            with self.engine.connect() as conn:
                if ":db" in sql_tpl:
                    res = conn.execute(text(sql_tpl), {"db": target_db})
                else:
                    res = conn.execute(text(sql_tpl))
                return [row[0] for row in res.fetchall()]
        except Exception:
            return []

    def get_procedures(self, dbname=None):
        """获取指定数据库下的所有存储过程"""
        try:
            target_db = dbname or self.dbname
            if self.db_type == "sqlserver":
                db_ref = self._sqlserver_db_ref(target_db)
                sql = f"SELECT name FROM {db_ref}.sys.objects WHERE type='P' ORDER BY name"
                with self.engine.connect() as conn:
                    res = conn.execute(text(sql))
                    return [row[0] for row in res.fetchall()]
            if self.db_type in ("mysql", "postgresql", "gaussdb", "opengauss", "kingbase", "oceanbase", "polardb", "tdsql", "tidb") and target_db != self.dbname:
                self._build_engine(target_db)
                self.dbname = target_db
            sql_tpl = self.PROCEDURES_SQL.get(self.db_type)
            if not sql_tpl:
                return []
            with self.engine.connect() as conn:
                if ":db" in sql_tpl:
                    res = conn.execute(text(sql_tpl), {"db": target_db})
                else:
                    res = conn.execute(text(sql_tpl))
                return [row[0] for row in res.fetchall()]
        except Exception:
            return []



    # ─────────────────────────────────────────────────
    # 表数据
    # ─────────────────────────────────────────────────
    def get_table_data(self, table_name, dbname=None, limit=200):
        """查询表数据，返回 (columns, rows)"""
        try:
            target_db = dbname or self.dbname
            try:
                limit_num = max(1, int(limit))
            except Exception:
                limit_num = 200

            if self._is_argo():
                if target_db and target_db != self.dbname:
                    with self.engine.connect() as conn:
                        conn.execute(f"USE {target_db}")
                    self.dbname = target_db
                sql = f"SELECT * FROM `{table_name}` LIMIT {limit_num}"
                with self.engine.connect() as conn:
                    result = conn.execute(sql)
                    cols = result.keys()
                    rows = result.fetchall()
                    return list(cols), list(rows)

            if self._is_xugu():
                return self._get_xugu_table_data(table_name, limit_num)

            # SQL Server 临时表特殊处理：不切换数据库，直接使用当前连接
            is_temp_table = self.db_type == "sqlserver" and str(table_name or "").strip().startswith('#')

            if not is_temp_table and self.db_type in ("mysql", "postgresql", "gaussdb", "opengauss", "kingbase", "oceanbase", "polardb", "tdsql", "tidb") and target_db != self.dbname:
                self._build_engine(target_db)
                self.dbname = target_db

            # 根据数据库类型选择 LIMIT 语法
            if self.db_type in ("oracle", "shentong"):
                sql = f"SELECT * FROM {table_name} WHERE ROWNUM <= {limit_num}"
            elif self.db_type == "sqlserver":
                table_ref = self._resolve_sqlserver_table_ref(target_db, table_name)
                sql = f"SELECT TOP {limit_num} * FROM {table_ref}"
            else:
                sql = f"SELECT * FROM `{table_name}` LIMIT {limit_num}" if self.db_type in (
                    "mysql", "oceanbase", "polardb", "tdsql", "tidb", "gbase"
                ) else f'SELECT * FROM "{table_name}" LIMIT {limit_num}'

            with self.engine.connect() as conn:
                result = conn.execute(text(sql))
                cols = list(result.keys())
                rows = result.fetchall()
                return cols, rows
        except Exception as e:
            raise e


    # ─────────────────────────────────────────────────
    # Schema（AI 上下文）
    # ─────────────────────────────────────────────────
    def get_schema_rows(self, dbname=None):
        """获取当前库的列结构明细，返回 (table, column, type, comment) 列表。"""
        target_db = dbname or self.dbname

        if self._is_argo():
            return self._get_schema_rows_argo(target_db)

        if self._is_xugu():
            return self._get_xugu_columns()

        if self.db_type == "sqlserver":
            db_ref = self._sqlserver_db_ref(target_db)
            sql = (
                "SELECT t.name, c.name, tp.name, '' "
                f"FROM {db_ref}.sys.tables t "
                f"JOIN {db_ref}.sys.columns c ON t.object_id = c.object_id "
                f"JOIN {db_ref}.sys.types tp ON c.user_type_id = tp.user_type_id "
                "ORDER BY t.name, c.column_id"
            )
            with self.engine.connect() as conn:
                res = conn.execute(text(sql))
                return res.fetchall()

        if self.db_type in ("mysql", "postgresql", "gaussdb", "opengauss", "kingbase", "oceanbase", "polardb", "tdsql", "tidb") and target_db != self.dbname:
            self._build_engine(target_db)
            self.dbname = target_db

        sql_tpl = self.COLUMNS_SQL.get(self.db_type)

        if not sql_tpl:
            return []

        with self.engine.connect() as conn:
            if ":db" in sql_tpl:
                res = conn.execute(text(sql_tpl), {"db": target_db})
            else:
                res = conn.execute(text(sql_tpl))
            return res.fetchall()


    def get_schema(self, dbname=None, max_tables=60) -> str:
        """
        获取当前库的完整表结构，返回适合注入给 AI 的文本格式。
        星环空间数据库会在开头附加空间数据库说明。
        """
        try:
            target_db = dbname or self.dbname

            if self._is_argo():
                return self._get_schema_argo(target_db, max_tables)

            rows = self.get_schema_rows(target_db)
            return self._format_schema(rows, max_tables)
        except Exception:
            return ""


    def _get_schema_rows_argo(self, target_db, max_tables=60):
        """星环专用 schema 行获取：先 USE db，再查 information_schema，失败时降级到 DESCRIBE。"""
        try:
            with self.engine.connect() as conn:
                if target_db and target_db != self.dbname:
                    conn.execute(f"USE {target_db}")
                    self.dbname = target_db
                try:
                    sql = (
                        f"SELECT table_name, column_name, data_type, '' "
                        f"FROM information_schema.columns "
                        f"WHERE table_schema='{target_db}' "
                        f"ORDER BY table_name, ordinal_position"
                    )
                    res = conn.execute(sql)
                    return res.fetchall()
                except Exception:
                    rows = []
                    res2 = conn.execute("SHOW TABLES")
                    tables = [r[0] for r in res2.fetchall()]
                    for tbl in tables[:max_tables]:
                        try:
                            r3 = conn.execute(f"DESCRIBE {tbl}")
                            for col_row in r3.fetchall():
                                col_name = col_row[0]
                                col_type = col_row[1] if len(col_row) > 1 else ""
                                rows.append((tbl, col_name, col_type, ""))
                        except Exception:
                            pass
                    return rows
        except Exception:
            return []

    def _get_schema_argo(self, target_db, max_tables) -> str:
        """星环专用 schema 获取：先 USE db，再查 information_schema"""
        try:
            rows = self._get_schema_rows_argo(target_db, max_tables=max_tables)
            result = self._format_schema(rows, max_tables)

            # 空间数据库额外提示
            if self.is_spatial and result:
                spatial_hint = (
                    "【注：当前为星环空间数据库（ArgoDB GIS），"
                    "支持 ST_GeomFromText / ST_Distance / ST_Intersects / "
                    "ST_Contains / ST_Buffer 等 OGC 标准空间函数。"
                    "空间列类型为 GEOMETRY / POINT / LINESTRING / POLYGON 等。】\n\n"
                )
                return spatial_hint + result
            return result
        except Exception:
            return ""


    @staticmethod
    def _format_schema(rows, max_tables) -> str:
        """将 (table, col, col_type, comment) 行列表格式化为文本"""
        schema: dict = {}
        for row in rows:
            table   = row[0]
            col     = row[1]
            col_type = row[2] if len(row) > 2 else ""
            comment = row[3] if len(row) > 3 else ""
            if table not in schema:
                if len(schema) >= max_tables:
                    continue
                schema[table] = []
            desc = f"  - {col} {col_type}"
            if comment:
                desc += f"  // {comment}"
            schema[table].append(desc)

        if not schema:
            return ""

        lines = []
        for tbl, cols in schema.items():
            lines.append(f"表名: {tbl}")
            lines.extend(cols)
        return "\n".join(lines)

    # 保留原有接口兼容
    def get_all_tables(self):
        return self.get_tables()

    # ─────────────────────────────────────────────────
    # SQL 多语句拆分执行
    # ─────────────────────────────────────────────────
    @staticmethod
    def _split_statements(sql: str) -> list[str]:
        """
        按分号拆分 SQL，同时处理字符串内的分号（单引号/双引号内不拆分）。
        返回非空语句列表。
        """
        stmts = []
        buf = []
        in_single = False
        in_double = False
        i = 0
        while i < len(sql):
            ch = sql[i]
            if ch == "'" and not in_double:
                in_single = not in_single
                buf.append(ch)
            elif ch == '"' and not in_single:
                in_double = not in_double
                buf.append(ch)
            elif ch == ';' and not in_single and not in_double:
                stmt = ''.join(buf).strip()
                if stmt:
                    stmts.append(stmt)
                buf = []
            else:
                buf.append(ch)
            i += 1
        last = ''.join(buf).strip()
        if last:
            stmts.append(last)
        return stmts

    def execute(self, sql: str):
        """
        执行一条或多条 SQL（以分号分隔）。
        - 遇到 USE <dbname> 自动切换数据库
        - 遇到注释行（-- 开头）跳过
        - 返回最后一条有结果集的语句的 (cols, rows)；DDL/DML 返回 ([], [])
        """
        stmts = self._split_statements(sql)
        if not stmts:
            return [], []

        last_cols: list = []
        last_rows: list = []

        for stmt in stmts:
            # 跳过纯注释语句
            if all(line.strip().startswith('--') or line.strip() == ''
                   for line in stmt.splitlines()):
                continue

            upper = stmt.strip().upper()

            # ── USE 语句：切换库 ──────────────────
            if upper.startswith('USE '):
                new_db = stmt.strip()[4:].strip().strip('`').strip('"').strip("'").strip('[]')
                if new_db:

                    if self._is_argo():
                        # 星环：直接发 USE 语句
                        with self.engine.connect() as conn:
                            conn.execute(f"USE {new_db}")
                        self.dbname = new_db
                    else:
                        self._build_engine(new_db)
                        self.dbname = new_db
                continue

            # ── 其他语句 ─────────────────────────
            try:
                with self.engine.connect() as conn:
                    if self._is_argo() or self._is_xugu():
                        result = conn.execute(stmt)
                    else:
                        result = conn.execute(text(stmt))

                    conn.commit()
                    if result.returns_rows:
                        last_cols = list(result.keys())
                        last_rows = result.fetchall()
                    else:
                        last_cols = []
                        last_rows = []
            except Exception as e:
                raise e

        return last_cols, last_rows
