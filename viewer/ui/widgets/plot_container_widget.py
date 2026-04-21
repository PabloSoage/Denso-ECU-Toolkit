from PyQt6.QtWidgets import QWidget, QVBoxLayout
import matplotlib.pyplot as plt
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from widgets.custom_canvas import CustomCanvas
from widgets.pyqtgraph_canvas import PyQtGraphCanvas

class PlotContainerWidget(QWidget):
    def __init__(self, main_window):
        super().__init__()
        self.main_window = main_window
        self.init_ui()

    def init_ui(self):
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0,0,0,0)
        
        self.main_window.fig = plt.figure(figsize=(8, 6))
        self.main_window.fig.subplots_adjust(left=0.05, right=0.95, bottom=0.08, top=0.92)
        
        self.main_window.ax = self.main_window.fig.add_subplot(111, projection='3d')
        self.main_window.ax.set_navigate(False)
        
        self.main_window.canvas = CustomCanvas(self.main_window.fig, self.main_window)
        self.main_window.canvas.mpl_connect('button_press_event', self.main_window.on_mouse_press)
        self.main_window.canvas.mpl_connect('button_release_event', self.main_window.on_mouse_release)
        self.main_window.canvas.mpl_connect('motion_notify_event', self.main_window.on_mouse_move)

        self.main_window.pg_canvas = PyQtGraphCanvas(self.main_window)
        self.main_window.pg_canvas.setVisible(False)
        
        self.layout.addWidget(self.main_window.canvas)
        self.layout.addWidget(self.main_window.pg_canvas)
