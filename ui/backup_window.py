"""
backup_window.py
数据库备份与恢复管理窗口
- 备份标签页：选择连接/库/表，设置输出目录，开始备份
- 备份记录标签页：查看历史备份，恢复/删除/打开文件夹
"""
import os
import threading
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTabWidget, QWidget,
    QLabel, QComboBox, QPushButton, QProgressBar, QTextEdit,
    QGroupBox, QFormLayout, QCheckBox, QListWidget, QListWidgetItem,
    QAbstractItemView, QSplitter, QFrame, QMessageBox, QLineEdit,
    QSizePolicy, QTableWidget, QTableWidgetItem, QHeaderView,
    QFileDialog, QRadioButton, QButtonGroup, QScrollArea,
)
from PySide6.QtCore import Qt, QThread, Signal, QObject, QMetaObject, Q_ARG
from PySide6.QtGui import QFont, QColor

from core.platform_utils import get_default_backup_dir, open_folder
from core.backup_engine import (
    BackupEngine, BackupConfig, BackupProgress,
    BackupRecord, load_backup_records, delete_backup_record,
)
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


# ── 信号转发 ────────────────────────────────────────────────────
class _BackupSignals(QObject):
    log       = Signal(str)
    progress  = Signal(int, int, str)   # (done, total, message)
    finished  = Signal(object)          # BackupRecord or None


class _RestoreSignals(QObject):
    log       = Signal(str)
    progress  = Signal(int, int, str)
    finished  = Signal()


# ── 后台备份线程 ─────────────────────────────────────────────────
class _BackupWorker(QThread):
    def __init__(self, engine: BackupEngine, cfg: BackupConfig, signals: _BackupSignals):
        super().__init__()
        self._engine  = engine
        self._cfg     = cfg
        self._signals = signals

    def run(self):
        def on_progress(prog: BackupProgress):
            self._signals.progress.emit(prog.done, prog.total, prog.message)

        def on_log(msg: str):
            self._signals.log.emit(msg)

        record = self._engine.backup(self._cfg, on_progress=on_progress, on_log=on_log)
        self._signals.finished.emit(record)


# ── 后台恢复线程 ─────────────────────────────────────────────────
class _RestoreWorker(QThread):
    def __init__(
        self, engine: BackupEngine, connector: DatabaseConnector,
        sql_file: str, signals: _RestoreSignals
    ):
        super().__init__()
        self._engine    = engine
        self._connector = connector
        self._sql_file  = sql_file
        self._signals   = signals

    def run(self):
        def on_progress(prog: BackupProgress):
            self._signals.progress.emit(prog.done, prog.total, prog.message)

        def on_log(msg: str):
            self._signals.log.emit(msg)

        self._engine.restore(
            self._connector, self._sql_file,
            on_progress=on_progress, on_log=on_log
        )
        self._signals.finished.emit()


# ── 主窗口 ───────────────────────────────────────────────────────
class BackupWindow(QDialog):
    """数据库备份与恢复管理窗口"""

    def __init__(self, parent=None, connectors: dict = None):
        """
        connectors: {conn_name: DatabaseConnector} 字典，传入当前所有已连接的连接器
        """
        super().__init__(parent)
        # 无边框窗口设置
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setWindowTitle("数据库备份与恢复")
        self.setMinimumSize(860, 620)
        self.resize(960, 680)

        self._connectors: dict = connectors or {}
        self._engine = BackupEngine()
        self._backup_worker: _BackupWorker = None
        self._restore_worker: _RestoreWorker = None
        self._theme = load_theme()
        self._tokens = get_theme_tokens(self._theme)
        # 先创建标题栏（必须在 _build_ui 之前）
        self._title_bar, self._title_lbl, self._title_close_btn = make_frameless_title_bar(
            self, "数据库备份与恢复", self._tokens)
        self._title_close_btn.clicked.connect(self.close)

        self._build_ui()
        self._load_records()

    # ── UI 构建 ──────────────────────────────────────────────────
    def _build_ui(self):
        frame, frame_layout, inner = build_dialog_frame(self._tokens, self, self._title_bar)
        inner_layout = QVBoxLayout(inner)
        inner_layout.setContentsMargins(14, 14, 14, 14)
        inner_layout.setSpacing(0)

        tabs = QTabWidget()
        tabs.addTab(self._build_backup_tab(),  Icon.prefixed_text('archive', "备份"))
        tabs.addTab(self._build_records_tab(), Icon.prefixed_text('table', "备份记录"))
        tabs.addTab(self._build_restore_tab(), Icon.prefixed_text('refresh', "还原"))
        inner_layout.addWidget(tabs)

    # ── 备份标签页 ────────────────────────────────────────────────
    def _build_backup_tab(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setSpacing(10)

        # ── 连接 & 库 选择 ──────────────────────────────────────
        src_group = QGroupBox("备份来源")
        src_form  = QFormLayout(src_group)
        src_form.setSpacing(8)

        self.cb_conn = QComboBox()
        self.cb_conn.addItems(list(self._connectors.keys()))
        self.cb_conn.currentTextChanged.connect(self._on_conn_changed)
        src_form.addRow("连接：", self.cb_conn)

        self.cb_db = QComboBox()
        self.cb_db.currentTextChanged.connect(self._on_db_changed)
        src_form.addRow("数据库：", self.cb_db)

        layout.addWidget(src_group)

        # ── 表选择 ────────────────────────────────────────────
        table_group = QGroupBox("选择备份表（不选 = 备份全部）")
        table_layout = QVBoxLayout(table_group)

        ctrl_row = QHBoxLayout()
        btn_all  = QPushButton("全选")
        btn_none = QPushButton("全不选")
        btn_all.setFixedWidth(70)
        btn_none.setFixedWidth(70)
        btn_all.clicked.connect(self._select_all_tables)
        btn_none.clicked.connect(self._select_none_tables)
        ctrl_row.addWidget(btn_all)
        ctrl_row.addWidget(btn_none)
        ctrl_row.addStretch()
        table_layout.addLayout(ctrl_row)

        self.list_tables = QListWidget()
        self.list_tables.setSelectionMode(QAbstractItemView.SelectionMode.MultiSelection)
        self.list_tables.setFixedHeight(130)
        table_layout.addWidget(self.list_tables)
        layout.addWidget(table_group)

        # ── 备份选项 ──────────────────────────────────────────
        opt_group  = QGroupBox("备份选项")
        opt_layout = QFormLayout(opt_group)

        # 备份内容
        self.rb_full   = QRadioButton("结构 + 数据")
        self.rb_schema = QRadioButton("仅结构")
        self.rb_full.setChecked(True)
        rb_row = QHBoxLayout()
        rb_row.addWidget(self.rb_full)
        rb_row.addWidget(self.rb_schema)
        rb_row.addStretch()
        opt_layout.addRow("备份内容：", rb_row)

        # 输出目录
        dir_row = QHBoxLayout()
        self.txt_backup_dir = QLineEdit()
        default_dir = get_default_backup_dir()
        self.txt_backup_dir.setText(default_dir)
        btn_browse = QPushButton("浏览…")
        btn_browse.setFixedWidth(70)
        btn_browse.clicked.connect(self._browse_backup_dir)
        dir_row.addWidget(self.txt_backup_dir)
        dir_row.addWidget(btn_browse)
        opt_layout.addRow("保存目录：", dir_row)

        layout.addWidget(opt_group)

        # ── 进度 & 日志 ───────────────────────────────────────
        self.progress_bar_bk = QProgressBar()
        self.progress_bar_bk.setValue(0)
        layout.addWidget(self.progress_bar_bk)

        self.log_area_bk = QTextEdit()
        self.log_area_bk.setReadOnly(True)
        self.log_area_bk.setFixedHeight(120)
        self.log_area_bk.setStyleSheet(get_log_box_style(self._theme))
        layout.addWidget(self.log_area_bk)


        # ── 按钮行 ────────────────────────────────────────────
        btn_row = QHBoxLayout()
        self.btn_start = QPushButton(Icon.prefixed_text('play', "开始备份"))
        self.btn_start.setProperty("role", "primary")
        self.btn_start.setFixedHeight(34)
        self.btn_stop_bk = QPushButton(Icon.prefixed_text('stop', "停止"))
        self.btn_stop_bk.setProperty("role", "danger")
        self.btn_stop_bk.setFixedHeight(34)

        self.btn_stop_bk.setEnabled(False)

        self.btn_start.clicked.connect(self._start_backup)
        self.btn_stop_bk.clicked.connect(self._stop_backup)

        btn_row.addStretch()
        btn_row.addWidget(self.btn_stop_bk)
        btn_row.addWidget(self.btn_start)
        layout.addLayout(btn_row)

        # 初始化连接列表
        if self._connectors:
            self._on_conn_changed(self.cb_conn.currentText())

        return w

    # ── 备份记录标签页 ────────────────────────────────────────────
    def _build_records_tab(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setSpacing(8)

        # 工具栏
        tb = QHBoxLayout()
        btn_refresh = QPushButton(Icon.prefixed_text('refresh', "刷新"))
        btn_refresh.setFixedWidth(80)
        btn_refresh.clicked.connect(self._load_records)
        btn_open_folder = QPushButton(Icon.prefixed_text('folder_open', "打开目录"))
        btn_open_folder.setFixedWidth(100)
        btn_open_folder.clicked.connect(self._open_record_folder)
        self.btn_del_record = QPushButton(Icon.prefixed_text('delete', "删除记录"))
        self.btn_del_record.setFixedWidth(100)
        self.btn_del_record.clicked.connect(self._delete_record)
        tb.addWidget(btn_refresh)
        tb.addWidget(btn_open_folder)
        tb.addWidget(self.btn_del_record)
        tb.addStretch()
        layout.addLayout(tb)

        # 记录表
        self.tbl_records = QTableWidget(0, 6)
        self.tbl_records.setHorizontalHeaderLabels(
            ["数据库", "备份时间", "文件大小", "表数量", "包含数据", "状态"]
        )
        self.tbl_records.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.tbl_records.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.tbl_records.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.tbl_records.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.tbl_records.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        self.tbl_records.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
        self.tbl_records.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.tbl_records.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.tbl_records.setAlternatingRowColors(True)
        layout.addWidget(self.tbl_records)

        # 选中文件路径展示
        self.lbl_record_path = QLabel("选中记录后可还原或打开目录")
        self.lbl_record_path.setWordWrap(True)
        layout.addWidget(self.lbl_record_path)

        self.tbl_records.currentItemChanged.connect(self._on_record_selected)

        return w

    # ── 还原标签页 ────────────────────────────────────────────────
    def _build_restore_tab(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setSpacing(10)

        # 目标连接
        tgt_group = QGroupBox("还原目标")
        tgt_form  = QFormLayout(tgt_group)

        self.cb_restore_conn = QComboBox()
        self.cb_restore_conn.addItems(list(self._connectors.keys()))
        tgt_form.addRow("目标连接：", self.cb_restore_conn)

        layout.addWidget(tgt_group)

        # SQL 文件
        file_group  = QGroupBox("SQL 备份文件")
        file_layout = QVBoxLayout(file_group)

        file_row = QHBoxLayout()
        self.txt_restore_file = QLineEdit()
        self.txt_restore_file.setPlaceholderText("选择 .sql 备份文件路径")
        btn_browse_file = QPushButton("浏览…")
        btn_browse_file.setFixedWidth(70)
        btn_browse_file.clicked.connect(self._browse_restore_file)
        file_row.addWidget(self.txt_restore_file)
        file_row.addWidget(btn_browse_file)
        file_layout.addLayout(file_row)

        self.btn_fill_from_record = QPushButton(Icon.prefixed_text('arrow_left', "从备份记录中填充文件路径"))
        self.btn_fill_from_record.clicked.connect(self._fill_restore_from_record)
        file_layout.addWidget(self.btn_fill_from_record)

        layout.addWidget(file_group)

        # 进度 & 日志
        self.progress_bar_re = QProgressBar()
        self.progress_bar_re.setValue(0)
        layout.addWidget(self.progress_bar_re)

        self.log_area_re = QTextEdit()
        self.log_area_re.setReadOnly(True)
        self.log_area_re.setFixedHeight(150)
        self.log_area_re.setStyleSheet(get_log_box_style(self._theme))
        layout.addWidget(self.log_area_re)


        # 按钮行
        btn_row = QHBoxLayout()
        self.btn_restore_sel = QPushButton(Icon.prefixed_text('play', "开始还原"))
        self.btn_restore_sel.setProperty("role", "success")
        self.btn_restore_sel.setFixedHeight(34)
        self.btn_stop_re = QPushButton(Icon.prefixed_text('stop', "停止"))
        self.btn_stop_re.setProperty("role", "danger")
        self.btn_stop_re.setFixedHeight(34)

        self.btn_stop_re.setEnabled(False)

        self.btn_restore_sel.clicked.connect(self._start_restore)
        self.btn_stop_re.clicked.connect(self._stop_restore)

        btn_row.addStretch()
        btn_row.addWidget(self.btn_stop_re)
        btn_row.addWidget(self.btn_restore_sel)
        layout.addLayout(btn_row)
        layout.addStretch()

        return w

    # ── 事件：连接切换 ────────────────────────────────────────────
    def _on_conn_changed(self, conn_name: str):
        self.cb_db.blockSignals(True)
        self.cb_db.clear()
        conn = self._connectors.get(conn_name)
        if conn:
            try:
                dbs = conn.get_databases()
                self.cb_db.addItems(dbs)
            except Exception:
                pass
        self.cb_db.blockSignals(False)
        self._on_db_changed(self.cb_db.currentText())

    def _on_db_changed(self, db_name: str):
        self.list_tables.clear()
        if not db_name:
            return
        conn_name = self.cb_conn.currentText()
        conn = self._connectors.get(conn_name)
        if conn:
            try:
                tables = conn.get_tables(db_name)
                for t in tables:
                    item = QListWidgetItem(t)
                    self.list_tables.addItem(item)
            except Exception:
                pass

    def _select_all_tables(self):
        for i in range(self.list_tables.count()):
            self.list_tables.item(i).setSelected(True)

    def _select_none_tables(self):
        self.list_tables.clearSelection()

    def _browse_backup_dir(self):
        d = QFileDialog.getExistingDirectory(self, "选择备份目录", self.txt_backup_dir.text())
        if d:
            self.txt_backup_dir.setText(d)

    def _browse_restore_file(self):
        f, _ = QFileDialog.getOpenFileName(
            self, "选择 SQL 文件", "", "SQL 文件 (*.sql);;所有文件 (*.*)"
        )
        if f:
            self.txt_restore_file.setText(f)

    # ── 开始备份 ──────────────────────────────────────────────────
    def _start_backup(self):
        conn_name = self.cb_conn.currentText()
        db_name   = self.cb_db.currentText()
        conn      = self._connectors.get(conn_name)

        if not conn:
            QMessageBox.warning(self, "提示", "请先在主窗口建立并打开数据库连接")
            return
        if not db_name:
            QMessageBox.warning(self, "提示", "请选择要备份的数据库")
            return

        backup_dir = self.txt_backup_dir.text().strip()
        if not backup_dir:
            QMessageBox.warning(self, "提示", "请设置备份文件保存目录")
            return

        # 获取选中表
        selected = [self.list_tables.item(i).text()
                    for i in range(self.list_tables.count())
                    if self.list_tables.item(i).isSelected()]

        cfg = BackupConfig(
            connector    = conn,
            db_name      = db_name,
            tables       = selected,
            include_data = self.rb_full.isChecked(),
            backup_dir   = backup_dir,
            file_prefix  = db_name,
        )

        self.log_area_bk.clear()
        self.progress_bar_bk.setValue(0)
        self.btn_start.setEnabled(False)
        self.btn_stop_bk.setEnabled(True)

        signals = _BackupSignals()
        signals.log.connect(lambda msg: self._append_log(self.log_area_bk, msg))
        signals.progress.connect(self._on_backup_progress)
        signals.finished.connect(self._on_backup_finished)

        self._backup_worker = _BackupWorker(self._engine, cfg, signals)
        self._backup_worker.start()

    def _stop_backup(self):
        self._engine.stop()
        self.btn_stop_bk.setEnabled(False)

    def _on_backup_progress(self, done: int, total: int, msg: str):
        if total > 0:
            self.progress_bar_bk.setMaximum(total)
            self.progress_bar_bk.setValue(done)

    def _on_backup_finished(self, record):
        self.progress_bar_bk.setValue(self.progress_bar_bk.maximum())
        self.btn_start.setEnabled(True)
        self.btn_stop_bk.setEnabled(False)
        if record:
            self._load_records()

    # ── 开始还原 ──────────────────────────────────────────────────
    def _start_restore(self):
        conn_name = self.cb_restore_conn.currentText()
        conn      = self._connectors.get(conn_name)
        sql_file  = self.txt_restore_file.text().strip()

        if not conn:
            QMessageBox.warning(self, "提示", "请先在主窗口建立并打开数据库连接")
            return
        if not sql_file or not os.path.exists(sql_file):
            QMessageBox.warning(self, "提示", "请选择有效的 SQL 备份文件")
            return

        reply = QMessageBox.question(
            self, "确认还原",
            f"将从以下文件还原数据：\n{sql_file}\n\n目标连接：{conn_name}\n\n{Icon.styled_char('warning')} 此操作可能覆盖已有数据，确认继续？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        self.log_area_re.clear()
        self.progress_bar_re.setValue(0)
        self.btn_restore_sel.setEnabled(False)
        self.btn_stop_re.setEnabled(True)

        signals = _RestoreSignals()
        signals.log.connect(lambda msg: self._append_log(self.log_area_re, msg))
        signals.progress.connect(self._on_restore_progress)
        signals.finished.connect(self._on_restore_finished)

        self._restore_worker = _RestoreWorker(
            BackupEngine(), conn, sql_file, signals
        )
        self._restore_worker.start()

    def _stop_restore(self):
        if self._restore_worker:
            # BackupEngine 的 stop 已在 worker 里持有
            pass
        self.btn_stop_re.setEnabled(False)

    def _on_restore_progress(self, done: int, total: int, msg: str):
        if total > 0:
            self.progress_bar_re.setMaximum(total)
            self.progress_bar_re.setValue(done)

    def _on_restore_finished(self):
        self.progress_bar_re.setValue(self.progress_bar_re.maximum())
        self.btn_restore_sel.setEnabled(True)
        self.btn_stop_re.setEnabled(False)

    # ── 备份记录管理 ──────────────────────────────────────────────
    def _load_records(self):
        records = load_backup_records()
        self.tbl_records.setRowCount(0)
        self._records = records

        for r in records:
            row = self.tbl_records.rowCount()
            self.tbl_records.insertRow(row)
            self.tbl_records.setItem(row, 0, QTableWidgetItem(r.db_name))
            self.tbl_records.setItem(row, 1, QTableWidgetItem(r.created_at))
            self.tbl_records.setItem(row, 2, QTableWidgetItem(r.size_str()))
            self.tbl_records.setItem(row, 3, QTableWidgetItem(str(len(r.tables))))
            self.tbl_records.setItem(row, 4, QTableWidgetItem("是" if r.include_data else "否"))
            exists = os.path.exists(r.file_path)
            status_item = QTableWidgetItem("文件存在" if exists else f"{Icon.styled_char('warning')} 文件缺失")
            if not exists:
                status_item.setForeground(QColor(self._tokens["danger"]))
            self.tbl_records.setItem(row, 5, status_item)

    def _on_record_selected(self, current, previous):
        if not current:
            return
        row = current.row()
        if row < len(self._records):
            r = self._records[row]
            self.lbl_record_path.setText(f"文件路径：{r.file_path}")

    def _open_record_folder(self):
        row = self.tbl_records.currentRow()
        if row < 0 or row >= len(self._records):
            QMessageBox.information(self, "提示", "请先选择一条备份记录")
            return
        r = self._records[row]
        folder = os.path.dirname(r.file_path)
        if not open_folder(folder):
            QMessageBox.warning(self, "提示", f"目录不存在：{folder}")

    def _delete_record(self):
        row = self.tbl_records.currentRow()
        if row < 0 or row >= len(self._records):
            QMessageBox.information(self, "提示", "请先选择一条备份记录")
            return
        r = self._records[row]
        reply = QMessageBox.question(
            self, "确认删除",
            f"删除备份记录：{r.db_name}（{r.created_at}）\n（仅删除记录，不删除文件）",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            delete_backup_record(r.record_id)
            self._load_records()

    def _fill_restore_from_record(self):
        row = self.tbl_records.currentRow()
        if row < 0 or row >= len(self._records):
            QMessageBox.information(self, "提示", "请先在「备份记录」标签页选择一条记录")
            return
        r = self._records[row]
        self.txt_restore_file.setText(r.file_path)

    # ── 工具 ──────────────────────────────────────────────────────
    @staticmethod
    def _append_log(log_widget: QTextEdit, msg: str):
        log_widget.append(wrap_pua(msg))
        bar = log_widget.verticalScrollBar()
        bar.setValue(bar.maximum())