import numpy as np
import pyqtgraph as pg
import pyqtgraph.opengl as gl
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QStackedWidget
import matplotlib.cm as cm

class PyQtGraphCanvas(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.stack = QStackedWidget()
        self.layout.addWidget(self.stack)

        self.view_3d = gl.GLViewWidget()
        # drawEdges=True dibuja la malla con las líneas (como matplotlib wireframe)
        self.surface_3d = gl.GLSurfacePlotItem(
            x=np.array([0, 1]),
            y=np.array([0, 1]),
            z=np.zeros((2, 2)),
            computeNormals=False, 
            smooth=False, 
            drawEdges=True, 
            edgeColor=(0, 0, 0, 0.4)  # Malla en color oscuro
        )
        self.view_3d.addItem(self.surface_3d)
        
        self.view_3d.setBackgroundColor('w')
        
        self.view_2d = pg.PlotWidget()
        self.plot_curve = self.view_2d.plot(pen=pg.mkPen('b', width=2), symbol='o', symbolBrush='b', symbolSize=6)
        self.view_2d.showGrid(x=True, y=True, alpha=0.3)
        self.view_2d.setBackground('w')
        self.view_2d.getAxis('bottom').setPen(pg.mkPen('k'))
        self.view_2d.getAxis('left').setPen(pg.mkPen('k'))

        self.stack.addWidget(self.view_3d)
        self.stack.addWidget(self.view_2d)

    def draw_3d(self, x, y, z):
        self.stack.setCurrentIndex(0)
        
        # Matplotlib z is shape (ny, nx), PyQtGraph expects (nx, ny)
        z_transposed = z.T
        
        z_min, z_max = z_transposed.min(), z_transposed.max()
        z_span = z_max - z_min if z_max > z_min else 1e-6
        z_norm = (z_transposed - z_min) / z_span
        
        # Scale Z for visualization to match X and Y dimensions
        x_span = max(x.max() - x.min(), 1)
        y_span = max(y.max() - y.min(), 1)
        max_xy = max(x_span, y_span)
        z_visual = z_norm * (max_xy * 0.4) # Aspect ratio adjustment
        
        cmap = cm.get_cmap('jet')
        colors = cmap(z_norm)
        
        # Invertimos el eje Y para coincidir con ax.invert_yaxis() de matplotlib
        y_inverted = -y
        
        # Set face colors instead of vertex colors for solid appearance, or keep vertex colors if preferred
        self.surface_3d.setData(x=x, y=y_inverted, z=z_visual, colors=colors.reshape(-1, 4))
        
        # FIX PRINCIPAL: Usamos z_visual.mean() en lugar de z_transposed.mean()
        # Esto pone el centro de rotación exactamente encima del modelo renderizado
        cx, cy, cz = x.mean(), y_inverted.mean(), z_visual.mean()
        self.view_3d.opts['center'] = pg.Vector(cx, cy, cz)
        
        span = max(x_span, y_span, z_visual.max() - z_visual.min())
        if span == 0: span = 10
        self.view_3d.opts['distance'] = span * 1.8

    def draw_2d(self, x, z):
        self.stack.setCurrentIndex(1)
        self.plot_curve.setData(x, z)
        self.view_2d.autoRange()

    def setVisible(self, visible):
        super().setVisible(visible)
