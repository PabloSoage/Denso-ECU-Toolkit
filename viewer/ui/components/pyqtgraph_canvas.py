"""
3D Surface Plot Widget with PyQtGraph and OpenGL.
Emulates the visual style of Matplotlib's 3D plots including
solid background panes, grids, and proper axis labeling.
"""

import matplotlib
import numpy as np
import pyqtgraph as pg
import pyqtgraph.opengl as gl
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QStackedWidget

# matplotlib.cm.get_cmap() was removed in 3.9; the registry works on 3.5+ too.
try:
    JET = matplotlib.colormaps["jet"]
except AttributeError:  # pragma: no cover - matplotlib < 3.5
    import matplotlib.cm

    JET = matplotlib.cm.get_cmap("jet")

class PyQtGraphCanvas(QWidget):
    """
    A widget containing a 3D surface plot and a 2D fallback plot,
    managed by a QStackedWidget.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()
        self._setup_3d_scene()
        self._setup_2d_scene()

    def _setup_ui(self):
        """Initializes the main layout and stacked widget."""
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.stack = QStackedWidget()
        self.layout.addWidget(self.stack)

    def _setup_3d_scene(self):
        """Initializes the 3D OpenGL view and its visual components."""
        self.view_3d = gl.GLViewWidget()
        self.view_3d.setBackgroundColor('w')
        
        # Main opaque surface
        self.surface_3d = gl.GLSurfacePlotItem(
            x=np.array([0, 1]), y=np.array([0, 1]), z=np.zeros((2, 2)),
            computeNormals=False, smooth=False, drawEdges=False, glOptions='opaque'
        )
        self.view_3d.addItem(self.surface_3d)
        
        # Black wireframe overlaid on the surface
        self.grid_lines = gl.GLLinePlotItem(pos=np.zeros((2, 3)), color=(0, 0, 0, 0.6), mode='lines', glOptions='opaque')
        self.view_3d.addItem(self.grid_lines)
        
        # Dark borders for the back panes
        self.pane_borders = gl.GLLinePlotItem(pos=np.zeros((2, 3)), color=(0, 0, 0, 0.8), mode='lines', glOptions='opaque')
        self.view_3d.addItem(self.pane_borders)

        # Solid light gray background panes
        self.solid_panes = gl.GLMeshItem(glOptions='opaque', shader=None, computeNormals=False, smooth=False)
        self.view_3d.addItem(self.solid_panes)

        # White grid lines on the background panes
        self.pane_grids = gl.GLLinePlotItem(pos=np.zeros((2, 3)), color=(1.0, 1.0, 1.0, 1.0), mode='lines', glOptions='opaque')
        self.view_3d.addItem(self.pane_grids)
        
        self.axis_labels = []
        self.stack.addWidget(self.view_3d)

    def _setup_2d_scene(self):
        """Initializes the standard 2D plot widget."""
        self.view_2d = pg.PlotWidget()
        self.plot_curve = self.view_2d.plot(pen=pg.mkPen('b', width=2), symbol='o', symbolBrush='b', symbolSize=6)
        self.view_2d.showGrid(x=True, y=True, alpha=0.3)
        self.view_2d.setBackground('w')
        self.view_2d.getAxis('bottom').setPen(pg.mkPen('k'))
        self.view_2d.getAxis('left').setPen(pg.mkPen('k'))
        self.stack.addWidget(self.view_2d)

    def draw_3d(self, x: np.ndarray, y: np.ndarray, z: np.ndarray, axis_x: np.ndarray = None, axis_y: np.ndarray = None):
        """
        Renders the 3D surface plot, applying data normalization, 
        X-axis data flipping, and dynamic bounding boxes.
        """
        self.stack.setCurrentIndex(0)
        
        # Z normalization for color mapping and visual scaling
        z_transposed = z.T
        z_min, z_max = z_transposed.min(), z_transposed.max()
        z_span = z_max - z_min if z_max > z_min else 1e-6
        z_norm = (z_transposed - z_min) / z_span

        max_xy = max(x.max() - x.min(), y.max() - y.min())
        z_visual = z_norm * (max_xy * 0.4)

        # Flip X-axis data for correct visual orientation without inverting the coordinate system
        z_plot = z_visual[::-1, :]
        z_norm_plot = z_norm[::-1, :]
        
        # Use actual Map axis values if provided, otherwise default to indices
        x_labels = axis_x[::-1] if axis_x is not None else x[::-1]
        y_labels = axis_y if axis_y is not None else y

        # Center the data around the origin (0,0,0)
        c_x = x.mean()
        c_y = y.mean()
        c_z = z_plot.mean()
        
        x_centered = x - c_x
        y_centered = y - c_y
        z_centered = z_plot - c_z

        colors = JET(z_norm_plot)
        colors[..., 3] = 1.0  # Force 100% opacity

        self.surface_3d.setData(x=x_centered, y=y_centered, z=z_centered, colors=colors.reshape(-1, 4))
        
        # Construct surface grid (black lines)
        visual_z_span = z_centered.max() - z_centered.min()
        z_offset = visual_z_span * 0.002 
        
        lines_pos = []
        for i in range(len(y_centered)):
            for j in range(len(x_centered)-1):
                lines_pos.append([x_centered[j], y_centered[i], z_centered[j, i] + z_offset])
                lines_pos.append([x_centered[j+1], y_centered[i], z_centered[j+1, i] + z_offset])
        for j in range(len(x_centered)):
            for i in range(len(y_centered)-1):
                lines_pos.append([x_centered[j], y_centered[i], z_centered[j, i] + z_offset])
                lines_pos.append([x_centered[j], y_centered[i+1], z_centered[j, i+1] + z_offset])
                
        if lines_pos:
            self.grid_lines.setData(pos=np.array(lines_pos, dtype=np.float32), color=(0.0, 0.0, 0.0, 0.7), width=1.0, mode='lines')

        # Define bounding box dimensions
        xmin, xmax = x_centered.min(), x_centered.max()
        ymin, ymax = y_centered.min(), y_centered.max()
        zvmin, zvmax = z_centered.min(), z_centered.max()

        # Padding expands the grid on the front, right, and top. 
        # Left and Back are flush with the figure boundaries.
        pad_x = (xmax - xmin) * 0.12
        pad_y = (ymax - ymin) * 0.12
        pad_z = (zvmax - zvmin) * 0.12

        px_min, px_max = xmin, xmax + pad_x
        py_min, py_max = ymin - pad_y, ymax
        pz_min, pz_max = zvmin, zvmax + pad_z

        # Outline segments for the background panes
        border_segments = [
            [px_min, py_min, pz_min], [px_max, py_min, pz_min],
            [px_max, py_min, pz_min], [px_max, py_max, pz_min],
            [px_max, py_max, pz_min], [px_min, py_max, pz_min],
            [px_min, py_max, pz_min], [px_min, py_min, pz_min],
            [px_min, py_max, pz_min], [px_min, py_max, pz_max],
            [px_max, py_max, pz_min], [px_max, py_max, pz_max],
            [px_min, py_max, pz_max], [px_max, py_max, pz_max],
            [px_min, py_min, pz_min], [px_min, py_min, pz_max],
            [px_min, py_min, pz_max], [px_min, py_max, pz_max]
        ]
        self.pane_borders.setData(pos=np.array(border_segments, dtype=np.float32), color=(0.0, 0.0, 0.0, 0.8), width=1.5, mode='lines')

        # Solid gray background panes (Floor, Back Wall, Left Wall)
        verts = np.array([
            [px_min, py_min, pz_min], [px_max, py_min, pz_min], [px_max, py_max, pz_min], [px_min, py_max, pz_min], 
            [px_min, py_max, pz_min], [px_max, py_max, pz_min], [px_max, py_max, pz_max], [px_min, py_max, pz_max], 
            [px_min, py_min, pz_min], [px_min, py_max, pz_min], [px_min, py_max, pz_max], [px_min, py_min, pz_max]  
        ])
        faces = np.array([
            [0, 1, 2], [0, 2, 3],
            [4, 5, 6], [4, 6, 7],
            [8, 9, 10], [8, 10, 11]
        ])
        colors_mesh = np.ones((6, 4), dtype=np.float32) * 0.94  
        colors_mesh[:, 3] = 1.0  
        self.solid_panes.setMeshData(vertexes=verts, faces=faces, faceColors=colors_mesh)

        # White grid drawn over the gray panes
        eps = max_xy * 0.001 
        ze = (pz_max - pz_min) * 0.001
        pane_lines = []
        
        num_z_ticks = 8
        z_ticks_vis = np.linspace(pz_min, pz_max, num_z_ticks)

        for xv in x_centered:
            pane_lines.extend([[xv, py_min+eps, pz_min+ze], [xv, py_max-eps, pz_min+ze]]) 
            pane_lines.extend([[xv, py_max-eps, pz_min+ze], [xv, py_max-eps, pz_max-ze]]) 
        for yv in y_centered:
            pane_lines.extend([[px_min+eps, yv, pz_min+ze], [px_max-eps, yv, pz_min+ze]]) 
            pane_lines.extend([[px_min+eps, yv, pz_min+ze], [px_min+eps, yv, pz_max-ze]]) 
        for zv in z_ticks_vis:
            pane_lines.extend([[px_min+eps, py_max-eps, zv], [px_max-eps, py_max-eps, zv]]) 
            pane_lines.extend([[px_min+eps, py_min+eps, zv], [px_min+eps, py_max-eps, zv]]) 

        self.pane_grids.setData(pos=np.array(pane_lines, dtype=np.float32), color=(0.7, 0.7, 0.7, 0.7), width=1.0, mode='lines')

        # Axis labeling
        for lbl in self.axis_labels:
            self.view_3d.removeItem(lbl)
        self.axis_labels.clear()

        def add_text_item(px: float, py: float, pz: float, text: str):
            lbl = gl.GLTextItem(pos=(px, py, pz), text=text, color=(0, 0, 0, 255))
            self.view_3d.addItem(lbl)
            self.axis_labels.append(lbl)

        off_x = (px_max - px_min) * 0.04
        off_y = (py_max - py_min) * 0.04
        
        # X-Axis: Drawn every 2 units, mapped to flipped x-labels
        for v_real, v_vis in zip(x_labels[::2], x_centered[::2]):
            # If the v_real is a float/int, we can format it. If already string, print directly.
            try: text_val = f"{float(v_real):.0f}"
            except (ValueError, TypeError): text_val = str(v_real)
            add_text_item(v_vis, py_min - off_y, pz_min, text_val)
        add_text_item(0, py_min - off_y * 2.5, pz_min, "X Axis")

        # Y-Axis: Drawn every 2 units
        for v_real, v_vis in zip(y_labels[::2], y_centered[::2]):
            try: text_val = f"{float(v_real):.0f}"
            except (ValueError, TypeError): text_val = str(v_real)
            add_text_item(px_max + off_x, v_vis, pz_min, text_val)
        add_text_item(px_max + off_x * 2.5, 0, pz_min, "Y Axis")

        # Z-Axis: Linear mapping
        z_ticks_real = np.linspace(z_min, z_max, num_z_ticks)
        for v_real, v_vis in zip(z_ticks_real, z_ticks_vis):
            add_text_item(px_max + off_x, py_max + off_y, v_vis, f"{v_real:.0f}")
        add_text_item(px_max + off_x, py_max + off_y, pz_max + off_x * 1.5, "Z Data")

        # Set initial camera orientation: Zoomed out, -90 degrees CCW relative to default
        self.view_3d.opts['center'] = pg.Vector(0, 0, 0)
        self.view_3d.setCameraPosition(distance=max_xy * 2.8, elevation=30, azimuth=-45)

    def draw_2d(self, x: np.ndarray, z: np.ndarray):
        """Renders the standard 2D plot."""
        self.stack.setCurrentIndex(1)
        self.plot_curve.setData(x, z)
        self.view_2d.autoRange()

    def setVisible(self, visible: bool):
        super().setVisible(visible)