import sys
import time
from typing import List
from PyQt6.QtWidgets import QApplication, QWidget, QFileDialog
from PyQt6.QtCore import Qt, QRect, QPoint, QMimeData
from PyQt6.QtGui import QPainter, QPen, QColor, QPixmap, QCursor, QFont

from config import Config, AnnotationMode, AnnotationColor
from drawing_utils import DrawStyle, DrawHelper
from annotations import Annotation, ArrowAnnotation, RectangleAnnotation, TextAnnotation
from coordinate_converter import CoordinateConverter
from screenshot_utils import MultiMonitorScreenshot
from clipboard_manager import ClipboardManager


class ScreenshotOverlay(QWidget):
    """Fullscreen overlay for screenshot selection and annotation"""
    
    def __init__(self):
        super().__init__()
        
        # Initialize core components
        self.virtual_geometry = MultiMonitorScreenshot.get_virtual_geometry()
        self.coord_converter = CoordinateConverter(self.virtual_geometry)
        self.background_screenshot = MultiMonitorScreenshot.capture_all_screens()
        
        # Selection state
        self.selection_rect = QRect()
        self.is_selecting = False
        self.selection_start = QPoint()
        self.selection_complete = False
        
        # Annotation state
        self.annotation_mode = AnnotationMode.NONE
        self.current_color_index = 0
        self.colors = list(AnnotationColor)
        self.current_style = DrawStyle(thickness=3, color=self.colors[self.current_color_index].value)
        self.annotations: List[Annotation] = []
        self.annotation_history: List[List[Annotation]] = []
        self.history_index = -1
        
        # Drawing state
        self.is_drawing = False
        self.draw_start_point = QPoint()
        self.current_rect = QRect()
        self.current_arrow_end = QPoint()
        
        # Text editing state
        self.is_text_editing = False
        self.text_position = QPoint()
        self.current_text = ""
        self.text_cursor_position = 0
        
        # Exit state
        self._is_exiting = False
        
        self.setup_ui()
    
    def setup_ui(self):
        """Setup the overlay UI"""
        self.setWindowFlags(
            Qt.WindowType.WindowStaysOnTopHint | 
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.BypassWindowManagerHint
        )
        
        self.setGeometry(self.virtual_geometry)
        self.setWindowState(Qt.WindowState.WindowFullScreen)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setCursor(QCursor(Qt.CursorShape.CrossCursor))
        
        self.setFocus()
        self.grabKeyboard()
    
    def add_to_history(self):
        """Add current state to history"""
        self.annotation_history = self.annotation_history[:self.history_index + 1]
        self.annotation_history.append(self.annotations.copy())
        self.history_index += 1
        
        if len(self.annotation_history) > Config.MAX_HISTORY:
            self.annotation_history.pop(0)
            self.history_index -= 1
    
    def undo(self):
        """Undo last annotation"""
        if self.history_index > 0:
            self.history_index -= 1
            self.annotations = self.annotation_history[self.history_index].copy()
            self.update()
            print("Undo")
    
    def redo(self):
        """Redo last undone annotation"""
        if self.history_index < len(self.annotation_history) - 1:
            self.history_index += 1
            self.annotations = self.annotation_history[self.history_index].copy()
            self.update()
            print("Redo")
    
    def set_annotation_mode(self, mode: AnnotationMode):
        """Set annotation mode"""
        self.annotation_mode = mode
        print(f"Annotation mode: {mode.name}")
    
    def finish_text_editing(self):
        """Complete text editing and save annotation"""
        if self.is_text_editing and self.current_text.strip():
            annotation = TextAnnotation(self.text_position, self.current_text.strip(), self.current_style.copy())
            self.annotations.append(annotation)
            self.add_to_history()
        
        self.is_text_editing = False
        self.current_text = ""
        self.update()
    
    def get_selected_pixmap_with_annotations(self) -> QPixmap:
        """Get selected area with annotations"""
        if not self.selection_rect.isValid():
            return QPixmap()
        
        base_pixmap = MultiMonitorScreenshot.extract_rect_from_pixmap(
            self.background_screenshot, self.selection_rect, self.virtual_geometry
        )
        
        if base_pixmap.isNull():
            return QPixmap()
        
        # Draw annotations
        painter = QPainter(base_pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        selection_widget_rect = self.coord_converter.desktop_to_widget(self.selection_rect)
        painter.translate(-selection_widget_rect.topLeft())
        
        for annotation in self.annotations:
            annotation.draw(painter)
        
        painter.end()
        return base_pixmap
    
    def mousePressEvent(self, event):
        """Handle mouse press"""
        if self._is_exiting:
            return
            
        widget_pos = event.position().toPoint()
        desktop_pos = self.coord_converter.widget_to_desktop(widget_pos)
        
        if event.button() == Qt.MouseButton.LeftButton:
            if not self.selection_complete:
                # Erste Auswahl - starte neue Selektion
                self.is_selecting = True
                self.selection_start = desktop_pos
                self.selection_rect = QRect()
            else:
                # Prüfe ob Klick außerhalb der aktuellen Auswahl ist
                selection_widget = self.coord_converter.desktop_to_widget(self.selection_rect)
                if not selection_widget.contains(widget_pos):
                    # Klick außerhalb - starte neue Auswahl
                    self._start_new_selection(desktop_pos)
                else:
                    # Klick innerhalb - normale Annotation
                    self._handle_annotation_click(widget_pos)
    
    def _start_new_selection(self, desktop_pos: QPoint):
        """Start a new area selection, clearing previous state"""
        print("Starting new selection...")
        
        # Reset selection state
        self.selection_complete = False
        self.is_selecting = True
        self.selection_start = desktop_pos
        self.selection_rect = QRect()
        
        # Clear annotation state
        self.annotation_mode = AnnotationMode.NONE
        self.annotations.clear()
        self.annotation_history.clear()
        self.history_index = -1
        
        # Clear drawing state
        self.is_drawing = False
        self.current_rect = QRect()
        self.current_arrow_end = QPoint()
        
        # Clear text editing state
        self.finish_text_editing()
        
        self.update()

    def _handle_annotation_click(self, widget_pos: QPoint):
        """Handle annotation mode clicks"""
        if self.annotation_mode == AnnotationMode.NONE:
            return
        
        if self.is_text_editing and self.annotation_mode == AnnotationMode.TEXT:
            self.finish_text_editing()
            self._start_text_editing(widget_pos)
        elif self.is_text_editing:
            self.finish_text_editing()
        
        self.is_drawing = True
        self.draw_start_point = widget_pos
        
        if self.annotation_mode == AnnotationMode.TEXT:
            self._start_text_editing(widget_pos)
    
    def _start_text_editing(self, pos: QPoint):
        """Start text editing at position"""
        self.is_text_editing = True
        self.text_position = pos
        self.current_text = ""
        self.text_cursor_position = 0
        self.is_drawing = False
        print("Text editing started - type your text, press Enter to finish")
        self.update()
    
    def mouseMoveEvent(self, event):
        """Handle mouse move"""
        if self._is_exiting:
            return
            
        widget_pos = event.position().toPoint()
        desktop_pos = self.coord_converter.widget_to_desktop(widget_pos)
        
        if self.is_selecting:
            self.selection_rect = QRect(self.selection_start, desktop_pos).normalized()
            self.update()
        elif self.is_drawing and self.annotation_mode in [AnnotationMode.ARROW, AnnotationMode.RECTANGLE]:
            if self.annotation_mode == AnnotationMode.RECTANGLE:
                self.current_rect = QRect(self.draw_start_point, widget_pos).normalized()
            elif self.annotation_mode == AnnotationMode.ARROW:
                self.current_arrow_end = widget_pos
            self.update()
    
    def mouseReleaseEvent(self, event):
        """Handle mouse release"""
        if self._is_exiting:
            return
            
        if event.button() != Qt.MouseButton.LeftButton:
            return
        
        widget_pos = event.position().toPoint()
        
        if self.is_selecting:
            self._complete_selection()
        elif self.is_drawing:
            self._complete_drawing(widget_pos)
        
        self.update()
    
    def _complete_selection(self):
        """Complete area selection"""
        self.is_selecting = False
        if (self.selection_rect.width() > Config.MIN_SELECTION_SIZE and 
            self.selection_rect.height() > Config.MIN_SELECTION_SIZE):
            self.selection_complete = True
            print(f"Selection complete: {self.selection_rect}")
            print("Use keys 1-3 to annotate, Ctrl+C to copy, Ctrl+S to save")
            self.annotation_history = [[]]
            self.history_index = 0
    
    def _complete_drawing(self, end_pos: QPoint):
        """Complete annotation drawing"""
        self.is_drawing = False
        annotation = None
        
        if self.annotation_mode == AnnotationMode.ARROW:
            length = ((end_pos.x() - self.draw_start_point.x())**2 + 
                               (end_pos.y() - self.draw_start_point.y())**2)**0.5
            if length >= Config.MIN_ARROW_LENGTH:
                annotation = ArrowAnnotation(self.draw_start_point, end_pos, self.current_style.copy())
        
        elif self.annotation_mode == AnnotationMode.RECTANGLE:
            rect = QRect(self.draw_start_point, end_pos).normalized()
            if rect.width() > Config.MIN_RECT_SIZE and rect.height() > Config.MIN_RECT_SIZE:
                annotation = RectangleAnnotation(rect, self.current_style.copy())
        
        if annotation:
            self.annotations.append(annotation)
            self.add_to_history()
        
        self.current_rect = QRect()
        self.current_arrow_end = QPoint()
    
    def wheelEvent(self, event):
        """Adjust thickness with mouse wheel"""
        if self._is_exiting:
            return
            
        if self.selection_complete:
            delta = event.angleDelta().y()
            if delta > 0:
                self.current_style.thickness = min(20, self.current_style.thickness + 1)
            else:
                self.current_style.thickness = max(1, self.current_style.thickness - 1)
            print(f"Thickness: {self.current_style.thickness}")
            self.update()
            event.accept()

    def _prepare_exit(self):
        """Prepare for exit by cleaning up"""
        if self._is_exiting:
            return
            
        self._is_exiting = True
        self.finish_text_editing()
        
        if hasattr(self, 'grabKeyboard'):
            self.releaseKeyboard()
        
        # Remove BypassWindowManagerHint for proper focus management
        self.setWindowFlags(
            Qt.WindowType.WindowStaysOnTopHint | 
            Qt.WindowType.FramelessWindowHint
        )
        self.show()
        QApplication.processEvents()
        self.hide()
        QApplication.processEvents()

    def _exit_application(self):
        """Exit the application consistently"""
        self._prepare_exit()
        self.close()
        QApplication.quit()

    def _exit_with_focus_restore(self):
        """Exit with proper focus restoration like Ctrl+C/Ctrl+S"""
        self._prepare_exit()
        time.sleep(0.3)  # Same delay as in copy_to_clipboard and save
        self.close()
        QApplication.quit()

    def keyPressEvent(self, event):
        """Handle keyboard input"""
        if self._is_exiting:
            return
            
        key = event.key()
        modifiers = event.modifiers()
        text = event.text()
        
        if self.is_text_editing:
            self._handle_text_input(key, text)
            event.accept()
            return
        
        # Shortcuts
        shortcuts = {
            (Qt.Key.Key_S, Qt.KeyboardModifier.ControlModifier): self.save_screenshot,
            (Qt.Key.Key_C, Qt.KeyboardModifier.ControlModifier): self.copy_to_clipboard,
            (Qt.Key.Key_Z, Qt.KeyboardModifier.ControlModifier): self.undo,
            (Qt.Key.Key_R, Qt.KeyboardModifier.ControlModifier): self.redo,
            (Qt.Key.Key_Escape, 0): self._exit_with_focus_restore,
            (Qt.Key.Key_1, 0): lambda: self._switch_mode(AnnotationMode.ARROW),
            (Qt.Key.Key_2, 0): lambda: self._switch_mode(AnnotationMode.RECTANGLE),
            (Qt.Key.Key_3, 0): lambda: self._switch_mode(AnnotationMode.TEXT),
            (Qt.Key.Key_4, 0): self._cycle_color,
        }
        
        for (shortcut_key, shortcut_mod), action in shortcuts.items():
            if key == shortcut_key and (not shortcut_mod or modifiers & shortcut_mod):
                action()
                break
        
        event.accept()
    
    def _handle_text_input(self, key: int, text: str):
        """Handle text input during text editing"""
        if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self.finish_text_editing()
        elif key == Qt.Key.Key_Escape:
            self.is_text_editing = False
            self.current_text = ""
            self.update()
        elif key == Qt.Key.Key_Backspace and self.text_cursor_position > 0:
            self.current_text = self.current_text[:self.text_cursor_position - 1] + self.current_text[self.text_cursor_position:]
            self.text_cursor_position -= 1
            self.update()
        elif key == Qt.Key.Key_Delete and self.text_cursor_position < len(self.current_text):
            self.current_text = self.current_text[:self.text_cursor_position] + self.current_text[self.text_cursor_position + 1:]
            self.update()
        elif key == Qt.Key.Key_Left:
            self.text_cursor_position = max(0, self.text_cursor_position - 1)
            self.update()
        elif key == Qt.Key.Key_Right:
            self.text_cursor_position = min(len(self.current_text), self.text_cursor_position + 1)
            self.update()
        elif text and text.isprintable():
            self.current_text = (
                self.current_text[:self.text_cursor_position] +
                text +
                self.current_text[self.text_cursor_position:]
            )
            self.text_cursor_position += len(text)
            self.update()
    
    def _switch_mode(self, mode: AnnotationMode):
        """Switch annotation mode"""
        self.finish_text_editing()
        self.set_annotation_mode(mode)

    def _cycle_color(self):
        """Cycle through annotation colors"""
        self.current_color_index = (self.current_color_index + 1) % len(self.colors)
        self.current_style.color = self.colors[self.current_color_index].value
        print(f"Annotation color: {self.colors[self.current_color_index].name}")
        self.update()
    
    def paintEvent(self, event):
        """Paint the overlay"""
        if self._is_exiting:
            return
            
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # Draw background
        painter.drawPixmap(0, 0, self.background_screenshot)
        
        # Draw overlay - ALWAYS draw dark overlay over entire screen
        self._draw_full_screen_overlay(painter)
        
        # Draw annotations and previews only if selection is complete
        if self.selection_complete:
            self._draw_annotations(painter)
            self._draw_drawing_preview(painter)
            self._draw_text_editing(painter)
    
    def _draw_full_screen_overlay(self, painter: QPainter):
        """Draw overlay over entire screen, with selection highlighted"""
        overlay_color = QColor(0, 0, 0, Config.OVERLAY_ALPHA)
        widget_rect = self.rect()
        
        if self.selection_rect.isValid():
            # Convert selection to widget coordinates
            selection_widget = self.coord_converter.desktop_to_widget(self.selection_rect)
            
            # Darken areas outside selection
            areas = [
                # Area above selection
                QRect(0, 0, widget_rect.width(), selection_widget.top()),
                
                # Area to the left of selection
                QRect(0, selection_widget.top(), selection_widget.left(), selection_widget.height()),
                
                # Area to the right of selection
                QRect(selection_widget.right() + 1, selection_widget.top(), 
                      widget_rect.width() - (selection_widget.right() + 1), selection_widget.height()),
                
                # Area below selection
                QRect(0, selection_widget.bottom() + 1, widget_rect.width(), 
                      widget_rect.height() - (selection_widget.bottom() + 1))
            ]
            
            for area in areas:
                if area.isValid():
                    painter.fillRect(area, overlay_color)
            
            # Draw selection border
            painter.setPen(QPen(self.current_style.color, Config.SELECTION_BORDER_WIDTH))
            painter.drawRect(selection_widget)
            
            # Draw info text
            self._draw_info_text(painter, selection_widget)
        else:
            # No selection yet - darken entire screen
            painter.fillRect(widget_rect, overlay_color)
            
            # Draw initial help text on primary screen only
            self._draw_help_text_on_primary_screen(painter)
    
    def _draw_help_text_on_primary_screen(self, painter: QPainter):
        """Draw help text centered on primary screen only"""
        from PyQt6.QtWidgets import QApplication
        
        # Get primary screen geometry
        primary_screen = QApplication.primaryScreen()
        primary_geometry = primary_screen.geometry()
        
        # Convert primary screen geometry to widget coordinates
        primary_widget_rect = self.coord_converter.desktop_to_widget(primary_geometry)
        
        # Setup text
        painter.setPen(QPen(QColor(255, 255, 255)))
        font = QFont("Arial", 16, QFont.Weight.Bold)
        painter.setFont(font)
        
        help_text = "Click and drag to select area • Click outside selection to start new area • ESC to exit"
        text_rect = painter.fontMetrics().boundingRect(help_text)
        
        # Center text on primary screen
        text_pos = QPoint(
            primary_widget_rect.x() + (primary_widget_rect.width() - text_rect.width()) // 2,
            primary_widget_rect.y() + (primary_widget_rect.height() - text_rect.height()) // 2
        )
        
        painter.drawText(text_pos, help_text)

    def _draw_info_text(self, painter: QPainter, selection_widget: QRect):
        """Draw informational text"""
        painter.setPen(QPen(QColor(255, 255, 255)))
        
        if not self.selection_complete:
            size_text = f"{self.selection_rect.width()} × {self.selection_rect.height()}"
            painter.drawText(selection_widget.bottomLeft() + QPoint(5, 20), size_text)
        else:
            help_text = self._get_help_text()
            text_pos = selection_widget.bottomLeft() + QPoint(5, 20)
            
            # Split long text into multiple lines
            if len(help_text) > 120:
                parts = help_text.split(' • ')
                painter.drawText(text_pos, parts[0])
                if len(parts) > 1:
                    painter.drawText(text_pos + QPoint(0, 15), ' • '.join(parts[1:]))
            else:
                painter.drawText(text_pos, help_text)
    
    def _get_help_text(self) -> str:
        """Get context-appropriate help text"""
        if self.is_text_editing:
            return f"✏️ TEXT EDITING: Type your text • Enter=Finish • Esc=Cancel • Thickness: {self.current_style.thickness}"
        
        mode_texts = {
            AnnotationMode.NONE: "🎯 SELECT MODE: Press 1=Arrow 2=Rectangle 3=Text",
            AnnotationMode.ARROW: f"➡️ ARROW MODE: Click & drag to draw arrows • Scroll=Thickness({self.current_style.thickness}) • Keys: 1,2,3=Switch",
            AnnotationMode.RECTANGLE: f"⬜ RECTANGLE MODE: Click & drag to draw boxes • Scroll=Thickness({self.current_style.thickness}) • Keys: 1,2,3=Switch",
            AnnotationMode.TEXT: f"📝 TEXT MODE: Click anywhere to start typing • Scroll=Thickness({self.current_style.thickness}) • Keys: 1,2,3=Switch"
        }
        
        base_text = mode_texts.get(self.annotation_mode, "")
        current_color_name = self.colors[self.current_color_index].name
        return base_text + f" • 4=Color({current_color_name}) • Ctrl+Z=Undo • Ctrl+R=Redo • Ctrl+C=Copy • Ctrl+S=Save"
    
    def _draw_annotations(self, painter: QPainter):
        """Draw all annotations"""
        for annotation in self.annotations:
            annotation.draw(painter)
    
    def _draw_drawing_preview(self, painter: QPainter):
        """Draw preview of current drawing"""
        if not self.is_drawing:
            return
        
        if self.annotation_mode == AnnotationMode.RECTANGLE and self.current_rect.isValid():
            temp_annotation = RectangleAnnotation(self.current_rect, self.current_style.copy())
            temp_annotation.draw(painter)
        
        elif self.annotation_mode == AnnotationMode.ARROW and not self.current_arrow_end.isNull():
            temp_annotation = ArrowAnnotation(self.draw_start_point, self.current_arrow_end, self.current_style.copy())
            temp_annotation.draw(painter)
    
    def _draw_text_editing(self, painter: QPainter):
        """Draw current text being edited"""
        if self.is_text_editing:
            # Set the font for the painter before calculating font metrics
            font = QFont("Arial", max(Config.MIN_FONT_SIZE, self.current_style.thickness * Config.TEXT_FONT_SCALE))
            font.setBold(True)
            painter.setFont(font)

            font_metrics = painter.fontMetrics()
            text_until_cursor = self.current_text[:self.text_cursor_position]
            cursor_x_offset = font_metrics.horizontalAdvance(text_until_cursor)

            display_text = self.current_text
            
            # Draw outline
            for dx in [-1, 0, 1]:
                for dy in [-1, 0, 1]:
                    if dx != 0 or dy != 0:
                        painter.setPen(QPen(self.current_style.outline_color, 1))
                        painter.drawText(self.text_position + QPoint(dx, dy), display_text)
            
            # Draw main text
            painter.setPen(QPen(self.current_style.color))
            painter.drawText(self.text_position, display_text)

            # Draw cursor
            cursor_x = self.text_position.x() + cursor_x_offset
            cursor_y = self.text_position.y() - font_metrics.ascent()
            cursor_height = font_metrics.height()
            
            painter.setPen(QPen(self.current_style.color, 1))
            painter.drawLine(cursor_x, cursor_y, cursor_x, cursor_y + cursor_height)
    
    def save_screenshot(self):
        """Save screenshot with dialog"""
        if not self.selection_rect.isValid():
            print("No valid selection!")
            return
        
        pixmap = self.get_selected_pixmap_with_annotations()
        if pixmap.isNull():
            print("ERROR: Could not extract selected area!")
            return
        
        self._show_save_dialog(pixmap)
    
    def _show_save_dialog(self, pixmap: QPixmap):
        """Show save dialog and save file"""
        self._prepare_exit()
        time.sleep(0.3)
        
        filename, _ = QFileDialog.getSaveFileName(
            None, "Save Screenshot", "screenshot.png",
            "PNG Files (*.png);;JPEG Files (*.jpg);;All Files (*)"
        )
        
        if filename:
            success = pixmap.save(filename)
            print(f"Screenshot {'saved' if success else 'save failed'}: {filename}")
            self._exit_application()
        else:
            print("Save cancelled")
            self._restore_overlay()

    def _restore_overlay(self):
        """Restore overlay after cancelled dialog"""
        if self._is_exiting:
            return
            
        self._is_exiting = False
        
        self.setWindowFlags(
            Qt.WindowType.WindowStaysOnTopHint | 
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.BypassWindowManagerHint
        )
        
        self.setGeometry(self.virtual_geometry)
        self.setWindowState(Qt.WindowState.WindowFullScreen)
        self.show()
        self.raise_()
        self.activateWindow()
        self.setFocus()
        self.grabKeyboard()

    def copy_to_clipboard(self):
        """Copy screenshot to clipboard"""
        if not self.selection_rect.isValid():
            print("No valid selection!")
            return
        
        pixmap = self.get_selected_pixmap_with_annotations()
        if pixmap.isNull():
            print("ERROR: Could not extract selected area!")
            return
        
        self._prepare_exit()
        time.sleep(0.4)
        
        success = ClipboardManager.copy_pixmap_to_clipboard(pixmap)
        
        if success:
            print("✅ Screenshot successfully copied to clipboard!")
        else:
            print("❌ Clipboard copy failed!")
            print("Install 'xclip' or 'xsel': sudo apt install xclip")
        
        self._exit_application()
        
    def closeEvent(self, event):
        """Clean up on close"""
        self._prepare_exit()
        super().closeEvent(event)