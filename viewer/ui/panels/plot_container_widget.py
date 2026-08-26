"""Holds the two render engines: matplotlib and PyQtGraph/OpenGL."""

import matplotlib.pyplot as plt
from PyQt6.QtWidgets import QVBoxLayout, QWidget

from ..components.custom_canvas import CustomCanvas
from ..components.pyqtgraph_canvas import PyQtGraphCanvas


class PlotContainerWidget(QWidget):
    def __init__(self, main_window):
        super().__init__()
        self.main_window = main_window
        self.init_ui()

    def init_ui(self):
        mw = self.main_window
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)

        mw.fig = plt.figure(figsize=(8, 6))
        mw.fig.subplots_adjust(left=0.05, right=0.95, bottom=0.08, top=0.92)

        mw.ax = mw.fig.add_subplot(111, projection="3d")
        mw.ax.set_navigate(False)

        mw.canvas = CustomCanvas(mw.fig, mw)
        mw.canvas.mpl_connect("button_press_event", mw.on_mouse_press)
        mw.canvas.mpl_connect("button_release_event", mw.on_mouse_release)
        mw.canvas.mpl_connect("motion_notify_event", mw.on_mouse_move)

        mw.pg_canvas = PyQtGraphCanvas(mw)
        mw.pg_canvas.setVisible(False)

        self.layout.addWidget(mw.canvas)
        self.layout.addWidget(mw.pg_canvas)
