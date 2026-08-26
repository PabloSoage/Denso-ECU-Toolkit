"""Application bootstrap."""

import sys

from PyQt6.QtWidgets import QApplication


def main(argv=None):
    """Start the viewer. Returns the Qt exit code."""
    from .ui.main_window import DensoViewerApp

    app = QApplication(argv if argv is not None else sys.argv)
    window = DensoViewerApp()
    window.showMaximized()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
