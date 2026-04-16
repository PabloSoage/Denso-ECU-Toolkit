import sys
import struct
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from mpl_toolkits.mplot3d import proj3d

from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
                             QListWidget, QLineEdit, QPushButton, QLabel, QStackedWidget,
                             QTableWidget, QTableWidgetItem, QGroupBox, QRadioButton,
                             QFormLayout, QDialog, QDialogButtonBox, QDoubleSpinBox)
from PyQt6.QtCore import Qt

# ================= CONFIGURATION =================
CSV_FILE = "3d_maps_review.csv"
ORI_FILE = "115_e3a4d17c28.bin"       
# =================================================

class DensoViewerApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Denso Map Viewer 3D")
        self.resize(1400, 850)
        
        # --- Variables de Estado ---
        self.df = pd.DataFrame()
        self.current_index = 0
        self.total_maps = 0
        
        self.factor_z = 0.0025
        self.offset_z = 0.0
        self.z_format = '>H'
        self.ax_format = 'f'
        self.rot_mode = 'Z' 
        self.view_mode = '3d'
        
        # Variables de Cámara y Zoom persistentes
        self.dragging = False
        self.mouse_x = 0
        self.mouse_y = 0
        self.start_elev = 35
        self.start_azim = 135
        self.cam_dist = 10.0  # Zoom para versiones antiguas de Matplotlib
        self.cam_zoom = 1.0   # Zoom para versiones modernas de Matplotlib
        
        self.real_axis_x = []
        self.real_axis_y = []
        self.x_flat = []
        self.y_flat = []
        self.z_flat = []
        
        self.load_data()
        self.init_ui()
        self.draw_map()

    def load_data(self):
        try:
            self.df = pd.read_csv(CSV_FILE, dtype=str)
            self.total_maps = len(self.df)
        except Exception as e:
            print(f"Error reading CSV: {e}")
            sys.exit()

    def init_ui(self):
        # Layout Principal
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)
        
        # --- PANEL IZQUIERDO ---
        left_panel = QVBoxLayout()
        left_panel.addWidget(QLabel("<b>Search Map Address:</b>"))
        
        self.search_box = QLineEdit()
        self.search_box.textChanged.connect(self.update_list)
        left_panel.addWidget(self.search_box)
        
        self.map_listbox = QListWidget()
        self.map_listbox.itemSelectionChanged.connect(self.on_list_select)
        left_panel.addWidget(self.map_listbox)
        
        main_layout.addLayout(left_panel, 1) 
        
        # --- PANEL DERECHO ---
        right_panel = QVBoxLayout()
        
        # Barra de Herramientas
        toolbar_layout = QHBoxLayout()
        
        self.lbl_title = QLabel("Map Info")
        self.lbl_title.setStyleSheet("font-size: 14px; font-weight: bold;")
        toolbar_layout.addWidget(self.lbl_title)
        
        toolbar_layout.addStretch()
        
        btn_prev = QPushButton("<- Prev Map")
        btn_prev.clicked.connect(self.prev_map)
        toolbar_layout.addWidget(btn_prev)
        
        btn_next = QPushButton("Next Map ->")
        btn_next.clicked.connect(self.next_map)
        toolbar_layout.addWidget(btn_next)
        
        btn_toggle = QPushButton("Toggle 3D / Table")
        btn_toggle.clicked.connect(self.toggle_view)
        toolbar_layout.addWidget(btn_toggle)
        
        btn_settings = QPushButton("⚙ Settings")
        btn_settings.clicked.connect(self.open_settings)
        toolbar_layout.addWidget(btn_settings)
        
        right_panel.addLayout(toolbar_layout)
        
        # Stacked Widget (Alternar entre Canvas 3D y Tabla)
        self.stacked_widget = QStackedWidget()
        
        # 1. Matplotlib Canvas
        self.fig = plt.figure(figsize=(8, 6))
        self.fig.subplots_adjust(left=0.01, right=0.99, bottom=0.05, top=0.95)
        self.ax3d = self.fig.add_subplot(111, projection='3d')
        self.ax3d.set_navigate(False)
        
        self.canvas = FigureCanvas(self.fig)
        self.canvas.setFocusPolicy(Qt.FocusPolicy.StrongFocus) # Asegura que capture eventos de rueda
        
        # Eventos nativos de Matplotlib (funcionan en cualquier SO)
        self.canvas.mpl_connect('button_press_event', self.on_mouse_press)
        self.canvas.mpl_connect('button_release_event', self.on_mouse_release)
        self.canvas.mpl_connect('motion_notify_event', self.on_mouse_move)
        self.canvas.mpl_connect('scroll_event', self.on_scroll)
        
        self.stacked_widget.addWidget(self.canvas)
        
        # 2. Qt Table
        self.table = QTableWidget()
        self.stacked_widget.addWidget(self.table)
        
        right_panel.addWidget(self.stacked_widget, 1)
        
        # Barra de estado
        self.status_lbl = QLabel("Hover over the graph to see values...")
        self.status_lbl.setStyleSheet("background-color: #222; color: #FFF; font-weight: bold; font-size: 14px; padding: 8px; border-radius: 4px;")
        right_panel.addWidget(self.status_lbl)
        
        main_layout.addLayout(right_panel, 4) 
        
        self.filtered_indices = []
        self.update_list()

    # --- UI LOGIC ---
    def update_list(self):
        search_term = self.search_box.text().lower()
        self.map_listbox.clear()
        self.filtered_indices = []
        
        for idx, row in self.df.iterrows():
            addr = str(row['Map_Z_Addr']).strip()
            if search_term in addr.lower():
                self.map_listbox.addItem(f"Map {idx+1}: {addr}")
                self.filtered_indices.append(idx)

    def on_list_select(self):
        items = self.map_listbox.selectedIndexes()
        if items:
            visual_idx = items[0].row()
            self.current_index = self.filtered_indices[visual_idx]
            self.draw_map()

    def prev_map(self):
        if self.current_index > 0:
            self.current_index -= 1
            self.sync_listbox_selection()
            self.draw_map()

    def next_map(self):
        if self.current_index < self.total_maps - 1:
            self.current_index += 1
            self.sync_listbox_selection()
            self.draw_map()
            
    def sync_listbox_selection(self):
        if self.current_index in self.filtered_indices:
            vis_idx = self.filtered_indices.index(self.current_index)
            self.map_listbox.setCurrentRow(vis_idx)

    def toggle_view(self):
        if self.view_mode == '3d':
            self.view_mode = 'table'
            self.stacked_widget.setCurrentIndex(1)
        else:
            self.view_mode = '3d'
            self.stacked_widget.setCurrentIndex(0)
        self.draw_map()

    def open_settings(self):
        dialog = QDialog(self)
        dialog.setWindowTitle("Configuration")
        dialog.resize(350, 400)
        layout = QVBoxLayout(dialog)
        
        # Z Format
        gb_z = QGroupBox("Z Data Format")
        vbox_z = QVBoxLayout()
        rb_z1 = QRadioButton("16-bit Big Endian (>H)")
        rb_z2 = QRadioButton("16-bit Little Endian (<H)")
        rb_z3 = QRadioButton("8-bit Unsigned (>B)")
        if self.z_format == '>H': rb_z1.setChecked(True)
        elif self.z_format == '<H': rb_z2.setChecked(True)
        else: rb_z3.setChecked(True)
        vbox_z.addWidget(rb_z1); vbox_z.addWidget(rb_z2); vbox_z.addWidget(rb_z3)
        gb_z.setLayout(vbox_z)
        layout.addWidget(gb_z)
        
        # Axis Format
        gb_a = QGroupBox("Axis X/Y Format")
        vbox_a = QVBoxLayout()
        rb_a1 = QRadioButton("32-bit Float (f)")
        rb_a2 = QRadioButton("16-bit Int (H)")
        if self.ax_format == 'f': rb_a1.setChecked(True)
        else: rb_a2.setChecked(True)
        vbox_a.addWidget(rb_a1); vbox_a.addWidget(rb_a2)
        gb_a.setLayout(vbox_a)
        layout.addWidget(gb_a)
        
        # Rotation
        gb_r = QGroupBox("Mouse Rotation Mode")
        vbox_r = QVBoxLayout()
        rb_r1 = QRadioButton("Z-Axis Only (WinOLS Azimuth)")
        rb_r2 = QRadioButton("WinOLS Style (Azimuth & Tilt)")
        rb_r3 = QRadioButton("Tilt Only (Elevation)")
        if self.rot_mode == 'Z': rb_r1.setChecked(True)
        elif self.rot_mode == 'WinOLS': rb_r2.setChecked(True)
        else: rb_r3.setChecked(True)
        vbox_r.addWidget(rb_r1); vbox_r.addWidget(rb_r2); vbox_r.addWidget(rb_r3)
        gb_r.setLayout(vbox_r)
        layout.addWidget(gb_r)
        
        # Math
        gb_m = QGroupBox("Math")
        form_m = QFormLayout()
        spin_f = QDoubleSpinBox()
        spin_f.setDecimals(5)
        spin_f.setSingleStep(0.001)
        spin_f.setRange(-1000, 1000)
        spin_f.setValue(self.factor_z)
        
        spin_o = QDoubleSpinBox()
        spin_o.setRange(-10000, 10000)
        spin_o.setValue(self.offset_z)
        
        form_m.addRow("Factor Z:", spin_f)
        form_m.addRow("Offset Z:", spin_o)
        gb_m.setLayout(form_m)
        layout.addWidget(gb_m)
        
        # Botones
        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        btns.accepted.connect(dialog.accept)
        btns.rejected.connect(dialog.reject)
        layout.addWidget(btns)
        
        if dialog.exec():
            if rb_z1.isChecked(): self.z_format = '>H'
            elif rb_z2.isChecked(): self.z_format = '<H'
            else: self.z_format = '>B'
            
            if rb_a1.isChecked(): self.ax_format = 'f'
            else: self.ax_format = 'H'
            
            if rb_r1.isChecked(): self.rot_mode = 'Z'
            elif rb_r2.isChecked(): self.rot_mode = 'WinOLS'
            else: self.rot_mode = 'Tilt'
            
            self.factor_z = spin_f.value()
            self.offset_z = spin_o.value()
            
            self.draw_map()

    # --- MATPLOTLIB EVENTS (ZOOM & HOVER) ---
    def on_scroll(self, event):
        """Zoom robusto sin bloqueos de ejes."""
        if self.view_mode != '3d': return
        
        zoom_in = event.step > 0
        
        # Ajustamos la distancia física
        factor = 0.85 if zoom_in else 1.15
        self.cam_dist = max(1.0, min(self.cam_dist * factor, 50.0))
        self.ax3d.dist = self.cam_dist
        
        # Ajustamos el nivel de zoom matemático
        z_factor = 1.15 if zoom_in else 0.85
        self.cam_zoom = max(0.1, min(self.cam_zoom * z_factor, 10.0))
        
        try:
            self.ax3d.set_zoom(self.cam_zoom)
        except AttributeError:
            pass
            
        self.canvas.draw_idle()

    def on_mouse_press(self, event):
        if event.button != 1: return
        self.dragging = True
        self.mouse_x = event.x
        self.mouse_y = event.y
        self.start_elev = self.ax3d.elev
        self.start_azim = self.ax3d.azim

    def on_mouse_release(self, event):
        self.dragging = False

    def on_mouse_move(self, event):
        if self.dragging:
            if event.x is None or event.y is None: return
            
            dx = event.x - self.mouse_x
            dy = event.y - self.mouse_y
            sens = 0.4
            
            if self.rot_mode == 'WinOLS':
                new_elev = max(-90, min(90, self.start_elev - (dy * sens)))
                new_azim = self.start_azim - (dx * sens)
                self.ax3d.view_init(elev=new_elev, azim=new_azim)
            elif self.rot_mode == 'Z':
                new_azim = self.start_azim - (dx * sens)
                self.ax3d.view_init(elev=self.start_elev, azim=new_azim)
            elif self.rot_mode == 'Tilt':
                new_elev = max(-90, min(90, self.start_elev - (dy * sens)))
                self.ax3d.view_init(elev=new_elev, azim=self.start_azim)
                
            self.canvas.draw_idle()
            return
            
        # Hover Tracking
        if getattr(event, 'inaxes', None) != self.ax3d or self.dragging or len(self.z_flat) == 0:
            if hasattr(self, 'cursor_marker') and self.cursor_marker.get_visible():
                self.cursor_marker.set_visible(False)
                self.status_lbl.setText("Hover over the graph to see values...")
                self.canvas.draw_idle()
            return

        try:
            xs, ys, _ = proj3d.proj_transform(self.x_flat, self.y_flat, self.z_flat, self.ax3d.get_proj())
            points2d = self.ax3d.transData.transform(np.column_stack([xs, ys]))
            
            dists = (points2d[:, 0] - event.x)**2 + (points2d[:, 1] - event.y)**2
            min_idx = np.argmin(dists)
            
            if dists[min_idx] < 600: 
                best_x = self.x_flat[min_idx]
                best_y = self.y_flat[min_idx]
                best_z = self.z_flat[min_idx]
                
                self.cursor_marker.set_data([best_x], [best_y])
                self.cursor_marker.set_3d_properties([best_z])
                self.cursor_marker.set_visible(True)
                
                rx = self.real_axis_x[best_x]
                ry = self.real_axis_y[best_y]
                
                lbl = f"Target Point: X = {rx:g}   |   Y = {ry:g}   |   Z = {best_z:.2f}"
                self.status_lbl.setText(lbl)
                self.canvas.draw_idle()
            else:
                self.cursor_marker.set_visible(False)
                self.status_lbl.setText("Hover over the graph to see values...")
                self.canvas.draw_idle()
        except: pass

    # --- DATA READING ---
    def read_axis(self, hex_addr, size, endian, axis_format):
        try:
            addr = int(str(hex_addr).strip(), 16)
            if addr == 0 or addr >= 0xFFFF0000:
                return np.arange(size)
                
            bytes_per_value = 4 if axis_format == 'f' else 2
            with open(ORI_FILE, "rb") as f:
                f.seek(addr)
                raw = f.read(size * bytes_per_value)
                
            return np.array(struct.unpack(f"{endian}{size}{axis_format}", raw))
        except:
            return np.arange(size)

    def read_map(self):
        row = self.df.iloc[self.current_index]
        size_x = int(row['Size_X'])
        size_y = int(row['Size_Y'])
        map_z_hex = str(row['Map_Z_Addr']).strip()
        axis_x_hex = str(row['Axis_X_Addr']).strip()
        axis_y_hex = str(row['Axis_Y_Addr']).strip()
        
        endian = self.z_format[0]
        bytes_per_value = 2 if 'h' in self.z_format.lower() else 1
        
        with open(ORI_FILE, "rb") as f:
            f.seek(int(map_z_hex, 16))
            raw_z_data = f.read(size_y * size_x * bytes_per_value)
            
        z_values = struct.unpack(f"{endian}{size_y * size_x}{self.z_format[-1]}", raw_z_data)
        matrix_z = np.array(z_values).reshape((size_y, size_x))
        
        axis_x = self.read_axis(axis_x_hex, size_x, endian, self.ax_format)
        axis_y = self.read_axis(axis_y_hex, size_y, endian, self.ax_format)
        
        return matrix_z, axis_x, axis_y, size_y, size_x, map_z_hex

    # --- RENDERING ---
    def draw_map(self):
        try:
            raw_matrix, axis_x, axis_y, size_y, size_x, map_z_hex = self.read_map()
            matrix_z = (raw_matrix * self.factor_z) + self.offset_z
            
            clean_axis_x = [str(round(v, 2)).rstrip('0').rstrip('.') for v in axis_x]
            clean_axis_y = [str(round(v, 2)).rstrip('0').rstrip('.') for v in axis_y]
            
            self.real_axis_x = axis_x
            self.real_axis_y = axis_y
            
            title = f"Map {self.current_index + 1}/{self.total_maps} | Addr: {map_z_hex} | Factor: {self.factor_z}"
            self.lbl_title.setText(title)

            if self.view_mode == '3d':
                self.ax3d.clear()
                
                x_grid = np.arange(size_x)
                y_grid = np.arange(size_y)
                X, Y = np.meshgrid(x_grid, y_grid)
                
                self.x_flat = X.flatten()
                self.y_flat = Y.flatten()
                self.z_flat = matrix_z.flatten()
                
                surf = self.ax3d.plot_surface(X, Y, matrix_z, cmap='jet', edgecolor='k', linewidth=0.3, alpha=0.9)
                
                self.cursor_marker, = self.ax3d.plot([0], [0], [0], marker='o', color='red', markersize=8, zorder=10)
                self.cursor_marker.set_visible(False)
                
                self.ax3d.set_xticks(x_grid)
                self.ax3d.set_xticklabels(clean_axis_x, rotation=45, ha='right', fontsize=8)
                self.ax3d.set_yticks(y_grid)
                self.ax3d.set_yticklabels(clean_axis_y, fontsize=8)
                
                self.ax3d.set_xlabel('\nX Axis')
                self.ax3d.set_ylabel('\nY Axis')
                self.ax3d.set_zlabel('Z Data')
                
                self.ax3d.invert_yaxis() 
                try:
                    self.ax3d.set_box_aspect((2.5, 2.0, 0.6))
                except AttributeError:
                    pass
                
                self.ax3d.view_init(elev=self.start_elev, azim=self.start_azim)
                
                # Aplicamos el Zoom almacenado
                self.ax3d.dist = self.cam_dist
                try:
                    self.ax3d.set_zoom(self.cam_zoom)
                except AttributeError:
                    pass

                self.canvas.draw_idle()
                
            elif self.view_mode == 'table':
                self.table.clear()
                self.table.setRowCount(size_y)
                self.table.setColumnCount(size_x)
                
                self.table.setHorizontalHeaderLabels(clean_axis_x)
                self.table.setVerticalHeaderLabels(clean_axis_y)
                
                for i in range(size_y):
                    for j in range(size_x):
                        val = round(matrix_z[i, j], 2)
                        item = QTableWidgetItem(str(val))
                        item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                        self.table.setItem(i, j, item)
                        
                self.table.resizeColumnsToContents()
                
        except Exception as e:
            if self.view_mode == '3d':
                self.ax3d.clear()
                self.ax3d.text2D(0.5, 0.5, f"Error:\n{str(e)}", transform=self.ax3d.transAxes, ha='center', color='red')
                self.canvas.draw_idle()
            else:
                self.table.clear()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    viewer = DensoViewerApp()
    viewer.show()
    sys.exit(app.exec())