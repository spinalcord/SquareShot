from enum import Enum
from PyQt6.QtGui import QColor
import math

class Config:
    MIN_SELECTION_SIZE = 10
    MIN_ARROW_LENGTH = 10
    MIN_RECT_SIZE = 5
    ARROWHEAD_ANGLE = math.pi / 5  # 36 degrees
    ARROWHEAD_SCALE = 4
    ARROWHEAD_WIDTH_SCALE = 2.5
    ARROWHEAD_OFFSET = 0.3
    TEXT_FONT_SCALE = 2
    MIN_FONT_SIZE = 12
    OUTLINE_THICKNESS_OFFSET = 2
    OVERLAY_ALPHA = 120
    SELECTION_BORDER_WIDTH = 2
    SELECTION_COLOR = QColor(0, 150, 255)
    MAX_HISTORY = 20


class AnnotationMode(Enum):
    NONE = 0
    ARROW = 1
    RECTANGLE = 2
    TEXT = 3


class AnnotationType(Enum):
    ARROW = 1
    RECTANGLE = 2
    TEXT = 3


class AnnotationColor(Enum):
    RED = QColor(255, 0, 0)
    BLUE = QColor(0, 0, 255)
    GREEN = QColor(0, 255, 0)
    YELLOW = QColor(255, 255, 0)
    PURPLE = QColor(128, 0, 128)