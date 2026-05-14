"""
sync_window.py
数据同步窗口 —— 表→表同步 + 库→库同步
"""
import threading
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTabWidget, QWidget,
    QLabel, QComboBox, QPushButton, QProgressBar, QTextEdit,
    QGroupBox, QFormLayout, QCheckBox, QSpinBox, QListWidget,
    QListWidgetItem, QAbstractItemView, QSplitter, QFrame,
    QMessageBox, QLineEdit, QSizePolicy,
)
from PySide6.QtCore import Qt, QThread, Signal, QObject
from PySide6.QtGui import QFont

from core.sync_engine import SyncEngine, SyncConfig, SyncProgress
from core.connection import DatabaseConnector
from ui.iconfont_loader import Icon, wrap_pua
from ui.theme_manager import (
    load_theme, THEME_DARK, THEME_AUTO, _is_system_dark,
    get_theme_tokens, get_log_box_style, build_popup_base_style,
    build_dialog_frame,
    build_frameless_dialog_style, make_frameless_title_bar,
)



def _is_dark_now() -> bool:
    t = load_theme()
    if t == THEME_AUTO:
        return _is_system_dark()
    return t == THEME_DARK


# ── 信号转发 ───────────────────────────────────────────────────────────────
class _SyncSignals(QObject):
    log     = Signal(str)
    progress = Signal(int, int, str)   # (done, total, message)
    finished = Signal()


# ── 后台同步线程 ───────────────────────────────────────────────────────────
class _SyncWorker(QThread):
    def __init__(self, engine: SyncEngine, cfg: SyncConfig, signals: _SyncSignals):
        super().__init__()
        self._engine  = engine
        self._cfg     = cfg
        self._signals = signals

    def run(self):
        def on_progress(prog: SyncProgress):
            self._signals.progress.emit(prog.done, prog.total, prog.message)

        def on_log(msg: str):
            self._signals.log.emit(msg)

        self._engine.sync_table(self._cfg, on_progress=on_progress, on_log=on_log)
        self._signals.finished.emit()


class _DbSyncWorker(QThread):
    def __init__(self, engine: SyncEngine, signals: _SyncSignals,
                 src_conn, src_db, dst_conn, dst_db, tables, mode, batch):
        super().__init__()
        self._engine  = engine
        self._signals = signals
        self._src_conn = src_conn
        self._src_db   = src_db
        self._dst_conn = dst_conn
        self._dst_db   = dst_db
        self._tables   = tables
        self._mode     = mode
        self._batch    = batch

    def run(self):
        done_tables = [0]

        def on_progress(table, prog: SyncProgress):
            total_rows = max(prog.total, 1)
            self._signals.progress.emit(
                done_tables[0], len(self._tables),
                f"[{table}] {prog.done}/{prog.total}"
            )

        def on_log(msg: str):
            self._signals.log.emit(msg)

        results = self._engine.sync_database(
            self._src_conn, self._src_db,
            self._dst_conn, self._dst_db,
            self._tables,
            mode=self._mode,
            batch_size=self._batch,
            on_progress=on_progress,
            on_log=on_log,
        )
        done_tables[0] = len(results)
        self._signals.progress.emit(len(results), len(self._tables), "完成")
        self._signals.finished.emit()


# ── 主同步窗口 ─────────────────────────────────────────────────────────────
class SyncWindow(QDialog):
    def __init__(self, parent=None,
                 conns: dict = None,
                 conn_infos: dict = None):
        """
        conns: {conn_name: DatabaseConnector}
        conn_infos: {conn_name: info_dict}
        """
        super().__init__(parent)
        # 无边框窗口设置
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setWindowTitle("数据同步")
        self.setMinimumSize(820, 600)
        self.resize(920, 660)
        self._theme = load_theme()
        self._tokens = get_theme_tokens(self._theme)
        self._conns      = conns      or {}
        self._conn_infos = conn_infos or {}
        self._engine     = SyncEngine()
        self._worker     = None
        self._signals    = _SyncSignals()
        self._signals.log.connect(self._on_log)
        self._signals.progress.connect(self._on_progress)
        self._signals.finished.connect(self._on_finished)
        # 先创建标题栏（必须在 _build_ui 之前）
        self._title_bar, self._title_lbl, self._title_close_btn = make_frameless_title_bar(
            self, "数据同步", self._tokens)
        self._title_close_btn.clicked.connect(self.close)
        self._build_ui()

    def _build_ui(self):
        frame, frame_layout, inner = build_dialog_frame(self._tokens, self, self._title_bar)
        inner_layout = QVBoxLayout(inner)
        inner_layout.setContentsMargins(14, 14, 14, 14)
        inner_layout.setSpacing(0)

        self.tabs = QTabWidget()
        self.tabs.addTab(self._build_table_sync_tab(), Icon.prefixed_text('table', "表→表同步"))
        self.tabs.addTab(self._build_db_sync_tab(),    Icon.prefixed_text('database', "库→库同步"))
        inner_layout.addWidget(self.tabs)

        # 日志区
        log_grp = QGroupBox("执行日志")
        log_lay = QVBoxLayout(log_grp)
        self.log_box = QTextEdit()
        self.log_box.setReadOnly(True)
        self.log_box.setFont(QFont("Consolas", 9))
        self.log_box.setMaximumHeight(120)
        self.log_box.setStyleSheet(get_log_box_style(self._theme))
        log_lay.addWidget(self.log_box)
        inner_layout.addWidget(log_grp)

        # 进度条
        self.progress = QProgressBar()
        self.progress.setValue(0)
        self.progress.setFixedHeight(16)
        frame_layout.addWidget(self.progress)

    # ── 表→表同步 Tab ─────────────────────────────────
    def _build_table_sync_tab(self):
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setSpacing(10)

        # 源
        src_grp = QGroupBox("源表")
        src_form = QFormLayout(src_grp)
        self.cmb_src_conn = QComboBox()
        self.cmb_src_db   = QComboBox()
        self.cmb_src_tbl  = QComboBox()
        self.cmb_src_conn.addItems(list(self._conns.keys()))
        self.cmb_src_conn.currentTextChanged.connect(self._on_src_conn_changed)
        self.cmb_src_db.currentTextChanged.connect(self._on_src_db_changed)
        src_form.addRow("连接:", self.cmb_src_conn)
        src_form.addRow("数据库:", self.cmb_src_db)
        src_form.addRow("表:", self.cmb_src_tbl)

        # 目标
        dst_grp = QGroupBox("目标表")
        dst_form = QFormLayout(dst_grp)
        self.cmb_dst_conn = QComboBox()
        self.cmb_dst_db   = QComboBox()
        self.txt_dst_tbl  = QLineEdit()
        self.txt_dst_tbl.setPlaceholderText("留空则与源表同名")
        self.cmb_dst_conn.addItems(list(self._conns.keys()))
        self.cmb_dst_conn.currentTextChanged.connect(self._on_dst_conn_changed)
        dst_form.addRow("连接:", self.cmb_dst_conn)
        dst_form.addRow("数据库:", self.cmb_dst_db)
        dst_form.addRow("表名:", self.txt_dst_tbl)

        src_dst_row = QHBoxLayout()
        src_dst_row.addWidget(src_grp)
        src_dst_row.addWidget(dst_grp)
        lay.addLayout(src_dst_row)

        # 选项
        opt_grp = QGroupBox("同步选项")
        opt_form = QFormLayout(opt_grp)
        self.cmb_tbl_mode = QComboBox()
        self.cmb_tbl_mode.addItems(["全量覆盖 (overwrite)", "追加 (append)", "增量 (incremental)"])
        self.cmb_tbl_mode.currentTextChanged.connect(self._on_tbl_mode_changed)
        opt_form.addRow("同步模式:", self.cmb_tbl_mode)

        self.txt_inc_col = QLineEdit()
        self.txt_inc_col.setPlaceholderText("增量字段名（如：updated_at / id）")
        self.txt_inc_col.setEnabled(False)
        self.lbl_inc_col = QLabel("增量列:")
        opt_form.addRow(self.lbl_inc_col, self.txt_inc_col)

        self.spin_batch = QSpinBox()
        self.spin_batch.setRange(100, 50000)
        self.spin_batch.setValue(1000)
        self.spin_batch.setSuffix(" 行/批")
        opt_form.addRow("批大小:", self.spin_batch)

        self.chk_auto_create = QCheckBox("目标表不存在时自动建表")
        self.chk_auto_create.setChecked(True)
        opt_form.addRow("", self.chk_auto_create)

        lay.addWidget(opt_grp)
        lay.addStretch()

        # 按钮
        btn_row = QHBoxLayout()
        self.btn_tbl_sync = QPushButton(Icon.prefixed_text('play', "开始同步"))
        self.btn_tbl_sync.setFixedHeight(34)
        self.btn_tbl_sync.setProperty("role", "primary")
        self.btn_tbl_stop = QPushButton(Icon.prefixed_text('stop', "停止"))
        self.btn_tbl_stop.setFixedHeight(34)
        self.btn_tbl_stop.setEnabled(False)
        self.btn_tbl_stop.setProperty("role", "danger")

        self.btn_tbl_sync.clicked.connect(self._on_tbl_sync)
        self.btn_tbl_stop.clicked.connect(self._on_stop)
        btn_row.addWidget(self.btn_tbl_sync)
        btn_row.addWidget(self.btn_tbl_stop)
        btn_row.addStretch()
        lay.addLayout(btn_row)

        # 初始化
        if self._conns:
            self._on_src_conn_changed(self.cmb_src_conn.currentText())
            self._on_dst_conn_changed(self.cmb_dst_conn.currentText())

        return w

    # ── 库→库同步 Tab ─────────────────────────────────
    def _build_db_sync_tab(self):
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setSpacing(10)

        conn_row = QHBoxLayout()
        # 源
        src_grp = QGroupBox("源库")
        sf = QFormLayout(src_grp)
        self.cmb_sdb_src_conn = QComboBox()
        self.cmb_sdb_src_db   = QComboBox()
        self.cmb_sdb_src_conn.addItems(list(self._conns.keys()))
        self.cmb_sdb_src_conn.currentTextChanged.connect(self._on_sdb_src_conn_changed)
        sf.addRow("连接:", self.cmb_sdb_src_conn)
        sf.addRow("数据库:", self.cmb_sdb_src_db)
        # 目标
        dst_grp = QGroupBox("目标库")
        df = QFormLayout(dst_grp)
        self.cmb_sdb_dst_conn = QComboBox()
        self.cmb_sdb_dst_db   = QComboBox()
        self.cmb_sdb_dst_conn.addItems(list(self._conns.keys()))
        self.cmb_sdb_dst_conn.currentTextChanged.connect(self._on_sdb_dst_conn_changed)
        df.addRow("连接:", self.cmb_sdb_dst_conn)
        df.addRow("数据库:", self.cmb_sdb_dst_db)

        conn_row.addWidget(src_grp)
        conn_row.addWidget(dst_grp)
        lay.addLayout(conn_row)

        # 选择要同步的表
        tbl_grp = QGroupBox("选择同步的表（不选则同步全部）")
        tbl_lay = QVBoxLayout(tbl_grp)
        top_row = QHBoxLayout()
        btn_load = QPushButton(Icon.prefixed_text('refresh', "加载表列表"))
        btn_load.clicked.connect(self._sdb_load_tables)
        btn_sel_all  = QPushButton("全选")
        btn_sel_none = QPushButton("全不选")
        btn_sel_all.clicked.connect(lambda: self._sdb_set_all(True))
        btn_sel_none.clicked.connect(lambda: self._sdb_set_all(False))
        top_row.addWidget(btn_load); top_row.addWidget(btn_sel_all)
        top_row.addWidget(btn_sel_none); top_row.addStretch()
        tbl_lay.addLayout(top_row)
        self.sdb_tbl_list = QListWidget()
        self.sdb_tbl_list.setSelectionMode(QAbstractItemView.SelectionMode.MultiSelection)
        self.sdb_tbl_list.setMaximumHeight(140)
        tbl_lay.addWidget(self.sdb_tbl_list)
        lay.addWidget(tbl_grp)

        # 选项
        opt_grp = QGroupBox("同步选项")
        opt_form = QFormLayout(opt_grp)
        self.cmb_db_mode = QComboBox()
        self.cmb_db_mode.addItems(["全量覆盖 (overwrite)", "追加 (append)"])
        opt_form.addRow("同步模式:", self.cmb_db_mode)
        self.spin_db_batch = QSpinBox()
        self.spin_db_batch.setRange(100, 50000)
        self.spin_db_batch.setValue(1000)
        self.spin_db_batch.setSuffix(" 行/批")
        opt_form.addRow("批大小:", self.spin_db_batch)
        lay.addWidget(opt_grp)
        lay.addStretch()

        btn_row = QHBoxLayout()
        self.btn_db_sync = QPushButton(Icon.prefixed_text('play', "开始库同步"))
        self.btn_db_sync.setFixedHeight(34)
        self.btn_db_sync.setProperty("role", "success")
        self.btn_db_stop = QPushButton(Icon.prefixed_text('stop', "停止"))
        self.btn_db_stop.setFixedHeight(34)
        self.btn_db_stop.setEnabled(False)
        self.btn_db_stop.setProperty("role", "danger")

        self.btn_db_sync.clicked.connect(self._on_db_sync)
        self.btn_db_stop.clicked.connect(self._on_stop)
        btn_row.addWidget(self.btn_db_sync)
        btn_row.addWidget(self.btn_db_stop)
        btn_row.addStretch()
        lay.addLayout(btn_row)

        if self._conns:
            self._on_sdb_src_conn_changed(self.cmb_sdb_src_conn.currentText())
            self._on_sdb_dst_conn_changed(self.cmb_sdb_dst_conn.currentText())

        return w

    # ── 连接/库/表 级联刷新 ──────────────────────────
    def _on_src_conn_changed(self, name: str):
        self.cmb_src_db.clear()
        conn = self._conns.get(name)
        if conn:
            try:
                dbs = conn.get_databases()
                self.cmb_src_db.addItems(dbs)
            except Exception:
                pass

    def _on_src_db_changed(self, db: str):
        self.cmb_src_tbl.clear()
        conn = self._conns.get(self.cmb_src_conn.currentText())
        if conn and db:
            try:
                tables = conn.get_tables(db)
                self.cmb_src_tbl.addItems(tables)
            except Exception:
                pass

    def _on_dst_conn_changed(self, name: str):
        self.cmb_dst_db.clear()
        conn = self._conns.get(name)
        if conn:
            try:
                dbs = conn.get_databases()
                self.cmb_dst_db.addItems(dbs)
            except Exception:
                pass

    def _on_tbl_mode_changed(self, text: str):
        is_inc = "incremental" in text
        self.txt_inc_col.setEnabled(is_inc)

    def _on_sdb_src_conn_changed(self, name: str):
        self.cmb_sdb_src_db.clear()
        conn = self._conns.get(name)
        if conn:
            try:
                self.cmb_sdb_src_db.addItems(conn.get_databases())
            except Exception:
                pass

    def _on_sdb_dst_conn_changed(self, name: str):
        self.cmb_sdb_dst_db.clear()
        conn = self._conns.get(name)
        if conn:
            try:
                self.cmb_sdb_dst_db.addItems(conn.get_databases())
            except Exception:
                pass

    def _sdb_load_tables(self):
        self.sdb_tbl_list.clear()
        src_conn = self._conns.get(self.cmb_sdb_src_conn.currentText())
        src_db   = self.cmb_sdb_src_db.currentText()
        if not src_conn or not src_db:
            QMessageBox.warning(self, "提示", "请先选择源库连接和数据库")
            return
        try:
            tables = src_conn.get_tables(src_db)
            for t in tables:
                item = QListWidgetItem(t)
                item.setSelected(True)
                self.sdb_tbl_list.addItem(item)
        except Exception as e:
            QMessageBox.critical(self, "错误", f"获取表列表失败：{e}")

    def _sdb_set_all(self, selected: bool):
        for i in range(self.sdb_tbl_list.count()):
            self.sdb_tbl_list.item(i).setSelected(selected)

    # ── 启动/停止同步 ──────────────────────────────
    def _on_tbl_sync(self):
        src_conn_name = self.cmb_src_conn.currentText()
        src_db        = self.cmb_src_db.currentText()
        src_tbl       = self.cmb_src_tbl.currentText()
        dst_conn_name = self.cmb_dst_conn.currentText()
        dst_db        = self.cmb_dst_db.currentText()
        dst_tbl       = self.txt_dst_tbl.text().strip() or src_tbl

        if not all([src_conn_name, src_db, src_tbl, dst_conn_name, dst_db]):
            QMessageBox.warning(self, "提示", "请完整填写源表和目标表信息")
            return

        src_conn = self._conns.get(src_conn_name)
        dst_conn = self._conns.get(dst_conn_name)
        if not src_conn or not dst_conn:
            QMessageBox.warning(self, "提示", "连接不存在，请先建立数据库连接")
            return

        mode_text = self.cmb_tbl_mode.currentText()
        if "overwrite" in mode_text:
            mode = "overwrite"
        elif "append" in mode_text:
            mode = "append"
        else:
            mode = "incremental"

        cfg = SyncConfig(
            src_connector=src_conn, src_db=src_db, src_table=src_tbl,
            dst_connector=dst_conn, dst_db=dst_db, dst_table=dst_tbl,
            mode=mode,
            incremental_col=self.txt_inc_col.text().strip(),
            batch_size=self.spin_batch.value(),
            auto_create=self.chk_auto_create.isChecked(),
        )

        self._start_sync(cfg)

    def _on_db_sync(self):
        src_conn_name = self.cmb_sdb_src_conn.currentText()
        src_db        = self.cmb_sdb_src_db.currentText()
        dst_conn_name = self.cmb_sdb_dst_conn.currentText()
        dst_db        = self.cmb_sdb_dst_db.currentText()

        if not all([src_conn_name, src_db, dst_conn_name, dst_db]):
            QMessageBox.warning(self, "提示", "请完整填写源库和目标库信息")
            return

        src_conn = self._conns.get(src_conn_name)
        dst_conn = self._conns.get(dst_conn_name)
        if not src_conn or not dst_conn:
            QMessageBox.warning(self, "提示", "连接不存在，请先建立数据库连接")
            return

        # 获取选中的表
        selected = [self.sdb_tbl_list.item(i).text()
                    for i in range(self.sdb_tbl_list.count())
                    if self.sdb_tbl_list.item(i).isSelected()]
        if not selected:
            # 未选则加载全部
            try:
                selected = src_conn.get_tables(src_db)
            except Exception as e:
                QMessageBox.critical(self, "错误", f"获取表列表失败：{e}")
                return

        mode_text = self.cmb_db_mode.currentText()
        mode = "overwrite" if "overwrite" in mode_text else "append"

        self._engine.reset()
        self._set_busy(True)
        self.progress.setMaximum(len(selected))
        self.log_box.clear()
        self._append_log(f"{Icon.char('play')} 开始库同步：{src_conn_name}.{src_db} → {dst_conn_name}.{dst_db}（{len(selected)} 张表）")

        worker = _DbSyncWorker(
            self._engine, self._signals,
            src_conn, src_db, dst_conn, dst_db,
            selected, mode, self.spin_db_batch.value(),
        )
        self._worker = worker
        worker.start()

    def _start_sync(self, cfg: SyncConfig):
        self._engine.reset()
        self._set_busy(True)
        self.progress.setMaximum(0)
        self.log_box.clear()
        self._append_log(
            f"{Icon.char('play')} 开始同步：{cfg.src_db}.{cfg.src_table} → {cfg.dst_db}.{cfg.dst_table}"
            f"（模式：{cfg.mode}）"
        )
        worker = _SyncWorker(self._engine, cfg, self._signals)
        self._worker = worker
        worker.start()

    def _on_stop(self):
        self._engine.stop()
        self._append_log(f"{Icon.char('stop')} 正在停止…")

    def _set_busy(self, busy: bool):
        self.btn_tbl_sync.setEnabled(not busy)
        self.btn_tbl_stop.setEnabled(busy)
        self.btn_db_sync.setEnabled(not busy)
        self.btn_db_stop.setEnabled(busy)

    # ── 信号槽 ──────────────────────────────────────
    def _on_log(self, msg: str):
        self._append_log(msg)

    def _on_progress(self, done: int, total: int, message: str):
        if total > 0:
            self.progress.setMaximum(total)
            self.progress.setValue(done)
        if message:
            self._append_log(message)

    def _on_finished(self):
        self._set_busy(False)
        self.progress.setMaximum(100)
        self.progress.setValue(100)
        self._append_log(f"{Icon.char('success')} 同步任务结束")

    def _append_log(self, msg: str):
        self.log_box.append(wrap_pua(msg))
        self.log_box.verticalScrollBar().setValue(
            self.log_box.verticalScrollBar().maximum()
        )