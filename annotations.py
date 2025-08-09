import math
from PyQt6.QtGui import QPainter, QPolygonF, QPen
from PyQt6.QtCore import QPointF, Qt
from PyQt6.QtCore import QRect, QPoint
from config import AnnotationType, Config
from drawing_utils import DrawStyle, DrawHelper

class Annotation:
    """Base class for annotations"""
    def __init__(self, annotation_type: AnnotationType, style: DrawStyle):
        self.type = annotation_type
        self.style = style
    
    def draw(self, painter: QPainter):
        """Override in subclasses"""
        pass


class ArrowAnnotation(Annotation):
    def __init__(self, start: QPoint, end: QPoint, style: DrawStyle):
        super().__init__(AnnotationType.ARROW, style)
        self.start = start
        self.end = end
    
    def draw(self, painter: QPainter):
        # Check minimum length
        length = math.sqrt((self.end.x() - self.start.x())**2 + (self.end.y() - self.start.y())**2)
        if length < Config.MIN_ARROW_LENGTH:
            return
        
        # Calculate arrow geometry
        angle = math.atan2(self.end.y() - self.start.y(), self.end.x() - self.start.x())
        arrowhead_length = max(12, self.style.thickness * Config.ARROWHEAD_SCALE)
        
        # Calculate line end and arrowhead
        line_end_x = self.end.x() - arrowhead_length * Config.ARROWHEAD_OFFSET * math.cos(angle)
        line_end_y = self.end.y() - arrowhead_length * Config.ARROWHEAD_OFFSET * math.sin(angle)
        line_end = QPoint(int(line_end_x), int(line_end_y))
        
        # Arrowhead points
        x1 = self.end.x() - arrowhead_length * math.cos(angle - Config.ARROWHEAD_ANGLE)
        y1 = self.end.y() - arrowhead_length * math.sin(angle - Config.ARROWHEAD_ANGLE)
        x2 = self.end.x() - arrowhead_length * math.cos(angle + Config.ARROWHEAD_ANGLE)
        y2 = self.end.y() - arrowhead_length * math.sin(angle + Config.ARROWHEAD_ANGLE)
        
        arrowhead = QPolygonF([
            QPointF(self.end.x(), self.end.y()),
            QPointF(x1, y1),
            QPointF(line_end_x, line_end_y),
            QPointF(x2, y2)
        ])
        
        def draw_arrow(painter, is_outline):
            painter.drawLine(self.start, line_end)
            if not is_outline:
                painter.setPen(QPen(self.style.color, 1))
            painter.drawPolygon(arrowhead)
        
        DrawHelper.draw_with_outline(painter, self.style, draw_arrow)


class RectangleAnnotation(Annotation):
    def __init__(self, rect: QRect, style: DrawStyle):
        super().__init__(AnnotationType.RECTANGLE, style)
        self.rect = rect
    
    def draw(self, painter: QPainter):
        def draw_rect(painter, is_outline):
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRect(self.rect)
        
        DrawHelper.draw_with_outline(painter, self.style, draw_rect)


class TextAnnotation(Annotation):
    def __init__(self, position: QPoint, text: str, style: DrawStyle):
        super().__init__(AnnotationType.TEXT, style)
        self.position = position
        self.text = text
    
    def draw(self, painter: QPainter):
        if self.text:
            DrawHelper.draw_text_with_outline(painter, self.position, self.text, self.style)