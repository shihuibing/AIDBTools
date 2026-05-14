from __future__ import annotations

import datetime
import math
import os
import queue
import threading
from typing import Optional
from PySide6.QtWidgets import *
from PySide6.QtCore import *
from PySide6.QtGui import *
from version import VERSION, get_about_text, APP_FULL_NAME
from core.connection import DatabaseConnector
from core.connection_store import load_connections, save_connection, delete_connection, update_connection_meta, get_config_path
from core.ai_sql import AISQLGenerator
from core.ai_chat import AIChatEngine, DEFAULT_HISTORY_KEY
from core.skill_manager import SkillManager
from core.ncx_importer import parse_ncx
from core.query_manager import save_query, load_query, list_queries, delete_query
from ui.model_config_window import ModelConfigWindow
from ui.ai_chat_window import AIChatWindow, AIChatWidget
from ui.export_import_window import ExportImportWindow
from ui.skill_manager_window import SkillManagerWindow
from ui.sync_window import SyncWindow
from ui.scheduler_window import SchedulerWindow
from ui.backup_window import BackupWindow
from ui.theme_manager import (
    THEME_LIGHT, THEME_DARK, THEME_WILLOW,
    load_theme, save_theme, apply_theme, get_log_box_style, get_theme_tokens, get_table_style,
    build_popup_base_style, load_config_dir, save_config_dir,
    make_frameless_title_bar, build_dialog_frame,
)
from ui.icon_manager import IconManager
from ui.iconfont_loader import Icon
from ui.sql_editor_helper import apply_sql_highlighter, setup_sql_completer
from ui.table_extension import SelectableTableWidget, ORIGINAL_ORDER_ROLE, CheckBoxDelegate
from sqlalchemy import text as sa_text

# ─────────────────────────────────────────────
# 自定义树节点类型常量
# ─────────────────────────────────────────────
NODE_CONNECTION = 0   # 顶层：连接
NODE_DATABASE   = 1   # 二级：数据库
NODE_TABLE      = 2   # 三级：表
NODE_GROUP      = 3   # 三级：分组（表/视图/函数/索引/存储过程）
NODE_VIEW       = 4   # 四级：视图
NODE_FUNCTION   = 5   # 四级：函数
NODE_INDEX      = 6   # 四级：索引
NODE_PROCEDURE  = 7   # 四级：存储过程









# ─────────────────────────────────────────────
# AI 后台工作线程（避免 AI 调用阻塞 UI）
# ─────────────────────────────────────────────
class _AISignals(QObject):
    result = Signal(str)


class _AIWorker(QRunnable):
    def __init__(self, fn, *args):
        super().__init__()
        self.fn = fn
        self.args = args
        self.signals = _AISignals()

    def run(self):
        try:
            result = self.fn(*self.args)
        except Exception as e:
            result = f"-- AI调用失败：{str(e)}"
        self.signals.result.emit(result)


class ConnDialog(QDialog):
    """新建/编辑连接对话框"""

    DB_TYPE_OPTIONS = [
        ("mysql", "MySQL"),
        ("postgresql", "PostgreSQL"),
        ("sqlserver", "SQL Server"),
        ("oracle", "Oracle"),
        ("xugu", "虚谷（XuguDB）"),
        ("dameng", "达梦（Dameng）"),
        ("kingbase", "人大金仓（KingbaseES）"),
        ("gaussdb", "高斯（GaussDB）"),
        ("opengauss", "高斯开源（openGauss）"),
        ("oceanbase", "OceanBase"),
        ("polardb", "PolarDB"),
        ("tdsql", "腾讯云 TDSQL"),
        ("gbase", "南大通用 GBase"),
        ("tidb", "TiDB"),
        ("shentong", "神通（ShenTong）"),
        ("argodb", "星环 ArgoDB"),
        ("inceptor", "星环 Inceptor"),
    ]
    DB_TYPES = [code for code, _ in DB_TYPE_OPTIONS]
    DEFAULT_PORTS = {
        "mysql": "3306", "postgresql": "5432", "sqlserver": "1433",
        "oracle": "1521", "xugu": "5138", "gaussdb": "5432", "opengauss": "5432",
        "oceanbase": "2881", "polardb": "3306", "tdsql": "3306",
        "gbase": "3306", "tidb": "4000", "shentong": "2003",
        "dameng": "5236", "kingbase": "54321",
        # 星环：Quark Gateway 默认端口 10000
        "argodb": "10000", "inceptor": "10000",
    }


    # 需要 JDBC jar 路径的数据库类型
    _JDBC_TYPES = {"argodb", "inceptor"}

    def __init__(self, parent=None, conn_info=None):
        super().__init__(parent)
        # 无边框窗口设置
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setObjectName("connDialog")
        self.setWindowTitle("新建连接" if conn_info is None else "编辑连接")
        self.setMinimumWidth(500)
        self.conn_info = conn_info or {}
        self._theme = load_theme()
        self._tokens = get_theme_tokens(self._theme)
        # 先创建标题栏（必须在 _build_ui 之前）
        self._title_bar, self._title_lbl, self._title_close_btn = make_frameless_title_bar(
            self, "新建连接" if conn_info is None else "编辑连接", self._tokens)
        self._title_close_btn.clicked.connect(self.reject)
        self._build_ui()

    def _build_ui(self):
        frame, frame_layout, inner = build_dialog_frame(self._tokens, self, self._title_bar)
        inner_layout = QVBoxLayout(inner)
        inner_layout.setContentsMargins(18, 12, 18, 14)
        inner_layout.setSpacing(12)

        layout = QFormLayout()
        self.form_layout = layout
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setHorizontalSpacing(12)
        layout.setVerticalSpacing(8)
        layout.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        layout.setLabelAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        self.txt_name = QLineEdit(self.conn_info.get("name", ""))
        self.cb_type = QComboBox()
        for code, label in self.DB_TYPE_OPTIONS:
            self.cb_type.addItem(label, code)
        cur_type = self.conn_info.get("db_type", "mysql")
        if cur_type not in self.DB_TYPES:
            cur_type = "mysql"
        cur_idx = self.cb_type.findData(cur_type)
        self.cb_type.setCurrentIndex(cur_idx if cur_idx >= 0 else 0)

        self.txt_host = QLineEdit(self.conn_info.get("host", "127.0.0.1"))
        self.txt_port = QLineEdit(self.conn_info.get("port", "3306"))
        self.txt_user = QLineEdit(self.conn_info.get("user", "root"))
        self.txt_pwd = QLineEdit(self.conn_info.get("pwd", ""))
        self.txt_pwd.setEchoMode(QLineEdit.EchoMode.Password)
        self.txt_db = QLineEdit(self.conn_info.get("dbname", ""))

        self.lbl_driver_status = QLabel("正在探测…")
        self.lbl_driver_status.setWordWrap(True)

        self.btn_install_odbc = QPushButton("安装 ODBC 驱动")
        self.btn_install_odbc.setFixedWidth(126)
        self.btn_install_odbc.setVisible(False)
        self.btn_install_odbc.clicked.connect(self._install_odbc)

        driver_row = QHBoxLayout()
        driver_row.setContentsMargins(0, 0, 0, 0)
        driver_row.setSpacing(6)
        driver_row.addWidget(self.lbl_driver_status)
        driver_row.addWidget(self.btn_install_odbc)

        jar_row = QHBoxLayout()
        jar_row.setContentsMargins(0, 0, 0, 0)
        jar_row.setSpacing(6)
        self.txt_jar = QLineEdit(self.conn_info.get("jar_path", ""))
        self.txt_jar.setPlaceholderText("（可选）手动指定 quark-driver-*.jar 路径覆盖自动探测")
        self.btn_browse_jar = QPushButton("浏览…")
        self.btn_browse_jar.setFixedWidth(68)
        self.btn_browse_jar.clicked.connect(self._browse_jar)
        jar_row.addWidget(self.txt_jar)
        jar_row.addWidget(self.btn_browse_jar)
        self.txt_jar.textChanged.connect(self._refresh_driver_status)

        self.chk_spatial = QCheckBox("空间数据库（GIS）")
        self.chk_spatial.setChecked(bool(self.conn_info.get("is_spatial", False)))
        self.chk_spatial.setToolTip("勾选后 AI 上下文会包含空间函数提示（ST_GeomFromText 等）")

        self.lbl_driver_row = QLabel("驱动状态")
        self.lbl_jar = QLabel("JDBC JAR（可选）")
        self.lbl_spatial = QLabel("空间支持")
        self.lbl_db = QLabel("默认数据库")

        self.cb_type.currentIndexChanged.connect(self._auto_port)
        self.cb_type.currentIndexChanged.connect(self._toggle_jdbc_fields)
        self.cb_type.currentIndexChanged.connect(self._refresh_conn_hints)

        layout.addRow("连接名称 *", self.txt_name)
        layout.addRow("数据库类型", self.cb_type)
        layout.addRow("主机地址", self.txt_host)
        layout.addRow("端口", self.txt_port)
        layout.addRow("用户名", self.txt_user)
        layout.addRow("密码", self.txt_pwd)
        layout.addRow(self.lbl_db, self.txt_db)
        layout.addRow(self.lbl_driver_row, driver_row)
        layout.addRow(self.lbl_jar, jar_row)
        layout.addRow(self.lbl_spatial, self.chk_spatial)
        inner_layout.addLayout(layout)

        footer = QHBoxLayout()
        footer.setContentsMargins(18, 4, 18, 2)
        footer.setSpacing(8)

        self.btn_test = QPushButton("测试连接")
        self.btn_test.setObjectName("connTestButton")
        self.btn_test.clicked.connect(self._on_test_connection)
        footer.addWidget(self.btn_test)
        footer.addStretch()

        self.btn_cancel = QPushButton("取消")
        self.btn_cancel.setFixedWidth(84)
        self.btn_cancel.clicked.connect(self.reject)
        footer.addWidget(self.btn_cancel)

        self.btn_ok = QPushButton("保存")
        self.btn_ok.setFixedWidth(84)
        self.btn_ok.setProperty("role", "primary")
        self.btn_ok.clicked.connect(self._on_ok)
        self.btn_ok.setDefault(True)
        footer.addWidget(self.btn_ok)
        inner_layout.addLayout(footer)

        self._toggle_jdbc_fields()
        self._refresh_conn_hints()

    def _show_feedback_message(self, title: str, message: str, icon: QMessageBox.Icon):
        lines = [line.strip() for line in str(message).splitlines() if line.strip()]
        summary = lines[0] if lines else str(message)
        details = "\n".join(lines[1:]).strip()
        box = QMessageBox(self)
        box.setIcon(icon)
        box.setWindowTitle(title)
        box.setText(summary)
        if details:
            preview = details[:360] + ("…" if len(details) > 360 else "")
            box.setInformativeText(preview)
            box.setDetailedText(str(message))
        box.setStyleSheet(self.styleSheet())
        box.exec()

    def _collect_form_data(self, require_name: bool = True):
        name = self.txt_name.text().strip()
        if require_name and not name:
            self._show_feedback_message("提示", "连接名称不能为空", QMessageBox.Icon.Warning)
            return None

        db_type = self.cb_type.currentData() or "mysql"
        if db_type in self._JDBC_TYPES:
            from core.argo_driver_manager import ArgoDriverManager
            info = ArgoDriverManager.detect(jar_path=self.txt_jar.text().strip())
            if info.mode == "none":
                installer = info.odbc_installer
                hint = (
                    f"\n\n可安装内置 ODBC 驱动包：\n{installer}"
                    if installer else
                        "\n\n请将 quark-driver-*.jar 放入 drivers/transwarp/jdbc/ 目录，\n"
                    "或手动指定 JAR 文件路径。"
                )
                self._show_feedback_message(
                    "无可用驱动",
                    f"未找到星环数据库的 JDBC 或 ODBC 驱动。{hint}",
                    QMessageBox.Icon.Warning,
                )
                return None

        port_value = self.txt_port.text().strip()
        dbname_value = self.txt_db.text().strip()
        if db_type == "xugu":
            port_value = port_value or self.DEFAULT_PORTS.get("xugu", "5138")
            if not dbname_value:
                self._show_feedback_message("提示", "虚谷连接必须填写数据库实例名", QMessageBox.Icon.Warning)
                return None

        return {
            "name": name,
            "db_type": db_type,
            "host": self.txt_host.text().strip(),
            "port": port_value,
            "user": self.txt_user.text().strip(),
            "pwd": self.txt_pwd.text(),
            "dbname": dbname_value,
            "jar_path": self.txt_jar.text().strip(),
            "is_spatial": self.chk_spatial.isChecked(),
        }

    def _on_test_connection(self):
        info = self._collect_form_data(require_name=False)
        if not info:
            return

        connector = DatabaseConnector()
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            ok, msg = connector.connect(
                info["db_type"], info["host"], info["port"],
                info["user"], info["pwd"], info["dbname"],
                jar_path=info.get("jar_path", ""),
                is_spatial=info.get("is_spatial", False),
            )
        finally:
            QApplication.restoreOverrideCursor()
            engine = getattr(connector, "engine", None)
            if engine is not None:
                try:
                    engine.dispose()
                except Exception:
                    pass

        if ok:
            self._show_feedback_message("测试连接", msg, QMessageBox.Icon.Information)
        else:
            self._show_feedback_message("测试连接失败", msg, QMessageBox.Icon.Critical)

    def _refresh_conn_hints(self, _=None):
        db_type = self.cb_type.currentData() or "mysql"
        self.lbl_db.setText("默认数据库")
        if db_type == "sqlserver":
            self.txt_host.setPlaceholderText("例：127.0.0.1 / 主机名 / 主机名\\SQLEXPRESS / 127.0.0.1,1433")
            self.txt_host.setToolTip("SQL Server 支持 IP、主机名、主机\\实例名，也支持直接写 host,port。")
            self.txt_port.setPlaceholderText("默认 1433；若主机里已写 host,port 或使用主机\\实例名，可留空")
            self.txt_port.setToolTip("命名实例通常可只填主机\\实例名；若主机框已经写了 host,port，这里可以留空。")
            self.txt_db.setPlaceholderText("可留空；未填写时会先尝试 master")
            self.txt_db.setToolTip("SQL Server 默认数据库可先留空，程序会先用 master 建立连接。")
            return
        if db_type == "xugu":
            self.lbl_db.setText("数据库（实例名） *")
            self.txt_host.setPlaceholderText("例：127.0.0.1 / 主机名 / 10.0.0.1,10.0.0.2")
            self.txt_host.setToolTip("虚谷支持单节点 IP/主机名，也支持逗号分隔的多节点地址。")
            self.txt_port.setPlaceholderText("默认 5138")
            self.txt_port.setToolTip("虚谷数据库官方默认端口通常为 5138。")
            self.txt_db.setPlaceholderText("请输入实际数据库实例名，例如 SYSTEM")
            self.txt_db.setToolTip("虚谷连接必须显式填写数据库实例名，不能留空。")
            return

        self.txt_host.setPlaceholderText("")
        self.txt_host.setToolTip("")
        self.txt_port.setPlaceholderText(self.DEFAULT_PORTS.get(db_type, ""))
        self.txt_port.setToolTip("")
        self.txt_db.setPlaceholderText("")
        self.txt_db.setToolTip("")

    def _toggle_jdbc_fields(self, _=None):
        """只有星环类型才显示驱动状态和 JAR 路径"""
        db_type = self.cb_type.currentData() or "mysql"
        is_argo = db_type in self._JDBC_TYPES

        for w in (
            self.lbl_driver_row,
            self.lbl_driver_status,
            self.btn_install_odbc,
            self.lbl_jar,
            self.txt_jar,
            self.btn_browse_jar,
            self.lbl_spatial,
            self.chk_spatial,
        ):
            w.setVisible(is_argo)

        if is_argo:
            self._refresh_driver_status()

    def _refresh_driver_status(self, _=None):
        """探测驱动并刷新状态标签"""
        try:
            from core.argo_driver_manager import ArgoDriverManager
            info = ArgoDriverManager.detect(jar_path=self.txt_jar.text().strip())
            self.lbl_driver_status.setText(info.description)
            has_installer = bool(info.odbc_installer and info.mode != "odbc")
            self.btn_install_odbc.setVisible(has_installer)
            if has_installer:
                self.btn_install_odbc.setToolTip(f"安装包：{info.odbc_installer}")
            # 使用主题 token 区分状态
            color = self._tokens["success"] if info.mode != "none" else self._tokens["danger"]
            self.lbl_driver_status.setStyleSheet(f"color:{color};")
        except Exception as e:
            self.lbl_driver_status.setText(f"探测失败：{e}")

    def _install_odbc(self):
        """启动 ODBC 安装程序（静默安装）"""
        import subprocess, os
        from core.argo_driver_manager import ArgoDriverManager
        installer = ArgoDriverManager.get_odbc_installer_path()
        if not os.path.isfile(installer):
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.warning(self, "提示", f"安装包不存在：{installer}")
            return
        try:
            subprocess.Popen([installer, "/S"], shell=False)
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.information(
                self, "安装中",
                "ODBC 驱动正在后台安装，安装完成后请重新打开此对话框以刷新驱动状态。"
            )
        except Exception as e:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.warning(self, "启动失败", str(e))

    def _browse_jar(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "选择 JDBC JAR 文件", "", "JAR 文件 (*.jar);;所有文件 (*.*)"
        )
        if path:
            self.txt_jar.setText(path)

    def _auto_port(self, _=None):
        db_type = self.cb_type.currentData() or "mysql"
        self.txt_port.setText(self.DEFAULT_PORTS.get(db_type, ""))


    def _on_ok(self):
        info = self._collect_form_data(require_name=True)
        if not info:
            return
        self.result_info = info
        self.accept()

    def get_result(self):
        return getattr(self, "result_info", None)


# ─────────────────────────────────────────────
# Navicat .ncx 导入预览对话框
# ─────────────────────────────────────────────
class _NcxImportPreviewDialog(QDialog):
    """
    展示即将导入的连接列表。
    每行：[勾选框] [类型] [连接名 / host:port] [用户名] [密码输入框]
    密码留空则导入后为空，可填写后直接携带入库。
    """

    def __init__(self, parent, new_conns: list, conflict_conns: list, skipped: list):
        super().__init__(parent)
        # 无边框窗口设置
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setWindowTitle("导入 Navicat 连接 — 预览")
        self.setMinimumSize(860, 500)
        self._new_conns = new_conns
        self._conflict_conns = conflict_conns
        self._skipped = skipped
        # 每项：(QCheckBox, info_dict, pwd_QLineEdit)
        self._rows: list[tuple[QCheckBox, dict, QLineEdit]] = []
        self._theme = load_theme()
        self._tokens = get_theme_tokens(self._theme)
        self.setObjectName("ncxPreviewDialog")
        # 先创建标题栏（必须在 _build_ui 之前）
        self._title_bar, self._title_lbl, self._title_close_btn = make_frameless_title_bar(
            self, "导入 Navicat 连接 — 预览", self._tokens)
        self._title_close_btn.clicked.connect(self.reject)
        self._build_ui()

    # ── 工具：在 grid 中追加一行 ──────────────────

    def _append_section_label(self, grid: QGridLayout, row: int, text: str, color: str):
        from ui.iconfont_loader import wrap_pua
        lbl = QLabel(wrap_pua(text))
        lbl.setStyleSheet(f"font-weight:bold; color:{color}; margin-top:6px;")
        grid.addWidget(lbl, row, 0, 1, 5)

    def _append_conn_row(self, grid: QGridLayout, row: int, info: dict, conflict: bool):
        color = self._tokens["danger"] if conflict else self._tokens["text"]
        addr_color = self._tokens["text_muted"]

        cb = QCheckBox()
        cb.setChecked(True)
        grid.addWidget(cb, row, 0, Qt.AlignmentFlag.AlignCenter)

        lbl_type = QLabel(f"[{info['db_type'].upper()}]")
        lbl_type.setStyleSheet(f"color:{color}; font-size:12px; font-weight:600;")
        lbl_type.setFixedWidth(80)
        grid.addWidget(lbl_type, row, 1)

        lbl_name = QLabel(f"{info['name']}")
        lbl_name.setStyleSheet(f"color:{color}; font-weight:600;")
        lbl_name.setToolTip(f"{info['user']}@{info['host']}:{info['port']}"
                             + (f"  db:{info['dbname']}" if info.get("dbname") else ""))
        grid.addWidget(lbl_name, row, 2)

        lbl_addr = QLabel(f"{info['user']}@{info['host']}:{info['port']}")
        lbl_addr.setStyleSheet(f"color:{addr_color}; font-size:11px;")
        grid.addWidget(lbl_addr, row, 3)

        pwd_edit = QLineEdit()
        pwd_edit.setEchoMode(QLineEdit.EchoMode.Password)
        pwd_edit.setPlaceholderText("密码（可留空）")
        pwd_edit.setFixedWidth(170)
        pwd_edit.setFixedHeight(28)
        grid.addWidget(pwd_edit, row, 4)

        self._rows.append((cb, info, pwd_edit))


    def _build_ui(self):
        frame, frame_layout, inner = build_dialog_frame(self._tokens, self, self._title_bar)
        inner_layout = QVBoxLayout(inner)
        inner_layout.setContentsMargins(16, 12, 16, 12)
        inner_layout.setSpacing(10)

        tokens = self._tokens
        total = len(self._new_conns) + len(self._conflict_conns)
        header_card = QWidget()
        header_card.setObjectName("ncxHeader")
        header_layout = QVBoxLayout(header_card)
        header_layout.setContentsMargins(14, 12, 14, 12)
        header_layout.setSpacing(6)

        info_text = (
            f"共解析到 <b>{total}</b> 条连接"
            + (f"，其中 <b style='color:{tokens['danger']}'>{len(self._conflict_conns)} 条</b> 与现有同名（导入后会覆盖）"
               if self._conflict_conns else "")
                   + (f"，跳过 <b>{len(self._skipped)} 条</b> 不支持类型。"
               if self._skipped else "。")
                   )
        lbl_info = QLabel(info_text)
        lbl_info.setProperty("role", "summary")
        lbl_info.setWordWrap(True)
        header_layout.addWidget(lbl_info)

        pwd_note = QLabel(Icon.prefixed_text('lightbulb', "Navicat 导出不含密码，请在下方「密码」列直接填写，导入后即可使用。"))
        pwd_note.setProperty("role", "note")
        pwd_note.setWordWrap(True)
        header_layout.addWidget(pwd_note)
        inner_layout.addWidget(header_card)

        top_row = QHBoxLayout()
        top_row.setContentsMargins(0, 0, 0, 0)
        top_row.setSpacing(8)
        btn_all = QPushButton("全选")
        btn_none = QPushButton("全不选")
        btn_all.setObjectName("tbText")
        btn_none.setObjectName("tbText")
        btn_all.setFixedHeight(28)
        btn_none.setFixedHeight(28)
        btn_all.clicked.connect(lambda: self._set_all(True))
        btn_none.clicked.connect(lambda: self._set_all(False))
        top_row.addWidget(btn_all)
        top_row.addWidget(btn_none)
        top_row.addStretch()
        inner_layout.addLayout(top_row)

        header = QWidget()
        header.setObjectName("ncxTableHeader")
        hlay = QHBoxLayout(header)
        hlay.setContentsMargins(12, 8, 12, 8)
        hlay.setSpacing(8)
        for text, width in [(Icon.styled_char('checkbox_circle'), 24), ("类型", 88), ("连接名", 220), ("地址", 230), ("密码", 170)]:
            lbl = QLabel(text)
            lbl.setStyleSheet(f"font-weight:700; color:{tokens['text_soft']}; font-size:12px;")
            lbl.setFixedWidth(width)
            hlay.addWidget(lbl)
        hlay.addStretch()
        inner_layout.addWidget(header)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        container = QWidget()
        grid = QGridLayout(container)
        grid.setSpacing(6)
        grid.setContentsMargins(10, 10, 10, 10)
        grid.setColumnStretch(2, 1)

        cur_row = 0
        new_clr = tokens["success"]
        conf_clr = tokens["danger"]
        skip_clr = tokens["text_muted"]

        if self._new_conns:
            self._append_section_label(grid, cur_row, f"{Icon.char('success')} 新增连接（{len(self._new_conns)} 条）", new_clr)
            cur_row += 1
            for info in self._new_conns:
                self._append_conn_row(grid, cur_row, info, conflict=False)
                cur_row += 1

        if self._conflict_conns:
            self._append_section_label(grid, cur_row, f"{Icon.char('error')} 同名覆盖（{len(self._conflict_conns)} 条）", conf_clr)
            cur_row += 1
            for info in self._conflict_conns:
                self._append_conn_row(grid, cur_row, info, conflict=True)
                cur_row += 1

        if self._skipped:
            self._append_section_label(grid, cur_row, f"{Icon.char('close_circle')} 不支持（跳过 {len(self._skipped)} 条）", skip_clr)
            cur_row += 1
            for s in self._skipped:
                lbl_s = QLabel(f"  {s}")
                lbl_s.setStyleSheet(f"color:{skip_clr}; font-size:12px;")
                grid.addWidget(lbl_s, cur_row, 0, 1, 5)
                cur_row += 1

        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        grid.addWidget(spacer, cur_row, 0, 1, 5)

        scroll.setWidget(container)
        inner_layout.addWidget(scroll, stretch=1)

        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        ok_btn = btns.button(QDialogButtonBox.StandardButton.Ok)
        ok_btn.setText("确认导入")
        ok_btn.setProperty("role", "primary")
        cancel_btn = btns.button(QDialogButtonBox.StandardButton.Cancel)
        cancel_btn.setText("取消")
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        inner_layout.addWidget(btns)


    def _set_all(self, checked: bool):
        for cb, _, _ in self._rows:
            cb.setChecked(checked)

    def get_result(self) -> tuple[list[dict], bool]:
        """返回 (selected_conns_list_with_pwd, overwrite_flag)"""
        selected = []
        for cb, info, pwd_edit in self._rows:
            if cb.isChecked():
                merged = dict(info)
                merged["pwd"] = pwd_edit.text()   # 携带用户填入的密码
                selected.append(merged)
        return selected, True


# ─────────────────────────────────────────────
# Worker：在后台线程执行耗时操作
# ─────────────────────────────────────────────
class Worker(QThread):
    finished  = Signal(object)   # 成功结果
    error     = Signal(str)      # 错误信息

    def __init__(self, fn, *args, **kwargs):
        super().__init__()
        self._fn = fn
        self._args = args
        self._kwargs = kwargs

    def run(self):
        try:
            result = self._fn(*self._args, **self._kwargs)
            self.finished.emit(result)
        except Exception as e:
            self.error.emit(str(e))


# ─────────────────────────────────────────────
# 主窗口
# ─────────────────────────────────────────────
class MainWindow(QMainWindow):

    # Agent 在子线程中发射此信号，主线程接收后把 SQL 注入编辑器并执行
    agentSqlSignal = Signal(str)

    # 每个连接名对应一个 DatabaseConnector
    # _conns: dict[name -> DatabaseConnector]
    # _conn_info: dict[name -> conn_info_dict]

    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"{APP_FULL_NAME}  v{VERSION}")
        self.setGeometry(80, 80, 1600, 960)
        # ── 设置应用图标 ──
        _icon_path = self._resolve_icon_path()
        if _icon_path:
            self.setWindowIcon(QIcon(_icon_path))
        # ── 主题（在构建 UI 之前读取，菜单勾选需要它）──
        self._current_theme: str = load_theme()
        self._tokens = get_theme_tokens(self._current_theme)
        self._conns: dict[str, DatabaseConnector] = {}
        self._conn_infos: dict[str, dict] = {}
        self._workers = []        # 持有 worker 引用防止 GC
        self._current_conn_name = None
        self._ai_chat_collapsed = False
        self._ai_chat_last_width = 320
        self._log_panel_collapsed = False
        self._log_panel_last_height = 110
        self._log_panel_min_height = 40
        self._focus_mode_active = False  # 专注模式状态
        self._focus_mode_left_width = 232  # 记录左侧面板宽度
        self._focus_mode_log_collapsed = False  # 记录日志面板原始状态




        # Agent SQL 执行结果队列（子线程 put，主线程 get）
        self._agent_result_queue: queue.Queue = queue.Queue()

        # 分页状态
        self._all_cols: list = []
        self._all_rows: list = []
        self._cur_page: int = 1
        self._page_offset: int = 0   # 当前页第一行在 _all_rows 中的偏移

        # 当前表信息（用于增删改查写回数据库）
        self._current_table_name: str = ""   # 当前展示的表名
        self._current_db_name: str = ""      # 当前展示的库名
        self._table_pk_col: str = ""         # 主键列名（探测失败则为第一列）
        self._edit_mode: bool = False        # 是否处于编辑模式

        from core.scheduler import TaskScheduler
        self.scheduler = TaskScheduler()
        self.scheduler.set_run_callback(self._on_scheduled_task)
        self.scheduler.start()

        self.ai = AISQLGenerator()
        self.skill_mgr = SkillManager()

        self._init_ui()

        self._load_saved_connections()
        # Agent SQL 信号 → 主线程执行槽
        self.agentSqlSignal.connect(self._on_agent_sql_request)

    # ─── UI 构建 ─────────────────────────────
    def _init_ui(self):
        self._build_menu()
        self._build_toolbar()

        central = QWidget()
        central.setObjectName("workspaceRoot")
        self.setCentralWidget(central)
        root_layout = QVBoxLayout(central)
        root_layout.setContentsMargins(4, 0, 4, 4)
        root_layout.setSpacing(0)

        # 顶部 Win11 工具栏（在菜单栏下方）
        root_layout.addWidget(self._toolbar_widget)

        # 主工作区（水平分割）
        workspace = QWidget()
        main_layout = QHBoxLayout(workspace)
        main_layout.setContentsMargins(0, 4, 0, 0)
        main_layout.setSpacing(4)




        # 左侧面板
        left = self._build_left_panel()
        # 右侧面板
        right = self._build_right_panel()

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setObjectName("mainWorkspaceSplitter")
        splitter.addWidget(left)
        splitter.addWidget(right)
        splitter.setSizes([232, 1368])
        splitter.setHandleWidth(1)
        splitter.setChildrenCollapsible(False)
        self._workspace_splitter = splitter  # 保存引用用于专注模式
        main_layout.addWidget(splitter)

        root_layout.addWidget(workspace)
        root_layout.addSpacing(4)

        self._build_statusbar()
        self.log(f"{Icon.char('success')} 团子已就绪")

    # ─── 事件过滤器 ─────────────────────────────
    def eventFilter(self, obj: QObject, event: QEvent) -> bool:
        """处理 focus-within 等伪 CSS 效果（Qt 不支持 :focus-within）"""
        # 过滤栏聚焦时：容器边框变强调色（模拟 CSS :focus-within）
        if hasattr(self, '_filter_input') and obj == self._filter_input:
            if event.type() == QEvent.Type.FocusIn:
                t = self._tokens
                self._filter_container.setStyleSheet(
                    f"QWidget#filterBarContainer{{"
                    f"background:{t['surface']}; border:1px solid {t['accent_hover']}; "
                    f"border-radius:15px;"
                    f"}}"
                )
                return True
            elif event.type() == QEvent.Type.FocusOut:
                if hasattr(self, '_filter_container'):
                    t = self._tokens
                    self._filter_container.setStyleSheet(
                        f"QWidget#filterBarContainer{{"
                        f"background:{t['bg']}; border:1px solid {t['border']}; "
                        f"border-radius:15px;"
                        f"}}"
                    )
                return True
        # AI 输入框聚焦时：包裹容器边框变强调色
        if hasattr(self, 'ai_input') and obj == self.ai_input:
            if event.type() == QEvent.Type.FocusIn:
                t = self._tokens
                # 找到 ai_input_wrap（ai_input 的父控件）
                wrap = self.ai_input.parent()
                if wrap:
                    wrap.setStyleSheet(
                        f"background:{t['surface']}; border:1px solid {t['accent']}; "
                        f"border-radius:6px; padding:0 10px 0 0;"
                    )
                    if hasattr(self, '_ai_input_icon'):
                        self._ai_input_icon.setStyleSheet(
                            f"background:transparent; color:{t['accent']}; border:none; padding:0;"
                        )
                return True
            elif event.type() == QEvent.Type.FocusOut:
                t = self._tokens
                wrap = self.ai_input.parent()
                if wrap:
                    wrap.setStyleSheet(
                        f"background:{t['bg']}; border:1px solid {t['border']}; "
                        f"border-radius:6px; padding:0 10px 0 0;"
                    )
                    if hasattr(self, '_ai_input_icon'):
                        self._ai_input_icon.setStyleSheet(
                            f"background:transparent; color:{t['text_muted']}; border:none; padding:0;"
                        )
                return True
        return super().eventFilter(obj, event)

    def _build_menu(self):
        mb = self.menuBar()

        # ── 文件(&F) ──────────────────────────────
        file_menu = mb.addMenu("文件(&F)")
        file_menu.addAction(QIcon.fromTheme("list-add"), "新建连接…        Ctrl+N", self._on_new_conn)
        file_menu.addAction(Icon.prefixed_text('download', "导入 Navicat 连接 (.ncx)…"), self._on_import_ncx)
        file_menu.addSeparator()
        file_menu.addAction(Icon.prefixed_text('upload', "导出数据…"), self._open_export_import)
        file_menu.addAction(Icon.prefixed_text('download', "导入数据…"), self._open_export_import)
        file_menu.addSeparator()
        file_menu.addAction("退出", self.close).setShortcut("Alt+F4")

        # ── 编辑(&E) ──────────────────────────────
        edit_menu = mb.addMenu("编辑(&E)")
        # 使用 lambda 延迟绑定，因为菜单构建时 sql_edit 尚未创建
        def _editor_action(slot):
            return lambda: getattr(self.sql_edit, slot)()
        edit_menu.addAction("撤销        Ctrl+Z", _editor_action("undo"))
        edit_menu.addAction("重做        Ctrl+Y", _editor_action("redo"))
        edit_menu.addSeparator()
        edit_menu.addAction("剪切        Ctrl+X", _editor_action("cut"))
        edit_menu.addAction("复制        Ctrl+C", _editor_action("copy"))
        edit_menu.addAction("粘贴        Ctrl+V", _editor_action("paste"))
        edit_menu.addSeparator()
        edit_menu.addAction("全选        Ctrl+A", _editor_action("selectAll"))
        edit_menu.addAction("清除", self._on_clear_editor)

        # ── AI 配置(&V) ────────────────────────────
        ai_menu = mb.addMenu("AI 配置(&V)")
        ai_menu.addAction(Icon.prefixed_text('robot', "AI 对话助手        F12"), self._open_ai_chat)
        ai_menu.addAction("大模型配置…", self._open_model_config)
        ai_menu.addSeparator()
        ai_menu.addAction(Icon.prefixed_text('star', "Skill 管理"), self._open_skill_manager)
        ai_menu.addAction(Icon.prefixed_text('download', "导入 Skill 文件…"), self._import_skill)

        # ── 工具(&T) ──────────────────────────────
        tool_menu = mb.addMenu("工具(&T)")
        tool_menu.addAction(Icon.prefixed_text('swap', "数据同步"), self._open_sync)
        tool_menu.addAction(Icon.prefixed_text('schedule', "定时任务"), self._open_scheduler)
        tool_menu.addAction(Icon.prefixed_text('archive', "备份与恢复"), self._open_backup)
        tool_menu.addSeparator()
        tool_menu.addAction(Icon.prefixed_text('folder', "配置文件目录…"), self._set_config_dir)
        tool_menu.addAction(Icon.prefixed_text('database', "查询管理"), self._open_query_manager)
        tool_menu.addAction(Icon.prefixed_text('swap', "Navicat 数据传输…"), self._open_export_import)

        # ── 帮助(&H) ──────────────────────────────
        help_menu = mb.addMenu("帮助(&H)")
        help_menu.addAction(Icon.prefixed_text('book', "使用说明"), self._show_user_guide)
        help_menu.addAction(f"关于 {APP_FULL_NAME}…", self._show_about)


    def _build_toolbar(self):
        """Win11 Fluent Design 风格顶部工具栏 — 纯图标 + 分组分隔"""
        self._toolbar_widget = QWidget()
        self._toolbar_widget.setObjectName("win11Toolbar")
        self._toolbar_widget.setFixedHeight(34)
        tb = QHBoxLayout(self._toolbar_widget)
        tb.setContentsMargins(6, 0, 6, 0)
        tb.setSpacing(0)

        icon_size = 15

        def _add_icon_btn(icon_name, tooltip, handler, size=icon_size, use_svg=None):
            """创建一个纯图标工具按钮；use_svg 为 SVG 文件名时改用 setIcon"""
            btn = QToolButton()
            btn.setFixedSize(30, 28)
            btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setToolTip(tooltip)
            btn.clicked.connect(handler)
            btn.setObjectName("tbIcon")
            if use_svg:
                btn.setIcon(Icon.svg_icon(use_svg, size))
                btn.setIconSize(btn.size())
            else:
                btn.setText(Icon.char(icon_name))
                btn.setFont(Icon.font(size))
            tb.addWidget(btn)
            return btn

        def _add_separator():
            """添加分组间距"""
            tb.addSpacing(6)

        # ── 分组1：连接管理 ──
        self.toolbar_btn_new_conn = QPushButton(" 新建连接")
        self.toolbar_btn_new_conn.setIcon(Icon.svg_icon('connect.svg', 16))
        self.toolbar_btn_new_conn.setFixedHeight(26)
        self.toolbar_btn_new_conn.setToolTip("新建连接 (Ctrl+N)")
        self.toolbar_btn_new_conn.clicked.connect(self._on_new_conn)
        self.toolbar_btn_new_conn.setObjectName("tbText")
        tb.addWidget(self.toolbar_btn_new_conn)

        self.toolbar_btn_import_ncx = QPushButton(Icon.prefixed_text('file_download', "导入NCX"))
        self.toolbar_btn_import_ncx.setFont(Icon.font(13))
        self.toolbar_btn_import_ncx.setFixedHeight(26)
        self.toolbar_btn_import_ncx.setToolTip("导入NCX")
        self.toolbar_btn_import_ncx.clicked.connect(self._on_import_ncx)
        self.toolbar_btn_import_ncx.setObjectName("tbText")
        tb.addWidget(self.toolbar_btn_import_ncx)

        _add_separator()

        # ── 分组2：SQL 操作（带文字，执行按钮蓝色）──
        btn_exec = QPushButton(" 执行")
        btn_exec.setIcon(Icon.svg_icon('execute.svg', 16))
        btn_exec.setFixedHeight(26)
        btn_exec.setProperty("role", "primary")
        btn_exec.setToolTip("执行全部 SQL (F5)")
        btn_exec.clicked.connect(self._on_exec)
        btn_exec.setObjectName("tbText")
        tb.addWidget(btn_exec)

        btn_exec_sel = QPushButton(Icon.prefixed_text('arrow_right', "执行选中"))
        btn_exec_sel.setFont(Icon.font(13))
        btn_exec_sel.setFixedHeight(26)
        btn_exec_sel.setToolTip("执行选中 SQL (F6)")
        btn_exec_sel.clicked.connect(self._on_exec_selected)
        btn_exec_sel.setObjectName("tbText")
        tb.addWidget(btn_exec_sel)

        btn_format = QPushButton(Icon.prefixed_text('code', "格式化"))
        btn_format.setFont(Icon.font(13))
        btn_format.setFixedHeight(26)
        btn_format.setToolTip("格式化 SQL (Ctrl+Shift+F)")
        btn_format.clicked.connect(self._on_format_sql)
        btn_format.setObjectName("tbText")
        tb.addWidget(btn_format)

        _add_separator()

        # ── 分组3：数据操作 ──
        btn_export_data = QPushButton(" 导出")
        btn_export_data.setIcon(Icon.svg_icon('导出.svg', 16))
        btn_export_data.setFixedHeight(26)
        btn_export_data.setToolTip("导出数据")
        btn_export_data.clicked.connect(self._open_export_import)
        btn_export_data.setObjectName("tbText")
        tb.addWidget(btn_export_data)

        btn_sync = QPushButton(Icon.prefixed_text('swap', "同步"))
        btn_sync.setFont(Icon.font(13))
        btn_sync.setFixedHeight(26)
        btn_sync.setToolTip("数据同步")
        btn_sync.clicked.connect(self._open_sync)
        btn_sync.setObjectName("tbText")
        tb.addWidget(btn_sync)

        btn_queries = QPushButton(Icon.prefixed_text('database', "查询管理"))
        btn_queries.setFont(Icon.font(13))
        btn_queries.setFixedHeight(26)
        btn_queries.setToolTip("查询管理")
        btn_queries.clicked.connect(self._open_query_manager)
        btn_queries.setObjectName("tbText")
        tb.addWidget(btn_queries)

        _add_separator()

        # ── 分组4：刷新 ──
        btn_refresh_tb = QPushButton(Icon.prefixed_text('refresh', "刷新"))
        btn_refresh_tb.setFont(Icon.font(13))
        btn_refresh_tb.setFixedHeight(26)
        btn_refresh_tb.setToolTip("刷新连接树")
        btn_refresh_tb.clicked.connect(self._on_refresh)
        btn_refresh_tb.setObjectName("tbText")
        tb.addWidget(btn_refresh_tb)

        tb.addStretch()

        # ── 右侧：主题切换 + AI 面板 ──
        self.toolbar_btn_theme = _add_icon_btn('sun', "切换主题", self._toggle_theme)
        self._update_theme_btn_icon()
        self.toolbar_btn_ai = _add_icon_btn('robot', "AI 助手", self._toggle_ai_chat_panel, use_svg='AI对话.svg')


    def _build_left_panel(self):
        panel = QWidget()
        panel.setObjectName("leftPanel")
        panel.setMinimumWidth(196)

        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        card = QWidget()
        card.setObjectName("sidebarCard")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(12, 10, 12, 10)
        card_layout.setSpacing(6)

        title_row = QHBoxLayout()
        title_row.setContentsMargins(0, 0, 0, 0)
        title_row.setSpacing(4)

        title = QLabel("数据库连接")
        title.setProperty("role", "panelTitle")
        title_row.addWidget(title)
        title_row.addStretch()

        # Navicat 17 风格：左侧面板顶部快捷按钮组
        btn_new = QToolButton()
        btn_new.setText(Icon.char('add'))
        btn_new.setFont(Icon.font(16))
        btn_new.setFixedSize(22, 22)
        btn_new.setToolTip("新建连接")
        btn_new.clicked.connect(self._on_new_conn)
        title_row.addWidget(btn_new)

        btn_refresh = QToolButton()
        btn_refresh.setText(Icon.char('refresh'))
        btn_refresh.setFont(Icon.font(14))
        btn_refresh.setFixedSize(22, 22)
        btn_refresh.setToolTip("刷新连接列表")
        btn_refresh.clicked.connect(self._on_refresh)
        title_row.addWidget(btn_refresh)

        card_layout.addLayout(title_row)

        # 连接搜索栏（Navicat 17 新增）
        self._conn_search = QLineEdit()
        self._conn_search.setPlaceholderText("搜索连接…")
        self._conn_search.setFixedHeight(24)
        self._conn_search.setClearButtonEnabled(True)
        self._conn_search.textChanged.connect(self._filter_conn_tree)
        card_layout.addWidget(self._conn_search)

        self.tree = QTreeWidget()
        self.tree.setObjectName("connectionTree")
        self.tree.setHeaderHidden(True)
        self.tree.setAnimated(True)
        self.tree.setIndentation(16)
        self.tree.setUniformRowHeights(False)
        self.tree.setExpandsOnDoubleClick(False)
        self.tree.setAllColumnsShowFocus(True)
        self.tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self._tree_context_menu)
        self.tree.itemExpanded.connect(self._on_tree_expanded)
        self.tree.itemDoubleClicked.connect(self._on_tree_double_click)
        self.tree.itemClicked.connect(self._on_tree_click)
        self.tree.currentItemChanged.connect(self._on_tree_current_changed)
        # Navicat 风格：无外部边框
        self.tree.setFrameShape(QFrame.Shape.NoFrame)
        card_layout.addWidget(self.tree, stretch=1)

        layout.addWidget(card)
        return panel


    def _build_right_panel(self):
        """右侧面板：左边 SQL 工作区，右边 AI 对话面板（左右 Splitter）"""
        tokens = self._tokens
        outer = QWidget()
        outer.setObjectName("rightPanel")
        outer_layout = QHBoxLayout(outer)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.setSpacing(0)

        h_splitter = QSplitter(Qt.Orientation.Horizontal)
        h_splitter.setObjectName("workChatSplitter")
        h_splitter.setHandleWidth(1)

        h_splitter.setChildrenCollapsible(True)
        h_splitter.setCollapsible(0, False)
        h_splitter.setCollapsible(1, True)
        self._work_chat_splitter = h_splitter



        # ── 左：SQL 工作区 ──────────────────────────
        work_panel = QWidget()
        work_layout = QVBoxLayout(work_panel)
        work_layout.setContentsMargins(0, 0, 0, 0)
        work_layout.setSpacing(0)

        # ── 垂直三段 Splitter：SQL编辑器 / 数据区 / 日志区（可最小化） ──
        v_splitter = QSplitter(Qt.Orientation.Vertical)
        v_splitter.setObjectName("workVerticalSplitter")
        v_splitter.setHandleWidth(1)

        v_splitter.setChildrenCollapsible(False)
        self._work_v_splitter = v_splitter


        # ── 段1：SQL 编辑器区 ────────────────────────
        sql_panel = QWidget()
        sql_panel.setObjectName("sectionCard")
        sql_layout = QVBoxLayout(sql_panel)
        sql_layout.setContentsMargins(12, 16, 12, 10)
        sql_layout.setSpacing(0)

        # 标题行：SQL 徽章 + 标题 + 分隔线 + 状态胶囊组
        sql_title_row = QHBoxLayout()
        sql_title_row.setContentsMargins(5, 0, 0, 5)
        sql_title_row.setSpacing(8)

        sql_badge = QLabel("SQL")
        sql_badge.setObjectName("sqlBadge")
        sql_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sql_badge.setStyleSheet(f"background:{tokens['accent_soft']}; color:{tokens['accent']}; border:0px solid {tokens['accent_hover']}; border-radius:4px; padding:1px 7px; font-size:12px; font-weight:700;")
        self._sql_badge = sql_badge
        sql_title_row.addWidget(sql_badge)

        sql_title = QLabel("工作台")
        sql_title.setProperty("role", "panelTitle")
        sql_title_row.addWidget(sql_title)

        # 用 Stretch 实现弹性分隔
        sql_title_row.addStretch(1)

        self._status_conn = QLabel("未连接")
        self._status_conn.setStyleSheet(
            f"font-size:11px; color:{tokens['text_muted']}; "
            f"background:{tokens['bg']}; border:0px solid {tokens['border']}; "
            f"border-radius:4px; padding:2px 8px;"
        )
        sql_title_row.addWidget(self._status_conn)

        self._status_theme = QLabel("")
        self._status_theme.setProperty("role", "statusAccent")
        self._status_theme.setVisible(False)
        sql_title_row.addWidget(self._status_theme)

        sql_layout.addLayout(sql_title_row)

        ai_row = QHBoxLayout()
        ai_row.setSpacing(6)

        # AI 输入框：包裹在带图标的容器里（⚡ 图标 + 输入框）
        self.ai_input = QLineEdit()
        self.ai_input.setObjectName("aiInputField")
        self.ai_input.setPlaceholderText("描述需求，AI 生成 SQL…")
        self.ai_input.setMinimumHeight(30)
        self.ai_input.setStyleSheet("border:none; background:transparent;")

        # 左侧 ✨ 图标（用 QLabel 叠加在输入框左侧 — 用 sparkles 代表 AI）
        self._ai_input_icon = QLabel("\u2728")  # ✨
        self._ai_input_icon.setFont(Icon.font(13))
        self._ai_input_icon.setFixedWidth(28)
        self._ai_input_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._ai_input_icon.setStyleSheet(
            f"background:transparent; color:{tokens['text_muted']}; border:none; padding:0;"
        )

        # 用 QHBoxLayout 模拟 .ai-input-wrap（图标 + 输入框）
        ai_input_wrap = QWidget()
        ai_input_wrap.setStyleSheet(
            f"background:{tokens['bg']}; border:none; "
            f"border-radius:6px; padding:0 10px 0 0;"
        )
        ai_input_wrap_layout = QHBoxLayout(ai_input_wrap)
        ai_input_wrap_layout.setContentsMargins(0, 0, 0, 0)
        ai_input_wrap_layout.setSpacing(6)
        ai_input_wrap_layout.addWidget(self._ai_input_icon)
        ai_input_wrap_layout.addWidget(self.ai_input, stretch=1)

        # AI 输入框聚焦时触发容器 focus-within 效果
        self.ai_input.installEventFilter(self)

        # 主按钮：生成（强调色）/ 优化（次级灰）
        btn_ai_gen = QPushButton("\u25b6 \u751f\u6210")  # ▶ 生成
        btn_ai_gen.setObjectName("tbText")
        btn_ai_gen.setProperty("role", "primary")
        btn_ai_gen.setFixedHeight(28)
        btn_ai_gen.setStyleSheet(
            f"QPushButton{{background:{tokens['accent']}; color:#fff; border:none; "
            f"border-radius:5px; padding:5px 10px; font-size:12px; font-weight:500;}}"
            f"QPushButton:hover{{background:{tokens['accent_hover']};}}"
            f"QPushButton:pressed{{background:{tokens['accent_pressed']};}}"
        )
        btn_ai_gen.clicked.connect(self._on_ai_gen)
        self._btn_ai_gen = btn_ai_gen

        btn_ai_opt = QPushButton("\u26a1 \u4f18\u5316")  # ⚡ 优化
        btn_ai_opt.setObjectName("tbText")
        btn_ai_opt.setFixedHeight(28)
        btn_ai_opt.setStyleSheet(
            f"QPushButton{{background:{tokens['surface_alt']}; color:{tokens['text_soft']}; "
            f"border:1px solid {tokens['border']}; border-radius:5px; padding:5px 10px; font-size:12px;}}"
            f"QPushButton:hover{{background:{tokens['surface_hover']}; color:{tokens['text']};}}"
        )
        btn_ai_opt.clicked.connect(self._on_ai_opt)
        self._btn_ai_opt = btn_ai_opt

        # 分隔符
        def _make_sep():
            w = QWidget()
            w.setObjectName("toolbarSep")
            w.setFixedWidth(1)
            w.setFixedHeight(18)
            w.setStyleSheet(f"background:{tokens['border']}; min-width:1px; max-width:1px; margin:0 2px; border-radius:1px;")
            return w

        # 片段按钮（图标风格）
        self._btn_snippets = QToolButton()
        self._btn_snippets.setObjectName("tbIcon")
        self._btn_snippets.setText("{ }")
        self._btn_snippets.setFixedSize(28, 28)
        self._btn_snippets.setToolTip("插入常用 SQL 代码片段")
        self._btn_snippets.clicked.connect(lambda: self._show_snippets_menu(self._btn_snippets))

        # 专注模式
        self._btn_focus = QPushButton("⛶ 专注")
        self._btn_focus.setFont(Icon.font(13))
        self._btn_focus.setObjectName("btnFocus")
        self._btn_focus.setFixedHeight(28)
        self._btn_focus.setCheckable(True)
        self._btn_focus.setToolTip("专注模式：隐藏左侧连接面板，聚焦SQL编辑 (F11)")
        self._btn_focus.setShortcut("F11")
        self._btn_focus.toggled.connect(self._on_focus_mode_toggled)

        ai_row.addWidget(ai_input_wrap, stretch=1)
        ai_row.addWidget(btn_ai_gen)
        ai_row.addWidget(btn_ai_opt)
        ai_row.addWidget(_make_sep())
        ai_row.addWidget(self._btn_snippets)
        ai_row.addWidget(self._btn_focus)

        sql_layout.addLayout(ai_row)

        # ── SQL 多标签页（Navicat 17 风格）──────────────
        self._sql_tab_bar = QTabBar()
        self._sql_tab_bar.setObjectName("sqlTabBar")
        self._sql_tab_bar.setTabsClosable(True)
        self._sql_tab_bar.setMovable(True)
        self._sql_tab_bar.setExpanding(False)
        self._sql_tab_bar.tabCloseRequested.connect(self._close_sql_tab)
        self._sql_tab_bar.currentChanged.connect(self._on_sql_tab_switched)

        # "+" 新建标签按钮
        btn_new_tab = QToolButton()
        btn_new_tab.setText("+")
        btn_new_tab.setFixedSize(24, 24)
        btn_new_tab.setToolTip("新建查询标签页 (Ctrl+T)")
        btn_new_tab.clicked.connect(self._add_sql_tab)
        btn_new_tab.setObjectName("newTabBtn")

        # "保存" 按钮
        self._btn_save_query = QToolButton()
        self._btn_save_query.setText(Icon.char('save'))
        self._btn_save_query.setFont(Icon.font(14))
        self._btn_save_query.setFixedSize(24, 24)
        self._btn_save_query.setToolTip("保存当前查询")
        self._btn_save_query.clicked.connect(self._on_save_current_query)
        self._btn_save_query.setObjectName("btnSaveQuery")

        # "导入" 按钮
        self._btn_import_query = QToolButton()
        self._btn_import_query.setText(Icon.char('download'))
        self._btn_import_query.setFont(Icon.font(14))
        self._btn_import_query.setFixedSize(24, 24)
        self._btn_import_query.setToolTip("从已保存的查询中导入")
        self._btn_import_query.clicked.connect(self._on_show_saved_queries_menu)
        self._btn_import_query.setObjectName("btnImportQuery")

        tab_row = QHBoxLayout()
        tab_row.setContentsMargins(0, 0, 0, 0)
        tab_row.setSpacing(4)
        tab_row.addWidget(self._sql_tab_bar, stretch=1)
        tab_row.addWidget(self._btn_save_query)
        tab_row.addWidget(self._btn_import_query)
        tab_row.addWidget(btn_new_tab)
        sql_layout.addLayout(tab_row)

        # 堆叠式 SQL 编辑器（每个标签对应一个）
        self._sql_editor_stack = QStackedWidget()
        sql_layout.addWidget(self._sql_editor_stack, stretch=1)

        # 初始化第一个标签
        self._sql_tabs: list[QTextEdit] = []
        self._add_sql_tab(title="查询 1")

        # sql_edit 始终指向当前激活的编辑器（供其他方法直接使用）
        self.sql_edit = self._sql_tabs[0]

        v_splitter.addWidget(sql_panel)

        # ── 段2：数据操作工具栏 + 结果表格 ──────────────────
        data_panel = QWidget()
        data_panel.setObjectName("sectionCard")
        data_layout = QVBoxLayout(data_panel)
        data_layout.setContentsMargins(12, 10, 12, 10)
        data_layout.setSpacing(6)

        data_action_bar = QHBoxLayout()
        data_action_bar.setContentsMargins(0, 0, 0, 0)
        data_action_bar.setSpacing(4)

        data_title = QLabel("结果")
        data_title.setProperty("role", "panelTitle")
        data_action_bar.addWidget(data_title)

        self.lbl_result_info = QLabel("")
        self.lbl_result_info.setProperty("role", "muted")
        self.lbl_result_info.setStyleSheet(
            f"font-size:11px; font-weight:500; color:{tokens['info']}; "
            f"background:{tokens['surface_alt']}; border:1px solid {tokens['border']}; "
            f"border-radius:10px; padding:1px 6px;"
        )
        data_action_bar.addWidget(self.lbl_result_info)
        self.lbl_result_info.hide()  # 初始隐藏

        self.lbl_selected_info = QLabel("已选 0 行")
        self.lbl_selected_info.setProperty("role", "muted")
        self.lbl_selected_info.setStyleSheet(
            f"font-size:10px; color:{tokens['text_muted']}; background:transparent; border:none; padding:0;"
        )
        data_action_bar.addWidget(self.lbl_selected_info)
        self.lbl_selected_info.hide()  # 初始隐藏

        # 统计条（monospace 风格，强调色背景 — 预览精确色值）
        self._lbl_stat_bar = QLabel("")
        self._lbl_stat_bar.setObjectName("statBar")
        self._lbl_stat_bar.setStyleSheet(
            f"color:{tokens['accent']}; background:{tokens['accent_soft']}; "
            f"border:1px solid {tokens['accent_hover']}; border-radius:4px; "
            f"padding:2px 8px; font-size:10px; "
            f"font-family:Consolas,'Cascadia Code',monospace; font-weight:500;"
        )
        data_action_bar.addWidget(self._lbl_stat_bar)
        self._lbl_stat_bar.hide()  # 初始隐藏

        def _sep(parent):
            """工具栏视觉分隔条"""
            w = QWidget(parent)
            w.setObjectName("toolbarSep")
            w.setFixedWidth(1)
            w.setFixedHeight(18)
            w.setStyleSheet(f"background:{tokens['border']}; min-width:1px; max-width:1px; margin:0 4px; border-radius:1px;")
            return w

        def _tb(parent, icon_key, label, handler, height=28, obj="toolbarBtn",
                 style="view", tooltip="", checkable=False, toggled=None):
            """统一工具栏按钮工厂"""
            btn = QToolButton(parent)
            btn.setObjectName(obj)
            btn.setText(Icon.prefixed_text(icon_key, label))
            btn.setFont(Icon.font(13))
            btn.setFixedHeight(height)
            btn.setToolTip(tooltip or "")
            btn.setCheckable(checkable)
            btn.setProperty("tbStyle", style)  # 用于主题切换时重建 QSS
            t = tokens  # 使用外层作用域的 tokens
            if style == "view":
                btn.setStyleSheet(
                    f"QToolButton#toolbarBtn{{background:transparent; color:{t['info']}; "
                    f"border:none; border-radius:4px; padding:3px 8px; font-size:11px;}}"
                    f"QToolButton#toolbarBtn:hover{{background:{t['surface_hover']}; color:{t['text']};}}"
                )
            elif style == "accent":
                btn.setStyleSheet(
                    f"QToolButton#toolbarBtn{{background:transparent; color:{t['accent']}; "
                    f"border:none; border-radius:4px; padding:3px 8px; font-size:11px;}}"
                    f"QToolButton#toolbarBtn:hover{{background:{t['accent_soft']}; color:{t['accent']};}}"
                )
            elif style == "danger":
                btn.setStyleSheet(
                    f"QToolButton#toolbarBtn{{background:transparent; color:{t['danger']}; "
                    f"border:none; border-radius:4px; padding:3px 8px; font-size:11px;}}"
                    f"QToolButton#toolbarBtn:hover{{background:{t['danger_soft']}; color:{t['danger']};}}"
                )
            elif style == "pin":
                btn.setStyleSheet(
                    f"QToolButton#toolbarBtn{{background:transparent; color:{t['info']}; "
                    f"border:none; border-radius:4px; padding:3px 8px; font-size:11px;}}"
                    f"QToolButton#toolbarBtn:hover{{background:{t['surface_hover']}; color:{t['text']};}}"
                    f"QToolButton#toolbarBtn:checked{{background:{t['warning_soft']}; color:{t['warning']};}}"
                )
            if handler is not None:
                btn.clicked.connect(handler)
            if checkable and toggled:
                btn.toggled.connect(toggled)
            return btn

        data_action_bar.addStretch()

        # ── 分组1：选择操作（已移至表格表头复选框）──
        # 保留按钮占位但隐藏，用于右键菜单等功能
        self.btn_select_all = _tb(sql_panel, 'check', "全选", lambda: self._on_header_clicked(0), tooltip="全选所有行 (Ctrl+A)")
        self.btn_select_none = _tb(sql_panel, 'close', "取消", self._on_select_none, tooltip="取消所有选择")
        self.btn_select_all.hide()  # 已移至表头复选框
        self.btn_select_none.hide()  # 已移至表头复选框

        # ── 分组2：复制导出 ──
        self.btn_copy_selected = _tb(sql_panel, 'clipboard', "复制", self._on_copy_selected_rows, tooltip="复制选中行到剪贴板（Tab 分隔）")
        self.btn_export_selected = _tb(sql_panel, 'upload', "导出", self._on_export_selected_rows, tooltip="将选中行导出为 CSV / Excel")
        data_action_bar.addWidget(self.btn_copy_selected)
        data_action_bar.addWidget(self.btn_export_selected)
        data_action_bar.addWidget(_sep(sql_panel))

        # ── 分组3：编辑操作（强调色） ──
        self.btn_edit_mode = _tb(sql_panel, 'edit', "编辑", None, checkable=True, toggled=self._on_edit_mode_toggled, style="accent", tooltip="开启后可双击单元格直接修改数据")
        self.btn_add_row = _tb(sql_panel, 'add', "新增", self._on_add_row, style="accent", tooltip="新增一行数据")
        self.btn_delete_selected = _tb(sql_panel, 'delete', "删除", self._on_delete_selected_rows, style="danger", tooltip="删除选中行")
        data_action_bar.addWidget(self.btn_edit_mode)
        data_action_bar.addWidget(self.btn_add_row)
        data_action_bar.addWidget(self.btn_delete_selected)
        data_action_bar.addWidget(_sep(sql_panel))

        # ── 分组4：工具 ──
        self._btn_pin_result = _tb(sql_panel, 'pushpin', "固定", self._on_pin_result, style="pin", tooltip="固定当前结果")
        data_action_bar.addWidget(self._btn_pin_result)

        data_layout.addLayout(data_action_bar)

        # ── 快速过滤栏（独立容器样式）─────────────────
        self._filter_container = QWidget()
        self._filter_container.setObjectName("filterBarContainer")
        self._filter_container.setFixedHeight(32)  # 固定高度：CSS padding(4+4) + 内容(32)
        filter_layout = QHBoxLayout(self._filter_container)
        filter_layout.setContentsMargins(10, 0, 10, 0)
        filter_layout.setSpacing(6)

        filter_icon = QLabel('🔍')
        filter_icon.setStyleSheet(f"color:{tokens['text_muted']}; font-size:14px; background:transparent; border:none; padding:0; margin:0;")
        filter_icon.setFixedWidth(18)
        filter_layout.addWidget(filter_icon)

        self._filter_input = QLineEdit()
        self._filter_input.setPlaceholderText("快速过滤（关键词 / 正则）…")
        self._filter_input.setFixedHeight(32)
        self._filter_input.setClearButtonEnabled(True)
        self._filter_input.setStyleSheet(
            "QLineEdit{"
            "border:none; background:transparent; "
            "padding:0; margin:0; font-size:13px; "
            f"color:{tokens['text']}; outline:none;"
            "}"
            "QLineEdit:focus{outline:none;}"
        )
        self._filter_input.textChanged.connect(self._apply_table_filter)
        filter_layout.addWidget(self._filter_input, stretch=1)

        self._filter_col_combo = QComboBox()
        self._filter_col_combo.setFixedHeight(28)
        self._filter_col_combo.setFixedWidth(90)
        self._filter_col_combo.setToolTip("限定过滤列")
        self._filter_col_combo.setStyleSheet(
            f"QComboBox{{border:none; background:transparent; font-size:12px; "
            f"color:{tokens['text_muted']}; padding:0 4px 0 8px; outline:none;}}"
            f"QComboBox:hover{{color:{tokens['text']};}}"
            f"QComboBox::dropDown{{border:none; background:transparent; width:16px;}}"
            f"QComboBox::down-arrow{{image:none; width:0;}}"
            f"QComboBox QAbstractItemView{{"
            f"background:{tokens['surface']}; color:{tokens['text']}; "
            f"border:1px solid {tokens['border']}; border-radius:6px; "
            f"font-size:12px; padding:4px; selection-background-color:{tokens['surface_hover']};}}"
        )
        self._filter_col_combo.addItem("全部列")
        self._filter_col_combo.currentIndexChanged.connect(self._apply_table_filter)
        filter_layout.addWidget(self._filter_col_combo)

        self._filter_case_btn = QToolButton()
        self._filter_case_btn.setObjectName("filterToggle")
        self._filter_case_btn.setText("Aa")
        self._filter_case_btn.setCheckable(True)
        self._filter_case_btn.setFixedSize(24, 24)
        self._filter_case_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._filter_case_btn.setToolTip("区分大小写")
        self._filter_case_btn.toggled.connect(self._apply_table_filter)
        filter_layout.addWidget(self._filter_case_btn)

        self._filter_regex_btn = QToolButton()
        self._filter_regex_btn.setObjectName("filterToggle")
        self._filter_regex_btn.setText(".*")
        self._filter_regex_btn.setCheckable(True)
        self._filter_regex_btn.setFixedSize(24, 24)
        self._filter_regex_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._filter_regex_btn.setToolTip("正则表达式模式")
        self._filter_regex_btn.toggled.connect(self._apply_table_filter)
        filter_layout.addWidget(self._filter_regex_btn)

        # filterBarContainer focus-within：输入框聚焦时容器边框变强调色
        self._filter_input.installEventFilter(self)

        self._filter_count_label = QLabel("")
        self._filter_count_label.setStyleSheet(
            f"font-size:11px; font-family:Consolas,monospace; "
            f"color:{tokens['text_muted']}; background:transparent; "
            f"border:none; padding:0px; margin-left:0px;"
        )
        filter_layout.addWidget(self._filter_count_label)

        # 将过滤栏容器包装在水平居中的布局中
        filter_wrapper = QWidget()
        filter_wrapper_layout = QHBoxLayout(filter_wrapper)
        filter_wrapper_layout.setContentsMargins(0, 0, 0, 0)
        filter_wrapper_layout.setSpacing(0)
        filter_wrapper_layout.addWidget(self._filter_container)
        filter_wrapper_layout.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        data_layout.addWidget(filter_wrapper)

        # _tb() 工厂函数已统一设置样式，无需额外覆盖


        self._table_container = QWidget()
        self._table_container.setObjectName("tableContainer")
        self._table_container_layout = QVBoxLayout(self._table_container)
        self._table_container_layout.setContentsMargins(0, 0, 0, 0)
        self._table_container_layout.setSpacing(0)


        self.table = SelectableTableWidget()
        self.table.setShowGrid(False)
        self.table.verticalHeader().setDefaultSectionSize(38)
        self.table.verticalHeader().setMinimumSectionSize(38)
        self.table.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.table.setFrameShape(QFrame.Shape.NoFrame)
        
        # 精致表格样式 - 专业数据表格设计（随后会被 _apply_table_theme 覆盖）
        self.table.setStyleSheet(
            "QTableWidget{"
            "border:none; background:#fefefe; font-size:13px; color:#1f2937; outline:none;"
            "}"
            "QTableWidget::item{"
            "padding:0 16px; "
            "border:none; "
            "border-bottom:1px solid #f3f4f6; "
            "background:transparent;"
            "}"
            "QTableWidget::item:hover:!selected{"
            "background:#f8fafc; "
            "}"
            "QTableWidget::item:selected{"
            "background:#e0e7ff; "
            "color:#3730a3; "
            "}"
            "QHeaderView{"
            "background:#f8fafc; border:none;"
            "}"
            "QHeaderView::section{"
            "background:#f8fafc; "
            "color:#64748b; "
            "font-weight:600; font-size:11px; text-transform:uppercase; letter-spacing:0.5px; "
            "padding:12px 16px; "
            "border:none; "
            "border-bottom:2px solid #e2e8f0; "
            "border-right:1px solid #f1f5f9; "
            "}"
            "QHeaderView::section:hover{"
            "background:#f1f5f9; color:#475569; "
            "}"
            "QScrollBar:vertical{"
            "background:transparent; width:6px; margin:12px 0; border-radius:3px;"
            "}"
            "QScrollBar::handle:vertical{"
            "background:#cbd5e1; border-radius:3px; min-height:28px;"
            "}"
            "QScrollBar::handle:vertical:hover{"
            "background:#94a3b8; "
            "}"
            "QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical{height:0px;}"
            "QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical{background:transparent;}"
            "QScrollBar:horizontal{"
            "background:transparent; height:6px; margin:0 12px; border-radius:3px;"
            "}"
            "QScrollBar::handle:horizontal{"
            "background:#cbd5e1; border-radius:3px; min-width:28px;"
            "}"
            "QScrollBar::handle:horizontal:hover{"
            "background:#94a3b8; "
            "}"
            "QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal{width:0px;}"
            "QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal{background:transparent;}"
        )
        
        # 表格容器包装（参照 HTML 预览的 .result-table-wrap 样式）
        self.table_wrapper = QWidget()
        self.table_wrapper.setObjectName("tableWrapper")
        
        # 表格样式（参照 HTML 预览的 .result-table 样式）
        self.table.setAlternatingRowColors(True)

        def _apply_table_theme():
            """应用表格主题样式（支持亮色/暗色自动切换）"""
            table_styles = get_table_style(self._current_theme)
            self.table_wrapper.setStyleSheet(table_styles['table_wrapper'])
            self.table.setStyleSheet(table_styles['table'])
            # 更新复选框委托样式
            if hasattr(self, '_checkbox_delegate'):
                self._checkbox_delegate.update_colors(
                    table_styles['checkbox']['checked'],
                    table_styles['checkbox']['unchecked_bg'],
                    table_styles['checkbox']['border'],
                    table_styles['checkbox']['checkmark']
                )
            # SortableTableHeader 颜色由其内部 update_checkbox_colors() 更新（见下）
        _apply_table_theme()
        
        self.table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Interactive
        )
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.MultiSelection)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        
        # 应用自定义复选框委托（第0列使用蓝色复选框）
        self._checkbox_delegate = CheckBoxDelegate(self.table, checkbox_column=0)
        self._checkbox_delegate.setTableView(self.table)  # 启用悬停检测
        self.table.setItemDelegateForColumn(0, self._checkbox_delegate)
        # 第0列表头复选框由 SortableTableHeader.paintSection() 绘制（paintSection 读取 header_item.checkState）
        # 记录上次已日志的列选中状态，避免重复打印
        self._last_logged_cols: set = set()
        
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._table_context_menu)
        self.table.cellDoubleClicked.connect(self._on_cell_double_clicked)
        self.table.selectedColumnsChanged.connect(self._on_selected_columns_changed)
        self.table.horizontalHeader().sectionClicked.connect(self._on_header_clicked)

        # 将表格添加到包装容器中
        table_wrapper_layout = QVBoxLayout(self.table_wrapper)
        table_wrapper_layout.setContentsMargins(0, 0, 0, 0)
        table_wrapper_layout.setSpacing(0)
        table_wrapper_layout.addWidget(self.table)
        # 将包装容器添加到主布局
        self._table_container_layout.addWidget(self.table_wrapper, stretch=1)
        page_bar_widget = QWidget()
        page_bar_widget.setObjectName("pageBarWidget")
        page_bar = QHBoxLayout(page_bar_widget)
        page_bar.setContentsMargins(8, 0, 8, 0)
        page_bar.setSpacing(0)
        # 左侧：行数统计信息
        self.lbl_page_info = QLabel("")
        self.lbl_page_info.setProperty("role", "muted")
        self.lbl_page_info.setFixedHeight(22)
        page_bar.addWidget(self.lbl_page_info)
        page_bar.addStretch()
        # ── 翻页按钮组（Navicat 风格）──
        def _page_btn(text, tooltip, handler):
            btn = QPushButton(text)
            btn.setFixedSize(24, 22)
            btn.setProperty("role", "page")
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setToolTip(tooltip)
            btn.clicked.connect(handler)
            page_bar.addWidget(btn)
            return btn
        self.btn_first_page = _page_btn("|◁", "第一页", self._go_first_page)
        self.btn_prev_page = _page_btn("◁", "上一页", self._go_prev_page)
        page_bar.addSpacing(4)
        # 页码显示
        self.spin_page = QSpinBox()
        self.spin_page.setMinimum(1)
        self.spin_page.setMaximum(1)
        self.spin_page.setFixedWidth(36)
        self.spin_page.setFixedHeight(22)
        self.spin_page.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.spin_page.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.NoButtons)
        self.spin_page.valueChanged.connect(self._on_page_spin_changed)
        page_bar.addWidget(self.spin_page)
        self.lbl_total_pages = QLabel("/")
        self.lbl_total_pages.setProperty("role", "muted")
        self.lbl_total_pages.setFixedHeight(22)
        page_bar.addWidget(self.lbl_total_pages)
        self._lbl_total_count = QLabel("1")
        self._lbl_total_count.setProperty("role", "muted")
        self._lbl_total_count.setFixedHeight(22)
        page_bar.addWidget(self._lbl_total_count)
        page_bar.addSpacing(4)
        self.btn_next_page = _page_btn("▷", "下一页", self._go_next_page)
        self.btn_last_page = _page_btn("▷|", "最后一页", self._go_last_page)
        page_bar.addSpacing(8)
        # ── 右侧：每页行数（紧跟翻页按钮，不再加 stretch 将其推开）──
        lbl_ps = QLabel("每页")
        lbl_ps.setProperty("role", "muted")
        lbl_ps.setFixedHeight(22)
        page_bar.addWidget(lbl_ps)
        page_bar.addSpacing(2)
        self.cmb_page_size = QLineEdit("100")
        self.cmb_page_size.setFixedSize(36, 22)
        self.cmb_page_size.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.cmb_page_size.setToolTip("每页显示行数（输入数字后按 Enter 生效）")
        self.cmb_page_size.returnPressed.connect(self._on_page_size_changed_edit)
        page_bar.addWidget(self.cmb_page_size)
        page_bar.addSpacing(2)
        lbl_ps2 = QLabel("行")
        lbl_ps2.setProperty("role", "muted")
        lbl_ps2.setFixedHeight(22)
        page_bar.addWidget(lbl_ps2)
        self._table_container_layout.addWidget(page_bar_widget)
        data_layout.addWidget(self._table_container, stretch=1)
        v_splitter.addWidget(data_panel)
        # ── 段3：日志区（支持最小化） ─────────────────────
        log_panel = QWidget()
        log_panel.setObjectName("sectionCard")
        log_panel.setMinimumHeight(self._log_panel_min_height)
        log_layout = QVBoxLayout(log_panel)
        log_layout.setContentsMargins(12, 10, 12, 10)
        log_layout.setSpacing(6)
        log_title_row = QHBoxLayout()
        log_title_row.setContentsMargins(0, 0, 0, 0)
        log_title_row.setSpacing(4)
        log_title = QLabel("运行日志")
        log_title.setProperty("role", "panelTitle")
        log_title_row.addWidget(log_title)
        # 添加配置文件路径标签
        self._lbl_config_path = QLabel()
        self._lbl_config_path.setProperty("role", "statusPill")
        self._lbl_config_path.setStyleSheet(f"color: {self._tokens['text_muted']}; font-size: 11px;")
        self._update_config_path_label()
        log_title_row.addWidget(self._lbl_config_path)
        log_title_row.addSpacing(8)
        log_title_row.addStretch()
        self._log_toggle_btn = QToolButton()
        self._log_toggle_btn.setIcon(Icon.svg_icon('收起展开-向下.svg', 14))
        self._log_toggle_btn.setIconSize(QSize(14, 14))
        self._log_toggle_btn.setFixedSize(24, 22)
        self._log_toggle_btn.setStyleSheet(
        f"QToolButton {{ border: none; background: transparent; padding: 0; }}"
        f"QToolButton:hover {{ background: transparent; }}"
        )
        self._log_toggle_btn.clicked.connect(self._toggle_log_panel)
        log_title_row.addWidget(self._log_toggle_btn)
        log_layout.addLayout(log_title_row)
        self.log_box = QTextEdit()
        self.log_box.setObjectName("logBox")
        self.log_box.setReadOnly(True)
        self.log_box.setFont(QFont("Consolas", 10))
        self.log_box.setStyleSheet(get_log_box_style(self._current_theme))
        log_layout.addWidget(self.log_box, stretch=1)
        self._log_panel = log_panel
        v_splitter.addWidget(log_panel)
        v_splitter.setSizes([230, 620, self._log_panel_last_height])
        work_layout.addWidget(v_splitter, stretch=1)
        # ── 右：AI 对话面板 ──────────────────────
        self.ai_chat_widget = AIChatWidget(
        parent=self,
        get_schema_fn=self._get_current_schema,
        get_db_info_fn=self._get_current_db_info,
        list_db_contexts_fn=self._list_chat_db_contexts,
        list_skill_items_fn=self._list_chat_skill_items,
        apply_skill_fn=self._on_apply_skill_for_chat,
        execute_fn=self._agent_execute_sql,
        )
        self.ai_chat_widget.setObjectName("sectionCard")
        self.ai_chat_widget.setMinimumWidth(0)
        self.ai_chat_widget.collapseRequested.connect(self._toggle_ai_chat_panel)
        # AI专注模式信号：收起SQL工作台
        self.ai_chat_widget.aiFocusModeChanged.connect(self._on_ai_focus_mode_toggled)
        h_splitter.addWidget(work_panel)
        h_splitter.addWidget(self.ai_chat_widget)
        h_splitter.setSizes([1080, self._ai_chat_last_width])
        outer_layout.addWidget(h_splitter)
        return outer
        # ─── SQL 多标签页管理 ─────────────────────────
    def _make_sql_editor(self) -> QTextEdit:
        """创建一个新的 SQL 编辑器实例"""
        editor = QTextEdit()
        editor.setObjectName("sqlEditor")
        editor.setFont(QFont("Consolas", 12))
        editor.setMinimumHeight(120)
        editor.setStyleSheet(
        f"QTextEdit#sqlEditor{{"
        f"background:{self._tokens['surface']}; border:1px solid {self._tokens['accent_soft']};; border-top:2px solid {self._tokens['accent']}; "
        f"border-top-left-radius: 0px;border-top-right-radius: 0;border-bottom-left-radius: 4px;border-bottom-right-radius: 4px; padding:4px 4px; "
        f"font-family:'Cascadia Code','JetBrains Mono',Consolas,monospace; "
        f"font-size:12px; color:{self._tokens['text']}; line-height:1.6;}}"
        )
        # 应用 SQL 高亮
        try:
            apply_sql_highlighter(editor)
        except Exception:
            pass
        return editor

    def _add_sql_tab(self, title: str = "", content: str = "") -> int:
        """新增一个 SQL 标签页，返回标签索引"""
        idx = len(self._sql_tabs)
        if not title:
            title = f"查询 {idx + 1}"
        editor = self._make_sql_editor()
        if content:
            editor.setPlainText(content)
        self._sql_tabs.append(editor)
        self._sql_editor_stack.addWidget(editor)

        tab_idx = self._sql_tab_bar.addTab(title)
        self._sql_tab_bar.setCurrentIndex(tab_idx)
        # 切换到新标签（会触发 _on_sql_tab_switched）
        return tab_idx

    def _close_sql_tab(self, tab_idx: int):
        """关闭指定标签页（至少保留一个）"""
        if self._sql_tab_bar.count() <= 1:
            # 只剩一个：清空内容而不关闭
            self.sql_edit.clear()
            return
        # 移除标签
        editor = self._sql_tabs.pop(tab_idx)
        self._sql_editor_stack.removeWidget(editor)
        editor.deleteLater()
        self._sql_tab_bar.removeTab(tab_idx)
        # 切换到最后一个激活的标签
        new_idx = min(tab_idx, self._sql_tab_bar.count() - 1)
        self._sql_tab_bar.setCurrentIndex(new_idx)

    def _on_sql_tab_switched(self, tab_idx: int):
        """切换标签页时同步 sql_edit 指针和堆叠窗口"""
        if 0 <= tab_idx < len(self._sql_tabs):
            self._sql_editor_stack.setCurrentIndex(tab_idx)
            self.sql_edit = self._sql_tabs[tab_idx]

    def _rename_current_sql_tab(self, name: str):
        """重命名当前标签页"""
        idx = self._sql_tab_bar.currentIndex()
        if 0 <= idx < self._sql_tab_bar.count():
            self._sql_tab_bar.setTabText(idx, name)

    def _build_statusbar(self):
        bar = self.statusBar()
        bar.showMessage("就绪")
        bar.setSizeGripEnabled(False)
        bar.hide()

        self._refresh_status_badges()

    def _theme_display_name(self, theme: str) -> str:
        return {
        THEME_LIGHT: "紫罗兰",
        THEME_WILLOW: "柳叶绿",
        THEME_DARK: "暗色",
        }.get(theme, str(theme))

    def _update_config_path_label(self):
        """更新配置文件路径标签显示"""
        if hasattr(self, "_lbl_config_path"):
            path = get_config_path()
            self._lbl_config_path.setText(f"配置：{path}")

    def _refresh_status_badges(self):
        if hasattr(self, "_status_conn"):
            conn_text = self._current_conn_name or "未连接"
            self._status_conn.setText(f"连接：{conn_text}")
        if hasattr(self, "_status_theme"):
            self._status_theme.setText(self._theme_display_name(self._current_theme))



    # ─── 连接持久化 ─────────────────────────
    def _load_saved_connections(self):
        """启动时加载已保存的连接，显示在树上（不自动连接）"""
        # 记录状态，在加载动画结束后显示欢迎对话框
        self._needs_welcome_dialog = False  # 已禁用欢迎弹窗

        conns = load_connections()
        for info in conns:
            self._add_conn_node(info, connected=False)

        # 记录是否需要显示无连接提示
        self._needs_no_connections_dialog = not conns

    def _on_loading_finished(self):
        """加载动画完全结束后调用，用于显示欢迎对话框"""
        if hasattr(self, '_needs_welcome_dialog') and self._needs_welcome_dialog:
            self._show_welcome_dialog()

        if hasattr(self, '_needs_no_connections_dialog') and self._needs_no_connections_dialog:
            self._show_no_connections_dialog()

    def _show_welcome_dialog(self):
        """显示欢迎对话框，可直接编辑配置目录"""
        default_path = get_config_path()
        current_dir = load_config_dir() or ""

        dlg = QDialog(self)
        dlg.setWindowTitle("欢迎使用团子")
        dlg.setMinimumWidth(480)

        layout = QVBoxLayout(dlg)
        layout.setSpacing(12)

        # 标题
        title_label = QLabel("🎉 欢迎使用团子 AIDBTools")
        title_label.setStyleSheet(f"font-size: 16px; font-weight: bold; color: {self._tokens['text']};")
        layout.addWidget(title_label)

        # 说明
        info_label = QLabel("请设置配置文件保存目录（可手动输入或浏览选择）：")
        info_label.setStyleSheet(f"font-size: 13px; color: {self._tokens['text_soft']};")
        layout.addWidget(info_label)

        # 路径选择区
        path_layout = QHBoxLayout()
        path_input = QLineEdit()
        path_input.setPlaceholderText("输入或选择配置文件保存目录…")
        path_input.setText(current_dir)
        path_input.setStyleSheet("font-size: 13px;")
        path_layout.addWidget(path_input, 1)

        browse_btn = QPushButton("浏览…")
        browse_btn.setFixedWidth(70)
        browse_btn.clicked.connect(lambda: self._browse_config_dir_for_welcome(path_input))
        path_layout.addWidget(browse_btn)
        layout.addLayout(path_layout)

        # 默认路径说明
        default_label = QLabel(f"默认路径：{default_path}")
        default_label.setStyleSheet(f"color: {self._tokens['text_muted']}; font-size: 11px;")
        layout.addWidget(default_label)

        # 提示
        tip_label = QLabel(
        "💡 提示：配置文件包含数据库连接、UI偏好等数据。"
        )
        tip_label.setStyleSheet(f"color: {self._tokens['text_muted']}; font-size: 12px; background: {self._tokens['surface_alt']}; "
        "padding: 8px; border-radius: 2px;")
        layout.addWidget(tip_label)

        # 按钮行
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        skip_btn = QPushButton("暂不设置")
        skip_btn.clicked.connect(lambda: self._on_skip_config_dir(dlg))
        btn_layout.addWidget(skip_btn)

        save_btn = QPushButton("保存并继续")
        save_btn.setDefault(True)
        save_btn.clicked.connect(lambda: self._save_welcome_config_dir(dlg, path_input))
        btn_layout.addWidget(save_btn)
        layout.addLayout(btn_layout)

        dlg.exec()

    def _browse_config_dir_for_welcome(self, path_input: QLineEdit):
        """欢迎对话框中浏览目录"""
        dir_path = QFileDialog.getExistingDirectory(
        self,
        "选择配置文件保存目录",
        os.path.expanduser("~"),
        QFileDialog.Option.ShowDirsOnly
        )
        if dir_path:
            path_input.setText(dir_path)

    def _on_skip_config_dir(self, dlg: QDialog):
        """点击「暂不设置」：关闭欢迎对话框，打开配置文件目录设置窗口"""
        dlg.accept()
        # 打开配置文件目录设置窗口
        QTimer.singleShot(100, self._set_config_dir)

    def _reload_configs_from_dir(self):
        """重新从当前配置目录加载所有配置文件"""
        from core.connection_store import load_connections, get_config_path

        # 更新状态栏显示
        self._update_config_path_label()

        # 清空现有连接树，重新加载
        self.tree.clear()
        conns = load_connections()
        for info in conns:
            self._add_conn_node(info, connected=False)

        # 如果加载到连接配置，显示提示
        if conns:
            self.log(f"已从 {get_config_path()} 加载 {len(conns)} 个连接配置")
        else:
            # 没有连接时提示创建
            self._show_no_connections_dialog()

    def _save_welcome_config_dir(self, dlg: QDialog, path_input: QLineEdit):
        """保存欢迎对话框中的配置目录，并重新加载配置"""
        new_dir = path_input.text().strip()
        save_config_dir(new_dir)
        dlg.accept()
        # 重新加载该目录下的配置文件
        QTimer.singleShot(100, self._reload_configs_from_dir)

    def _show_no_connections_dialog(self):
        """显示没有连接的提示对话框"""
        config_path = get_config_path()
        msg = (
        "尚未保存任何数据库连接配置。\n\n"
        f"配置文件路径：{config_path}\n\n"
        "点击「确定」创建第一个连接，或在左侧「新建连接」添加。"
        )
        QMessageBox.information(self, "欢迎使用团子", msg)
        # 自动触发新建连接对话框
        QTimer.singleShot(300, self._on_new_conn)

    @staticmethod
    def _star_icon(tokens=None) -> QIcon:
        """绘制星标小图标（Navicat 风格填充星）"""
        import math
        color = (tokens or {}).get("warning", "#f59e0b")
        pix = QPixmap(16, 16)
        pix.fill(Qt.GlobalColor.transparent)
        p = QPainter(pix)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setBrush(QColor(color))
        p.setPen(Qt.PenStyle.NoPen)
        cx, cy, outer_r, inner_r = 8, 8, 7, 3
        pts = []
        for i in range(10):
            angle = math.pi / 2 + i * math.pi / 5
            r = outer_r if i % 2 == 0 else inner_r
            pts.append(QPointF(cx + r * math.cos(angle), cy - r * math.sin(angle)))
        p.drawPolygon(QPolygon(pts))
        p.end()
        return QIcon(pix)

    @staticmethod
    def _no_star_icon(tokens=None) -> QIcon:
        """绘制空心星标图标（未收藏状态）"""
        import math
        color = (tokens or {}).get("text_muted", "#94a3b8")
        pix = QPixmap(16, 16)
        pix.fill(Qt.GlobalColor.transparent)
        p = QPainter(pix)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.setPen(QPen(QColor(color), 1))
        cx, cy, outer_r, inner_r = 8, 8, 7, 3
        pts = []
        for i in range(10):
            angle = math.pi / 2 + i * math.pi / 5
            r = outer_r if i % 2 == 0 else inner_r
            pts.append(QPointF(cx + r * math.cos(angle), cy - r * math.sin(angle)))
        p.drawPolygon(QPolygon(pts))
        p.end()
        return QIcon(pix)

    @staticmethod
    def _color_bar_icon(hex_color: str) -> QIcon:
        """绘制颜色标记竖条图标（Navicat 风格左侧色条）"""
        pix = QPixmap(16, 16)
        pix.fill(Qt.GlobalColor.transparent)
        p = QPainter(pix)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(hex_color))
        p.drawRoundedRect(0, 1, 3, 14, 1, 1)
        p.end()
        return QIcon(pix)

    def _add_conn_node(self, info: dict, connected=False):
        """在树中新增一个连接节点（未连接状态）"""
        name = info["name"]
        self._conn_infos[name] = info

        root = QTreeWidgetItem(self.tree)
        # Navicat 风格：直接显示连接名，无前导空格
        root.setText(0, name)
        root.setData(0, Qt.ItemDataRole.UserRole, {"type": NODE_CONNECTION, "name": name})
        self._set_conn_icon(root, connected)
        self._apply_conn_color(root, info.get("color", ""))

        # 占位子节点，让展开箭头出现
        placeholder = QTreeWidgetItem(root)
        placeholder.setText(0, "")
        placeholder.setData(0, Qt.ItemDataRole.UserRole, {"type": -1})

    def _set_conn_icon(self, item: QTreeWidgetItem, connected: bool):
        data = item.data(0, Qt.ItemDataRole.UserRole) or {}
        conn_name = data.get("name", "")
        info = self._conn_infos.get(conn_name, {})
        db_type = info.get("db_type", "")
        is_spatial = bool(info.get("is_spatial"))
        meta = self._conn_type_meta(db_type, is_spatial=is_spatial)
        starred = bool(info.get("starred", False))
        color_key = info.get("color", "")

        item.setIcon(0, self._conn_type_icon(db_type, connected, is_spatial=is_spatial,
        starred=starred, color_key=color_key))
        item.setToolTip(
        0,
        f"{conn_name}\n类型：{meta['label']}\n状态：{'已连接' if connected else '未连接'}",
        )

    # 颜色方案：Navicat 风格的8色标记
    _CONN_COLORS = {
        "red":     ("#e53e3e", ""),
        "orange":  ("#ed8936", ""),
        "yellow":  ("#d69e2e", ""),
        "green":   ("#38a169", ""),
        "teal":    ("#319795", ""),
        "blue":    ("#3182ce", ""),
        "purple":  ("#805ad5", ""),
        "gray":    ("#718096", ""),
    }
    _CONN_COLOR_LABELS = {
        "red": "红色", "orange": "橙色", "yellow": "黄色",
        "green": "绿色", "teal": "青色", "blue": "蓝色",
        "purple": "紫色", "gray": "灰色",
    }

    def _apply_conn_color(self, item: QTreeWidgetItem, color: str):
        """对连接节点应用 Navicat 风格颜色标记（左侧竖条图标）"""
        # 文字颜色完全由 QSS 控制（QTreeWidget#connectionTree::item { color: ... }），
        # 不用 setForeground 以免覆盖 QSS

    def _refresh_conn_node_display(self, conn_name: str):
        """刷新连接节点的显示（颜色+星标）"""
        for i in range(self.tree.topLevelItemCount()):
            item = self.tree.topLevelItem(i)
            data = item.data(0, Qt.ItemDataRole.UserRole) or {}
            if data.get("name") == conn_name:
                info = self._conn_infos.get(conn_name, {})
                # Navicat 风格：连接名不带星标前缀
                item.setText(0, conn_name)
                self._apply_conn_color(item, info.get("color", ""))
                # 重新设置连接图标（含状态指示灯）
                connected = conn_name in self._conns
                self._set_conn_icon(item, connected)
                break

    def _tree_item_chat_context(self, item: QTreeWidgetItem | None):
        if item is None:
            return None
        data = item.data(0, Qt.ItemDataRole.UserRole) or {}
        node_type = data.get("type")

        if node_type == NODE_CONNECTION:
            conn_name = (data.get("name") or "").strip()
            if not conn_name:
                return None
            connector = self._conns.get(conn_name)
            info = self._conn_infos.get(conn_name, {})
            db_name = ((getattr(connector, "dbname", "") if connector else "") or info.get("dbname", "")).strip()
            db_type = ((getattr(connector, "db_type", "") if connector else "") or info.get("db_type", "mysql")).strip() or "mysql"
            return self._build_chat_context(conn_name, db_name, db_type)

        if node_type in (NODE_DATABASE, NODE_GROUP, NODE_TABLE, NODE_VIEW, NODE_FUNCTION):
            conn_name = (data.get("conn_name") or "").strip()
            if not conn_name:
                return None
            db_name = (data.get("db_name") or "").strip()
            db_type = self._conn_infos.get(conn_name, {}).get("db_type", "mysql")
            return self._build_chat_context(conn_name, db_name, db_type)

        return None

    def _sync_ai_chat_context(self, context: Optional[dict] = None):
        if not hasattr(self, "ai_chat_widget"):
            return
        if not context:
            self.ai_chat_widget.refresh_contexts()
            return

        conn_name = (context.get("conn_name") or "").strip()
        db_name = (context.get("db_name") or "").strip()
        if conn_name:
            self._current_conn_name = conn_name
            self._current_db_name = db_name
            self._refresh_status_badges()
        self.ai_chat_widget.refresh_contexts(preferred_key=context.get("key", ""))

    # ─── 树交互 ─────────────────────────────

    def _on_tree_expanded(self, item: QTreeWidgetItem):
        data = item.data(0, Qt.ItemDataRole.UserRole)
        if not data:
            return
        node_type = data.get("type")

        if node_type == NODE_CONNECTION:
            self._expand_connection(item, data["name"])
        elif node_type == NODE_DATABASE:
            self._expand_database(item, data["conn_name"], data["db_name"])
        elif node_type == NODE_GROUP:
            self._expand_group(item, data["conn_name"], data["db_name"], data["kind"])

    def _on_tree_current_changed(self, current: QTreeWidgetItem | None, _previous: QTreeWidgetItem | None):
        context = self._tree_item_chat_context(current)
        if context:
            self._sync_ai_chat_context(context)

    def _on_tree_click(self, item: QTreeWidgetItem, col: int):
        """Navicat 风格：单击选中 + 展开/折叠，表/视图自动查询"""
        data = item.data(0, Qt.ItemDataRole.UserRole)
        if not data:
            return
        node_type = data.get("type")

        # 单击展开/折叠（Navicat 标准）
        if node_type in (NODE_CONNECTION, NODE_DATABASE, NODE_GROUP):
            if node_type == NODE_CONNECTION:
                # 连接节点：单击建立连接并展开
                if not item.isExpanded():
                    self.tree.expandItem(item)
                elif data.get("name") not in self._conns:
                    self._expand_connection(item, data["name"])
            else:
                # 数据库/分组：切换展开状态
                if item.isExpanded():
                    self.tree.collapseItem(item)
                else:
                    self.tree.expandItem(item)

        # 表/视图节点：单击自动查询数据
        if node_type in (NODE_TABLE, NODE_VIEW):
            conn_name = data["conn_name"]
            db_name   = data["db_name"]
            table_name = data["table_name"]
            self._load_table_data(conn_name, db_name, table_name)

    def _on_tree_double_click(self, item: QTreeWidgetItem, col: int):
        """Navicat 风格：双击打开编辑器/查询窗口"""
        data = item.data(0, Qt.ItemDataRole.UserRole)
        if not data:
            return

        node_type = data.get("type")
        if node_type == NODE_CONNECTION:
            conn_name = data["name"]
            # 双击连接节点 → 新建查询
            if conn_name in self._conns:
                self._new_query_for_conn(conn_name, item)
            elif not item.isExpanded():
                self.tree.expandItem(item)
            return

        if node_type == NODE_DATABASE:
            # 双击数据库 → 新建查询并 USE 该库
            conn_name = data["conn_name"]
            db_name = data["db_name"]
            self._new_query_for_db(conn_name, db_name, item)
            return

        if node_type == NODE_TABLE:
            # 双击表 → 设计表（Navicat 标准）
            conn_name  = data["conn_name"]
            db_name    = data["db_name"]
            table_name = data["table_name"]
            self._on_design_table(conn_name, db_name, table_name)
            return

        if node_type == NODE_VIEW:
            # 双击视图 → 查看数据
            conn_name  = data["conn_name"]
            db_name    = data["db_name"]
            table_name = data["table_name"]
            self._load_table_data(conn_name, db_name, table_name)
        return

    def _expand_connection(self, item: QTreeWidgetItem, conn_name: str):
        """展开连接节点：先建立连接，再拉取数据库列表"""
        # 已连接则直接刷新子节点
        connector = self._conns.get(conn_name)
        info = self._conn_infos[conn_name]

        # ── 密码为空时直接弹编辑框，不尝试连接 ──
        if connector is None and not info.get("pwd"):
            ret = QMessageBox.question(
        self, "密码为空",
        f"连接 [{conn_name}] 的密码未设置，无法连接。\n\n是否立即编辑连接填写密码？",
        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
            # 无论选哪个，都把节点折叠并恢复占位
            item.takeChildren()
            ph = QTreeWidgetItem(item)
            ph.setText(0, "")
            ph.setData(0, Qt.ItemDataRole.UserRole, {"type": -1})
            self.tree.collapseItem(item)
            if ret == QMessageBox.StandardButton.Yes:
                self._on_edit_conn(conn_name)
            return

        connector = DatabaseConnector()
        ok, msg = connector.connect(
        info["db_type"], info["host"], info["port"],
        info["user"], info["pwd"], info["dbname"],
        jar_path=info.get("jar_path", ""),
        is_spatial=info.get("is_spatial", False),
        )
        self.log(f"[{conn_name}] {msg}")
        if not ok:
            # ── 连接失败：折叠节点、恢复占位、弹提示 ──
            item.takeChildren()
            ph = QTreeWidgetItem(item)
            ph.setText(0, "")
            ph.setData(0, Qt.ItemDataRole.UserRole, {"type": -1})
            self.tree.collapseItem(item)
            self.statusBar().showMessage(msg)
            lines = [line.strip() for line in msg.splitlines() if line.strip()]
            summary = lines[0] if lines else msg
            details = "\n".join(lines[1:]).strip()
            box = QMessageBox(self)
            box.setIcon(QMessageBox.Icon.Critical)
            box.setWindowTitle(f"连接失败 — {conn_name}")
            box.setText(summary)
            box.setStyleSheet(build_popup_base_style(load_theme(), """
QMessageBox QLabel {
    min-width: 320px;
}
QMessageBox QPushButton {
    min-width: 84px;
    padding: 5px 14px;
}
"""))
            if details:
                preview = details[:360] + ("…" if len(details) > 360 else "")
            else:
                preview = ""
            box.setInformativeText(preview)
            box.setDetailedText(msg)
            box.exec()
            return

        # ── 连接成功 ──
        self._conns[conn_name] = connector
        self._set_conn_icon(item, True)
        self.statusBar().showMessage(f"已连接 {conn_name}")

        self._current_conn_name = conn_name
        self._sync_ai_chat_context(self._tree_item_chat_context(item))
        # 清除占位子节点
        item.takeChildren()

        dbs = connector.get_databases()
        for db in dbs:
            db_item = QTreeWidgetItem(item)
            db_item.setText(0, db)
            db_item.setData(0, Qt.ItemDataRole.UserRole, {
                "type": NODE_DATABASE,
                "conn_name": conn_name,
                "db_name": db,
            })
            # 给数据库节点加图标（小数据库桶）
            db_item.setIcon(0, self._db_icon())
            db_item.setToolTip(0, f"数据库：{db}\n连接：{conn_name}\n单击展开查看表/视图/函数")
            # 占位
            ph = QTreeWidgetItem(db_item)
            ph.setText(0, "")
            ph.setData(0, Qt.ItemDataRole.UserRole, {"type": -1})

    def _expand_database(self, item: QTreeWidgetItem, conn_name: str, db_name: str):
        """展开数据库节点：显示 表/视图/函数/索引/存储过程 分组"""
        connector = self._conns.get(conn_name)
        if connector is None:
            return
        item.takeChildren()

        groups = [
        ("表",          NODE_GROUP, "tables"),
        ("视图",        NODE_GROUP, "views"),
        ("函数",        NODE_GROUP, "functions"),
        ("索引",        NODE_GROUP, "indexes"),
        ("存储过程",    NODE_GROUP, "procedures"),
        ]
        for label, gtype, gkind in groups:
            g_item = QTreeWidgetItem(item)
            g_item.setText(0, label)
            g_item.setData(0, Qt.ItemDataRole.UserRole, {
                "type": NODE_GROUP,
                "kind": gkind,
                "conn_name": conn_name,
                "db_name": db_name,
            })
            # Navicat 风格分组图标
            g_item.setIcon(0, self._group_icon(gkind))
            # 占位子节点（让展开箭头出现）
            ph = QTreeWidgetItem(g_item)
            ph.setText(0, "")
            ph.setData(0, Qt.ItemDataRole.UserRole, {"type": -1})

    def _expand_group(self, item: QTreeWidgetItem, conn_name: str, db_name: str, kind: str):
        """展开分组节点：拉取对应类型的对象列表"""
        connector = self._conns.get(conn_name)
        if connector is None:
            return
        item.takeChildren()

        if kind == "tables":
            names = connector.get_tables(db_name)
            node_type = NODE_TABLE
        elif kind == "views":
            names = connector.get_views(db_name)
            node_type = NODE_VIEW
        elif kind == "functions":
            names = connector.get_functions(db_name)
            node_type = NODE_FUNCTION
        elif kind == "indexes":
            names = connector.get_indexes(db_name)
            node_type = NODE_INDEX
        elif kind == "procedures":
            names = connector.get_procedures(db_name)
            node_type = NODE_PROCEDURE
        else:
            names = []
            node_type = NODE_TABLE

        if not names:
            empty = QTreeWidgetItem(item)
            empty.setText(0, "(空)")
            empty.setData(0, Qt.ItemDataRole.UserRole, {"type": -1})
            empty.setFlags(empty.flags() & ~Qt.ItemFlag.ItemIsSelectable)
            return

        # 预取列信息用于 tooltip（只取一次，失败则降级）
        col_map: dict[str, list] = {}
        try:
            schema_rows = connector.get_schema_rows(db_name) or []
            for row in schema_rows:
                tbl = str(row[0]) if row[0] else ""
                col = str(row[1]) if len(row) > 1 and row[1] else ""
                col_type = str(row[2]) if len(row) > 2 and row[2] else ""
                comment = str(row[3]) if len(row) > 3 and row[3] else ""
                if tbl:
                    col_map.setdefault(tbl, []).append((col, col_type, comment))
        except Exception:
            col_map = {}

        # 记录数量到分组节点显示
        count_label = f" ({len(names)})" if names else ""
        item.setText(0, item.text(0).split(" (")[0] + count_label)

        for name in names:
            t_item = QTreeWidgetItem(item)
            t_item.setText(0, name)
            t_item.setData(0, Qt.ItemDataRole.UserRole, {
                "type": node_type,
                "kind": kind,
                "conn_name": conn_name,
                "db_name": db_name,
                "table_name": name,
            })
            if node_type == NODE_TABLE:
                t_item.setIcon(0, self._table_icon())
                # 构建 tooltip：显示前 12 列的列名+类型+注释
                cols = col_map.get(name, [])
                if cols:
                    shown = cols[:12]
                    lines = [f"表：{name}  ({len(cols)} 列)  —  {db_name} @ {conn_name}", ""]
                    for c_name, c_type, c_cmt in shown:
                        line = f"  {c_name}  {c_type}"
                        if c_cmt:
                            line += f"  # {c_cmt}"
                        lines.append(line)
                    if len(cols) > 12:
                        lines.append(f"  ... 共 {len(cols)} 列")
                    t_item.setToolTip(0, "\n".join(lines))
                else:
                    t_item.setToolTip(0, f"表：{name}\n数据库：{db_name}\n连接：{conn_name}\n单击加载数据，右键查看更多操作")
            elif node_type == NODE_VIEW:
                t_item.setIcon(0, self._view_icon())
                t_item.setToolTip(0, f"视图：{name}\n数据库：{db_name}\n连接：{conn_name}\n单击预览数据，右键可导出")
            elif node_type == NODE_FUNCTION:
                t_item.setIcon(0, self._func_icon())
                t_item.setToolTip(0, f"函数：{name}\n数据库：{db_name}\n连接：{conn_name}")
            elif node_type == NODE_INDEX:
                t_item.setIcon(0, self._index_icon())
                t_item.setToolTip(0, f"索引：{name}\n数据库：{db_name}\n连接：{conn_name}")
            elif node_type == NODE_PROCEDURE:
                t_item.setIcon(0, self._proc_icon())
                t_item.setToolTip(0, f"存储过程：{name}\n数据库：{db_name}\n连接：{conn_name}")
            else:
                t_item.setIcon(0, self._table_icon())
                t_item.setToolTip(0, f"{name}\n数据库：{db_name}\n连接：{conn_name}")



    def _load_table_data(self, conn_name: str, db_name: str, table_name: str):
        """在后台线程拉取表数据，完成后渲染到表格"""
        connector = self._conns.get(conn_name)
        if connector is None:
            return

        # 记录当前表信息（供增删改查使用）
        self._current_table_name = table_name
        self._current_db_name = db_name
        self._current_conn_name = conn_name
        self._table_pk_col = ""   # 每次加载新表时先清空，_render_table 后再探测
        self._sync_ai_chat_context(self._build_chat_context(conn_name, db_name))

        self.statusBar().showMessage(f"正在查询 {db_name}.{table_name} …")

        self.lbl_result_info.setText("查询中…")
        # 同时填充 SQL 编辑器
        db_type = getattr(connector, "db_type", "")
        if db_type == "sqlserver":
            self.sql_edit.setPlainText(f"USE [{db_name}];\nSELECT TOP 200 * FROM [{table_name}]")
        elif db_type in ("postgresql", "gaussdb", "opengauss", "kingbase"):
            self.sql_edit.setPlainText(f"USE \"{db_name}\";\nSELECT * FROM \"{table_name}\" LIMIT 200")
        else:
            self.sql_edit.setPlainText(f"SELECT * FROM `{table_name}` LIMIT 200")



        w = Worker(connector.get_table_data, table_name, db_name, 200)
        self._workers.append(w)

        def on_done(result):
            cols, rows = result
            self._render_table(cols, rows)
            self.statusBar().showMessage(f"{db_name}.{table_name}  共 {len(rows)} 行")
            self._workers.remove(w)
            # 数据渲染完成后再探测主键（此时 _all_cols 已就绪）
            self._detect_primary_key(conn_name, db_name, table_name)

        def on_err(msg):
            self.log(f"{Icon.char('error')} 查询失败：{msg}")
            self.statusBar().showMessage("查询失败")
            self._workers.remove(w)

        w.finished.connect(on_done)
        w.error.connect(on_err)
        w.start()

    def _detect_primary_key(self, conn_name: str, db_name: str, table_name: str):
        """探测表的主键列名，存入 _table_pk_col"""
        connector = self._conns.get(conn_name)
        if not connector:
            return
        db_type = getattr(connector, "db_type", "mysql") or "mysql"
        try:
            if db_type == "sqlserver":
                db_ref = connector._sqlserver_db_ref(db_name)
                sql = (
                    "SELECT TOP 1 c.name "
                    f"FROM {db_ref}.sys.indexes i "
                    f"JOIN {db_ref}.sys.index_columns ic ON i.object_id = ic.object_id AND i.index_id = ic.index_id "
                    f"JOIN {db_ref}.sys.columns c ON ic.object_id = c.object_id AND ic.column_id = c.column_id "
                    f"JOIN {db_ref}.sys.tables t ON i.object_id = t.object_id "
                    "WHERE i.is_primary_key = 1 AND t.name = :table_name "
                    "ORDER BY ic.key_ordinal"
                )
                with connector.engine.connect() as conn:
                    row = conn.execute(sa_text(sql), {"table_name": table_name}).fetchone()
                if row and row[0]:
                    self._table_pk_col = str(row[0])
                return

            if db_type in ("postgresql", "gaussdb", "opengauss", "kingbase") and db_name and db_name != connector.dbname:
                connector._build_engine(db_name)
            connector.dbname = db_name
            pk_sqls = {
                "mysql":      f"SELECT column_name FROM information_schema.key_column_usage WHERE table_schema='{db_name}' AND table_name='{table_name}' AND constraint_name='PRIMARY' LIMIT 1",
                "postgresql": f"SELECT a.attname FROM pg_index i JOIN pg_attribute a ON a.attrelid=i.indrelid AND a.attnum=ANY(i.indkey) WHERE i.indrelid='{table_name}'::regclass AND i.indisprimary LIMIT 1",
                "gaussdb":    f"SELECT a.attname FROM pg_index i JOIN pg_attribute a ON a.attrelid=i.indrelid AND a.attnum=ANY(i.indkey) WHERE i.indrelid='{table_name}'::regclass AND i.indisprimary LIMIT 1",
                "opengauss":  f"SELECT a.attname FROM pg_index i JOIN pg_attribute a ON a.attrelid=i.indrelid AND a.attnum=ANY(i.indkey) WHERE i.indrelid='{table_name}'::regclass AND i.indisprimary LIMIT 1",
                "kingbase":   f"SELECT a.attname FROM pg_index i JOIN pg_attribute a ON a.attrelid=i.indrelid AND a.attnum=ANY(i.indkey) WHERE i.indrelid='{table_name}'::regclass AND i.indisprimary LIMIT 1",
                "oracle":     f"SELECT cols.column_name FROM user_constraints cons JOIN user_cons_columns cols ON cons.constraint_name=cols.constraint_name WHERE cons.constraint_type='P' AND cons.table_name=upper('{table_name}') AND rownum=1",
                "xugu":       f"SELECT cols.column_name FROM user_constraints cons JOIN user_cons_columns cols ON cons.constraint_name=cols.constraint_name WHERE cons.constraint_type='P' AND cons.table_name=upper('{table_name}') AND rownum=1",
            }

            sql = pk_sqls.get(db_type, pk_sqls.get("mysql"))
            rows = None
            if sql:
                _, rows = connector.execute(sql)
            if rows and rows[0]:
                self._table_pk_col = str(rows[0][0])
            return

        except Exception:
            pass
        # 探测失败：用第一列作为 fallback
        self._table_pk_col = self._all_cols[0] if self._all_cols else ""


    def _render_table(self, cols, rows):
        """接收全量数据，初始化分页状态后渲染当前页"""
        self._all_cols = list(cols)
        self._all_rows = list(rows)
        self._cur_page = 1
        # 阻断 spin_page 的 valueChanged 信号，避免重置时触发重渲
        self.spin_page.blockSignals(True)
        self.spin_page.setValue(1)
        self.spin_page.blockSignals(False)
        self._refresh_page()

    def _get_page_size(self) -> int:
        """返回当前每页行数；0 或空表示不分页"""
        txt = self.cmb_page_size.text().strip()
        if not txt or txt == "0":
            return 0
        try:
            return max(1, int(txt))
        except ValueError:
            return 100



    def _total_pages(self) -> int:
        ps = self._get_page_size()
        total = len(self._all_rows)
        if ps == 0 or total == 0:
            return 1
        import math
        return math.ceil(total / ps)

    def _refresh_page(self):
        """根据 _cur_page 和每页行数，渲染表格并更新分页控件状态"""
        # 防重入：渲染过程中不允许再次进入
        if getattr(self, "_refreshing", False):
            return
        self._refreshing = True
        try:
            self._do_refresh_page()
        except Exception as _e:
            import traceback
            _tb = traceback.format_exc()
            # 写到 crash.log
            try:
                import datetime, os as _os
                _log = _os.path.join(_os.path.dirname(_os.path.dirname(__file__)), "crash.log")
                with open(_log, "a", encoding="utf-8") as _f:
                    _f.write(f"\n{'='*60}\n{datetime.datetime.now()}\n_do_refresh_page error:\n{_tb}\n")
            except Exception:
                pass
            self.log(f"{Icon.char('error')} 表格渲染出错（详见 crash.log）：{_e}")
        finally:
            self._refreshing = False

    def _do_refresh_page(self):
        """实际渲染逻辑（由 _refresh_page 调用）"""
        cols = self._all_cols
        rows = self._all_rows
        ps = self._get_page_size()
        total = len(rows)
        tp = self._total_pages()

        # 计算本页数据切片
        if ps == 0:
            page_rows = rows
            self._page_offset = 0
        else:
            self._page_offset = (self._cur_page - 1) * ps
            page_rows = rows[self._page_offset: self._page_offset + ps]

        # 先断开 itemChanged 信号，整个填充过程都不触发
        # PySide6/PyQt6 断开未连接的信号会发出警告，所以用标志跟踪连接状态
        if hasattr(self, '_item_changed_connected') and self._item_changed_connected:
            try:
                self.table.itemChanged.disconnect(self._on_table_item_changed)
                self._item_changed_connected = False
            except Exception:
                self._item_changed_connected = False

        # 重置排序和列选中状态
        self.table._sortable_header.reset_sort()
        self.table.clear_column_selection()

        # 渲染表格（第0列为复选框，第1列起为数据列）
        # 继续关闭 QTableWidget 内建排序，只保留自定义表头排序逻辑
        self.table.setSortingEnabled(False)
        self.table.blockSignals(True)

        self.table.setColumnCount(len(cols) + 1)   # +1 for checkbox
        # 第0列表头 - 全选复选框 - ItemIsEditable 是让 editorEvent 被调用的必要标志
        chk_header = QTableWidgetItem()
        chk_header.setFlags(Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsEditable)
        chk_header.setCheckState(Qt.CheckState.Unchecked)
        chk_header.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        self.table.setHorizontalHeaderItem(0, chk_header)
        self.table.horizontalHeader().setSortIndicatorShown(False)
        # 数据列表头（Navicat 17：列名下方显示数据类型）
        self._col_types: dict[int, str] = {}  # col_index -> type_str
        for j, c in enumerate(cols):
            col_str = str(c)
            header_item = QTableWidgetItem(col_str)
            # 尝试从数据推断类型（仅作显示用）
            col_type = self._infer_col_type(j, page_rows)
            if col_type:
                self._col_types[j + 1] = col_type
            header_item.setToolTip(f"{col_str}\n类型：{col_type}")
            self.table.setHorizontalHeaderItem(j + 1, header_item)

        self.table.setRowCount(len(page_rows))

        for i, row in enumerate(page_rows):
            # 复选框列 - ItemIsEditable 是让 editorEvent 被调用的必要标志
            chk_item = QTableWidgetItem()
            chk_item.setFlags(Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsEditable)
            chk_item.setCheckState(Qt.CheckState.Unchecked)
            chk_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            chk_item.setData(ORIGINAL_ORDER_ROLE, i)
            self.table.setItem(i, 0, chk_item)
            # 数据列
            for j, v in enumerate(row):
                # 将原始值转为字符串，避免 bytes/Decimal/datetime 等类型
                # 传入 setData(UserRole, ...) 导致 Qt C++ 层崩溃（segfault）
                is_null = v is None
                display_str = "NULL" if is_null else str(v)
                item = QTableWidgetItem(display_str)
                # 只存字符串到 UserRole，不存原始 Python 对象
                item.setData(Qt.ItemDataRole.UserRole, display_str)
                if is_null:
                    item.setForeground(QColor(self._tokens["text_muted"]))
                if not self._edit_mode:
                    item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self.table.setItem(i, j + 1, item)

        # 列宽模式（在 blockSignals 期间设置，不触发任何信号）
        self.table.horizontalHeader().setSectionResizeMode(
        0, QHeaderView.ResizeMode.Fixed
        )
        for j in range(1, len(cols) + 1):
            self.table.horizontalHeader().setSectionResizeMode(
        j, QHeaderView.ResizeMode.Interactive
        )
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setColumnWidth(0, 40)

        # 恢复信号（不再重新开启排序，有复选框列时排序无意义）
        self.table.blockSignals(False)

        # resize 列宽
        self.table.resizeColumnsToContents()
        self.table.setColumnWidth(0, 40)   # 复选框列 40px（参照 HTML 预览）

        # 渲染完毕后重连 itemChanged
        self.table.itemChanged.connect(self._on_table_item_changed)
        self._item_changed_connected = True

        # 更新分页控件
        self.spin_page.blockSignals(True)
        self.spin_page.setMaximum(tp)
        self.spin_page.setValue(self._cur_page)
        self.spin_page.blockSignals(False)
        self.lbl_total_pages.setText(f"/ {tp}")
        self._lbl_total_count.setText(f"{tp}")

        # 按钮可用状态
        self.btn_first_page.setEnabled(self._cur_page > 1)
        self.btn_prev_page.setEnabled(self._cur_page > 1)
        self.btn_next_page.setEnabled(self._cur_page < tp)
        self.btn_last_page.setEnabled(self._cur_page < tp)

        # 信息标签
        if ps == 0:
            self.lbl_result_info.setText(f"共 {total} 行 × {len(cols)} 列  （全部显示）")
            self.lbl_page_info.setText("")
        else:
            start = (self._cur_page - 1) * ps + 1
            end = min(self._cur_page * ps, total)
            self.lbl_result_info.setText(f"共 {total} 行 × {len(cols)} 列")
            self.lbl_page_info.setText(
                f"第 {start}–{end} 行  （第 {self._cur_page}/{tp} 页）"
        )
        # 显示结果信息控件
        self.lbl_result_info.show()
        self.lbl_selected_info.show()
        self._lbl_stat_bar.show()
        self._update_selected_info()
        # 渲染完成后同步更新列过滤下拉
        self._refresh_filter_col_combo()
        # 重置过滤状态
        if hasattr(self, "_filter_input"):
            self._filter_count_label.setText("")

    # ── 快速过滤（Navicat 17 风格）────────────────
    # ── 列类型推断（Navicat 17：列头 Tooltip 显示类型）──
    def _infer_col_type(self, col_idx: int, rows) -> str:
        """从当前页数据推断该列的数据类型标签（仅作展示用）"""
        sample_vals = [row[col_idx] for row in rows[:20] if row[col_idx] is not None]
        if not sample_vals:
            return "NULL"
        # 类型推断：尝试所有样本
        has_float = any(isinstance(v, float) for v in sample_vals)
        has_int = any(isinstance(v, int) for v in sample_vals)
        has_str = any(isinstance(v, str) for v in sample_vals)
        has_bytes = any(isinstance(v, (bytes, bytearray)) for v in sample_vals)
        has_date = any(hasattr(v, "year") for v in sample_vals)
        if has_bytes:
            return "BLOB"
        if has_date:
            return "DATETIME"
        if has_float:
            return "DECIMAL"
        if has_int and not has_str:
            return "INT"
        if has_str:
            # 尝试判断是否都是纯数字字符串
            if all(str(v).lstrip("-").replace(".", "").isdigit() for v in sample_vals if str(v).strip()):
                return "NUMBER"
            return "VARCHAR"
        return ""

    # ── 固定结果集（Navicat 17 Pin Result）─────────────
    def _on_pin_result(self):
        """
        固定当前结果集：在日志区打印快照，并弹出独立的表格窗口供对比。
        类 Navicat 17 "固定查询结果"功能。
        """
        if not self._all_cols or not self._all_rows:
            self.log(f"{Icon.char('warning')} 没有可固定的结果集")
            return
        sql_preview = self.sql_edit.toPlainText()[:60].replace("\n", " ").strip()
        title = f"固定结果 — {sql_preview}…" if len(sql_preview) >= 60 else f"固定结果 — {sql_preview}"
        self._show_pinned_result_window(title, self._all_cols, self._all_rows)
        self.log(f"{Icon.char('pushpin')} 已固定结果集（{len(self._all_rows)} 行 × {len(self._all_cols)} 列）")

    def _show_pinned_result_window(self, title: str, cols: list, rows: list):
        """弹出一个独立的固定结果窗口"""
        dlg = QDialog(self)
        dlg.setWindowTitle(title)
        dlg.resize(900, 500)
        dlg.setStyleSheet(build_popup_base_style(self._current_theme))
        layout = QVBoxLayout(dlg)
        layout.setContentsMargins(8, 8, 8, 8)

        # 工具栏
        top_bar = QHBoxLayout()
        lbl = QLabel(f"共 {len(rows)} 行 × {len(cols)} 列")
        lbl.setProperty("role", "muted")
        top_bar.addWidget(lbl)
        top_bar.addStretch()
        btn_export = QPushButton("导出 CSV")
        btn_export.setFixedHeight(26)
        layout.addLayout(top_bar)

        # 表格
        table = QTableWidget()
        table.setColumnCount(len(cols))
        table.setRowCount(min(len(rows), 2000))
        table.setHorizontalHeaderLabels([str(c) for c in cols])
        table.setAlternatingRowColors(True)
        table.horizontalHeader().setStretchLastSection(True)
        for i, row in enumerate(rows[:2000]):
            for j, v in enumerate(row):
                item = QTableWidgetItem("NULL" if v is None else str(v))
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                table.setItem(i, j, item)
        table.resizeColumnsToContents()
        layout.addWidget(table)

        # 导出 CSV
        def _do_export():
            path, _ = QFileDialog.getSaveFileName(dlg, "保存 CSV", f"result_{len(rows)}rows.csv", "CSV (*.csv)")
            if path:
                import csv as _csv
                with open(path, "w", newline="", encoding="utf-8-sig") as f:
                    w = _csv.writer(f)
                    w.writerow(cols)
                    w.writerows(rows)
                QMessageBox.information(dlg, "完成", f"已导出到：{path}")
        btn_export.clicked.connect(_do_export)
        top_bar.addWidget(btn_export)

        dlg.exec()

    # ── 统计栏更新（Navicat 17 底部选中行统计）──────────
    def _update_stat_bar(self):
        """对勾选行的数值列计算 COUNT/SUM/AVG/MIN/MAX，显示在数据标题旁"""
        if not hasattr(self, "_lbl_stat_bar"):
            return
        checked_rows = []
        for row in range(self.table.rowCount()):
            chk = self.table.item(row, 0)
            if chk and chk.checkState() == Qt.CheckState.Checked:
                checked_rows.append(row)

        if not checked_rows:
            self._lbl_stat_bar.setText("")
            return

        # 收集勾选行所有数值列的数值
        nums = []
        for row in checked_rows:
            for col in range(1, self.table.columnCount()):
                item = self.table.item(row, col)
                if item:
                    try:
                        nums.append(float(item.text()))
                    except (ValueError, TypeError):
                        pass

        if not nums:
            self._lbl_stat_bar.setText(f"已选 {len(checked_rows)} 行")
            return

        total = sum(nums)
        avg = total / len(nums)
        mn = min(nums)
        mx = max(nums)
        stat_text = (
            f"│ COUNT: {len(checked_rows)} 行  "
            f"SUM: {total:,.2f}  "
            f"AVG: {avg:,.2f}  "
            f"MIN: {mn:,.2f}  "
            f"MAX: {mx:,.2f}"
        )
        self._lbl_stat_bar.setText(stat_text)

    def _refresh_filter_col_combo(self):
        """渲染完表格后刷新过滤列下拉选项"""
        if not hasattr(self, "_filter_col_combo"):
            return
        self._filter_col_combo.blockSignals(True)
        self._filter_col_combo.clear()
        self._filter_col_combo.addItem("全部列")
        for col in self._all_cols:
            self._filter_col_combo.addItem(str(col))
        self._filter_col_combo.blockSignals(False)

    def _apply_table_filter(self, *_):
        """
        根据过滤输入框内容，隐藏/显示表格行（在当前页内过滤）。
        类 Navicat 17 快速过滤功能。
        """
        if not hasattr(self, "_filter_input"):
            return
        keyword = self._filter_input.text()
        col_idx = self._filter_col_combo.currentIndex() - 1  # -1=全部列, 0..n=第n列
        case_sensitive = self._filter_case_btn.isChecked()
        use_regex = self._filter_regex_btn.isChecked()

        if not keyword:
            # 无关键词：全部显示
            for row in range(self.table.rowCount()):
                self.table.setRowHidden(row, False)
            self._filter_count_label.setText("")
            return

        import re
        flags = 0 if case_sensitive else re.IGNORECASE
        try:
            if use_regex:
                pattern = re.compile(keyword, flags)
            else:
                pattern = re.compile(re.escape(keyword), flags)
            is_valid_regex = True
        except re.error:
            self._filter_count_label.setText(f"{Icon.char('warning')} 正则错误")
            return

        visible_count = 0
        for row in range(self.table.rowCount()):
            matched = False
            if col_idx < 0:
                # 搜索所有列（跳过复选框列0）
                for c in range(1, self.table.columnCount()):
                    cell = self.table.item(row, c)
                    cell_text = cell.text() if cell else ""
                    if pattern.search(cell_text):
                        matched = True
                        break
            else:
                # 搜索指定列（+1 是因为 col 0 是复选框）
                c = col_idx + 1
                if 0 < c < self.table.columnCount():
                    cell = self.table.item(row, c)
                    cell_text = cell.text() if cell else ""
                    matched = bool(pattern.search(cell_text))
                else:
                    matched = False
            self.table.setRowHidden(row, not matched)
            if matched:
                visible_count += 1

        total = self.table.rowCount()
        self._filter_count_label.setText(f"{visible_count}/{total} 行")

    # ── 分页控件事件 ──────────────────────────
    def _on_page_size_changed(self, _=None):
        self._cur_page = 1
        self._refresh_page()

    def _on_page_size_changed_edit(self):
        """每页输入框 Enter 触发"""
        self._cur_page = 1
        self._refresh_page()



    def _on_page_spin_changed(self, val):
        self._cur_page = val
        self._refresh_page()

    def _on_jump_page(self):
        """快速跳页"""
        text = self._jump_edit.text().strip()
        self._jump_edit.clear()
        if not text:
            return
        try:
            page = int(text)
        except ValueError:
            return
        tp = self._total_pages()
        page = max(1, min(page, tp))
        if page != self._cur_page:
            self._cur_page = page
        self._refresh_page()

    def _go_first_page(self):
        if self._cur_page != 1:
            self._cur_page = 1
        self._refresh_page()

    def _go_prev_page(self):
        if self._cur_page > 1:
            self._cur_page -= 1
        self._refresh_page()

    def _go_next_page(self):
        if self._cur_page < self._total_pages():
            self._cur_page += 1
        self._refresh_page()

    def _go_last_page(self):
        tp = self._total_pages()
        if self._cur_page != tp:
            self._cur_page = tp
        self._refresh_page()

    # ─── 右键菜单 ──────────────────────────
    def _tree_context_menu(self, pos: QPoint):
        item = self.tree.itemAt(pos)
        if item is None:
            # 空白区域右键：新建连接
            menu = QMenu(self)
            menu.addAction("新建连接", self._on_new_conn)
            menu.addAction(Icon.prefixed_text('download', "导入 Navicat 连接 (.ncx)"), self._on_import_ncx)
            menu.exec(self.tree.mapToGlobal(pos))
            return

        data = item.data(0, Qt.ItemDataRole.UserRole)
        if not data:
            return
        node_type = data.get("type")
        menu = QMenu(self)

        # ── 连接节点 ────────────────────────────────
        if node_type == NODE_CONNECTION:
            conn_name = data["name"]
            is_connected = conn_name in self._conns
            conn_info = self._conn_infos.get(conn_name, {})

            if is_connected:
                act_open = menu.addAction("关闭连接")
                act_open.triggered.connect(lambda: self._disconnect(item, conn_name))
            else:
                act_open = menu.addAction("打开连接")
                act_open.triggered.connect(lambda: self._expand_connection(item, conn_name))

            menu.addSeparator()

            act_query = menu.addAction("新建查询")
            act_query.triggered.connect(lambda: self._new_query_for_conn(conn_name, item))

            menu.addSeparator()

            act_edit = menu.addAction("编辑连接…")
            act_edit.triggered.connect(lambda: self._on_edit_conn(conn_name))

            act_copy = menu.addAction("复制连接…")
            act_copy.triggered.connect(lambda: self._on_copy_conn(conn_name))

            act_rename = menu.addAction("重命名连接…")
            act_rename.triggered.connect(lambda: self._on_rename_conn(item, conn_name))

            menu.addSeparator()

            # ── Navicat 17 风格：颜色标记 ──
            color_menu = menu.addMenu(Icon.prefixed_text('palette', "颜色标记"))
            cur_color = conn_info.get("color", "")
            # 无颜色选项
            act_no_color = color_menu.addAction("  无颜色")
            act_no_color.setCheckable(True)
            act_no_color.setChecked(not bool(cur_color))
            act_no_color.triggered.connect(lambda: self._set_conn_color(conn_name, ""))
            color_menu.addSeparator()
            for color_key, color_label in self._CONN_COLOR_LABELS.items():
                hex_c, _ = self._CONN_COLORS[color_key]
                act_c = color_menu.addAction(f"  {color_label}")
                act_c.setCheckable(True)
                act_c.setChecked(cur_color == color_key)
                _ck = color_key  # 闭包捕获
                act_c.triggered.connect(lambda checked, ck=_ck: self._set_conn_color(conn_name, ck))

            # ── Navicat 17 风格：星标收藏 ──
            is_starred = bool(conn_info.get("starred", False))
            star_label = "取消收藏" if is_starred else "添加到收藏"
            act_star = menu.addAction(star_label)
            act_star.triggered.connect(lambda: self._toggle_conn_star(conn_name))

            menu.addSeparator()

            act_del = menu.addAction("删除连接")
            act_del.triggered.connect(lambda: self._on_delete_conn(item, conn_name))

            menu.addSeparator()

            act_ref = menu.addAction("刷新")
            act_ref.triggered.connect(lambda: self._on_refresh_conn(item, conn_name))

        # ── 数据库节点 ──────────────────────────────
        elif node_type == NODE_DATABASE:
            conn_name = data["conn_name"]
            db_name   = data["db_name"]

            act_query = menu.addAction("新建查询")
            act_query.triggered.connect(lambda: self._new_query_for_db(conn_name, db_name, item))

            menu.addSeparator()

            act_doc = menu.addAction("导出数据库说明文档…")
            act_doc.triggered.connect(lambda: self._export_database_doc(conn_name, db_name))

            menu.addSeparator()

            act_ref = menu.addAction("刷新")
            act_ref.triggered.connect(lambda: self._expand_database(item, conn_name, db_name))

        # ── 表节点 ──────────────────────────────────
        elif node_type == NODE_TABLE:
            conn_name  = data["conn_name"]
            db_name    = data["db_name"]
            table_name = data["table_name"]

            act_view = menu.addAction("打开表")
            act_view.triggered.connect(lambda: self._load_table_data(conn_name, db_name, table_name))

            act_design = menu.addAction("设计表")
            act_design.triggered.connect(lambda: self._on_design_table(conn_name, db_name, table_name))

            act_props = menu.addAction("属性")
            act_props.triggered.connect(lambda: self._on_table_properties(conn_name, db_name, table_name))

            menu.addSeparator()

            act_new_tbl = menu.addAction("新建表")
            act_new_tbl.triggered.connect(lambda: self._on_new_table(conn_name, db_name))

            act_del_tbl = menu.addAction("删除表")
            act_del_tbl.triggered.connect(lambda: self._on_drop_table(conn_name, db_name, table_name, item))

            act_trunc = menu.addAction("清空表")
            act_trunc.triggered.connect(lambda: self._on_truncate_table(conn_name, db_name, table_name))

            menu.addSeparator()

            act_copy_tbl = menu.addAction("复制表")
            act_copy_tbl.triggered.connect(lambda: self._on_copy_table(conn_name, db_name, table_name))

            menu.addSeparator()

            act_import = menu.addAction("导入向导…")
            act_import.triggered.connect(lambda: self._open_import_wizard(conn_name, table_name))

            act_export = menu.addAction("导出向导…")
            act_export.triggered.connect(lambda: self._open_export_wizard(conn_name, table_name))

            menu.addSeparator()

            act_dump = menu.addAction("转储 SQL 文件…")
            act_dump.triggered.connect(lambda: self._on_dump_sql(conn_name, db_name, table_name))

            act_dll = menu.addAction("DLL信息")
            act_dll.triggered.connect(lambda: self._on_table_dll_info(conn_name, db_name, table_name))

            menu.addSeparator()

            act_sel = menu.addAction("新建查询（SELECT *）")
            act_sel.triggered.connect(lambda: self._new_query_select(conn_name, db_name, table_name))

            act_copy_name = menu.addAction("复制表名")
            act_copy_name.triggered.connect(lambda: QApplication.clipboard().setText(table_name))

            menu.addSeparator()

            act_ref = menu.addAction("刷新")
            act_ref.triggered.connect(lambda: self._load_table_data(conn_name, db_name, table_name))

        # ── 视图节点 ──────────────────────────────────
        elif node_type == NODE_VIEW:
            conn_name  = data["conn_name"]
            db_name    = data["db_name"]
            table_name = data["table_name"]

            act_view = menu.addAction("查看数据")
            act_view.triggered.connect(lambda: self._load_table_data(conn_name, db_name, table_name))

            act_design_v = menu.addAction("设计视图（查看DDL）")
            act_design_v.triggered.connect(lambda: self._on_design_view(conn_name, db_name, table_name))

            menu.addSeparator()

            act_new_v = menu.addAction("创建视图…")
            act_new_v.triggered.connect(lambda: self._on_create_view(conn_name, db_name))

            act_drop_v = menu.addAction("删除视图")
            act_drop_v.triggered.connect(lambda: self._on_drop_view(conn_name, db_name, table_name, item))

            menu.addSeparator()

            act_sel = menu.addAction("新建查询（SELECT *）")
            act_sel.triggered.connect(lambda: self._new_query_select(conn_name, db_name, table_name))

            act_copy_name = menu.addAction("复制视图名")
            act_copy_name.triggered.connect(lambda: QApplication.clipboard().setText(table_name))

            menu.addSeparator()

            act_ref_v = menu.addAction("刷新")
            act_ref_v.triggered.connect(lambda: self._refresh_group_node(item))

        # ── 函数节点 ──────────────────────────────────
        elif node_type == NODE_FUNCTION:
            conn_name  = data["conn_name"]
            db_name    = data["db_name"]
            func_name  = data["table_name"]

            act_copy_name = menu.addAction("复制函数名")
            act_copy_name.triggered.connect(lambda: QApplication.clipboard().setText(func_name))

            act_sel = menu.addAction("生成调用语句")
            act_sel.triggered.connect(lambda: self._insert_func_call(func_name))

        # ── 分组节点（表/视图/函数）──────────────────
        elif node_type == NODE_GROUP:
            conn_name = data["conn_name"]
            db_name   = data["db_name"]
            kind      = data.get("kind", "")

            if kind == "views":
                act_new_v = menu.addAction("创建视图…")
                act_new_v.triggered.connect(lambda: self._on_create_view(conn_name, db_name))
            elif kind == "tables":
                act_new_t = menu.addAction("新建表…")
                act_new_t.triggered.connect(lambda: self._on_new_table(conn_name, db_name))

            menu.addSeparator()

            act_refresh = menu.addAction("刷新")
            act_refresh.triggered.connect(lambda: self._refresh_group_node(item))

        menu.exec(self.tree.mapToGlobal(pos))

    # ─── 连接搜索过滤（Navicat 17 风格）───────────
    def _filter_conn_tree(self, keyword: str):
        """根据关键词过滤连接树的顶层节点（连接节点）"""
        kw = keyword.strip().lower()
        for i in range(self.tree.topLevelItemCount()):
            item = self.tree.topLevelItem(i)
            data = item.data(0, Qt.ItemDataRole.UserRole) or {}
            name = data.get("name", "").lower()
            # 同时匹配主机地址
            info = self._conn_infos.get(data.get("name", ""), {})
            host = info.get("host", "").lower()
            match = (not kw) or (kw in name) or (kw in host)
            item.setHidden(not match)

    # ─── 连接颜色 & 星标 ──────────────────────────
    def _set_conn_color(self, conn_name: str, color: str):
        """设置连接颜色标记并持久化"""
        info = self._conn_infos.get(conn_name)
        if info is None:
            return
        info["color"] = color
        update_connection_meta(conn_name, color=color)
        self._refresh_conn_node_display(conn_name)
        self.log(f"[{conn_name}] 颜色标记 → {self._CONN_COLOR_LABELS.get(color, '无')}")

    def _toggle_conn_star(self, conn_name: str):
        """切换连接收藏（星标）状态并持久化"""
        info = self._conn_infos.get(conn_name)
        if info is None:
            return
        new_val = not bool(info.get("starred", False))
        info["starred"] = new_val
        update_connection_meta(conn_name, starred=new_val)
        self._refresh_conn_node_display(conn_name)
        self.log(f"[{conn_name}] {'已添加收藏' if new_val else '已取消收藏'}")

    # ─── 右键菜单辅助操作 ────────────────────────
    def _new_query_for_conn(self, conn_name: str, item: QTreeWidgetItem):
        """连接节点→新建查询：在新标签页打开"""
        if conn_name not in self._conns:
            self._expand_connection(item, conn_name)
        if conn_name not in self._conns:
            return
        self._current_conn_name = conn_name
        self._add_sql_tab(title=f"{conn_name}")
        self.sql_edit.setFocus()
        self.statusBar().showMessage(f"当前连接：{conn_name}")

    def _new_query_for_db(self, conn_name: str, db_name: str, item: QTreeWidgetItem):
        """数据库节点→新建查询：在新标签页打开，插入 USE 语句"""
        conn_item = item.parent()
        if conn_name not in self._conns and conn_item:
            self._expand_connection(conn_item, conn_name)
        if conn_name not in self._conns:
            return
        self._current_conn_name = conn_name
        connector = self._conns.get(conn_name)
        db_type = getattr(connector, "db_type", "") if connector else ""
        if connector:
            connector.dbname = db_name
        if db_type == "sqlserver":
            use_sql = f"USE [{db_name}];\n"
        elif db_type in ("postgresql", "gaussdb", "opengauss", "kingbase"):
            use_sql = f"USE \"{db_name}\";\n"
        else:
            use_sql = f"USE `{db_name}`;\n"
        # 在新标签页打开
        self._add_sql_tab(title=f"{db_name}", content=use_sql)
        self.sql_edit.setFocus()
        self.statusBar().showMessage(f"当前连接：{conn_name} / {db_name}")

    def _new_query_select(self, conn_name: str, db_name: str, table_name: str):
        """表节点→新建查询（SELECT *）：在新标签页插入 SELECT 语句"""
        self._current_conn_name = conn_name
        self._refresh_status_badges()
        connector = self._conns.get(conn_name)
        db_type = getattr(connector, "db_type", "") if connector else ""
        if db_type == "sqlserver":
            sql = f"USE [{db_name}];\nSELECT TOP 100 * FROM [{table_name}];\n"
        elif db_type in ("postgresql", "gaussdb", "opengauss", "kingbase"):
            sql = f"USE \"{db_name}\";\nSELECT * FROM \"{table_name}\" LIMIT 100;\n"
        else:
            sql = f"SELECT * FROM `{table_name}` LIMIT 100;\n"

        # 在新标签页打开（类 Navicat 双击表→新查询标签）
        self._add_sql_tab(title=f"{table_name}", content=sql)
        self.sql_edit.setFocus()

    def _on_design_table(self, conn_name: str, db_name: str, table_name: str):
        """设计表：查询并展示表结构（列定义）"""
        connector = self._conns.get(conn_name)
        if not connector:
            QMessageBox.warning(self, "提示", "请先连接数据库")
            return
        try:
            db_type = connector.db_type
            if db_type in ("mysql", "oceanbase", "polardb", "tdsql", "tidb", "gbase"):
                sql = f"SHOW FULL COLUMNS FROM `{table_name}`"
            elif db_type in ("postgresql", "gaussdb", "opengauss", "kingbase"):
                sql = f"SELECT column_name, data_type, character_maximum_length, is_nullable, column_default FROM information_schema.columns WHERE table_schema='public' AND table_name='{table_name}' ORDER BY ordinal_position"
            elif db_type == "sqlserver":
                sql = f"SELECT c.name, t.name as type, c.max_length, c.is_nullable, c.is_identity FROM sys.columns c JOIN sys.types t ON c.user_type_id=t.user_type_id WHERE object_id=OBJECT_ID('{table_name}') ORDER BY c.column_id"
            elif db_type in ("oracle", "shentong", "dameng"):
                sql = f"SELECT column_name, data_type, data_length, nullable, data_default FROM user_tab_columns WHERE table_name=UPPER('{table_name}') ORDER BY column_id"
            elif db_type == "xugu":
                safe_table_name = table_name.replace("'", "''")
                sql = (
                "SELECT c.col_name AS column_name, "
                "c.type_name AS data_type, "
                "c.scale AS data_scale, "
                "c.not_null AS not_null, "
                "c.def_val AS default_value, "
                "c.comments AS comments "
                "FROM all_columns c "
                "JOIN all_tables t ON c.table_id = t.table_id "
                f"WHERE t.table_name = UPPER('{safe_table_name}') "
                "ORDER BY c.col_no"
                )
            else:
                sql = f"SELECT * FROM information_schema.columns WHERE table_name='{table_name}' ORDER BY ordinal_position"

            with connector.engine.connect() as conn:
                result = conn.execute(sa_text(sql))
            cols = list(result.keys())
            rows = [list(r) for r in result.fetchall()]
        except Exception as e:
            QMessageBox.critical(self, "查询失败", str(e))

    def _on_table_properties(self, conn_name: str, db_name: str, table_name: str):
        """显示表属性信息：行数、大小、创建时间等"""
        connector = self._conns.get(conn_name)
        if not connector:
            QMessageBox.warning(self, "提示", "请先连接数据库")
            return
        props = []
        try:
            db_type = connector.db_type
            
            if db_type in ("mysql", "oceanbase", "polardb", "tdsql", "tidb", "gbase"):
                # MySQL 属性查询
                sql = f"SHOW TABLE STATUS LIKE '{table_name}'"
                with connector.engine.connect() as conn:
                    result = conn.execute(sa_text(sql))
                row = result.fetchone()
                if row:
                    props.append(("表名", row[0]))
                    props.append(("引擎", row[1]))
                    props.append(("行数", row[4]))
                    props.append(("数据大小 (MB)", f"{int(row[6])/1024/1024:.2f}" if row[6] else "0"))
                    props.append(("索引大小 (MB)", f"{int(row[8])/1024/1024:.2f}" if row[8] else "0"))
                    props.append(("创建时间", row[11]))
                    props.append(("更新时间", row[12]))
                    props.append(("字符集", row[14]))
                        
            elif db_type in ("postgresql", "gaussdb", "opengauss", "kingbase"):
                # PostgreSQL 属性查询
                sql1 = f"SELECT pg_size_pretty(pg_total_relation_size('{table_name}'))"
                sql2 = f"SELECT reltuples::bigint FROM pg_class WHERE relname='{table_name}'"
                sql3 = f"SELECT obj_description(oid) FROM pg_class WHERE relname='{table_name}'"
                with connector.engine.connect() as conn:
                    size_res = conn.execute(sa_text(sql1))
                    size = size_res.scalar() or "未知"
                    row_res = conn.execute(sa_text(sql2))
                    rows = row_res.scalar() or "未知"
                    desc_res = conn.execute(sa_text(sql3))
                    desc = desc_res.scalar() or "无"
                    
                props.append(("表名", table_name))
                props.append(("总大小", size))
                props.append(("估算行数", rows))
                props.append(("描述", desc))
                    
            elif db_type == "sqlserver":
                # SQL Server 属性查询
                sql = f"""
                SELECT 
                t.name,
                s.row_count,
                (SUM(a.total_pages) * 8.0 / 1024) AS total_size_mb,
                t.create_date,
                t.modify_date
                FROM sys.tables t
                INNER JOIN sys.dm_db_partition_stats s ON t.object_id = s.object_id
                INNER JOIN sys.allocation_units a ON s.partition_id = a.container_id
                WHERE t.name = '{table_name}'
                GROUP BY t.name, s.row_count, t.create_date, t.modify_date
                """
                with connector.engine.connect() as conn:
                    result = conn.execute(sa_text(sql))
                row = result.fetchone()
                if row:
                    props.append(("表名", row[0]))
                    props.append(("行数", row[1]))
                    props.append(("总大小 (MB)", f"{row[2]:.2f}"))
                    props.append(("创建时间", row[3]))
                    props.append(("修改时间", row[4]))
                        
            elif db_type in ("oracle", "shentong", "dameng"):
                # Oracle 属性查询
                sql = f"""
                SELECT 
                table_name,
                tablespace_name,
                num_rows,
                avg_row_len,
                blocks,
                empty_blocks,
                last_analyzed
                FROM user_tables 
                WHERE table_name = UPPER('{table_name}')
                """
                with connector.engine.connect() as conn:
                    result = conn.execute(sa_text(sql))
                row = result.fetchone()
                if row:
                    props.append(("表名", row[0]))
                    props.append(("表空间", row[1]))
                    props.append(("行数", row[2] or "未知"))
                    props.append(("平均行长度", f"{row[3] or 0} 字节"))
                    props.append(("数据块数", row[4] or 0))
                    props.append(("空块数", row[5] or 0))
                    props.append(("最后分析时间", row[6] or "未知"))
            
            if not props:
                props.append(("信息", "无法获取表属性信息"))
            props.append(("数据库类型", db_type))
            props.append(("表名", table_name))

            # 显示属性对话框
            dlg = QDialog(self)
            dlg.setWindowTitle(f"表属性 — {table_name}")
            dlg.resize(520, 320)
            layout = QVBoxLayout(dlg)
            
            table = QTableWidget(len(props), 2)
            table.setHorizontalHeaderLabels(["属性", "值"])
            table.horizontalHeader().setStretchLastSection(True)
            table.setAlternatingRowColors(True)
            table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
            
            for i, (key, value) in enumerate(props):
                key_item = QTableWidgetItem(str(key))
                value_item = QTableWidgetItem(str(value))
                table.setItem(i, 0, key_item)
                table.setItem(i, 1, value_item)
            
            table.resizeColumnsToContents()
            layout.addWidget(table)
            
            btn_close = QPushButton("关闭")
            btn_close.clicked.connect(dlg.accept)
            layout.addWidget(btn_close)
            
            dlg.exec()
            
        except Exception as e:
            QMessageBox.critical(self, "查询失败", str(e))
            self.log(f"{Icon.char('error')} 查询表属性失败：{e}")

    def _on_table_dll_info(self, conn_name: str, db_name: str, table_name: str):
        """显示表的 DLL/DDL 信息（创建语句）"""
        connector = self._conns.get(conn_name)
        if not connector:
            QMessageBox.warning(self, "提示", "请先连接数据库")
            return
        ddl = ""
        try:
            db_type = connector.db_type
            
            if db_type in ("mysql", "oceanbase", "polardb", "tdsql", "tidb", "gbase"):
                sql = f"SHOW CREATE TABLE `{table_name}`"
                with connector.engine.connect() as conn:
                    result = conn.execute(sa_text(sql))
                row = result.fetchone()
                if row:
                    ddl = row[1]  # Create Table 列
                        
            elif db_type in ("postgresql", "gaussdb", "opengauss", "kingbase"):
                sql = f"SELECT pg_get_tabledef('{table_name}')"
                with connector.engine.connect() as conn:
                    result = conn.execute(sa_text(sql))
                row = result.fetchone()
                if row:
                    ddl = row[0]
                        
            elif db_type == "sqlserver":
                sql = f"""
                SELECT 
                m.definition
                FROM sys.sql_modules m
                INNER JOIN sys.tables t ON m.object_id = t.object_id
                WHERE t.name = '{table_name}'
                """
                with connector.engine.connect() as conn:
                    result = conn.execute(sa_text(sql))
                row = result.fetchone()
                if row:
                    ddl = row[0]
                        
            elif db_type in ("oracle", "shentong", "dameng"):
                sql = f"""
                SELECT DBMS_METADATA.GET_DDL('TABLE', UPPER('{table_name}')) FROM DUAL
                """
                with connector.engine.connect() as conn:
                    result = conn.execute(sa_text(sql))
                row = result.fetchone()
                if row:
                    ddl = row[0]
            
            if not ddl:
                ddl = f"-- 无法获取 {table_name} 的 DDL 信息\n-- 数据库类型: {db_type}"
            
            # 显示 DDL 对话框
            dlg = QDialog(self)
            dlg.setWindowTitle(f"DDL 信息 — {table_name}")
            dlg.resize(700, 500)
            layout = QVBoxLayout(dlg)
            
            editor = QPlainTextEdit()
            editor.setPlainText(ddl)
            editor.setFont(QFont("Consolas", 10))
            editor.setReadOnly(True)
            layout.addWidget(editor)
            
            btn_copy = QPushButton("复制到剪贴板")
            btn_copy.clicked.connect(lambda: QApplication.clipboard().setText(ddl))
            
            btn_close = QPushButton("关闭")
            btn_close.clicked.connect(dlg.accept)
            
            btn_layout = QHBoxLayout()
            btn_layout.addWidget(btn_copy)
            btn_layout.addWidget(btn_close)
            layout.addLayout(btn_layout)
            
            dlg.exec()
            
        except Exception as e:
            QMessageBox.critical(self, "查询失败", str(e))
            self.log(f"{Icon.char('error')} 查询表 DDL 失败：{e}")

    def _on_new_table(self, conn_name: str, db_name: str):
        """新建表：弹对话框填写 CREATE TABLE DDL"""
        connector = self._conns.get(conn_name)
        if not connector:
            QMessageBox.warning(self, "提示", "请先连接数据库")
            return
        tpl = (
            f"CREATE TABLE `new_table` (\n"
            f"  `id` INT NOT NULL AUTO_INCREMENT,\n"
            f"  `name` VARCHAR(255) DEFAULT NULL,\n"
            f"  PRIMARY KEY (`id`)\n"
            f");")
        dlg = QDialog(self)
        dlg.setWindowTitle("新建表")
        dlg.resize(560, 300)
        ly = QVBoxLayout(dlg)
        lbl = QLabel("请输入 CREATE TABLE 语句：")
        ly.addWidget(lbl)
        editor = QTextEdit()
        editor.setPlainText(tpl)
        editor.setFont(QFont("Consolas", 10))
        ly.addWidget(editor)
        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        btns.accepted.connect(dlg.accept)
        btns.rejected.connect(dlg.reject)
        ly.addWidget(btns)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            ddl = editor.toPlainText().strip()
            if ddl:
                try:
                    with connector.engine.connect() as conn:
                        conn.execute(sa_text(ddl))
                        conn.commit()
                    self.log(f"{Icon.char('success')} 表已创建")
                    # 刷新当前数据库节点
                    self._refresh_db_node(conn_name, db_name)
                except Exception as e:
                    QMessageBox.critical(self, "创建失败", str(e))

    def _on_drop_table(self, conn_name: str, db_name: str, table_name: str, tree_item: QTreeWidgetItem):
        """删除表"""
        connector = self._conns.get(conn_name)
        if not connector:
            return
        ret = QMessageBox.warning(
            self, "删除表",
            f"确定要删除表 [{db_name}.{table_name}] 吗？\n此操作不可恢复！",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if ret == QMessageBox.StandardButton.Yes:
            try:
                db_type = connector.db_type
                if db_type in ("mysql", "oceanbase", "polardb", "tdsql", "tidb", "gbase"):
                    sql = f"DROP TABLE `{table_name}`"
                elif db_type in ("sqlserver",):
                    sql = f"DROP TABLE [{table_name}]"
                else:
                    sql = f'DROP TABLE "{table_name}"'
                with connector.engine.connect() as conn:
                    conn.execute(sa_text(sql))
                    conn.commit()
                self.log(f"{Icon.char('success')} 表 [{table_name}] 已删除")
                # 从树中移除节点
                parent = tree_item.parent()
                if parent:
                    parent.removeChild(tree_item)
            except Exception as e:
                QMessageBox.critical(self, "删除失败", str(e))

    def _on_truncate_table(self, conn_name: str, db_name: str, table_name: str):
        """清空表"""
        connector = self._conns.get(conn_name)
        if not connector:
            return
        ret = QMessageBox.warning(
            self, "清空表",
            f"确定要清空表 [{db_name}.{table_name}] 的所有数据吗？\n此操作不可恢复！",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if ret == QMessageBox.StandardButton.Yes:
            try:
                db_type = connector.db_type
                if db_type in ("mysql", "oceanbase", "polardb", "tdsql", "tidb", "gbase"):
                    sql = f"TRUNCATE TABLE `{table_name}`"
                elif db_type == "sqlserver":
                    sql = f"TRUNCATE TABLE [{table_name}]"
                else:
                    sql = f'TRUNCATE TABLE "{table_name}"'
                with connector.engine.connect() as conn:
                    conn.execute(sa_text(sql))
                    conn.commit()
                self.log(f"{Icon.char('success')} 表 [{table_name}] 已清空")
                # 刷新结果区
                if self._current_table_name == table_name:
                    self._load_table_data(conn_name, db_name, table_name)
            except Exception as e:
                QMessageBox.critical(self, "清空失败", str(e))

    def _on_copy_table(self, conn_name: str, db_name: str, table_name: str):
        """复制表：弹对话框输入新表名，执行 CREATE TABLE ... SELECT"""
        connector = self._conns.get(conn_name)
        if not connector:
            return
        new_name, ok = QInputDialog.getText(
            self, "复制表", "请输入新表名称：",
            QLineEdit.EchoMode.Normal, f"{table_name}_copy"
        )
        if not ok or not new_name.strip():
            return
        new_name = new_name.strip()
        try:
            db_type = connector.db_type
            if db_type in ("mysql", "oceanbase", "polardb", "tdsql", "tidb", "gbase"):
                sql = f"CREATE TABLE `{new_name}` SELECT * FROM `{table_name}`"
            elif db_type == "postgresql":
                sql = f'CREATE TABLE "{new_name}" AS SELECT * FROM "{table_name}"'
            elif db_type == "sqlserver":
                sql = f"SELECT * INTO [{new_name}] FROM [{table_name}]"
            else:
                sql = f'CREATE TABLE "{new_name}" AS SELECT * FROM "{table_name}"'
            with connector.engine.connect() as conn:
                conn.execute(sa_text(sql))
                conn.commit()
            self.log(f"{Icon.char('success')} 表 [{table_name}] 已复制为 [{new_name}]")
            self._refresh_db_node(conn_name, db_name)
        except Exception as e:
            QMessageBox.critical(self, "复制失败", str(e))

    def _on_dump_sql(self, conn_name: str, db_name: str, table_name: str):
        """转储 SQL 文件：将表的 CREATE + INSERT 语句写入文件"""
        connector = self._conns.get(conn_name)
        if not connector:
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "转储 SQL 文件",
            f"{table_name}.sql",
            "SQL Files (*.sql);;All Files (*)"
        )
        if not path:
            return
        try:
            lines = [f"-- 转储表 {table_name}  (数据库: {db_name})\n"]
            # 获取建表 DDL
            db_type = connector.db_type
            if db_type in ("mysql", "oceanbase", "polardb", "tdsql", "tidb"):
                with connector.engine.connect() as conn:
                    res = conn.execute(sa_text(f"SHOW CREATE TABLE `{table_name}`"))
                    row = res.fetchone()
                    if row:
                        lines.append(str(row[1]) + ";\n\n")
            # 获取数据
            cols, rows = connector.get_table_data(table_name, db_name, limit=10000)
            if rows:
                col_str = ", ".join(f"`{c}`" for c in cols)
                for row in rows:
                    vals = ", ".join(
                        "NULL" if v is None else f"'{str(v).replace(chr(39), chr(39)*2)}'"
                        for v in row
                    )
                    lines.append(f"INSERT INTO `{table_name}` ({col_str}) VALUES ({vals});\n")
            with open(path, "w", encoding="utf-8") as f:
                f.writelines(lines)
            self.log(f"{Icon.char('success')} 已转储 {len(rows)} 行到 {path}")
            QMessageBox.information(self, "转储完成", f"已写入：{path}")
        except Exception as e:
            QMessageBox.critical(self, "转储失败", str(e))

    def _open_import_wizard(self, conn_name: str, table_name: str):
        """打开导入向导（复用现有 ExportImportWindow）"""
        connector = self._conns.get(conn_name)
        if not connector:
            QMessageBox.warning(self, "提示", "请先连接数据库")
            return
        dlg = ExportImportWindow(
        parent=self,
        connector=connector,
        current_table=table_name,
        )
        dlg.exec()

    def _open_export_wizard(self, conn_name: str, table_name: str):
        """打开导出向导（复用现有 ExportImportWindow）"""
        connector = self._conns.get(conn_name)
        if not connector:
            QMessageBox.warning(self, "提示", "请先连接数据库")
            return
        dlg = ExportImportWindow(
        parent=self,
        connector=connector,
        current_table=table_name,
        )
        dlg.exec()

    def _export_database_doc(self, conn_name: str, db_name: str):
        """导出当前数据库的结构说明 Markdown 文档。"""
        connector = self._conns.get(conn_name)
        if not connector:
            QMessageBox.warning(self, "提示", "请先连接数据库")
            return

        def safe_md(value) -> str:
            text = "" if value is None else str(value)
            return text.replace("|", "\\|").replace("\r", "").replace("\n", "<br>")

        def safe_filename(name: str) -> str:
            invalid = '<>:"/\\|?*'
            return "".join("_" if ch in invalid else ch for ch in name)

        try:
            tables = sorted(connector.get_tables(db_name) or [])
            views = sorted(connector.get_views(db_name) or [])
            functions = sorted(connector.get_functions(db_name) or [])
            schema_rows = connector.get_schema_rows(db_name) or []

            table_map: dict[str, list[tuple[str, str, str]]] = {}
            for row in schema_rows:
                table_name = str(row[0]) if len(row) > 0 else ""
                col_name = str(row[1]) if len(row) > 1 else ""
                col_type = "" if len(row) <= 2 or row[2] is None else str(row[2])
                comment = "" if len(row) <= 3 or row[3] is None else str(row[3])
                table_map.setdefault(table_name, []).append((col_name, col_type, comment))

            timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            default_name = safe_filename(
                f"{conn_name}_{db_name}_数据库说明_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
            )
            path, _ = QFileDialog.getSaveFileName(
                self,
                "导出数据库说明文档",
                default_name,
                "Markdown 文档 (*.md)",
            )
            if not path:
                return
            if not path.lower().endswith(".md"):
                path += ".md"

            db_type = (
                getattr(connector, "db_type", "")
                or self._conn_infos.get(conn_name, {}).get("db_type", "")
                or "unknown"
            )

            lines = [
                f"# {APP_FULL_NAME} 数据库说明文档",
                "",
                f"- 导出时间：{timestamp}",
                f"- 连接名称：{conn_name}",
                f"- 数据库名称：{db_name}",
                f"- 数据库类型：{db_type}",
                f"- 表数量：{len(tables)}",
                f"- 视图数量：{len(views)}",
                f"- 函数数量：{len(functions)}",
                "",
                "## 结构概览",
                "",
            ]

            if tables:
                lines.append("### 表")
                lines.append("")
                for table_name in tables:
                    lines.append(f"- `{table_name}`（{len(table_map.get(table_name, []))} 列）")
                lines.append("")

            if views:
                lines.append("### 视图")
                lines.append("")
                for view_name in views:
                    lines.append(f"- `{view_name}`")
                lines.append("")

            if functions:
                lines.append("### 函数")
                lines.append("")
                for func_name in functions:
                    lines.append(f"- `{func_name}`")
                lines.append("")

            lines.append("## 表结构详情")
            lines.append("")
            if not tables:
                lines.append("_当前数据库未获取到表信息。_")
                lines.append("")
            else:
                for table_name in tables:
                    lines.append(f"### `{table_name}`")
                    lines.append("")
                    columns = table_map.get(table_name, [])
                    if not columns:
                        lines.append("_未获取到该表的列结构信息。_")
                        lines.append("")
                        continue
                    lines.append("| 列名 | 类型 | 说明 |")
                    lines.append("| --- | --- | --- |")
                    for col_name, col_type, comment in columns:
                        lines.append(
                            f"| {safe_md(col_name)} | {safe_md(col_type)} | {safe_md(comment) or '-'} |"
                        )
                    lines.append("")

            with open(path, "w", encoding="utf-8") as f:
                f.write("\n".join(lines))

            self.log(f"{Icon.char('file_text')} 已导出数据库说明文档：{path}")
            QMessageBox.information(self, "导出完成", f"数据库说明文档已保存到：\n{path}")
        except Exception as e:
            QMessageBox.critical(self, "导出失败", str(e))

    def _insert_func_call(self, func_name: str):
        """将函数调用语句插入 SQL 编辑器"""
        sql = f"SELECT {func_name}();\n"
        cur = self.sql_edit.textCursor()
        cur.movePosition(cur.MoveOperation.End)
        self.sql_edit.setTextCursor(cur)
        self.sql_edit.insertPlainText(sql)
        self.sql_edit.setFocus()

    def _refresh_db_node(self, conn_name: str, db_name: str):
        """刷新树中对应的数据库节点"""
        root = self.tree.invisibleRootItem()
        for i in range(root.childCount()):
            conn_item = root.child(i)
            d = conn_item.data(0, Qt.ItemDataRole.UserRole)
            if d and d.get("name") == conn_name:
                for j in range(conn_item.childCount()):
                    db_item = conn_item.child(j)
                    dd = db_item.data(0, Qt.ItemDataRole.UserRole)
                    if dd and dd.get("db_name") == db_name:
                        self._expand_database(db_item, conn_name, db_name)
                        return

    def _refresh_group_node(self, group_item: QTreeWidgetItem):
        """刷新分组节点（表/视图/函数），重新加载其子节点"""
        data = group_item.data(0, Qt.ItemDataRole.UserRole)
        if not data:
            return
        conn_name = data.get("conn_name")
        db_name   = data.get("db_name")
        kind      = data.get("kind")
        # 清除现有子节点
        group_item.takeChildren()
        # 添加占位节点触发懒加载
        ph = QTreeWidgetItem(group_item, [""])
        ph.setData(0, Qt.ItemDataRole.UserRole, {"type": -1})
        # 折叠后重新展开，触发 _on_tree_expanded
        group_item.setExpanded(False)
        group_item.setExpanded(True)

    # ── 视图相关操作 ─────────────────────────────────────
    def _on_create_view(self, conn_name: str, db_name: str):
        """创建视图：弹对话框编辑 CREATE VIEW DDL 并执行"""
        connector = self._conns.get(conn_name)
        if not connector:
            QMessageBox.warning(self, "提示", "请先连接数据库")
            return
        db_type = connector.db_type

        # 根据数据库类型生成模板
        if db_type in ("mysql", "oceanbase", "polardb", "tdsql", "tidb", "gbase"):
            tpl = (
                f"CREATE OR REPLACE VIEW `{db_name}`.`new_view` AS\n"
                f"SELECT\n"
                f"    t.id,\n"
                f"    t.name\n"
                f"FROM `{db_name}`.`your_table` t\n"
                f"WHERE 1=1;"
            )
        elif db_type in ("postgresql", "gaussdb", "opengauss", "kingbase"):
            tpl = (
                f"CREATE OR REPLACE VIEW {db_name}.new_view AS\n"
                f"SELECT\n"
                f"    t.id,\n"
                f"    t.name\n"
                f"FROM {db_name}.your_table t\n"
                f"WHERE 1=1;"
            )
        elif db_type == "sqlserver":
            tpl = (
                f"CREATE OR ALTER VIEW dbo.new_view AS\n"
                f"SELECT\n"
                f"    t.id,\n"
                f"    t.name\n"
                f"FROM dbo.your_table t\n"
                f"WHERE 1=1;"
            )
        elif db_type in ("oracle", "shentong", "dameng"):
            tpl = (
                f"CREATE OR REPLACE VIEW new_view AS\n"
                f"SELECT\n"
                f"    t.id,\n"
                f"    t.name\n"
                f"FROM your_table t\n"
                f"WHERE 1=1;"
            )
        else:
            tpl = (
                f"CREATE OR REPLACE VIEW new_view AS\n"
                f"SELECT * FROM your_table WHERE 1=1;"
            )

        dlg = QDialog(self)
        dlg.setWindowTitle(f"创建视图 — {db_name}")
        dlg.resize(680, 380)
        layout = QVBoxLayout(dlg)

        lbl = QLabel("编辑 CREATE VIEW 语句，确认后执行：")
        layout.addWidget(lbl)

        editor = QPlainTextEdit()
        editor.setPlainText(tpl)
        editor.setFont(QFont("Consolas", 10))
        layout.addWidget(editor)

        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        btns.button(QDialogButtonBox.StandardButton.Ok).setText("执行创建")
        btns.button(QDialogButtonBox.StandardButton.Cancel).setText("取消")
        btns.accepted.connect(dlg.accept)
        btns.rejected.connect(dlg.reject)
        layout.addWidget(btns)

        if dlg.exec() != QDialog.DialogCode.Accepted:
            return

        ddl = editor.toPlainText().strip()
        if not ddl:
            return
        try:
            with connector.engine.connect() as conn:
                conn.execute(sa_text(ddl))
                conn.commit()
            QMessageBox.information(self, "成功", "视图创建成功！")
            self.log(f"{Icon.char('success')} 视图创建成功 [{db_name}]")
            # 刷新视图分组节点
            self._refresh_views_group(conn_name, db_name)
        except Exception as e:
            QMessageBox.critical(self, "执行失败", str(e))
            self.log(f"{Icon.char('error')} 创建视图失败：{e}")

    def _on_design_view(self, conn_name: str, db_name: str, view_name: str):
        """设计视图：查询并显示视图 DDL"""
        connector = self._conns.get(conn_name)
        if not connector:
            QMessageBox.warning(self, "提示", "请先连接数据库")
            return
        db_type = connector.db_type
        try:
            if db_type in ("mysql", "oceanbase", "polardb", "tdsql", "tidb", "gbase"):
                sql = f"SHOW CREATE VIEW `{view_name}`"
                col_idx = 1   # CREATE VIEW 列
            elif db_type in ("postgresql", "gaussdb", "opengauss", "kingbase"):
                sql = (
                    f"SELECT pg_get_viewdef('{view_name}'::regclass, true)"
                )
                col_idx = 0
            elif db_type == "sqlserver":
                sql = (
                    f"SELECT OBJECT_DEFINITION(OBJECT_ID('{view_name}'))"
                )
                col_idx = 0
            elif db_type in ("oracle", "xugu", "shentong", "dameng"):
                sql = (
                    f"SELECT TEXT FROM user_views WHERE view_name=UPPER('{view_name}')"
                )
                col_idx = 0
            else:
                sql = (
                    f"SELECT view_definition FROM information_schema.views "
                    f"WHERE table_name='{view_name}'"
                )
                col_idx = 0

            with connector.engine.connect() as conn:
                result = conn.execute(sa_text(sql))
            row = result.fetchone()
            ddl = str(row[col_idx]) if row else "（无法获取 DDL）"

            dlg = QDialog(self)
            dlg.setWindowTitle(f"设计视图 — {view_name}")
            dlg.resize(720, 440)
            layout = QVBoxLayout(dlg)

            editor = QPlainTextEdit()
            editor.setPlainText(ddl)
            editor.setFont(QFont("Consolas", 10))
            editor.setReadOnly(False)
            layout.addWidget(editor)

            hint = QLabel(Icon.prefixed_text('lightbulb', "修改后点击「保存修改」将执行 CREATE OR REPLACE VIEW"))
            tokens = get_theme_tokens(load_theme())
            hint.setStyleSheet(f"color: {tokens['text_muted']}; font-size: 11px;")
            layout.addWidget(hint)

            btns = QDialogButtonBox(
                QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Close
            )
            btns.button(QDialogButtonBox.StandardButton.Save).setText("保存修改")
            btns.button(QDialogButtonBox.StandardButton.Close).setText("关闭")
            btns.accepted.connect(dlg.accept)
            btns.rejected.connect(dlg.reject)
            layout.addWidget(btns)

            if dlg.exec() == QDialog.DialogCode.Accepted:
                new_ddl = editor.toPlainText().strip()
                if new_ddl and new_ddl != ddl:
                    try:
                        with connector.engine.connect() as conn2:
                            conn2.execute(sa_text(new_ddl))
                            conn2.commit()
                        QMessageBox.information(self, "成功", "视图已更新！")
                        self.log(f"{Icon.char('success')} 视图 [{view_name}] 已更新")
                    except Exception as e2:
                        QMessageBox.critical(self, "执行失败", str(e2))
                        self.log(f"{Icon.char('error')} 更新视图失败：{e2}")
        except Exception as e:
            QMessageBox.critical(self, "查询失败", str(e))
            self.log(f"{Icon.char('error')} 查询视图DDL失败：{e}")

    def _on_drop_view(self, conn_name: str, db_name: str, view_name: str, item: QTreeWidgetItem):
        """删除视图"""
        connector = self._conns.get(conn_name)
        if not connector:
            QMessageBox.warning(self, "提示", "请先连接数据库")
        return
        ret = QMessageBox.question(
        self, "确认删除",
        f"确定要删除视图 [{view_name}] 吗？\n此操作不可恢复！",
        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        QMessageBox.StandardButton.No
        )
        if ret != QMessageBox.StandardButton.Yes:
            return
        db_type = connector.db_type
        try:
            if db_type in ("mysql", "oceanbase", "polardb", "tdsql", "tidb", "gbase"):
                sql = f"DROP VIEW IF EXISTS `{db_name}`.`{view_name}`"
            elif db_type in ("postgresql", "gaussdb", "opengauss", "kingbase"):
                sql = f"DROP VIEW IF EXISTS {view_name} CASCADE"
            elif db_type == "sqlserver":
                sql = f"DROP VIEW IF EXISTS dbo.{view_name}"
            elif db_type in ("oracle", "shentong", "dameng"):
                sql = f"DROP VIEW {view_name}"
            else:
                sql = f"DROP VIEW IF EXISTS {view_name}"

            with connector.engine.connect() as conn:
                conn.execute(sa_text(sql))
                conn.commit()

            # 从树中移除节点
            parent = item.parent()
            if parent:
                parent.removeChild(item)
            QMessageBox.information(self, "成功", f"视图 [{view_name}] 已删除")
            self.log(f"{Icon.char('success')} 视图 [{view_name}] 已删除")
        except Exception as e:
            QMessageBox.critical(self, "执行失败", str(e))
            self.log(f"{Icon.char('error')} 删除视图失败：{e}")

    def _refresh_views_group(self, conn_name: str, db_name: str):
        """刷新指定数据库下的视图分组节点"""
        root = self.tree.invisibleRootItem()
        for i in range(root.childCount()):
            conn_item = root.child(i)
            d = conn_item.data(0, Qt.ItemDataRole.UserRole)
            if d and d.get("name") == conn_name:
                for j in range(conn_item.childCount()):
                    db_item = conn_item.child(j)
                    dd = db_item.data(0, Qt.ItemDataRole.UserRole)
                    if dd and dd.get("db_name") == db_name:
                        for k in range(db_item.childCount()):
                            grp = db_item.child(k)
                            gd = grp.data(0, Qt.ItemDataRole.UserRole)
                            if gd and gd.get("kind") == "views":
                                self._refresh_group_node(grp)
                                return


        """复制连接：以原连接信息为模板新建，名称加「_copy」"""
        info = dict(self._conn_infos.get(conn_name, {}))
        if not info:
            return
        # 生成不重名的副本名称
        base_name = conn_name + "_copy"
        new_name = base_name
        idx = 2
        while new_name in self._conn_infos:
            new_name = f"{base_name}{idx}"
        idx += 1
        info["name"] = new_name
        dlg = ConnDialog(self, info)
        dlg.setWindowTitle("复制连接")
        if dlg.exec() == QDialog.DialogCode.Accepted:
            new_info = dlg.get_result()
            save_connection(new_info)
            self._remove_conn_node(new_info["name"])
            self._add_conn_node(new_info, connected=False)
            self.log(f"{Icon.char('success')} 连接 [{new_info['name']}] 已复制")

    def _on_rename_conn(self, item: QTreeWidgetItem, conn_name: str):
        """重命名连接：弹输入框，改名后同步更新树和存储"""
        new_name, ok = QInputDialog.getText(
        self, "重命名连接", "请输入新的连接名称：",
        QLineEdit.EchoMode.Normal, conn_name
        )
        if not ok or not new_name.strip() or new_name.strip() == conn_name:
            return
        new_name = new_name.strip()
        if new_name in self._conn_infos:
            QMessageBox.warning(self, "名称重复", f"已存在名为「{new_name}」的连接，请换一个名称。")
            return
        # 断开旧连接
        if conn_name in self._conns:
            self._conns[conn_name].engine.dispose()
        self._conns[new_name] = self._conns.pop(conn_name)
        # 更新 info
        info = dict(self._conn_infos[conn_name])
        info["name"] = new_name
        delete_connection(conn_name)
        save_connection(info)
        self._remove_conn_node(conn_name)
        self._add_conn_node(info, connected=(new_name in self._conns))
        self.log(f"{Icon.char('edit')} 连接 [{conn_name}] 已重命名为 [{new_name}]")

    # ─── 连接管理操作 ────────────────────────
    def _on_import_ncx(self):
        """从 Navicat .ncx 文件批量导入连接"""
        filepath, _ = QFileDialog.getOpenFileName(
        self, "选择 Navicat 连接导出文件", "",
        "Navicat 连接文件 (*.ncx);;所有文件 (*.*)"
        )
        if not filepath:
            return

        try:
            imported, skipped = parse_ncx(filepath)
        except Exception as e:
            QMessageBox.critical(self, "解析失败", f"无法解析 .ncx 文件：\n{e}")
            return

        if not imported and not skipped:
            QMessageBox.information(self, "提示", "文件中没有找到任何连接。")
            return

        # 检测与现有连接的冲突（同名）
        existing_names = set(self._conn_infos.keys())
        conflict = [c for c in imported if c["name"] in existing_names]
        new_only  = [c for c in imported if c["name"] not in existing_names]

        # 构建预览对话框
        dlg = _NcxImportPreviewDialog(self, new_only, conflict, skipped)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return

        selected, overwrite = dlg.get_result()
        if not selected:
            QMessageBox.information(self, "提示", "未选择任何连接，操作已取消。")
            return

        # 执行导入
        count = 0
        for info in selected:
            save_connection(info)
        self._remove_conn_node(info["name"])
        self._add_conn_node(info, connected=False)
        count += 1

        msg = f"{Icon.char('success')} 成功导入 {count} 条连接。"
        if skipped:
            msg += f"\n{Icon.char('warning')} 跳过 {len(skipped)} 条不支持的类型：\n" + "\n".join(f"  - {s}" for s in skipped)
        msg += f"\n\n{Icon.char('lightbulb')} 提示：Navicat 导出的连接不含密码，请双击连接后手动填写密码。"
        QMessageBox.information(self, "导入完成", msg)
        self.log(f"{Icon.char('download')} Navicat 连接导入完成：成功 {count} 条，跳过 {len(skipped)} 条")

    def _on_new_conn(self):
        dlg = ConnDialog(self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            info = dlg.get_result()
            save_connection(info)
            # 如果同名节点已存在则先移除
            self._remove_conn_node(info["name"])
            self._add_conn_node(info, connected=False)
            self.log(f"{Icon.char('success')} 连接 [{info['name']}] 已保存")

    def _on_edit_conn(self, conn_name: str):
        info = self._conn_infos.get(conn_name, {})
        dlg = ConnDialog(self, info)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            new_info = dlg.get_result()
            # 断开旧连接
            if conn_name in self._conns:
                self._conns[conn_name].engine.dispose()
            del self._conns[conn_name]
            # 如果改了名字，删除旧记录
            if new_info["name"] != conn_name:
                delete_connection(conn_name)
            self._remove_conn_node(conn_name)
            save_connection(new_info)
            self._remove_conn_node(new_info["name"])
            self._add_conn_node(new_info, connected=False)
            self.log(f"{Icon.char('success')} 连接 [{new_info['name']}] 已更新")

    def _on_delete_conn(self, item: QTreeWidgetItem, conn_name: str):
        ret = QMessageBox.question(
        self, "删除连接",
        f"确定删除连接 [{conn_name}] 吗？\n此操作不影响数据库本身。",
        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if ret == QMessageBox.StandardButton.Yes:
            if conn_name in self._conns:
                self._conns[conn_name].engine.dispose()
        del self._conns[conn_name]
        delete_connection(conn_name)
        self._remove_conn_node(conn_name)
        self.log(f"{Icon.char('delete')} 连接 [{conn_name}] 已删除")

    def _disconnect(self, item: QTreeWidgetItem, conn_name: str):
        if conn_name in self._conns:
            self._conns[conn_name].engine.dispose()
        del self._conns[conn_name]
        item.takeChildren()
        ph = QTreeWidgetItem(item)
        ph.setText(0, "")
        ph.setData(0, Qt.ItemDataRole.UserRole, {"type": -1})
        self._set_conn_icon(item, False)
        self.log(f"已断开 [{conn_name}]")

    def _on_refresh_conn(self, item: QTreeWidgetItem, conn_name: str):
        if conn_name in self._conns:
            del self._conns[conn_name]
        self._expand_connection(item, conn_name)

    def _remove_conn_node(self, conn_name: str):
        """从树上移除指定连接的顶层节点"""
        root = self.tree.invisibleRootItem()
        for i in range(root.childCount()):
            child = root.child(i)
            d = child.data(0, Qt.ItemDataRole.UserRole)
            if d and d.get("name") == conn_name:
                root.removeChild(child)
                break
        if conn_name in self._conn_infos:
            del self._conn_infos[conn_name]

    def _on_refresh(self):
        """刷新当前选中节点"""
        items = self.tree.selectedItems()
        if not items:
            return
        item = items[0]
        data = item.data(0, Qt.ItemDataRole.UserRole)
        if not data:
            return
        t = data.get("type")
        if t == NODE_CONNECTION:
            self._on_refresh_conn(item, data["name"])
        elif t == NODE_DATABASE:
            self._expand_database(item, data["conn_name"], data["db_name"])

    # ─── SQL 执行 ──────────────────────────
    def _on_clear_editor(self):
        """清空 SQL 编辑器"""
        self.sql_edit.clear()
        self.log(f"{Icon.char('file_text')} 编辑器已清空")

    def _on_exec(self):
        """执行全部 SQL（F5）"""
        sql = self.sql_edit.toPlainText().strip()
        self._execute_sql(sql)

    def _on_exec_selected(self):
        """执行选中的 SQL（F6）——无选中时执行光标所在语句"""
        cursor = self.sql_edit.textCursor()
        sql = cursor.selectedText().strip()
        if not sql:
            # 无选中：取光标所在的完整语句（以分号分割）
            full_text = self.sql_edit.toPlainText()
            pos = cursor.position()
            sql = self._extract_statement_at(full_text, pos)
        self._execute_sql(sql)

    def _extract_statement_at(self, full_text: str, pos: int) -> str:
        """从 full_text 中提取 pos 所在的 SQL 语句（以分号为分界）"""
        # 按分号拆分，找到 pos 所在的段
        parts = full_text.split(";")
        offset = 0
        for part in parts:
            end = offset + len(part)
            if offset <= pos <= end:
                return part.strip()
            offset = end + 1  # +1 for ";"
        return full_text.strip()

    def _execute_sql(self, sql: str):
        """实际执行 SQL 的核心逻辑"""
        if not sql:
            return
        if not self._conns:
            QMessageBox.information(self, "提示", "请先建立数据库连接")
            return
        conn_name = self._current_conn_name or next(iter(self._conns))
        connector = self._conns.get(conn_name)
        if not connector:
            self.log(f"{Icon.char('error')} 无可用连接")
            return
        import re as _re
        _m = _re.search(r'FROM\s+[`"\[]?(\w+)[`"\]]?', sql, _re.IGNORECASE)
        self._current_table_name = _m.group(1) if _m else ""
        self.log(f"{Icon.char('play')} 执行 SQL: {sql[:80].replace(chr(10), ' ')}{'…' if len(sql) > 80 else ''}")
        try:
            import time as _time
            t0 = _time.perf_counter()
            cols, rows = connector.execute(sql)
            elapsed = _time.perf_counter() - t0
            self._render_table(cols, rows)
            self.log(f"{Icon.char('success')} 执行成功，返回 {len(rows)} 行，耗时 {elapsed*1000:.0f} ms")
            # 更新标签页标题为前30个字符的 SQL
            self._rename_current_sql_tab(sql[:20].replace("\n", " ").strip() + "…" if len(sql) > 20 else sql)
        except Exception as e:
            self.log(f"{Icon.char('error')} 执行失败：{str(e)}")

    # ── SQL 格式化（Navicat 17 美化功能）──────────────
    def _on_format_sql(self):
        """格式化/美化当前 SQL 编辑器中的 SQL"""
        sql = self.sql_edit.toPlainText()
        if not sql.strip():
            return
        formatted = self._format_sql_text(sql)
        if formatted != sql:
            self.sql_edit.setPlainText(formatted)
        self.log(f"{Icon.char('sparkling')} SQL 已格式化")

    def _format_sql_text(self, sql: str) -> str:
        """
        简单 SQL 格式化器（不依赖第三方库）。
        - 关键字大写并换行
        - SELECT 子句列换行对齐
        - 保留注释
        """
        import re
        # 尝试用 sqlparse（如已安装）
        try:
            import sqlparse
            return sqlparse.format(
                sql,
                reindent=True,
                keyword_case="upper",
                indent_width=4,
                strip_comments=False,
            )
        except ImportError:
            pass
        # 降级：简单关键字大写 + 换行
        keywords_nl = [
        "SELECT", "FROM", "WHERE", "JOIN", "LEFT JOIN", "RIGHT JOIN",
        "INNER JOIN", "GROUP BY", "ORDER BY", "HAVING", "LIMIT",
        "UNION", "UNION ALL", "INSERT INTO", "UPDATE", "SET",
        "DELETE FROM", "CREATE TABLE", "ALTER TABLE",
        ]
        result = sql
        for kw in keywords_nl:
            result = re.sub(rf'\b{kw}\b', f'\n{kw}', result, flags=re.IGNORECASE)
        # 清理多余空行并大写关键字
        lines = [line.strip() for line in result.splitlines() if line.strip()]
        return "\n".join(lines)

    # ── 专注模式（Navicat 17 Focus Mode）───────────────
    def _on_focus_mode_toggled(self, on: bool):
        """专注模式：隐藏左侧连接面板 + 底部日志区"""
        # 左侧面板
        left_panel = self.centralWidget().findChild(QWidget, "leftPanel")
        if left_panel:
            left_panel.setVisible(not on)
        # 日志区
        if hasattr(self, "_log_panel"):
            self._log_panel.setVisible(not on)
        # AI 对话区（如有）
        if hasattr(self, "_ai_panel"):
            self._ai_panel.setVisible(not on)
        self._btn_focus.setText(Icon.prefixed_text('fullscreen_exit', "退出专注") if on else Icon.prefixed_text('fullscreen', "专注"))
        if on:
            self.statusBar().showMessage("专注模式已开启  F11 退出")
        else:
            self.statusBar().showMessage("已退出专注模式")

    def _on_selected_columns_changed(self, selected_cols):
        """处理列选中变化"""
        current = set(selected_cols)
        if current == self._last_logged_cols:
            return  # 列选择未变，跳过重复日志（避免全选/取消时每次都打印）
        self._last_logged_cols = current

        if selected_cols:
            col_names = []
            for col_idx in selected_cols:
                header_item = self.table.horizontalHeaderItem(col_idx)
                if header_item:
                    col_names.append(header_item.text())
            if col_names:
                self.log(f"{Icon.char('pushpin')} 选中列：{', '.join(col_names)}")


    # ─── 表格选择与操作 ──────────────────────

    def _on_table_item_changed(self, item: QTableWidgetItem):
        """复选框列变化时更新选中信息"""
        if getattr(self, "_refreshing", False):
            return
        if item.column() == 0:
            self._update_selected_info()
        # 刷新视图以确保复选框正确显示
        self.table.viewport().update()

    def _update_selected_info(self, count: int | None = None):
        """更新已选行提示 + 触发统计栏更新

        Args:
            count: 可选，已知勾选行数时传入可避免重复全行扫描
        """
        if count is None:
            count = self._get_checked_rows()
        total = self.table.rowCount()
        if count:
            self.lbl_selected_info.setText(f"已选 <b>{count}</b> 行")
            self.lbl_selected_info.setStyleSheet(f"font-size:11px; color:{self._tokens['accent']};")
            self._lbl_stat_bar.show()  # 有选中行时显示统计条
        else:
            self.lbl_selected_info.setText("已选 0 行")
            self.lbl_selected_info.setStyleSheet(f"font-size:11px; color:{self._tokens['text_muted']};")
            self._lbl_stat_bar.hide()  # 无选中行时隐藏统计条
        # 同步更新表头复选框状态
        header_item = self.table.horizontalHeaderItem(0)
        if header_item and header_item.flags() & Qt.ItemFlag.ItemIsUserCheckable:
            # QTableWidgetItem 不支持 PartiallyChecked 可视化，只支持二态切换
            old_state = header_item.checkState()
            if count == total and total > 0:
                header_item.setCheckState(Qt.CheckState.Checked)
            else:
                header_item.setCheckState(Qt.CheckState.Unchecked)
            new_state = header_item.checkState()
            # 同步 SortableTableHeader 的 _header_checked 状态（paintSection 依赖此值）
            partial = count > 0 and count < total
            self.table.horizontalHeader().set_header_check_state(
                new_state == Qt.CheckState.Checked, partial
            )
        # 刷新表头视图以确保复选框正确显示
        self.table.horizontalHeader().viewport().update()
        # 同步更新统计栏（Navicat 17 底部 SUM/AVG/COUNT/MIN/MAX）
        self._update_stat_bar()

    def _get_checked_rows(self) -> int:
        """返回当前已勾选的行数"""
        count = 0
        for i in range(self.table.rowCount()):
            item = self.table.item(i, 0)
            if item and item.checkState() == Qt.CheckState.Checked:
                count += 1
        return count

    def _get_checked_row_indices(self) -> list[int]:
        """返回已勾选行的行索引列表"""
        indices = []
        for i in range(self.table.rowCount()):
            item = self.table.item(i, 0)
            if item and item.checkState() == Qt.CheckState.Checked:
                indices.append(i)
        return indices

    def _on_header_clicked(self, logicalIndex: int):
        """表头复选框点击 - 全选/取消"""
        if logicalIndex != 0:  # 只处理第0列（复选框列）
            return
        header_item = self.table.horizontalHeaderItem(0)
        if not header_item or not (header_item.flags() & Qt.ItemFlag.ItemIsUserCheckable):
            return
        total_rows = self.table.rowCount()
        all_checked = header_item.checkState() == Qt.CheckState.Checked
        target_state = Qt.CheckState.Unchecked if all_checked else Qt.CheckState.Checked
        # 批量设所有行复选框（同时 block table 和 model 信号，避免逐 item 触发 dataChanged）
        new_state = Qt.CheckState.Checked if target_state == Qt.CheckState.Checked else Qt.CheckState.Unchecked
        self.table.blockSignals(True)
        self.table.model().blockSignals(True)
        for i in range(self.table.rowCount()):
            item = self.table.item(i, 0)
            if item:
                item.setCheckState(new_state)
        self.table.model().blockSignals(False)
        self.table.blockSignals(False)
        # 触发单元格重绘（blockSignals 阻止了 model.dataChanged，view 不知道数据变了）
        self.table.viewport().update()
        # 更新表头复选框状态 + 统一视图刷新
        header_item.setCheckState(target_state)
        checked_count = total_rows if target_state == Qt.CheckState.Checked else 0
        self._update_selected_info(checked_count)

    def _on_select_none(self):
        self.table.blockSignals(True)
        self.table.model().blockSignals(True)
        for i in range(self.table.rowCount()):
            item = self.table.item(i, 0)
            if item:
                item.setCheckState(Qt.CheckState.Unchecked)
        self.table.model().blockSignals(False)
        self.table.blockSignals(False)
        self.table.viewport().update()  # 触发单元格重绘
        self.table.horizontalHeader().set_header_check_state(False, False)
        self._update_selected_info(0)

    def _get_row_data(self, row_idx: int) -> list:
        """获取表格某行（不含复选框列）的单元格文本列表"""
        data = []
        for j in range(1, self.table.columnCount()):
            item = self.table.item(row_idx, j)
            data.append(item.text() if item else "")
        return data

    def _on_copy_selected_rows(self):
        """复制选中行到剪贴板（Tab 分隔，含列头）"""
        indices = self._get_checked_row_indices()
        if not indices:
            QMessageBox.information(self, "提示", "请先勾选要复制的行")
            return
        # 表头
        headers = [self.table.horizontalHeaderItem(j).text()
                   for j in range(1, self.table.columnCount())]
        lines = ["\t".join(headers)]
        for i in indices:
            lines.append("\t".join(self._get_row_data(i)))
        QApplication.clipboard().setText("\n".join(lines))
        self.log(f"{Icon.char('clipboard')} 已复制 {len(indices)} 行到剪贴板")

    def _on_export_selected_rows(self):
        """将选中行导出为 CSV 或 Excel"""
        indices = self._get_checked_row_indices()
        if not indices:
            QMessageBox.information(self, "提示", "请先勾选要导出的行")
        return
        path, ftype = QFileDialog.getSaveFileName(
        self, "导出选中行",
        f"export_{self._current_table_name or 'data'}.csv",
        "CSV 文件 (*.csv);;Excel 文件 (*.xlsx)"
        )
        if not path:
            return
        headers = [self.table.horizontalHeaderItem(j).text()
                   for j in range(1, self.table.columnCount())]
        data_rows = [self._get_row_data(i) for i in indices]

        if path.endswith(".xlsx"):
            try:
                import openpyxl
                wb = openpyxl.Workbook()
                ws = wb.active
                ws.append(headers)
                for r in data_rows:
                    ws.append(r)
                wb.save(path)
                self.log(f"{Icon.char('upload')} 已导出 {len(indices)} 行到 {path}")
            except ImportError:
                QMessageBox.warning(self, "缺少依赖", "导出 Excel 需要安装 openpyxl：\npip install openpyxl")
        else:
            import csv
            with open(path, "w", newline="", encoding="utf-8-sig") as f:
                writer = csv.writer(f)
                writer.writerow(headers)
                writer.writerows(data_rows)
            self.log(f"{Icon.char('upload')} 已导出 {len(indices)} 行到 {path}")

    # ─── 表格内联编辑（增删改查写回数据库）──────────

    def _build_text_preview(self, value, max_chars: int = 300, max_lines: int = 6) -> str:
        """生成适合弹窗/日志展示的文本预览，避免超长内容撑爆界面。"""
        if value is None:
            return "NULL"

        text = str(value).replace("\r\n", "\n").replace("\r", "\n")
        lines = text.split("\n")
        preview_lines = []
        used = 0

        for idx, line in enumerate(lines):
            if idx >= max_lines or used >= max_chars:
                break
            remain = max_chars - used
            part = line[:remain]
            preview_lines.append(part)
            used += len(part)
            if len(line) > len(part):
                break

        preview = "\n".join(preview_lines)
        if len(preview) < len(text) or len(lines) > len(preview_lines):
            preview += "\n…"
        return preview

    def _set_sql_preview(self, sql: str, max_chars: int = 6000):
        """超长 SQL 不整段塞回编辑器，避免再次卡住界面。"""
        if len(sql) <= max_chars:
            self.sql_edit.setPlainText(sql)
        return

        preview = sql[:max_chars] + "\n\n-- SQL 过长，界面仅显示前 6000 个字符预览。"
        self.sql_edit.setPlainText(preview)
        self.log(f"{Icon.char('info')} SQL 过长（{len(sql)} 字符），编辑器中仅显示前 {max_chars} 个字符预览")

    def _looks_like_html(self, text: str) -> bool:
        text = (text or "").strip().lower()
        if not text or "<" not in text or ">" not in text:
            return False
        markers = (
        "<html", "<body", "<div", "<span", "<p", "<br", "<table", "<tr", "<td",
        "<img", "<a ", "<ul", "<ol", "<li", "<strong", "<em", "<h1", "<h2", "<h3"
        )
        return any(marker in text for marker in markers)

    def _looks_like_markdown(self, text: str) -> bool:
        text = (text or "").strip()
        if not text or self._looks_like_html(text):
            return False
        markers = ("# ", "## ", "### ", "- ", "* ", "1. ", "```", "> ", "**", "__", "](", "![](")
        return any(marker in text for marker in markers)

    def _guess_text_edit_mode(self, text: str) -> str:
        if self._looks_like_html(text):
            return "html"
        if self._looks_like_markdown(text):
            return "markdown"
        return "plain"

    def _convert_text_between_modes(self, text: str, from_mode: str, to_mode: str) -> str:
        text = "" if text is None else str(text)
        if from_mode == to_mode or not text:
            return text

        doc = QTextDocument()
        if from_mode in ("html", "rich"):
            doc.setHtml(text)
        elif from_mode == "markdown":
            doc.setMarkdown(text)
        else:
            doc.setPlainText(text)

        if to_mode == "plain":
            return doc.toPlainText()
        if to_mode == "html":
            return text if from_mode in ("html", "rich") else doc.toHtml()
        if to_mode == "markdown":
            return text if from_mode == "markdown" else doc.toMarkdown()
        return text

    def _open_large_text_editor(self, col_name: str, old_val: str):
        """可调大小的大字段编辑器，支持纯文本 / HTML / Markdown / 富文本。"""
        dlg = QDialog(self)
        dlg.setWindowTitle(f"编辑单元格 [{col_name}]")
        dlg.setModal(True)
        dlg.setSizeGripEnabled(True)
        dlg.setWindowFlag(Qt.WindowType.WindowMinimizeButtonHint, True)
        dlg.setWindowFlag(Qt.WindowType.WindowMaximizeButtonHint, True)

        screen = QApplication.primaryScreen()
        if screen:
            geo = screen.availableGeometry()
            dlg.resize(min(1280, max(860, int(geo.width() * 0.72))), min(860, max(560, int(geo.height() * 0.76))))
        else:
            dlg.resize(980, 640)
        dlg.setMinimumSize(760, 520)

        layout = QVBoxLayout(dlg)
        layout.setContentsMargins(14, 12, 14, 10)
        layout.setSpacing(8)

        info = QLabel(
        f"列：{col_name}    当前值长度：{len(old_val)} 字符\n"
        "已切换为可调整大小的多文本编辑器；可按需要选择纯文本、HTML、Markdown 或富文本模式，左右分栏也可拖动调整。"
        )

        info.setWordWrap(True)
        layout.addWidget(info)

        mode_row = QHBoxLayout()
        mode_row.setContentsMargins(0, 0, 0, 0)
        mode_row.setSpacing(8)
        mode_row.addWidget(QLabel("编辑模式"))

        mode_combo = QComboBox()
        mode_combo.addItem("纯文本", "plain")
        mode_combo.addItem("HTML", "html")
        mode_combo.addItem("Markdown", "markdown")
        mode_combo.addItem("富文本", "rich")
        mode_row.addWidget(mode_combo)
        mode_row.addStretch()

        mode_help = QLabel("")
        mode_help.setProperty("role", "muted")
        mode_help.setWordWrap(True)
        mode_row.addWidget(mode_help, stretch=1)
        layout.addLayout(mode_row)

        preview_label = QLabel("原值预览")
        preview_label.setProperty("role", "muted")
        layout.addWidget(preview_label)

        old_preview = QPlainTextEdit()
        old_preview.setReadOnly(True)
        old_preview.setMaximumHeight(120)
        old_preview.setPlainText(self._build_text_preview(old_val, max_chars=1600, max_lines=18))
        layout.addWidget(old_preview)

        source_editor = QPlainTextEdit()
        source_editor.setLineWrapMode(QPlainTextEdit.LineWrapMode.WidgetWidth)
        source_editor.setTabChangesFocus(False)

        rich_editor = QTextEdit()
        rich_editor.setAcceptRichText(True)
        rich_editor.setTabChangesFocus(False)

        def _merge_rich_format(fmt: QTextCharFormat):
            cursor = rich_editor.textCursor()
            cursor.mergeCharFormat(fmt)
            rich_editor.mergeCurrentCharFormat(fmt)
            rich_editor.setFocus()

        rich_toolbar = QWidget()
        toolbar_layout = QHBoxLayout(rich_toolbar)
        toolbar_layout.setContentsMargins(0, 0, 0, 0)
        toolbar_layout.setSpacing(4)

        def _make_tool_btn(text: str, tip: str, handler):
            btn = QToolButton()
            btn.setText(text)
            btn.setToolTip(tip)
            btn.clicked.connect(handler)
            toolbar_layout.addWidget(btn)
            return btn

        def _toggle_bold():
            fmt = QTextCharFormat()
            cur_weight = rich_editor.fontWeight()
            fmt.setFontWeight(QFont.Weight.Normal if cur_weight > QFont.Weight.Normal else QFont.Weight.Bold)
            _merge_rich_format(fmt)

        def _toggle_italic():
            fmt = QTextCharFormat()
            fmt.setFontItalic(not rich_editor.fontItalic())
            _merge_rich_format(fmt)

        def _toggle_underline():
            fmt = QTextCharFormat()
            fmt.setFontUnderline(not rich_editor.fontUnderline())
            _merge_rich_format(fmt)

        def _insert_list(style):
            cursor = rich_editor.textCursor()
            cursor.beginEditBlock()
            list_fmt = QTextListFormat()
            list_fmt.setStyle(style)
            cursor.createList(list_fmt)
            cursor.endEditBlock()
            rich_editor.setTextCursor(cursor)
            rich_editor.setFocus()

        _make_tool_btn("B", "加粗", _toggle_bold)
        _make_tool_btn("I", "斜体", _toggle_italic)
        _make_tool_btn("U", "下划线", _toggle_underline)
        _make_tool_btn(Icon.prefixed_text('text', "列表"), "项目符号列表", lambda: _insert_list(QTextListFormat.Style.ListDisc))
        _make_tool_btn("1. 列表", "编号列表", lambda: _insert_list(QTextListFormat.Style.ListDecimal))
        toolbar_layout.addStretch()

        editor_stack = QStackedWidget()
        source_page = QWidget()
        source_layout = QVBoxLayout(source_page)
        source_layout.setContentsMargins(0, 0, 0, 0)
        source_layout.setSpacing(4)
        source_layout.addWidget(source_editor, stretch=1)

        rich_page = QWidget()
        rich_layout = QVBoxLayout(rich_page)
        rich_layout.setContentsMargins(0, 0, 0, 0)
        rich_layout.setSpacing(4)
        rich_layout.addWidget(rich_toolbar)
        rich_layout.addWidget(rich_editor, stretch=1)

        editor_stack.addWidget(source_page)
        editor_stack.addWidget(rich_page)

        preview_panel = QTextEdit()
        preview_panel.setReadOnly(True)
        preview_panel.setMinimumWidth(220)
        preview_panel.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        editor_stack.setMinimumWidth(260)
        editor_stack.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setChildrenCollapsible(False)
        splitter.setOpaqueResize(True)
        splitter.setHandleWidth(10)
        splitter.addWidget(editor_stack)
        splitter.addWidget(preview_panel)
        splitter.setStretchFactor(0, 5)
        splitter.setStretchFactor(1, 4)
        splitter.setSizes([int(max(dlg.width() * 0.55, 420)), int(max(dlg.width() * 0.45, 320))])
        layout.addWidget(splitter, stretch=1)

        tip = QLabel("提示：Ctrl+Enter 可直接保存；HTML / Markdown 模式下可拖动中间分隔条，调整左右区域宽度。")

        tip.setProperty("role", "muted")
        tip.setWordWrap(True)
        layout.addWidget(tip)

        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        ok_btn = btns.button(QDialogButtonBox.StandardButton.Ok)
        ok_btn.setText("保存")
        cancel_btn = btns.button(QDialogButtonBox.StandardButton.Cancel)
        cancel_btn.setText("取消")
        btns.accepted.connect(dlg.accept)
        btns.rejected.connect(dlg.reject)
        layout.addWidget(btns)

        state = {"mode": self._guess_text_edit_mode(old_val), "preview_visible": False}
        source_editor.setPlainText(old_val)
        source_editor.moveCursor(QTextCursor.MoveOperation.End)

        def _reset_editor_splitter():
            total_width = max(splitter.width(), dlg.width() - 36, 760)
            splitter.setSizes([int(total_width * 0.55), int(total_width * 0.45)])

        def _load_into_rich(text: str, source_mode: str):
            rich_editor.blockSignals(True)
            if source_mode == "html":
                rich_editor.setHtml(text)
            elif source_mode == "markdown":
                rich_editor.setMarkdown(text)
            else:
                rich_editor.setPlainText(self._convert_text_between_modes(text, source_mode, "plain"))
            rich_editor.moveCursor(QTextCursor.MoveOperation.End)
            rich_editor.blockSignals(False)

        def _update_mode_ui():
            mode = state["mode"]
            if mode == "plain":
                editor_stack.setCurrentWidget(source_page)
                rich_toolbar.setVisible(False)
                preview_panel.setVisible(False)
                state["preview_visible"] = False
                mode_help.setText("按原样保存普通文本字符串。")
            elif mode == "html":
                editor_stack.setCurrentWidget(source_page)
                rich_toolbar.setVisible(False)
                preview_panel.setVisible(True)
                if not state["preview_visible"]:
                    _reset_editor_splitter()
                state["preview_visible"] = True
                preview_panel.setHtml(source_editor.toPlainText())
                mode_help.setText("左侧编辑 HTML 源码，右侧实时预览渲染效果，可拖动中间分隔条调整宽度。")
            elif mode == "markdown":
                editor_stack.setCurrentWidget(source_page)
                rich_toolbar.setVisible(False)
                preview_panel.setVisible(True)
                if not state["preview_visible"]:
                    _reset_editor_splitter()
                state["preview_visible"] = True
                preview_panel.setMarkdown(source_editor.toPlainText())
                mode_help.setText("左侧编辑 Markdown 源码，右侧实时预览渲染效果，可拖动中间分隔条调整宽度。")
            else:
                editor_stack.setCurrentWidget(rich_page)
                rich_toolbar.setVisible(True)
                preview_panel.setVisible(False)
        state["preview_visible"] = False
        mode_help.setText("可视化编辑富文本，保存时会写回 HTML 字符串。")


        def _switch_mode():
            new_mode = mode_combo.currentData()
            old_mode = state["mode"]
            if new_mode == old_mode:
                _update_mode_ui()
                return
            payload = rich_editor.toHtml() if old_mode == "rich" else source_editor.toPlainText()
            if new_mode == "rich":
                _load_into_rich(payload, old_mode)
            else:
                converted = self._convert_text_between_modes(payload, old_mode, new_mode)
                source_editor.blockSignals(True)
                source_editor.setPlainText(converted)
                source_editor.moveCursor(QTextCursor.MoveOperation.End)
                source_editor.blockSignals(False)
            state["mode"] = new_mode
            _update_mode_ui()

        source_editor.textChanged.connect(_update_mode_ui)
        mode_combo.currentIndexChanged.connect(_switch_mode)

        for target in (source_editor, rich_editor):
            shortcut = QShortcut(QKeySequence("Ctrl+Return"), target)
            shortcut.activated.connect(dlg.accept)
            shortcut2 = QShortcut(QKeySequence("Ctrl+Enter"), target)
            shortcut2.activated.connect(dlg.accept)

        init_idx = mode_combo.findData(state["mode"])
        mode_combo.setCurrentIndex(init_idx if init_idx >= 0 else 0)
        _update_mode_ui()

        if dlg.exec() != QDialog.DialogCode.Accepted:
            return old_val, False

        final_mode = state["mode"]
        if final_mode == "rich":
            return rich_editor.toHtml(), True
        return source_editor.toPlainText(), True


    def _confirm_sql_preview(self, title: str, intro: str, sql: str) -> bool:
        """超长 SQL 使用受限预览窗口确认，避免 QMessageBox 直接卡死。"""
        dlg = QDialog(self)
        dlg.setWindowTitle(title)
        dlg.setModal(True)
        dlg.resize(820, 480)
        dlg.setMinimumSize(620, 360)

        layout = QVBoxLayout(dlg)
        layout.setContentsMargins(14, 12, 14, 10)
        layout.setSpacing(8)

        lbl = QLabel(intro)
        lbl.setWordWrap(True)
        layout.addWidget(lbl)

        preview = QPlainTextEdit()
        preview.setReadOnly(True)
        preview.setPlainText(self._build_text_preview(sql, max_chars=4000, max_lines=40))
        layout.addWidget(preview, stretch=1)

        if len(sql) > 4000:
            tip = QLabel(f"SQL 共 {len(sql)} 个字符，当前仅显示前 4000 个字符预览。")
            tip.setProperty("role", "muted")
            layout.addWidget(tip)

        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Yes | QDialogButtonBox.StandardButton.No)
        yes_btn = btns.button(QDialogButtonBox.StandardButton.Yes)
        yes_btn.setText("确认执行")
        no_btn = btns.button(QDialogButtonBox.StandardButton.No)
        no_btn.setText("取消")
        btns.accepted.connect(dlg.accept)
        btns.rejected.connect(dlg.reject)
        layout.addWidget(btns)

        return dlg.exec() == QDialog.DialogCode.Accepted

    def _on_edit_mode_toggled(self, checked: bool):

        """切换编辑模式"""
        self._edit_mode = checked
        if checked:
            self.btn_edit_mode.setStyleSheet(
                f"QToolButton{{ font-size:12px; padding:2px 6px; border:none;"
                f" border-radius: 4px; background:{self._tokens['accent_soft']}; color:{self._tokens['accent']}; }}"
            )
            self.log(f"{Icon.char('edit')} 编辑模式已开启 — 双击单元格可直接修改数据")
        else:
            self.btn_edit_mode.setStyleSheet(
                f"QToolButton{{ font-size:12px; padding:2px 6px; border:none;"
                f" border-radius: 4px; background:transparent; }}"
                f"QToolButton:hover{{ background:{self._tokens['accent_soft']}; }}"
            )
            self.log("编辑模式已关闭")
        # 重新渲染（切换 ItemIsEditable flag）
        self._refresh_page()

    def _on_cell_double_clicked(self, row: int, col: int):
        """双击单元格：在编辑模式下弹出编辑对话框"""
        if col == 0:  # 复选框列
            return
        if not self._edit_mode:
            return
        if not self._current_table_name:
            QMessageBox.information(self, "提示", "当前结果集不来自单一表，无法直接修改。\n请在 SQL 编辑器中执行 UPDATE 语句。")
        return
        col_name = self.table.horizontalHeaderItem(col).text() if self.table.horizontalHeaderItem(col) else f"col{col}"
        cur_item = self.table.item(row, col)
        old_val = cur_item.text() if cur_item else ""

        # 弹出受限尺寸的多行编辑对话框，避免长文本把默认输入框撑爆
        new_val, ok = self._open_large_text_editor(col_name, old_val)
        if not ok or new_val == old_val:
            return


        # 找到主键列的值（用于 WHERE 条件）
        pk_col = self._table_pk_col or (self._all_cols[0] if self._all_cols else "")
        pk_idx = self._all_cols.index(pk_col) + 1 if pk_col in self._all_cols else 1
        pk_item = self.table.item(row, pk_idx)
        pk_val = pk_item.text() if pk_item else ""

        # 生成 UPDATE SQL
        table = self._current_table_name
        db_name = self._current_db_name
        db_type = self._conn_infos.get(self._current_conn_name, {}).get("db_type", "mysql") if self._current_conn_name else "mysql"
        q = "`" if db_type in ("mysql", "mariadb", "tidb", "oceanbase", "polardb", "tdsql", "gbase") else '"'
        full_table = f"{q}{db_name}{q}.{q}{table}{q}" if db_name else f"{q}{table}{q}"
        try:
            new_val_escaped = new_val.replace("'", "''")
            # pk 为 NULL 时用 IS NULL 条件
            if pk_val == "NULL":
                where_clause = f"{q}{pk_col}{q} IS NULL"
            else:
                pk_val_escaped = pk_val.replace("'", "''")
                where_clause = f"{q}{pk_col}{q} = '{pk_val_escaped}'"
            sql = (
                f"UPDATE {full_table} "
                f"SET {q}{col_name}{q} = '{new_val_escaped}' "
                f"WHERE {where_clause}"
            )
        except Exception as e:
            QMessageBox.critical(self, "错误", f"构造 SQL 失败：{e}")
        return

        # 预览并确认（超长 SQL 只展示受限预览，避免确认框卡死）
        if not self._confirm_sql_preview("确认修改", "将执行以下 SQL，确认执行？", sql):
            return


        # 执行
        connector = self._conns.get(self._current_conn_name)
        if not connector:
            QMessageBox.critical(self, "错误", "无可用数据库连接")
        return
        try:
            connector.execute(sql)
            # 更新表格单元格显示
            self.table.blockSignals(True)
            if cur_item:
                cur_item.setText(new_val)
            self.table.blockSignals(False)
            # 同步更新 _all_rows（以便翻页后不丢失修改）
            ps = self._get_page_size()
            global_row = (self._page_offset if ps else 0) + row
            if 0 <= global_row < len(self._all_rows):
                row_list = list(self._all_rows[global_row])
                row_list[col - 1] = new_val
                self._all_rows[global_row] = tuple(row_list)
            val_preview = self._build_text_preview(new_val, max_chars=160, max_lines=2).replace("\n", " ")
            pk_preview = self._build_text_preview(pk_val, max_chars=80, max_lines=1).replace("\n", " ")
            self.log(f"{Icon.char('success')} UPDATE 成功：{col_name} = {val_preview}（{pk_col}={pk_preview}）")
            self._set_sql_preview(sql)
        except Exception as e:
            QMessageBox.critical(self, "执行失败", str(e))
        self.log(f"{Icon.char('error')} UPDATE 失败：{e}")

    def _on_add_row(self):
        """新增行：弹出对话框填写各列值，生成 INSERT SQL"""
        if not self._current_table_name:
            QMessageBox.information(self, "提示", "请先点击左侧表节点加载一张表，再新增行。")
        return
        if not self._all_cols:
            QMessageBox.information(self, "提示", "当前无列信息，无法新增行。")
        return

        dlg = QDialog(self)
        dlg.setWindowTitle(f"新增行  —  {self._current_table_name}")
        dlg.setMinimumWidth(460)
        form = QFormLayout(dlg)
        form.setSpacing(8)
        form.setContentsMargins(16, 14, 16, 10)

        edits: dict[str, QLineEdit] = {}
        for col in self._all_cols:
            edit = QLineEdit()
        edit.setPlaceholderText("（留空则传 NULL）")
        form.addRow(col, edit)
        edits[col] = edit

        btns = QDialogButtonBox(
        QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        btns.button(QDialogButtonBox.StandardButton.Ok).setText("插入")
        btns.accepted.connect(dlg.accept)
        btns.rejected.connect(dlg.reject)
        form.addRow(btns)

        if dlg.exec() != QDialog.DialogCode.Accepted:
            return

        db_type = self._conn_infos.get(self._current_conn_name, {}).get("db_type", "mysql") if self._current_conn_name else "mysql"
        q = "`" if db_type in ("mysql", "mariadb", "tidb", "oceanbase", "polardb", "tdsql", "gbase") else '"'
        table = self._current_table_name
        db_name = self._current_db_name
        full_table = f"{q}{db_name}{q}.{q}{table}{q}" if db_name else f"{q}{table}{q}"

        col_parts, val_parts = [], []
        for col, edit in edits.items():
            val = edit.text()
        col_parts.append(f"{q}{col}{q}")
        if val.strip() == "":
            val_parts.append("NULL")
        else:
            val_parts.append(f"'{val.strip().replace(chr(39), chr(39)+chr(39))}'")

        sql = f"INSERT INTO {full_table} ({', '.join(col_parts)}) VALUES ({', '.join(val_parts)})"

        ret = QMessageBox.question(
        self, "确认插入",
        f"将执行以下 SQL：\n\n{sql}\n\n确认执行？",
        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if ret != QMessageBox.StandardButton.Yes:
            return

        connector = self._conns.get(self._current_conn_name)
        if not connector:
            QMessageBox.critical(self, "错误", "无可用数据库连接")
        return
        try:
            connector.execute(sql)
            self.log(f"{Icon.char('success')} INSERT 成功：{sql}")
            self.sql_edit.setPlainText(sql)
            # 刷新数据
            self._load_table_data(self._current_conn_name, self._current_db_name, self._current_table_name)
        except Exception as e:
            QMessageBox.critical(self, "执行失败", str(e))
            self.log(f"{Icon.char('error')} INSERT 失败：{e}")

    def _on_delete_selected_rows(self):
        """删除选中行（通过主键 WHERE 条件）"""
        indices = self._get_checked_row_indices()
        if not indices:
            QMessageBox.information(self, "提示", "请先勾选要删除的行")
        return
        if not self._current_table_name:
            QMessageBox.information(self, "提示", "当前结果集不来自单一表，无法直接删除。\n请在 SQL 编辑器中执行 DELETE 语句。")
        return

        pk_col = self._table_pk_col or (self._all_cols[0] if self._all_cols else "")
        if not pk_col:
            QMessageBox.warning(self, "无主键", "无法确定主键列，请手动执行 DELETE 语句。")
        return

        pk_idx = self._all_cols.index(pk_col) + 1 if pk_col in self._all_cols else 1
        pk_vals = []
        for i in indices:
            pk_item = self.table.item(i, pk_idx)
        if pk_item:
            pk_vals.append(pk_item.text())

        db_type = self._conn_infos.get(self._current_conn_name, {}).get("db_type", "mysql") if self._current_conn_name else "mysql"
        q = "`" if db_type in ("mysql", "mariadb", "tidb", "oceanbase", "polardb", "tdsql", "gbase") else '"'
        table = self._current_table_name
        db_name = self._current_db_name

        # 带库名前缀，避免跨库时找错表
        full_table = f"{q}{db_name}{q}.{q}{table}{q}" if db_name else f"{q}{table}{q}"

        # 区分 NULL 与非 NULL 值（渲染时 None 存为字符串 "NULL"）
        null_rows = [v for v in pk_vals if v == "NULL"]
        non_null_vals = [v for v in pk_vals if v != "NULL"]

        sqls = []
        if non_null_vals:
            val_list = ", ".join(f"'{v.replace(chr(39), chr(39)+chr(39))}'" for v in non_null_vals)
        sqls.append(f"DELETE FROM {full_table} WHERE {q}{pk_col}{q} IN ({val_list})")
        if null_rows:
            # 主键为 NULL 的行用 IS NULL 条件
            sqls.append(f"DELETE FROM {full_table} WHERE {q}{pk_col}{q} IS NULL")

        if not sqls:
            QMessageBox.warning(self, "无数据", "未能获取有效的主键值")
        return

        sql_preview = "\n".join(sqls)
        ret = QMessageBox.question(
        self, "确认删除",
        f"将删除 {len(indices)} 行，执行以下 SQL：\n\n{sql_preview}\n\n此操作不可逆，确认执行？",
        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        QMessageBox.StandardButton.No
        )
        if ret != QMessageBox.StandardButton.Yes:
            return

        connector = self._conns.get(self._current_conn_name)
        if not connector:
            QMessageBox.critical(self, "错误", "无可用数据库连接")
        return
        try:
            for sql in sqls:
                connector.execute(sql)
            self.log(f"{Icon.char('delete')} DELETE 成功：删除 {len(indices)} 行（{pk_col} IN {pk_vals}）")
            self.sql_edit.setPlainText(sql_preview)
            # 刷新数据
            self._load_table_data(self._current_conn_name, self._current_db_name, self._current_table_name)
        except Exception as e:
            QMessageBox.critical(self, "执行失败", str(e))
            self.log(f"{Icon.char('error')} DELETE 失败：{e}")

    def _table_context_menu(self, pos: "QPoint"):
        """表格右键菜单（Navicat 17 风格增强版）"""
        row = self.table.rowAt(pos.y())
        col = self.table.columnAt(pos.x())
        menu = QMenu(self)
        menu.setStyleSheet(build_popup_base_style(self._current_theme))

        # ── 单元格/行操作 ──
        item = self.table.item(row, col) if (row >= 0 and col > 0) else None
        col_name = self.table.horizontalHeaderItem(col).text() if self.table.horizontalHeaderItem(col) else ""
        val = item.text() if item else ""

        copy_menu = menu.addMenu(Icon.prefixed_text('clipboard', "复制"))

        copy_menu.addAction("复制单元格", lambda: QApplication.clipboard().setText(val))
        copy_menu.addAction("复制整行（Tab 分隔）", lambda: QApplication.clipboard().setText(
        "\t".join(self._get_row_data(row))
        ))
        copy_menu.addSeparator()
        copy_menu.addAction(Icon.prefixed_text('file_text', "复制为 INSERT SQL"), lambda: self._copy_rows_as_insert([row]))
        copy_menu.addAction("{ } 复制为 JSON", lambda: self._copy_rows_as_json([row]))
        copy_menu.addAction(Icon.prefixed_text('edit', "复制为 UPDATE SQL"), lambda: self._copy_row_as_update(row))

        menu.addSeparator()

        if self._edit_mode and self._current_table_name:
            act_edit = menu.addAction(Icon.prefixed_text('edit', f"编辑单元格 [{col_name}]"))
            act_edit.triggered.connect(lambda: self._on_cell_double_clicked(row, col))

        menu.addSeparator()

        act_del_row = menu.addAction(Icon.prefixed_text('delete', "删除此行"))
        act_del_row.triggered.connect(lambda: self._delete_single_row(row))

        menu.addSeparator()

        # ── 选择操作 ──
        if row >= 0:
            chk_item = self.table.item(row, 0)
            if chk_item:
                is_checked = chk_item.checkState() == Qt.CheckState.Checked
                act_chk = menu.addAction("取消勾选此行" if is_checked else "勾选此行")
                def _toggle_row(r=row, c=chk_item):
                    c.setCheckState(Qt.CheckState.Unchecked if is_checked else Qt.CheckState.Checked)
                act_chk.triggered.connect(_toggle_row)

        sel_menu = menu.addMenu(Icon.prefixed_text('check', "选择"))
        sel_menu.addAction("全选", lambda: self._on_header_clicked(0))
        sel_menu.addAction("取消全选", self._on_select_none)

        menu.addSeparator()

        # ── 批量操作 ──
        batch_menu = menu.addMenu(Icon.prefixed_text('clipboard', "批量复制"))
        batch_menu.addAction("复制选中行（Tab 分隔）", self._on_copy_selected_rows)
        batch_menu.addAction("复制为 INSERT SQL", self._copy_checked_rows_as_insert)
        batch_menu.addAction("复制为 JSON 数组", self._copy_checked_rows_as_json)
        batch_menu.addAction("复制为 CSV", self._copy_checked_rows_as_csv)

        act_export_sel = menu.addAction(Icon.prefixed_text('upload', "导出选中行…"))
        act_export_sel.triggered.connect(self._on_export_selected_rows)

        # ── 数据编辑 ──
        if self._current_table_name:
            menu.addSeparator()
        act_add = menu.addAction(Icon.prefixed_text('add', "新增行…"))
        act_add.triggered.connect(self._on_add_row)
        act_del_sel = menu.addAction(Icon.prefixed_text('delete', "删除选中行"))
        act_del_sel.triggered.connect(self._on_delete_selected_rows)

        menu.exec(self.table.mapToGlobal(pos))

    def _delete_single_row(self, row: int):
        """通过右键菜单删除单行"""
        # 先勾选该行，再复用批量删除逻辑
        self.table.blockSignals(True)
        chk = self.table.item(row, 0)
        if chk:
            chk.setCheckState(Qt.CheckState.Checked)
        self.table.blockSignals(False)
        self._on_delete_selected_rows()

    # ── 行数据格式化复制（Navicat 17 风格）────────────────
    def _get_all_col_names(self) -> list[str]:
        """获取所有数据列名（跳过复选框列0）"""
        cols = []
        for j in range(1, self.table.columnCount()):
            h = self.table.horizontalHeaderItem(j)
            cols.append(h.text() if h else f"col{j}")
        return cols

    def _get_row_vals(self, row: int) -> list[str]:
        """获取指定行所有单元格文本（跳过复选框列0）"""
        vals = []
        for j in range(1, self.table.columnCount()):
            it = self.table.item(row, j)
            vals.append(it.text() if it else "NULL")
        return vals

    def _get_checked_row_indices(self) -> list[int]:
        """返回所有勾选行的行号"""
        rows = []
        for r in range(self.table.rowCount()):
            chk = self.table.item(r, 0)
            if chk and chk.checkState() == Qt.CheckState.Checked:
                rows.append(r)
        return rows

    def _rows_to_insert_sql(self, row_indices: list[int]) -> str:
        """将指定行转为 INSERT INTO ... VALUES (...) SQL"""
        table_name = self._current_table_name or "table_name"
        col_names = self._get_all_col_names()
        lines = []
        cols_str = ", ".join(f"`{c}`" for c in col_names)
        for row in row_indices:
            vals = self._get_row_vals(row)
            vals_str = ", ".join(
                "NULL" if v == "NULL" else f"'{v}'" if not v.lstrip("-").replace(".", "").isdigit() else v
                for v in vals
            )
            lines.append(f"INSERT INTO `{table_name}` ({cols_str}) VALUES ({vals_str});")
        return "\n".join(lines)

    def _rows_to_json(self, row_indices: list[int]) -> str:
        """将指定行转为 JSON 数组字符串"""
        import json
        col_names = self._get_all_col_names()
        result = []
        for row in row_indices:
            vals = self._get_row_vals(row)
            obj = {}
            for c, v in zip(col_names, vals):
                if v == "NULL":
                    obj[c] = None
                else:
                    # 尝试转数值
                    try:
                        if "." in v:
                            obj[c] = float(v)
                        else:
                            obj[c] = int(v)
                    except ValueError:
                        obj[c] = v
            result.append(obj)
        return json.dumps(result, ensure_ascii=False, indent=2)

    def _rows_to_csv(self, row_indices: list[int]) -> str:
        """将指定行转为 CSV 字符串"""
        import csv, io
        col_names = self._get_all_col_names()
        buf = io.StringIO()
        w = csv.writer(buf)
        w.writerow(col_names)
        for row in row_indices:
            w.writerow(self._get_row_vals(row))
        return buf.getvalue()

    def _copy_rows_as_insert(self, row_indices: list[int]):
        sql = self._rows_to_insert_sql(row_indices)
        QApplication.clipboard().setText(sql)
        self.log(f"{Icon.char('clipboard')} 已复制 {len(row_indices)} 行为 INSERT SQL")

    def _copy_rows_as_json(self, row_indices: list[int]):
        js = self._rows_to_json(row_indices)
        QApplication.clipboard().setText(js)
        self.log(f"{Icon.char('clipboard')} 已复制 {len(row_indices)} 行为 JSON")

    def _copy_row_as_update(self, row: int):
        """复制单行为 UPDATE SQL（类 Navicat）"""
        table_name = self._current_table_name or "table_name"
        col_names = self._get_all_col_names()
        vals = self._get_row_vals(row)
        pk_col = self._table_pk_col or (col_names[0] if col_names else "id")
        pk_idx = col_names.index(pk_col) if pk_col in col_names else 0
        pk_val = vals[pk_idx]
        set_parts = []
        for c, v in zip(col_names, vals):
            if c == pk_col:
                continue
            v_sql = "NULL" if v == "NULL" else (v if v.lstrip("-").replace(".", "").isdigit() else f"'{v}'")
            set_parts.append(f"`{c}` = {v_sql}")
        pk_val_sql = pk_val if pk_val.lstrip("-").replace(".", "").isdigit() else f"'{pk_val}'"
        sql = f"UPDATE `{table_name}` SET {', '.join(set_parts)} WHERE `{pk_col}` = {pk_val_sql};"
        QApplication.clipboard().setText(sql)
        self.log(f"{Icon.char('clipboard')} 已复制行为 UPDATE SQL")

    def _copy_checked_rows_as_insert(self):
        rows = self._get_checked_row_indices()
        if not rows:
            self.log(f"{Icon.char('warning')} 请先勾选行")
        return
        self._copy_rows_as_insert(rows)

    def _copy_checked_rows_as_json(self):
        rows = self._get_checked_row_indices()
        if not rows:
            self.log(f"{Icon.char('warning')} 请先勾选行")
        return
        self._copy_rows_as_json(rows)

    def _copy_checked_rows_as_csv(self):
        rows = self._get_checked_row_indices()
        if not rows:
            self.log(f"{Icon.char('warning')} 请先勾选行")
        return
        csv_text = self._rows_to_csv(rows)
        QApplication.clipboard().setText(csv_text)
        self.log(f"{Icon.char('clipboard')} 已复制 {len(rows)} 行为 CSV")

    # ─── AI 功能 ───────────────────────────
    # ─── SQL 代码片段（Navicat 17 Snippets）───────────────
    # 预置常用 SQL 模板，可通过 AI 工具栏旁的按钮插入编辑器
    _SQL_SNIPPETS = [
        ("SELECT *", "SELECT * FROM `表名` LIMIT 100;"),
        ("WHERE 条件", "WHERE `列名` = '值' AND `列名2` > 0"),
        ("GROUP BY 聚合", "SELECT `列名`, COUNT(*), SUM(`数值列`) FROM `表名`\nGROUP BY `列名`\nORDER BY 2 DESC;"),
        ("JOIN 关联", "SELECT a.*, b.`列名`\nFROM `表A` a\nLEFT JOIN `表B` b ON a.`id` = b.`表A_id`\nWHERE a.`条件列` = '值';"),
        ("INSERT 插入", "INSERT INTO `表名` (`列1`, `列2`, `列3`)\nVALUES ('值1', '值2', '值3');"),
        ("UPDATE 更新", "UPDATE `表名` SET `列1` = '新值', `列2` = 0\nWHERE `id` = 1;"),
        ("DELETE 删除", "DELETE FROM `表名` WHERE `id` = 1;"),
        ("CREATE TABLE", "CREATE TABLE `新表名` (\n  `id` INT NOT NULL AUTO_INCREMENT,\n  `name` VARCHAR(255) NOT NULL,\n  `created_at` DATETIME DEFAULT CURRENT_TIMESTAMP,\n  PRIMARY KEY (`id`)\n);"),
        ("EXPLAIN 执行计划", "EXPLAIN SELECT * FROM `表名` WHERE `列名` = '值';"),
        ("分页查询", "SELECT * FROM `表名`\nWHERE 1=1\nORDER BY `id` DESC\nLIMIT 20 OFFSET 0;"),
        ("日期范围", "WHERE `created_at` BETWEEN '2024-01-01' AND '2024-12-31'"),
        ("CASE WHEN", "SELECT `列名`,\n  CASE\n    WHEN `状态` = 1 THEN '启用'\n    WHEN `状态` = 0 THEN '禁用'\n    ELSE '未知'\n  END AS `状态说明`\nFROM `表名`;"),
    ]

    def _show_snippets_menu(self, btn: "QToolButton"):
        """弹出代码片段选择菜单"""
        menu = QMenu(self)
        menu.setStyleSheet(build_popup_base_style(self._current_theme))
        for name, code in self._SQL_SNIPPETS:
            act = menu.addAction(name)
            _code = code
            act.triggered.connect(lambda checked, c=_code: self._insert_snippet(c))
        menu.exec(btn.mapToGlobal(btn.rect().bottomLeft()))

    def _insert_snippet(self, code: str):
        """将代码片段插入当前 SQL 编辑器（光标位置）"""
        cursor = self.sql_edit.textCursor()
        # 若当前编辑器有内容，先换行再插入
        if self.sql_edit.toPlainText().strip():
            cursor.movePosition(cursor.MoveOperation.End)
        cursor.insertText("\n\n")
        cursor.insertText(code)
        self.sql_edit.setTextCursor(cursor)
        self.sql_edit.setFocus()
        self.log(f"{Icon.char('file_text')} 已插入代码片段")

    # ── SQL 快速选择器（查询 / 表 / 库）─────────────────────────────

    def _on_show_saved_queries_menu(self):
        """显示已保存的查询列表（从 query_manager 加载）"""
        queries = list_queries()
        menu = QMenu(self)
        menu.setStyleSheet(build_popup_base_style(self._tokens))
        if not queries:
            no_item = QAction("暂无保存的查询", menu)
            no_item.setEnabled(False)
            menu.addAction(no_item)
        else:
            for q in queries:
                label = f"{q['name']}  [{q['connection']}/{q['database']}]"
                if q.get("description"):
                    label += f" — {q['description']}"
                act = QAction(label, menu)
                conn = q["connection"]
                db = q["database"]
                name = q["name"]
                act.triggered.connect(
                    lambda _, c=conn, b=db, n=name: self._load_saved_query(c, b, n)
                )
                menu.addAction(act)
        menu.addSeparator()
        act_save = QAction("💾 保存当前查询…", menu)
        act_save.triggered.connect(self._on_save_current_query)
        menu.addAction(act_save)
        menu.exec(self._btn_import_query.mapToGlobal(
        QPoint(0, self._btn_import_query.height())
        ))

    def _load_saved_query(self, conn_name: str, db_name: str, query_name: str):
        """加载指定查询内容到当前编辑器"""
        data = load_query(conn_name, db_name, query_name)
        if data:
            self.sql_edit.setPlainText(data.get("sql", ""))
            self.log(f"加载查询：「{query_name}」")
        else:
            QMessageBox.warning(self, "加载失败", f"无法加载查询「{query_name}」")

    def _on_save_current_query(self):
        """保存当前 SQL 编辑器内容为查询"""
        if not self._current_conn_name:
            QMessageBox.warning(self, "提示", "请先选择一个数据库连接")
        return
        sql = self.sql_edit.toPlainText().strip()
        if not sql:
            QMessageBox.warning(self, "提示", "SQL 内容为空")
        return
        name, ok = QInputDialog.getText(self, "保存查询", "查询名称：")
        if ok and name.strip():
            desc, _ = QInputDialog.getText(self, "保存查询", "描述（可选）：")
        save_query(self._current_conn_name, self._current_db_name, name.strip(), sql, desc.strip())
        self.log(f"查询「{name.strip()}」已保存")

    def _on_show_table_menu(self):
        """显示当前数据库下的表列表"""
        if not self._current_conn_name:
            QMessageBox.information(self, "提示", "请先连接到数据库")
            return
        connector = self._conns.get(self._current_conn_name)
        if not connector:
            return
        menu = QMenu(self)
        menu.setStyleSheet(build_popup_base_style(self._tokens))
        try:
            tables = connector.get_tables(self._current_db_name or "")
        except Exception as e:
            QMessageBox.warning(self, "获取失败", f"无法获取表列表：{e}")
            return
        if not tables:
            no_item = QAction("无表", menu)
            no_item.setEnabled(False)
            menu.addAction(no_item)
        else:
            for t in tables[:200]:
                tname = t if isinstance(t, str) else (t.get("name") or str(t))
                act = QAction(f"📄 {tname}", menu)
                act.triggered.connect(lambda _, n=tname: self._insert_table_name(n))
                menu.addAction(act)
        menu.exec(self._btn_select_table.mapToGlobal(
        QPoint(0, self._btn_select_table.height())
        ))

    def _insert_table_name(self, table_name: str):
        """将表名插入当前光标位置"""
        cursor = self.sql_edit.textCursor()
        cursor.insertText(f"[{table_name}]")
        self.sql_edit.setTextCursor(cursor)
        self.sql_edit.setFocus()

    def _on_show_db_menu(self):
        """显示当前连接的数据库列表"""
        if not self._current_conn_name:
            QMessageBox.information(self, "提示", "请先选择一个连接")
            return
        connector = self._conns.get(self._current_conn_name)
        if not connector:
            return
        menu = QMenu(self)
        menu.setStyleSheet(build_popup_base_style(self._tokens))
        try:
            dbs = connector.get_databases()
        except Exception as e:
            QMessageBox.warning(self, "获取失败", f"无法获取数据库列表：{e}")
            return
        if not dbs:
            no_item = QAction("无数据库", menu)
            no_item.setEnabled(False)
            menu.addAction(no_item)
        else:
            for db in dbs:
                act = QAction(f"🗄 {db}", menu)
                act.triggered.connect(lambda _, d=db: self._switch_database(d))
                menu.addAction(act)
        menu.exec(self._btn_select_db.mapToGlobal(
        QPoint(0, self._btn_select_db.height())
        ))

    def _switch_database(self, db_name: str):
        """切换当前数据库"""
        try:
            connector = self._conns.get(self._current_conn_name)
            if connector:
                connector._db_name = db_name
            self._current_db_name = db_name
            self._refresh_status_badges()
            self.log(f"已切换到数据库：{db_name}")
        except Exception as e:
            QMessageBox.warning(self, "切换失败", str(e))

    def _on_ai_gen(self):
        prompt = self.ai_input.text().strip()
        if not prompt:
            QMessageBox.information(self, "提示", "请先输入自然语言描述需求")
        return
        conn_name = self._current_conn_name
        db_type = self._conn_infos.get(conn_name, {}).get("db_type", "mysql") if conn_name else "mysql"
        schema = self._get_current_schema()
        self.log(f"{Icon.char('loader')} AI 生成 SQL 中…" + ("（已注入表结构）" if schema else "（未连接数据库，无表结构）"))

        # 注入用户消息到右侧对话
        self.ai_chat_widget.inject_user(f"[AI 生成] {prompt}")

        worker = _AIWorker(self.ai.generate_sql, prompt, db_type, schema)

        def _on_gen_done(sql: str):
            self.sql_edit.setPlainText(sql)
            if sql.startswith("--"):
                self.log(f"{Icon.char('error')} {sql}")
                self.ai_chat_widget.inject_assistant(f"{Icon.char('error')} 生成失败：\n{sql}")
            else:
                self.log(f"{Icon.char('success')} AI 生成完成")
                self.ai_chat_widget.inject_assistant(
                    f"{Icon.char('success')} 已生成 SQL（已填入编辑器）：\n\n```sql\n{sql}\n```"
                )

        worker.signals.result.connect(_on_gen_done)
        QThreadPool.globalInstance().start(worker)

    def _on_ai_opt(self):
        sql = self.sql_edit.toPlainText().strip()
        if not sql:
            QMessageBox.information(self, "提示", "SQL 编辑器为空，没有需要优化的内容")
        return
        conn_name = self._current_conn_name
        db_type = self._conn_infos.get(conn_name, {}).get("db_type", "mysql") if conn_name else "mysql"
        schema = self._get_current_schema()
        self.log(f"{Icon.char('loader')} AI 优化 SQL 中…" + ("（已注入表结构）" if schema else "（未连接数据库，无表结构）"))

        # 注入用户消息到右侧对话
        self.ai_chat_widget.inject_user(f"[AI 优化] 请优化以下 SQL：\n\n```sql\n{sql}\n```")

        worker = _AIWorker(self.ai.optimize_sql, sql, db_type, schema)

        def _on_opt_done(opt: str):
            self.sql_edit.setPlainText(opt)
            if opt.startswith("--"):
                self.log(f"{Icon.char('error')} {opt}")
                self.ai_chat_widget.inject_assistant(f"{Icon.char('error')} 优化失败：\n{opt}")
            else:
                self.log(f"{Icon.char('success')} AI 优化完成")
                self.ai_chat_widget.inject_assistant(
                    f"{Icon.char('success')} 已优化 SQL（已填入编辑器）：\n\n```sql\n{opt}\n```"
                )

        worker.signals.result.connect(_on_opt_done)
        QThreadPool.globalInstance().start(worker)

    def _agent_execute_sql(self, sql: str):
        """
        供 Agent 子线程调用的 SQL 执行钩子。
        流程：
        1. 发射 agentSqlSignal(sql) → 主线程收到后把 SQL 注入编辑器并执行
        2. 阻塞等待 _agent_result_queue，主线程把 (cols, rows) 或 Exception 放入队列
        3. 子线程拿到结果后返回给 Agent
        """
        conn_name = self._current_conn_name or (next(iter(self._conns)) if self._conns else None)
        if not conn_name:
            raise RuntimeError("没有可用的数据库连接，请先连接数据库")
        if not self._conns.get(conn_name):
            raise RuntimeError(f"连接 [{conn_name}] 不存在")
        # 清空队列（防止残留）
        while not self._agent_result_queue.empty():
            try:
                self._agent_result_queue.get_nowait()
            except Exception:
                break
        # 发射信号 → 主线程执行
        self.agentSqlSignal.emit(sql)
        # 阻塞等待结果（最多等 60s）
        result = self._agent_result_queue.get(timeout=60)
        if isinstance(result, Exception):
            raise result
        return result   # (cols, rows)

    @Slot(str)
    def _on_agent_sql_request(self, sql: str):
        """
        主线程槽：接收 Agent 发来的 SQL，
        新建标签页 → 执行 → 渲染结果表 → 把结果放回队列
        每条 Agent SQL 都创建独立标签页，不覆盖现有内容。
        """
        # 1. 新建独立标签页，填入 SQL
        agent_tab_count = sum(
        1 for i in range(self._sql_tab_bar.count())
        if self._sql_tab_bar.tabText(i).startswith("Agent-")
            )
        tab_title = f"Agent-{agent_tab_count + 1}"
        self._add_sql_tab(title=tab_title, content=sql)
        # _add_sql_tab 内部已触发 _on_sql_tab_switched，self.sql_edit 已指向新标签

        # 2. 执行
        conn_name = self._current_conn_name or (next(iter(self._conns)) if self._conns else None)
        try:
            connector = self._conns.get(conn_name)
            cols, rows = connector.execute(sql)
            # 3. 刷新结果表格
            self._render_table(cols, rows)
            self.log(f"{Icon.char('robot')} Agent 执行 SQL → 返回 {len(rows)} 行")
            # 4. 把结果放回队列
            self._agent_result_queue.put((cols, rows))
        except Exception as e:
            self.log(f"{Icon.char('error')} Agent SQL 执行失败：{e}")
            self._agent_result_queue.put(e)





    # ─── 菜单动作 ─────────────────────────
    def _open_model_config(self):
        dlg = ModelConfigWindow(self)
        dlg.exec()
        if hasattr(self, "ai_chat_widget"):
            self.ai_chat_widget.refresh_model_config(follow_active=True)


    def _set_log_panel_collapsed(self, collapsed: bool):
        if not hasattr(self, "_work_v_splitter") or not hasattr(self, "_log_panel") or not hasattr(self, "log_box"):
            return

        splitter = self._work_v_splitter
        current_sizes = splitter.sizes()
        total = max(sum(current_sizes), 320)

        if collapsed:
            if len(current_sizes) > 2 and current_sizes[2] > self._log_panel_min_height + 4:
                self._log_panel_last_height = current_sizes[2]
            self.log_box.hide()
            self._log_panel.setMaximumHeight(self._log_panel_min_height)
            if hasattr(self, "_log_toggle_btn"):
                self._log_toggle_btn.setIcon(Icon.svg_icon('收起展开-向上.svg', 14))
            self._log_toggle_btn.setText("展开")

            sql_size = current_sizes[0] if len(current_sizes) > 0 else 188
            data_size = max(total - sql_size - self._log_panel_min_height, 180)
            splitter.setSizes([sql_size, data_size, self._log_panel_min_height])
        else:
            self._log_panel.setMaximumHeight(16777215)
        self.log_box.show()
        if hasattr(self, "_log_toggle_btn"):
            self._log_toggle_btn.setIcon(Icon.svg_icon('收起展开-向下.svg', 14))
        self._log_toggle_btn.setText("最小化")

        target_height = max(self._log_panel_last_height, 96)
        available = max(total - target_height, 240)
        if len(current_sizes) > 1:
            top_total = max(current_sizes[0] + current_sizes[1], 1)
            sql_size = max(120, int(available * current_sizes[0] / top_total))
        else:
            sql_size = max(120, available // 4)
        data_size = max(180, available - sql_size)
        splitter.setSizes([sql_size, data_size, target_height])

        self._log_panel_collapsed = collapsed

    def _toggle_log_panel(self):
        self._set_log_panel_collapsed(not self._log_panel_collapsed)

    def _set_ai_chat_collapsed(self, collapsed: bool):
        if not hasattr(self, "_work_chat_splitter") or not hasattr(self, "ai_chat_widget"):
            return

        splitter = self._work_chat_splitter
        total = max(sum(splitter.sizes()), 900)

        current_sizes = splitter.sizes()
        if collapsed and len(current_sizes) > 1 and current_sizes[1] > 0:
            self._ai_chat_last_width = current_sizes[1]
            self.ai_chat_widget.hide()
            splitter.setSizes([total, 0])
        else:
            self.ai_chat_widget.show()
        chat_width = max(self._ai_chat_last_width, 300)
        splitter.setSizes([max(total - chat_width, 640), chat_width])


        self._ai_chat_collapsed = collapsed

    def _toggle_ai_chat_panel(self):
        self._set_ai_chat_collapsed(not self._ai_chat_collapsed)
        if not self._ai_chat_collapsed and hasattr(self, "ai_chat_widget"):
            self.ai_chat_widget.input_box.setFocus()

    def _open_ai_chat(self):
        """展开并聚焦右侧 AI 对话面板（已嵌入主窗口）"""
        if hasattr(self, "ai_chat_widget"):
            if self._ai_chat_collapsed:
                self._set_ai_chat_collapsed(False)
        self.ai_chat_widget.input_box.setFocus()

    def _on_focus_mode_toggled(self, checked: bool):
        """
        SQL工作台专注模式：隐藏左侧连接面板，聚焦SQL编辑器和AI对话
        """
        if not hasattr(self, "_workspace_splitter"):
            return

        self._focus_mode_active = checked
        splitter = self._workspace_splitter
        current_sizes = splitter.sizes()
        total_width = max(sum(current_sizes), 1600)

        if checked:
            # 进入专注模式：保存当前状态
            if len(current_sizes) > 0:
                self._focus_mode_left_width = current_sizes[0]

            # 隐藏左侧连接面板，展开右侧工作区
            splitter.setSizes([0, total_width])

            # 更新按钮样式
            self._btn_focus.setText(Icon.prefixed_text('fullscreen-exit', "退出专注"))
            self._btn_focus.setToolTip("退出专注模式 (F11)")
            self.log(f"{Icon.char('focus')} SQL专注模式：隐藏左侧连接面板")
        else:
            # 退出专注模式：恢复左侧面板
            left_width = max(self._focus_mode_left_width, 180)
            splitter.setSizes([left_width, total_width - left_width])

            # 更新按钮样式
            self._btn_focus.setText(Icon.prefixed_text('fullscreen', "专注"))
            self._btn_focus.setToolTip("专注模式：隐藏左侧连接面板，聚焦SQL编辑 (F11)")

            self.log(f"{Icon.char('focus')} 已退出SQL专注模式")

    def _on_ai_focus_mode_toggled(self, checked: bool):
        """
        AI对话专注模式：收起SQL工作台，AI对话独占屏幕
        通过 _work_chat_splitter 隐藏左侧SQL工作台
        """
        if not hasattr(self, "_work_chat_splitter"):
            return

        splitter = self._work_chat_splitter
        current_sizes = splitter.sizes()
        total_width = max(sum(current_sizes), 1600)

        if checked:
            # 进入AI专注模式：保存SQL工作台宽度，收起左侧
            if len(current_sizes) > 0:
                self._ai_focus_workbench_width = current_sizes[0]
            # 隐藏SQL工作台，AI对话独占
            splitter.setSizes([0, total_width])
            self.log(f"{Icon.char('focus')} AI专注模式：收起SQL工作台")
        else:
            # 退出AI专注模式：恢复SQL工作台
            wb_width = max(getattr(self, "_ai_focus_workbench_width", 900), 600)
            splitter.setSizes([wb_width, total_width - wb_width])
            self.log(f"{Icon.char('focus')} 已退出AI专注模式")


    def _open_scheduler(self):
        """打开定时任务管理窗口"""
        dlg =         SchedulerWindow(
        parent=self,
        scheduler=self.scheduler,
        conn_names=list(self._conns.keys()),
        conns=self._conns,
        execute_fn=self._scheduler_execute_sql,
        )
        dlg.taskTriggered.connect(self._on_scheduled_task_signal)
        dlg.exec()

    def _scheduler_execute_sql(self, sql: str):
        """定时任务执行 SQL（在调用线程中同步执行）"""
        conn_name = self._current_conn_name or (next(iter(self._conns)) if self._conns else None)
        if not conn_name:
            raise RuntimeError("无可用数据库连接")
        connector = self._conns.get(conn_name)
        if not connector:
            raise RuntimeError(f"连接 [{conn_name}] 不存在")
        return connector.execute(sql)

    def _on_scheduled_task(self, task):
        """调度器回调（可在子线程中调用，只记录日志，不操作 UI）"""
        self.log(f"{Icon.char('schedule')} 定时任务触发：{task.name}")

    def _on_scheduled_task_signal(self, task):
        """来自定时任务窗口的信号（同步/导出/备份类型）"""
        from core.scheduler import TASK_TYPE_BACKUP
        self.log(f"{Icon.char('play')} 手动触发任务：{task.name}（{task.task_type}）")
        if task.task_type == TASK_TYPE_BACKUP:
            self._execute_backup_task(task)

    def _execute_backup_task(self, task):
        """执行定时备份任务"""
        from core.scheduler import TASK_TYPE_BACKUP
        from core.backup_engine import BackupEngine, BackupConfig
        from core.platform_utils import get_default_backup_dir
        import datetime

        if task.task_type != TASK_TYPE_BACKUP:
            return

        conn_name = task.conn_name
        connector = self._conns.get(conn_name)
        if not connector:
            self.log(f"{Icon.char('error')} 备份失败：连接 [{conn_name}] 不存在或未连接")
        return

        bk_cfg = task.backup_cfg or {}
        backup_dir = bk_cfg.get("backup_dir", "") or get_default_backup_dir()
        include_data = bk_cfg.get("include_data", True)

        self.log(f"{Icon.char('archive')} 定时备份开始：{task.db_name} → {backup_dir}")

        engine = BackupEngine()
        cfg = BackupConfig(
        connector=connector,
        db_name=task.db_name or "",
        tables=[],  # 空=全量
        include_data=include_data,
        backup_dir=backup_dir,
        )

        def on_progress(prog):
            self.log(f"  进度：{prog.pct}% {prog.message}")

        try:
            record = engine.backup(cfg, on_progress=on_progress)
            if record:
                self.log(f"{Icon.char('success')} 定时备份完成：{record.file_path}（{record.size_str()}）")
            else:
                self.log(f"{Icon.char('error')} 定时备份失败")
        except Exception as e:
            self.log(f"{Icon.char('error')} 定时备份异常：{e}")

    def _open_sync(self):
        """打开数据同步窗口"""
        dlg = SyncWindow(
        parent=self,
        conns=self._conns,
        conn_infos=self._conn_infos,
        )
        dlg.exec()

    def _open_backup(self):
        """打开数据库备份与恢复窗口"""
        # 只传入已连接的连接器
        connected = {
        name: conn
        for name, conn in self._conns.items()
            if conn is not None
                }
        dlg = BackupWindow(parent=self, connectors=connected)
        dlg.exec()

    def _open_query_manager(self):
        """打开查询管理窗口"""
        from ui.query_manager_window import QueryManagerWindow
        dlg = QueryManagerWindow(
        parent=self,
        conns=self._conns,
        conn_infos=self._conn_infos,
        )
        dlg.queryExecuted.connect(self._on_query_executed_from_manager)
        dlg.exec()

    def _on_query_executed_from_manager(self, query_name: str, cols: list, rows: list):
        """从查询管理器执行查询后，将结果填入结果表格"""
        self._all_cols = cols
        self._all_rows = rows
        self._cur_page = 1
        self._page_offset = 0
        self._show_page(1)
        self.log(f"{Icon.char('database')} 查询「{query_name}」执行完成，返回 {len(rows)} 行")



    def _open_export_import(self):
        """打开导出/导入窗口"""
        conn_name = self._current_conn_name
        connector = self._conns.get(conn_name) if conn_name else None
        # 尝试获取当前选中表名
        current_table = ""
        item = self.tree.currentItem()
        data = item.data(0, Qt.ItemDataRole.UserRole) if item else {}
        if data and data.get("type") == NODE_TABLE:
            current_table = data.get("table_name", "")
        dlg = ExportImportWindow(
        parent=self,
        connector=connector,
        current_table=current_table,
        )
        dlg.exec()

    @staticmethod
    def _parse_chat_history_key(history_key: str) -> tuple[str, str, str]:
        key = (history_key or "").strip()
        if not key or key == DEFAULT_HISTORY_KEY:
            return "", "", ""
        parts = key.split("|", 2)
        conn_name = parts[0] if len(parts) > 0 else ""
        db_name = parts[1] if len(parts) > 1 else ""
        db_type = parts[2] if len(parts) > 2 else ""
        return conn_name, db_name, db_type

    def _build_chat_context(self, conn_name: str = "", db_name: str = "", db_type: str = "") -> dict:
        conn_name = (conn_name or "").strip()
        db_name = (db_name or "").strip()
        info = self._conn_infos.get(conn_name, {}) if conn_name else {}
        resolved_type = (db_type or info.get("db_type") or "mysql").strip() or "mysql"
        label = f"{conn_name} · {db_name}" if conn_name and db_name else (conn_name or db_name or "默认会话")
        return {
        "key": AIChatEngine.make_history_key(conn_name, db_name, resolved_type),
        "label": label,
        "conn_name": conn_name,
        "db_name": db_name,
        "db_type": resolved_type,
        }

    def _list_chat_db_contexts(self):
        contexts = []
        seen = set()

        def add_context(conn_name: str = "", db_name: str = "", db_type: str = ""):
            ctx = self._build_chat_context(conn_name, db_name, db_type)
            if ctx["key"] in seen:
                return
            seen.add(ctx["key"])
            contexts.append(ctx)

        root = self.tree.invisibleRootItem() if hasattr(self, "tree") else None
        if root is not None:
            for i in range(root.childCount()):
                conn_item = root.child(i)
                data = conn_item.data(0, Qt.ItemDataRole.UserRole) or {}
                if data.get("type") != NODE_CONNECTION:
                    continue
                conn_name = data.get("name", "")
                info = self._conn_infos.get(conn_name, {})
                db_type = info.get("db_type", "mysql")
                added_db = False
                for j in range(conn_item.childCount()):
                    db_item = conn_item.child(j)
                    db_data = db_item.data(0, Qt.ItemDataRole.UserRole) or {}
                    if db_data.get("type") != NODE_DATABASE:
                        continue
                    add_context(conn_name, db_data.get("db_name", ""), db_type)
                    added_db = True
                connector = self._conns.get(conn_name)
                fallback_db = getattr(connector, "dbname", "") if connector else info.get("dbname", "")
                if not added_db and (fallback_db or conn_name == self._current_conn_name):
                    add_context(conn_name, fallback_db, db_type)

        current = self._get_current_db_info(None)
        add_context(current.get("conn_name", ""), current.get("db_name", ""), current.get("db_type", "mysql"))
        return contexts

    def _get_current_schema(self, history_key: Optional[str] = None) -> str:
        """获取指定上下文的表结构，失败则返回空字符串"""
        try:
            context = self._get_current_db_info(history_key)
            conn_name = context.get("conn_name", "")
            if not conn_name:
                return ""
            connector = self._conns.get(conn_name)
            if not connector:
                return ""
            db_name = context.get("db_name", "") or None
            return connector.get_schema(db_name) or ""
        except Exception:
            return ""

    def _get_current_db_info(self, history_key: Optional[str] = None):
        """返回 AI 对话当前所需的数据库上下文字典。"""
        if history_key and history_key != DEFAULT_HISTORY_KEY:
            conn_name, db_name, db_type = self._parse_chat_history_key(history_key)
            return self._build_chat_context(conn_name, db_name, db_type)

        conn_name = (self._current_conn_name or "").strip()
        if not conn_name:
            return self._build_chat_context()

        connector = self._conns.get(conn_name)
        info = self._conn_infos.get(conn_name, {})
        db_name = (
        getattr(connector, "dbname", "") if connector else ""
        ) or self._current_db_name or info.get("dbname", "")
        db_type = (getattr(connector, "db_type", "") if connector else "") or info.get("db_type", "mysql")
        ctx = self._build_chat_context(conn_name, db_name, db_type)
        # 注入当前左侧选中表名，供 Agent 精确识别目标表
        if self._current_table_name:
            ctx["selected_table"] = self._current_table_name
        return ctx

    def _list_chat_skill_items(self):
        items = []
        for skill in self.skill_mgr.get_enabled():
            name = (skill.get("name") or "").strip()
            if not name:
                continue
            items.append({
                "name": name,
                "description": (skill.get("description") or "").strip(),
            })
        return items

    def _open_skill_manager(self):
        dlg = SkillManagerWindow(self, self.skill_mgr)
        dlg.skillApplied.connect(self._on_skill_applied)
        dlg.exec()
        if hasattr(self, "ai_chat_widget"):
            self.ai_chat_widget.refresh_skills()

    def _on_skill_applied(self, skill_name: str, skill_content: str):
        """将 Skill 注入 AI 对话系统提示词。"""
        skill_name = (skill_name or "").strip()
        skill_content = (skill_content or "").strip()
        if not skill_name or not skill_content:
            return False
        if hasattr(self, "ai_chat_widget"):
            self.ai_chat_widget.chat_engine.set_system_prompt(
        f"[Skill: {skill_name}]\n{skill_content}"
        )
        self.ai_chat_widget.inject_assistant(
        f"{Icon.char('success')} 已应用 Skill「{skill_name}」，后续对话将遵循此指令。"
        )
        self.log(f"{Icon.char('flag')} Skill 「{skill_name}」已应用")
        return True

    def _on_apply_skill_for_chat(self, skill_names):
        """应用一个或多个 Skill 到 AI 对话。
        
        参数:
        skill_names: 字符串（单个技能名）或列表（多个技能名）
        返回:
        bool: 是否成功应用
        """
        # 统一转换为列表
        if isinstance(skill_names, str):
            skill_names = [skill_names]
        elif not isinstance(skill_names, list):
            return False
        
        # 去除空白并过滤空值
        skill_names = [name.strip() for name in skill_names if name and isinstance(name, str)]
        if not skill_names:
            return False
        
        # 收集所有技能内容
        skill_contents = []
        applied_names = []
        for skill_name in skill_names:
            for skill in self.skill_mgr.get_enabled():
                if (skill.get("name") or "").strip() == skill_name:
                    content = skill.get("content", "").strip()
                    if content:
                        skill_contents.append(content)
                    applied_names.append(skill_name)
                    break
        
        if not skill_contents:
            return False
        
        # 合并内容：每个技能用分隔符隔开，并标注技能名
        if len(skill_contents) == 1:
            combined_content = skill_contents[0]
            display_name = applied_names[0]
        else:
            parts = []
            for name, content in zip(applied_names, skill_contents):
                parts.append(f"[Skill: {name}]\n{content}")
            combined_content = "\n\n---\n\n".join(parts)
            display_name = f"{len(applied_names)}个技能（{', '.join(applied_names)}）"
        
        return self._on_skill_applied(display_name, combined_content)

    def _import_skill(self):
        path, _ = QFileDialog.getOpenFileName(self, "导入Skill", "", "所有文件 (*.*)")
        if path:
            ok, msg = self.skill_mgr.import_skill(path)
            self.log(msg)
            if ok and hasattr(self, "ai_chat_widget"):
                self.ai_chat_widget.refresh_skills()


    def _on_theme_action(self):
        """视图→主题 子菜单触发"""
        action = self.sender()
        if not isinstance(action, QAction):
            return
        theme = action.data()
        if theme == self._current_theme:
            return
        self._apply_theme_refresh(theme)

    def _update_theme_btn_icon(self):
        """根据当前主题更新工具栏主题按钮的图标和提示"""
        if not hasattr(self, 'toolbar_btn_theme'):
            return
        if self._current_theme == THEME_DARK:
            icon_name = 'moon'
            tip = "切换到紫罗兰"
        elif self._current_theme == THEME_WILLOW:
            icon_name = 'leaf'
            tip = "切换到暗色"
        else:
            icon_name = 'sun'
            tip = "切换到柳叶绿"
        self.toolbar_btn_theme.setText(Icon.char(icon_name))
        self.toolbar_btn_theme.setToolTip(tip)

    def _toggle_theme(self):
        """工具栏主题按钮点击：紫罗兰→柳叶绿→暗色 三态循环"""
        _cycle = {THEME_LIGHT: THEME_WILLOW, THEME_WILLOW: THEME_DARK, THEME_DARK: THEME_LIGHT}
        new_theme = _cycle.get(self._current_theme, THEME_LIGHT)
        self._apply_theme_refresh(new_theme)

    def _apply_theme_refresh(self, new_theme: str):
        """统一主题刷新：保存、应用 QSS、刷新所有自定义控件"""
        self._current_theme = new_theme
        self._tokens = get_theme_tokens(new_theme)
        t = self._tokens
        save_theme(new_theme)
        apply_theme(QApplication.instance(), new_theme)
        if hasattr(self, "log_box"):
            self.log_box.setStyleSheet(get_log_box_style(new_theme))
        if hasattr(self, "ai_chat_widget") and self.ai_chat_widget:
            self.ai_chat_widget.refresh_theme()
        self._refresh_status_badges()
        self._update_theme_btn_icon()
        _names = {THEME_LIGHT: "紫罗兰", THEME_WILLOW: "柳叶绿", THEME_DARK: "暗色"}
        self.log(f"主题已切换：{_names.get(new_theme, new_theme)}")
        # 更新表格主题
        table_styles = get_table_style(self._current_theme)
        if hasattr(self, 'table_wrapper') and self.table_wrapper:
            self.table_wrapper.setStyleSheet(table_styles['table_wrapper'])
        if hasattr(self, 'table') and self.table:
            self.table.setStyleSheet(table_styles['table'])
        if hasattr(self, '_checkbox_delegate'):
            self._checkbox_delegate.update_colors(
                table_styles['checkbox']['checked'],
                table_styles['checkbox']['unchecked_bg'],
                table_styles['checkbox']['border'],
                table_styles['checkbox']['checkmark']
            )
        # 同步 SortableTableHeader 表头复选框颜色
        header = self.table.horizontalHeader()
        if hasattr(header, 'update_checkbox_colors'):
            header.update_checkbox_colors(
                table_styles['checkbox']['checked'],
                table_styles['checkbox']['unchecked_bg'],
                table_styles['checkbox']['border'],
                table_styles['checkbox']['checkmark']
            )
        # ── 刷新硬编码颜色控件 ──
        # SQL 徽章
        if hasattr(self, '_sql_badge'):
            self._sql_badge.setStyleSheet(
                f"background:{t['accent_soft']}; color:{t['accent']}; "
                f"border:0px solid {t['accent_hover']}; border-radius:4px; padding:1px 7px; font-size:12px; font-weight:700;"
            )
        # 状态连接标签
        if hasattr(self, '_status_conn'):
            self._status_conn.setStyleSheet(
                f"font-size:11px; color:{t['text_muted']}; "
                f"background:{t['bg']}; border:0px solid {t['border']}; "
                f"border-radius:4px; padding:2px 8px;"
            )
        # AI 输入框容器
        if hasattr(self, 'ai_input'):
            wrap = self.ai_input.parent()
            if wrap:
                wrap.setStyleSheet(
                    f"background:{t['bg']}; border:1px solid {t['border']}; "
                    f"border-radius:6px; padding:0 10px 0 0;"
                )
        # AI 图标
        if hasattr(self, '_ai_input_icon'):
            self._ai_input_icon.setStyleSheet(
                f"background:transparent; color:{t['text_muted']}; border:none; padding:0;"
            )
        # 生成按钮
        if hasattr(self, '_btn_ai_gen'):
            self._btn_ai_gen.setStyleSheet(
                f"QPushButton{{background:{t['accent']}; color:#fff; border:none; "
                f"border-radius:5px; padding:5px 10px; font-size:12px; font-weight:500;}}"
                f"QPushButton:hover{{background:{t['accent_hover']};}}"
                f"QPushButton:pressed{{background:{t['accent_pressed']};}}"
            )
        # 优化按钮
        if hasattr(self, '_btn_ai_opt'):
            self._btn_ai_opt.setStyleSheet(
                f"QPushButton{{background:{t['surface_alt']}; color:{t['text_soft']}; "
                f"border:1px solid {t['border']}; border-radius:5px; padding:5px 10px; font-size:12px;}}"
                f"QPushButton:hover{{background:{t['surface_hover']}; color:{t['text']};}}"
            )
        # 结果信息标签
        if hasattr(self, 'lbl_result_info'):
            self.lbl_result_info.setStyleSheet(
                f"font-size:11px; font-weight:500; color:{t['info']}; "
                f"background:{t['surface_alt']}; border:1px solid {t['border']}; "
                f"border-radius:10px; padding:1px 6px;"
            )
        if hasattr(self, 'lbl_selected_info'):
            self.lbl_selected_info.setStyleSheet(
                f"font-size:10px; color:{t['text_muted']}; background:transparent; border:none; padding:0;"
            )
        # 统计条
        if hasattr(self, '_lbl_stat_bar'):
            self._lbl_stat_bar.setStyleSheet(
                f"color:{t['accent']}; background:{t['accent_soft']}; "
                f"border:1px solid {t['accent_hover']}; border-radius:4px; "
                f"padding:2px 8px; font-size:10px; "
                f"font-family:Consolas,'Cascadia Code',monospace; font-weight:500;"
            )
        # 过滤栏容器
        if hasattr(self, '_filter_container'):
            self._filter_container.setStyleSheet(
                f"QWidget#filterBarContainer{{"
                f"background:{t['bg']}; border:1px solid {t['border']}; "
                f"border-radius:15px;}}"
            )
        # 过滤栏输入框
        if hasattr(self, '_filter_input'):
            self._filter_input.setStyleSheet(
                "QLineEdit{"
                "border:none; background:transparent; "
                "padding:0; margin:0; font-size:13px; "
                f"color:{t['text']}; outline:none;"
                "}"
                "QLineEdit:focus{outline:none;}"
            )
        # 过滤栏下拉框
        if hasattr(self, '_filter_col_combo'):
            self._filter_col_combo.setStyleSheet(
                f"QComboBox{{border:none; background:transparent; font-size:12px; "
                f"color:{t['text_muted']}; padding:0 4px 0 8px; outline:none;}}"
                f"QComboBox:hover{{color:{t['text']};}}"
                f"QComboBox::dropDown{{border:none; background:transparent; width:16px;}}"
                f"QComboBox::down-arrow{{image:none; width:0;}}"
                f"QComboBox QAbstractItemView{{"
                f"background:{t['surface']}; color:{t['text']}; "
                f"border:1px solid {t['border']}; border-radius:6px; "
                f"font-size:12px; padding:4px; selection-background-color:{t['surface_hover']};}}"
            )
        # 过滤栏计数标签
        if hasattr(self, '_filter_count_label'):
            self._filter_count_label.setStyleSheet(
                f"font-size:11px; font-family:Consolas,monospace; "
                f"color:{t['text_muted']}; background:transparent; "
                f"border:none; padding:0px; margin-left:0px;"
            )
        # 刷新 SQL 编辑器
        if hasattr(self, 'sql_edit'):
            self.sql_edit.setStyleSheet(
                f"QTextEdit#sqlEditor{{"
                f"background:{t['surface']}; border:1px solid {t['accent_soft']};; border-top:2px solid {t['accent']}; "
                f"border-top-left-radius: 0px;border-top-right-radius: 0;border-bottom-left-radius: 4px;border-bottom-right-radius: 4px; padding:4px 4px; "
                f"font-family:'Cascadia Code','JetBrains Mono',Consolas,monospace; "
                f"font-size:12px; color:{t['text']}; line-height:1.6;}}"
            )
        # 刷新连接树图标
        if hasattr(self, 'tree'):
            # setForeground 已移除，文字颜色由 QSS 控制（unpolish/polish 后自动更新）
            self.tree.update()
        # 刷新工具栏按钮（_tb 工厂创建时捕获了旧 tokens，需重建 QSS）
        for btn in self.findChildren(QToolButton, "toolbarBtn"):
            tb_style = btn.property("tbStyle") or "view"
            if tb_style == "view":
                btn.setStyleSheet(
                    f"QToolButton#toolbarBtn{{background:transparent; color:{t['info']}; "
                    f"border:none; border-radius:4px; padding:3px 8px; font-size:11px;}}"
                    f"QToolButton#toolbarBtn:hover{{background:{t['surface_hover']}; color:{t['text']};}}"
                )
            elif tb_style == "accent":
                btn.setStyleSheet(
                    f"QToolButton#toolbarBtn{{background:transparent; color:{t['accent']}; "
                    f"border:none; border-radius:4px; padding:3px 8px; font-size:11px;}}"
                    f"QToolButton#toolbarBtn:hover{{background:{t['accent_soft']}; color:{t['accent']};}}"
                )
            elif tb_style == "danger":
                btn.setStyleSheet(
                    f"QToolButton#toolbarBtn{{background:transparent; color:{t['danger']}; "
                    f"border:none; border-radius:4px; padding:3px 8px; font-size:11px;}}"
                    f"QToolButton#toolbarBtn:hover{{background:{t['danger_soft']}; color:{t['danger']};}}"
                )
            elif tb_style == "pin":
                btn.setStyleSheet(
                    f"QToolButton#toolbarBtn{{background:transparent; color:{t['info']}; "
                    f"border:none; border-radius:4px; padding:3px 8px; font-size:11px;}}"
                    f"QToolButton#toolbarBtn:hover{{background:{t['surface_hover']}; color:{t['text']};}}"
                    f"QToolButton#toolbarBtn:checked{{background:{t['warning_soft']}; color:{t['warning']};}}"
                )
        # 刷新表头 viewport 以确保复选框正确重绘
        if hasattr(self, 'table') and self.table:
            self.table.horizontalHeader().viewport().update()
            self.table.viewport().update()
            # 强制表格整体重绘（确保 CheckBoxDelegate 用更新后的颜色重画）
            self.table.repaint()


    # ─── 图标工厂 ──────────────────────────
    @staticmethod
    def _resolve_icon_path() -> str:
        """获取 icon.ico 的绝对路径，兼容打包和开发模式"""
        from core.platform_utils import get_icon_path
        p = get_icon_path()
        return p if os.path.exists(p) else ""

    @staticmethod
    def _conn_type_meta(db_type: str, is_spatial: bool = False):
        db_type = (db_type or "").lower()
        mapping = {
        "mysql": {"label": "MySQL", "code": "MY", "bg": "#2f80ed", "fg": "#ffffff"},
        "postgresql": {"label": "PostgreSQL", "code": "PG", "bg": "#336791", "fg": "#ffffff"},
        "sqlserver": {"label": "SQL Server", "code": "MS", "bg": "#cc2927", "fg": "#ffffff"},
        "oracle": {"label": "Oracle", "code": "OR", "bg": "#f04e3e", "fg": "#ffffff"},
        "xugu": {"label": "虚谷 XuguDB", "code": "XG", "bg": "#7c2d12", "fg": "#ffffff"},
        "dameng": {"label": "达梦", "code": "DM", "bg": "#6f42c1", "fg": "#ffffff"},
        "kingbase": {"label": "人大金仓", "code": "KB", "bg": "#0f766e", "fg": "#ffffff"},
        "gaussdb": {"label": "GaussDB", "code": "GS", "bg": "#2563eb", "fg": "#ffffff"},
        "opengauss": {"label": "openGauss", "code": "OG", "bg": "#4f46e5", "fg": "#ffffff"},

        "oceanbase": {"label": "OceanBase", "code": "OB", "bg": "#16a34a", "fg": "#ffffff"},
        "polardb": {"label": "PolarDB", "code": "PD", "bg": "#0891b2", "fg": "#ffffff"},
        "tdsql": {"label": "TDSQL", "code": "TD", "bg": "#059669", "fg": "#ffffff"},
        "gbase": {"label": "GBase", "code": "GB", "bg": "#d97706", "fg": "#ffffff"},
        "tidb": {"label": "TiDB", "code": "TI", "bg": "#334155", "fg": "#ffffff"},
        "shentong": {"label": "神通", "code": "ST", "bg": "#64748b", "fg": "#ffffff"},
        "argodb": {"label": "ArgoDB", "code": "AR", "bg": "#7c3aed", "fg": "#ffffff"},
        "inceptor": {"label": "Inceptor", "code": "IN", "bg": "#ea580c", "fg": "#ffffff"},
        }
        meta = mapping.get(db_type, {
        "label": db_type.upper() if db_type else "数据库",
        "code": (db_type[:2] if db_type else "DB").upper(),
        "bg": "#475569",
        "fg": "#ffffff",
        }).copy()
        if db_type == "argodb" and is_spatial:
            meta["label"] = "ArgoDB Spatial"
        meta["code"] = "GIS"
        meta["bg"] = "#0f766e"
        return meta

    @staticmethod
    def _conn_type_icon(db_type: str, connected: bool, is_spatial: bool = False,
        starred: bool = False, color_key: str = ""):
        """Navicat 风格连接图标：左侧色条 + 数据库类型 + 状态灯 + 星标"""
        meta = MainWindow._conn_type_meta(db_type, is_spatial=is_spatial)
        pix = QPixmap(20, 16)
        pix.fill(Qt.GlobalColor.transparent)

        painter = QPainter(pix)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        x_off = 0

        # 1) 左侧颜色条（如果有颜色标记）
        _COLORS = {
        "red": ("#e53e3e", ""), "orange": ("#ed8936", ""), "yellow": ("#d69e2e", ""),
        "green": ("#38a169", ""), "teal": ("#319795", ""), "blue": ("#3182ce", ""),
        "purple": ("#805ad5", ""), "gray": ("#718096", ""),
        }
        if color_key and color_key in _COLORS:
            hex_c = _COLORS[color_key][0]
        else:
            hex_c = "#94a3b8"
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(hex_c))
        painter.drawRoundedRect(x_off, 1, 3, 14, 1, 1)
        x_off += 4

        # 2) 数据库类型小徽章
        badge_color = QColor(meta["bg"])
        if not connected:
            badge_color.setAlpha(100)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(badge_color)
        painter.drawRoundedRect(x_off + 1, 2, 10, 12, 2, 2)

        # 徽章文字
        text_color = QColor(meta["fg"])
        if not connected:
            text_color.setAlpha(180)
        font = QFont("Segoe UI", 6, QFont.Weight.Bold)
        if len(meta["code"]) >= 3:
            font.setPointSize(5)
        painter.setFont(font)
        painter.setPen(text_color)
        painter.drawText(QRect(x_off + 1, 2, 10, 12), Qt.AlignmentFlag.AlignCenter, meta["code"])

        # 3) 状态指示灯
        _ct = get_theme_tokens(load_theme())
        status_color = QColor(_ct.get("success", "#22c55e") if connected else _ct.get("text_muted", "#94a3b8"))
        painter.setPen(QPen(QColor(_ct.get("surface", "#ffffff")), 0.5))
        painter.setBrush(status_color)
        painter.drawEllipse(x_off + 10, 8, 6, 6)

        # 4) 星标（右上角小黄点）
        if starred:
            painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(_ct.get("warning", "#f59e0b")))
        painter.drawEllipse(x_off + 10, 0, 5, 5)

        painter.end()
        return QIcon(pix)

    @staticmethod
    def _group_icon(kind: str) -> QIcon:
        """Navicat 风格分组图标：表=网格，视图=眼睛，函数=fx"""
        tokens = get_theme_tokens(load_theme())
        pix = QPixmap(16, 16)
        pix.fill(Qt.GlobalColor.transparent)
        p = QPainter(pix)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        if kind == "tables":
            # 表格网格图标
            p.setBrush(QColor(tokens["accent_soft"]))
            p.setPen(QPen(QColor(tokens["accent"]), 1))
            p.drawRect(1, 1, 14, 14)
            p.setPen(QPen(QColor(tokens["accent"]), 0.5))
            p.drawLine(1, 6, 15, 6)
            p.drawLine(1, 11, 15, 11)
            p.drawLine(6, 1, 6, 15)
            p.drawLine(11, 1, 11, 15)
        elif kind == "views":
            # 眼睛图标
            p.setPen(QPen(QColor(tokens["success"]), 1.2))
            p.setBrush(QColor(tokens["success_soft"]))
            p.drawEllipse(1, 4, 14, 8)
            p.setBrush(QColor(tokens["success"]))
            p.drawEllipse(5, 6, 6, 4)
        elif kind == "indexes":
            # 钥匙图标
            p.setBrush(QColor(tokens["accent_soft"]))
            p.setPen(QPen(QColor(tokens["accent"]), 1.2))
            p.drawEllipse(2, 2, 7, 7)
            p.setBrush(QColor(tokens["accent"]))
            p.setPen(QPen(QColor(tokens["accent"]), 1))
            p.drawRect(7, 4, 6, 3)
            p.drawRect(10, 7, 2, 2)
            p.drawRect(7, 7, 2, 2)
        elif kind == "procedures":
            # 齿轮图标
            p.setBrush(QColor(tokens["accent_soft"]))
            p.setPen(QPen(QColor(tokens["accent"]), 1.2))
            p.drawEllipse(3, 3, 10, 10)
            p.setBrush(QColor(tokens["surface"] if "surface" in tokens else "#1e1e1e"))
            p.drawEllipse(6, 6, 4, 4)
        else:
            # fx 图标
            p.setBrush(QColor(tokens["warning_soft"]))
            p.setPen(QPen(QColor(tokens["warning"]), 1))
            p.drawRoundedRect(1, 1, 14, 14, 2, 2)
            p.setPen(QColor(tokens["warning"]))
        font = QFont("Arial", 7, QFont.Weight.Bold)
        p.setFont(font)
        p.drawText(QRect(1, 2, 14, 12), Qt.AlignmentFlag.AlignCenter, "fx")
        p.end()
        return QIcon(pix)

    def _db_icon(self):
        """数据库图标 - 使用主题色"""
        tokens = self._tokens if hasattr(self, '_tokens') else get_theme_tokens(load_theme())
        pix = QPixmap(16, 16)
        pix.fill(Qt.GlobalColor.transparent)
        p = QPainter(pix)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        # 数据库圆柱形（简化）- 使用主题强调色
        p.setBrush(QColor(tokens["accent"]))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(1, 1, 14, 5)
        p.drawRect(1, 4, 14, 8)
        p.setBrush(QColor(tokens["accent_pressed"]))
        p.drawEllipse(1, 8, 14, 5)
        p.end()
        return QIcon(pix)

    def _table_icon(self):
        """表格图标 - 使用主题色"""
        tokens = self._tokens if hasattr(self, '_tokens') else get_theme_tokens(load_theme())
        pix = QPixmap(16, 16)
        pix.fill(Qt.GlobalColor.transparent)
        p = QPainter(pix)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        # 简单表格图标
        p.setPen(QColor(tokens["text_muted"]))
        p.setBrush(QColor(tokens["accent_soft"]))
        p.drawRect(1, 1, 14, 14)
        p.setPen(QColor(tokens["border_strong"]))
        p.drawLine(1, 5, 15, 5)
        p.drawLine(1, 9, 15, 9)
        p.drawLine(6, 1, 6, 15)
        p.drawLine(11, 1, 11, 15)
        p.end()
        return QIcon(pix)

    def _view_icon(self):
        """视图图标（眼睛形状简化版）- 使用主题色"""
        tokens = self._tokens if hasattr(self, '_tokens') else get_theme_tokens(load_theme())
        pix = QPixmap(16, 16)
        pix.fill(Qt.GlobalColor.transparent)
        p = QPainter(pix)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setPen(QPen(QColor(tokens["success"]), 1))
        p.setBrush(QColor(tokens["success_soft"]))
        p.drawEllipse(1, 1, 14, 14)
        p.setPen(QPen(QColor(tokens["success"]), 1))
        p.setBrush(QColor(tokens["success"]))
        p.drawEllipse(5, 5, 6, 6)
        p.end()
        return QIcon(pix)

    def _func_icon(self):
        """函数图标（fx 文字简化）- 使用主题色"""
        tokens = self._tokens if hasattr(self, '_tokens') else get_theme_tokens(load_theme())
        pix = QPixmap(16, 16)
        pix.fill(Qt.GlobalColor.transparent)
        p = QPainter(pix)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setBrush(QColor(tokens["warning_soft"]))
        p.setPen(QPen(QColor(tokens["warning"]), 1))
        p.drawRoundedRect(1, 1, 14, 14, 2, 2)
        p.setPen(QColor(tokens["warning"]))
        font = QFont("Arial", 7, QFont.Weight.Bold)
        p.setFont(font)
        p.drawText(QRect(1, 2, 14, 12), Qt.AlignmentFlag.AlignCenter, "fx")
        p.end()
        return QIcon(pix)

    def _index_icon(self):
        """索引图标（钥匙形状简化）- 使用主题色"""
        tokens = self._tokens if hasattr(self, '_tokens') else get_theme_tokens(load_theme())
        pix = QPixmap(16, 16)
        pix.fill(Qt.GlobalColor.transparent)
        p = QPainter(pix)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        # 钥匙环（圆形）
        p.setBrush(QColor(tokens["accent_soft"]))
        p.setPen(QPen(QColor(tokens["accent"]), 1.2))
        p.drawEllipse(2, 2, 7, 7)
        # 钥匙杆
        p.setBrush(QColor(tokens["accent"]))
        p.setPen(QPen(QColor(tokens["accent"]), 1))
        p.drawRect(7, 4, 6, 3)
        # 钥匙齿
        p.drawRect(10, 7, 2, 2)
        p.drawRect(7, 7, 2, 2)
        p.end()
        return QIcon(pix)

    def _proc_icon(self):
        """存储过程图标（齿轮形状简化）- 使用主题色"""
        tokens = self._tokens if hasattr(self, '_tokens') else get_theme_tokens(load_theme())
        pix = QPixmap(16, 16)
        pix.fill(Qt.GlobalColor.transparent)
        p = QPainter(pix)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        # 圆形齿轮
        p.setBrush(QColor(tokens["accent_soft"]))
        p.setPen(QPen(QColor(tokens["accent"]), 1.2))
        p.drawEllipse(3, 3, 10, 10)
        # 中心孔
        p.setBrush(QColor(tokens["surface"] if "surface" in tokens else "#1e1e1e"))
        p.drawEllipse(6, 6, 4, 4)
        # 齿（简化为4个小矩形）
        for angle in range(0, 360, 45):
            rad = math.radians(angle)
            cx, cy = 8 + 6 * math.cos(rad), 8 + 6 * math.sin(rad)
            p.setBrush(QColor(tokens["accent"]))
            p.drawRect(int(cx) - 1, int(cy) - 1, 2, 2)
        p.end()
        return QIcon(pix)


    def _show_user_guide(self):
        """显示使用说明对话框。"""
        tokens = get_theme_tokens(self._current_theme)
        dlg = QDialog(self)
        dlg.setWindowTitle(f"{APP_FULL_NAME} 使用说明")
        dlg.resize(900, 680)
        dlg.setMinimumSize(760, 560)
        dlg.setStyleSheet(
        f"QDialog{{background:{tokens['surface']};color:{tokens['text']};}}"
        f"QTextBrowser{{background:{tokens['surface']};color:{tokens['text']};"
        f"border:1px solid {tokens['border']};border-radius: 2px;padding:8px;selection-background-color:{tokens['selection_bg']};}}"
        f"QPushButton{{background:{tokens['surface_muted']};color:{tokens['text']};"
        f"border:none;border-radius: 4px;padding:6px 14px;}}"
        f"QPushButton:hover{{border-color:{tokens['accent']};background:{tokens['accent_soft']};}}"
        )

        layout = QVBoxLayout(dlg)
        layout.setContentsMargins(18, 18, 18, 14)
        layout.setSpacing(12)

        browser = QTextBrowser()
        browser.setOpenExternalLinks(True)
        browser.document().setDefaultStyleSheet(
        f"body{{font-family:'Microsoft YaHei UI','Segoe UI',sans-serif;line-height:1.75;color:{tokens['text']};}}"
        f"h1{{font-size:26px;color:{tokens['text']};margin:0 0 8px 0;}}"
        f"h2{{font-size:18px;color:{tokens['accent']};margin:18px 0 8px 0;}}"
        f"h3{{font-size:15px;color:{tokens['text_soft']};margin:14px 0 6px 0;}}"
        f"p,li{{font-size:13px;color:{tokens['text']};}}"
        f"ul{{margin-top:4px;}}"
        f"code{{background:{tokens['code_bg']};padding:1px 4px;border-radius: 2px;}}"
        f"blockquote{{margin:10px 0;padding:8px 12px;border-left:3px solid {tokens['accent']};background:{tokens['surface_alt']};color:{tokens['text_soft']};}}"
        f"table{{border-collapse:collapse;width:100%;margin:8px 0 14px 0;}}"
        f"th,td{{border:1px solid {tokens['border']};padding:6px 8px;text-align:left;}}"
        f"th{{background:{tokens['surface_muted']};}}"
        f"a{{color:{tokens['accent']};text-decoration:none;}}"
        )
        browser.setHtml(
        f"""
        <h1>{APP_FULL_NAME} 使用说明</h1>
        <p>版本：v{VERSION}。这是一份面向日常使用的快速指南，覆盖连接管理、SQL 执行、结果表格、AI 对话、导入导出和常见操作入口。</p>
        <blockquote>建议先完成一次数据库连接，再开始查询、表设计、AI 问答或导入导出操作。</blockquote>

        <h2>1. 快速开始</h2>
        <ul>
        <li>左侧连接树中右键空白区域，可新建连接或导入 Navicat 连接。</li>
        <li>双击连接节点或右键“打开连接”，会建立连接并加载数据库列表。</li>
        <li>展开数据库后，可看到 <code>表</code>、<code>视图</code>、<code>函数</code> 三个分组。</li>
        <li>点击工具栏或右键菜单中的“新建查询”，可快速把当前连接切到 SQL 工作区。</li>
        </ul>

        <h2>2. 连接与数据库浏览</h2>
        <table>
        <tr><th>入口</th><th>作用</th></tr>
        <tr><td>连接节点右键</td><td>打开/关闭连接、编辑连接、复制连接、重命名、删除、刷新</td></tr>
        <tr><td>数据库节点右键</td><td>新建查询、导出数据库说明文档、刷新结构</td></tr>
        <tr><td>表节点右键</td><td>打开表、设计表、属性、新建表、删除表、清空表、复制表、导入导出、转储 SQL</td></tr>
        <tr><td>视图节点右键</td><td>查看数据、查看/修改 DDL、创建视图、删除视图</td></tr>
        <tr><td>函数节点右键</td><td>复制函数名、生成调用语句</td></tr>
        </table>
        <p>如果连接里配置了默认数据库，连接后会优先定位到该库；右侧 AI 对话也会同步更新可选数据库上下文。</p>

        <h2>3. SQL 工作区</h2>
        <ul>
        <li>中部是 SQL 编辑器，可直接输入多条 SQL。</li>
        <li>执行后，下方结果区会展示列名、数据和分页信息。</li>
        <li>页码支持直接输入，回车后跳转；也可以用首页、上一页、下一页、末页按钮。</li>
        <li>日志面板已改成可折叠区域，适合在查询时保留更多结果空间。</li>
        </ul>

        <h2>4. 结果表格</h2>
        <ul>
        <li>点击表头可三态排序：升序 → 降序 → 恢复原序。</li>
        <li>点击表头可选中整列；支持 Ctrl 多选、Shift 范围选中。</li>
        <li>工具条中可执行复制、导出、筛选等相关操作。</li>
        </ul>

        <h2>5. AI 对话与 SQL 辅助</h2>
        <ul>
        <li>右侧 AI 面板可以折叠/展开，不影响主工作区。</li>
        <li>AI 会结合当前数据库结构进行问答、SQL 生成和解释。</li>
        <li>聊天历史按“连接名 + 数据库名 + 数据库类型”分组保存，切换上下文时可查看对应历史。</li>
        <li>已启用的 Skill 可直接在聊天面板引用，扩展 AI 的行为。</li>
        </ul>

        <h2>6. 导入 / 导出 / 文档</h2>
        <ul>
        <li>表节点支持打开导入向导和导出向导，当前表会自动带入。</li>
        <li>数据库节点支持“导出数据库说明文档”，会导出 Markdown 格式的结构说明。</li>
        <li>表节点支持“转储 SQL 文件”，可导出表结构与数据 INSERT 语句。</li>
        </ul>

        <h2>7. 主题与界面</h2>
        <ul>
        <li>视图菜单支持紫罗兰、柳叶绿和暗色三种主题。</li>
        <li>当前连接状态、主题状态会显示在 SQL 区标题栏右侧。</li>
        <li>应用名称已统一为“团子”，图标会同步用于窗口和任务栏。</li>
        </ul>

        <h2>8. 常见建议</h2>
        <ul>
        <li>首次连接失败时，优先检查主机、端口、实例名、用户名、密码和默认库。</li>
        <li>SQL Server 在 Windows 下依赖 ODBC Driver，若系统已装驱动但仍报错，重点检查连接参数是否写对。</li>
        <li>做高风险操作前，建议先通过“新建查询”确认目标库，再执行删除、清空、DDL 变更等操作。</li>
        </ul>

        <h2>9. 支持数据库</h2>
        <p>当前版本面向多数据库场景，覆盖 MySQL、PostgreSQL、SQL Server、Oracle，以及部分国产/兼容数据库与星环场景。</p>
        """
        )
        layout.addWidget(browser, 1)

        btn_close = QPushButton("关闭")
        btn_close.setFixedWidth(88)
        btn_close.clicked.connect(dlg.accept)
        footer = QHBoxLayout()
        footer.addStretch()
        footer.addWidget(btn_close)
        layout.addLayout(footer)

        dlg.exec()

    def _set_config_dir(self):
        """设置配置文件保存目录"""
        current_dir = load_config_dir()
        default_path = get_config_path()

        dlg = QDialog(self)
        dlg.setWindowTitle("配置文件目录设置")
        dlg.setMinimumWidth(520)

        layout = QVBoxLayout(dlg)
        layout.setSpacing(12)

        # 说明
        info_label = QLabel(
        "设置 connections.json 等配置文件的保存目录。<br>"
        "留空则使用程序默认目录。"
        )
        info_label.setWordWrap(True)
        info_label.setStyleSheet(f"color: {self._tokens['text_soft']}; font-size: 13px;")
        layout.addWidget(info_label)

        # 当前配置
        current_label = QLabel(f"当前配置目录：<b>{current_dir if current_dir else '（默认）'}</b>")
        current_label.setStyleSheet(f"color: {self._tokens['text_muted']}; font-size: 12px;")
        layout.addWidget(current_label)

        # 默认路径说明
        default_label = QLabel(f"默认路径：{default_path}")
        default_label.setStyleSheet(f"color: {self._tokens['text_muted']}; font-size: 11px;")
        default_label.setWordWrap(True)
        layout.addWidget(default_label)

        # 路径选择区
        path_layout = QHBoxLayout()
        self._config_dir_input = QLineEdit()
        self._config_dir_input.setPlaceholderText("选择配置文件保存目录…")
        self._config_dir_input.setText(current_dir)
        self._config_dir_input.setReadOnly(True)
        path_layout.addWidget(self._config_dir_input, 1)

        browse_btn = QPushButton("浏览…")
        browse_btn.setFixedWidth(70)
        browse_btn.clicked.connect(self._browse_config_dir)
        path_layout.addWidget(browse_btn)
        layout.addLayout(path_layout)

        # 提示
        tip_label = QLabel(
        "💡 提示：修改目录后，新的连接配置会保存到新位置。<br>"
        "   原有连接不会自动移动，如需迁移请手动复制文件。"
        )
        tip_label.setStyleSheet(f"color: {self._tokens['text_muted']}; font-size: 12px; background: {self._tokens['surface_alt']}; "
        "padding: 8px; border-radius: 2px;")
        tip_label.setWordWrap(True)
        layout.addWidget(tip_label)

        # 按钮行
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        clear_btn = QPushButton("恢复默认")
        clear_btn.clicked.connect(lambda: self._config_dir_input.setText(""))
        btn_layout.addWidget(clear_btn)

        cancel_btn = QPushButton("取消")
        cancel_btn.clicked.connect(dlg.reject)
        btn_layout.addWidget(cancel_btn)

        save_btn = QPushButton("保存")
        save_btn.setDefault(True)
        save_btn.clicked.connect(lambda: self._save_config_dir(dlg))
        btn_layout.addWidget(save_btn)
        layout.addLayout(btn_layout)

        dlg.exec()

    def _browse_config_dir(self):
        """打开目录选择对话框"""
        dir_path = QFileDialog.getExistingDirectory(
        self,
        "选择配置文件保存目录",
        os.path.expanduser("~"),
        QFileDialog.Option.ShowDirsOnly
        )
        if dir_path:
            self._config_dir_input.setText(dir_path)

    def _save_config_dir(self, dlg: QDialog):
        """保存配置文件目录"""
        new_dir = self._config_dir_input.text().strip()
        save_config_dir(new_dir)

        # 更新状态栏显示
        self._update_config_path_label()

        QMessageBox.information(self, "已保存", f"配置文件目录已设置。\n\n{get_config_path()}")
        dlg.accept()

    def _show_about(self):
        """显示「关于」对话框"""
        dlg = QDialog(self)
        dlg.setWindowTitle(f"关于 {APP_FULL_NAME}")
        dlg.setMinimumWidth(480)
        dlg.setMaximumWidth(560)

        layout = QVBoxLayout(dlg)
        layout.setContentsMargins(24, 20, 24, 16)
        layout.setSpacing(0)

        # 图标 + 正文横排
        top_row = QHBoxLayout()
        top_row.setSpacing(16)

        # 应用图标
        icon_lbl = QLabel()
        icon_lbl.setFixedSize(64, 64)
        icon_path = self._resolve_icon_path()
        if icon_path:
            pix = QPixmap(icon_path).scaled(
                64, 64, Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )
            icon_lbl.setPixmap(pix)
        else:
            icon_lbl.setText(Icon.char('database'))
        icon_lbl.setFont(Icon.font(40))
        icon_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        top_row.addWidget(icon_lbl, 0, Qt.AlignmentFlag.AlignTop)

        # 富文本内容
        lbl = QLabel()
        lbl.setTextFormat(Qt.TextFormat.RichText)
        lbl.setText(get_about_text())
        lbl.setOpenExternalLinks(True)
        lbl.setWordWrap(True)
        top_row.addWidget(lbl, 1)

        layout.addLayout(top_row)
        layout.addSpacing(12)

        # 关闭按钮
        btn_close = QPushButton("关闭")
        btn_close.setFixedWidth(80)
        btn_close.clicked.connect(dlg.accept)
        h = QHBoxLayout()
        h.addStretch()
        h.addWidget(btn_close)
        layout.addLayout(h)

        dlg.exec()

    # ─── 日志 ─────────────────────────────
    def log(self, msg: str):
        ts = datetime.datetime.now().strftime("%H:%M:%S")
        # 自动给 PUA 字符（图标字符）包裹 font-family span，确保图标正确渲染
        from ui.iconfont_loader import wrap_pua
        self.log_box.append(f"<span style='color:{self._tokens['text_muted']}'>[{ts}]</span> {wrap_pua(msg)}")

    # ─── 兼容旧接口（on_connect 等）──────
    def on_connect(self):
        self._on_new_conn()