"""
sync_engine.py
表/库数据同步引擎
- 支持表→表同步（相同连接 or 跨连接）
- 支持库→库同步（批量表同步）
- 支持增量同步（基于主键或时间戳字段）
- 支持全量覆盖、追加两种模式
"""
import threading
from dataclasses import dataclass, field
from typing import Callable, Optional
from core.connection import DatabaseConnector


@dataclass
class SyncConfig:
    """同步配置"""
    # 源
    src_connector:  DatabaseConnector = None
    src_db:         str = ""
    src_table:      str = ""

    # 目标
    dst_connector:  DatabaseConnector = None
    dst_db:         str = ""
    dst_table:      str = ""

    # 同步模式
    mode:           str = "overwrite"   # "overwrite" | "append" | "incremental"
    incremental_col: str = ""           # 增量列（时间戳或自增ID）
    batch_size:     int = 1000          # 每批写入行数

    # 目标表不存在时是否自动建表
    auto_create:    bool = True

    # 列映射 {src_col: dst_col}（为空表示按列名映射）
    column_map:     dict = field(default_factory=dict)


class SyncProgress:
    """同步进度"""
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


class SyncEngine:
    """数据同步执行引擎（线程安全）"""

    def __init__(self):
        self._stop_flag = threading.Event()
        self.progress   = SyncProgress()

    def stop(self):
        self._stop_flag.set()

    def reset(self):
        self._stop_flag.clear()
        self.progress = SyncProgress()

    # ── 表→表同步入口 ────────────────────────────
    def sync_table(
        self,
        cfg: SyncConfig,
        on_progress: Callable[[SyncProgress], None] = None,
        on_log:      Callable[[str], None] = None,
    ) -> SyncProgress:
        """
        同步单张表，阻塞直到完成或停止。
        返回 SyncProgress。
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
            src = cfg.src_connector
            dst = cfg.dst_connector

            # 1. 获取源列信息
            _log(f"[SEARCH] 读取源表结构：{cfg.src_db}.{cfg.src_table}")
            src_cols, src_rows = src.get_table_data(cfg.src_table, cfg.src_db, limit=0)
            prog.total = len(src_rows)
            _notify()

            if not src_cols:
                raise ValueError("源表无列信息")

            # 2. 列映射
            if cfg.column_map:
                mapped_cols = [cfg.column_map.get(c, c) for c in src_cols]
            else:
                mapped_cols = list(src_cols)

            # 3. 全量模式 → 目标表清空或建表
            if cfg.mode == "overwrite":
                _log(f"[CLEAR] 清空目标表：{cfg.dst_db}.{cfg.dst_table}")
                self._truncate_or_create(
                    dst, cfg.dst_db, cfg.dst_table,
                    src_cols, mapped_cols, cfg.auto_create
                )

            # 4. 增量模式 → 查询最新值
            last_val = None
            if cfg.mode == "incremental" and cfg.incremental_col:
                last_val = self._get_last_value(
                    dst, cfg.dst_db, cfg.dst_table, cfg.incremental_col
                )
                if last_val is not None:
                    _log(f"[PIN] 增量列 {cfg.incremental_col} 最新值：{last_val}")
                    # 重新过滤源数据
                    inc_idx = list(src_cols).index(cfg.incremental_col) if cfg.incremental_col in src_cols else -1
                    if inc_idx >= 0:
                        src_rows = [r for r in src_rows if r[inc_idx] > last_val]
                        prog.total = len(src_rows)
                        _notify()

            if not src_rows:
                _log("[INFO] 无需同步（无新数据）")
                prog.done     = 0
                prog.finished = True
                prog.running  = False
                _notify()
                return prog

            # 5. 分批写入
            _log(f"[WRITE] 开始写入 {prog.total} 行到 {cfg.dst_db}.{cfg.dst_table}")
            total_written = 0
            for batch_start in range(0, len(src_rows), cfg.batch_size):
                if self._stop_flag.is_set():
                    _log("[STOP] 同步已停止")
                    break
                batch = src_rows[batch_start: batch_start + cfg.batch_size]
                try:
                    self._insert_batch(
                        dst, cfg.dst_db, cfg.dst_table,
                        mapped_cols, batch
                    )
                    total_written += len(batch)
                    prog.done = total_written
                    _log(f"  已写入 {total_written}/{prog.total} 行")
                    _notify()
                except Exception as e:
                    prog.errors.append(str(e))
                    _log(f"[FAIL] 批量写入失败（第 {batch_start} 行起）：{e}")
                    if len(prog.errors) >= 5:
                        _log("[FAIL] 错误过多，终止同步")
                        break

            _log(f"[OK] 同步完成：写入 {total_written} 行，错误 {len(prog.errors)} 条")

        except Exception as e:
            prog.errors.append(str(e))
            _log(f"[FAIL] 同步异常：{e}")
        finally:
            prog.running  = False
            prog.finished = True
            _notify()

        return prog

    # ── 库→库批量同步 ────────────────────────────
    def sync_database(
        self,
        src_connector: DatabaseConnector,
        src_db: str,
        dst_connector: DatabaseConnector,
        dst_db: str,
        tables: list[str],
        mode: str = "overwrite",
        batch_size: int = 1000,
        on_progress: Callable[[str, SyncProgress], None] = None,
        on_log: Callable[[str], None] = None,
    ) -> dict[str, SyncProgress]:
        """
        批量同步多张表，返回 {table_name: SyncProgress}。
        """
        results = {}
        for i, table in enumerate(tables):
            if self._stop_flag.is_set():
                break
            if on_log:
                on_log(f"\n[{i+1}/{len(tables)}] 同步表：{table}")
            cfg = SyncConfig(
                src_connector=src_connector, src_db=src_db, src_table=table,
                dst_connector=dst_connector, dst_db=dst_db, dst_table=table,
                mode=mode, batch_size=batch_size,
            )

            def _combined_progress(prog, tbl=table):
                if on_progress:
                    on_progress(tbl, prog)

            prog = self.sync_table(cfg, on_progress=_combined_progress, on_log=on_log)
            results[table] = prog
        return results

    # ── 私有工具 ─────────────────────────────────
    @staticmethod
    def _truncate_or_create(
        connector: DatabaseConnector,
        dbname: str, table: str,
        src_cols: list, dst_cols: list,
        auto_create: bool,
    ):
        """清空目标表，若不存在则按源表列名+文本类型建表（简单版）"""
        try:
            connector.execute(f"USE `{dbname}`")
        except Exception:
            try:
                connector.execute(f'USE "{dbname}"')
            except Exception:
                pass

        # 尝试 TRUNCATE，失败则 DELETE
        try:
            connector.execute(f"TRUNCATE TABLE `{table}`")
        except Exception:
            try:
                connector.execute(f'TRUNCATE TABLE "{table}"')
            except Exception:
                if auto_create:
                    # 建表：全部用 TEXT 类型
                    cols_def = ", ".join(f"`{c}` TEXT" for c in dst_cols)
                    connector.execute(
                        f"CREATE TABLE IF NOT EXISTS `{table}` ({cols_def})"
                    )

    @staticmethod
    def _get_last_value(connector: DatabaseConnector, dbname: str, table: str, col: str):
        """获取目标表增量列的最大值"""
        try:
            _, rows = connector.execute(f"SELECT MAX(`{col}`) FROM `{dbname}`.`{table}`")
            if rows and rows[0][0] is not None:
                return rows[0][0]
        except Exception:
            pass
        return None

    @staticmethod
    def _insert_batch(
        connector: DatabaseConnector,
        dbname: str, table: str,
        cols: list, rows: list,
    ):
        """批量 INSERT"""
        if not rows:
            return
        placeholders = ", ".join(["?"] * len(cols))
        cols_str     = ", ".join(f"`{c}`" for c in cols)
        sql = f"INSERT INTO `{dbname}`.`{table}` ({cols_str}) VALUES ({placeholders})"

        # 尝试批量参数化插入
        try:
            connector.execute_many(sql, rows)
            return
        except AttributeError:
            pass

        # 降级：逐行插入（兼容不支持 execute_many 的连接器）
        for row in rows:
            vals = []
            for v in row:
                if v is None:
                    vals.append("NULL")
                elif isinstance(v, (int, float)):
                    vals.append(str(v))
                else:
                    escaped = str(v).replace("'", "''")
                    vals.append(f"'{escaped}'")
            row_sql = (
                f"INSERT INTO `{dbname}`.`{table}` ({cols_str})"
                f" VALUES ({', '.join(vals)})"
            )
            connector.execute(row_sql)
