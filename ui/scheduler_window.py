"""
scheduler_window.py
定时任务管理窗口
- 查看/新建/编辑/删除/启停定时任务
- 立即执行
- 执行日志
"""
from __future__ import annotations  # Python 3.9 兼容：支持 X | Y 类型注解
import datetime
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QWidget,
    QLabel, QComboBox, QPushButton, QTextEdit,
    QTableWidget, QTableWidgetItem, QHeaderView,
    QGroupBox, QFormLayout, QCheckBox, QSpinBox,
    QMessageBox, QLineEdit, QSizePolicy, QAbstractItemView,
    QTabWidget, QFrame, QTimeEdit, QDialogButtonBox,
    QRadioButton,
)
from PySide6.QtCore import Qt, QTimer, QTime, Signal
from PySide6.QtGui import QFont, QColor

from core.scheduler import (
    TaskScheduler, ScheduledTask,
    TASK_TYPE_SQL, TASK_TYPE_SYNC, TASK_TYPE_EXPORT, TASK_TYPE_BACKUP,
    STATUS_ENABLED, STATUS_DISABLED,
)
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


# ── 任务编辑对话框 ─────────────────────────────────────────────────────────
class _TaskEditDialog(QDialog):
    def __init__(self, parent=None, task: ScheduledTask = None,
                 conn_names: list = None, conns: dict = None):
        super().__init__(parent)
        # 无边框窗口设置
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self._task = task
        self._conn_names = conn_names or []
        self._conns = conns or {}  # {conn_name: connector}
        self._is_new = not task
        self.setWindowTitle("新建定时任务" if self._is_new else "编辑定时任务")
        self.setMinimumSize(560, 480)
        self._theme = load_theme()
        self._tokens = get_theme_tokens(self._theme)
        # 先创建标题栏（必须在 _build_ui 之前）
        title_text = "新建定时任务" if self._is_new else "编辑定时任务"
        self._title_bar, self._title_lbl, self._title_close_btn = make_frameless_title_bar(
            self, title_text, self._tokens)
        self._title_close_btn.clicked.connect(self.reject)
        self._build_ui()

    def _build_ui(self):
        frame, frame_layout, inner = build_dialog_frame(self._tokens, self, self._title_bar)
        inner_layout = QVBoxLayout(inner)
        inner_layout.setContentsMargins(16, 12, 16, 12)
        inner_layout.setSpacing(10)

        form = QFormLayout()
        form.setSpacing(8)

        t = self._task

        # 基础信息
        self.txt_name = QLineEdit(t.name if t else "")
        self.txt_name.setPlaceholderText("任务名称（必填）")
        form.addRow("任务名称 *:", self.txt_name)

        self.txt_desc = QLineEdit(t.description if t else "")
        form.addRow("描述:", self.txt_desc)

        # 任务类型
        self.cmb_type = QComboBox()
        self.cmb_type.addItems(["执行 SQL", "数据同步", "数据导出", "数据库备份"])
        if t:
            type_map = {TASK_TYPE_SQL: 0, TASK_TYPE_SYNC: 1, TASK_TYPE_EXPORT: 2, TASK_TYPE_BACKUP: 3}
            self.cmb_type.setCurrentIndex(type_map.get(t.task_type, 0))
        form.addRow("任务类型:", self.cmb_type)
        self.cmb_type.currentIndexChanged.connect(self._on_type_changed)

        # 连接
        self.cmb_conn = QComboBox()
        self.cmb_conn.addItems(self._conn_names)
        if t and t.conn_name in self._conn_names:
            self.cmb_conn.setCurrentText(t.conn_name)
        form.addRow("数据库连接:", self.cmb_conn)
        self.cmb_conn.currentIndexChanged.connect(self._on_conn_changed_for_db)

        # 数据库（可输入+可选择）
        self.cmb_db = QComboBox()
        self.cmb_db.setEditable(True)
        self.cmb_db.lineEdit().setPlaceholderText("输入或选择数据库名")
        if t:
            self.cmb_db.setCurrentText(t.db_name)
        form.addRow("数据库:", self.cmb_db)

        # 表选择（可输入+可选择，用于备份/导出/同步）
        self.cmb_table = QComboBox()
        self.cmb_table.setEditable(True)
        self.cmb_table.lineEdit().setPlaceholderText("输入或选择表名（留空为全部）")
        if t and t.backup_cfg and t.backup_cfg.get("tables"):
            self.cmb_table.setCurrentText(",".join(t.backup_cfg.get("tables", [])))
        elif t and t.sync_cfg and t.sync_cfg.get("src_table"):
            self.cmb_table.setCurrentText(t.sync_cfg.get("src_table", ""))
        elif t and t.export_cfg and t.export_cfg.get("tables"):
            self.cmb_table.setCurrentText(",".join(t.export_cfg.get("tables", [])))
        self.cmb_table.currentIndexChanged.connect(self._on_db_changed_for_table)
        form.addRow("表（可选）:", self.cmb_table)

        frame_layout.addLayout(form)

        # SQL 内容
        self.lbl_sql = QLabel("SQL 语句（任务类型为「执行 SQL」时有效）:")
        self.lbl_sql.setProperty("role", "title")

        frame_layout.addWidget(self.lbl_sql)
        self.txt_sql = QTextEdit()
        self.txt_sql.setFont(QFont("Consolas", 10))
        self.txt_sql.setPlainText(t.sql if t else "")
        self.txt_sql.setMaximumHeight(120)
        self.txt_sql.setPlaceholderText("-- 在此输入要定时执行的 SQL\nSELECT * FROM table_name;")
        frame_layout.addWidget(self.txt_sql)

        # ── 备份配置（任务类型为「数据库备份」时显示）──────────────────
        self._backup_grp = QGroupBox("备份设置")
        backup_form = QFormLayout(self._backup_grp)
        backup_form.setSpacing(8)

        # 备份内容
        self.rb_backup_full   = QRadioButton("结构 + 数据")
        self.rb_backup_schema = QRadioButton("仅结构")
        self.rb_backup_full.setChecked(
            t.backup_cfg.get("include_data", True) if t and t.backup_cfg else True
        )
        rb_backup_row = QHBoxLayout()
        rb_backup_row.addWidget(self.rb_backup_full)
        rb_backup_row.addWidget(self.rb_backup_schema)
        rb_backup_row.addStretch()
        backup_form.addRow("备份内容：", rb_backup_row)

        # 备份目录
        from core.platform_utils import get_default_backup_dir
        self.txt_backup_dir = QLineEdit(
            t.backup_cfg.get("backup_dir", "") if t and t.backup_cfg else get_default_backup_dir()
        )
        self.txt_backup_dir.setPlaceholderText("留空使用默认备份目录")
        backup_form.addRow("保存目录：", self.txt_backup_dir)

        # 备注
        self.txt_backup_note = QLineEdit(
            t.backup_cfg.get("note", "") if t and t.backup_cfg else ""
        )
        self.txt_backup_note.setPlaceholderText("可选备注说明")
        backup_form.addRow("备注：", self.txt_backup_note)

        frame_layout.addWidget(self._backup_grp)

        # 调度设置
        sched_grp = QGroupBox("调度设置")
        sched_form = QFormLayout(sched_grp)

        self.cmb_sched = QComboBox()
        self.cmb_sched.addItems(["间隔执行", "每天定时", "每周定时", "每月定时"])
        sched_map = {"interval": 0, "daily": 1, "weekly": 2, "monthly": 3}
        if t:
            self.cmb_sched.setCurrentIndex(sched_map.get(t.schedule_type, 0))
        self.cmb_sched.currentIndexChanged.connect(self._on_sched_changed)
        sched_form.addRow("调度方式:", self.cmb_sched)

        # 间隔分钟
        self.spin_interval = QSpinBox()
        self.spin_interval.setRange(1, 10080)  # 最多1周
        self.spin_interval.setValue(t.interval_min if t else 60)
        self.spin_interval.setSuffix(" 分钟")
        sched_form.addRow("执行间隔:", self.spin_interval)

        # 每天时间
        self.time_edit = QTimeEdit()
        daily_time = t.daily_time if t else "00:00"
        try:
            h, m = map(int, daily_time.split(":"))
            self.time_edit.setTime(QTime(h, m))
        except Exception:
            self.time_edit.setTime(QTime(0, 0))
        sched_form.addRow("执行时间:", self.time_edit)

        # 每周几
        self.cmb_weekday = QComboBox()
        self.cmb_weekday.addItems(["周一","周二","周三","周四","周五","周六","周日"])
        self.cmb_weekday.setCurrentIndex(t.weekly_day if t else 0)
        sched_form.addRow("执行日:", self.cmb_weekday)

        # 每月几号
        self.spin_monthday = QSpinBox()
        self.spin_monthday.setRange(1, 28)
        self.spin_monthday.setValue(t.monthly_day if t else 1)
        self.spin_monthday.setSuffix(" 日")
        sched_form.addRow("每月几号:", self.spin_monthday)

        frame_layout.addWidget(sched_grp)

        self._on_sched_changed(self.cmb_sched.currentIndex())
        self._on_type_changed(self.cmb_type.currentIndex())

        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        ok = btns.button(QDialogButtonBox.StandardButton.Ok)
        ok.setText("保存")
        ok.setProperty("role", "primary")

        btns.accepted.connect(self._on_ok)
        btns.rejected.connect(self.reject)
        frame_layout.addWidget(btns)

    def _on_conn_changed_for_db(self, idx: int = 0):
        """连接切换时，尝试拉取该连接下的数据库和表列表"""
        conn_name = self.cmb_conn.currentText()
        connector = self._conns.get(conn_name)
        self.cmb_db.blockSignals(True)
        self.cmb_db.clear()
        self.cmb_table.blockSignals(True)
        self.cmb_table.clear()
        if connector:
            try:
                dbs = connector.get_databases()
                if dbs:
                    self.cmb_db.addItems(dbs)
                    self.cmb_db.setCurrentText(connector._db_name or "")
            except Exception:
                pass  # 无法获取时保持空，由用户手动输入

            # 加载表列表
            self._load_tables_for_current_db(connector)
        self.cmb_db.blockSignals(False)
        self.cmb_table.blockSignals(False)

    def _on_db_changed_for_table(self, idx: int = 0):
        """数据库切换时，重新加载表列表"""
        conn_name = self.cmb_conn.currentText()
        connector = self._conns.get(conn_name)
        if connector:
            self._load_tables_for_current_db(connector)

    def _load_tables_for_current_db(self, connector):
        """加载当前数据库的表列表"""
        self.cmb_table.blockSignals(True)
        self.cmb_table.clear()
        try:
            db_name = self.cmb_db.currentText()
            if db_name and hasattr(connector, 'get_tables'):
                tables = connector.get_tables(db_name)
                if tables:
                    self.cmb_table.addItems(tables)
        except Exception:
            pass
        self.cmb_table.blockSignals(False)

    def _on_sched_changed(self, idx: int):
        self.spin_interval.setVisible(idx == 0)
        self.time_edit.setVisible(idx == 1)
        self.cmb_weekday.setVisible(idx == 2)
        self.spin_monthday.setVisible(idx == 3)

    def _on_type_changed(self, idx: int):
        """根据任务类型切换 SQL / 备份配置区域的可见性"""
        is_backup = (idx == 3)  # 数据库备份
        is_export = (idx == 2)  # 数据导出
        is_sync   = (idx == 1)  # 数据同步
        is_sql    = (idx == 0)  # 执行 SQL

        # SQL 内容：仅 SQL 任务显示
        self.lbl_sql.setVisible(is_sql)
        self.txt_sql.setVisible(is_sql)

        # 备份设置：仅备份任务显示
        self._backup_grp.setVisible(is_backup)

        # 表选择：备份/导出/同步任务显示
        # 找到表选择的行并设置可见性
        for i in range(self.layout().count()):
            item = self.layout().itemAt(i)
            if item and item.widget() and hasattr(item.widget(), 'placeholderText'):
                if item.widget().placeholderText() and "表名" in item.widget().placeholderText():
                    item.widget().setVisible(is_backup or is_export or is_sync)
                    break

    def _on_ok(self):
        name = self.txt_name.text().strip()
        if not name:
            QMessageBox.warning(self, "提示", "任务名称不能为空")
            return
        type_map = {0: TASK_TYPE_SQL, 1: TASK_TYPE_SYNC, 2: TASK_TYPE_EXPORT, 3: TASK_TYPE_BACKUP}
        sched_map = {0: "interval", 1: "daily", 2: "weekly", 3: "monthly"}

        # 解析表名（支持多个，用逗号分隔）
        table_input = self.cmb_table.currentText().strip()
        tables = [t.strip() for t in table_input.split(",") if t.strip()] if table_input else []

        task = self._task or ScheduledTask()
        task.name         = name
        task.description  = self.txt_desc.text().strip()
        task.task_type    = type_map[self.cmb_type.currentIndex()]
        task.conn_name    = self.cmb_conn.currentText()
        task.db_name      = self.cmb_db.currentText().strip()
        task.sql          = self.txt_sql.toPlainText().strip()
        task.schedule_type = sched_map[self.cmb_sched.currentIndex()]
        task.interval_min = self.spin_interval.value()
        task.daily_time   = self.time_edit.time().toString("HH:mm")
        task.weekly_day   = self.cmb_weekday.currentIndex()
        task.monthly_day  = self.spin_monthday.value()

        # 任务类型对应的配置
        task_type_idx = self.cmb_type.currentIndex()
        if task_type_idx == 3:  # 备份
            task.backup_cfg   = {
                "tables":       tables,
                "include_data": self.rb_backup_full.isChecked(),
                "backup_dir":   self.txt_backup_dir.text().strip(),
                "note":         self.txt_backup_note.text().strip(),
            }
        elif task_type_idx == 2:  # 导出
            task.export_cfg   = {
                "tables":       tables,
                "sql":          self.txt_sql.toPlainText().strip(),  # 支持用 SQL 导出
            }
        elif task_type_idx == 1:  # 同步
            task.sync_cfg     = {
                "src_table":    table_input,
            }
        self._result = task
        self.accept()

    def get_result(self) -> ScheduledTask:
        return getattr(self, "_result", None)


# ── 主窗口 ─────────────────────────────────────────────────────────────────
class SchedulerWindow(QDialog):
    """定时任务管理窗口"""

    taskTriggered = Signal(object)   # ScheduledTask → 主窗口执行

    def __init__(self, parent=None, scheduler: TaskScheduler = None,
                 conn_names: list = None,
                 conns: dict = None,
                 execute_fn=None):
        super().__init__(parent)
        self.scheduler   = scheduler or TaskScheduler()
        self._conn_names = conn_names or []
        self._conns = conns or {}  # {conn_name: connector}
        self._execute_fn = execute_fn  # 主窗口提供的执行回调
        # 无边框窗口设置
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setWindowTitle("定时任务管理")
        self.setMinimumSize(900, 580)
        self.resize(1000, 640)
        self._theme = load_theme()
        self._tokens = get_theme_tokens(self._theme)
        # 先创建标题栏（必须在 _build_ui 之前）
        self._title_bar, self._title_lbl, self._title_close_btn = make_frameless_title_bar(
            self, "定时任务管理", self._tokens)
        self._title_close_btn.clicked.connect(self.close)
        self._build_ui()
        self._refresh_table()

    def _build_ui(self):
        frame, frame_layout, inner = build_dialog_frame(self._tokens, self, self._title_bar)
        inner_layout = QVBoxLayout(inner)
        inner_layout.setContentsMargins(10, 10, 10, 10)
        inner_layout.setSpacing(8)

        # 定时刷新状态（每 10 秒）
        self._refresh_timer = QTimer(self)
        self._refresh_timer.timeout.connect(self._refresh_table)
        self._refresh_timer.start(10_000)

        # 顶部工具栏
        bar = QHBoxLayout()
        for text, slot, role in [
            (Icon.prefixed_text('add', "新建任务"), self._on_new, "primary"),
            (Icon.prefixed_text('edit', "编辑"), self._on_edit, ""),
            (Icon.prefixed_text('delete', "删除"), self._on_delete, ""),
            (Icon.prefixed_text('play', "立即执行"), self._on_run_now, "success"),
            (Icon.prefixed_text('pause', "启停"), self._on_toggle, ""),
        ]:
            btn = QPushButton(text)
            btn.setFixedHeight(30)
            if role:
                btn.setProperty("role", role)
            btn.clicked.connect(slot)
            bar.addWidget(btn)

        bar.addStretch()
        btn_refresh = QPushButton(Icon.prefixed_text('refresh', "刷新"))
        btn_refresh.setFixedHeight(30)
        btn_refresh.clicked.connect(self._refresh_table)
        bar.addWidget(btn_refresh)
        inner_layout.addLayout(bar)

        # 任务列表
        self.table = QTableWidget()
        self.table.setColumnCount(8)
        self.table.setHorizontalHeaderLabels(
            ["ID", "任务名称", "类型", "调度", "状态", "上次执行", "下次执行", "执行次数"]
        )
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.doubleClicked.connect(self._on_edit)
        inner_layout.addWidget(self.table, stretch=1)

        # 日志
        log_grp = QGroupBox("执行日志")
        log_lay = QVBoxLayout(log_grp)
        self.log_box = QTextEdit()
        self.log_box.setReadOnly(True)
        self.log_box.setFont(QFont("Consolas", 9))
        self.log_box.setMaximumHeight(100)
        self.log_box.setStyleSheet(get_log_box_style(self._theme))

        log_lay.addWidget(self.log_box)
        inner_layout.addWidget(log_grp)

    def _refresh_table(self):
        self.scheduler.load()
        tasks = self.scheduler.tasks
        self.table.setRowCount(len(tasks))
        type_labels = {TASK_TYPE_SQL: "执行SQL", TASK_TYPE_SYNC: "数据同步", TASK_TYPE_EXPORT: "数据导出", TASK_TYPE_BACKUP: "数据库备份"}
        for i, t in enumerate(tasks):
            self.table.setItem(i, 0, QTableWidgetItem(t.id))
            self.table.setItem(i, 1, QTableWidgetItem(t.name))
            self.table.setItem(i, 2, QTableWidgetItem(type_labels.get(t.task_type, t.task_type)))
            self.table.setItem(i, 3, QTableWidgetItem(t.schedule_label()))
            status_item = QTableWidgetItem(
                Icon.prefixed_text('success', "启用") if t.status == STATUS_ENABLED else Icon.prefixed_text('pause', "停用")
            )
            if t.status == STATUS_DISABLED:
                status_item.setForeground(QColor(self._tokens["text_muted"]))
            self.table.setItem(i, 4, status_item)
            self.table.setItem(i, 5, QTableWidgetItem(t.last_run or "—"))
            self.table.setItem(i, 6, QTableWidgetItem(t.next_run or "—"))
            self.table.setItem(i, 7, QTableWidgetItem(str(t.run_count)))

    def _get_selected_task(self) -> ScheduledTask | None:
        row = self.table.currentRow()
        if row < 0 or row >= len(self.scheduler.tasks):
            return None
        return self.scheduler.tasks[row]

    def _on_new(self):
        dlg = _TaskEditDialog(self, conn_names=self._conn_names, conns=self._conns)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            task = dlg.get_result()
            if task:
                self.scheduler.add_task(task)
                self._refresh_table()
                self._log(f"{Icon.char('success')} 新建任务：{task.name}（下次执行：{task.next_run}）")

    def _on_edit(self, *_):
        task = self._get_selected_task()
        if not task:
            return
        dlg = _TaskEditDialog(self, task=task, conn_names=self._conn_names, conns=self._conns)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            result = dlg.get_result()
            if result:
                self.scheduler.update_task(
                    task.id,
                    name=result.name,
                    description=result.description,
                    task_type=result.task_type,
                    conn_name=result.conn_name,
                    db_name=result.db_name,
                    sql=result.sql,
                    schedule_type=result.schedule_type,
                    interval_min=result.interval_min,
                    daily_time=result.daily_time,
                    weekly_day=result.weekly_day,
                    monthly_day=result.monthly_day,
                    backup_cfg=result.backup_cfg,
                )
                self._refresh_table()
                self._log(f"{Icon.char('edit')} 任务已更新：{result.name}")

    def _on_delete(self):
        task = self._get_selected_task()
        if not task:
            return
        ret = QMessageBox.question(
            self, "删除任务",
            f"确定删除任务「{task.name}」？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if ret == QMessageBox.StandardButton.Yes:
            self.scheduler.delete_task(task.id)
            self._refresh_table()
            self._log(f"{Icon.char('delete')} 任务已删除：{task.name}")

    def _on_toggle(self):
        task = self._get_selected_task()
        if not task:
            return
        new_status = self.scheduler.toggle_task(task.id)
        self._refresh_table()
        label = "启用" if new_status == STATUS_ENABLED else "停用"
        self._log(f"{Icon.char('play') if new_status == STATUS_ENABLED else Icon.char('pause')} 任务已{label}：{task.name}")

    def _on_run_now(self):
        task = self._get_selected_task()
        if not task:
            return
        self._log(f"{Icon.char('play')} 立即执行：{task.name}")
        self._execute_task(task)

    def _execute_task(self, task: ScheduledTask):
        """执行任务（SQL 类型直接在此调用，其他类型发信号给主窗口）"""
        if task.task_type == TASK_TYPE_SQL:
            if self._execute_fn and task.sql:
                try:
                    cols, rows = self._execute_fn(task.sql)
                    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    task.last_run    = now
                    task.last_result = f"{Icon.styled_char('success')} 返回 {len(rows)} 行"
                    task.run_count  += 1
                    self.scheduler.save()
                    self._refresh_table()
                    self._log(f"  {Icon.char('success')} 执行完成，返回 {len(rows)} 行")
                except Exception as e:
                    task.last_result = f"{Icon.styled_char('error')} {e}"
                    self.scheduler.save()
                    self._log(f"  {Icon.char('error')} 执行失败：{e}")
            else:
                self._log(f"  {Icon.char('warning')} 未配置执行函数或 SQL 为空")
        else:
            # sync / export / backup 类型 → 交给主窗口处理
            self.taskTriggered.emit(task)

    def _log(self, msg: str):
        ts = datetime.datetime.now().strftime("%H:%M:%S")
        self.log_box.append(f"[{ts}] {wrap_pua(msg)}")
        self.log_box.verticalScrollBar().setValue(
            self.log_box.verticalScrollBar().maximum()
        )

    def closeEvent(self, event):
        self._refresh_timer.stop()
        super().closeEvent(event)