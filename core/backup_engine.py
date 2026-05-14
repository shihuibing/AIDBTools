"""
backup_engine.py
数据库备份与恢复引擎
- 支持导出整库为 SQL 文件（INSERT 语句）
- 支持按表选择、增量备份（仅含结构 / 含结构+数据）
- 支持恢复（从 SQL 文件执行）
- 支持备份记录管理（本地 JSON）
"""
import os
import json
import threading
import datetime
from dataclasses import dataclass, field, asdict
from typing import Callable, Optional, List
from core.connection import DatabaseConnector


# ── 备份配置 ──────────────────────────────────────────────────────
@dataclass
class BackupConfig:
    connector:      DatabaseConnector = None
    db_name:        str = ""
    tables:         list = field(default_factory=list)   # 空=备份全部
    include_data:   bool = True    # True=结构+数据, False=仅结构
    backup_dir:     str = ""       # 备份文件保存目录
    file_prefix:    str = ""       # 文件名前缀（空=自动用库名）
    batch_size:     int = 500      # 每条 INSERT 的行数（批量插入）


# ── 备份记录 ──────────────────────────────────────────────────────
@dataclass
class BackupRecord:
    record_id:    str = ""        # 唯一 ID
    db_name:      str = ""
    tables:       list = field(default_factory=list)
    file_path:    str = ""
    file_size:    int = 0         # 字节
    created_at:   str = ""
    include_data: bool = True
    note:         str = ""

    def size_str(self) -> str:
        sz = self.file_size
        if sz < 1024:
            return f"{sz} B"
        elif sz < 1024 * 1024:
            return f"{sz/1024:.1f} KB"
        else:
            return f"{sz/1024/1024:.2f} MB"


# ── 备份进度 ──────────────────────────────────────────────────────
class BackupProgress:
    def __init__(self):
        self.total:    int  = 0
        self.done:     int  = 0
        self.errors:   list = []
        self.running:  bool = False
        self.finished: bool = False
        self.message:  str  = ""

    @property
    def pct(self) -> int:
        if self.total <= 0:
            return 0
        return int(self.done / self.total * 100)


# ── 备份记录存储 ───────────────────────────────────────────────────
_RECORDS_FILE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "config", "backup_records.json"
)


def load_backup_records() -> List[BackupRecord]:
    try:
        with open(_RECORDS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        return [BackupRecord(**d) for d in data]
    except Exception:
        return []


def save_backup_records(records: List[BackupRecord]):
    os.makedirs(os.path.dirname(_RECORDS_FILE), exist_ok=True)
    with open(_RECORDS_FILE, "w", encoding="utf-8") as f:
        json.dump([asdict(r) for r in records], f, ensure_ascii=False, indent=2)


def add_backup_record(record: BackupRecord):
    records = load_backup_records()
    records.insert(0, record)
    # 最多保留 200 条记录
    records = records[:200]
    save_backup_records(records)


def delete_backup_record(record_id: str):
    records = load_backup_records()
    records = [r for r in records if r.record_id != record_id]
    save_backup_records(records)


# ── 备份引擎 ──────────────────────────────────────────────────────
class BackupEngine:
    """数据库备份与恢复引擎（线程安全）"""

    def __init__(self):
        self._stop_flag = threading.Event()
        self.progress   = BackupProgress()

    def stop(self):
        self._stop_flag.set()

    def reset(self):
        self._stop_flag.clear()
        self.progress = BackupProgress()

    # ── 备份入口 ───────────────────────────────────────────────────
    def backup(
        self,
        cfg: BackupConfig,
        on_progress: Callable[[BackupProgress], None] = None,
        on_log: Callable[[str], None] = None,
    ) -> Optional[BackupRecord]:
        """
        执行备份，阻塞直到完成或停止。
        成功返回 BackupRecord，失败返回 None。
        """
        self.reset()
        prog = self.progress

        def _log(msg: str):
            prog.message = msg
            if on_log:
                on_log(msg)

        def _notify():
            if on_progress:
                on_progress(prog)

        try:
            prog.running = True
            connector = cfg.connector
            db_name   = cfg.db_name

            # 1. 获取要备份的表列表
            if cfg.tables:
                tables = list(cfg.tables)
            else:
                _log(f"[SEARCH] 获取 {db_name} 表列表…")
                tables = connector.get_tables(db_name)

            if not tables:
                _log("[WARN] 该数据库没有可备份的表")
                prog.finished = True
                prog.running  = False
                _notify()
                return None

            prog.total = len(tables)
            _notify()

            # 2. 生成备份文件路径
            ts       = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            prefix   = cfg.file_prefix or db_name or "backup"
            filename = f"{prefix}_{ts}.sql"
            filepath = os.path.join(cfg.backup_dir or ".", filename)
            os.makedirs(os.path.dirname(os.path.abspath(filepath)), exist_ok=True)

            _log(f"[FILE] 备份文件：{filepath}")

            # 3. 逐表导出
            with open(filepath, "w", encoding="utf-8") as f:
                # 文件头
                f.write(f"-- AIDBTools Backup\n")
                f.write(f"-- Database: {db_name}\n")
                f.write(f"-- Created:  {datetime.datetime.now().isoformat()}\n")
                f.write(f"-- Tables:   {', '.join(tables)}\n\n")

                for i, table in enumerate(tables):
                    if self._stop_flag.is_set():
                        _log("[STOP] 备份已停止")
                        break

                    _log(f"[{i+1}/{len(tables)}] 备份表：{table}")

                    try:
                        # 写表分隔注释
                        f.write(f"\n-- ─────────────────────────────\n")
                        f.write(f"-- 表: {table}\n")
                        f.write(f"-- ─────────────────────────────\n\n")

                        # 写建表语句（结构）
                        create_sql = self._get_create_table(connector, db_name, table)
                        if create_sql:
                            f.write(create_sql.rstrip(";") + ";\n\n")

                        # 写数据
                        if cfg.include_data:
                            row_count = self._write_table_data(
                                f, connector, db_name, table,
                                cfg.batch_size, _log
                            )
                            _log(f"  → 已写入 {row_count} 行")

                        prog.done = i + 1
                        _notify()

                    except Exception as e:
                        prog.errors.append(f"{table}: {e}")
                        _log(f"[FAIL] 表 {table} 备份失败：{e}")

            # 4. 构建备份记录
            file_size = os.path.getsize(filepath) if os.path.exists(filepath) else 0
            record = BackupRecord(
                record_id   = f"{db_name}_{ts}",
                db_name     = db_name,
                tables      = tables,
                file_path   = filepath,
                file_size   = file_size,
                created_at  = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                include_data = cfg.include_data,
                note        = f"错误 {len(prog.errors)} 条" if prog.errors else "成功",
            )
            add_backup_record(record)

            if prog.errors:
                _log(f"[WARN] 备份完成（{len(prog.errors)} 个表出错）：{filepath}")
            else:
                _log(f"[OK] 备份完成！文件大小：{record.size_str()}，路径：{filepath}")

        except Exception as e:
            prog.errors.append(str(e))
            _log(f"[FAIL] 备份异常：{e}")
            record = None
        finally:
            prog.running  = False
            prog.finished = True
            _notify()

        return record if not prog.errors or (prog.done > 0) else None

    # ── 恢复入口 ───────────────────────────────────────────────────
    def restore(
        self,
        connector: DatabaseConnector,
        sql_file: str,
        on_progress: Callable[[BackupProgress], None] = None,
        on_log: Callable[[str], None] = None,
    ) -> BackupProgress:
        """
        从 SQL 文件恢复数据库。
        逐条执行语句，忽略注释行。
        """
        self.reset()
        prog = self.progress

        def _log(msg: str):
            prog.message = msg
            if on_log:
                on_log(msg)

        def _notify():
            if on_progress:
                on_progress(prog)

        try:
            prog.running = True

            if not os.path.exists(sql_file):
                raise FileNotFoundError(f"文件不存在：{sql_file}")

            _log(f"📂 读取 SQL 文件：{sql_file}")
            with open(sql_file, "r", encoding="utf-8") as f:
                content = f.read()

            # 拆分语句
            stmts = self._split_sql(content)
            prog.total = len(stmts)
            _log(f"共 {prog.total} 条语句待执行")
            _notify()

            ok_count = 0
            for i, stmt in enumerate(stmts):
                if self._stop_flag.is_set():
                    _log("[STOP] 恢复已停止")
                    break
                try:
                    connector.execute(stmt)
                    ok_count += 1
                except Exception as e:
                    prog.errors.append(f"[{i+1}] {str(e)[:120]}")
                    _log(f"  [WARN] 第 {i+1} 条语句出错（已跳过）：{str(e)[:80]}")

                prog.done = i + 1
                if (i + 1) % 50 == 0 or (i + 1) == prog.total:
                    _log(f"  进度：{i+1}/{prog.total} 条")
                    _notify()

            _log(f"[OK] 恢复完成：成功 {ok_count} 条，失败 {len(prog.errors)} 条")

        except Exception as e:
            prog.errors.append(str(e))
            _log(f"[FAIL] 恢复异常：{e}")
        finally:
            prog.running  = False
            prog.finished = True
            _notify()

        return prog

    # ── 私有工具 ───────────────────────────────────────────────────
    @staticmethod
    def _get_create_table(connector: DatabaseConnector, db_name: str, table: str) -> str:
        """尝试获取 CREATE TABLE 语句，不同数据库有差异"""
        db_type = connector.db_type or ""

        # MySQL / 兼容 MySQL 方言
        mysql_like = {"mysql", "oceanbase", "polardb", "tdsql", "tidb", "gbase", "argodb", "inceptor"}
        if db_type in mysql_like:
            try:
                _, rows = connector.execute(f"SHOW CREATE TABLE `{db_name}`.`{table}`")
                if rows:
                    return rows[0][1]
            except Exception:
                pass

        # SQL Server
        if db_type == "sqlserver":
            try:
                sql = (
                    f"SELECT 'CREATE TABLE [{table}] (' + CHAR(13) + "
                    f"STRING_AGG(CAST('[' + c.name + '] ' + tp.name + "
                    f"CASE WHEN tp.name IN ('varchar','nvarchar','char','nchar') THEN '(' + "
                    f"CAST(c.max_length AS VARCHAR) + ')' ELSE '' END AS NVARCHAR(MAX)), "
                    f"', ' + CHAR(13)) + CHAR(13) + ')' "
                    f"FROM sys.tables t "
                    f"JOIN sys.columns c ON t.object_id=c.object_id "
                    f"JOIN sys.types tp ON c.user_type_id=tp.user_type_id "
                    f"WHERE t.name='{table}'"
                )
                _, rows = connector.execute(sql)
                if rows and rows[0][0]:
                    return rows[0][0]
            except Exception:
                pass

        # PostgreSQL / GaussDB
        if db_type in ("postgresql", "gaussdb", "opengauss", "kingbase"):
            try:
                sql = (
                    f"SELECT 'CREATE TABLE IF NOT EXISTS ' || quote_ident(table_name) || ' (' || "
                    f"string_agg(quote_ident(column_name) || ' ' || data_type, ', ') || ')' "
                    f"FROM information_schema.columns "
                    f"WHERE table_schema='public' AND table_name='{table}' "
                    f"GROUP BY table_name"
                )
                _, rows = connector.execute(sql)
                if rows and rows[0][0]:
                    return rows[0][0]
            except Exception:
                pass

        # 降级：生成简单列注释
        try:
            cols, sample_rows = connector.get_table_data(table, db_name, limit=0)
            if cols:
                col_defs = ", ".join(f"`{c}` TEXT" for c in cols)
                return f"-- CREATE TABLE `{table}` ({col_defs})"
        except Exception:
            pass

        return f"-- CREATE TABLE `{table}` (结构无法获取)"

    @staticmethod
    def _write_table_data(
        f,
        connector: DatabaseConnector,
        db_name: str,
        table: str,
        batch_size: int,
        log_fn: Callable,
    ) -> int:
        """将表中所有数据写成 INSERT 语句，返回写入行数"""
        try:
            cols, rows = connector.get_table_data(table, db_name, limit=0)
        except Exception as e:
            log_fn(f"  [WARN] 读取 {table} 数据失败：{e}")
            return 0

        if not rows:
            f.write(f"-- 表 {table} 无数据\n\n")
            return 0

        db_type  = connector.db_type or ""
        mysql_like = {"mysql", "oceanbase", "polardb", "tdsql", "tidb", "gbase", "argodb", "inceptor"}

        if db_type in mysql_like:
            q = "`"
        elif db_type == "sqlserver":
            q = "["
        else:
            q = '"'

        def quote_col(c):
            if db_type == "sqlserver":
                return f"[{c}]"
            return f"{q}{c}{q}"

        def quote_val(v):
            if v is None:
                return "NULL"
            if isinstance(v, bool):
                return "1" if v else "0"
            if isinstance(v, (int, float)):
                return str(v)
            # datetime/date 转字符串
            s = str(v).replace("'", "''")
            return f"'{s}'"

        cols_str = ", ".join(quote_col(c) for c in cols)
        total_written = 0

        # 分批写 INSERT
        for batch_start in range(0, len(rows), batch_size):
            batch = rows[batch_start: batch_start + batch_size]
            vals_list = []
            for row in batch:
                vals_list.append("(" + ", ".join(quote_val(v) for v in row) + ")")
            all_vals = ",\n  ".join(vals_list)

            if db_type in mysql_like:
                insert_sql = (
                    f"INSERT INTO `{db_name}`.`{table}` ({cols_str}) VALUES\n  {all_vals};\n"
                )
            elif db_type == "sqlserver":
                insert_sql = (
                    f"INSERT INTO [{table}] ({cols_str}) VALUES\n  {all_vals};\n"
                )
            else:
                insert_sql = (
                    f"INSERT INTO \"{table}\" ({cols_str}) VALUES\n  {all_vals};\n"
                )

            f.write(insert_sql)
            total_written += len(batch)

        f.write("\n")
        return total_written

    @staticmethod
    def _split_sql(content: str) -> list[str]:
        """按分号拆分 SQL 文件为语句列表，跳过注释行"""
        stmts = []
        buf   = []
        in_single = False
        in_double = False

        for ch in content:
            if ch == "'" and not in_double:
                in_single = not in_single
                buf.append(ch)
            elif ch == '"' and not in_single:
                in_double = not in_double
                buf.append(ch)
            elif ch == ';' and not in_single and not in_double:
                stmt = ''.join(buf).strip()
                # 去掉纯注释语句
                non_comment = [
                    ln for ln in stmt.splitlines()
                    if ln.strip() and not ln.strip().startswith('--')
                ]
                if non_comment:
                    stmts.append(stmt)
                buf = []
            else:
                buf.append(ch)

        last = ''.join(buf).strip()
        non_comment = [
            ln for ln in last.splitlines()
            if ln.strip() and not ln.strip().startswith('--')
        ]
        if non_comment:
            stmts.append(last)

        return stmts
