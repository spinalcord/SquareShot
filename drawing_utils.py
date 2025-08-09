from PyQt6.QtGui import QPainter, QPen, QColor, QFont
from PyQt6.QtCore import Qt, QPoint
from dataclasses import dataclass
from config import Config

@dataclass
class DrawStyle:
    """Drawing style configuration"""
    thickness: int
    color: QColor
    
    @property
    def outline_color(self) -> QColor:
        """Get contrasting outline color"""
        return QColor(255, 255, 255) if self.color != QColor(255, 255, 255) else QColor(0, 0, 0)
    
    @property
    def outline_thickness(self) -> int:
        return self.thickness + Config.OUTLINE_THICKNESS_OFFSET
    
    def copy(self) -> 'DrawStyle':
        """Create a copy of this style"""
        return DrawStyle(self.thickness, QColor(self.color))


class DrawHelper:
    """Helper class for common drawing operations"""
    
    @staticmethod
    def draw_with_outline(painter: QPainter, style: DrawStyle, draw_func):
        """Draw shape with outline using provided function"""
        # Draw outline first
        outline_pen = QPen(style.outline_color, style.outline_thickness, 
                          Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
        painter.setPen(outline_pen)
        painter.setBrush(style.outline_color)
        draw_func(painter, True)  # True = outline mode
        
        # Draw main shape
        main_pen = QPen(style.color, style.thickness, 
                       Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
        painter.setPen(main_pen)
        painter.setBrush(style.color)
        draw_func(painter, False)  # False = main mode
    
    @staticmethod
    def draw_text_with_outline(painter: QPainter, pos: QPoint, text: str, style: DrawStyle):
        """Draw text with outline for visibility"""
        font = QFont("Arial", max(Config.MIN_FONT_SIZE, style.thickness * Config.TEXT_FONT_SCALE))
        font.setBold(True)
        painter.setFont(font)
        
        # Draw outline
        for dx in [-1, 0, 1]:
            for dy in [-1, 0, 1]:
                if dx != 0 or dy != 0:
                    painter.setPen(QPen(style.outline_color, 1))
                    painter.drawText(pos + QPoint(dx, dy), text)
        
        # Draw main text
        painter.setPen(QPen(style.color))
        painter.drawText(pos, text)