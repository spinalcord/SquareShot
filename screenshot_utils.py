import os
import subprocess
import tempfile
import shutil
from pathlib import Path
from typing import Optional, Tuple
from PyQt6.QtWidgets import QApplication, QMessageBox
from PyQt6.QtGui import QPixmap, QPainter
from PyQt6.QtCore import QRect, Qt, QProcess
from coordinate_converter import CoordinateConverter


class ScreenshotBackend:
    """Base class for screenshot backends"""
    
    def __init__(self):
        self.name = "Base"
        self.available = False
    
    def is_available(self) -> bool:
        """Check if this backend is available"""
        return self.available
    
    def capture_all_screens(self, virtual_rect: QRect) -> Optional[QPixmap]:
        """Capture all screens and return as QPixmap"""
        raise NotImplementedError
    
    def get_virtual_geometry(self) -> QRect:
        """Get virtual desktop geometry"""
        screens = QApplication.screens()
        if not screens:
            return QRect()
        
        virtual_rect = QRect()
        for screen in screens:
            virtual_rect = virtual_rect.united(screen.geometry())
        return virtual_rect


class QtScreenshotBackend(ScreenshotBackend):
    """Traditional Qt screenshot backend (X11)"""
    
    def __init__(self):
        super().__init__()
        self.name = "Qt Native"
        # Check if we're running under X11
        self.available = self._check_x11_availability()
    
    def _check_x11_availability(self) -> bool:
        """Check if X11 is available and Qt screenshots work"""
        try:
            session_type = os.environ.get('XDG_SESSION_TYPE', '').lower()
            wayland_display = os.environ.get('WAYLAND_DISPLAY', '')
            
            # If we're definitely on Wayland, Qt screenshots won't work
            if session_type == 'wayland' or wayland_display:
                return False
            
            # Try a test screenshot
            screens = QApplication.screens()
            if screens:
                test_pixmap = screens[0].grabWindow(0, 0, 0, 1, 1)
                return not test_pixmap.isNull()
        except Exception:
            pass
        return False
    
    def capture_all_screens(self, virtual_rect: QRect) -> Optional[QPixmap]:
        """Capture using Qt's native method"""
        if virtual_rect.isEmpty():
            return None
        
        total_pixmap = QPixmap(virtual_rect.size())
        total_pixmap.fill(Qt.GlobalColor.black)
        
        painter = QPainter(total_pixmap)
        try:
            for screen in QApplication.screens():
                screen_pixmap = screen.grabWindow(0)
                if screen_pixmap.isNull():
                    continue
                
                screen_geometry = screen.geometry()
                offset = screen_geometry.topLeft() - virtual_rect.topLeft()
                painter.drawPixmap(offset, screen_pixmap)
        finally:
            painter.end()
        
        return total_pixmap if not total_pixmap.isNull() else None


class GrimScreenshotBackend(ScreenshotBackend):
    """Grim screenshot backend for Wayland (sway/wlroots)"""
    
    def __init__(self):
        super().__init__()
        self.name = "Grim (Wayland)"
        self.available = shutil.which('grim') is not None
    
    def capture_all_screens(self, virtual_rect: QRect) -> Optional[QPixmap]:
        """Capture using grim"""
        with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as temp_file:
            temp_path = temp_file.name
        
        try:
            # Use grim to capture the entire desktop
            result = subprocess.run(
                ['grim', temp_path],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode == 0 and os.path.exists(temp_path):
                pixmap = QPixmap(temp_path)
                return pixmap if not pixmap.isNull() else None
            else:
                print(f"Grim error: {result.stderr}")
                return None
        
        except (subprocess.TimeoutExpired, subprocess.SubprocessError, FileNotFoundError) as e:
            print(f"Grim capture failed: {e}")
            return None
        finally:
            # Clean up temp file
            try:
                os.unlink(temp_path)
            except OSError:
                pass


class GnomeScreenshotBackend(ScreenshotBackend):
    """GNOME Screenshot backend"""
    
    def __init__(self):
        super().__init__()
        self.name = "GNOME Screenshot"
        self.available = (
            shutil.which('gnome-screenshot') is not None and
            os.environ.get('XDG_CURRENT_DESKTOP', '').lower() in ['gnome', 'ubuntu:gnome']
        )
    
    def capture_all_screens(self, virtual_rect: QRect) -> Optional[QPixmap]:
        """Capture using gnome-screenshot"""
        with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as temp_file:
            temp_path = temp_file.name
        
        try:
            result = subprocess.run(
                ['gnome-screenshot', '-f', temp_path],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode == 0 and os.path.exists(temp_path):
                pixmap = QPixmap(temp_path)
                return pixmap if not pixmap.isNull() else None
            else:
                print(f"GNOME Screenshot error: {result.stderr}")
                return None
        
        except (subprocess.TimeoutExpired, subprocess.SubprocessError) as e:
            print(f"GNOME Screenshot failed: {e}")
            return None
        finally:
            try:
                os.unlink(temp_path)
            except OSError:
                pass


class SpectacleScreenshotBackend(ScreenshotBackend):
    """KDE Spectacle backend"""
    
    def __init__(self):
        super().__init__()
        self.name = "Spectacle (KDE)"
        self.available = (
            shutil.which('spectacle') is not None and
            os.environ.get('XDG_CURRENT_DESKTOP', '').lower() in ['kde', 'plasma']
        )
    
    def capture_all_screens(self, virtual_rect: QRect) -> Optional[QPixmap]:
        """Capture using spectacle"""
        with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as temp_file:
            temp_path = temp_file.name
        
        try:
            result = subprocess.run(
                ['spectacle', '-b', '-n', '-o', temp_path],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode == 0 and os.path.exists(temp_path):
                pixmap = QPixmap(temp_path)
                return pixmap if not pixmap.isNull() else None
            else:
                print(f"Spectacle error: {result.stderr}")
                return None
        
        except (subprocess.TimeoutExpired, subprocess.SubprocessError) as e:
            print(f"Spectacle failed: {e}")
            return None
        finally:
            try:
                os.unlink(temp_path)
            except OSError:
                pass


class ImageMagickScreenshotBackend(ScreenshotBackend):
    """ImageMagick import backend (fallback)"""
    
    def __init__(self):
        super().__init__()
        self.name = "ImageMagick"
        self.available = shutil.which('import') is not None
    
    def capture_all_screens(self, virtual_rect: QRect) -> Optional[QPixmap]:
        """Capture using ImageMagick import"""
        with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as temp_file:
            temp_path = temp_file.name
        
        try:
            result = subprocess.run(
                ['import', '-window', 'root', temp_path],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode == 0 and os.path.exists(temp_path):
                pixmap = QPixmap(temp_path)
                return pixmap if not pixmap.isNull() else None
            else:
                print(f"ImageMagick error: {result.stderr}")
                return None
        
        except (subprocess.TimeoutExpired, subprocess.SubprocessError) as e:
            print(f"ImageMagick failed: {e}")
            return None
        finally:
            try:
                os.unlink(temp_path)
            except OSError:
                pass


class MultiMonitorScreenshot:
    """Enhanced screenshot manager with Wayland support"""
    
    _backends = None
    _active_backend = None
    
    @classmethod
    def _initialize_backends(cls):
        """Initialize and test all available backends"""
        if cls._backends is not None:
            return
        
        cls._backends = [
            QtScreenshotBackend(),
            GrimScreenshotBackend(), 
            GnomeScreenshotBackend(),
            SpectacleScreenshotBackend(),
            ImageMagickScreenshotBackend(),
        ]
        
        # Find first available backend
        for backend in cls._backends:
            if backend.is_available():
                cls._active_backend = backend
                print(f"Using screenshot backend: {backend.name}")
                break
        
        if cls._active_backend is None:
            print("WARNING: No screenshot backend available!")
            print("Install one of: grim, gnome-screenshot, spectacle, or imagemagick")
    
    @staticmethod
    def get_virtual_geometry() -> QRect:
        """Calculate total virtual desktop geometry"""
        MultiMonitorScreenshot._initialize_backends()
        
        if MultiMonitorScreenshot._active_backend:
            return MultiMonitorScreenshot._active_backend.get_virtual_geometry()
        
        # Fallback
        screens = QApplication.screens()
        if not screens:
            return QRect()
        
        virtual_rect = QRect()
        for screen in screens:
            virtual_rect = virtual_rect.united(screen.geometry())
        return virtual_rect
    
    @staticmethod
    def capture_all_screens() -> QPixmap:
        """Capture all screens as one pixmap using best available method"""
        MultiMonitorScreenshot._initialize_backends()
        
        if not MultiMonitorScreenshot._active_backend:
            print("ERROR: No screenshot backend available!")
            return QPixmap()
        
        virtual_rect = MultiMonitorScreenshot.get_virtual_geometry()
        if virtual_rect.isEmpty():
            print("ERROR: No valid screen geometry!")
            return QPixmap()
        
        pixmap = MultiMonitorScreenshot._active_backend.capture_all_screens(virtual_rect)
        
        if pixmap is None or pixmap.isNull():
            print(f"ERROR: Screenshot capture failed with {MultiMonitorScreenshot._active_backend.name}")
            return QPixmap()
        
        return pixmap
    
    @staticmethod
    def extract_rect_from_pixmap(source: QPixmap, desktop_rect: QRect, virtual_geometry: QRect) -> QPixmap:
        """Extract area from existing pixmap based on desktop coordinates"""
        if source.isNull() or desktop_rect.isEmpty():
            return QPixmap()
        
        # Convert to pixmap coordinates
        pixmap_rect = QRect(
            desktop_rect.x() - virtual_geometry.x(),
            desktop_rect.y() - virtual_geometry.y(),
            desktop_rect.width(),
            desktop_rect.height()
        )
        
        # Clip to bounds
        pixmap_bounds = QRect(0, 0, source.width(), source.height())
        clipped_rect = pixmap_rect.intersected(pixmap_bounds)
        
        return source.copy(clipped_rect) if not clipped_rect.isEmpty() else QPixmap()
    
    @staticmethod
    def get_backend_info() -> str:
        """Get information about available backends"""
        MultiMonitorScreenshot._initialize_backends()
        
        info = []
        info.append("Screenshot Backend Information:")
        info.append("=" * 35)
        
        if MultiMonitorScreenshot._backends:
            for backend in MultiMonitorScreenshot._backends:
                status = "✓ AVAILABLE" if backend.is_available() else "✗ Not available"
                active = " (ACTIVE)" if backend == MultiMonitorScreenshot._active_backend else ""
                info.append(f"{backend.name:20} {status}{active}")
        else:
            info.append("No backends initialized")
        
        # Environment info
        info.append("\nEnvironment:")
        info.append(f"Session Type: {os.environ.get('XDG_SESSION_TYPE', 'unknown')}")
        info.append(f"Desktop: {os.environ.get('XDG_CURRENT_DESKTOP', 'unknown')}")
        info.append(f"Wayland Display: {os.environ.get('WAYLAND_DISPLAY', 'none')}")
        
        return "\n".join(info)
    
    @staticmethod
    def show_backend_dialog():
        """Show dialog with backend information"""
        info = MultiMonitorScreenshot.get_backend_info()
        
        msg = QMessageBox()
        msg.setWindowTitle("Screenshot Backend Info")
        msg.setText(info)
        msg.setIcon(QMessageBox.Icon.Information)
        
        if not MultiMonitorScreenshot._active_backend:
            msg.setIcon(QMessageBox.Icon.Warning)
            msg.setInformativeText("No screenshot backend is available! Please install grim, gnome-screenshot, spectacle, or imagemagick.")
        
        msg.exec()


# Utility function for debugging
def test_screenshot_backends():
    """Test all backends and show results"""
    print(MultiMonitorScreenshot.get_backend_info())
    
    # Try to take a test screenshot
    print("\nTesting screenshot capture...")
    pixmap = MultiMonitorScreenshot.capture_all_screens()
    
    if not pixmap.isNull():
        print(f"✓ Screenshot successful: {pixmap.width()}x{pixmap.height()}")
    else:
        print("✗ Screenshot failed")


if __name__ == "__main__":
    app = QApplication([])
    test_screenshot_backends()
    app.quit()