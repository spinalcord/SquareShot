import sys
import tempfile
import os
import subprocess
import platform
from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QPixmap
from PyQt6.QtCore import QMimeData

class ClipboardManager:
    """Handles clipboard operations with Linux optimization"""
    
    @staticmethod
    def copy_pixmap_to_clipboard(pixmap: QPixmap) -> bool:
        """Copy pixmap to clipboard with platform-specific optimizations"""
        if pixmap.isNull():
            return False
        
        success = False
        
        if platform.system() == "Linux":
            success = ClipboardManager._linux_clipboard_copy(pixmap)
        
        # Fallback to Qt clipboard
        if not success:
            try:
                clipboard = QApplication.clipboard()
                clipboard.clear()
                clipboard.setPixmap(pixmap)
                success = True
            except Exception as e:
                print(f"Qt clipboard failed: {e}")
        
        return success
    
    @staticmethod
    def _linux_clipboard_copy(pixmap: QPixmap) -> bool:
        """Linux-specific clipboard copy using external tools"""
        try:
            with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp_file:
                tmp_path = tmp_file.name
            
            if not pixmap.save(tmp_path, 'PNG'):
                return False
            
            # Try different clipboard tools
            tools = [
                ['xclip', '-selection', 'clipboard', '-t', 'image/png', '-i', tmp_path],
                ['wl-copy', '--type', 'image/png'],
            ]
            
            for tool in tools:
                try:
                    if tool[0] == 'wl-copy':
                        with open(tmp_path, 'rb') as f:
                            subprocess.run(tool, input=f.read(), check=True)
                    else:
                        subprocess.run(tool, check=True)
                    
                    print(f"✅ {tool[0]} clipboard success")
                    return True
                except (FileNotFoundError, subprocess.CalledProcessError):
                    continue
            
            return False
            
        except Exception as e:
            print(f"Linux clipboard error: {e}")
            return False
        finally:
            try:
                os.unlink(tmp_path)
            except:
                pass