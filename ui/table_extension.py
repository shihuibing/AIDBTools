"""
表格排序和列选中功能扩展模块

提供：
1. 表头点击排序（升序 → 降序 → 原序）
2. 表头点击选中整列（支持 Ctrl/Shift 多选）
3. 选中列高亮显示（跟随主题）
"""

from PySide6.QtWidgets import QTableWidget, QHeaderView, QApplication, QStyledItemDelegate, QStyleOptionButton, QStyle
from PySide6.QtCore import Qt, Signal, QRect, QEvent
from PySide6.QtGui import QColor, QPainter, QPen, QBrush, QPainterPath, QEnterEvent

from ui.theme_manager import get_theme_tokens, load_theme, _is_system_dark, THEME_AUTO, THEME_DARK


def _get_column_highlight_color() -> QColor:
    """获取当前主题的列高亮颜色"""
    theme = load_theme()
    if theme == THEME_AUTO:
        is_dark = _is_system_dark()
    else:
        is_dark = theme == THEME_DARK
    
    tokens = get_theme_tokens(theme)
    # 使用 selection_bg 的透明度版本，或 accent_soft
    if is_dark:
        # 暗色主题：使用 accent_soft 颜色
        accent_soft = tokens.get("accent_soft", "#1b3057")
        # 解析颜色
        if accent_soft.startswith("#"):
            r = int(accent_soft[1:3], 16)
            g = int(accent_soft[3:5], 16)
            b = int(accent_soft[5:7], 16)
            return QColor(r, g, b, 120)
    else:
        # 亮色主题：使用 selection_bg 或自定义浅蓝
        selection_bg = tokens.get("selection_bg", "#dbeafe")
        if selection_bg.startswith("#"):
            r = int(selection_bg[1:3], 16)
            g = int(selection_bg[3:5], 16)
            b = int(selection_bg[5:7], 16)
            return QColor(r, g, b, 180)
    return QColor(200, 220, 240, 160)


ORIGINAL_ORDER_ROLE = int(Qt.ItemDataRole.UserRole) + 1


class SortableTableHeader(QHeaderView):
    """可排序的表头，内置第0列复选框绘制"""

    # 信号：排序改变时发出 (col_idx, sort_order)
    # sort_order: 0=升序, 1=降序, -1=不排序(原序)
    sortChanged = Signal(int, int)

    def __init__(self, orientation, parent=None):
        super().__init__(orientation, parent)
        self._sort_col = -1  # 当前排序列
        self._sort_order = -1  # -1=原序, 0=升序, 1=降序
        self.setSectionsClickable(True)
        self.setSortIndicatorShown(False)
        self.sectionClicked.connect(self._on_header_clicked)

        # 表头复选框状态与颜色
        self._header_checked = False        # 当前是否全选
        self._header_partial = False        # 部分选中
        self._header_hovered = False        # 复选框是否悬停
        self._checked_color = QColor(99, 102, 241)   # #6366f1
        self._border_color = QColor(229, 231, 235)    # #e5e7eb
        self._unchecked_bg = QColor(255, 255, 255)
        self._checkmark_color = QColor(255, 255, 255)

        # 安装事件过滤器以检测复选框区域的悬停和点击
        self.setMouseTracking(True)
        self.viewport().setMouseTracking(True)
        self.viewport().installEventFilter(self)

    # ── 表头复选框颜色更新 ──
    def update_checkbox_colors(self, checked, unchecked_bg, border, checkmark):
        """更新复选框颜色（主题切换时调用）"""
        if isinstance(checked, str):
            self._checked_color = QColor(checked)
        elif isinstance(checked, QColor):
            self._checked_color = checked
        if isinstance(unchecked_bg, str):
            self._unchecked_bg = QColor(unchecked_bg)
        elif isinstance(unchecked_bg, QColor):
            self._unchecked_bg = unchecked_bg
        if isinstance(border, str):
            self._border_color = QColor(border)
        elif isinstance(border, QColor):
            self._border_color = border
        if isinstance(checkmark, str):
            self._checkmark_color = QColor(checkmark)
        elif isinstance(checkmark, QColor):
            self._checkmark_color = checkmark
        self.viewport().update()

    # ── 表头复选框状态 ──
    def set_header_check_state(self, checked: bool, partial: bool = False):
        """设置表头复选框状态（由外部调用同步）"""
        self._header_checked = checked
        self._header_partial = partial
        self.viewport().update()

    def header_check_state(self):
        """返回表头复选框状态 (checked, partial)"""
        return self._header_checked, self._header_partial

    # ── 复选框区域 ──
    def _checkbox_rect(self, section_rect: QRect) -> QRect:
        """计算复选框在 section 中的居中位置"""
        box_size = 16
        x = section_rect.x() + (section_rect.width() - box_size) // 2
        y = section_rect.y() + (section_rect.height() - box_size) // 2
        return QRect(int(x), int(y), box_size, box_size)

    # ── 绘制 ──
    def paintSection(self, painter: QPainter, rect, logical_index):
        """重写 paintSection：第0列绘制复选框，其余列正常绘制"""
        if logical_index == 0:
            # 先让 Qt 绘制 section 背景
            painter.save()
            super().paintSection(painter, rect, logical_index)
            painter.restore()

            # 在背景之上绘制复选框
            painter.save()
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            box_rect = self._checkbox_rect(rect)
            radius = 3

            if self._header_checked:
                # 选中：填充背景 + 勾
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(QBrush(self._checked_color))
                painter.drawRoundedRect(box_rect, radius, radius)
                # 勾
                painter.setPen(QPen(self._checkmark_color, 1.5))
                painter.setBrush(Qt.BrushStyle.NoBrush)
                path = QPainterPath()
                path.moveTo(box_rect.x() + 3, box_rect.y() + 8)
                path.lineTo(box_rect.x() + 6, box_rect.y() + 11)
                path.lineTo(box_rect.x() + 13, box_rect.y() + 4)
                painter.drawPath(path)
            elif self._header_partial:
                # 部分选中：填充背景 + 短横线
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(QBrush(self._checked_color))
                painter.drawRoundedRect(box_rect, radius, radius)
                painter.setPen(QPen(self._checkmark_color, 2))
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.drawLine(int(box_rect.x() + 4), int(box_rect.y() + 8),
                                 int(box_rect.x() + 12), int(box_rect.y() + 8))
            else:
                # 未选中
                painter.setPen(QPen(self._border_color, 1))
                painter.setBrush(QBrush(self._unchecked_bg))
                painter.drawRoundedRect(box_rect, radius, radius)
                # hover 时用强调色边框
                if self._header_hovered:
                    painter.setPen(QPen(self._checked_color, 1))
                    painter.setBrush(Qt.BrushStyle.NoBrush)
                    painter.drawRoundedRect(box_rect, radius, radius)

            painter.restore()
        else:
            super().paintSection(painter, rect, logical_index)

    # ── 事件过滤器：悬停效果 ──
    def eventFilter(self, obj, event):
        from PySide6.QtCore import QEvent as QEv
        if obj is self.viewport():
            if event.type() == QEv.Type.MouseMove:
                # 检测是否在复选框区域
                pos = event.position().toPoint()
                logical = self.logicalIndexAt(pos)
                if logical == 0:
                    section_rect = self._section_rect(0)
                    box_rect = self._checkbox_rect(section_rect)
                    hovered = box_rect.contains(pos)
                    if hovered != self._header_hovered:
                        self._header_hovered = hovered
                        self.viewport().update()
                else:
                    if self._header_hovered:
                        self._header_hovered = False
                        self.viewport().update()
            elif event.type() == QEv.Type.Leave:
                if self._header_hovered:
                    self._header_hovered = False
                    self.viewport().update()
        return super().eventFilter(obj, event)

    def _section_rect(self, logical_index: int) -> QRect:
        """获取指定逻辑列的 section 矩形"""
        v = self.logicalIndexAt(0)
        x = self.sectionViewportPosition(logical_index)
        w = self.sectionSize(logical_index)
        return QRect(x, 0, w, self.height())

    # ── 排序 ──
    def _on_header_clicked(self, col_idx):
        """表头被点击时的处理"""
        # 避免对第0列（复选框列）排序
        if col_idx == 0:
            return

        # 切换排序状态
        if self._sort_col == col_idx:
            # 同一列被连续点击：升序 → 降序 → 原序 → 升序...
            self._sort_order = (self._sort_order + 1) % 3
            if self._sort_order == 2:  # 如果是第三个状态（原序），设为 -1
                self._sort_order = -1
        else:
            # 不同列被点击：从升序开始
            self._sort_col = col_idx
            self._sort_order = 0

        if self._sort_order == -1:
            self.setSortIndicatorShown(False)
        else:
            self.setSortIndicatorShown(True)
            qt_order = (
                Qt.SortOrder.AscendingOrder
                if self._sort_order == 0
                else Qt.SortOrder.DescendingOrder
            )
            self.setSortIndicator(self._sort_col, qt_order)

        self.sortChanged.emit(self._sort_col, self._sort_order)

    def get_sort_state(self):
        """获取当前排序状态"""
        return self._sort_col, self._sort_order

    def reset_sort(self):
        """重置排序状态"""
        self._sort_col = -1
        self._sort_order = -1
        self.setSortIndicatorShown(False)


class SelectableTableWidget(QTableWidget):
    """支持排序和列选中的表格"""

    # 信号：选中列改变时发出 selected_cols (list of col_idx)
    selectedColumnsChanged = Signal(list)

    def __init__(self, parent=None):
        super().__init__(parent)

        # 初始化排序和列选中状态
        self._selected_cols = set()  # 选中的列索引集合
        self._last_selected_col = -1  # 用于 Shift+点击的范围选择

        # 替换表头为可排序的表头
        self._sortable_header = SortableTableHeader(Qt.Orientation.Horizontal, self)
        self.setHorizontalHeader(self._sortable_header)

        # 连接表头排序信号
        self._sortable_header.sortChanged.connect(self._on_sort_changed)

        # 连接表头点击事件（用于列选中）
        self.horizontalHeader().sectionClicked.connect(self._on_header_section_clicked)

        # 安装事件过滤器（用于复选框悬停效果）
        self.setMouseTracking(True)
        self.viewport().setMouseTracking(True)
        self._hovered_index = None

    def enterEvent(self, event: QEnterEvent):
        """鼠标进入事件 - 更新悬停状态"""
        self._update_hover_index(event)
        super().enterEvent(event)

    def leaveEvent(self, event: QEvent):
        """鼠标离开事件 - 清除悬停状态"""
        if self._hovered_index is not None:
            old_index = self._hovered_index
            self._hovered_index = None
            delegate = self.itemDelegateForColumn(0)
            if isinstance(delegate, CheckBoxDelegate):
                delegate.setHoveredIndex(None)
            # 重绘旧单元格
            self.viewport().update(self.visualRect(old_index))

        # 清除表头悬停状态
        self._update_header_hover(None)
        super().leaveEvent(event)

    def mouseMoveEvent(self, event):
        """鼠标移动事件 - 更新悬停状态"""
        self._update_hover_index(event)
        super().mouseMoveEvent(event)

    def _update_hover_index(self, event):
        """更新悬停的单元格索引"""
        # 获取当前鼠标位置对应的索引
        pos = event.pos() if hasattr(event, 'pos') else event
        index = self.indexAt(pos)

        if index.isValid() and index.column() == 0:
            if self._hovered_index != index:
                old_index = self._hovered_index
                self._hovered_index = index

                # 更新复选框委托的悬停状态
                delegate = self.itemDelegateForColumn(0)
                if isinstance(delegate, CheckBoxDelegate):
                    delegate.setHoveredIndex(index)

                # 重绘单元格
                if old_index and old_index.isValid():
                    self.viewport().update(self.visualRect(old_index))
                if index.isValid():
                    self.viewport().update(self.visualRect(index))
        else:
            if self._hovered_index is not None:
                old_index = self._hovered_index
                self._hovered_index = None

                # 更新复选框委托的悬停状态
                delegate = self.itemDelegateForColumn(0)
                if isinstance(delegate, CheckBoxDelegate):
                    delegate.setHoveredIndex(None)

                if old_index.isValid():
                    self.viewport().update(self.visualRect(old_index))

    def _update_header_hover(self, logical_index):
        """更新表头复选框悬停状态（SortableTableHeader 内部通过 eventFilter 处理，这里不再需要）"""
        # SortableTableHeader 的 _header_hovered 由其自身的 eventFilter 管理，无需外部调用
        pass

    def _on_sort_changed(self, col_idx, sort_order):
        """处理排序变化"""
        self._apply_sort(col_idx, sort_order)

    def _apply_sort(self, col_idx, sort_order):
        """应用排序"""
        if col_idx < 0 or col_idx >= self.columnCount() or self.rowCount() == 0:
            return

        rows_data = self._collect_rows()
        if not rows_data:
            return

        if sort_order == -1:
            rows_data.sort(key=self._get_original_row_order)
            self._apply_rows(rows_data)
            return

        self._do_sort(rows_data, col_idx, sort_order)

    def _collect_rows(self):
        """收集当前表格所有行的 item 对象"""
        rows_data = []
        for row in range(self.rowCount()):
            row_items = []
            for col in range(self.columnCount()):
                row_items.append(self.item(row, col))
            rows_data.append(row_items)
        return rows_data

    def _apply_rows(self, rows_data):
        """按给定顺序重新写回行数据"""
        self.blockSignals(True)

        for row in range(self.rowCount()):
            for col in range(self.columnCount()):
                self.takeItem(row, col)

        for row_idx, row_items in enumerate(rows_data):
            for col_idx, item in enumerate(row_items):
                if item is not None:
                    self.setItem(row_idx, col_idx, item)

        self.blockSignals(False)
        self._update_column_highlight()

    def _do_sort(self, rows_data, col_idx, sort_order):
        """执行实际排序"""
        null_rows = []
        normal_rows = []
        for row_items in rows_data:
            cell_text = self._get_sort_text(row_items, col_idx)
            if self._is_null_text(cell_text):
                null_rows.append(row_items)
            else:
                normal_rows.append(row_items)

        is_numeric = self._is_numeric_column(normal_rows, col_idx)
        is_descending = sort_order == 1

        if is_numeric:
            normal_rows.sort(
                key=lambda row: self._try_convert_to_number(self._get_sort_text(row, col_idx)),
                reverse=is_descending,
            )
        else:
            normal_rows.sort(
                key=lambda row: self._get_sort_text(row, col_idx).lower(),
                reverse=is_descending,
            )

        self._apply_rows(null_rows + normal_rows)

    def _get_sort_text(self, row_items, col_idx):
        """读取排序时使用的文本值"""
        if col_idx < 0 or col_idx >= len(row_items):
            return ""
        item = row_items[col_idx]
        if item is None:
            return ""
        raw_value = item.data(Qt.ItemDataRole.UserRole)
        if raw_value not in (None, ""):
            return str(raw_value)
        return item.text()

    def _get_original_row_order(self, row_items):
        """读取行的原始顺序编号"""
        if not row_items:
            return float("inf")
        first_item = row_items[0]
        if first_item is None:
            return float("inf")
        original_order = first_item.data(ORIGINAL_ORDER_ROLE)
        return original_order if original_order is not None else float("inf")

    def _is_numeric_column(self, rows_data, col_idx):
        """判断当前列是否应按数值排序"""
        has_value = False
        for row_items in rows_data:
            text = self._get_sort_text(row_items, col_idx)
            if self._is_null_text(text):
                continue
            has_value = True
            if self._try_convert_to_number(text) is None:
                return False
        return has_value

    def _try_convert_to_number(self, val):
        """尝试将字符串转换为数字用于排序"""
        try:
            if self._is_null_text(val):
                return None
            return float(str(val).replace(",", ""))
        except (ValueError, TypeError, AttributeError):
            return None

    def _is_null_text(self, val):
        """判断单元格是否应视为 NULL/空值"""
        if val is None:
            return True
        text = str(val).strip()
        return text == "" or text.lower() == "null"

    def _on_header_section_clicked(self, col_idx):
        """表头被点击时处理列选中"""
        # 获取当前键盘修饰符
        modifiers = (
            QApplication.instance().queryKeyboardModifiers()
            if QApplication.instance()
            else Qt.KeyboardModifier.NoModifier
        )

        # 处理列选中逻辑
        if modifiers & Qt.KeyboardModifier.ControlModifier:
            # Ctrl+点击：切换选中状态
            if col_idx in self._selected_cols:
                self._selected_cols.discard(col_idx)
            else:
                self._selected_cols.add(col_idx)
            self._last_selected_col = col_idx
        elif modifiers & Qt.KeyboardModifier.ShiftModifier and self._last_selected_col >= 0:
            # Shift+点击：范围选中
            min_col = min(self._last_selected_col, col_idx)
            max_col = max(self._last_selected_col, col_idx)
            self._selected_cols = set(range(min_col, max_col + 1))
        else:
            # 普通点击：选中单列
            self._selected_cols = {col_idx}
            self._last_selected_col = col_idx

        # 更新视觉反馈
        self._update_column_highlight()

        # 发出信号
        self.selectedColumnsChanged.emit(sorted(list(self._selected_cols)))

    def _update_column_highlight(self):
        """更新选中列的高亮显示（block 信号避免逐 item 触发重绘）"""
        self.blockSignals(True)
        self.model().blockSignals(True)

        # 清除所有高亮
        for col in range(self.columnCount()):
            for row in range(self.rowCount()):
                item = self.item(row, col)
                if item:
                    item.setBackground(QColor(255, 255, 255, 0))

        # 应用新的高亮（跟随主题）
        highlight_color = _get_column_highlight_color()
        for col in self._selected_cols:
            for row in range(self.rowCount()):
                item = self.item(row, col)
                if item:
                    item.setBackground(highlight_color)

        self.model().blockSignals(False)
        self.blockSignals(False)
        self.viewport().update()  # 手动触发一锅端重绘（避免逐 item 触发）

    def clear_column_selection(self):
        """清空列选中状态"""
        self._selected_cols.clear()
        self._last_selected_col = -1
        self._update_column_highlight()

    def get_selected_columns(self):
        """获取选中的列索引"""
        return sorted(list(self._selected_cols))


class CheckBoxDelegate(QStyledItemDelegate):
    """自定义复选框委托 - Ant Design 蓝色主题，参照 HTML 预览样式"""

    def __init__(self, parent=None, checkbox_column=0):
        super().__init__(parent)
        self._checkbox_column = checkbox_column
        # Ant Design 蓝色主题色
        self._checked_color = QColor(99, 102, 241)  # #6366f1
        self._border_color = QColor(229, 231, 235)  # #e5e7eb (亮色)
        self._hovered_index = None  # 跟踪悬停的单元格
        self._table_view = None  # 保存表格引用
        self._is_dark = False  # 是否暗色主题

    def setTableView(self, table_view):
        """设置关联的表格视图以启用悬停检测"""
        if self._table_view:
            if self._table_view.viewport():
                self._table_view.viewport().removeEventFilter(self)
            self._table_view.removeEventFilter(self)
        self._table_view = table_view
        if table_view:
            table_view.setMouseTracking(True)
            table_view.viewport().setMouseTracking(True)
            # 事件发送到 viewport，需要在其上安装过滤器
            table_view.viewport().installEventFilter(self)
        # 更新主题
        from ui.theme_manager import load_theme, _is_system_dark, THEME_AUTO, THEME_DARK
        theme = load_theme()
        if theme == THEME_AUTO:
            self._is_dark = _is_system_dark()
        else:
            self._is_dark = theme == THEME_DARK
        # 更新边框颜色
        if self._is_dark:
            self._border_color = QColor(59, 65, 81)  # #3b4151
            self._checked_color = QColor(129, 140, 248)  # #818cf8
        else:
            self._border_color = QColor(229, 231, 235)  # #e5e7eb
            self._checked_color = QColor(99, 102, 241)  # #6366f1

    def update_colors(self, checked_color, unchecked_bg, border_color, checkmark_color):
        """动态更新复选框颜色（支持主题切换）"""
        self._checked_color = QColor(checked_color)
        self._border_color = QColor(border_color)
        self._unchecked_bg = QColor(unchecked_bg)
        self._checkmark_color = QColor(checkmark_color)

    def _get_table_widget(self):
        """获取 QTableWidget 引用"""
        # 优先使用保存的引用
        if self._table_view:
            return self._table_view
        # 回退到 parent()（委托通常直接设置在表格上）
        parent = self.parent()
        if parent:
            from PySide6.QtWidgets import QTableWidget
            if isinstance(parent, QTableWidget):
                return parent
        return None

    def eventFilter(self, obj, event):
        """处理鼠标悬停事件"""
        # 安全检查：确保 _table_view 仍然有效（可能在关闭时已被删除）
        if self._table_view is None:
            return super().eventFilter(obj, event)
        
        try:
            # 检查底层 C++ 对象是否已删除
            if not hasattr(self._table_view, 'isValid') and not self._table_view:
                return super().eventFilter(obj, event)
        except RuntimeError:
            return super().eventFilter(obj, event)
        
        # 处理来自 table_view 本身或其 viewport() 的事件
        try:
            if obj == self._table_view or (self._table_view and obj == self._table_view.viewport()):
                if event.type() == QEvent.Type.MouseMove:
                    index = self._table_view.indexAt(event.pos())
                    if index.isValid() and index.column() == self._checkbox_column:
                        if self._hovered_index != index:
                            self._hovered_index = index
                            # 更新当前单元格区域
                            rect = self._table_view.visualRect(index)
                            self._table_view.viewport().update(rect.x(), rect.y(), rect.width(), rect.height())
                    else:
                        if self._hovered_index is not None:
                            old_index = self._hovered_index
                            self._hovered_index = None
                            rect = self._table_view.visualRect(old_index)
                            self._table_view.viewport().update(rect.x(), rect.y(), rect.width(), rect.height())
                    return False
                elif event.type() == QEvent.Type.Leave:
                    if self._hovered_index is not None:
                        old_index = self._hovered_index
                        self._hovered_index = None
                        rect = self._table_view.visualRect(old_index)
                        self._table_view.viewport().update(rect.x(), rect.y(), rect.width(), rect.height())
                    return False
        except RuntimeError:
            # C++ 对象已被删除
            self._table_view = None
            return super().eventFilter(obj, event)
        
        return super().eventFilter(obj, event)

    def paint(self, painter: QPainter, option, index):
        """绘制复选框"""
        # 只绘制复选框列
        if index.column() != self._checkbox_column:
            super().paint(painter, option, index)
            return

        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # 获取复选框状态 - QTableWidget 使用 table.item() 获取
        table = self._get_table_widget()
        
        if table:
            item = table.item(index.row(), index.column())
        else:
            item = index.model().itemFromIndex(index) if hasattr(index.model(), 'itemFromIndex') else None
        
        if item:
            checked = item.checkState() == Qt.CheckState.Checked
        else:
            checked = False

        # 计算复选框位置（居中）
        box_size = 16
        x = option.rect.x() + (option.rect.width() - box_size) // 2
        y = option.rect.y() + (option.rect.height() - box_size) // 2
        rect = QRect(int(x), int(y), int(box_size), int(box_size))

        # 圆角半径
        radius = 3

        # 检查是否悬停
        is_hovered = (self._hovered_index == index) if self._hovered_index else False

        # 根据主题或动态设置选择颜色
        if hasattr(self, '_unchecked_bg'):
            unchecked_bg = self._unchecked_bg
            checkmark_color = self._checkmark_color
        elif self._is_dark:
            unchecked_bg = QColor(31, 34, 51)  # 深色背景
            checkmark_color = QColor(255, 255, 255)  # 白色勾
        else:
            unchecked_bg = QColor(255, 255, 255)  # 亮色背景
            checkmark_color = QColor(255, 255, 255)  # 白色勾

        if checked:
            # 绘制蓝色填充背景
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(self._checked_color))
            painter.drawRoundedRect(rect, radius, radius)

            # 绘制白色勾
            painter.setPen(QPen(checkmark_color, 1.5))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            # 勾的路径
            path = QPainterPath()
            path.moveTo(x + 3, y + 8)
            path.lineTo(x + 6, y + 11)
            path.lineTo(x + 13, y + 4)
            painter.drawPath(path)
        else:
            # 绘制背景色
            painter.setPen(QPen(self._border_color, 1))
            painter.setBrush(QBrush(unchecked_bg))
            painter.drawRoundedRect(rect, radius, radius)

            # hover 效果 - 悬停时边框变蓝
            if is_hovered:
                painter.setPen(QPen(self._checked_color, 1))
                painter.drawRoundedRect(rect, radius, radius)

        painter.restore()

    def editorEvent(self, event, model, option, index):
        """处理复选框点击事件"""
        # 只处理复选框列
        if index.column() != self._checkbox_column:
            return False

        # 只处理鼠标按下事件（不处理 release，否则会切换两次状态）
        from PySide6.QtCore import QEvent
        if event.type() != QEvent.Type.MouseButtonPress:
            return False

        # 检查点击位置是否在复选框区域内
        box_size = 16
        x = option.rect.x() + (option.rect.width() - box_size) // 2
        y = option.rect.y() + (option.rect.height() - box_size) // 2
        box_rect = QRect(int(x), int(y), int(box_size), int(box_size))

        if box_rect.contains(event.pos()):
            # 切换状态 - QTableWidget 使用 table.item()
            table = self._get_table_widget()
            if table:
                item = table.item(index.row(), index.column())
            else:
                item = model.itemFromIndex(index) if hasattr(model, 'itemFromIndex') else None
            if item:
                new_state = Qt.CheckState.Unchecked if item.checkState() == Qt.CheckState.Checked else Qt.CheckState.Checked
                item.setCheckState(new_state)
                # 强制重绘单元格以更新视觉效果
                if table:
                    rect = table.visualRect(index)
                    table.viewport().update(rect)
                return True

        return False

    def setHoveredIndex(self, index):
        """设置当前悬停的单元格索引"""
        self._hovered_index = index


class HeaderCheckBoxDelegate(QStyledItemDelegate):
    """表头复选框委托 - 自定义全选复选框样式，参照 HTML 预览"""

    def __init__(self, parent=None):
        super().__init__(parent)
        # 紫罗兰强调色（与 CheckBoxDelegate 保持一致）
        self._checked_color = QColor(99, 102, 241)  # #6366f1
        self._border_color = QColor(229, 231, 235)  # #e5e7eb (亮色)
        self._is_hovered = False
        self._header_view = None  # 保存表头引用
        self._table = None  # 保存 QTableWidget 引用
        self._is_dark = False
        self._unchecked_bg = QColor(255, 255, 255)
        self._checkmark_color = QColor(255, 255, 255)

        # 初始化时检测主题
        from ui.theme_manager import load_theme, _is_system_dark, THEME_AUTO, THEME_DARK
        theme = load_theme()
        if theme == THEME_AUTO:
            self._is_dark = _is_system_dark()
        else:
            self._is_dark = theme == THEME_DARK
        # 更新边框颜色
        if self._is_dark:
            self._border_color = QColor(59, 65, 81)  # #3b4151
            self._checked_color = QColor(129, 140, 248)  # #818cf8
            self._unchecked_bg = QColor(31, 34, 51)  # 深色背景
            self._checkmark_color = QColor(255, 255, 255)  # 白色勾
        else:
            self._border_color = QColor(229, 231, 235)  # #e5e7eb
            self._checked_color = QColor(99, 102, 241)  # #6366f1
            self._unchecked_bg = QColor(255, 255, 255)  # 亮色背景
            self._checkmark_color = QColor(255, 255, 255)  # 白色勾

    def update_colors(self, checked_color, unchecked_bg, border_color, checkmark_color):
        """动态更新复选框颜色（支持主题切换）"""
        self._checked_color = QColor(checked_color)
        self._border_color = QColor(border_color)
        self._unchecked_bg = QColor(unchecked_bg)
        self._checkmark_color = QColor(checkmark_color)

    def setHeaderView(self, header_view):
        """设置关联的表头视图以启用悬停检测"""
        if self._header_view:
            self._header_view.removeEventFilter(self)
        self._header_view = header_view
        if header_view:
            header_view.installEventFilter(self)

    def setTable(self, table_view):
        """设置关联的 QTableWidget 引用（直接在 paint 中获取 header_item，避免 parent 链遍历）"""
        self._table = table_view

    def _get_header_widget(self):
        """获取 QHeaderView 引用"""
        if self._header_view:
            return self._header_view
        parent = self.parent()
        from PySide6.QtWidgets import QHeaderView
        if isinstance(parent, QHeaderView):
            return parent
        return None

    def eventFilter(self, obj, event):
        """处理鼠标悬停事件"""
        # 安全检查：确保 _header_view 仍然有效（可能在关闭时已被删除）
        if self._header_view is None or obj != self._header_view:
            return super().eventFilter(obj, event)
        
        try:
            if event.type() == QEvent.Type.MouseMove:
                # 检查是否悬停在第0列
                from PySide6.QtWidgets import QHeaderView
                if isinstance(obj, QHeaderView):
                    section = obj.logicalIndexAt(event.pos())
                    if section == 0:
                        if not self._is_hovered:
                            self._is_hovered = True
                            obj.update()
                    else:
                        if self._is_hovered:
                            self._is_hovered = False
                            obj.update()
                return False
            elif event.type() == QEvent.Type.Leave:
                if self._is_hovered:
                    self._is_hovered = False
                    self._header_view.update()
                return False
        except RuntimeError:
            # C++ 对象已被删除
            self._header_view = None
            return super().eventFilter(obj, event)
        
        return super().eventFilter(obj, event)

    def paint(self, painter: QPainter, option, index):
        """绘制表头复选框"""
        print(f"[DEBUG] HeaderCheckBoxDelegate.paint called, index={index.column() if index.isValid() else 'invalid'}")
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # 先绘制 section 背景和边框（否则 QSS 样式和默认文本会覆盖 delegate）
        tokens = get_theme_tokens(load_theme())
        # 填充 section 背景
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(QColor(tokens['surface_alt'])))
        painter.drawRect(option.rect)
        # 绘制 section 底边框和右边框
        painter.setPen(QPen(QColor(tokens['border']), 1))
        painter.drawLine(option.rect.bottomLeft(), option.rect.bottomRight())
        painter.drawLine(option.rect.topRight(), option.rect.bottomRight())

        # 获取复选框状态 - QTableWidget 使用 horizontalHeaderItem() 获取表头项
        header_item = None
        if self._table:
            # 直接使用保存的 QTableWidget 引用，避免 parent 链遍历不可靠的问题
            header_item = self._table.horizontalHeaderItem(0)
            print(f"[DEBUG] HeaderCheckBoxDelegate.paint: using self._table, header_item={header_item}")
        else:
            # 兜底：通过 parent 链遍历获取 QTableWidget（兼容未调用 setTable 的情况）
            header = self._get_header_widget()
            print(f"[DEBUG] HeaderCheckBoxDelegate.paint: header={header}, _header_view={self._header_view}")
            if header:
                table = header.parent()
                print(f"[DEBUG] HeaderCheckBoxDelegate.paint: header.parent()={table}")
                while table and not hasattr(table, 'horizontalHeaderItem'):
                    table = table.parent()
                    print(f"[DEBUG] HeaderCheckBoxDelegate.paint: traversing, table={table}")
                if table and hasattr(table, 'horizontalHeaderItem'):
                    print(f"[DEBUG] HeaderCheckBoxDelegate.paint: found table with horizontalHeaderItem")
                    header_item = table.horizontalHeaderItem(0)
        
        if header_item:
            checked = header_item.checkState() == Qt.CheckState.Checked
            # 半选中状态（部分选中）
            partially_checked = header_item.checkState() == Qt.CheckState.PartiallyChecked
            print(f"[DEBUG] HeaderCheckBoxDelegate.paint: header_item.checkState()={header_item.checkState()}, checked={checked}, partially_checked={partially_checked}")
        else:
            checked = False
            partially_checked = False
            print(f"[DEBUG] HeaderCheckBoxDelegate.paint: no header_item, using checked=False")

        # 计算复选框位置（居中）
        box_size = 16
        x = option.rect.x() + (option.rect.width() - box_size) // 2
        y = option.rect.y() + (option.rect.height() - box_size) // 2
        rect = QRect(int(x), int(y), int(box_size), int(box_size))

        # 圆角半径
        radius = 3

        # 根据主题或动态设置选择颜色
        if hasattr(self, '_unchecked_bg'):
            unchecked_bg = self._unchecked_bg
            checkmark_color = self._checkmark_color
        elif self._is_dark:
            unchecked_bg = QColor(31, 34, 51)  # 深色背景
            checkmark_color = QColor(255, 255, 255)  # 白色勾
        else:
            unchecked_bg = QColor(255, 255, 255)  # 亮色背景
            checkmark_color = QColor(255, 255, 255)  # 白色勾

        if checked:
            # 绘制蓝色填充背景
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(self._checked_color))
            painter.drawRoundedRect(rect, radius, radius)

            # 绘制白色勾
            painter.setPen(QPen(checkmark_color, 1.5))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            path = QPainterPath()
            path.moveTo(x + 3, y + 8)
            path.lineTo(x + 6, y + 11)
            path.lineTo(x + 13, y + 4)
            painter.drawPath(path)
        elif partially_checked:
            # 半选中状态 - 蓝色背景 + 白色短横线
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(self._checked_color))
            painter.drawRoundedRect(rect, radius, radius)

            # 绘制白色短横线
            painter.setPen(QPen(checkmark_color, 2))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawLine(int(x + 4), int(y + 8), int(x + 12), int(y + 8))
        else:
            # 未选中状态
            painter.setPen(QPen(self._border_color, 1))
            painter.setBrush(QBrush(unchecked_bg))
            painter.drawRoundedRect(rect, radius, radius)

            # hover 效果
            if self._is_hovered:
                painter.setPen(QPen(self._checked_color, 1))
                painter.drawRoundedRect(rect, radius, radius)

        painter.restore()

    def editorEvent(self, event, model, option, index):
        """处理表头复选框点击 — 不自行切换状态，交给 sectionClicked → _on_header_clicked 统一处理"""
        from PySide6.QtCore import QEvent
        # 只处理鼠标按下事件
        if event.type() != QEvent.Type.MouseButtonPress:
            return False

        # 检查点击位置是否在复选框区域内
        box_size = 16
        x = option.rect.x() + (option.rect.width() - box_size) // 2
        y = option.rect.y() + (option.rect.height() - box_size) // 2
        box_rect = QRect(int(x), int(y), int(box_size), int(box_size))

        if box_rect.contains(event.pos()):
            # 不自行切换状态，返回 False 让 QHeaderView 发出 sectionClicked
            # sectionClicked → _on_header_clicked 负责统一处理全选/取消
            return False

        return False

    def setHovered(self, hovered: bool):
        """设置悬停状态"""
        self._is_hovered = hovered