"""
skill_manager_window.py
Skill 管理与应用窗口
- 支持导入、新建、编辑、删除、启用/禁用、排序
- 支持快捷键绑定
- 支持直接「应用 Skill」到 AI 对话（将 Skill 内容作为系统提示词注入）
"""
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QListWidget, QListWidgetItem,
    QPushButton, QLabel, QTextEdit, QLineEdit, QComboBox, QCheckBox,
    QSplitter, QWidget, QMessageBox, QFileDialog, QFormLayout,
    QGroupBox, QFrame, QSizePolicy, QDialogButtonBox, QMenu,
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont, QIcon, QColor

from core.skill_manager import SkillManager
from ui.iconfont_loader import Icon
from ui.theme_manager import (
    load_theme, THEME_DARK, THEME_AUTO, _is_system_dark,
    get_theme_tokens, build_popup_base_style, build_dialog_frame,
    build_frameless_dialog_style,
    make_frameless_title_bar,
)



def _is_dark_now() -> bool:
    t = load_theme()
    if t == THEME_AUTO:
        return _is_system_dark()
    return t == THEME_DARK


# ── Skill 编辑对话框 ────────────────────────────────────────────────────────
class _SkillEditDialog(QDialog):
    def __init__(self, parent=None, skill: dict = None):
        super().__init__(parent)
        # 无边框窗口设置
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self._skill = skill or {}
        self._is_new = not skill
        self.setWindowTitle("新建 Skill" if self._is_new else "编辑 Skill")
        self.setMinimumSize(680, 520)
        self._theme = load_theme()
        self._tokens = get_theme_tokens(self._theme)
        # 先创建标题栏（必须在 _build_ui 之前）
        title_text = "新建 Skill" if self._is_new else "编辑 Skill"
        self._title_bar, self._title_lbl, self._title_close_btn = make_frameless_title_bar(
            self, title_text, self._tokens)
        self._title_close_btn.clicked.connect(self.reject)
        self._build_ui()
        self._apply_theme()

    def _apply_theme(self):
        """应用主题到编辑对话框的各个组件。"""
        t = self._tokens
        accent = t.get("accent", "#3b82f6")
        accent_soft = t.get("accent_soft", "#dbeafe")
        surface = t.get("surface", "#ffffff")
        surface_alt = t.get("surface_alt", "#f3f4f6")
        border = t.get("border", "#d1d5db")
        text = t.get("text", "#1f2937")
        scroll_handle = t.get("scroll_handle", "#bcc8d9")
        scroll_handle_hover = t.get("scroll_handle_hover", "#8b9bb0")

        # QLineEdit 样式
        edit_style = (
            f"QLineEdit{{background:{surface_alt}; border:1px solid {border}; border-radius: 2px; padding:6px 10px; color:{text}; font-size:13px;}}"
            f"QLineEdit:focus{{border-color:{accent}; background:{surface};}}"
            f"QLineEdit{{selection-background-color:{accent_soft}; selection-color:{accent};}}"
            f"QLineEdit:disabled{{background:{surface_alt}; color:#9ca3af;}}"
        )
        for attr in ("txt_name", "txt_desc", "txt_hotkey"):
            w = getattr(self, attr, None)
            if w is not None:
                w.setStyleSheet(edit_style)

        # QComboBox 样式
        combo_style = (
            f"QComboBox{{background:{surface_alt}; border:1px solid {border}; border-radius: 2px; padding:5px 10px; color:{text}; font-size:13px;}}"
            f"QComboBox:hover{{border-color:{accent};}}"
            f"QComboBox:focus{{border-color:{accent}; background:{surface};}}"
            f"QComboBox::drop-down{{border:none; width:20px;}}"
            f"QComboBox QAbstractItemView{{background:{surface}; color:{text}; selection-background-color:{accent_soft}; selection-color:{accent}; border:none; border-radius: 2px; padding:2px;}}"
        )
        if hasattr(self, "cmb_category"):
            self.cmb_category.setStyleSheet(combo_style)

        # QTextEdit 样式
        textedit_style = (
            f"QTextEdit{{background:{surface_alt}; border:1px solid {border}; border-radius: 2px; color:{text}; font-size:12px; padding:8px; font-family:Consolas,monospace;}}"
            f"QTextEdit:focus{{border-color:{accent}; background:{surface};}}"
            f"QTextEdit{{selection-background-color:{accent_soft}; selection-color:{accent};}}"
            f"QScrollBar:vertical{{background:transparent; width:6px; margin:4px 0; border:none;}}"
            f"QScrollBar::handle:vertical{{background:{scroll_handle}; border-radius: 2px; min-height:30px;}}"
            f"QScrollBar::handle:vertical:hover{{background:{scroll_handle_hover};}}"
            f"QScrollBar::handle:vertical:pressed{{background:{accent};}}"
            f"QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical{{height:0; width:0;}}"
            f"QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical{{background:transparent;}}"
        )
        if hasattr(self, "txt_content"):
            self.txt_content.setStyleSheet(textedit_style)


    def _build_ui(self):
        frame, frame_layout, inner = build_dialog_frame(self._tokens, self, self._title_bar)
        inner_layout = QVBoxLayout(inner)
        inner_layout.setContentsMargins(16, 12, 16, 12)
        inner_layout.setSpacing(10)

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        form.setSpacing(8)

        self.txt_name = QLineEdit(self._skill.get("name", ""))
        self.txt_name.setPlaceholderText("Skill 名称（必填）")
        form.addRow("名称 *:", self.txt_name)

        self.txt_desc = QLineEdit(self._skill.get("description", ""))
        self.txt_desc.setPlaceholderText("简短描述（可选）")
        form.addRow("描述:", self.txt_desc)

        self.cmb_category = QComboBox()
        self.cmb_category.setEditable(True)
        categories = ["通用", "SQL优化", "数据分析", "报表生成", "数据清洗", "其他"]
        self.cmb_category.addItems(categories)
        cur = self._skill.get("category", "通用")
        if cur not in categories:
            self.cmb_category.addItem(cur)
        self.cmb_category.setCurrentText(cur)
        form.addRow("分类:", self.cmb_category)

        self.txt_hotkey = QLineEdit(self._skill.get("hotkey", ""))
        self.txt_hotkey.setPlaceholderText("例如：/sql  /report（输入时触发，可留空）")
        self.txt_hotkey.setMaximumWidth(200)
        form.addRow("快捷触发词:", self.txt_hotkey)

        inner_layout.addLayout(form)

        lbl_content = QLabel("Skill 内容（提示词 / 模板）:")
        lbl_content.setProperty("role", "title")

        inner_layout.addWidget(lbl_content)

        self.txt_content = QTextEdit()
        self.txt_content.setFont(QFont("Consolas", 10))
        self.txt_content.setPlainText(self._skill.get("content", ""))
        self.txt_content.setPlaceholderText(
            "在此输入 Skill 提示词内容。\n"
            "例如：\n"
            "你是一名专业的 SQL 优化顾问。当用户提问时，请：\n"
            "1. 分析 SQL 性能瓶颈\n"
            "2. 给出优化后的 SQL\n"
            "3. 解释优化原因"
        )
        inner_layout.addWidget(self.txt_content, stretch=1)

        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        ok = btns.button(QDialogButtonBox.StandardButton.Ok)
        ok.setText("保存")
        ok.setProperty("role", "primary")

        btns.accepted.connect(self._on_ok)
        btns.rejected.connect(self.reject)
        inner_layout.addWidget(btns)

    def _on_ok(self):
        name = self.txt_name.text().strip()
        if not name:
            QMessageBox.warning(self, "提示", "Skill 名称不能为空")
            return
        content = self.txt_content.toPlainText().strip()
        if not content:
            QMessageBox.warning(self, "提示", "Skill 内容不能为空")
            return
        self._result = {
            "name":        name,
            "description": self.txt_desc.text().strip(),
            "category":    self.cmb_category.currentText().strip() or "通用",
            "hotkey":      self.txt_hotkey.text().strip(),
            "content":     content,
            "enabled":     self._skill.get("enabled", True),
        }
        self.accept()

    def get_result(self) -> dict:
        return getattr(self, "_result", {})


# ── Skill 管理主窗口 ────────────────────────────────────────────────────────
class SkillManagerWindow(QDialog):
    """Skill 管理与应用窗口"""

    # 发射此信号通知主窗口注入 Skill 提示词到 AI 对话
    skillApplied = Signal(str, str)  # (skill_name, skill_content)

    def __init__(self, parent=None, skill_mgr: SkillManager = None):
        super().__init__(parent)
        # 无边框窗口设置
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.mgr = skill_mgr or SkillManager()
        self._is_dark = _is_dark_now()
        self._theme = load_theme()
        self._tokens = get_theme_tokens(self._theme)
        self.setWindowTitle("Skill 管理")
        self.setMinimumSize(900, 600)
        self.resize(1000, 660)
        # 先创建标题栏（必须在 _build_ui 之前）
        self._title_bar, self._title_lbl, self._title_close_btn = make_frameless_title_bar(
            self, "Skill 管理", self._tokens)
        self._title_close_btn.clicked.connect(self.close)
        self._build_ui()
        self._refresh_list()
        self._apply_theme()

    def _build_ui(self):
        frame, frame_layout, inner = build_dialog_frame(self._tokens, self, self._title_bar)
        inner_layout = QVBoxLayout(inner)
        inner_layout.setContentsMargins(0, 0, 0, 0)
        inner_layout.setSpacing(0)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(self._build_left())
        splitter.addWidget(self._build_right())
        splitter.setSizes([320, 680])
        splitter.setHandleWidth(1)
        inner_layout.addWidget(splitter)

    def _apply_theme(self):
        """应用当前主题到所有 UI 组件。"""
        t = self._tokens
        accent = t.get("accent", "#3b82f6")
        accent_soft = t.get("accent_soft", "#dbeafe")
        surface = t.get("surface", "#ffffff")
        surface_alt = t.get("surface_alt", "#f3f4f6")
        surface_muted = t.get("surface_muted", "#e5e7eb")
        border = t.get("border", "#d1d5db")
        text = t.get("text", "#1f2937")
        text_soft = t.get("text_soft", "#6b7280")
        muted = t.get("text_muted", "#9ca3af")
        danger = t.get("danger", "#ef4444")
        danger_hover = t.get("danger_hover", "#dc2626")
        scroll_handle = t.get("scroll_handle", "#bcc8d9")
        scroll_handle_hover = t.get("scroll_handle_hover", "#8b9bb0")

        # 搜索框
        if hasattr(self, "search_box"):
            self.search_box.setStyleSheet(
                f"QLineEdit{{background:{surface_alt}; border:1px solid {border}; border-radius: 2px; padding:4px 10px; color:{text}; font-size:12px;}}"
                f"QLineEdit:focus{{border-color:{accent}; background:{surface};}}"
                f"QLineEdit{{selection-background-color:{accent_soft}; selection-color:{accent};}}"
            )

        # 分类下拉框
        combo_style = (
            f"QComboBox{{background:{surface_alt}; border:1px solid {border}; border-radius: 2px; padding:3px 8px; color:{text}; font-size:12px;}}"
            f"QComboBox:hover{{border-color:{accent};}}"
            f"QComboBox:focus{{border-color:{accent}; background:{surface};}}"
            f"QComboBox::drop-down{{border:none; width:20px;}}"
            f"QComboBox QAbstractItemView{{background:{surface}; color:{text}; selection-background-color:{accent_soft}; selection-color:{accent}; border:none; border-radius: 2px; padding:2px;}}"
        )
        if hasattr(self, "cmb_filter"):
            self.cmb_filter.setStyleSheet(combo_style)

        # Skill 列表（替换 setAlternatingRowColors）
        list_style = (
            f"QListWidget{{background:{surface}; border:none; border-radius: 2px; color:{text}; font-size:12px; outline:none;}}"
            f"QListWidget::item{{padding:6px 8px; border-radius: 2px; margin:1px 4px;}}"
            f"QListWidget::item:hover{{background:{surface_alt};}}"
            f"QListWidget::item:selected{{background:{accent_soft}; color:{accent}; border:none;}}"
            f"QListWidget::item:selected:hover{{background:{accent_soft};}}"
            f"QScrollBar:vertical{{background:transparent; width:5px; margin:4px 0; border:none;}}"
            f"QScrollBar::handle:vertical{{background:{scroll_handle}; border-radius: 2px; min-height:30px;}}"
            f"QScrollBar::handle:vertical:hover{{background:{scroll_handle_hover};}}"
            f"QScrollBar::handle:vertical:pressed{{background:{accent};}}"
            f"QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical{{height:0; width:0;}}"
            f"QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical{{background:transparent;}}"
        )
        if hasattr(self, "skill_list"):
            self.skill_list.setAlternatingRowColors(False)
            self.skill_list.setStyleSheet(list_style)

        # 工具栏按钮（无边框）
        btn_style = (
            f"QPushButton{{background:{surface_alt}; color:{text}; border:none; border-radius: 4px; padding:4px 12px; font-size:12px;}}"
            f"QPushButton:hover{{color:{accent}; background:{accent_soft};}}"
            f"QPushButton:pressed{{padding-top:5px; padding-left:13px;}}"
            f"QPushButton:disabled{{background:{surface_muted}; color:{muted};}}"
        )
        accent_btn_style = (
            f"QPushButton{{background:{accent}; color:#fff; border:none; border-radius: 4px; padding:6px 20px; font-size:13px; font-weight:600;}}"
            f"QPushButton:hover{{opacity:0.9;}}"
            f"QPushButton:pressed{{padding-top:7px; padding-left:21px;}}"
        )
        # 收集所有按钮
        for btn in getattr(self, "_toolbar_btns", []):
            btn.setStyleSheet(btn_style)
        for btn in getattr(self, "_toolbar_btns2", []):
            btn.setStyleSheet(btn_style)
        if hasattr(self, "btn_apply"):
            self.btn_apply.setStyleSheet(accent_btn_style)
        if hasattr(self, "btn_toggle"):
            self.btn_toggle.setStyleSheet(btn_style)

        # 详情区标签
        if hasattr(self, "lbl_name"):
            self.lbl_name.setStyleSheet(f"font-weight:bold; font-size:15px; color:{text};")
        if hasattr(self, "lbl_hotkey"):
            self.lbl_hotkey.setStyleSheet(f"font-family:Consolas; color:{accent}; font-size:12px;")
        if hasattr(self, "lbl_desc"):
            self.lbl_desc.setStyleSheet(f"color:{text_soft}; font-size:12px;")
        if hasattr(self, "lbl_category"):
            self.lbl_category.setStyleSheet(f"color:{muted}; font-size:11px;")

        # 预览区
        preview_style = (
            f"QTextEdit{{background:{surface}; border:1px solid {border}; border-radius: 2px; color:{text}; font-size:12px; padding:8px; font-family:Consolas,monospace;}}"
            f"QTextEdit:focus{{border-color:{accent};}}"
            f"QTextEdit{{selection-background-color:{accent_soft}; selection-color:{accent};}}"
        )
        if hasattr(self, "preview"):
            self.preview.setStyleSheet(preview_style)

        # 启用复选框
        if hasattr(self, "chk_enabled"):
            self.chk_enabled.setStyleSheet(
                f"QCheckBox{{color:{text}; spacing:4px; font-size:12px;}}"
                f"QCheckBox::indicator{{width:14px; height:14px; border-radius: 2px; border:1px solid {border};}}"
                f"QCheckBox::indicator:checked{{background:{accent}; border-color:{accent};}}"
            )

    # ── 左侧：列表 + 工具栏 ──────────────────────────────
    def _build_left(self):
        panel = QWidget()
        panel.setMinimumWidth(260)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(8, 8, 4, 8)
        layout.setSpacing(6)

        # 搜索框
        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText(Icon.prefixed_text('search', "搜索 Skill…"))
        self.search_box.setFixedHeight(28)
        self.search_box.textChanged.connect(self._on_search)
        layout.addWidget(self.search_box)

        # 分类筛选
        filter_row = QHBoxLayout()
        filter_row.setSpacing(4)
        lbl = QLabel("分类:")
        lbl.setStyleSheet("font-size:12px;")
        filter_row.addWidget(lbl)
        self.cmb_filter = QComboBox()
        self.cmb_filter.addItem("全部")
        self.cmb_filter.setFixedHeight(26)
        self.cmb_filter.currentTextChanged.connect(self._on_filter_changed)
        filter_row.addWidget(self.cmb_filter, stretch=1)
        layout.addLayout(filter_row)

        # Skill 列表
        self.skill_list = QListWidget()
        self.skill_list.setAlternatingRowColors(True)
        self.skill_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.skill_list.customContextMenuRequested.connect(self._list_context_menu)
        self.skill_list.currentRowChanged.connect(self._on_selection_changed)
        self.skill_list.itemDoubleClicked.connect(self._on_edit)
        layout.addWidget(self.skill_list, stretch=1)

        # 工具栏
        bar = QHBoxLayout()
        bar.setSpacing(4)
        self._toolbar_btns = []
        for text, slot, tip in [
            (Icon.prefixed_text('add', "新建"), self._on_new, "新建 Skill"),
            (Icon.prefixed_text('edit', "编辑"), self._on_edit, "编辑选中的 Skill"),
            (Icon.prefixed_text('delete', "删除"), self._on_delete, "删除选中的 Skill"),
        ]:
            btn = QPushButton(text)
            btn.setFixedHeight(28)
            btn.setToolTip(tip)
            btn.clicked.connect(slot)
            bar.addWidget(btn)
            self._toolbar_btns.append(btn)
        layout.addLayout(bar)

        bar2 = QHBoxLayout()
        bar2.setSpacing(4)
        self._toolbar_btns2 = []
        for text, slot, tip in [
            (Icon.prefixed_text('arrow_up', "上移"), self._on_move_up, "上移"),
            (Icon.prefixed_text('arrow_down', "下移"), self._on_move_down, "下移"),
            (Icon.prefixed_text('download', "导入"), self._on_import, "从文件导入"),
            (Icon.prefixed_text('upload', "导出"), self._on_export, "导出到文件"),
        ]:
            btn = QPushButton(text)
            btn.setFixedHeight(26)
            btn.setToolTip(tip)
            btn.clicked.connect(slot)
            bar2.addWidget(btn)
            self._toolbar_btns2.append(btn)
        layout.addLayout(bar2)

        return panel

    # ── 右侧：预览 + 应用 ────────────────────────────────
    def _build_right(self):
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(4, 8, 8, 8)
        layout.setSpacing(8)

        # 顶部信息区
        info_layout = QFormLayout()
        info_layout.setSpacing(6)
        info_layout.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        self.lbl_name = QLabel("—")
        self.lbl_name.setStyleSheet("font-weight:bold; font-size:15px;")
        info_layout.addRow("名称:", self.lbl_name)

        self.lbl_desc = QLabel("—")
        self.lbl_desc.setWordWrap(True)
        info_layout.addRow("描述:", self.lbl_desc)

        self.lbl_category = QLabel("—")
        info_layout.addRow("分类:", self.lbl_category)

        self.lbl_hotkey = QLabel("—")
        self.lbl_hotkey.setStyleSheet(f"font-family:Consolas; color:{self._tokens['accent']};")
        info_layout.addRow("快捷触发词:", self.lbl_hotkey)

        self.chk_enabled = QCheckBox("已启用")
        self.chk_enabled.setEnabled(False)
        info_layout.addRow("状态:", self.chk_enabled)

        layout.addLayout(info_layout)

        lbl_prev = QLabel("Skill 内容预览:")
        lbl_prev.setStyleSheet("font-weight:bold;")
        layout.addWidget(lbl_prev)

        self.preview = QTextEdit()
        self.preview.setReadOnly(True)
        self.preview.setFont(QFont("Consolas", 10))
        self.preview.setPlaceholderText("选中左侧 Skill 查看内容…")
        layout.addWidget(self.preview, stretch=1)

        # 底部操作按钮
        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)

        self.btn_toggle = QPushButton(f"{Icon.char('pause')} 禁用")
        self.btn_toggle.setFixedHeight(34)
        self.btn_toggle.setToolTip("切换启用/禁用状态")
        self.btn_toggle.clicked.connect(self._on_toggle)

        self.btn_apply = QPushButton(Icon.prefixed_text('robot', "应用到 AI 对话"))
        self.btn_apply.setFixedHeight(34)
        self.btn_apply.setProperty("role", "primary")

        self.btn_apply.setToolTip("将此 Skill 注入到当前 AI 对话的系统提示词")
        self.btn_apply.clicked.connect(self._on_apply)

        btn_row.addWidget(self.btn_toggle)
        btn_row.addStretch()
        btn_row.addWidget(self.btn_apply)
        layout.addLayout(btn_row)

        self._set_detail_enabled(False)
        return panel

    def _set_detail_enabled(self, enabled: bool):
        self.btn_toggle.setEnabled(enabled)
        self.btn_apply.setEnabled(enabled)
        self.chk_enabled.setEnabled(False)

    # ── 列表刷新 ──────────────────────────────────────
    def _refresh_list(self, keep_selection: int = -1):
        """刷新左侧列表，保持选中行"""
        self.skill_list.blockSignals(True)
        self.skill_list.clear()

        search = self.search_box.text().strip().lower()
        cat_filter = self.cmb_filter.currentText()

        # 刷新分类筛选下拉
        old_filter = self.cmb_filter.currentText()
        self.cmb_filter.blockSignals(True)
        self.cmb_filter.clear()
        self.cmb_filter.addItem("全部")
        for c in self.mgr.get_categories():
            self.cmb_filter.addItem(c)
        self.cmb_filter.setCurrentText(old_filter if old_filter in self.mgr.get_categories() + ["全部"] else "全部")
        self.cmb_filter.blockSignals(False)

        self._filtered_indices = []
        for i, skill in enumerate(self.mgr.skills):
            # 搜索过滤
            if search and search not in skill["name"].lower() and search not in skill.get("description", "").lower():
                continue
            # 分类过滤
            if cat_filter != "全部" and skill.get("category", "通用") != cat_filter:
                continue

            enabled = skill.get("enabled", True)
            item = QListWidgetItem()
            icon = Icon.styled_char('success') if enabled else Icon.styled_char('pause')
            item.setText(f" {icon}  {skill['name']}")
            if skill.get("hotkey"):
                item.setToolTip(f"快捷触发词: {skill['hotkey']}")
            if not enabled:
                item.setForeground(QColor(self._tokens["text_muted"]))
            self.skill_list.addItem(item)
            self._filtered_indices.append(i)

        self.skill_list.blockSignals(False)

        # 恢复选中
        if keep_selection >= 0:
            for row, idx in enumerate(self._filtered_indices):
                if idx == keep_selection:
                    self.skill_list.setCurrentRow(row)
                    break
        elif self.skill_list.count() > 0:
            self.skill_list.setCurrentRow(0)
        else:
            self._clear_detail()

    def _get_selected_index(self) -> int:
        """获取当前选中的 skills 数组原始索引"""
        row = self.skill_list.currentRow()
        if row < 0 or row >= len(self._filtered_indices):
            return -1
        return self._filtered_indices[row]

    def _clear_detail(self):
        self.lbl_name.setText("—")
        self.lbl_desc.setText("—")
        self.lbl_category.setText("—")
        self.lbl_hotkey.setText("—")
        self.chk_enabled.setChecked(False)
        self.preview.clear()
        self._set_detail_enabled(False)

    def _on_selection_changed(self, row: int):
        if row < 0 or row >= len(getattr(self, "_filtered_indices", [])):
            self._clear_detail()
            return
        idx = self._filtered_indices[row]
        skill = self.mgr.skills[idx]
        self.lbl_name.setText(skill["name"])
        self.lbl_desc.setText(skill.get("description", "—") or "—")
        self.lbl_category.setText(skill.get("category", "通用"))
        hk = skill.get("hotkey", "")
        self.lbl_hotkey.setText(hk if hk else "—（未设置）")
        self.chk_enabled.setChecked(skill.get("enabled", True))
        self.preview.setPlainText(skill.get("content", ""))
        enabled = skill.get("enabled", True)
        self.btn_toggle.setText(Icon.prefixed_text('pause', "禁用") if enabled else Icon.prefixed_text('play', "启用"))
        self._set_detail_enabled(True)

    # ── 搜索 / 过滤 ──────────────────────────────────
    def _on_search(self, _):
        self._refresh_list(self._get_selected_index())

    def _on_filter_changed(self, _):
        self._refresh_list(self._get_selected_index())

    # ── 列表右键菜单 ─────────────────────────────────
    def _list_context_menu(self, pos):
        idx = self._get_selected_index()
        if idx < 0:
            return
        skill = self.mgr.skills[idx]
        menu = QMenu(self)
        menu.addAction(Icon.prefixed_text('edit', "编辑"), self._on_edit)
        menu.addAction(Icon.prefixed_text('delete', "删除"), self._on_delete)
        menu.addSeparator()
        enabled = skill.get("enabled", True)
        menu.addAction(Icon.prefixed_text('pause', "禁用") if enabled else Icon.prefixed_text('play', "启用"), self._on_toggle)
        menu.addSeparator()
        menu.addAction(Icon.prefixed_text('robot', "应用到 AI 对话"), self._on_apply)
        menu.exec(self.skill_list.mapToGlobal(pos))

    # ── 操作槽 ────────────────────────────────────
    def _on_new(self):
        dlg = _SkillEditDialog(self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            skill = dlg.get_result()
            self.mgr.add_skill(
                skill["name"], skill["content"],
                description=skill["description"],
                category=skill["category"],
                hotkey=skill["hotkey"],
            )
            self._refresh_list(len(self.mgr.skills) - 1)

    def _on_edit(self, *_):
        idx = self._get_selected_index()
        if idx < 0:
            return
        dlg = _SkillEditDialog(self, self.mgr.skills[idx])
        if dlg.exec() == QDialog.DialogCode.Accepted:
            result = dlg.get_result()
            self.mgr.update_skill(idx, **result)
            self._refresh_list(idx)

    def _on_delete(self):
        idx = self._get_selected_index()
        if idx < 0:
            return
        name = self.mgr.skills[idx]["name"]
        ret = QMessageBox.question(
            self, "删除 Skill",
            f"确定删除 Skill 「{name}」？此操作不可恢复。",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if ret == QMessageBox.StandardButton.Yes:
            self.mgr.delete_skill(idx)
            self._refresh_list()

    def _on_toggle(self):
        idx = self._get_selected_index()
        if idx < 0:
            return
        new_state = self.mgr.toggle_enabled(idx)
        self._refresh_list(idx)

    def _on_move_up(self):
        idx = self._get_selected_index()
        if idx <= 0:
            return
        self.mgr.move_up(idx)
        self._refresh_list(idx - 1)

    def _on_move_down(self):
        idx = self._get_selected_index()
        if idx < 0 or idx >= len(self.mgr.skills) - 1:
            return
        self.mgr.move_down(idx)
        self._refresh_list(idx + 1)

    def _on_import(self):
        paths, _ = QFileDialog.getOpenFileNames(
            self, "导入 Skill 文件", "",
            "Skill 包 (*.zip);;文本文件 (*.txt *.md *.py *.sql);;所有文件 (*.*)"
        )
        if not paths:
            return
        ok_count = 0
        imported_count = 0
        for path in paths:
            if path.lower().endswith(".zip"):
                ok, msg, cnt = self.mgr.import_from_zip(path)
                if ok:
                    ok_count += 1
                    imported_count += cnt
                QMessageBox.information(self, "ZIP 导入结果", msg)
            else:
                ok, msg = self.mgr.import_skill(path)
                if ok:
                    ok_count += 1
                    imported_count += 1
        if not paths[0].lower().endswith(".zip"):
            QMessageBox.information(
                self, "导入完成",
                f"{Icon.styled_char('success')} 成功导入 {ok_count}/{len(paths)} 个 Skill"
            )
        self._refresh_list(len(self.mgr.skills) - 1)

    def _on_export(self):
        idx = self._get_selected_index()
        if idx < 0:
            return
        skill = self.mgr.skills[idx]
        path, _ = QFileDialog.getSaveFileName(
            self, "导出 Skill",
            f"{skill['name']}.txt",
            "文本文件 (*.txt);;Markdown (*.md);;所有文件 (*.*)"
        )
        if not path:
            return
        ok, msg = self.mgr.export_skill(idx, path)
        QMessageBox.information(self, "导出结果", msg)

    def _on_apply(self):
        idx = self._get_selected_index()
        if idx < 0:
            return
        skill = self.mgr.skills[idx]
        if not skill.get("enabled", True):
            QMessageBox.warning(self, "提示", "该 Skill 已被禁用，请先启用后再应用。")
            return
        self.skillApplied.emit(skill["name"], skill.get("content", ""))
        QMessageBox.information(
            self, "已应用",
            f"{Icon.styled_char('success')} Skill 「{skill['name']}」已注入到 AI 对话系统提示词中。\n\n"
            f"之后的 AI 对话将会遵循此 Skill 的指令。"
        )