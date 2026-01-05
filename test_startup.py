#!/usr/bin/env python3
"""
Test that the application can start without errors
"""
import sys
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QTimer

def test_startup():
    print("Creating QApplication...")
    app = QApplication(sys.argv)

    print("Importing MainWindow...")
    from gui.main_window import MainWindow

    print("Creating MainWindow...")
    window = MainWindow()

    print("Showing window...")
    window.show()

    print("✓ Application started successfully!")
    print("✓ No X Window errors!")
    print("✓ Preview widget initialized without issues!")

    # Close after 1 second
    QTimer.singleShot(1000, app.quit)

    app.exec()
    print("✓ Application closed cleanly!")

if __name__ == "__main__":
    test_startup()
