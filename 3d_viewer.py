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
from PyQt6.QtCore import Qt, QEvent

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
        self.current_map_addr = ""
        
        self.factor_z = 0.0025
        self.offset_z = 0.0
        self.z_format = '>H'
        self.ax_format = 'f'
        self.rot_mode = 'Z' 
        self.view_mode = '3d'
        
        # --- Variables de Cámara y Zoom ---
        self.dragging = False
        self.mouse_x = 0
        self.mouse_y = 0
        self.start_elev = 35
        self.start_azim = 135
        self.cam_zoom = 1.0
        
        # Variables para Zoom hacia el ratón
        self.is_hovering = False
        self.hover_x = 0
        self.hover_y = 0
        
        self.real_axis_x = []
        self.real_axis_y = []
        self.x_flat = []
        self.y_flat = []
        self.z_flat = []
        
        self.load_data()
        self.init_ui()
        self.draw_map()
        
        QApplication.instance().installEventFilter(self)

    # ================== FILTRO GLOBAL DE EVENTOS (ZOOM CORREGIDO) ==================
    def eventFilter(self, obj, event):
        if event.type() == QEvent.Type.Wheel:
            if hasattr(self, 'view_mode') and self.view_mode == '3d':
                if hasattr(self, 'canvas') and self.canvas.underMouse():
                    delta = event.angleDelta().y()
                    if delta != 0:
                        zoom_in = delta > 0
                        factor = 1.15 if zoom_in else 0.85
                        old_zoom = self.cam_zoom
                        
                        # Limitamos el zoom mínimo a 1.0 (tamaño original) para evitar bugs de recorte
                        self.cam_zoom = max(1.0, min(self.cam_zoom * factor, 15.0))
                        
                        if self.cam_zoom == 1.0:
                            # Reset absoluto al centro si alejamos al máximo
                            self.center_x = self.abs_center_x
                            self.center_y = self.abs_center_y
                        elif old_zoom != self.cam_zoom:
                            d_zoom = self.cam_zoom / old_zoom
                            
                            # Si acercamos y estamos sobre el gráfico, el centro va hacia el ratón
                            if zoom_in and self.is_hovering:
                                self.center_x = self.hover_x - (self.hover_x - self.center_x) / d_zoom
                                self.center_y = self.hover_y - (self.hover_y - self.center_y) / d_zoom
                            # Si alejamos, el centro se dirige magnéticamente al centro original
                            else:
                                self.center_x = self.abs_center_x - (self.abs_center_x - self.center_x) / d_zoom
                                self.center_y = self.abs_center_y - (self.abs_center_y - self.center_y) / d_zoom
                        
                        self.apply_zoom()
                        self.status_lbl.setText(f"Zoom level: {self.cam_zoom:.2f}x")
                    return True 
        return super().eventFilter(obj, event)
    # ===============================================================================

    def load_data(self):
        try:
            self.df = pd.read_csv(CSV_FILE, dtype=str)
            self.total_maps = len(self.df)
        except Exception as e:
            print(f"Error reading CSV: {e}")
            sys.exit()

    def init_ui(self):
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
        
        self.stacked_widget = QStackedWidget()
        
        # Matplotlib Canvas
        self.fig = plt.figure(figsize=(8, 6))
        self.fig.subplots_adjust(left=0.01, right=0.99, bottom=0.05, top=0.95)
        self.ax3d = self.fig.add_subplot(111, projection='3d')
        self.ax3d.set_navigate(False)
        
        self.canvas = FigureCanvas(self.fig)
        
        self.canvas.mpl_connect('button_press_event', self.on_mouse_press)
        self.canvas.mpl_connect('button_release_event', self.on_mouse_release)
        self.canvas.mpl_connect('motion_notify_event', self.on_mouse_move)
        
        self.stacked_widget.addWidget(self.canvas)
        
        self.table = QTableWidget()
        self.stacked_widget.addWidget(self.table)
        
        right_panel.addWidget(self.stacked_widget, 1)
        
        self.status_lbl = QLabel("Hover over the graph to see values...")
        self.status_lbl.setStyleSheet("background-color: #222; color: #FFF; font-weight: bold; font-size: 14px; padding: 8px; border-radius: 4px;")
        right_panel.addWidget(self.status_lbl)
        
        main_layout.addLayout(right_panel, 4) 
        self.update_list()

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
        
        gb_a = QGroupBox("Axis X/Y Format")
        vbox_a = QVBoxLayout()
        rb_a1 = QRadioButton("32-bit Float (f)")
        rb_a2 = QRadioButton("16-bit Int (H)")
        if self.ax_format == 'f': rb_a1.setChecked(True)
        else: rb_a2.setChecked(True)
        vbox_a.addWidget(rb_a1); vbox_a.addWidget(rb_a2)
        gb_a.setLayout(vbox_a)
        layout.addWidget(gb_a)
        
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

    # --- LÓGICA MATEMÁTICA DE ZOOM INFALIBLE ---
    def apply_zoom(self):
        if not hasattr(self, 'map_size_x'): return
        
        x_range = max(1, self.map_size_x - 1) / self.cam_zoom
        y_range = max(1, self.map_size_y - 1) / self.cam_zoom
        
        # Bloqueador (Clamp) para que el mapa NUNCA se salga de los límites al hacer zoom
        min_c_x = x_range / 2
        max_c_x = (self.map_size_x - 1) - x_range / 2
        self.center_x = max(min_c_x, min(self.center_x, max_c_x))
        
        min_c_y = y_range / 2
        max_c_y = (self.map_size_y - 1) - y_range / 2
        self.center_y = max(min_c_y, min(self.center_y, max_c_y))
        
        self.ax3d.set_xlim(self.center_x - x_range/2, self.center_x + x_range/2)
        self.ax3d.set_ylim(self.center_y + y_range/2, self.center_y - y_range/2)
        
        # EL Z-AXIS SE QUEDA BLOQUEADO PARA QUE LOS NÚMEROS NO CAMBIEN NI SE DEFORMEN
        if self.z_min == self.z_max:
            self.ax3d.set_zlim(self.z_min - 1, self.z_max + 1)
        else:
            self.ax3d.set_zlim(self.z_min, self.z_max)
        
        self.canvas.draw_idle()

    # --- MATPLOTLIB EVENTS (HOVER & ROTATION) ---
    def on_mouse_press(self, event):
        if event.button == 1: 
            self.dragging = True
            self.mouse_x = event.x
            self.mouse_y = event.y
            self.start_elev = self.ax3d.elev
            self.start_azim = self.ax3d.azim

    def on_mouse_release(self, event):
        self.dragging = False
        self.start_elev = self.ax3d.elev
        self.start_azim = self.ax3d.azim

    def on_mouse_move(self, event):
        if self.dragging:
            if event.x is None or event.y is None: return
            dx = event.x - self.mouse_x
            dy = event.y - self.mouse_y
            sens = 0.4
            
            new_elev = self.start_elev
            new_azim = self.start_azim
            
            if self.rot_mode == 'WinOLS':
                new_elev = max(-90, min(90, self.start_elev - (dy * sens)))
                new_azim = self.start_azim - (dx * sens)
            elif self.rot_mode == 'Z':
                new_azim = self.start_azim - (dx * sens)
            elif self.rot_mode == 'Tilt':
                new_elev = max(-90, min(90, self.start_elev - (dy * sens)))
                
            self.ax3d.view_init(elev=new_elev, azim=new_azim)
            self.canvas.draw_idle()
            return
            
        # Hover Tracking
        if getattr(event, 'inaxes', None) != self.ax3d or self.dragging or len(self.z_flat) == 0:
            self.is_hovering = False
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
                self.is_hovering = True
                self.hover_x = self.x_flat[min_idx]
                self.hover_y = self.y_flat[min_idx]
                
                best_z = self.z_flat[min_idx]
                
                self.cursor_marker.set_data([self.hover_x], [self.hover_y])
                self.cursor_marker.set_3d_properties([best_z])
                self.cursor_marker.set_visible(True)
                
                rx = self.real_axis_x[self.hover_x]
                ry = self.real_axis_y[self.hover_y]
                
                lbl = f"Target Point: X = {rx:g}   |   Y = {ry:g}   |   Z = {best_z:.2f}"
                self.status_lbl.setText(lbl)
                self.canvas.draw_idle()
            else:
                self.is_hovering = False
                self.cursor_marker.set_visible(False)
                self.status_lbl.setText("Hover over the graph to see values...")
                self.canvas.draw_idle()
        except: pass

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

    def draw_map(self):
        try:
            raw_matrix, axis_x, axis_y, size_y, size_x, map_z_hex = self.read_map()
            matrix_z = (raw_matrix * self.factor_z) + self.offset_z
            
            clean_axis_x = [str(round(v, 2)).rstrip('0').rstrip('.') for v in axis_x]
            clean_axis_y = [str(round(v, 2)).rstrip('0').rstrip('.') for v in axis_y]
            
            self.real_axis_x = axis_x
            self.real_axis_y = axis_y
            
            # Recalculamos los centros de zoom solo si cambiamos de mapa
            self.map_size_x = size_x
            self.map_size_y = size_y
            self.z_min = matrix_z.min()
            self.z_max = matrix_z.max()
            
            if self.current_map_addr != map_z_hex:
                self.abs_center_x = (size_x - 1) / 2.0
                self.abs_center_y = (size_y - 1) / 2.0
                self.center_x = self.abs_center_x
                self.center_y = self.abs_center_y
                self.cam_zoom = 1.0 # Resetea el zoom al cambiar de mapa
                self.current_map_addr = map_z_hex
            
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
                
                # Ajuste de labelpad para separar el nombre del eje de los números
                self.ax3d.set_xlabel('\nX Axis', labelpad=12)
                self.ax3d.set_ylabel('\nY Axis', labelpad=12)
                self.ax3d.set_zlabel('Z Data', labelpad=12)
                
                try:
                    self.ax3d.set_box_aspect((2.5, 2.0, 0.6))
                except AttributeError:
                    pass
                
                self.ax3d.view_init(elev=self.start_elev, azim=self.start_azim)
                self.apply_zoom()
                
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