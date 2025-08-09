from PyQt6.QtCore import QRect, QPoint

class CoordinateConverter:
    """Handles coordinate conversion between desktop and widget space"""
    
    def __init__(self, virtual_geometry: QRect):
        self.virtual_geometry = virtual_geometry
    
    def desktop_to_widget(self, point_or_rect):
        """Convert desktop coordinates to widget coordinates"""
        if isinstance(point_or_rect, QPoint):
            return point_or_rect - self.virtual_geometry.topLeft()
        elif isinstance(point_or_rect, QRect):
            widget_top_left = self.desktop_to_widget(point_or_rect.topLeft())
            return QRect(widget_top_left, point_or_rect.size())
    
    def widget_to_desktop(self, point_or_rect):
        """Convert widget coordinates to desktop coordinates"""
        if isinstance(point_or_rect, QPoint):
            return point_or_rect + self.virtual_geometry.topLeft()
        elif isinstance(point_or_rect, QRect):
            desktop_top_left = self.widget_to_desktop(point_or_rect.topLeft())
            return QRect(desktop_top_left, point_or_rect.size())