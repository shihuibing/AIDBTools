"""
query_manager_window.py
查询管理窗口 - 类似 Navicat 查询保存与管理功能
- 保存/编辑/删除 SQL 查询
- 按连接/数据库筛选
- 执行查询并返回结果
"""
import os
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QWidget,
    QLabel, QComboBox, QPushButton, QTextEdit,
    QTableWidget, QTableWidgetItem, QHeaderView,
    QGroupBox, QFormLayout, QCheckBox,
    QMessageBox, QLineEdit, QAbstractItemView,
    QSplitter, QListWidget, QListWidgetItem,
    QDialogButtonBox,
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont

from sqlalchemy import text as sa_text
from core.query_manager import (
    save_query, load_query, list_queries,
    delete_query, rename_query, get_query_dir,
)
from core.platform_utils import get_default_backup_dir
from ui.theme_manager import (
    load_theme, THEME_DARK, THEME_AUTO, _is_system_dark,
    get_theme_tokens, get_log_box_style, build_popup_base_style,
    build_dialog_frame,
    build_frameless_dialog_style, make_frameless_title_bar,
)
from ui.iconfont_loader import Icon


def _is_dark_now() -> bool:
    t = load_theme()
    if t == THEME_AUTO:
        return _is_system_dark()
    return t == THEME_DARK


class QueryManagerWindow(QDialog):
    """
    查询管理窗口
    signals:
        queryExecuted(str query_name, list cols, list rows): 执行查询后发射
    """
    queryExecuted = Signal(str, list, list)

    def __init__(self, parent=None, conns: dict = None,
                 conn_infos: dict = None):
        super().__init__(parent)
        # 无边框窗口设置
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self._conns = conns or {}
        self._conn_infos = conn_infos or {}
        self._current_query_file = None
        self._theme = load_theme()
        self._tokens = get_theme_tokens(self._theme)
        self.setWindowTitle("查询管理")
        self.setMinimumSize(900, 580)
        self.resize(1000, 640)
        # 先创建标题栏（必须在 _build_ui 之前）
        self._title_bar, self._title_lbl, self._title_close_btn = make_frameless_title_bar(
            self, "查询管理", self._tokens)
        self._title_close_btn.clicked.connect(self.close)
        self._build_ui()
        self._refresh_query_list()

    def _build_ui(self):
        frame, frame_layout, inner = build_dialog_frame(self._tokens, self, self._title_bar)
        inner_layout = QVBoxLayout(inner)
        inner_layout.setContentsMargins(10, 10, 10, 10)
        inner_layout.setSpacing(8)

        # ── 左侧：查询列表 ────────────────────────────────
        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(6)

        # 筛选栏
        filter_row = QHBoxLayout()
        filter_row.setSpacing(6)

        self.cb_conn_filter = QComboBox()
        self.cb_conn_filter.addItems(["全部连接"])
        self.cb_conn_filter.addItems(list(self._conns.keys()))
        self.cb_conn_filter.currentTextChanged.connect(self._on_filter_changed)
        filter_row.addWidget(QLabel("连接:"))
        filter_row.addWidget(self.cb_conn_filter)

        self.cb_db_filter = QComboBox()
        self.cb_db_filter.addItems(["全部数据库"])
        self.cb_db_filter.currentTextChanged.connect(self._refresh_query_list)
        filter_row.addWidget(QLabel("库:"))
        filter_row.addWidget(self.cb_db_filter)
        filter_row.addStretch()

        left_layout.addLayout(filter_row)

        # 搜索
        self.txt_search = QLineEdit()
        self.txt_search.setPlaceholderText("搜索查询名称…")
        self.txt_search.setFixedHeight(26)
        self.txt_search.textChanged.connect(self._refresh_query_list)
        left_layout.addWidget(self.txt_search)

        # 查询列表
        self.list_queries = QListWidget()
        self.list_queries.setAlternatingRowColors(True)
        self.list_queries.itemClicked.connect(self._on_query_selected)
        self.list_queries.itemDoubleClicked.connect(self._on_query_double_clicked)
        left_layout.addWidget(self.list_queries, stretch=1)

        # 左侧按钮
        btn_left = QHBoxLayout()
        btn_new = QPushButton(Icon.prefixed_text('add', "新建"))
        btn_new.setFixedHeight(28)
        btn_new.clicked.connect(self._on_new_query)
        btn_del = QPushButton(Icon.prefixed_text('delete', "删除"))
        btn_del.setFixedHeight(28)
        btn_del.clicked.connect(self._on_delete_query)
        btn_exec = QPushButton(Icon.prefixed_text('play', "执行"))
        btn_exec.setFixedHeight(28)
        btn_exec.setProperty("role", "primary")
        btn_exec.clicked.connect(self._on_execute_query)
        btn_left.addWidget(btn_new)
        btn_left.addWidget(btn_del)
        btn_left.addStretch()
        btn_left.addWidget(btn_exec)
        left_layout.addLayout(btn_left)

        # ── 右侧：查询编辑器 ──────────────────────────────
        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(6)

        # 基本信息
        info_grp = QGroupBox("查询信息")
        info_form = QFormLayout(info_grp)
        info_form.setSpacing(8)

        self.txt_name = QLineEdit()
        self.txt_name.setPlaceholderText("查询名称（必填）")
        info_form.addRow("名称 *:", self.txt_name)

        row_conn = QHBoxLayout()
        self.cb_conn = QComboBox()
        self.cb_conn.addItems(list(self._conns.keys()))
        row_conn.addWidget(self.cb_conn)
        info_form.addRow("连接:", row_conn)

        self.txt_db = QLineEdit()
        self.txt_db.setPlaceholderText("数据库名（可选）")
        info_form.addRow("数据库:", self.txt_db)

        self.txt_desc = QLineEdit()
        self.txt_desc.setPlaceholderText("查询描述（可选）")
        info_form.addRow("描述:", self.txt_desc)

        right_layout.addWidget(info_grp)

        # SQL 编辑器
        lbl_sql = QLabel("SQL 语句:")
        lbl_sql.setProperty("role", "title")
        right_layout.addWidget(lbl_sql)

        self.txt_sql = QTextEdit()
        self.txt_sql.setFont(QFont("Consolas", 10))
        self.txt_sql.setPlaceholderText("-- 在此输入 SQL 语句\n-- 可以在工具栏点击「保存」将查询保存到列表")
        self.txt_sql.setMinimumHeight(160)
        right_layout.addWidget(self.txt_sql, stretch=1)

        # 按钮行
        btn_row = QHBoxLayout()
        btn_save = QPushButton(Icon.prefixed_text('save', "保存"))
        btn_save.setFixedHeight(30)
        btn_save.setProperty("role", "primary")
        btn_save.clicked.connect(self._on_save_query)
        btn_update = QPushButton(Icon.prefixed_text('save', "更新"))
        btn_update.setFixedHeight(30)
        btn_update.setProperty("role", "primary")
        btn_update.clicked.connect(self._on_update_query)
        btn_clear = QPushButton(Icon.prefixed_text('delete', "清空"))
        btn_clear.setFixedHeight(30)
        btn_clear.clicked.connect(self._on_clear_form)
        btn_row.addWidget(btn_update)
        btn_row.addWidget(btn_save)
        btn_row.addWidget(btn_clear)
        btn_row.addStretch()
        right_layout.addLayout(btn_row)

        # 加入主布局
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(left)
        splitter.addWidget(right)
        splitter.setSizes([320, 680])
        splitter.setHandleWidth(4)
        splitter.setChildrenCollapsible(False)
        inner_layout.addWidget(splitter)

    # ── 查询列表刷新 ────────────────────────────────────────
    def _refresh_query_list(self):
        conn_filter = self.cb_conn_filter.currentText()
        if conn_filter == "全部连接":
            conn_filter = None
        db_filter = self.cb_db_filter.currentText()
        if db_filter == "全部数据库":
            db_filter = None
        search = self.txt_search.text().strip()

        queries = list_queries(conn_name=conn_filter, db_name=db_filter)
        if search:
            queries = [q for q in queries
                       if search.lower() in q["name"].lower()
                       or search.lower() in q.get("description", "").lower()]

        self.list_queries.clear()
        for q in queries:
            item = QListWidgetItem()
            name = q["name"]
            desc = q.get("description", "")
            updated = q.get("updated_at", "")[:10]
            if desc:
                display = f"{name}\n  {desc}  [{q['connection']}/{q['database']}] {updated}"
            else:
                display = f"{name}\n  [{q['connection']}/{q['database']}] {updated}"
            item.setText(display)
            item.setData(Qt.ItemDataRole.UserRole, q)
            item.setToolTip(f"{name}\n连接: {q['connection']}  库: {q['database']}\n描述: {desc}")
            self.list_queries.addItem(item)

    def _on_filter_changed(self, conn_name: str):
        """切换连接时，更新数据库下拉"""
        self.cb_db_filter.blockSignals(True)
        self.cb_db_filter.clear()
        self.cb_db_filter.addItems(["全部数据库"])
        if conn_name and conn_name != "全部连接":
            # 获取该连接的数据库列表
            connector = self._conns.get(conn_name)
            if connector:
                try:
                    with connector._get_session() as session:
                        if connector._db_type in ("postgresql", "gaussdb", "opengauss", "tidb", "polardb", "oceanbase"):
                            dbs = [r[0] for r in session.execute(sa_text("SELECT datname FROM pg_database WHERE datistemplate = false"))]
                        elif connector._db_type == "sqlserver":
                            dbs = [r[0] for r in session.execute(sa_text("SELECT name FROM sys.databases"))]
                        elif connector._db_type == "oracle":
                            dbs = [r[0] for r in session.execute(sa_text("SELECT username FROM dba_users WHERE account_status='OPEN'"))]
                        else:
                            dbs = []
                    for db in dbs:
                        if isinstance(db, str):
                            self.cb_db_filter.addItem(db)
                except Exception:
                    pass
        self.cb_db_filter.blockSignals(False)
        self._refresh_query_list()

    def _on_query_selected(self, item: QListWidgetItem):
        """选中查询，加载内容到编辑器"""
        q = item.data(Qt.ItemDataRole.UserRole)
        data = load_query(q["connection"], q["database"], q["name"])
        if data:
            self.txt_name.setText(q["name"])
            self.txt_name.setEnabled(False)  # 已保存的不能改名
            self.cb_conn.setCurrentText(q["connection"])
            self.txt_db.setText(q["database"])
            self.txt_desc.setText(q.get("description", ""))
            self.txt_sql.setPlainText(data.get("sql", ""))
            self._current_query_file = q["filepath"]

    def _on_query_double_clicked(self, item: QListWidgetItem):
        """双击直接执行"""
        self._on_query_selected(item)
        self._on_execute_query()

    def _on_new_query(self):
        """新建查询"""
        self.txt_name.setEnabled(True)
        self.txt_name.clear()
        self.txt_desc.clear()
        self.txt_sql.clear()
        self.txt_db.clear()
        if self._conns:
            self.cb_conn.setCurrentIndex(0)
        self._current_query_file = None
        self.txt_name.setFocus()

    def _on_clear_form(self):
        """清空表单"""
        self._on_new_query()

    def _on_save_query(self):
        """保存新查询"""
        name = self.txt_name.text().strip()
        if not name:
            QMessageBox.warning(self, "提示", "查询名称不能为空")
            return
        conn = self.cb_conn.currentText()
        if not conn:
            QMessageBox.warning(self, "提示", "请选择连接")
            return
        db = self.txt_db.text().strip()
        desc = self.txt_desc.text().strip()
        sql = self.txt_sql.toPlainText().strip()
        if not sql:
            QMessageBox.warning(self, "提示", "SQL 语句不能为空")
            return

        ok = save_query(conn, db, name, sql, desc)
        if ok:
            QMessageBox.information(self, "成功", f"查询「{name}」已保存")
            self._refresh_query_list()
            self.txt_name.setEnabled(False)
        else:
            QMessageBox.warning(self, "失败", "保存查询失败")

    def _on_update_query(self):
        """更新已有查询"""
        name = self.txt_name.text().strip()
        if not name:
            QMessageBox.warning(self, "提示", "查询名称不能为空")
            return
        q_file = self._current_query_file
        if not q_file:
            QMessageBox.warning(self, "提示", "请先在列表中选择要更新的查询")
            return
        # 从文件路径提取 conn/db
        query_dir = get_query_dir()
        rel = os.path.relpath(q_file, query_dir)
        parts = rel.split(os.sep)
        if len(parts) >= 2:
            conn = parts[0]
            db = parts[1]
            old_name = parts[2].replace(".sql", "")
            desc = self.txt_desc.text().strip()
            sql = self.txt_sql.toPlainText().strip()
            ok = save_query(conn, db, old_name, sql, desc)
            if ok:
                QMessageBox.information(self, "成功", f"查询「{old_name}」已更新")
                self._refresh_query_list()
            else:
                QMessageBox.warning(self, "失败", "更新查询失败")

    def _on_delete_query(self):
        """删除查询"""
        item = self.list_queries.currentItem()
        if not item:
            QMessageBox.warning(self, "提示", "请先在列表中选择要删除的查询")
            return
        q = item.data(Qt.ItemDataRole.UserRole)
        ret = QMessageBox.question(
            self, "删除确认",
            f"确定删除查询「{q['name']}」？\n连接: {q['connection']}  数据库: {q['database']}",
        )
        if ret == QMessageBox.StandardButton.Yes:
            ok = delete_query(q["connection"], q["database"], q["name"])
            if ok:
                self._on_new_query()
                self._refresh_query_list()
                QMessageBox.information(self, "成功", "查询已删除")
            else:
                QMessageBox.warning(self, "失败", "删除失败")

    def _on_execute_query(self):
        """执行查询"""
        sql = self.txt_sql.toPlainText().strip()
        if not sql:
            QMessageBox.warning(self, "提示", "SQL 编辑器为空")
            return
        conn_name = self.cb_conn.currentText()
        if not conn_name:
            QMessageBox.warning(self, "提示", "请选择连接")
            return
        connector = self._conns.get(conn_name)
        if not connector:
            QMessageBox.warning(self, "提示", f"连接 [{conn_name}] 未连接")
            return

        name = self.txt_name.text().strip() or "未命名查询"
        db = self.txt_db.text().strip()

        try:
            cols, rows = connector.execute(sql)
            self.queryExecuted.emit(name, cols, rows)
            QMessageBox.information(
                self, "执行成功",
                f"查询「{name}」执行完成\n返回 {len(rows)} 行数据"
            )
        except Exception as e:
            QMessageBox.warning(self, "执行失败", str(e))