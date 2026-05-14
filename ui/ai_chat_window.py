"""
ai_chat_window.py
AI 多轮对话 + Agent 自动执行模式
============================================================
- AIChatWidget(QWidget)  ── 可直接嵌入任意布局的对话面板
- AIChatWindow(QDialog)  ── 弹窗包装（向下兼容）

模式切换（右上角按钮组）：
  对话模式   —— 普通多轮对话（AIChatEngine）
  Agent 模式 —— ReAct 自动执行（AIAgent）

增强能力：
- 发送区支持上传文件、选择数据库、选择模型、引用 Skill
- 历史记录按数据库上下文归档，可按库切换查看
- 气泡和面板样式统一走主题 token
"""
from __future__ import annotations

import datetime
from typing import Optional

from PySide6.QtWidgets import (
    QWidget, QDialog, QVBoxLayout, QHBoxLayout, QSplitter,
    QScrollArea, QTextEdit, QPushButton, QLabel,
    QListWidget, QListWidgetItem, QMessageBox, QSizePolicy,
    QFrame, QApplication, QToolButton, QFileDialog,
    QComboBox, QMenu, QAbstractScrollArea, QCheckBox, QAbstractItemView,
    QStyledItemDelegate, QStyleOptionButton, QStyle,
    QLineEdit, QListView,
)
from PySide6.QtCore import (
    Qt, QRunnable, QObject, QThreadPool, Signal, QPoint, QSize, QTimer,
    QModelIndex,
)
from PySide6 import QtCore, QtGui

from PySide6.QtGui import QFont, QTextOption, QStandardItemModel, QStandardItem, QBrush


from core.ai_chat import AIChatEngine, DEFAULT_HISTORY_KEY
from core.ai_agent import AIAgent
from app_config.model_config import ModelConfig, get_model_config_notifier
from ui.iconfont_loader import Icon
from ui.theme_manager import (
    load_theme, THEME_DARK, THEME_LIGHT, THEME_WILLOW, THEME_AUTO,
    get_theme_tokens, get_bubble_colors, build_popup_base_style,
    build_frameless_dialog_style,
)



def _current_theme() -> str:
    theme = load_theme()
    # 向后兼容：旧配置 "auto" 默认映射为紫罗兰亮色
    if theme == THEME_AUTO:
        return THEME_LIGHT
    return theme


def _current_is_dark() -> bool:
    return _current_theme() == THEME_DARK


def _tokens() -> dict:
    return get_theme_tokens(_current_theme())


def _bubble_palette() -> dict:
    return get_bubble_colors(_current_theme())


# ─── 后台线程信号 ────────────────────────────────
class _ChatSignals(QObject):
    finished = Signal(str)   # 最终回复文本


class _ChatWorker(QRunnable):
    """普通对话后台线程"""

    def __init__(
        self,
        engine: AIChatEngine,
        text: str,
        schema: str,
        db_type: str,
        history_key: str,
        db_label: str,
        provider_override: str,
        model_override: str,
    ):
        super().__init__()
        self.engine = engine
        self.text = text
        self.schema = schema
        self.db_type = db_type
        self.history_key = history_key
        self.db_label = db_label
        self.provider_override = provider_override
        self.model_override = model_override
        self.signals = _ChatSignals()

    def run(self):
        reply = self.engine.chat(
            self.text,
            self.schema,
            self.db_type,
            history_key=self.history_key,
            db_label=self.db_label,
            provider_override=self.provider_override,
            model_override=self.model_override,
        )
        self.signals.finished.emit(reply)


class _AgentWorker(QRunnable):
    """Agent 后台线程"""

    def __init__(
        self,
        agent: AIAgent,
        text: str,
        schema: str,
        db_type: str,
    ):
        super().__init__()
        self.agent = agent
        self.text = text
        self.schema = schema
        self.db_type = db_type
        self.signals = _ChatSignals()

    def run(self):
        result = self.agent.run(
            self.text,
            self.schema,
            self.db_type,
        )
        self.signals.finished.emit(result)



# ─── 加载状态指示器 ──────────────────────────────
class _LoadingBubble(QWidget):
    """三点跳动动画的加载气泡 —— 显示 AI 正在思考"""

    def __init__(self, text: str = "AI 正在思考中"):
        super().__init__()
        self._text = text
        self._dot_count = 0
        self._init_ui()
        self._start_animation()

    def _init_ui(self):
        tokens = _tokens()
        palette = _bubble_palette()

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 6)
        layout.setSpacing(8)

        # 头像
        avatar = QLabel("团")
        avatar.setFixedSize(30, 30)
        avatar.setAlignment(Qt.AlignmentFlag.AlignCenter)
        avatar.setStyleSheet(
            f"border-radius: 2px; font-size:12px; font-weight:700; color:white;"
            f"background:{tokens['accent']};"
        )
        layout.addWidget(avatar, 0, Qt.AlignmentFlag.AlignTop)

        # 气泡容器
        bubble_frame = QFrame()
        bubble_layout = QVBoxLayout(bubble_frame)
        bubble_layout.setContentsMargins(12, 10, 12, 10)
        bubble_layout.setSpacing(6)

        # 文本标签
        self.text_label = QLabel(f"{self._text}...")
        self.text_label.setStyleSheet(
            f"color:{tokens['text_muted']}; font-size:13px; border:none;"
        )
        bubble_layout.addWidget(self.text_label)

        # 三个跳动的点
        dots_layout = QHBoxLayout()
        dots_layout.setSpacing(4)
        self.dots = []
        for i in range(3):
            dot = QLabel("•")
            dot.setStyleSheet(
                f"color:{tokens['accent']}; font-size:20px; font-weight:bold;"
            )
            dot.setProperty("dot_index", i)
            dots_layout.addWidget(dot)
            self.dots.append(dot)
        dots_layout.addStretch()
        bubble_layout.addLayout(dots_layout)

        # 气泡样式 Cursor 风格（18px 大圆角）
        bubble_frame.setStyleSheet(
            f"QFrame{{"
            f"background:{palette.get('ai', tokens['surface_muted'])};"
            f"border:1px solid {tokens['border']};"
            f"border-top-left-radius:18px; border-top-right-radius:18px;"
            f"border-bottom-left-radius:18px; border-bottom-right-radius:6px;"
            f"}}"
        )

        layout.addWidget(bubble_frame, 0, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        layout.addStretch(1)

    def _start_animation(self):
        """启动三点跳动动画"""
        from PySide6.QtCore import QPropertyAnimation, QEasingCurve
        
        # 使用定时器来实现简单的跳动效果
        self.animation_timer = QTimer(self)
        self._animation_step = 0
        self.animation_timer.timeout.connect(self._animate_dots)
        self.animation_timer.start(150)  # 每150ms更新一次
    
    def _animate_dots(self):
        """动画回调 - 更新三个点的位置"""
        self._animation_step = (self._animation_step + 1) % 4
        
        for i, dot in enumerate(self.dots):
            # 计算每个点的偏移量（错开相位）
            phase = (self._animation_step + i) % 4
            if phase == 0:
                offset = 0
            elif phase == 1:
                offset = -6
            elif phase == 2:
                offset = -8
            else:
                offset = -4
            
            # 使用 margin-top 来实现上下移动
            dot.setStyleSheet(
                f"color:{_tokens()['accent']}; font-size:20px; font-weight:bold;"
                f"margin-top:{offset}px;"
            )

    def _update_dots_text(self):
        """更新省略号动画"""
        self._dot_count = (self._dot_count + 1) % 4
        dots = "." * self._dot_count
        self.text_label.setText(f"{self._text}{dots}")

    def stop_animation(self):
        """停止所有动画"""
        if hasattr(self, 'text_timer'):
            self.text_timer.stop()
        if hasattr(self, 'animation_timer'):
            self.animation_timer.stop()


# ─── 气泡消息控件 ────────────────────────────────
class _BubbleWidget(QWidget):
    """单条消息气泡 —— 支持 Markdown 代码块渲染 + 双击复制"""

    STEP_META = {
        "think": (f"{Icon.styled_char('question')} 思考中…", "think"),
        "sql": (Icon.prefixed_text('play', "执行 SQL"), "sql"),
        "obs": (f"{Icon.styled_char('bar_chart')} 执行结果", "obs"),
        "done": (Icon.prefixed_text('success', "完成"), "done"),
        "error": (Icon.prefixed_text('error', "出错"), "error"),
        "info": (Icon.prefixed_text('info', "信息"), "info"),
    }

    def _get_avatar_colors(self) -> dict:
        """获取头像颜色 - 使用主题 token"""
        tokens = _tokens()
        return {
            "user": tokens["success"],
            "assistant": tokens["accent"],
            "think": tokens["warning"],
            "sql": tokens["accent"],
            "obs": tokens["success"],
            "done": tokens.get("info", tokens["text_soft"]),
            "error": tokens["danger"],
            "info": tokens["text_muted"],
        }


    def __init__(self, role: str, text: str, time_str: str = "", step_type: str = ""):
        super().__init__()
        self.role = role
        self._step_type = step_type
        self._raw_text = text
        self._init_ui(time_str)

    def _init_ui(self, time_str: str):
        tokens = _tokens()
        palette = _bubble_palette()
        is_dark = _current_is_dark()

        outer = QVBoxLayout(self)
        outer.setContentsMargins(8, 4, 8, 6)
        outer.setSpacing(5)

        display_time = time_str[:5] if len(time_str or "") >= 5 and ":" in time_str else time_str
        if display_time:
            time_lbl = QLabel(display_time)
            time_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            time_lbl.setStyleSheet(
                f"background:{tokens['surface_muted']}; color:{tokens['text_muted']};"
                "border:none; border-radius: 2px;"
                "padding:1px 9px; font-size:10px;"
            )
            outer.addWidget(time_lbl, 0, Qt.AlignmentFlag.AlignHCenter)

        layout = QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        avatar_colors = self._get_avatar_colors()
        av_key = self._step_type if self._step_type in avatar_colors else self.role
        av_bg = avatar_colors.get(av_key, tokens["accent"])
        av_lbl = "我" if self.role == "user" else "团"
        avatar = QLabel(av_lbl)
        avatar.setFixedSize(30, 30)
        avatar.setAlignment(Qt.AlignmentFlag.AlignCenter)
        avatar.setStyleSheet(
            f"border-radius: 2px; font-size:12px; font-weight:700; color:white; background:{av_bg};"
        )

        bubble_padding = "padding:10px 12px 11px 12px;"

        border_left = ""
        bubble_shape = (
            "border-top-left-radius:18px; border-top-right-radius:18px;"
            "border-bottom-left-radius:18px; border-bottom-right-radius:6px;"
        )

        if self._step_type and self._step_type in self.STEP_META:
            title, palette_key = self.STEP_META[self._step_type]
            bg_color = palette.get(palette_key, tokens["surface_alt"])
            title_color = tokens["accent"] if self._step_type == "sql" else tokens["text"]
            title_bg = tokens["surface"]
            title_border = tokens["border"]
            if self._step_type == "think":
                title_color = tokens["warning"]
                title_bg = tokens.get("warning_soft", tokens["surface"])
                title_border = tokens["warning"]
            elif self._step_type == "obs":
                title_color = tokens["success"]
                title_bg = tokens.get("success_soft", tokens["surface"])
                title_border = tokens["success"]
            elif self._step_type == "done":
                title_color = tokens["accent"]
                title_bg = tokens.get("success_soft", tokens["surface"])
                title_border = tokens.get("success", tokens["border"])
            elif self._step_type == "error":
                title_color = tokens["danger"]
                title_bg = tokens.get("danger_soft", tokens["surface"])
                title_border = tokens["danger"]
                bg_color = tokens.get("danger_soft", bg_color)
            full_html = (
                f"<div style='display:inline-block; font-size:11px; font-weight:700; color:{title_color};"
                f" background:{title_bg}; border:1px solid {title_border}; border-radius: 2px;"
                f" padding:3px 10px; margin-bottom:8px;'>{title}</div>"
                + self._render_html(self._raw_text, is_dark, self._step_type)
            )
            txt_color = tokens["text"]
            border_c = title_border if self._step_type == "error" else tokens["border"]
            border_left = f"border-left:4px solid {title_color};"
            bubble_shape = (
                "border-top-left-radius:18px; border-top-right-radius:18px;"
                "border-bottom-left-radius:18px; border-bottom-right-radius:18px;"
            )
        elif self.role == "user":
            # Cursor 风格：用户气泡，柔和紫蓝
            bg_color = tokens.get("user_bubble_bg", tokens["accent_soft"])
            txt_color = tokens["text"]
            border_c = "transparent"
            full_html = self._render_html(self._raw_text, is_dark, "user")
        else:
            bg_color = tokens["surface"]
            txt_color = tokens["text"]
            border_c = tokens["border"]
            bubble_shape = (
                "border-top-left-radius:18px; border-top-right-radius:18px;"
                "border-bottom-left-radius:6px; border-bottom-right-radius:18px;"
            )
            full_html = self._render_html(self._raw_text, is_dark, "")

        msg = QTextEdit()
        msg.setReadOnly(True)
        msg.setAcceptRichText(True)
        msg.setFrameShape(QFrame.Shape.NoFrame)
        msg.setSizeAdjustPolicy(QAbstractScrollArea.SizeAdjustPolicy.AdjustToContents)
        msg.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        msg.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        msg.setLineWrapMode(QTextEdit.LineWrapMode.WidgetWidth)
        text_option = msg.document().defaultTextOption()
        text_option.setWrapMode(QTextOption.WrapMode.WrapAtWordBoundaryOrAnywhere)
        msg.document().setDefaultTextOption(text_option)
        msg.setHtml(full_html)
        use_mono = self._step_type in ("sql", "obs")
        msg.setFont(QFont("Consolas" if use_mono else "Microsoft YaHei", 10))

        msg.setStyleSheet(
            "QTextEdit{"
            f"background:{bg_color}; color:{txt_color};"
            f"border:1px solid {border_c}; {bubble_shape}"
            f"{border_left} {bubble_padding}"
            "}"
        )
        msg.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)

        def _copy_message(_event):
            QApplication.clipboard().setText(self._raw_text)
            self._show_copy_tip(msg)
            _event.accept()

        msg.mouseDoubleClickEvent = _copy_message

        if self.role == "user":
            layout.addStretch(1)
            layout.addWidget(msg, 0, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignTop)
            layout.addWidget(avatar, 0, Qt.AlignmentFlag.AlignTop)
        else:
            layout.addWidget(avatar, 0, Qt.AlignmentFlag.AlignTop)
            layout.addWidget(msg, 0, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
            layout.addStretch(1)

        outer.addLayout(layout)
        self.msg_widget = msg
        QTimer.singleShot(0, self.resize_msg)
        
        # 启用右键菜单
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_context_menu)



    def contextMenuEvent(self, event):
        """右键菜单事件"""
        self._show_context_menu(event.pos())
    
    def _show_context_menu(self, pos):
        """显示上下文菜单"""
        menu = QMenu(self)
        menu.setStyleSheet(self._build_menu_style())
        
        # 复制文本
        copy_action = menu.addAction(Icon.prefixed_text('clipboard', "复制文本"))
        copy_action.triggered.connect(self._copy_text)
        
        # 引用此消息
        quote_action = menu.addAction(Icon.prefixed_text('chat', "引用此消息"))
        quote_action.triggered.connect(self._quote_message)
        
        # 分隔线
        menu.addSeparator()
        
        # 编辑消息（仅用户消息）
        if self.role == "user":
            edit_action = menu.addAction(Icon.prefixed_text('edit', "编辑消息"))
            edit_action.triggered.connect(self._edit_message)
        
        # 重新生成（仅AI消息）
        if self.role == "assistant" and not self._step_type:
            regen_action = menu.addAction(Icon.prefixed_text('refresh', "重新生成"))
            regen_action.triggered.connect(self._regenerate_message)
        
        # 导出为文件
        export_action = menu.addAction(Icon.prefixed_text('save', "导出为文件"))
        export_action.triggered.connect(self._export_to_file)
        
        # 如果是SQL，添加执行选项
        if self._step_type == "sql" or (self.role == "assistant" and self._is_sql_content()):
            exec_action = menu.addAction(Icon.prefixed_text('play', "执行此SQL"))
            exec_action.triggered.connect(self._execute_sql)
            menu.addSeparator()
        
        # 删除消息
        delete_action = menu.addAction(Icon.prefixed_text('delete', "删除此消息"))
        delete_action.setStyleSheet(delete_action.styleSheet() + 
                                   "QAction{color:#d9363e;}")
        delete_action.triggered.connect(self._delete_message)
        
        # 显示菜单
        menu.exec(self.mapToGlobal(pos))
    
    def _build_menu_style(self) -> str:
        """构建菜单样式"""
        tokens = _tokens()
        return f"""
            QMenu {{
                background-color: {tokens['surface']};
                color: {tokens['text']};
                border: 1px solid {tokens['border_strong']};
                border-radius: 2px;
                padding: 4px;
            }}
            QMenu::item {{
                padding: 6px 20px 6px 12px;
                border-radius: 2px;
            }}
            QMenu::item:selected {{
                background-color: {tokens['accent_soft']};
                color: {tokens['accent']};
            }}
            QMenu::separator {{
                height: 1px;
                background: {tokens['border']};
                margin: 4px 8px;
            }}
        """
    
    def _copy_text(self):
        """复制文本到剪贴板"""
        QApplication.clipboard().setText(self._raw_text)
        self._show_action_tip("已复制到剪贴板")
    
    def _quote_message(self):
        """引用此消息到输入框"""
        # 获取引用的内容，如果内容过长则截断
        text = self._raw_text.strip()
        if len(text) > 500:
            text = text[:500] + "..."
        
        # 格式化为引用格式（处理多行）
        lines = text.split('\n')
        quoted_lines = [f"> {line}" for line in lines]
        quoted_text = '\n'.join(quoted_lines)
        
        # 查找父窗口并调用插入方法
        parent = self.parentWidget()
        while parent and not hasattr(parent, '_insert_text_at_cursor'):
            parent = parent.parentWidget()
        
        if parent and hasattr(parent, '_insert_text_at_cursor'):
            parent._insert_text_at_cursor(quoted_text)
            self._show_action_tip("已引用到输入框")
    
    def _edit_message(self):
        """编辑用户消息"""
        if self.role != "user":
            return
        
        # 查找父窗口并调用编辑方法
        parent = self.parentWidget()
        while parent and not hasattr(parent, '_edit_bubble_message'):
            parent = parent.parentWidget()
        
        if parent and hasattr(parent, '_edit_bubble_message'):
            parent._edit_bubble_message(self)
    
    def _regenerate_message(self):
        """重新生成AI回复"""
        if self.role != "assistant":
            return
        
        # 查找父窗口并调用重新生成方法
        parent = self.parentWidget()
        while parent and not hasattr(parent, '_regenerate_bubble_message'):
            parent = parent.parentWidget()
        
        if parent and hasattr(parent, '_regenerate_bubble_message'):
            parent._regenerate_bubble_message(self)
    
    def _export_to_file(self):
        """导出消息到文件"""
        from PySide6.QtWidgets import QFileDialog
        
        # 生成默认文件名
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        default_name = f"message_{timestamp}.txt"
        
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "导出消息",
            default_name,
            "文本文件 (*.txt);;Markdown文件 (*.md);;所有文件 (*)"
        )
        
        if file_path:
            try:
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(f"# {'用户' if self.role == 'user' else 'AI'} 消息\n\n")
                    f.write(f"时间: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
                    f.write("---\n\n")
                    f.write(self._raw_text)
                self._show_action_tip(f"已导出到: {file_path}")
            except Exception as e:
                QMessageBox.warning(self, "导出失败", f"无法导出文件: {str(e)}")
    
    def _execute_sql(self):
        """执行SQL"""
        # 提取SQL内容
        sql_text = self._raw_text
        
        # 如果包含在代码块中，提取出来
        import re
        sql_match = re.search(r'```(?:sql)?\s*(.*?)```', sql_text, re.DOTALL)
        if sql_match:
            sql_text = sql_match.group(1).strip()
        
        # 查找父窗口并调用执行方法
        parent = self.parentWidget()
        while parent and not hasattr(parent, '_execute_sql_from_bubble'):
            parent = parent.parentWidget()
        
        if parent and hasattr(parent, '_execute_sql_from_bubble'):
            parent._execute_sql_from_bubble(sql_text)
    
    def _delete_message(self):
        """删除此消息"""
        reply = QMessageBox.question(
            self,
            "确认删除",
            "确定要删除这条消息吗？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            # 查找父窗口并调用删除方法
            parent = self.parentWidget()
            while parent and not hasattr(parent, '_delete_bubble_message'):
                parent = parent.parentWidget()
            
            if parent and hasattr(parent, '_delete_bubble_message'):
                parent._delete_bubble_message(self)
    
    def _is_sql_content(self) -> bool:
        """检查内容是否为SQL"""
        import re
        # 检查是否包含SQL关键字
        sql_keywords = ['SELECT', 'INSERT', 'UPDATE', 'DELETE', 'CREATE', 'DROP', 'ALTER']
        text_upper = self._raw_text.upper()
        
        # 检查是否包含SQL代码块
        if re.search(r'```sql', self._raw_text, re.IGNORECASE):
            return True
        
        # 检查是否以SQL关键字开头
        for keyword in sql_keywords:
            if text_upper.strip().startswith(keyword):
                return True
        
        return False
    
    def _show_action_tip(self, message: str):
        """显示操作提示"""
        # 临时修改气泡边框颜色作为反馈
        if hasattr(self, 'msg_widget'):
            original_style = self.msg_widget.styleSheet()
            tokens = _tokens()
            self.msg_widget.setStyleSheet(
                original_style + 
                f"border: 2px solid {tokens['success']};"
            )
            
            # 显示tooltip
            from PySide6.QtWidgets import QToolTip
            QToolTip.showText(
                self.mapToGlobal(self.rect().center()),
                message,
                None,
                self.rect(),
                1500  # 1.5秒后自动消失
            )
            
            # 恢复原始样式
            QTimer.singleShot(1000, lambda: self.msg_widget.setStyleSheet(original_style))



    def _ideal_text_width(self) -> int:
        width = 0
        parent = self.parentWidget()
        while parent is not None:
            width = max(width, parent.width())
            parent = parent.parentWidget()
        if width <= 0:
            width = 760
        return max(260, min(width - 120, 880))

    def _preferred_bubble_width(self, available_width: int) -> int:
        text = (self._raw_text or "").strip()
        text_len = len(text)
        is_multiline = "\n" in text or "```" in text

        if self.role == "user":
            if is_multiline or text_len > 22:
                return min(available_width, max(220, int(available_width * 0.56)))
            return min(available_width, max(118, min(320, 72 + text_len * 14)))

        if self._step_type == "error":
            return min(available_width, max(360, int(available_width * 0.78)))
        if self._step_type:
            return min(available_width, max(320, int(available_width * 0.74)))
        if is_multiline or text_len > 52:
            return min(available_width, max(360, int(available_width * 0.72)))
        return min(available_width, max(240, min(520, 116 + text_len * 10)))


    @staticmethod
    def _render_html(text: str, is_dark: bool, step_type: str) -> str:
        """渲染HTML内容，支持增强的代码块"""
        import re
        import html as html_mod

        tokens = _tokens()
        code_bg = tokens["surface_alt"] if is_dark else "#f6f8fa"
        code_fg = tokens["text"] if is_dark else "#24292e"
        inline_bg = tokens["surface_muted"] if is_dark else "#eef0f2"
        
        # 尝试使用 Pygments 进行语法高亮
        try:
            from pygments import highlight
            from pygments.lexers import get_lexer_by_name, TextLexer
            from pygments.formatters import HtmlFormatter
            has_pygments = True
        except ImportError:
            has_pygments = False

        parts = re.split(r"(```[\w]*\n?[\s\S]*?```)", text)
        html_parts = []
        
        for part in parts:
            if part.startswith("```"):
                m = re.match(r"```(\w*)\n?([\s\S]*?)```", part, re.DOTALL)
                if m:
                    lang = m.group(1).lower() or "text"
                    code = m.group(2).rstrip()
                    
                    if has_pygments and lang != "text":
                        # 使用 Pygments 进行语法高亮
                        try:
                            lexer = get_lexer_by_name(lang, stripall=True)
                        except:
                            lexer = TextLexer()
                        
                        formatter = HtmlFormatter(
                            style="monokai" if is_dark else "default",
                            noclasses=True,
                            prestyles=f"background:{code_bg}; color:{code_fg}; border-radius: 2px; padding:8px 10px; font-family:Consolas,monospace; font-size:12px; white-space:pre-wrap; margin:4px 0;",
                        )
                        highlighted = highlight(code, lexer, formatter)
                        # 移除 Pygments 生成的外层 pre 标签，我们自己在工具栏中添加
                        highlighted = re.sub(r'^<pre[^>]*>|</pre>$', '', highlighted, flags=re.DOTALL)

                        # 添加带工具栏的代码块
                        toolbar_bg = tokens["surface_muted"]
                        text_muted = tokens["text_muted"]
                        lang_label = lang.upper()
                        html_parts.append(
                            f"<div style='background:{code_bg}; border-radius: 2px; margin:4px 0;'>"
                            f"<div style='display:flex; justify-content:space-between; align-items:center; "
                            f"padding:4px 8px; background:{toolbar_bg}; border-radius: 2px 8px 0 0;'>"
                            f"<span style='color:{text_muted}; font-size:11px;'>{lang_label}</span>"
                            f"</div>"
                            f"<pre style='background:{code_bg}; color:{code_fg};"
                            f" border-radius:0 0 2px 2px; padding:8px 10px; font-family:Consolas,monospace;"
                            f" font-size:12px; white-space:pre-wrap; margin:0;'>{highlighted}</pre>"
                            f"</div>"
                        )
                    else:
                        # 简单渲染（无语法高亮）
                        escaped_code = html_mod.escape(code)
                        toolbar_bg = tokens["surface_muted"]
                        text_muted = tokens["text_muted"]
                        lang_label = lang.upper() if lang else "TEXT"
                        html_parts.append(
                            f"<div style='background:{code_bg}; border-radius: 2px; margin:4px 0;'>"
                            f"<div style='padding:4px 8px; background:{toolbar_bg}; border-radius: 2px 6px 0 0;'>"
                            f"<span style='color:{text_muted}; font-size:11px;'>{lang_label}</span>"
                            f"</div>"
                            f"<pre style='background:{code_bg}; color:{code_fg};"
                            f" border-radius:0 0 2px 2px; padding:8px 10px; font-family:Consolas,monospace;"
                            f" font-size:12px; white-space:pre-wrap; margin:0;'>{escaped_code}</pre>"
                            f"</div>"
                        )
                else:
                    # 解析失败，原样显示
                    escaped = html_mod.escape(part)
                    html_parts.append(
                        f"<pre style='background:{code_bg}; color:{code_fg};"
                        f" border-radius: 2px; padding:8px 10px; font-family:Consolas,monospace;"
                        f" font-size:12px; white-space:pre-wrap; margin:4px 0;'>{escaped}</pre>"
                    )
            else:
                # 普通文本处理
                escaped = html_mod.escape(part)
                escaped = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", escaped)
                escaped = re.sub(
                    r"`([^`]+)`",
                    lambda mm: (
                        f"<code style='background:{inline_bg}; border-radius: 2px;"
                        f" padding:1px 4px; font-family:Consolas,monospace;'>{mm.group(1)}</code>"
                    ),
                    escaped,
                )
                escaped = escaped.replace("\n", "<br>")
                html_parts.append(f"<span>{escaped}</span>")

        return (
            "<div style='font-size:13px; line-height:1.55; white-space:normal;"
            " word-wrap:break-word;'>"
            f"{''.join(html_parts)}"
            "</div>"
        )



    def _show_copy_tip(self, widget):
        orig = widget.styleSheet()
        tokens = _tokens()
        widget.setStyleSheet(orig + f"border:1.5px solid {tokens['success']};")
        from PySide6.QtCore import QTimer
        QTimer.singleShot(600, lambda: widget.setStyleSheet(orig))

    def resize_msg(self):
        if not hasattr(self, "msg_widget"):
            return
        available_width = self._ideal_text_width()
        bubble_width = self._preferred_bubble_width(available_width)
        self.msg_widget.setFixedWidth(bubble_width)
        self.msg_widget.document().setTextWidth(max(bubble_width - 28, 120))
        doc_h = int(self.msg_widget.document().size().height()) + 22
        self.msg_widget.setFixedHeight(max(doc_h, 46))


    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.resize_msg()


# ─── 技能可勾选下拉框 ─────────────────────────────

class _CheckboxDelegate(QStyledItemDelegate):
    """为 QListView 的每一行绘制复选框"""
    def paint(self, painter, option, index):
        super().paint(painter, option, index)
        checked = index.data(Qt.ItemDataRole.CheckStateRole) == Qt.CheckState.Checked
        opt = QStyleOptionButton()
        opt.rect = option.rect.adjusted(4, 0, 0, 0)
        opt.state = QStyle.StateFlag.State_Enabled
        if checked:
            opt.state |= QStyle.StateFlag.State_On
        else:
            opt.state |= QStyle.StateFlag.State_Off
        QApplication.style().drawControl(QStyle.ControlElement.CE_CheckBox, opt, painter)

    def sizeHint(self, option, index):
        sh = super().sizeHint(option, index)
        return QSize(sh.width(), max(sh.height(), 28))


class SkillDropdownSelector(QWidget):
    """
    参考 WorkBuddy 技能选择器设计：
    - 胶囊形触发按钮（图标 + "选择技能..."）
    - 弹出浮动面板含搜索框 + 技能列表
    - 列表项点击即切换勾选，搜索实时过滤
    - 右侧有垂直滚动条（原生 QScrollBar）
    """
    selectionChanged = Signal(list)   # [name1, name2, ...]

    def __init__(self, parent=None):
        super().__init__(parent)
        # 颜色默认值
        self._accent       = "#6366f1"
        self._accent_soft  = "#ede9fe"
        self._text         = "#1e1e2e"
        self._surface      = "#ffffff"
        self._surface_alt  = "#f1f3f4"
        self._surface_hover= "#e8eaed"
        self._border       = "#e5e7eb"
        self._muted        = "#9ca3af"

        # ── 触发按钮 ─────────────────────────────
        self._btn = QPushButton()
        self._btn.setObjectName("skillDropdownBtn")
        self._btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn.clicked.connect(self._toggle_popup)

        btn_layout = QHBoxLayout(self._btn)
        btn_layout.setContentsMargins(8, 4, 8, 4)
        btn_layout.setSpacing(4)
        self._icon_label = QLabel("⚡")
        self._icon_label.setStyleSheet("border:none; background:transparent; font-size:13px;")
        btn_layout.addWidget(self._icon_label)
        self._text_label = QLabel("选择技能...")
        self._text_label.setStyleSheet("border:none; background:transparent; font-size:12px; font-weight:500;")
        btn_layout.addWidget(self._text_label)
        btn_layout.addStretch()
        self._arrow_label = QLabel("▾")
        self._arrow_label.setStyleSheet("border:none; background:transparent; color:#9ca3af; font-size:12px;")
        btn_layout.addWidget(self._arrow_label)

        # ── 浮动面板 ─────────────────────────────
        self._panel = QFrame(self, Qt.WindowType.Popup)
        self._panel.setObjectName("skillDropdownPanel")
        self._panel.setWindowFlags(Qt.WindowType.Popup)
        self._panel.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._panel.hide()

        panel_vlayout = QVBoxLayout(self._panel)
        panel_vlayout.setContentsMargins(6, 6, 6, 6)
        panel_vlayout.setSpacing(4)

        # 搜索框（含图标）
        search_container = QFrame()
        search_container.setObjectName("skillSearchContainer")
        search_hlayout = QHBoxLayout(search_container)
        search_hlayout.setContentsMargins(4, 2, 4, 2)
        search_hlayout.setSpacing(4)
        self._search_icon = QLabel("🔍")
        self._search_icon.setStyleSheet("border:none; background:transparent; font-size:11px;")
        search_hlayout.addWidget(self._search_icon)
        self._search = QLineEdit()
        self._search.setObjectName("skillDropdownSearch")
        self._search.setPlaceholderText("搜索技能...")
        self._search.textChanged.connect(self._on_search_changed)
        self._search.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        search_hlayout.addWidget(self._search, 1)
        panel_vlayout.addWidget(search_container)

        # 列表视图
        self._list_model = QStandardItemModel()
        self._proxy = QtCore.QSortFilterProxyModel(self)
        self._proxy.setSourceModel(self._list_model)
        self._proxy.setFilterCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self._proxy.setFilterRole(Qt.ItemDataRole.DisplayRole)

        self._list_view = QListView(self._panel)
        self._list_view.setObjectName("skillDropdownList")
        self._list_view.setModel(self._proxy)
        self._list_view.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._list_view.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self._list_view.pressed.connect(self._on_list_pressed)
        panel_vlayout.addWidget(self._list_view, 1)  # stretch=1

        # 事件过滤：点击空白处关闭面板
        self._panel.installEventFilter(self)

        # 布局：按钮填满
        outer = QHBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        outer.addWidget(self._btn)

    # ── 颜色注入 ─────────────────────────────
    def setColors(self, accent: str, accent_soft: str, text: str, muted: str,
                  surface: str = None, surface_alt: str = None,
                  surface_hover: str = None, border: str = None):
        self._accent       = accent
        self._accent_soft  = accent_soft
        self._text         = text
        self._muted        = muted
        if surface:       self._surface       = surface
        if surface_alt:   self._surface_alt   = surface_alt
        if surface_hover: self._surface_hover = surface_hover
        if border:        self._border        = border
        self._apply_btn_style()
        self._apply_panel_style()
        # 刷新所有已有 item 的颜色
        for row in range(self._list_model.rowCount()):
            item = self._list_model.item(row)
            if item:
                self._item_colors(item)

    def _apply_btn_style(self):
        self._btn.setStyleSheet(
            f"#skillDropdownBtn{{"
            f"background:{self._surface_alt};"
            f"color:{self._text};"
            f"border:1px solid {self._border};"
            f"border-radius:18px;"
            f"padding:2px 10px;"
            f"text-align:left;"
            f"}}"
            f"#skillDropdownBtn:hover{{background:{self._surface_hover};}}"
            f"#skillDropdownBtn:pressed{{background:{self._surface};}}"
        )
        self._text_label.setStyleSheet(
            f"color:{self._text}; border:none; background:transparent; font-size:12px; font-weight:500;"
        )
        self._icon_label.setStyleSheet(
            f"color:{self._accent}; border:none; background:transparent; font-size:13px;"
        )
        self._arrow_label.setStyleSheet(
            f"border:none; background:transparent; color:{self._muted}; font-size:12px; padding-left:4px;"
        )

    def _apply_panel_style(self):
        scroll_w = 4
        panel_qss = (
            f"#skillDropdownPanel{{"
            f"background:{self._surface};"
            f"border:1px solid {self._border};"
            f"border-radius:10px;"
            f"box-shadow:0 8px 32px rgba(0,0,0,0.18), 0 2px 8px rgba(0,0,0,0.08);"
            f"}}"
            f"#skillSearchContainer{{"
            f"background:{self._surface_alt};"
            f"border:1px solid {self._border};"
            f"border-radius:6px;"
            f"}}"
            f"#skillDropdownSearch{{"
            f"background:transparent;"
            f"color:{self._text};"
            f"border:none;"
            f"padding:3px 0;"
            f"font-size:12px;"
            f"outline:none;"
            f"}}"
            f"#skillDropdownSearch:focus{{"
            f"outline:none;"
            f"}}"
            f"#skillDropdownSearch::placeholder{{"
            f"color:{self._muted};"
            f"background:transparent;"
            f"}}"
            f"#skillDropdownList{{"
            f"background:transparent;"
            f"border:none;"
            f"outline:none;"
            f"font-size:12px;"
            f"}}"
            f"#skillDropdownList::item{{"
            f"padding:5px 8px 5px 2px;"
            f"border-radius:4px;"
            f"color:{self._text};"
            f"min-height:28px;"
            f"}}"
            f"#skillDropdownList::item:hover{{"
            f"background:{self._surface_hover};"
            f"}}"
            f"#skillDropdownList::item:selected{{"
            f"background:{self._accent_soft};"
            f"color:{self._accent};"
            f"outline:none;"
            f"}}"
            f"#skillDropdownList QScrollBar:vertical{{"
            f"background:transparent; width:{scroll_w}px; margin:2px 0; border-radius:{scroll_w}px;"
            f"}}"
            f"#skillDropdownList QScrollBar::handle:vertical{{"
            f"background:{self._border}; border-radius:{scroll_w}px; min-height:20px;"
            f"}}"
            f"#skillDropdownList QScrollBar::handle:vertical:hover{{"
            f"background:{self._muted};"
            f"}}"
            f"#skillDropdownList QScrollBar::add-line:vertical,"
            f"#skillDropdownList QScrollBar::sub-line:vertical{{"
            f"height:0; background:transparent;"
            f"}}"
            f"#skillDropdownList QScrollBar::add-page:vertical,"
            f"#skillDropdownList QScrollBar::sub-page:vertical{{"
            f"background:transparent;"
            f"}}"
        )
        self._panel.setStyleSheet(panel_qss)

    # ── 事件过滤 ─────────────────────────────
    def eventFilter(self, obj, event):
        if obj is self._panel:
            from PySide6.QtCore import QEvent
            if event.type() == QEvent.Type.MouseButtonPress:
                # 检查点击是否在 _list_view 内（列表内交给 _on_list_pressed）
                gp = self._panel.mapToGlobal(event.pos())
                lv_rect = self._list_view.rect()
                lv_top = self._list_view.mapToGlobal(lv_rect.topLeft())
                if (lv_rect.contains(self._list_view.mapFromGlobal(gp))):
                    return False  # 列表内事件不拦截
                # 搜索框内点击也不拦截
                sr = self._search.rect()
                if sr.contains(self._search.mapFromGlobal(gp)):
                    return False
                # 面板内其他区域点击 -> 关闭
                self._hide_panel()
                return True
        return super().eventFilter(obj, event)

    # ── 弹出/关闭 ─────────────────────────────
    def _toggle_popup(self):
        if self._panel.isVisible():
            self._hide_panel()
        else:
            self._show_panel()

    def _show_panel(self):
        self._search.setText("")
        self._proxy.setFilterFixedString("")
        self._search.setFocus()
        # 定位在按钮下方
        btn_bottom = self._btn.mapToGlobal(self._btn.rect().bottomLeft())
        x = btn_bottom.x()
        y = btn_bottom.y() + 2

        # 避免超出屏幕
        from PySide6.QtWidgets import QApplication
        screen = QApplication.screenAt(self._btn.mapToGlobal(self._btn.rect().center()))
        if screen:
            geo = screen.availableGeometry()
            pw, ph = self._panel.width(), self._panel.height()
            if x + pw > geo.right():
                x = geo.right() - pw
            if y + ph > geo.bottom():
                y = self._btn.mapToGlobal(self._btn.rect().topLeft()).y() - ph - 2

        self._panel.move(x, y)
        self._panel.resize(max(220, self._btn.width() + 20), 240)
        self._panel.show()

    def _hide_panel(self):
        self._panel.hide()
        self._search.clearFocus()

    def _on_search_changed(self, text: str):
        self._proxy.setFilterFixedString(text)

    def _on_list_pressed(self, index: QtCore.QModelIndex):
        src_index = self._proxy.mapToSource(index)
        item = self._list_model.itemFromIndex(src_index)
        if item is None:
            return
        # 切换勾选
        checked = item.checkState() == Qt.CheckState.Unchecked
        item.setCheckState(Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked)
        self._item_colors(item)  # 更新背景色
        self._refresh_display()
        self.selectionChanged.emit(self.selectedNames())

    # ── 数据操作 ─────────────────────────────
    def addCheckItem(self, label: str, name: str, checked: bool = False):
        item = QStandardItem(label)
        item.setData(name, Qt.ItemDataRole.UserRole)
        item.setCheckable(True)
        item.setCheckState(Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked)
        item.setEditable(False)
        self._list_model.appendRow(item)
        self._item_colors(item)  # 初始化背景色
        self._refresh_display()

    def clearItems(self):
        self._list_model.clear()
        self._refresh_display()

    def selectedNames(self) -> list:
        names = []
        for row in range(self._list_model.rowCount()):
            item = self._list_model.item(row)
            if item and item.checkState() == Qt.CheckState.Checked:
                names.append(item.data(Qt.ItemDataRole.UserRole))
        return names

    def setCheckedNames(self, names: list):
        for row in range(self._list_model.rowCount()):
            item = self._list_model.item(row)
            if item:
                n = item.data(Qt.ItemDataRole.UserRole)
                item.setCheckState(Qt.CheckState.Checked if n in names else Qt.CheckState.Unchecked)
                self._item_colors(item)  # 更新所有项的背景色
        self._refresh_display()

    def _item_colors(self, item: QStandardItem):
        """根据勾选状态设置 item 的背景/前景色"""
        checked = item.checkState() == Qt.CheckState.Checked
        if checked:
            item.setBackground(QtGui.QColor(self._accent_soft))
            item.setForeground(QtGui.QColor(self._accent))
        else:
            item.setBackground(QtGui.QBrush())
            item.setForeground(QtGui.QColor(self._text))

    def _refresh_display(self):
        names = self.selectedNames()
        n = len(names)
        if n == 0:
            self._text_label.setText("选择技能...")
        elif n == 1:
            self._text_label.setText(names[0])
        else:
            self._text_label.setText(f"{n} 个技能")
        self._text_label.setToolTip("、".join(names) if names else "")


# ─── 技能标签显示区 ────────────────────────────────

class SkillTagBar(QWidget):
    """在输入框上方用小标签展示已选技能，点 × 取消"""
    tagRemoved = Signal(str)   # 被移除的技能 name

    def __init__(self, parent=None):
        super().__init__(parent)
        self._layout = QHBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(4)
        self._layout.addStretch(1)
        self._tags: dict[str, QWidget] = {}   # name -> widget
        self.setVisible(False)

    def setTags(self, names: list, tokens: dict):
        """用新的技能名列表刷新所有标签"""
        # 先清掉已不在新列表里的
        for name in list(self._tags.keys()):
            if name not in names:
                self._remove_tag_widget(name)
        # 补上新增的
        for name in names:
            if name not in self._tags:
                self._add_tag_widget(name, tokens)
        self.setVisible(bool(self._tags))

    def clearTags(self, tokens: dict = None):
        for name in list(self._tags.keys()):
            self._remove_tag_widget(name)
        self.setVisible(False)

    def _add_tag_widget(self, name: str, tokens: dict):
        accent = tokens.get("accent", "#6366f1")
        accent_soft = tokens.get("accent_soft", "#ede9fe")
        text_color = tokens.get("text", "#1e1e2e")

        tag = QFrame()
        tag.setObjectName("skillTag")
        row = QHBoxLayout(tag)
        row.setContentsMargins(6, 2, 4, 2)
        row.setSpacing(3)

        lbl = QLabel(name)
        lbl.setStyleSheet(f"color:{accent}; font-size:11px; font-weight:500; border:none; background:transparent;")
        row.addWidget(lbl)

        btn_close = QPushButton("×")
        btn_close.setFixedSize(14, 14)
        btn_close.setStyleSheet(
            f"QPushButton{{color:{accent}; background:transparent; border:none; "
            f"font-size:11px; font-weight:700; padding:0; border-radius:7px;}}"
            f"QPushButton:hover{{background:{accent}; color:#fff;}}"
        )
        btn_close.clicked.connect(lambda _checked=False, n=name: self._on_remove(n))
        row.addWidget(btn_close)

        tag.setStyleSheet(
            f"QFrame#skillTag{{background:{accent_soft}; border:none; border-radius:8px;}}"
        )

        # 插到 stretch 之前
        self._layout.insertWidget(self._layout.count() - 1, tag)
        self._tags[name] = tag

    def _remove_tag_widget(self, name: str):
        widget = self._tags.pop(name, None)
        if widget:
            self._layout.removeWidget(widget)
            widget.deleteLater()

    def _on_remove(self, name: str):
        self._remove_tag_widget(name)
        self.setVisible(bool(self._tags))
        self.tagRemoved.emit(name)


# ─── 可嵌入的对话面板 ────────────────────────────

class AIChatWidget(QWidget):
    collapseRequested = Signal()
    aiFocusModeChanged = Signal(bool)  # AI专注模式切换信号，参数为是否进入专注模式

    def __init__(
        self,
        parent=None,
        get_schema_fn=None,
        get_db_info_fn=None,
        list_db_contexts_fn=None,
        list_skill_items_fn=None,
        apply_skill_fn=None,
        execute_fn=None,
    ):
        super().__init__(parent)
        self._get_schema = get_schema_fn or (lambda context_key=None: "")
        self._get_db_info = get_db_info_fn or (lambda context_key=None: {"conn_name": "", "db_name": "", "db_type": "mysql", "label": "默认会话", "key": DEFAULT_HISTORY_KEY})
        self._list_db_contexts = list_db_contexts_fn or (lambda: [])
        self._list_skill_items = list_skill_items_fn or (lambda: [])
        self._apply_skill = apply_skill_fn or (lambda name: False)
        self._execute_fn = execute_fn or (lambda sql: ([], []))

        self.chat_engine = AIChatEngine()
        self._agent: Optional[AIAgent] = None
        self._bubble_widgets: list[_BubbleWidget] = []
        # 两种模式：chat（普通对话）、agent（ReAct Agent）
        self._chat_mode = "chat"
        self._running = False
        self._step_queue = []
        self._history_user_indices: list[int] = []
        self._uploaded_files: list[str] = []
        self._syncing_db_combo = False
        self._input_frame: Optional[QFrame] = None
        self._history_panel: Optional[QWidget] = None
        self._chat_panel: Optional[QWidget] = None
        self._composer_meta_label: Optional[QLabel] = None
        self._model_config_notifier = get_model_config_notifier()
        
        # 加载状态指示器相关
        self._loading_bubble: Optional[_LoadingBubble] = None
        self._request_start_time: Optional[float] = None
        
        # 历史记录导航
        self._history_navigation_index: int = -1
        self._temp_input_buffer: str = ""

        # 专注模式
        self._focus_mode: bool = False


        self.setMinimumWidth(0)
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)

        self._init_ui()
        self._model_config_notifier.changed.connect(self._on_model_config_changed)

        self._refresh_db_contexts()
        self._refresh_model_options(follow_active=True)
        self._refresh_skill_options()
        self._load_history_to_ui()
        self.update_context()


    def minimumSizeHint(self):
        return QSize(0, 0)

    # ── 基础工具 ─────────────────────────────────

    @staticmethod
    def _split_history_key(history_key: str) -> tuple[str, str, str]:
        key = (history_key or "").strip()
        if not key or key == DEFAULT_HISTORY_KEY:
            return "", "", ""
        parts = key.split("|", 2)
        conn_name = parts[0] if len(parts) > 0 else ""
        db_name = parts[1] if len(parts) > 1 else ""
        db_type = parts[2] if len(parts) > 2 else ""
        return conn_name, db_name, db_type

    def _normalize_context(self, info) -> dict:
        if isinstance(info, dict):
            raw_key = info.get("key") or info.get("history_key") or AIChatEngine.make_history_key(
                info.get("conn_name", ""), info.get("db_name", ""), info.get("db_type", "")
            )
            conn_name = info.get("conn_name", "")
            db_name = info.get("db_name", "")
            db_type = info.get("db_type", "mysql") or "mysql"
            if raw_key and raw_key != DEFAULT_HISTORY_KEY and (not conn_name or not db_name):
                key_conn, key_db, key_type = self._split_history_key(raw_key)
                conn_name = conn_name or key_conn
                db_name = db_name or key_db
                db_type = db_type or key_type or "mysql"
            label = info.get("label")
            if not label:
                if conn_name and db_name:
                    label = f"{conn_name} · {db_name}"
                else:
                    label = conn_name or db_name or "默认会话"
            return {
                "key": raw_key or DEFAULT_HISTORY_KEY,
                "label": label,
                "conn_name": conn_name,
                "db_name": db_name,
                "db_type": db_type or "mysql",
            }
        if isinstance(info, tuple):
            conn_name = info[0] if len(info) > 0 else ""
            db_type = info[1] if len(info) > 1 else "mysql"
            db_name = info[2] if len(info) > 2 else ""
            label = f"{conn_name} · {db_name or '默认库'}" if conn_name else "默认会话"
            return {
                "key": AIChatEngine.make_history_key(conn_name, db_name, db_type),
                "label": label,
                "conn_name": conn_name,
                "db_name": db_name,
                "db_type": db_type or "mysql",
            }
        return {
            "key": DEFAULT_HISTORY_KEY,
            "label": "默认会话",
            "conn_name": "",
            "db_name": "",
            "db_type": "mysql",
        }

    def _selected_context(self) -> dict:
        data = self.db_selector.currentData() if hasattr(self, "db_selector") else None
        if isinstance(data, dict):
            return self._normalize_context(data)
        return self._normalize_context(self._get_db_info(None))

    def _selected_history_key(self) -> str:
        return self._selected_context().get("key", DEFAULT_HISTORY_KEY)

    def _selected_schema(self) -> str:
        try:
            return self._get_schema(self._selected_history_key()) or ""
        except TypeError:
            return self._get_schema() or ""
        except Exception:
            return ""

    def _selected_db_info(self) -> dict:
        try:
            return self._normalize_context(self._get_db_info(self._selected_history_key()))
        except TypeError:
            return self._normalize_context(self._get_db_info())
        except Exception:
            return self._selected_context()

    def _find_context_index(self, combo: QComboBox, context_key: str) -> int:
        target = (context_key or "").strip()
        if not target:
            return -1
        for idx in range(combo.count()):
            data = combo.itemData(idx)
            if isinstance(data, dict) and data.get("key") == target:
                return idx
        return -1

    def _set_combo_context(self, combo: QComboBox, context_key: str):
        idx = self._find_context_index(combo, context_key)
        if idx >= 0:
            combo.setCurrentIndex(idx)

    @staticmethod
    def _is_image_file(path: str) -> bool:
        return os.path.splitext(path or "")[1].lower() in {
            ".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".svg",
        }

    def _context_mention(self, context: Optional[dict] = None) -> str:
        ctx = self._normalize_context(context or self._selected_context())
        if ctx.get("key") == DEFAULT_HISTORY_KEY and not ctx.get("conn_name"):
            return "@db:默认会话"
        return f"@db:{ctx.get('label', '默认会话')}"

    def _attachment_mention(self, path: str) -> str:
        prefix = "@image" if self._is_image_file(path) else "@file"
        return f"{prefix}:{os.path.basename(path)}"

    def _insert_text_at_cursor(self, text: str):
        if not text or not hasattr(self, "input_box"):
            return
        cursor = self.input_box.textCursor()
        current = self.input_box.toPlainText()
        prefix = "" if not current or current.endswith((" ", "\n")) else " "
        cursor.insertText(f"{prefix}{text} ")
        self.input_box.setTextCursor(cursor)
        self.input_box.setFocus()

    def _set_context_by_index(self, index: int, insert_mention: bool = True):
        if index < 0 or index >= self.db_selector.count():
            return
        self.db_selector.setCurrentIndex(index)
        if insert_mention:
            self._insert_text_at_cursor(self._context_mention(self.db_selector.itemData(index)))
        self._update_file_tip()

    def _open_db_context_menu(self, anchor_global: Optional[QPoint] = None, insert_mention: bool = True):
        menu = QMenu(self)
        for idx in range(self.db_selector.count()):
            ctx = self.db_selector.itemData(idx)
            label = self.db_selector.itemText(idx)
            action = menu.addAction(label)
            action.setCheckable(True)
            action.setChecked(idx == self.db_selector.currentIndex())
            action.triggered.connect(lambda _checked=False, i=idx, _ctx=ctx: self._set_context_by_index(i, insert_mention=insert_mention))
        if menu.isEmpty():
            return
        point = anchor_global
        if point is None:
            if hasattr(self, "btn_db_picker"):
                point = self.btn_db_picker.mapToGlobal(self.btn_db_picker.rect().bottomLeft())
            else:
                point = self.mapToGlobal(QPoint(0, 0))
        menu.exec(point)

    def _sync_attachment_mentions(self, paths: list[str]):
        if not paths:
            return
        existing = {os.path.normcase(p): p for p in self._uploaded_files}
        inserted_tags = []
        for path in paths:
            norm = os.path.normcase(path)
            if norm in existing:
                continue
            existing[norm] = path
            self._uploaded_files.append(path)
            inserted_tags.append(self._attachment_mention(path))
        if inserted_tags:
            self._insert_text_at_cursor(" ".join(inserted_tags))
        self._update_file_tip()

    def _composer_placeholder_text(self) -> str:
        if self._chat_mode == "agent":
            return "给团子描述任务目标，Agent 会结合当前数据库上下文自动拆解执行…"
        return "给团子发消息，输入 @ 选择数据库，点击 " + Icon.char('attachment') + " 添加附件"

    # ── UI 构建 ──────────────────────────────────

    def _init_ui(self):
        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setChildrenCollapsible(True)
        splitter.setCollapsible(0, True)
        splitter.setCollapsible(1, True)
        splitter.addWidget(self._build_history_panel())
        splitter.addWidget(self._build_chat_panel())
        splitter.setSizes([0, 728])  # 默认隐藏历史面板
        splitter.setHandleWidth(0)  # 禁用拖动，只通过按钮切换显示
        self._history_splitter = splitter

        root.addWidget(splitter)

        # 为 AI 对话模块添加 Ctrl+F11 快捷键
        from PySide6.QtGui import QShortcut, QKeySequence
        focus_shortcut = QShortcut(QKeySequence("Ctrl+F11"), self)
        focus_shortcut.activated.connect(self._on_focus_mode_toggled)

        self._apply_theme_styles()

    def _build_history_panel(self):
        panel = QWidget()
        panel.setMinimumWidth(156)
        panel.setMaximumWidth(246)
        self._history_panel = panel

        layout = QVBoxLayout(panel)
        layout.setContentsMargins(10, 12, 10, 12)
        layout.setSpacing(8)

        self.history_title = QLabel("最近会话")
        self.history_title.setProperty("role", "sectionTitle")
        layout.addWidget(self.history_title)

        self.history_hint = QLabel("按数据库上下文切换和回看最近消息")

        self.history_hint.setProperty("role", "sectionHint")
        self.history_hint.setWordWrap(True)
        layout.addWidget(self.history_hint)

        self.history_db_combo = QComboBox()
        self.history_db_combo.currentIndexChanged.connect(self._on_history_db_changed)
        self.history_db_combo.setToolTip("切换当前查看的数据库上下文")
        layout.addWidget(self.history_db_combo)

        self.history_list = QListWidget()
        self.history_list.itemClicked.connect(self._on_history_item_click)
        layout.addWidget(self.history_list, stretch=1)

        self.btn_clear_history = QPushButton("清空当前会话")
        self.btn_clear_history.setFixedHeight(28)
        self.btn_clear_history.clicked.connect(self._on_clear_history)
        layout.addWidget(self.btn_clear_history)
        return panel

    def _toggle_history_panel(self):
        """切换最近会话面板的显示/隐藏（带动画）"""
        splitter = getattr(self, "_history_splitter", None)
        if splitter is None:
            return
        
        from PySide6.QtCore import QPropertyAnimation, QEasingCurve
        
        current_sizes = splitter.sizes()
        is_visible = current_sizes[0] > 0
        
        # 创建尺寸动画
        if is_visible:
            # 隐藏面板
            target_sizes = [0, current_sizes[0] + current_sizes[1]]
            self.btn_toggle_history.setChecked(False)
            self.btn_toggle_history.setIcon(Icon.svg_icon('历史记录.svg', 16))
            self.btn_toggle_history.setToolTip("显示最近会话")
        else:
            # 显示面板
            target_sizes = [168, max(0, current_sizes[1] - 168)]
            self.btn_toggle_history.setChecked(True)
            self.btn_toggle_history.setIcon(Icon.svg_icon('历史记录-当前.svg', 16))
            self.btn_toggle_history.setToolTip("隐藏最近会话")
        
        # 使用QTimer逐步动画化splitter sizes
        # 注意：QSplitter不支持直接的属性动画，所以我们用定时器模拟
        if not hasattr(self, '_panel_animation_step'):
            self._panel_animation_step = 0
        
        total_steps = 10  # 动画分为10步
        start_sizes = current_sizes[:]
        
        def animate_panel():
            self._panel_animation_step += 1
            progress = self._panel_animation_step / total_steps
            
            # 使用缓动函数
            ease_progress = 1 - (1 - progress) ** 3  # OutCubic
            
            # 计算中间状态
            current_width = int(start_sizes[0] + (target_sizes[0] - start_sizes[0]) * ease_progress)
            current_width = max(0, current_width)
            
            new_sizes = [current_width, start_sizes[0] + start_sizes[1] - current_width]
            splitter.setSizes(new_sizes)
            
            if self._panel_animation_step < total_steps:
                QTimer.singleShot(16, animate_panel)  # ~60fps
            else:
                # 确保最终状态正确
                splitter.setSizes(target_sizes)
                self._panel_animation_step = 0
        
        # 启动动画
        self._panel_animation_step = 0
        animate_panel()

    def _on_focus_mode_toggled(self):
        """
        AI 对话专注模式：收起SQL工作台，AI对话独占屏幕
        通过发射信号通知 main_window 收起 SQL 工作台区域
        """
        self._focus_mode = not self._focus_mode

        # 发射信号通知 main_window 收起/恢复 SQL 工作台
        self.aiFocusModeChanged.emit(self._focus_mode)

        if self._focus_mode:
            # 更新按钮状态
            self.btn_focus.setChecked(True)
            self.btn_focus.setIcon(Icon.qicon('fullscreen-exit', 14))
            self.btn_focus.setToolTip("退出专注模式 (Ctrl+F11)")
        else:
            # 更新按钮状态
            self.btn_focus.setChecked(False)
            self.btn_focus.setIcon(Icon.qicon('fullscreen', 14))
            self.btn_focus.setToolTip("专注模式：收起SQL工作台 (Ctrl+F11)")

    def _build_chat_panel(self):
        panel = QWidget()
        self._chat_panel = panel
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(10, 8, 10, 10)
        layout.setSpacing(8)

        top_row = QHBoxLayout()
        top_row.setContentsMargins(0, 0, 0, 0)
        top_row.setSpacing(10)

        title_col = QVBoxLayout()
        title_col.setContentsMargins(0, 0, 0, 0)
        title_col.setSpacing(3)

        self.lbl_chat_title = QLabel("团子")
        self.lbl_chat_title.setProperty("role", "panelTitle")
        title_col.addWidget(self.lbl_chat_title)

        self.lbl_chat_subtitle = QLabel("像微信/QQ 一样直接发消息；需要自动处理时切到 Agent")
        self.lbl_chat_subtitle.setProperty("role", "sectionHint")
        title_col.addWidget(self.lbl_chat_subtitle)

        self.lbl_schema_status = QLabel("")
        self.lbl_schema_status.setWordWrap(False)
        self.lbl_schema_status.setVisible(False)
        title_col.addWidget(self.lbl_schema_status, 0, Qt.AlignmentFlag.AlignLeft)

        top_row.addLayout(title_col)
        top_row.addStretch(1)


        # 历史面板切换按钮 - 放大图标，去掉边框背景
        self.btn_toggle_history = QToolButton()
        self.btn_toggle_history.setIcon(Icon.svg_icon('历史记录.svg', 20))
        self.btn_toggle_history.setIconSize(QSize(20, 20))
        self.btn_toggle_history.setToolTip("显示最近会话")
        self.btn_toggle_history.setFixedSize(28, 28)
        self.btn_toggle_history.setStyleSheet(
            "QToolButton { border: none; background: transparent; padding: 0px; outline: none; }"
            "QToolButton:hover { background: transparent; border: none; outline: none; }"
            "QToolButton:pressed { background: transparent; border: none; outline: none; }"
        )
        self.btn_toggle_history.clicked.connect(self._toggle_history_panel)
        self.btn_toggle_history.setCheckable(True)
        self.btn_toggle_history.setChecked(False)
        top_row.addWidget(self.btn_toggle_history)

        mode_frame = QFrame()
        self.mode_frame = mode_frame
        mode_layout = QHBoxLayout(mode_frame)
        mode_layout.setContentsMargins(0, 0, 0, 0)
        mode_layout.setSpacing(0)

        # 两种模式：chat（普通对话）、agent（ReAct Agent）
        self.btn_chat_mode = QPushButton("对话")
        self.btn_agent_mode = QPushButton("Agent")
        for btn in (self.btn_chat_mode, self.btn_agent_mode):
            btn.setFixedHeight(24)
            btn.setCheckable(True)
            btn.setProperty("chatModeButton", True)
        # 初始状态同步
        if self._chat_mode == "agent":
            self.btn_agent_mode.setChecked(True)
        else:
            self.btn_chat_mode.setChecked(True)
        self.btn_chat_mode.clicked.connect(lambda: self._switch_mode("chat"))
        self.btn_agent_mode.clicked.connect(lambda: self._switch_mode("agent"))
        mode_layout.addWidget(self.btn_chat_mode)
        mode_layout.addWidget(self.btn_agent_mode)
        top_row.addWidget(mode_frame)

        # 专注模式按钮 - 放大图标
        self.btn_focus = QToolButton()
        self.btn_focus.setIcon(Icon.qicon('fullscreen', 18))
        self.btn_focus.setIconSize(QSize(18, 18))
        self.btn_focus.setToolTip("专注模式：收起SQL工作台 (Ctrl+F11)")
        self.btn_focus.setFixedSize(28, 28)
        self.btn_focus.setStyleSheet(
            "QToolButton { border: none; background: transparent; padding: 0px; outline: none; }"
            "QToolButton:hover { background: transparent; border: none; outline: none; }"
            "QToolButton:pressed { background: transparent; border: none; outline: none; }"
        )
        self.btn_focus.clicked.connect(self._on_focus_mode_toggled)
        self.btn_focus.setCheckable(True)
        top_row.addWidget(self.btn_focus)

        # 收起按钮 - 放大图标
        self.btn_collapse = QToolButton()
        self.btn_collapse.setIcon(Icon.svg_icon('关闭.svg', 18))
        self.btn_collapse.setIconSize(QSize(18, 18))
        self.btn_collapse.setToolTip("收起右侧 AI 对话区，可通过工具栏再次打开")
        self.btn_collapse.setFixedSize(28, 28)
        self.btn_collapse.setStyleSheet(
            "QToolButton { border: none; background: transparent; padding: 0px; outline: none; }"
            "QToolButton:hover { background: transparent; border: none; outline: none; }"
            "QToolButton:pressed { background: transparent; border: none; outline: none; }"
        )
        self.btn_collapse.clicked.connect(self.collapseRequested.emit)
        top_row.addWidget(self.btn_collapse)
        layout.addLayout(top_row)

        self.agent_tip = QLabel("Agent 会沿用当前数据库和模型，自动拆步骤执行。")
        self.agent_tip.setWordWrap(True)
        self.agent_tip.setVisible(False)  # 初始隐藏，根据模式动态显示
        layout.addWidget(self.agent_tip)

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        self.chat_container = QWidget()
        self.chat_layout = QVBoxLayout(self.chat_container)
        self.chat_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.chat_layout.setSpacing(8)
        self.chat_layout.setContentsMargins(4, 10, 4, 10)

        self._welcome_label = QLabel("开始聊吧：@ 选数据库，" + Icon.styled_char('attachment') + " 加附件，Enter 发送；双击消息可快速复制。")
        self._welcome_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._welcome_label.setWordWrap(True)
        self.chat_layout.addWidget(self._welcome_label)


        self.scroll_area.setWidget(self.chat_container)
        layout.addWidget(self.scroll_area, stretch=1)

        self.lbl_status = QLabel("")
        self.lbl_status.setWordWrap(True)
        self.lbl_status.setVisible(False)
        layout.addWidget(self.lbl_status)

        input_frame = QFrame()
        self._input_frame = input_frame
        input_outer = QVBoxLayout(input_frame)
        input_outer.setContentsMargins(10, 10, 10, 10)
        input_outer.setSpacing(8)

        top_row = QHBoxLayout()
        top_row.setContentsMargins(0, 0, 0, 0)
        top_row.setSpacing(6)

        self.btn_db_picker = QToolButton()
        self.btn_db_picker.setText("@")
        self.btn_db_picker.setToolTip("选择数据库上下文")
        self.btn_db_picker.setFixedSize(28, 28)
        self.btn_db_picker.clicked.connect(lambda: self._open_db_context_menu(insert_mention=True))
        top_row.addWidget(self.btn_db_picker)

        self.btn_upload = QToolButton()
        self.btn_upload.setText(Icon.char('attachment'))
        self.btn_upload.setFont(Icon.font(14))
        self.btn_upload.setToolTip("上传文件")
        self.btn_upload.setFixedSize(28, 28)
        self.btn_upload.clicked.connect(self._on_upload_files)
        top_row.addWidget(self.btn_upload)

        self.db_selector = QComboBox()
        self.db_selector.currentIndexChanged.connect(self._on_send_db_changed)
        self.db_selector.setVisible(False)

        self.file_tip = QLabel("")
        self.file_tip.setWordWrap(False)
        self.file_tip.setFixedHeight(26)
        self.file_tip.setMaximumWidth(360)
        self.file_tip.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self.file_tip.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed)
        self._composer_meta_label = self.file_tip
        top_row.addWidget(self.file_tip)
        top_row.addStretch(1)

        input_outer.addLayout(top_row)
        
        # 图片缩略图区域
        self.thumbnail_container = QWidget()
        self.thumbnail_layout = QHBoxLayout(self.thumbnail_container)
        self.thumbnail_layout.setContentsMargins(0, 4, 0, 4)
        self.thumbnail_layout.setSpacing(6)
        self.thumbnail_container.setVisible(False)  # 默认隐藏
        input_outer.addWidget(self.thumbnail_container)

        self.input_box = QTextEdit()
        self.input_box.setPlaceholderText(self._composer_placeholder_text())
        self.input_box.setFont(QFont("Microsoft YaHei", 10))
        self.input_box.setMaximumHeight(156)
        self.input_box.setMinimumHeight(84)
        self.input_box.installEventFilter(self)
        
        # 启用拖拽支持
        self.input_box.setAcceptDrops(True)
        self.input_box.dragEnterEvent = self._on_drag_enter
        self.input_box.dragMoveEvent = self._on_drag_move
        self.input_box.dropEvent = self._on_drop
        
        input_outer.addWidget(self.input_box)

        # 技能标签显示区（在输入框和底部按钮栏之间）
        self.skill_tag_bar = SkillTagBar()
        self.skill_tag_bar.tagRemoved.connect(self._on_skill_tag_removed)
        input_outer.addWidget(self.skill_tag_bar)

        bottom_row = QHBoxLayout()
        bottom_row.setContentsMargins(0, 0, 0, 0)
        bottom_row.setSpacing(8)

        selector_row = QHBoxLayout()
        selector_row.setContentsMargins(0, 0, 0, 0)
        selector_row.setSpacing(6)

        self.model_selector = QComboBox()
        self.model_selector.setMinimumWidth(140)
        self.model_selector.setSizePolicy(QSizePolicy.Policy.MinimumExpanding, QSizePolicy.Policy.Fixed)
        self.model_selector.currentIndexChanged.connect(self._on_model_changed)
        selector_row.addWidget(self.model_selector, 1)  # stretch=1 让它可以扩展

        # 技能选择器（浮动面板多选）
        self.skill_selector = SkillDropdownSelector()
        self.skill_selector.setMinimumWidth(100)
        self.skill_selector.setSizePolicy(QSizePolicy.Policy.MinimumExpanding, QSizePolicy.Policy.Fixed)
        self.skill_selector.selectionChanged.connect(self._on_skill_selection_changed)
        selector_row.addWidget(self.skill_selector, 0)  # 不扩展

        bottom_row.addLayout(selector_row, 0)
        bottom_row.addStretch(1)

        self.lbl_hint = QLabel("Enter 发送 · Shift+Enter 换行")
        self.lbl_hint.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Preferred)
        bottom_row.addWidget(self.lbl_hint)

        self._btn_stop = QPushButton("停止")
        self._btn_stop.setFixedSize(64, 30)
        self._btn_stop.setVisible(False)
        self._btn_stop.clicked.connect(self._on_stop)
        bottom_row.addWidget(self._btn_stop)

        self._btn_send = QPushButton("发送")
        self._btn_send.setFixedSize(76, 32)
        self._btn_send.clicked.connect(self._on_send)
        bottom_row.addWidget(self._btn_send)

        input_outer.addLayout(bottom_row)

        self._update_file_tip()
        layout.addWidget(input_frame)
        return panel



    def _apply_theme_styles(self):
        tokens = _tokens()
        accent = tokens["accent"]
        accent_hover = tokens.get("accent_hover", accent)
        accent_pressed = tokens.get("accent_pressed", accent)
        accent_soft = tokens["accent_soft"]
        text = tokens["text"]
        text_soft = tokens.get("text_soft", text)
        muted = tokens["text_muted"]
        surface = tokens["surface"]
        surface_alt = tokens["surface_alt"]
        surface_hover = tokens.get("surface_hover", surface_alt)
        surface_muted = tokens["surface_muted"]
        border = tokens["border"]
        border_strong = tokens.get("border_strong", border)
        danger = tokens["danger"]
        danger_hover = tokens.get("danger_hover", danger)
        scroll_handle = tokens.get("scroll_handle", "#bcc8d9")
        scroll_handle_hover = tokens.get("scroll_handle_hover", "#8b9bb0")

        if self._history_panel is not None:
            self._history_panel.setStyleSheet(
                f"background:{surface};"
            )
        if self._chat_panel is not None:
            self._chat_panel.setStyleSheet(f"background:{surface_muted};")
        if hasattr(self, "history_hint"):
            self.history_hint.setStyleSheet(f"color:{muted}; font-size:11px;")

        if hasattr(self, "history_db_combo"):
            self.history_db_combo.setStyleSheet(
                f"QComboBox{{background:{surface_alt}; border:none; border-radius: 4px; padding:4px 8px; color:{text};}}"
                f"QComboBox:hover{{background:{surface_muted};}}"
                f"QComboBox QAbstractItemView{{background:{surface}; color:{text}; selection-background-color:{accent_soft}; selection-color:{accent}; border:none; border-radius:4px;}}"
            )
        if hasattr(self, "history_list"):
            self.history_list.setStyleSheet(
                f"QListWidget{{border:none; background:transparent; outline:none; color:{text};}}"
                f"QListWidget::item{{padding:9px 8px; border-radius: 4px; margin:2px 0; color:{text}; background:transparent;}}"
                f"QListWidget::item:hover{{background:{surface_muted};}}"
                f"QListWidget::item:selected{{background:{accent_soft}; color:{accent}; border:none;}}"
            )
        if hasattr(self, "btn_clear_history"):
            self.btn_clear_history.setStyleSheet(
                f"QPushButton{{background:{danger}; color:#fff; border:none; border-radius: 4px; padding:4px 10px; font-weight:600;}}"
                f"QPushButton:hover{{background:{danger_hover};}}"
            )
        if hasattr(self, "mode_frame"):
            self.mode_frame.setStyleSheet(
                f"QFrame{{background:{surface_muted}; border:none; border-radius: 4px;}}"
            )
        for btn in (getattr(self, "btn_chat_mode", None), getattr(self, "btn_agent_mode", None)):
            if btn is not None:
                btn.setStyleSheet(
                    f"QPushButton{{border:none; border-radius: 4px; padding:2px 10px; font-size:11px; font-weight:600; color:{muted}; background:transparent;}}"
                    f"QPushButton:checked{{background:{surface}; color:{accent};}}"
                )
        if hasattr(self, "lbl_schema_status"):
            self.lbl_schema_status.setStyleSheet(
                f"background:{surface}; color:{accent}; border:none; border-radius: 4px; padding:2px 8px; font-size:10px; font-weight:600;"
            )
        if hasattr(self, "lbl_chat_subtitle"):
            self.lbl_chat_subtitle.setStyleSheet(f"color:{muted}; font-size:11px;")
        if hasattr(self, "agent_tip"):
            self.agent_tip.setStyleSheet(
                f"background:{surface}; color:{accent}; border:none; border-radius: 4px; padding:6px 10px; font-size:11px;"
            )

        if hasattr(self, "scroll_area"):
            self.scroll_area.setStyleSheet(
                f"QScrollArea{{border:none; background:transparent;}}"
                f"QWidget{{background:transparent;}}"
            )
        if hasattr(self, "chat_container"):
            self.chat_container.setStyleSheet("background: transparent;")
        if getattr(self, "_welcome_label", None) is not None:
            self._welcome_label.setStyleSheet(
                f"background:{surface}; color:{text_soft}; border:none; border-radius: 4px; padding:10px 16px; font-size:12px;"
            )
        if hasattr(self, "lbl_status"):
            self.lbl_status.setStyleSheet(self._status_style(self.lbl_status.text()))
        if self._input_frame is not None:
            self._input_frame.setStyleSheet(
                f"QFrame{{background:{surface}; border:none; border-radius: 4px;}}"
            )


        # 模型选择器美化样式
        model_combo_style = (
            f"QComboBox#model_selector{{"
            f"background:{surface_alt};"
            f"color:{text};"
            f"border:none;"
            f"border-radius: 4px;"
            f"padding:4px 10px 4px 24px;"
            f"padding-right:24px;"
            f"font-size:12px;"
            f"font-weight:500;"
            f"}}"
            f"QComboBox#model_selector:hover{{"
            f"background:{surface_hover};"
            f"}}"
            f"QComboBox#model_selector:focus{{"
            f"background:{surface};"
            f"border:1px solid {accent};"
            f"padding:3px 9px 3px 23px;"
            f"}}"
            f"QComboBox#model_selector::drop-down{{"
            f"border:none;"
            f"width:20px;"
            f"subcontrol-origin:padding;"
            f"subcontrol-position:right center;"
            f"}}"
            f"QComboBox#model_selector::down-arrow{{"
            f"image:none;"
            f"border-left:5px solid transparent;"
            f"border-right:5px solid transparent;"
            f"border-top:6px solid {muted};"
            f"margin-right:4px;"
            f"}}"
            f"QComboBox#model_selector QAbstractItemView{{"
            f"background:{surface};"
            f"color:{text};"
            f"selection-background-color:{accent_soft};"
            f"selection-color:{accent};"
            f"border:1px solid {border};"
            f"border-radius: 4px;"
            f"outline:0;"
            f"padding:4px;"
            f"}}"
            f"QComboBox#model_selector QAbstractItemView::item{{"
            f"padding:6px 10px;"
            f"border-radius: 2px;"
            f"margin:1px 2px;"
            f"}}"
            f"QComboBox#model_selector QAbstractItemView::item:hover{{"
            f"background:{surface_hover};"
            f"}}"
        )

        # 通用下拉框样式（数据库选择器等）
        combo_style = (
            f"QComboBox{{"
            f"background:{surface_alt};"
            f"color:{text};"
            f"border:none;"
            f"border-radius: 4px;"
            f"padding:4px 10px;"
            f"padding-right:24px;"
            f"font-size:12px;"
            f"}}"
            f"QComboBox:hover{{background:{surface_hover};}}"
            f"QComboBox:focus{{background:{surface};border:1px solid {accent};padding:3px 9px;}}"
            f"QComboBox::drop-down{{border:none;width:20px;subcontrol-origin:padding;subcontrol-position:right center;}}"
            f"QComboBox::down-arrow{{image:none;border-left:5px solid transparent;border-right:5px solid transparent;border-top:6px solid {muted};margin-right:4px;}}"
            f"QComboBox QAbstractItemView{{background:{surface};color:{text};selection-background-color:{accent_soft};selection-color:{accent};border:1px solid {border};border-radius: 4px;outline:0;padding:4px;}}"
            f"QComboBox QAbstractItemView::item{{padding:6px 10px;border-radius:2px;margin:1px 2px;}}"
            f"QComboBox QAbstractItemView::item:hover{{background:{surface_hover};}}"
        )

        # 为模型选择器设置样式
        if hasattr(self, "model_selector") and self.model_selector is not None:
            self.model_selector.setStyleSheet(model_combo_style)

        # 为数据库选择器设置通用样式
        if hasattr(self, "db_selector") and self.db_selector is not None:
            self.db_selector.setStyleSheet(combo_style)

        # 技能选择器（SkillDropdownSelector 自带样式，通过 setColors 注入主题色）
        if hasattr(self, "skill_selector") and self.skill_selector is not None:
            self.skill_selector.setColors(
                accent, accent_soft, text, muted,
                surface=surface, surface_alt=surface_alt,
                surface_hover=surface_hover, border=border
            )

        # 刷新技能标签栏颜色
        if hasattr(self, "skill_tag_bar") and self.skill_tag_bar is not None:
            sel = self.skill_selector.selectedNames() if hasattr(self, "skill_selector") else []
            self.skill_tag_bar.setTags(sel, tokens)
        neutral_btn_style = (
            f"QPushButton, QToolButton{{background:{surface}; color:{text_soft}; border:none; border-radius: 4px; padding:2px 6px; font-weight:600;}}"
            f"QPushButton:hover, QToolButton:hover{{color:{accent}; background:{accent_soft};}}"
            f"QPushButton:pressed, QToolButton:pressed{{padding-top:3px; padding-left:7px;}}"
        )

        tool_btn_style = (
            f"QToolButton{{background:{surface}; color:{text_soft}; border:none; border-radius: 4px; padding:2px 6px; font-weight:600;}}"
            f"QToolButton:hover{{color:{accent}; background:{surface_muted};}}"
            f"QToolButton:pressed{{padding-top:3px; padding-left:7px;}}"
        )

        for btn in (
            getattr(self, "btn_collapse", None),
        ):
            if btn is not None:
                btn.setStyleSheet(neutral_btn_style)
        for btn in (
            getattr(self, "btn_upload", None),
            getattr(self, "btn_db_picker", None),
            getattr(self, "btn_toggle_history", None),
        ):
            if btn is not None:
                btn.setStyleSheet(tool_btn_style)
        if hasattr(self, "_btn_stop"):
            self._btn_stop.setStyleSheet(
                f"QPushButton{{background:{danger}; color:#fff; border:none; border-radius: 4px; padding:2px 10px; font-weight:600;}}"
                f"QPushButton:hover{{background:{danger_hover};}}"
                f"QPushButton:pressed{{padding-top:3px; padding-left:11px;}}"
            )
        if hasattr(self, "_btn_send"):
            self._btn_send.setStyleSheet(
                f"QPushButton{{background:{accent}; color:#fff; border:none; border-radius: 4px; padding:2px 12px; font-weight:600;}}"
                f"QPushButton:hover{{background:{accent_hover};}}"
                f"QPushButton:pressed{{padding-top:3px; padding-left:13px;}}"
                f"QPushButton:disabled{{background:{surface_muted}; color:{muted}; border-color:{surface_muted};}}"
            )
        if hasattr(self, "input_box"):
            self.input_box.setStyleSheet(
                f"QTextEdit{{border:none; background:transparent; color:{text}; padding:2px 0 4px 0; selection-background-color:{tokens['selection_bg']};}}"
            )
        if hasattr(self, "lbl_hint"):
            self.lbl_hint.setStyleSheet(f"font-size:10px; color:{muted}; border:none;")
        if hasattr(self, "file_tip"):
            self.file_tip.setStyleSheet(
                f"font-size:10px; color:{text_soft}; border:none;"
                f"background:{surface_muted}; border-radius: 4px; padding:2px 6px;"
            )




    def refresh_theme(self, _theme: Optional[str] = None):
        current_input = self.input_box.toPlainText() if hasattr(self, "input_box") else ""
        current_key = self._selected_history_key()
        # 先刷新所有选项（clear 可能重置样式）
        self._refresh_model_options()
        self._refresh_skill_options()
        self._refresh_db_contexts(preferred_key=current_key)
        # 最后应用主题样式（覆盖 clear 后的默认样式）
        self._apply_theme_styles()
        self._reload_chat_from_history()
        if hasattr(self, "input_box"):
            self.input_box.setPlainText(current_input)
        self.update_context()

    def refresh_model_config(self, follow_active: bool = True):
        self._refresh_model_options(follow_active=follow_active)
        self.update_context()

    def _on_model_config_changed(self, _config: dict):
        # 配置变化时刷新模型选择器
        self.refresh_model_config(follow_active=True)

    def refresh_contexts(self, preferred_key: str = ""):
        self._refresh_db_contexts(preferred_key=preferred_key or self._selected_history_key())
        self._reload_chat_from_history()
        self.update_context()

    def refresh_skills(self):
        self._refresh_skill_options()

    def _refresh_bubble_layout(self):
        for bubble in self._bubble_widgets:
            bubble.resize_msg()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        QTimer.singleShot(0, self._refresh_bubble_layout)

    # ── 下拉数据刷新 ─────────────────────────────

    def _refresh_db_contexts(self, preferred_key: str = ""):
        contexts = []
        seen = set()
        current = self._normalize_context(self._get_db_info(None))

        def add_context(item):
            ctx = self._normalize_context(item)
            if ctx["key"] in seen:
                return
            contexts.append(ctx)
            seen.add(ctx["key"])

        if current.get("key") != DEFAULT_HISTORY_KEY or current.get("conn_name"):
            add_context(current)

        for item in self._list_db_contexts() or []:
            add_context(item)

        for group in self.chat_engine.list_history_groups():
            add_context(group)

        if not contexts:
            contexts.append(current)

        target_key = preferred_key or self._selected_history_key() or current.get("key", DEFAULT_HISTORY_KEY)
        self._syncing_db_combo = True
        try:
            for combo in (self.db_selector, self.history_db_combo):
                combo.clear()
                for ctx in contexts:
                    combo.addItem(ctx["label"], ctx)
            idx = self._find_context_index(self.db_selector, target_key)
            if idx < 0:
                idx = 0
            self.db_selector.setCurrentIndex(idx)
            self.history_db_combo.setCurrentIndex(idx)
        finally:
            self._syncing_db_combo = False
        self._update_file_tip()


    def _refresh_model_options(self, follow_active: bool = False):
        cfg = ModelConfig()
        # 正常读取 active_provider，Hermes 复用当前选中的模型
        active_provider = cfg.config.get("active_provider", "openai")
        active_model = cfg.get_active().get("model", "")
        options = []
        seen = set()
        
        def _get_provider_icon(provider: str):
            """根据提供商返回图标名称"""
            provider = provider.lower()
            icon_map = {
                "openai": "robot",
                "deepseek": "sparkling",  # 星形图标
                "anthropic": "user_voice",  # 用户语音
                "litellm": "api",  # API
                "bedrock": "server",  # 服务器
                "ollama": "cpu",  # CPU
                "qwen": "chat_smile",  # 阿里模型
                "doubao": "chat_smile",  # 豆包
                "kimi": "search",  # 搜索
                "glm": "chat_smile",  # GLM
                "minimax": "chat_smile",  # MiniMax
                "agent": "magic",
            }
            return icon_map.get(provider, "code")  # 默认代码图标

        def add_option(provider: str, model: str):
            provider = (provider or "").strip()
            model = (model or "").strip()
            if not provider or not model:
                return
            key = (provider, model)
            if key in seen:
                return
            seen.add(key)
            options.append({
                "provider": provider,
                "model": model,
                "label": f"{provider} / {model}",
                "icon": _get_provider_icon(provider),
            })

        # 首先添加当前活跃提供商的已配置模型
        provider_model = cfg.config.get(active_provider, {}).get("model", "")
        if provider_model:
            add_option(active_provider, provider_model)
        
        # 添加其他提供商的已配置模型
        for provider in ("openai", "deepseek", "anthropic", "litellm", "bedrock", "ollama",
                         "qwen", "doubao", "kimi", "glm", "minimax"):
            if provider != active_provider:  # 避免重复添加活跃提供商
                add_option(provider, cfg.config.get(provider, {}).get("model", ""))
        
        # 添加已激活的模型列表（属于活跃提供商）
        for model in cfg.config.get("active_models", []):
            add_option(active_provider, model)
        
        # 如果仍然没有选项，使用活跃提供商的默认模型
        if not options:
            options.append({
                "provider": active_provider,
                "model": active_model or "未配置模型",
                "label": f"{active_provider} / {active_model or '未配置模型'}",
                "icon": _get_provider_icon(active_provider),
            })

        current_data = self.model_selector.currentData() if hasattr(self, "model_selector") else None
        self.model_selector.blockSignals(True)
        try:
            self.model_selector.clear()
            for option in options:
                icon_name = option.get("icon", "code")
                icon = Icon.qicon(icon_name, size=12)
                self.model_selector.addItem(icon, option["label"], option)

            target_provider = active_provider
            target_model = active_model
            if not follow_active and isinstance(current_data, dict):
                target_provider = current_data.get("provider", active_provider)
                target_model = current_data.get("model", active_model)
            idx = 0
            for i in range(self.model_selector.count()):
                data = self.model_selector.itemData(i)
                if isinstance(data, dict) and data.get("provider") == target_provider and data.get("model") == target_model:
                    idx = i
                    break
            self.model_selector.setCurrentIndex(idx)
        finally:
            self.model_selector.blockSignals(False)
        self._update_model_selector_state()



    def _refresh_skill_options(self):
        """刷新技能选择器列表，保留当前选中状态"""
        if not hasattr(self, "skill_selector"):
            return
        selected_names = self.skill_selector.selectedNames()
        self.skill_selector.clearItems()

        for item_data in self._list_skill_items() or []:
            if isinstance(item_data, dict):
                name = item_data.get("name", "")
                desc = item_data.get("description", "")
                label = name if not desc else f"{name} · {desc}"
            else:
                name = str(item_data)
                label = name
            if name:
                self.skill_selector.addCheckItem(label, name, checked=(name in selected_names))

    # ── 模式切换 ─────────────────────────────────
    def _switch_mode(self, mode: str):
        """
        切换对话模式：chat（普通对话）、agent（ReAct Agent）
        """
        self._chat_mode = mode
        self.btn_chat_mode.setChecked(mode == "chat")
        self.btn_agent_mode.setChecked(mode == "agent")
        # agent 模式显示提示
        self.agent_tip.setVisible(mode == "agent")
        self._btn_stop.setVisible(self._running and mode == "agent")
        self.input_box.setPlaceholderText(self._composer_placeholder_text())
        # 刷新模型选择器
        self.refresh_model_config(follow_active=True)


    def _on_send_db_changed(self, _index: int):
        if self._syncing_db_combo:
            return
        self._syncing_db_combo = True
        try:
            self.history_db_combo.setCurrentIndex(self.db_selector.currentIndex())
        finally:
            self._syncing_db_combo = False
        self._reload_chat_from_history()
        self.update_context()
        self._update_file_tip()

    def _on_history_db_changed(self, _index: int):
        if self._syncing_db_combo:
            return
        self._syncing_db_combo = True
        try:
            self.db_selector.setCurrentIndex(self.history_db_combo.currentIndex())
        finally:
            self._syncing_db_combo = False
        self._reload_chat_from_history()
        self.update_context()

    def _selected_model_data(self) -> dict:
        data = self.model_selector.currentData() if hasattr(self, "model_selector") else None
        return data if isinstance(data, dict) else {}

    def _update_model_selector_state(self):
        data = self._selected_model_data()
        provider = data.get("provider", "")
        model = data.get("model", "")
        tooltip = f"当前模型：{provider} / {model}" if provider or model else ""
        self.model_selector.setToolTip(tooltip)

    def _on_model_changed(self, _index: int):
        self._update_model_selector_state()
        self._apply_selected_model_to_config()

    def _on_skill_selection_changed(self, selected_names: list):
        """SkillDropdownSelector 选中状态变化时自动应用，并刷新标签栏"""
        tokens = _tokens()
        self.skill_tag_bar.setTags(selected_names, tokens)
        # 立即应用（不在状态栏显示提示，标签栏已展示）

    def _on_skill_tag_removed(self, name: str):
        """用户点击标签的 × 时，取消对应技能的勾选"""
        selected = self.skill_selector.selectedNames()
        if name in selected:
            selected.remove(name)
        self.skill_selector.setCheckedNames(selected)
        # setCheckedNames 已触发 selectionChanged → 自动更新标签和应用

    def _apply_skills_immediately(self, selected_names: list):
        """立即应用或取消技能（无需点击确定按钮）"""
        if selected_names:
            ok = self._apply_skill(selected_names)
            if ok:
                if len(selected_names) == 1:
                    self._set_status_text(f"{Icon.char('flag')} 已引用 Skill：{selected_names[0]}")
                else:
                    self._set_status_text(f"{Icon.char('flag')} 已引用 {len(selected_names)} 个 Skill")
        else:
            ok = self._apply_skill([])
            if ok:
                self._set_status_text(f"{Icon.char('flag')} 已取消所有 Skill")

    # ── 文件上传 ─────────────────────────────────
    def _update_file_tip(self):
        if not hasattr(self, "file_tip"):
            return
        context = self._selected_db_info()
        db_text = self._context_mention(context)
        schema_ready = bool(self._selected_schema())
        db_type = context.get("db_type", "mysql")
        db_label = context.get("label", "默认会话")
        conn_state = "已接入表结构" if schema_ready else "未连接数据库"

        tooltip_lines = [f"[{db_type}] {db_label}", f"状态：{conn_state}"]
        if not self._uploaded_files:
            summary = f"{db_text} · {conn_state}"
            self.file_tip.setText(summary)
            self.file_tip.setToolTip("\n".join(tooltip_lines))
            return

        names = [os.path.basename(path) for path in self._uploaded_files[:5]]
        extra_count = max(0, len(self._uploaded_files) - len(names))
        summary = f"{db_text} · 附件 {len(self._uploaded_files)} 个"
        tooltip_lines.extend(["", "附件："])
        tooltip_lines.extend(f"- {name}" for name in names)
        if extra_count:
            tooltip_lines.append(f"- 其余 {extra_count} 个附件")
        self.file_tip.setText(summary)
        self.file_tip.setToolTip("\n".join(tooltip_lines))




    def _on_upload_files(self):
        paths, _ = QFileDialog.getOpenFileNames(self, "选择文件", "", "所有文件 (*.*)")
        if not paths:
            return
        self._sync_attachment_mentions(paths)

    def _attachment_context(self) -> str:
        if not self._uploaded_files:
            return ""
        chunks = ["参考附件："]
        for path in self._uploaded_files[:5]:
            name = os.path.basename(path)
            chunks.append(f"- 文件：{name}")
            ext = os.path.splitext(name)[1].lower()
            if ext in {".txt", ".md", ".sql", ".json", ".csv", ".py", ".log", ".yaml", ".yml"}:
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        content = f.read(3000).strip()
                    if content:
                        preview = content[:1200]
                        if len(content) > 1200:
                            preview += "\n...（内容已截断）"
                        chunks.append(preview)
                except Exception:
                    chunks.append("（文件已选择，当前无法读取文本内容）")
            else:
                chunks.append(f"（已附带路径：{path}）")
        return "\n".join(chunks)

    def _compose_user_message(self, text: str) -> str:
        attachment = self._attachment_context()
        if not attachment:
            return text
        return f"{text}\n\n{attachment}"

    # ── 历史加载 / 重建 ───────────────────────────
    def _load_history_to_ui(self):
        self._reload_chat_from_history()

    def _clear_chat_layout(self):
        self._bubble_widgets.clear()
        self._welcome_label = None
        while self.chat_layout.count():
            item = self.chat_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def _reload_chat_from_history(self):
        history_key = self._selected_history_key()
        history = self.chat_engine.get_history(history_key)
        self._clear_chat_layout()
        self._history_user_indices = []

        if not history:
            self._welcome_label = QLabel("开始聊吧：@ 选数据库，" + Icon.styled_char('attachment') + " 加附件，Enter 发送；双击消息可快速复制。")
            self._welcome_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self._welcome_label.setWordWrap(True)
            self.chat_layout.addWidget(self._welcome_label)
            self._apply_theme_styles()
            self._rebuild_history_list()
            return



        for idx, msg in enumerate(history):
            role = msg.get("role", "user")
            content = msg.get("content", "")
            time_str = msg.get("time", "")
            self._add_bubble(role, content, time_str, save=False)
            if role == "user":
                self._history_user_indices.append(idx)
        self._refresh_bubble_layout()
        self._rebuild_history_list()
        self._scroll_to_bottom()


    def _rebuild_history_list(self):
        self.history_list.clear()
        history = self.chat_engine.get_history(self._selected_history_key())
        user_index = -1
        for idx, msg in enumerate(history):
            if msg.get("role") != "user":
                continue
            user_index += 1
            text = msg.get("content", "")
            summary = text.replace("\n", " ")[:30] + ("…" if len(text) > 30 else "")
            time_str = msg.get("time", "")
            item = QListWidgetItem(f"{time_str}\n{summary}")
            item.setData(Qt.ItemDataRole.UserRole, user_index)
            self.history_list.addItem(item)

    def _on_history_item_click(self, item: QListWidgetItem):
        user_idx = item.data(Qt.ItemDataRole.UserRole)
        count = 0
        for bubble in self._bubble_widgets:
            if bubble.role == "user":
                if count == user_idx:
                    self.scroll_area.ensureWidgetVisible(bubble)
                    return
                count += 1

    # ── 发送消息 ──────────────────────────────────
    def eventFilter(self, obj, event):
        """事件过滤器 - 处理键盘快捷键"""
        from PySide6.QtCore import QEvent
        from PySide6.QtGui import QKeySequence
        
        if obj is self.input_box and event.type() == QEvent.Type.KeyPress:
            # @ 触发数据库选择
            if event.text() == "@":
                anchor = self.input_box.mapToGlobal(self.input_box.cursorRect().bottomLeft())
                self._open_db_context_menu(anchor_global=anchor, insert_mention=True)
                return True
            
            # Enter 发送（Shift+Enter 换行）
            if event.key() == Qt.Key.Key_Return:
                if event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
                    # Shift+Enter: 插入换行
                    return False  # 让默认行为处理
                else:
                    # Enter: 发送消息
                    self._on_send()
                    return True
            
            # Ctrl+K: 清空输入框
            if event.key() == Qt.Key.Key_K and (event.modifiers() & Qt.KeyboardModifier.ControlModifier):
                self.input_box.clear()
                self.input_box.setFocus()
                return True
            
            # Ctrl+L: 聚焦输入框
            if event.key() == Qt.Key.Key_L and (event.modifiers() & Qt.KeyboardModifier.ControlModifier):
                self.input_box.setFocus()
                self.input_box.selectAll()
                return True
            
            # Alt+Up: 上一条用户消息
            if event.key() == Qt.Key.Key_Up and (event.modifiers() & Qt.KeyboardModifier.AltModifier):
                self._navigate_history(-1)
                return True
            
            # Alt+Down: 下一条用户消息
            if event.key() == Qt.Key.Key_Down and (event.modifiers() & Qt.KeyboardModifier.AltModifier):
                self._navigate_history(1)
                return True
        
        # Esc: 停止生成
        if event.type() == QEvent.Type.KeyPress and event.key() == Qt.Key.Key_Escape:
            if self._running:
                self._on_stop()
                return True
        
        # Ctrl+Shift+H: 切换历史面板
        if event.type() == QEvent.Type.KeyPress:
            if (event.key() == Qt.Key.Key_H and 
                (event.modifiers() & Qt.KeyboardModifier.ControlModifier) and
                (event.modifiers() & Qt.KeyboardModifier.ShiftModifier)):
                self._toggle_history_panel()
                return True
            
            # Ctrl+F: 打开搜索（预留）
            if (event.key() == Qt.Key.Key_F and 
                (event.modifiers() & Qt.KeyboardModifier.ControlModifier)):
                # TODO: 实现搜索功能
                self._show_action_tip("搜索功能开发中...")
                return True
        
        return super().eventFilter(obj, event)

    def _on_send(self):
        text = self.input_box.toPlainText().strip()
        if not text or self._running:
            return
        # 根据模式选择调用方式
        if self._chat_mode == "agent":
            self._call_agent(text)
        else:
            self._call_ai(text)
        self.input_box.clear()
        self._uploaded_files = []
        self._update_file_tip()
        self._reset_history_navigation()  # 重置历史导航状态
        self._clear_thumbnails()  # 清除缩略图

    def _on_stop(self):
        if self._agent:
            self._agent.stop()
        self._hide_loading_indicator()  # 隐藏加载指示器
        # 强制终止：如果5秒后仍在运行，强制结束
        from PySide6.QtCore import QTimer
        QTimer.singleShot(5000, self._force_stop_check)

    def _force_stop_check(self):
        """检查是否成功停止，否则强制重置状态"""
        if self._running:
            self._hide_loading_indicator()  # 隐藏加载指示器
            self._set_running(False)
            if hasattr(self, '_step_timer') and self._step_timer:
                self._step_timer.stop()
            # 清理 Agent 引用，让下次可以重新启动
            self._agent = None


    # ── 公开方法 ─────────────────────────────────
    def inject_user(self, text: str):
        now_str = datetime.datetime.now().strftime("%H:%M:%S")
        self._add_bubble("user", text, now_str, save=False)
        self._scroll_to_bottom()

    def inject_assistant(self, text: str):
        now_str = datetime.datetime.now().strftime("%H:%M:%S")
        self._add_bubble("assistant", text, now_str, save=False)
        self._rebuild_history_list()
        self._scroll_to_bottom()

    def send_as_user(self, text: str):
        if not text.strip():
            return
        if self._chat_mode == "agent":
            self._call_agent(text.strip())
        else:
            self._call_ai(text.strip())

    def update_context(self):
        context = self._selected_db_info()
        schema = self._selected_schema()
        db_type = context.get("db_type", "mysql")
        db_label = context.get("label", "默认会话")
        selected_table = context.get("selected_table", "")
        table_part = f" · {selected_table}" if selected_table else ""
        status_text = f"[{db_type}] {db_label}{table_part} · {'已注入表结构' if schema else '未连接数据库'}"
        self.lbl_schema_status.setText(status_text)
        self.lbl_schema_status.setToolTip(status_text)
        self.lbl_schema_status.setVisible(bool(status_text.strip()))
        self._update_file_tip()


    def _status_style(self, text: str) -> str:
        tokens = _tokens()
        fg = tokens["accent"]
        bg = tokens.get("accent_soft", tokens["surface_muted"])
        bd = tokens["accent"]
        if any(key in text for key in ("错误", "出错", "失败")):
            fg = tokens["danger"]
            bg = tokens.get("danger_soft", tokens["surface_muted"])
            bd = tokens["danger"]
        elif any(key in text for key in ("完成", "成功")):
            fg = tokens["success"]
            bg = tokens.get("success_soft", tokens["surface_muted"])
            bd = tokens["success"]
        elif "停止" in text:
            fg = tokens["warning"]
            bg = tokens.get("warning_soft", tokens["surface_muted"])
            bd = tokens["warning"]
        return (
            "QLabel{" 
            f"background:{bg}; color:{fg}; border:1px solid {bd};"
            "border-radius: 2px; padding:5px 10px;"
            "font-size:11px; font-weight:600;"
            "}"
        )


    def _set_status_text(self, text: str):
        if not hasattr(self, "lbl_status"):
            return
        text = text or ""
        from ui.iconfont_loader import wrap_pua
        self.lbl_status.setText(wrap_pua(text))
        self.lbl_status.setStyleSheet(self._status_style(text) if text.strip() else "")
        self.lbl_status.setVisible(bool(text.strip()))

    def _apply_selected_model_to_config(self):
        data = self.model_selector.currentData() or {}
        if not isinstance(data, dict):
            return None
        provider = data.get("provider", "").strip()
        model = data.get("model", "").strip()
        # 忽略未配置的空选项（不污染 config）
        if not provider or not model or model == "未配置模型":
            return None
        cfg = ModelConfig()
        cfg.config.setdefault(provider, {})["model"] = model
        cfg.config["active_provider"] = provider
        # 同步更新 hermes 配置的模型字段（如果 hermes 配置存在）
        if provider != "hermes" and model:
            hermes_conf = cfg.config.setdefault("hermes", {})
            hermes_conf["model"] = model
        cfg.save()
        return data

    # ── 普通对话模式 ──────────────────────────────
    def _call_ai(self, text: str):
        self._set_running(True)
        self._show_loading_indicator()  # 显示加载指示器
        self._apply_selected_model_to_config()
        context = self._selected_db_info()
        history_key = context.get("key", DEFAULT_HISTORY_KEY)
        db_label = context.get("label", "默认会话")
        db_type = context.get("db_type", "mysql")
        schema = self._selected_schema()
        send_text = self._compose_user_message(text)

        now_str = datetime.datetime.now().strftime("%H:%M:%S")
        self._add_bubble("user", send_text, now_str, save=False)
        self._scroll_to_bottom()
        self.lbl_schema_status.setText(
            f"[{db_type}] {db_label} · {'已注入表结构' if schema else '未连接数据库'}"
        )
        self._update_file_tip()


        model_data = self.model_selector.currentData() or {}
        worker = _ChatWorker(
            self.chat_engine,
            send_text,
            schema,
            db_type,
            history_key,
            db_label,
            model_data.get("provider", ""),
            model_data.get("model", ""),
        )
        worker.signals.finished.connect(self._on_ai_reply)
        QThreadPool.globalInstance().start(worker)

    def _on_ai_reply(self, reply: str):
        self._hide_loading_indicator()  # 隐藏加载指示器
        self._set_running(False)
        now_str = datetime.datetime.now().strftime("%H:%M:%S")

        self._add_bubble("assistant", reply, now_str, save=False)
        self._rebuild_history_list()
        self._scroll_to_bottom()

    # ── Agent 模式 ────────────────────────────────
    def _call_agent(self, text: str):
        self._set_running(True)
        self._show_loading_indicator()  # 显示加载指示器
        self._apply_selected_model_to_config()
        context = self._selected_db_info()
        history_key = context.get("key", DEFAULT_HISTORY_KEY)
        db_label = context.get("label", "默认会话")
        db_type = context.get("db_type", "mysql")
        schema = self._selected_schema()
        selected_table = context.get("selected_table", "")

        # 若有选中表：① 在 schema 最前插入提示行；② 在用户消息中注入
        if selected_table and schema:
            schema = f"【当前选中表：{selected_table}】\n\n" + schema
        send_text = self._compose_user_message(text)
        if selected_table:
            send_text = f"[当前选中表：{selected_table}]\n{send_text}"

        now_str = datetime.datetime.now().strftime("%H:%M:%S")
        self._add_bubble("user", send_text, now_str, save=False)
        self.chat_engine.append_message(
            "user", send_text,
            time_str=now_str,
            history_key=history_key,
            db_label=db_label,
            db_type=db_type,
            save=True,
        )
        self._scroll_to_bottom()

        self.lbl_schema_status.setText(
            f"[{db_type}] {db_label} · {'已注入表结构' if schema else '未连接数据库'}"
        )
        self._update_file_tip()


        self._step_queue = []
        # 根据模式决定是否使用 Hermes Agent（Hermes 复用当前模型的配置）
        agent = AIAgent(
            execute_fn=self._execute_fn,
            on_step=self._agent_step_callback,
        )
        self._agent = agent

        from PySide6.QtCore import QTimer
        self._step_timer = QTimer(self)
        self._step_timer.timeout.connect(self._poll_step_queue)
        self._step_timer.start(50)

        worker = _AgentWorker(agent, send_text, schema, db_type)
        worker.signals.finished.connect(lambda result: self._on_agent_done(result, history_key, db_label, db_type))
        QThreadPool.globalInstance().start(worker)

    def _agent_step_callback(self, step_type: str, content: str):
        if not hasattr(self, "_step_queue"):
            self._step_queue = []
        self._step_queue.append((step_type, content))

    def _poll_step_queue(self):
        if not hasattr(self, "_step_queue"):
            return
        while self._step_queue:
            step_type, content = self._step_queue.pop(0)
            self._render_agent_step(step_type, content)

    def _render_agent_step(self, step_type: str, content: str):
        now_str = datetime.datetime.now().strftime("%H:%M:%S")
        status_map = {
            "think": f"{Icon.styled_char('question')} AI 正在推理…",
            "sql": Icon.prefixed_text('play', "执行 SQL…"),
            "obs": f"{Icon.styled_char('bar_chart')} 处理结果…",
            "done": Icon.prefixed_text('success', "任务完成"),
            "error": Icon.prefixed_text('error', "遇到错误"),
        }
        self._set_status_text(status_map.get(step_type, Icon.prefixed_text('robot', "Agent 运行中…")))


        bubble = _BubbleWidget(
            role="assistant",
            text=content,
            time_str=now_str,
            step_type=step_type,
        )
        self.chat_layout.addWidget(bubble)
        self._bubble_widgets.append(bubble)
        self._scroll_to_bottom()

    def _on_agent_done(self, result: str, history_key: str, db_label: str, db_type: str):
        if hasattr(self, "_step_timer"):
            self._step_timer.stop()
        self._poll_step_queue()
        self._hide_loading_indicator()  # 隐藏加载指示器
        self._set_running(False)

        final_text = result or ""
        if final_text.startswith("[已停止]"):
            final_text = f"{Icon.styled_char('stop')} Agent 已停止。"
            self.inject_assistant(final_text)
        elif final_text.startswith("[错误]") or final_text.startswith("[Agent错误]"):
            # 显示错误信息给用户
            self._set_status_text(final_text)
            self.inject_assistant(f"⚠️ {final_text}")
        else:
            pass  # 正常结果

        self.chat_engine.append_message(
            "assistant", final_text,
            time_str=datetime.datetime.now().strftime("%H:%M:%S"),
            history_key=history_key,
            db_label=db_label,
            db_type=db_type,
            save=True,
        )
        self._rebuild_history_list()

    # ── 运行状态管理 ──────────────────────────────
    def _set_running(self, running: bool):
        self._running = running
        self._btn_send.setEnabled(not running)
        self._btn_stop.setVisible(running and self._chat_mode == "agent")
        
        # 更新发送按钮文本和样式以显示加载状态
        if running:
            import time
            self._request_start_time = time.time()
            self._btn_send.setText("等待中")
            self._btn_send.setStyleSheet(
                self._btn_send.styleSheet() + 
                "QPushButton{opacity: 0.6;}"
            )
        else:
            # 计算并显示请求耗时
            if self._request_start_time:
                import time
                elapsed = time.time() - self._request_start_time
                self._set_status_text(f"{Icon.char('success')} 请求完成（耗时 {elapsed:.1f}s）")
                self._request_start_time = None
            self._btn_send.setText("发送")
            # 恢复原始样式（移除 opacity）
            base_style = self._btn_send.styleSheet().replace("QPushButton{opacity: 0.6;}", "")
            self._btn_send.setStyleSheet(base_style)

    def _show_loading_indicator(self):
        """显示加载状态指示器"""
        if self._loading_bubble:
            return  # 已经显示
        
        self._loading_bubble = _LoadingBubble("AI 正在思考中")
        self.chat_layout.addWidget(self._loading_bubble)
        self._scroll_to_bottom()
    
    def _hide_loading_indicator(self):
        """隐藏加载状态指示器"""
        if self._loading_bubble:
            self._loading_bubble.stop_animation()
            self.chat_layout.removeWidget(self._loading_bubble)
            self._loading_bubble.deleteLater()
            self._loading_bubble = None

    # ── 气泡操作 ─────────────────────────────────
    def _add_bubble(self, role: str, text: str, time_str: str, save: bool = True, step_type: str = ""):
        from ui.iconfont_loader import wrap_pua
        bubble = _BubbleWidget(role, wrap_pua(text), time_str, step_type=step_type)
        
        # 设置初始透明度为0
        from PySide6.QtWidgets import QGraphicsOpacityEffect
        opacity_effect = QGraphicsOpacityEffect(bubble)
        opacity_effect.setOpacity(0.0)
        bubble.setGraphicsEffect(opacity_effect)
        
        # 添加到布局
        self.chat_layout.addWidget(bubble)
        self._bubble_widgets.append(bubble)
        QTimer.singleShot(0, bubble.resize_msg)
        
        # 创建淡入动画
        from PySide6.QtCore import QPropertyAnimation, QEasingCurve
        animation = QPropertyAnimation(opacity_effect, b"opacity")
        animation.setDuration(200)  # 200ms
        animation.setStartValue(0.0)
        animation.setEndValue(1.0)
        animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        animation.start()
        
        # 保持动画对象引用，防止被垃圾回收
        if not hasattr(self, '_active_animations'):
            self._active_animations = []
        self._active_animations.append(animation)
        
        # 动画完成后清理引用（保留最近10个）
        if len(self._active_animations) > 10:
            self._active_animations = self._active_animations[-10:]


    def _scroll_to_bottom(self):
        QApplication.processEvents()
        self.scroll_area.verticalScrollBar().setValue(
            self.scroll_area.verticalScrollBar().maximum()
        )
    
    # ── 右键菜单操作处理 ─────────────────────────
    def _edit_bubble_message(self, bubble: _BubbleWidget):
        """编辑用户消息"""
        if bubble.role != "user":
            return
        
        # 创建编辑对话框
        from PySide6.QtWidgets import QDialog, QVBoxLayout, QTextEdit, QPushButton, QHBoxLayout
        dialog = QDialog(self)
        dialog.setWindowTitle("编辑消息")
        dialog.resize(600, 400)
        
        layout = QVBoxLayout(dialog)
        text_edit = QTextEdit()
        text_edit.setPlainText(bubble._raw_text)
        layout.addWidget(text_edit)
        
        btn_layout = QHBoxLayout()
        btn_cancel = QPushButton("取消")
        btn_save = QPushButton("保存并重新发送")
        btn_save.setProperty("role", "primary")
        
        btn_cancel.clicked.connect(dialog.close)
        btn_save.clicked.connect(lambda: self._save_edited_message(bubble, text_edit.toPlainText(), dialog))
        
        btn_layout.addStretch()
        btn_layout.addWidget(btn_cancel)
        btn_layout.addWidget(btn_save)
        layout.addLayout(btn_layout)
        
        dialog.exec()
    
    def _save_edited_message(self, old_bubble: _BubbleWidget, new_text: str, dialog: QDialog):
        """保存编辑后的消息并重新发送"""
        if not new_text.strip():
            QMessageBox.warning(self, "提示", "消息不能为空")
            return
        
        dialog.close()
        
        # 找到旧气泡的索引
        try:
            idx = self._bubble_widgets.index(old_bubble)
            
            # 删除从该气泡开始的所有后续消息
            for i in range(len(self._bubble_widgets) - 1, idx - 1, -1):
                widget = self._bubble_widgets[i]
                self.chat_layout.removeWidget(widget)
                widget.deleteLater()
            self._bubble_widgets = self._bubble_widgets[:idx]
            
            # 更新历史记录
            history_key = self._selected_history_key()
            history = self.chat_engine.get_history(history_key)
            # 找到对应的用户消息索引
            user_msg_count = 0
            target_idx = -1
            for i, msg in enumerate(history):
                if msg.get("role") == "user":
                    if user_msg_count == idx // 2:  # 每两个气泡（用户+AI）算一轮
                        target_idx = i
                        break
                    user_msg_count += 1
            
            if target_idx >= 0:
                # 删除该消息及之后的所有消息
                self.chat_engine.history = self.chat_engine.history[:target_idx]
                self.chat_engine._save_history()
            
            # 重新发送编辑后的消息
            self.input_box.setPlainText(new_text)
            self._on_send()
            
        except ValueError:
            QMessageBox.warning(self, "错误", "找不到要编辑的消息")
    
    def _regenerate_bubble_message(self, bubble: _BubbleWidget):
        """重新生成AI回复"""
        if bubble.role != "assistant":
            return
        
        # 找到前一条用户消息
        bubble_idx = self._bubble_widgets.index(bubble) if bubble in self._bubble_widgets else -1
        if bubble_idx <= 0:
            QMessageBox.warning(self, "提示", "没有可重新生成的消息")
            return
        
        # 查找前一条用户消息
        user_bubble = None
        for i in range(bubble_idx - 1, -1, -1):
            if self._bubble_widgets[i].role == "user":
                user_bubble = self._bubble_widgets[i]
                break
        
        if not user_bubble:
            QMessageBox.warning(self, "提示", "找不到对应的用户消息")
            return
        
        # 删除当前AI消息及之后的所有消息
        for i in range(len(self._bubble_widgets) - 1, bubble_idx - 1, -1):
            widget = self._bubble_widgets[i]
            self.chat_layout.removeWidget(widget)
            widget.deleteLater()
        self._bubble_widgets = self._bubble_widgets[:bubble_idx]
        
        # 更新历史记录
        history_key = self._selected_history_key()
        history = self.chat_engine.get_history(history_key)
        # 找到对应的AI消息索引并删除
        assistant_count = 0
        target_idx = -1
        for i, msg in enumerate(history):
            if msg.get("role") == "assistant":
                assistant_count += 1
                # 简化逻辑：删除最后一条AI消息
                target_idx = i
        
        if target_idx >= 0:
            self.chat_engine.history = self.chat_engine.history[:target_idx]
            self.chat_engine._save_history()
        
        # 重新发送用户消息
        user_text = user_bubble._raw_text
        self.input_box.setPlainText(user_text)
        self._on_send()
    
    def _execute_sql_from_bubble(self, sql: str):
        """从气泡执行SQL"""
        if not sql.strip():
            QMessageBox.warning(self, "提示", "SQL语句不能为空")
            return
        
        reply = QMessageBox.question(
            self,
            "确认执行",
            f"确定要执行以下SQL吗？\n\n{sql[:200]}{'...' if len(sql) > 200 else ''}",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        
        if reply != QMessageBox.StandardButton.Yes:
            return
        
        try:
            cols, rows = self._execute_fn(sql)
            
            # 显示结果
            result_text = f"执行成功！\n\n列: {', '.join(str(c) for c in cols)}\n\n行数: {len(rows)}\n\n"
            if rows:
                result_text += "前10行数据:\n"
                for row in rows[:10]:
                    result_text += str(row) + "\n"
            
            QMessageBox.information(self, "SQL执行结果", result_text)
        except Exception as e:
            QMessageBox.critical(self, "执行失败", f"SQL执行出错:\n{str(e)}")
    
    def _delete_bubble_message(self, bubble: _BubbleWidget):
        """删除气泡消息"""
        try:
            idx = self._bubble_widgets.index(bubble)
            
            # 从布局中移除
            self.chat_layout.removeWidget(bubble)
            bubble.deleteLater()
            
            # 从列表中删除
            self._bubble_widgets.pop(idx)
            
            # 同步删除历史记录
            history_key = self._selected_history_key()
            history = self.chat_engine.get_history(history_key)
            
            # 计算这是第几条消息
            if bubble.role == "user":
                msg_index = idx // 2
            else:
                msg_index = idx // 2 + (1 if idx % 2 == 0 else 0)
            
            if msg_index < len(history):
                self.chat_engine.history.pop(msg_index)
                self.chat_engine._save_history()
            
            self._show_action_tip("消息已删除")
            
        except (ValueError, IndexError):
            QMessageBox.warning(self, "错误", "删除消息失败")
    
    def _show_action_tip(self, message: str):
        """显示操作提示"""
        from PySide6.QtWidgets import QToolTip
        QToolTip.showText(
            self.mapToGlobal(self.rect().center()),
            message,
            None,
            self.rect(),
            1500
        )

    # ── 清除历史 ─────────────────────────────────
    def _on_clear_history(self):
        context = self._selected_db_info()
        history_key = context.get("key", DEFAULT_HISTORY_KEY)
        label = context.get("label", "当前会话")
        ret = QMessageBox.question(
            self,
            "确认清除",
            f"确定要清除“{label}”的对话历史记录吗？此操作不可恢复。",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if ret != QMessageBox.StandardButton.Yes:
            return

        self.chat_engine.clear_history(history_key)
        self._reload_chat_from_history()
        self._set_status_text("")
        self.update_context()
    
    # ── 键盘快捷键辅助方法 ───────────────────────
    def _navigate_history(self, direction: int):
        """
        导航历史记录（类似终端的上下键）
        direction: -1 = 上一条, 1 = 下一条
        """
        # 获取当前会话的所有用户消息
        history_key = self._selected_history_key()
        history = self.chat_engine.get_history(history_key)
        user_messages = [msg for msg in history if msg.get("role") == "user"]
        
        if not user_messages:
            return
        
        # 第一次按Alt+Up时，保存当前输入
        if self._history_navigation_index == -1:
            self._temp_input_buffer = self.input_box.toPlainText()
            self._history_navigation_index = len(user_messages)
        
        # 计算新的索引
        new_index = self._history_navigation_index + direction
        
        # 边界检查
        if new_index < 0:
            new_index = 0
        elif new_index >= len(user_messages):
            # 超出范围，恢复临时保存的输入
            self.input_box.setPlainText(self._temp_input_buffer)
            self._history_navigation_index = -1
            self._temp_input_buffer = ""
            return
        
        # 更新索引并显示消息
        self._history_navigation_index = new_index
        message_content = user_messages[new_index].get("content", "")
        self.input_box.setPlainText(message_content)
        self.input_box.setFocus()
        
        # 移动光标到末尾
        cursor = self.input_box.textCursor()
        cursor.movePosition(cursor.MoveOperation.End)
        self.input_box.setTextCursor(cursor)
        
        # 显示提示
        if self._history_navigation_index >= 0:
            self._show_action_tip(f"历史消息 {self._history_navigation_index + 1}/{len(user_messages)}")
    
    def _reset_history_navigation(self):
        """重置历史导航状态"""
        self._history_navigation_index = -1
        self._temp_input_buffer = ""
    
    # ── 图片预览与拖拽上传 ──────────────────────
    def _on_upload_files(self):
        """上传文件并显示缩略图"""
        paths, _ = QFileDialog.getOpenFileNames(
            self, 
            "选择文件", 
            "", 
            "所有文件 (*.*);;图片文件 (*.png *.jpg *.jpeg *.gif *.webp *.bmp);;文档文件 (*.txt *.md *.sql *.json *.csv *.py)"
        )
        if not paths:
            return
        self._sync_attachment_mentions(paths)
        self._update_thumbnails()
    
    def _clear_thumbnails(self):
        """清除所有缩略图并隐藏容器"""
        while self.thumbnail_layout.count():
            item = self.thumbnail_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self.thumbnail_container.setVisible(False)

    def _update_thumbnails(self):
        """更新缩略图显示"""
        # 清空现有缩略图
        while self.thumbnail_layout.count():
            item = self.thumbnail_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        
        # 检查是否有图片
        image_files = [p for p in self._uploaded_files if self._is_image_file(p)]
        
        if not image_files:
            self.thumbnail_container.setVisible(False)
            return
        
        # 显示缩略图
        self.thumbnail_container.setVisible(True)
        
        for img_path in image_files[:5]:  # 最多显示5个
            thumb_widget = self._create_thumbnail_widget(img_path)
            self.thumbnail_layout.addWidget(thumb_widget)
        
        # 如果超过5个，显示"更多"提示
        if len(image_files) > 5:
            more_label = QLabel(f"+{len(image_files) - 5}")
            more_label.setStyleSheet(
                f"background:{_tokens()['surface_muted']}; color:{_tokens()['text_muted']};"
                f"border-radius: 2px; padding:8px; font-size:12px; font-weight:bold;"
            )
            more_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            more_label.setFixedSize(48, 48)
            self.thumbnail_layout.addWidget(more_label)
        
        self.thumbnail_layout.addStretch()
    
    def _create_thumbnail_widget(self, img_path: str) -> QWidget:
        """创建单个缩略图widget"""
        container = QWidget()
        container.setFixedSize(48, 48)
        
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # 尝试加载图片
        try:
            from PySide6.QtGui import QPixmap
            pixmap = QPixmap(img_path)
            
            # 缩放为缩略图
            scaled = pixmap.scaled(
                44, 44,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )
            
            label = QLabel()
            label.setPixmap(scaled)
            label.setFixedSize(44, 44)
            label.setStyleSheet(
                f"border: 2px solid {_tokens()['border']}; border-radius: 2px;"
            )
            label.setCursor(Qt.CursorShape.PointingHandCursor)
            label.setToolTip(img_path)
            
            # 点击放大预览
            label.mousePressEvent = lambda event, p=img_path: self._show_image_preview(p)
            
            layout.addWidget(label)
        except Exception as e:
            # 加载失败显示占位符
            placeholder = QLabel(Icon.char('image'))
            placeholder.setFont(Icon.font(22))
            placeholder.setFixedSize(44, 44)
            placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
            placeholder.setStyleSheet(
                f"background:{_tokens()['surface_alt']}; border: 2px solid {_tokens()['border']};"
                f"border-radius: 2px;"
            )
            placeholder.setToolTip(f"加载失败: {img_path}")
            layout.addWidget(placeholder)
        
        return container
    
    def _show_image_preview(self, img_path: str):
        """显示图片放大预览"""
        from PySide6.QtWidgets import QDialog, QVBoxLayout, QLabel, QPushButton, QHBoxLayout
        from PySide6.QtGui import QPixmap
        from PySide6.QtCore import Qt
        
        dialog = QDialog(self)
        dialog.setWindowTitle("图片预览")
        dialog.setModal(True)
        
        # 获取屏幕尺寸
        screen = QApplication.primaryScreen().geometry()
        max_width = int(screen.width() * 0.8)
        max_height = int(screen.height() * 0.8)
        
        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(10, 10, 10, 10)
        
        # 加载并缩放图片
        pixmap = QPixmap(img_path)
        scaled_pixmap = pixmap.scaled(
            max_width, max_height,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation
        )
        
        label = QLabel()
        label.setPixmap(scaled_pixmap)
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label.setStyleSheet("background: transparent;")
        
        layout.addWidget(label)
        
        # 底部按钮
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        
        btn_close = QPushButton("关闭")
        btn_close.setFixedWidth(80)
        btn_close.clicked.connect(dialog.close)
        btn_layout.addWidget(btn_close)
        
        layout.addLayout(btn_layout)
        
        dialog.resize(min(scaled_pixmap.width() + 20, max_width), 
                     min(scaled_pixmap.height() + 60, max_height))
        dialog.exec()
    
    def _on_drag_enter(self, event):
        """拖拽进入事件"""
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            event.ignore()
    
    def _on_drag_move(self, event):
        """拖拽移动事件"""
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            event.ignore()
    
    def _on_drop(self, event):
        """拖拽放下事件"""
        urls = event.mimeData().urls()
        if urls:
            file_paths = [url.toLocalFile() for url in urls if url.isLocalFile()]
            if file_paths:
                self._sync_attachment_mentions(file_paths)
                self._update_thumbnails()
                event.acceptProposedAction()
            else:
                event.ignore()
        else:
            event.ignore()



# ─── 弹窗包装（向下兼容） ────────────────────────
class AIChatWindow(QDialog):
    """包装 AIChatWidget 的弹窗，保留向下兼容"""

    def __init__(
        self,
        parent=None,
        get_schema_fn=None,
        get_db_info_fn=None,
        list_db_contexts_fn=None,
        list_skill_items_fn=None,
        apply_skill_fn=None,
        execute_fn=None,
    ):
        super().__init__(parent)
        # 无边框窗口设置
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setObjectName("aiChatDialog")
        self.setWindowTitle("AI 对话助手")
        self.resize(980, 700)
        self.setMinimumSize(700, 500)
        self._apply_theme()
        self._setup_title_bar()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.widget = AIChatWidget(
            parent=self,
            get_schema_fn=get_schema_fn,
            get_db_info_fn=get_db_info_fn,
            list_db_contexts_fn=list_db_contexts_fn,
            list_skill_items_fn=list_skill_items_fn,
            apply_skill_fn=apply_skill_fn,
            execute_fn=execute_fn,
        )
        layout.addWidget(self.widget)

        # 设置主题监听定时器
        self._theme_check_timer = QTimer(self)
        self._theme_check_timer.timeout.connect(self._check_theme_change)
        self._theme_check_timer.start(1000)  # 每秒检查一次主题变化

    def _setup_title_bar(self):
        """设置自定义无边框标题栏"""
        root_layout = self.layout()
        if root_layout is None:
            return

        # 创建标题栏
        title_bar = QWidget()
        title_bar.setObjectName("dialogTitleBar")
        title_layout = QHBoxLayout(title_bar)
        title_layout.setContentsMargins(8, 0, 8, 0)
        title_layout.setSpacing(8)

        # 标题文字
        title_label = QLabel("AI 对话助手")
        title_label.setStyleSheet("font-weight: 600; font-size: 14px;")
        title_layout.addWidget(title_label)
        title_layout.addStretch()

        # 关闭按钮
        close_btn = QPushButton("✕")
        close_btn.setObjectName("titleBarCloseBtn")
        close_btn.setFixedSize(28, 28)
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.clicked.connect(self.close)
        title_layout.addWidget(close_btn)

        # 重新组织布局
        new_root = QVBoxLayout()
        new_root.setContentsMargins(0, 0, 0, 0)
        new_root.setSpacing(0)
        new_root.addWidget(title_bar)

        # 将原有 widget 移到内容区域
        content_widget = QWidget()
        content_widget.setStyleSheet("QWidget { background: transparent; }")
        content_layout = QVBoxLayout(content_widget)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)
        content_layout.addWidget(self.widget)

        new_root.addWidget(content_widget)
        self.setLayout(new_root)

    def _apply_theme(self):
        """应用当前主题样式"""
        self._theme = load_theme()
        self._tokens = get_theme_tokens(self._theme)
        self.setStyleSheet(build_popup_base_style(self._tokens, f"""
QDialog#aiChatDialog {{
    background: {self._tokens['surface']};
}}
"""))
        # 通知内部 widget 刷新主题
        if hasattr(self, 'widget') and self.widget:
            self.widget.refresh_theme()

    def _check_theme_change(self):
        """检查主题是否发生变化"""
        current_theme = load_theme()
        if current_theme != getattr(self, '_theme', None):
            self._apply_theme()

    def closeEvent(self, event):
        """关闭时停止定时器"""
        if hasattr(self, '_theme_check_timer'):
            self._theme_check_timer.stop()
        super().closeEvent(event)

    def inject_user(self, text: str):
        self.widget.inject_user(text)

    def inject_assistant(self, text: str):
        self.widget.inject_assistant(text)

    def send_as_user(self, text: str):
        self.widget.send_as_user(text)

    def update_context(self):
        self.widget.update_context()