import sys
import os
from PyQt6.QtWidgets import QApplication
from ui.main_window import DensoViewerApp

if __name__ == "__main__":
    app = QApplication(sys.argv)
    viewer = DensoViewerApp()
    viewer.showMaximized()
    sys.exit(app.exec())
