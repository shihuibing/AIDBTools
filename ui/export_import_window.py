"""
export_import_window.py
数据导出 / 导入功能窗口
导出：CSV、Excel(.xlsx)、SQL INSERT 语句
导入：CSV 文件 → 写入指定表、SQL 文件 → 逐条执行
"""
import csv
import io
import os
import datetime
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTabWidget, QWidget,
    QLabel, QComboBox, QPushButton, QLineEdit, QFileDialog,
    QProgressBar, QTextEdit, QGroupBox, QCheckBox, QSpinBox,
    QMessageBox, QFormLayout, QSizePolicy,
)
from PySide6.QtCore import Qt, QRunnable, QObject, QThreadPool, Signal
from PySide6.QtGui import QFont
from ui.iconfont_loader import Icon, wrap_pua
from ui.theme_manager import (
    load_theme, get_theme_tokens, get_log_box_style, build_popup_base_style,
    build_dialog_frame,
    build_frameless_dialog_style, make_frameless_title_bar,
)






# ─── 后台线程信号 ────────────────────────────────
class _WorkerSignals(QObject):
    progress = Signal(int)        # 0-100
    log      = Signal(str)        # 日志文本
    finished = Signal(bool, str)  # 成功?, 消息


class _ExportWorker(QRunnable):
    def __init__(self, connector, table: str, fmt: str,
                 filepath: str, limit: int, signals: _WorkerSignals):
        super().__init__()
        self.connector = connector
        self.table     = table
        self.fmt       = fmt        # 'csv' | 'excel' | 'sql'
        self.filepath  = filepath
        self.limit     = limit      # 0 = 不限
        self.signals   = signals

    def run(self):
        try:
            limit_clause = f" LIMIT {self.limit}" if self.limit > 0 else ""
            sql = f"SELECT * FROM `{self.table}`{limit_clause}"
            cols, rows = self.connector.execute(sql)
            if not cols:
                self.signals.finished.emit(False, "表中无数据或无法获取列信息")
                return

            self.signals.progress.emit(20)
            self.signals.log.emit(f"查询到 {len(rows)} 行，{len(cols)} 列")

            if self.fmt == "csv":
                self._export_csv(cols, rows)
            elif self.fmt == "excel":
                self._export_excel(cols, rows)
            elif self.fmt == "sql":
                self._export_sql(cols, rows)

            self.signals.progress.emit(100)
            self.signals.finished.emit(True, f"导出完成：{self.filepath}")
        except Exception as e:
            self.signals.finished.emit(False, f"导出失败：{str(e)}")

    def _export_csv(self, cols, rows):
        with open(self.filepath, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.writer(f)
            writer.writerow(cols)
            total = len(rows)
            for i, row in enumerate(rows):
                writer.writerow([str(v) if v is not None else "" for v in row])
                if total > 0:
                    self.signals.progress.emit(20 + int(80 * (i + 1) / total))
        self.signals.log.emit(f"CSV 已写入 {self.filepath}")

    def _export_excel(self, cols, rows):
        try:
            import openpyxl
        except ImportError:
            raise RuntimeError("需要安装 openpyxl：pip install openpyxl")
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = self.table[:31]  # sheet 名最长31
        ws.append(list(cols))
        total = len(rows)
        for i, row in enumerate(rows):
            ws.append([str(v) if v is not None else "" for v in row])
            if total > 0:
                self.signals.progress.emit(20 + int(80 * (i + 1) / total))
        wb.save(self.filepath)
        self.signals.log.emit(f"Excel 已写入 {self.filepath}")

    def _export_sql(self, cols, rows):
        col_names = ", ".join(f"`{c}`" for c in cols)
        total = len(rows)
        with open(self.filepath, "w", encoding="utf-8") as f:
            f.write(f"-- 导出时间: {datetime.datetime.now()}\n")
            f.write(f"-- 表名: {self.table}\n-- 总行数: {total}\n\n")
            for i, row in enumerate(rows):
                vals = []
                for v in row:
                    if v is None:
                        vals.append("NULL")
                    elif isinstance(v, (int, float)):
                        vals.append(str(v))
                    else:
                        escaped = str(v).replace("'", "''")
                        vals.append(f"'{escaped}'")
                val_str = ", ".join(vals)
                f.write(f"INSERT INTO `{self.table}` ({col_names}) VALUES ({val_str});\n")
                if total > 0:
                    self.signals.progress.emit(20 + int(80 * (i + 1) / total))
        self.signals.log.emit(f"SQL 已写入 {self.filepath}")


class _ImportWorker(QRunnable):
    def __init__(self, connector, table: str, fmt: str,
                 filepath: str, has_header: bool, signals: _WorkerSignals):
        super().__init__()
        self.connector  = connector
        self.table      = table
        self.fmt        = fmt         # 'csv' | 'sql'
        self.filepath   = filepath
        self.has_header = has_header
        self.signals    = signals

    def run(self):
        try:
            if self.fmt == "csv":
                self._import_csv()
            elif self.fmt == "sql":
                self._import_sql()
            self.signals.finished.emit(True, "导入完成")
        except Exception as e:
            self.signals.finished.emit(False, f"导入失败：{str(e)}")

    def _import_csv(self):
        with open(self.filepath, "r", encoding="utf-8-sig", errors="replace") as f:
            reader = csv.reader(f)
            rows_all = list(reader)

        if not rows_all:
            raise ValueError("CSV 文件为空")

        if self.has_header:
            headers = rows_all[0]
            data_rows = rows_all[1:]
        else:
            # 无 header 时从表结构获取列名
            cols_sql = f"SELECT * FROM `{self.table}` LIMIT 0"
            cols, _ = self.connector.execute(cols_sql)
            if not cols:
                raise ValueError("无法获取表结构，请确认表名正确")
            headers = cols
            data_rows = rows_all

        col_names = ", ".join(f"`{c}`" for c in headers)
        total = len(data_rows)
        self.signals.log.emit(f"共 {total} 行待导入…")

        for i, row in enumerate(data_rows):
            if len(row) != len(headers):
                self.signals.log.emit(f"  第 {i+2} 行列数不匹配，跳过")
                continue
            vals = []
            for v in row:
                if v.strip() == "" or v.strip().upper() == "NULL":
                    vals.append("NULL")
                else:
                    escaped = v.replace("'", "''")
                    vals.append(f"'{escaped}'")
            val_str = ", ".join(vals)
            sql = f"INSERT INTO `{self.table}` ({col_names}) VALUES ({val_str})"
            self.connector.execute(sql)
            if total > 0:
                self.signals.progress.emit(int(100 * (i + 1) / total))

        self.signals.log.emit(f"{Icon.char('success')} 成功导入 {total} 行到 {self.table}")

    def _import_sql(self):
        with open(self.filepath, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()

        from core.connection import DatabaseConnector
        stmts = DatabaseConnector._split_statements(content)
        # 过滤注释
        stmts = [s for s in stmts
                 if not all(l.strip().startswith('--') or l.strip() == ''
                            for l in s.splitlines())]
        total = len(stmts)
        self.signals.log.emit(f"共 {total} 条语句待执行…")
        ok = 0
        for i, stmt in enumerate(stmts):
            try:
                self.connector.execute(stmt)
                ok += 1
            except Exception as e:
                self.signals.log.emit(f"  第 {i+1} 条执行失败：{str(e)[:80]}")
            self.signals.progress.emit(int(100 * (i + 1) / total))
        self.signals.log.emit(f"{Icon.char('success')} 执行完毕：成功 {ok}/{total} 条")


# ─── 主窗口 ──────────────────────────────────────
class ExportImportWindow(QDialog):
    """数据导出/导入对话框"""

    def __init__(self, parent=None, connector=None, current_table: str = ""):
        super().__init__(parent)
        # 无边框窗口设置
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setWindowTitle("数据导出 / 导入")
        self.resize(620, 500)
        self.setMinimumSize(540, 420)
        self.connector = connector
        self._current_table = current_table
        self._theme = load_theme()
        self._tokens = get_theme_tokens(self._theme)
        # 先创建标题栏（必须在 _init_ui 之前）
        self._title_bar, self._title_lbl, self._title_close_btn = make_frameless_title_bar(
            self, "数据导出 / 导入", self._tokens)
        self._title_close_btn.clicked.connect(self.close)
        self._init_ui()
        self._apply_theme_styles()
        self._refresh_tables()

    def _init_ui(self):
        frame, frame_layout, inner = build_dialog_frame(self._tokens, self, self._title_bar)
        inner_layout = QVBoxLayout(inner)
        inner_layout.setContentsMargins(12, 12, 12, 12)
        inner_layout.setSpacing(8)

        self.tabs = QTabWidget()
        self.tabs.addTab(self._build_export_tab(), Icon.prefixed_text('upload', "导出数据"))
        self.tabs.addTab(self._build_import_tab(), Icon.prefixed_text('download', "导入数据"))
        inner_layout.addWidget(self.tabs)

        # 日志区
        self.log_group = QGroupBox("执行日志")
        log_lay = QVBoxLayout(self.log_group)
        self.log_box = QTextEdit()
        self.log_box.setReadOnly(True)
        self.log_box.setFont(QFont("Consolas", 9))
        self.log_box.setMaximumHeight(110)
        self.log_box.setStyleSheet(get_log_box_style(self._theme))
        log_lay.addWidget(self.log_box)
        inner_layout.addWidget(self.log_group)

        # 进度条
        self.progress = QProgressBar()
        self.progress.setValue(0)
        self.progress.setFixedHeight(16)
        inner_layout.addWidget(self.progress)

    def _apply_theme_styles(self):
        self.log_box.setStyleSheet(get_log_box_style(self._theme))
        if hasattr(self, "btn_export"):
            self.btn_export.setProperty("role", "primary")
            self.btn_export.style().unpolish(self.btn_export)
            self.btn_export.style().polish(self.btn_export)
        if hasattr(self, "btn_import"):
            self.btn_import.setProperty("role", "success")
            self.btn_import.style().unpolish(self.btn_import)
            self.btn_import.style().polish(self.btn_import)


    def _build_export_tab(self):
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setSpacing(10)

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        # 表选择
        self.exp_table = QComboBox()
        self.exp_table.setMinimumWidth(220)
        form.addRow("选择表：", self.exp_table)

        # 格式
        self.exp_fmt = QComboBox()
        self.exp_fmt.addItems(["CSV (.csv)", "Excel (.xlsx)", "SQL INSERT (.sql)"])
        form.addRow("导出格式：", self.exp_fmt)

        # 限制行数
        limit_row = QHBoxLayout()
        self.exp_limit_chk = QCheckBox("限制行数")
        self.exp_limit_spin = QSpinBox()
        self.exp_limit_spin.setRange(1, 10_000_000)
        self.exp_limit_spin.setValue(10000)
        self.exp_limit_spin.setEnabled(False)
        self.exp_limit_chk.toggled.connect(self.exp_limit_spin.setEnabled)
        limit_row.addWidget(self.exp_limit_chk)
        limit_row.addWidget(self.exp_limit_spin)
        limit_row.addStretch()
        form.addRow("行数限制：", limit_row)

        # 保存路径
        path_row = QHBoxLayout()
        self.exp_path = QLineEdit()
        self.exp_path.setPlaceholderText("点击右侧按钮选择保存路径…")
        btn_browse = QPushButton("浏览…")
        btn_browse.setFixedWidth(70)
        btn_browse.clicked.connect(self._browse_export_path)
        path_row.addWidget(self.exp_path)
        path_row.addWidget(btn_browse)
        form.addRow("保存路径：", path_row)

        lay.addLayout(form)
        lay.addStretch()

        self.btn_export = QPushButton(Icon.prefixed_text('play', "开始导出"))
        self.btn_export.setFixedHeight(34)
        self.btn_export.clicked.connect(self._on_export)
        lay.addWidget(self.btn_export)

        return w

    def _build_import_tab(self):
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setSpacing(10)

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        # 导入格式
        self.imp_fmt = QComboBox()
        self.imp_fmt.addItems(["CSV 文件 (.csv)", "SQL 文件 (.sql)"])
        self.imp_fmt.currentIndexChanged.connect(self._on_imp_fmt_changed)
        form.addRow("文件格式：", self.imp_fmt)

        # 目标表（CSV 导入时需要）
        self.imp_table_label = QLabel("目标表：")
        self.imp_table = QComboBox()
        self.imp_table.setMinimumWidth(220)
        form.addRow(self.imp_table_label, self.imp_table)

        # CSV header
        self.imp_header_chk = QCheckBox("首行为列名（Header）")
        self.imp_header_chk.setChecked(True)
        form.addRow("CSV选项：", self.imp_header_chk)

        # 文件路径
        path_row = QHBoxLayout()
        self.imp_path = QLineEdit()
        self.imp_path.setPlaceholderText("点击右侧按钮选择文件…")
        btn_browse2 = QPushButton("浏览…")
        btn_browse2.setFixedWidth(70)
        btn_browse2.clicked.connect(self._browse_import_path)
        path_row.addWidget(self.imp_path)
        path_row.addWidget(btn_browse2)
        form.addRow("文件路径：", path_row)

        lay.addLayout(form)
        lay.addStretch()

        self.btn_import = QPushButton(Icon.prefixed_text('play', "开始导入"))
        self.btn_import.setFixedHeight(34)
        self.btn_import.clicked.connect(self._on_import)
        lay.addWidget(self.btn_import)

        return w

    # ── 辅助 ─────────────────────────────────────
    def _refresh_tables(self):
        """刷新表列表"""
        tables = []
        if self.connector:
            try:
                tables = self.connector.get_tables() or []
            except Exception:
                pass
        self.exp_table.clear()
        self.imp_table.clear()
        for t in tables:
            self.exp_table.addItem(t)
            self.imp_table.addItem(t)
        if self._current_table:
            idx = self.exp_table.findText(self._current_table)
            if idx >= 0:
                self.exp_table.setCurrentIndex(idx)
            idx2 = self.imp_table.findText(self._current_table)
            if idx2 >= 0:
                self.imp_table.setCurrentIndex(idx2)

    def _on_imp_fmt_changed(self, idx):
        is_csv = (idx == 0)
        self.imp_table.setVisible(is_csv)
        self.imp_table_label.setVisible(is_csv)
        self.imp_header_chk.setVisible(is_csv)

    def _browse_export_path(self):
        fmt_idx = self.exp_fmt.currentIndex()
        exts = [("CSV 文件", "*.csv"), ("Excel 文件", "*.xlsx"), ("SQL 文件", "*.sql")]
        name_filter = f"{exts[fmt_idx][0]} ({exts[fmt_idx][1]})"
        table = self.exp_table.currentText() or "export"
        default = f"{table}_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}"
        path, _ = QFileDialog.getSaveFileName(self, "选择保存路径",
                                              default, name_filter)
        if path:
            self.exp_path.setText(path)

    def _browse_import_path(self):
        fmt_idx = self.imp_fmt.currentIndex()
        if fmt_idx == 0:
            name_filter = "CSV 文件 (*.csv)"
        else:
            name_filter = "SQL 文件 (*.sql)"
        path, _ = QFileDialog.getOpenFileName(self, "选择导入文件", "", name_filter)
        if path:
            self.imp_path.setText(path)

    def _log(self, msg: str):
        self.log_box.append(wrap_pua(msg))
        self.log_box.verticalScrollBar().setValue(
            self.log_box.verticalScrollBar().maximum()
        )

    # ── 导出 ─────────────────────────────────────
    def _on_export(self):
        if not self.connector:
            QMessageBox.warning(self, "提示", "请先在主窗口连接数据库")
            return
        table = self.exp_table.currentText()
        if not table:
            QMessageBox.warning(self, "提示", "请选择要导出的表")
            return
        filepath = self.exp_path.text().strip()
        if not filepath:
            QMessageBox.warning(self, "提示", "请选择保存路径")
            return

        fmt_map = {0: "csv", 1: "excel", 2: "sql"}
        fmt = fmt_map[self.exp_fmt.currentIndex()]
        limit = self.exp_limit_spin.value() if self.exp_limit_chk.isChecked() else 0

        self.progress.setValue(0)
        self._log(f"{Icon.char('play')} 开始导出：{table} → {fmt.upper()} → {filepath}")

        signals = _WorkerSignals()
        signals.progress.connect(self.progress.setValue)
        signals.log.connect(self._log)
        signals.finished.connect(self._on_worker_done)

        worker = _ExportWorker(self.connector, table, fmt, filepath, limit, signals)
        QThreadPool.globalInstance().start(worker)

    # ── 导入 ─────────────────────────────────────
    def _on_import(self):
        if not self.connector:
            QMessageBox.warning(self, "提示", "请先在主窗口连接数据库")
            return
        filepath = self.imp_path.text().strip()
        if not filepath or not os.path.exists(filepath):
            QMessageBox.warning(self, "提示", "请选择有效的文件路径")
            return

        fmt_idx = self.imp_fmt.currentIndex()
        fmt = "csv" if fmt_idx == 0 else "sql"
        table = self.imp_table.currentText() if fmt == "csv" else ""
        has_header = self.imp_header_chk.isChecked()

        if fmt == "csv" and not table:
            QMessageBox.warning(self, "提示", "CSV 导入请选择目标表")
            return

        self.progress.setValue(0)
        self._log(f"{Icon.char('play')} 开始导入：{filepath} → {fmt.upper()}" +
                  (f" → {table}" if table else ""))

        signals = _WorkerSignals()
        signals.progress.connect(self.progress.setValue)
        signals.log.connect(self._log)
        signals.finished.connect(self._on_worker_done)

        worker = _ImportWorker(self.connector, table, fmt,
                               filepath, has_header, signals)
        QThreadPool.globalInstance().start(worker)

    def _on_worker_done(self, success: bool, msg: str):
        self._log((Icon.char('success') + " " if success else Icon.char('close_circle') + " ") + msg)
        if success:
            QMessageBox.information(self, "完成", msg)
        else:
            QMessageBox.critical(self, "失败", msg)