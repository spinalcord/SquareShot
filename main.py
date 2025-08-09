#!/usr/bin/env python3
"""
PyScreenshot - Optimized Version with Annotations
Workflow: Start script → Select area → Annotate → Ctrl+C for clipboard or Ctrl+S to save
"""

import sys
from PyQt6.QtWidgets import QApplication
from screenshot_overlay import ScreenshotOverlay


def main():
    """Main function"""
    app = QApplication(sys.argv)
    app.setApplicationName("PyScreenshot")
    
    overlay = ScreenshotOverlay()
    overlay.show()
    overlay.raise_()
    overlay.activateWindow()
    overlay.setFocus()
    
    exit_code = app.exec()
    
    # Zusätzliche Cleanup-Zeit für Window-Manager
    QApplication.processEvents()
    
    sys.exit(exit_code)
if __name__ == "__main__":
    main()
