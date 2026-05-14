"""
icon_manager.py
图标管理器 - 提供统一的现代化图标系统
"""
from PySide6.QtGui import QIcon, QPixmap, QPainter, QColor, QPen, QFont, QPolygon
from PySide6.QtCore import Qt, QPointF, QRectF
from ui.theme_manager import get_theme_tokens, load_theme


class IconManager:
    """图标管理器"""
    
    @staticmethod
    def _create_icon(draw_func, size=16):
        """创建图标的辅助函数"""
        pix = QPixmap(size, size)
        pix.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pix)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        draw_func(painter, size)
        painter.end()
        return QIcon(pix)
    
    @staticmethod
    def new_connection(tokens=None, size=16):
        """新建连接图标"""
        if tokens is None:
            tokens = get_theme_tokens(load_theme())
        
        def draw(painter, size):
            margin = size * 0.15
            db_width = size - 2 * margin
            db_height = size * 0.6
            
            painter.setBrush(QColor(tokens["accent"]))
            painter.setPen(Qt.PenStyle.NoPen)
            
            painter.drawEllipse(margin, margin, db_width, db_height * 0.4)
            painter.drawRect(margin, margin + db_height * 0.2, db_width, db_height * 0.6)
            painter.drawEllipse(margin, margin + db_height * 0.6, db_width, db_height * 0.4)
            
            plus_size = size * 0.35
            plus_x = size - plus_size - 1
            plus_y = size - plus_size - 1
            painter.setPen(QPen(QColor("#ffffff"), 2))
            painter.drawLine(plus_x + 2, plus_y + plus_size // 2, 
                           plus_x + plus_size - 2, plus_y + plus_size // 2)
            painter.drawLine(plus_x + plus_size // 2, plus_y + 2, 
                           plus_x + plus_size // 2, plus_y + plus_size - 2)
        
        return IconManager._create_icon(draw, size)
    
    @staticmethod
    def refresh(tokens=None, size=16):
        """刷新图标"""
        if tokens is None:
            tokens = get_theme_tokens(load_theme())
        
        def draw(painter, size):
            center = size / 2
            radius = size * 0.35
            painter.setPen(QPen(QColor(tokens["accent"]), 2))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            
            rect = QRectF(center - radius, center - radius, radius * 2, radius * 2)
            painter.drawArc(rect, 30 * 16, 270 * 16)
            
            arrow_size = size * 0.15
            painter.setBrush(QColor(tokens["accent"]))
            painter.setPen(Qt.PenStyle.NoPen)
            points = [
                QPointF(center + radius - 2, center - radius + 2),
                QPointF(center + radius - 2 - arrow_size, center - radius + 2 - arrow_size),
                QPointF(center + radius - 2 + arrow_size * 0.3, center - radius + 2 + arrow_size * 0.5)
            ]
            polygon = QPolygon(points)
            painter.drawPolygon(polygon)
        
        return IconManager._create_icon(draw, size)
    
    @staticmethod
    def execute(tokens=None, size=16):
        """执行图标"""
        if tokens is None:
            tokens = get_theme_tokens(load_theme())
        
        def draw(painter, size):
            margin = size * 0.2
            painter.setBrush(QColor(tokens["success"]))
            painter.setPen(Qt.PenStyle.NoPen)
            
            points = [
                QPointF(margin, margin),
                QPointF(margin, size - margin),
                QPointF(size - margin, size / 2)
            ]
            polygon = QPolygon(points)
            painter.drawPolygon(polygon)
        
        return IconManager._create_icon(draw, size)
    
    @staticmethod
    def chat(tokens=None, size=16):
        """聊天图标"""
        if tokens is None:
            tokens = get_theme_tokens(load_theme())
        
        def draw(painter, size):
            margin = size * 0.15
            painter.setBrush(QColor(tokens["accent"]))
            painter.setPen(Qt.PenStyle.NoPen)
            
            rect = QRectF(margin, margin, size - 2 * margin, size * 0.65)
            painter.drawRoundedRect(rect, 3, 3)
            
            tail_points = [
                QPointF(size * 0.3, margin + size * 0.65),
                QPointF(size * 0.3, size - margin),
                QPointF(size * 0.45, margin + size * 0.65)
            ]
            polygon = QPolygon(tail_points)
            painter.drawPolygon(polygon)
        
        return IconManager._create_icon(draw, size)
    
    @staticmethod
    def export_import(tokens=None, size=16):
        """导入导出图标"""
        if tokens is None:
            tokens = get_theme_tokens(load_theme())
        
        def draw(painter, size):
            margin = size * 0.2
            painter.setPen(QPen(QColor(tokens["accent"]), 2))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            
            mid_x = size / 2
            painter.drawLine(mid_x, margin + 2, mid_x, size / 2 - 2)
            
            up_arrow = QPolygon([
                QPointF(mid_x - 3, margin + 4),
                QPointF(mid_x, margin),
                QPointF(mid_x + 3, margin + 4)
            ])
            painter.drawPolyline(up_arrow)
            
            painter.drawLine(mid_x, size / 2 + 2, mid_x, size - margin - 2)
            down_arrow = QPolygon([
                QPointF(mid_x - 3, size - margin - 4),
                QPointF(mid_x, size - margin),
                QPointF(mid_x + 3, size - margin - 4)
            ])
            painter.drawPolyline(down_arrow)
        
        return IconManager._create_icon(draw, size)
    
    @staticmethod
    def database(tokens=None, size=16):
        """数据库图标"""
        if tokens is None:
            tokens = get_theme_tokens(load_theme())
        
        def draw(painter, size):
            margin = size * 0.15
            db_width = size - 2 * margin
            db_height = size - 2 * margin
            
            painter.setBrush(QColor(tokens["accent"]))
            painter.setPen(Qt.PenStyle.NoPen)
            
            painter.drawEllipse(margin, margin, db_width, db_height * 0.35)
            painter.drawRect(margin, margin + db_height * 0.17, db_width, db_height * 0.66)
            painter.drawEllipse(margin, margin + db_height * 0.65, db_width, db_height * 0.35)
        
        return IconManager._create_icon(draw, size)
    
    @staticmethod
    def table(tokens=None, size=16):
        """表格图标"""
        if tokens is None:
            tokens = get_theme_tokens(load_theme())
        
        def draw(painter, size):
            margin = size * 0.15
            grid_size = size - 2 * margin
            
            painter.setBrush(QColor(tokens["accent_soft"]))
            painter.setPen(QPen(QColor(tokens["border_strong"]), 1))
            
            rect = QRectF(margin, margin, grid_size, grid_size)
            painter.drawRoundedRect(rect, 2, 2)
            
            painter.drawLine(margin, margin + grid_size * 0.33, 
                           margin + grid_size, margin + grid_size * 0.33)
            painter.drawLine(margin, margin + grid_size * 0.66, 
                           margin + grid_size, margin + grid_size * 0.66)
        
        return IconManager._create_icon(draw, size)
    
    @staticmethod
    def view(tokens=None, size=16):
        """视图图标"""
        if tokens is None:
            tokens = get_theme_tokens(load_theme())
        
        def draw(painter, size):
            center = size / 2
            eye_width = size * 0.7
            eye_height = size * 0.4
            
            painter.setPen(QPen(QColor(tokens["success"]), 1.5))
            painter.setBrush(QColor(tokens["success_soft"]))
            
            painter.drawEllipse(QRectF(center - eye_width/2, center - eye_height/2, 
                                      eye_width, eye_height))
            
            pupil_size = size * 0.2
            painter.setBrush(QColor(tokens["success"]))
            painter.drawEllipse(QRectF(center - pupil_size/2, center - pupil_size/2, 
                                      pupil_size, pupil_size))
        
        return IconManager._create_icon(draw, size)
    
    @staticmethod
    def function(tokens=None, size=16):
        """函数图标"""
        if tokens is None:
            tokens = get_theme_tokens(load_theme())
        
        def draw(painter, size):
            margin = size * 0.15
            
            painter.setBrush(QColor(tokens["warning_soft"]))
            painter.setPen(QPen(QColor(tokens["warning"]), 1))
            
            rect = QRectF(margin, margin, size - 2*margin, size - 2*margin)
            painter.drawRoundedRect(rect, 3, 3)
            
            painter.setPen(QColor(tokens["warning"]))
            font = QFont("Arial", int(size * 0.45), QFont.Weight.Bold)
            painter.setFont(font)
            painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, "fx")
        
        return IconManager._create_icon(draw, size)
    
    @staticmethod
    def sync(tokens=None, size=16):
        """同步图标"""
        if tokens is None:
            tokens = get_theme_tokens(load_theme())
        
        def draw(painter, size):
            center = size / 2
            radius = size * 0.3
            
            painter.setPen(QPen(QColor(tokens["accent"]), 2))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            
            rect1 = QRectF(center - radius, center - radius - 2, radius * 2, radius * 1.5)
            painter.drawArc(rect1, 0 * 16, 180 * 16)
            
            rect2 = QRectF(center - radius, center - radius + 2, radius * 2, radius * 1.5)
            painter.drawArc(rect2, 180 * 16, 180 * 16)
        
        return IconManager._create_icon(draw, size)
    
    @staticmethod
    def backup(tokens=None, size=16):
        """备份图标"""
        if tokens is None:
            tokens = get_theme_tokens(load_theme())
        
        def draw(painter, size):
            margin = size * 0.15
            
            painter.setBrush(QColor(tokens["accent_soft"]))
            painter.setPen(QPen(QColor(tokens["accent"]), 1.5))
            
            box_rect = QRectF(margin, margin * 2, size - 2*margin, size * 0.6)
            painter.drawRoundedRect(box_rect, 2, 2)
            
            lid_rect = QRectF(margin - 1, margin, size - 2*margin + 2, size * 0.25)
            painter.drawRoundedRect(lid_rect, 2, 2)
        
        return IconManager._create_icon(draw, size)
    
    @staticmethod
    def scheduler(tokens=None, size=16):
        """调度器图标"""
        if tokens is None:
            tokens = get_theme_tokens(load_theme())
        
        def draw(painter, size):
            center = size / 2
            radius = size * 0.35
            
            painter.setPen(QPen(QColor(tokens["accent"]), 1.5))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            
            circle = QRectF(center - radius, center - radius, radius * 2, radius * 2)
            painter.drawEllipse(circle)
            
            painter.setPen(QPen(QColor(tokens["accent"]), 2))
            painter.drawLine(center, center, center, center - radius * 0.5)
            painter.drawLine(center, center, center + radius * 0.6, center)
        
        return IconManager._create_icon(draw, size)
    
    @staticmethod
    def skill(tokens=None, size=16):
        """技能图标"""
        if tokens is None:
            tokens = get_theme_tokens(load_theme())
        
        def draw(painter, size):
            center = size / 2
            outer_r = size * 0.35
            inner_r = size * 0.15
            
            painter.setBrush(QColor(tokens["warning"]))
            painter.setPen(Qt.PenStyle.NoPen)
            
            import math
            points = []
            for i in range(10):
                angle = math.pi / 2 + i * math.pi / 5
                r = outer_r if i % 2 == 0 else inner_r
                x = center + r * math.cos(angle)
                y = center - r * math.sin(angle)
                points.append(QPointF(x, y))
            
            polygon = QPolygon(points)
            painter.drawPolygon(polygon)
        
        return IconManager._create_icon(draw, size)
    
    @staticmethod
    def settings(tokens=None, size=16):
        """设置图标"""
        if tokens is None:
            tokens = get_theme_tokens(load_theme())
        
        def draw(painter, size):
            center = size / 2
            outer_r = size * 0.38
            hole_r = size * 0.12
            
            painter.setBrush(QColor(tokens["text_muted"]))
            painter.setPen(Qt.PenStyle.NoPen)
            
            circle = QRectF(center - outer_r, center - outer_r, outer_r * 2, outer_r * 2)
            painter.drawEllipse(circle)
            
            painter.setBrush(QColor(tokens["surface"]))
            hole = QRectF(center - hole_r, center - hole_r, hole_r * 2, hole_r * 2)
            painter.drawEllipse(hole)
        
        return IconManager._create_icon(draw, size)
    
    @staticmethod
    def stop(tokens=None, size=16):
        """停止图标"""
        if tokens is None:
            tokens = get_theme_tokens(load_theme())
        
        def draw(painter, size):
            margin = size * 0.25
            
            painter.setBrush(QColor(tokens["danger"]))
            painter.setPen(Qt.PenStyle.NoPen)
            
            rect = QRectF(margin, margin, size - 2*margin, size - 2*margin)
            painter.drawRoundedRect(rect, 2, 2)
        
        return IconManager._create_icon(draw, size)
    
    @staticmethod
    def send(tokens=None, size=16):
        """发送图标"""
        if tokens is None:
            tokens = get_theme_tokens(load_theme())
        
        def draw(painter, size):
            margin = size * 0.15
            
            painter.setBrush(QColor(tokens["accent"]))
            painter.setPen(Qt.PenStyle.NoPen)
            
            points = [
                QPointF(margin, size / 2),
                QPointF(size - margin, margin),
                QPointF(size * 0.6, size / 2),
                QPointF(size - margin, size - margin)
            ]
            polygon = QPolygon(points)
            painter.drawPolygon(polygon)
        
        return IconManager._create_icon(draw, size)