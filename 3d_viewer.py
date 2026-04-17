import sys
import os
import struct
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from mpl_toolkits.mplot3d import proj3d

from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
                             QListWidget, QLineEdit, QPushButton, QLabel, QStackedWidget,
                             QTableWidget, QTableWidgetItem, QGroupBox, QRadioButton,
                             QFormLayout, QDialog, QDialogButtonBox, QDoubleSpinBox,
                             QTabWidget, QFileDialog, QMessageBox)
from PyQt6.QtCore import Qt, QEvent

# ================= DEFAULT CONFIGURATION =================
DEFAULT_CSV_3D = "3d_maps_review.csv"
DEFAULT_CSV_2D = "2d_maps_review.csv"
DEFAULT_BIN = "115_e3a4d17c28.bin"       
# =========================================================

class CustomCanvas(FigureCanvas):
    """Subclass to capture native PyQt6 mouse events for robust zooming"""
    def __init__(self, fig, parent):
        super().__init__(fig)
        self.parent_app = parent

    def wheelEvent(self, event):
        # Native PyQt6 scroll event
        if self.parent_app.view_mode != 'plot': return
        if not self.underMouse(): return
        
        delta = event.angleDelta().y()
        if delta == 0: return
        zoom_in = delta > 0

        # --- 3D Zoom Logic ---
        if self.parent_app.map_mode == '3d':
            factor = 1.15 if zoom_in else 0.85
            old_zoom = self.parent_app.cam_zoom
            self.parent_app.cam_zoom = max(1.0, min(self.parent_app.cam_zoom * factor, 15.0))
            
            if self.parent_app.cam_zoom == 1.0:
                self.parent_app.center_x = self.parent_app.abs_center_x
                self.parent_app.center_y = self.parent_app.abs_center_y
            elif old_zoom != self.parent_app.cam_zoom:
                d_zoom = self.parent_app.cam_zoom / old_zoom
                if zoom_in and self.parent_app.is_hovering:
                    self.parent_app.center_x = self.parent_app.hover_x - (self.parent_app.hover_x - self.parent_app.center_x) / d_zoom
                    self.parent_app.center_y = self.parent_app.hover_y - (self.parent_app.hover_y - self.parent_app.center_y) / d_zoom
                else:
                    self.parent_app.center_x = self.parent_app.abs_center_x - (self.parent_app.abs_center_x - self.parent_app.center_x) / d_zoom
                    self.parent_app.center_y = self.parent_app.abs_center_y - (self.parent_app.abs_center_y - self.parent_app.center_y) / d_zoom
            
            self.parent_app.apply_3d_zoom()
            self.parent_app.status_lbl.setText(f"3D Zoom: {self.parent_app.cam_zoom:.2f}x")
            
        # --- 2D Zoom Logic ---
        else:
            ax = self.parent_app.ax
            x_min, x_max = ax.get_xlim()
            y_min, y_max = ax.get_ylim()
            
            # Simple zoom towards mouse cursor for 2D
            inv = ax.transData.inverted()
            x_mouse, y_mouse = inv.transform((event.position().x(), self.height() - event.position().y()))
            
            factor = 0.85 if zoom_in else 1.15
            ax.set_xlim([x_mouse - (x_mouse - x_min)*factor, x_mouse + (x_max - x_mouse)*factor])
            ax.set_ylim([y_mouse - (y_mouse - y_min)*factor, y_mouse + (y_max - y_mouse)*factor])
            self.draw_idle()


class DensoViewerApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Denso Map Viewer")
        self.resize(1400, 850)
        
        # --- File Paths ---
        self.bin_path = DEFAULT_BIN
        self.csv_3d_path = DEFAULT_CSV_3D
        self.csv_2d_path = DEFAULT_CSV_2D
        
        # --- State Variables ---
        self.df = pd.DataFrame()
        self.current_index = 0
        self.total_maps = 0
        self.current_map_addr = ""
        
        self.map_mode = '3d' # '3d' or '2d'
        self.view_mode = 'plot' # 'plot' or 'table'
        
        # --- Independized Factors ---
        self.factor_z_3d = 0.0025
        self.offset_z_3d = 0.0
        self.factor_z_2d = 1.0
        self.offset_z_2d = 0.0
        
        self.z_format_3d = '>H'
        self.z_format_2d = '>f'
        self.ax_format = 'f'
        self.rot_mode = 'Z' 
        
        # --- Camera and Tracking Variables ---
        self.dragging = False
        self.mouse_x = 0
        self.mouse_y = 0
        self.start_elev = 35
        self.start_azim = 135
        self.cam_zoom = 1.0
        
        self.is_hovering = False
        self.hover_x = 0
        self.hover_y = 0
        
        self.real_axis_x = []
        self.real_axis_y = []
        self.x_flat = []
        self.y_flat = []
        self.z_flat = []
        
        self.init_ui()
        self.load_data()

    def init_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)
        
        # --- LEFT PANEL ---
        left_panel = QVBoxLayout()
        left_panel.addWidget(QLabel("<b>Search Map Address:</b>"))
        
        self.search_box = QLineEdit()
        self.search_box.textChanged.connect(self.update_list)
        left_panel.addWidget(self.search_box)
        
        self.map_listbox = QListWidget()
        self.map_listbox.itemSelectionChanged.connect(self.on_list_select)
        left_panel.addWidget(self.map_listbox)
        
        main_layout.addLayout(left_panel, 1) 
        
        # --- RIGHT PANEL ---
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
        
        btn_toggle = QPushButton("Toggle Plot / Table")
        btn_toggle.clicked.connect(self.toggle_view)
        toolbar_layout.addWidget(btn_toggle)
        
        btn_settings = QPushButton("⚙ Settings")
        btn_settings.clicked.connect(self.open_settings)
        toolbar_layout.addWidget(btn_settings)
        
        right_panel.addLayout(toolbar_layout)
        
        self.stacked_widget = QStackedWidget()
        
        # Matplotlib Canvas
        self.fig = plt.figure(figsize=(8, 6))
        self.fig.subplots_adjust(left=0.05, right=0.95, bottom=0.08, top=0.92)
        
        # Will be recreated dynamically depending on 2D/3D mode
        self.ax = self.fig.add_subplot(111, projection='3d')
        self.ax.set_navigate(False)
        
        self.canvas = CustomCanvas(self.fig, self)
        self.canvas.mpl_connect('button_press_event', self.on_mouse_press)
        self.canvas.mpl_connect('button_release_event', self.on_mouse_release)
        self.canvas.mpl_connect('motion_notify_event', self.on_mouse_move)
        
        self.stacked_widget.addWidget(self.canvas)
        
        # Qt Table
        self.table = QTableWidget()
        self.stacked_widget.addWidget(self.table)
        
        right_panel.addWidget(self.stacked_widget, 1)
        
        self.status_lbl = QLabel("Hover over the graph to see values...")
        self.status_lbl.setStyleSheet("background-color: #222; color: #FFF; font-weight: bold; font-size: 14px; padding: 8px; border-radius: 4px;")
        right_panel.addWidget(self.status_lbl)
        
        main_layout.addLayout(right_panel, 4) 

    def load_data(self):
        target_csv = self.csv_3d_path if self.map_mode == '3d' else self.csv_2d_path
        if not os.path.exists(target_csv):
            self.df = pd.DataFrame()
            self.total_maps = 0
            self.map_listbox.clear()
            self.status_lbl.setText(f"File not found: {target_csv}")
            return

        try:
            self.df = pd.read_csv(target_csv, dtype=str)
            self.total_maps = len(self.df)
            self.current_index = 0
            self.current_map_addr = ""
            self.update_list()
            self.rebuild_plot_axes()
            self.draw_map()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Could not read CSV:\n{e}")

    def rebuild_plot_axes(self):
        """Recreates the matplotlib subplot depending on 2D or 3D mode"""
        self.fig.clf()
        if self.map_mode == '3d':
            self.ax = self.fig.add_subplot(111, projection='3d')
            self.ax.set_navigate(False)
        else:
            self.ax = self.fig.add_subplot(111)
        self.canvas.draw_idle()

    # --- UI LOGIC ---
    def update_list(self):
        if self.df.empty: return
        search_term = self.search_box.text().lower()
        self.map_listbox.clear()
        self.filtered_indices = []
        
        addr_col = 'Map_Z_Addr' if self.map_mode == '3d' else 'Curve_Data_Addr'
        for idx, row in self.df.iterrows():
            addr = str(row[addr_col]).strip()
            if search_term in addr.lower():
                self.map_listbox.addItem(f"Map {idx+1}: {addr}")
                self.filtered_indices.append(idx)
                
        if self.filtered_indices:
            self.sync_listbox_selection()

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
        if self.view_mode == 'plot':
            self.view_mode = 'table'
            self.stacked_widget.setCurrentIndex(1)
        else:
            self.view_mode = 'plot'
            self.stacked_widget.setCurrentIndex(0)
        self.draw_map()

    def open_settings(self):
        dialog = QDialog(self)
        dialog.setWindowTitle("Settings")
        dialog.resize(450, 400)
        layout = QVBoxLayout(dialog)
        
        tabs = QTabWidget()
        layout.addWidget(tabs)
        
        # TAB 1: FILES & MODE
        tab_files = QWidget()
        vbox_f = QVBoxLayout(tab_files)
        
        gb_mode = QGroupBox("Visualization Mode")
        ly_mode = QHBoxLayout()
        rb_m1 = QRadioButton("3D Maps")
        rb_m2 = QRadioButton("2D Curves")
        if self.map_mode == '3d': rb_m1.setChecked(True)
        else: rb_m2.setChecked(True)
        ly_mode.addWidget(rb_m1); ly_mode.addWidget(rb_m2)
        gb_mode.setLayout(ly_mode)
        vbox_f.addWidget(gb_mode)
        
        def add_file_row(parent, label, current_path):
            lay = QHBoxLayout()
            lay.addWidget(QLabel(label))
            le = QLineEdit(current_path)
            btn = QPushButton("...")
            btn.setFixedWidth(30)
            def browse():
                path, _ = QFileDialog.getOpenFileName(dialog, "Select File")
                if path: le.setText(path)
            btn.clicked.connect(browse)
            lay.addWidget(le)
            lay.addWidget(btn)
            parent.addLayout(lay)
            return le
            
        vbox_f.addWidget(QLabel("<b>Paths:</b>"))
        le_bin = add_file_row(vbox_f, "BIN File:", self.bin_path)
        le_3d = add_file_row(vbox_f, "3D CSV:", self.csv_3d_path)
        le_2d = add_file_row(vbox_f, "2D CSV:", self.csv_2d_path)
        vbox_f.addStretch()
        tabs.addTab(tab_files, "Files & Mode")
        
        # TAB 2: FORMAT 
        tab_fmt = QWidget()
        vbox_fmt = QVBoxLayout(tab_fmt)
        
        gb_z = QGroupBox("Data Format (Z / Curve)")
        ly_z = QVBoxLayout()
        rb_z1 = QRadioButton("16-bit Big Endian (>H)")
        rb_z2 = QRadioButton("16-bit Little Endian (<H)")
        rb_z3 = QRadioButton("8-bit Unsigned (>B)")
        rb_z4 = QRadioButton("32-bit Float (>f)") 
        
        def update_z_format_rbs():
            fmt = self.z_format_3d if rb_m1.isChecked() else self.z_format_2d
            if fmt == '>H': rb_z1.setChecked(True)
            elif fmt == '<H': rb_z2.setChecked(True)
            elif fmt == '>B': rb_z3.setChecked(True)
            else: rb_z4.setChecked(True)

        rb_m1.toggled.connect(update_z_format_rbs)
        rb_m2.toggled.connect(update_z_format_rbs)
        update_z_format_rbs()
        
        ly_z.addWidget(rb_z1); ly_z.addWidget(rb_z2); ly_z.addWidget(rb_z3); ly_z.addWidget(rb_z4)
        gb_z.setLayout(ly_z)
        vbox_fmt.addWidget(gb_z)
        
        gb_a = QGroupBox("Axis Format")
        ly_a = QVBoxLayout()
        rb_a1 = QRadioButton("32-bit Float (f)")
        rb_a2 = QRadioButton("16-bit Int (H)")
        if self.ax_format == 'f': rb_a1.setChecked(True)
        else: rb_a2.setChecked(True)
        ly_a.addWidget(rb_a1); ly_a.addWidget(rb_a2)
        gb_a.setLayout(ly_a)
        vbox_fmt.addWidget(gb_a)
        vbox_fmt.addStretch()
        tabs.addTab(tab_fmt, "Format")
        
        # TAB 3: MATH & CONTROLS (SEPARATED FOR 3D / 2D)
        tab_math = QWidget()
        vbox_m = QVBoxLayout(tab_math)
        
        gb_math = QGroupBox("Math (Applied to Z/Curve)")
        form_m = QFormLayout()
        
        # 3D Math Inputs
        spin_f_3d = QDoubleSpinBox()
        spin_f_3d.setDecimals(5)
        spin_f_3d.setSingleStep(0.001)
        spin_f_3d.setRange(-10000, 10000)
        spin_f_3d.setValue(self.factor_z_3d)
        
        spin_o_3d = QDoubleSpinBox()
        spin_o_3d.setRange(-10000, 10000)
        spin_o_3d.setValue(self.offset_z_3d)
        
        # 2D Math Inputs
        spin_f_2d = QDoubleSpinBox()
        spin_f_2d.setDecimals(5)
        spin_f_2d.setSingleStep(0.001)
        spin_f_2d.setRange(-10000, 10000)
        spin_f_2d.setValue(self.factor_z_2d)
        
        spin_o_2d = QDoubleSpinBox()
        spin_o_2d.setRange(-10000, 10000)
        spin_o_2d.setValue(self.offset_z_2d)
        
        form_m.addRow("Factor 3D:", spin_f_3d)
        form_m.addRow("Offset 3D:", spin_o_3d)
        form_m.addRow("Factor 2D:", spin_f_2d)
        form_m.addRow("Offset 2D:", spin_o_2d)
        gb_math.setLayout(form_m)
        vbox_m.addWidget(gb_math)
        
        gb_r = QGroupBox("3D Mouse Rotation Mode")
        ly_r = QVBoxLayout()
        rb_r1 = QRadioButton("Z-Axis Only (WinOLS Azimuth)")
        rb_r2 = QRadioButton("WinOLS Style (Azimuth & Tilt)")
        rb_r3 = QRadioButton("Tilt Only (Elevation)")
        if self.rot_mode == 'Z': rb_r1.setChecked(True)
        elif self.rot_mode == 'WinOLS': rb_r2.setChecked(True)
        else: rb_r3.setChecked(True)
        ly_r.addWidget(rb_r1); ly_r.addWidget(rb_r2); ly_r.addWidget(rb_r3)
        gb_r.setLayout(ly_r)
        vbox_m.addWidget(gb_r)
        vbox_m.addStretch()
        tabs.addTab(tab_math, "Math & 3D")
        
        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        btns.accepted.connect(dialog.accept)
        btns.rejected.connect(dialog.reject)
        layout.addWidget(btns)
        
        if dialog.exec():
            # Apply File & Mode Changes
            self.bin_path = le_bin.text()
            self.csv_3d_path = le_3d.text()
            self.csv_2d_path = le_2d.text()
            
            new_mode = '3d' if rb_m1.isChecked() else '2d'
            if new_mode != self.map_mode:
                self.map_mode = new_mode
                self.load_data() 
            
            # Apply Formats 
            if rb_z1.isChecked(): new_z_format = '>H'
            elif rb_z2.isChecked(): new_z_format = '<H'
            elif rb_z3.isChecked(): new_z_format = '>B'
            else: new_z_format = '>f'
            
            if new_mode == '3d':
                self.z_format_3d = new_z_format
            else:
                self.z_format_2d = new_z_format
            
            if rb_a1.isChecked(): self.ax_format = 'f'
            else: self.ax_format = 'H'
            
            if rb_r1.isChecked(): self.rot_mode = 'Z'
            elif rb_r2.isChecked(): self.rot_mode = 'WinOLS'
            else: self.rot_mode = 'Tilt'
            
            # Save Math settings
            self.factor_z_3d = spin_f_3d.value()
            self.offset_z_3d = spin_o_3d.value()
            self.factor_z_2d = spin_f_2d.value()
            self.offset_z_2d = spin_o_2d.value()
            
            self.draw_map()

    # --- 3D ZOOM LOGIC ---
    def apply_3d_zoom(self):
        if not hasattr(self, 'map_size_x'): return
        
        x_range = max(1, self.map_size_x - 1) / self.cam_zoom
        y_range = max(1, self.map_size_y - 1) / self.cam_zoom
        
        min_c_x = x_range / 2
        max_c_x = (self.map_size_x - 1) - x_range / 2
        self.center_x = max(min_c_x, min(self.center_x, max_c_x))
        
        min_c_y = y_range / 2
        max_c_y = (self.map_size_y - 1) - y_range / 2
        self.center_y = max(min_c_y, min(self.center_y, max_c_y))
        
        self.ax.set_xlim(self.center_x - x_range/2, self.center_x + x_range/2)
        self.ax.set_ylim(self.center_y + y_range/2, self.center_y - y_range/2)
        
        if self.z_min == self.z_max:
            self.ax.set_zlim(self.z_min - 1, self.z_max + 1)
        else:
            self.ax.set_zlim(self.z_min, self.z_max)
            
        self.canvas.draw_idle()

    # --- MATPLOTLIB EVENTS (HOVER & ROTATION) ---
    def on_mouse_press(self, event):
        if event.button == 1: 
            self.dragging = True
            self.mouse_x = event.x
            self.mouse_y = event.y
            if self.map_mode == '3d':
                self.start_elev = self.ax.elev
                self.start_azim = self.ax.azim
            else:
                self.start_xlim = self.ax.get_xlim()
                self.start_ylim = self.ax.get_ylim()

    def on_mouse_release(self, event):
        self.dragging = False
        if self.map_mode == '3d':
            self.start_elev = self.ax.elev
            self.start_azim = self.ax.azim

    def on_mouse_move(self, event):
        if self.df.empty: return
        
        # 1. Handling Drag (Rotation/Pan)
        if self.dragging:
            if event.x is None or event.y is None: return
            
            # --- 3D Rotation ---
            if self.map_mode == '3d':
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
                    
                self.ax.view_init(elev=new_elev, azim=new_azim)
                self.canvas.draw_idle()
            
            # --- 2D Pan ---
            else:
                if event.xdata is None or event.ydata is None: return
                dx = event.xdata - self.mouse_x_data
                dy = event.ydata - self.mouse_y_data
                self.ax.set_xlim(self.start_xlim[0] - dx, self.start_xlim[1] - dx)
                self.ax.set_ylim(self.start_ylim[0] - dy, self.start_ylim[1] - dy)
                self.canvas.draw_idle()
            return
            
        else:
            self.mouse_x_data = event.xdata
            self.mouse_y_data = event.ydata
            
        # 2. Handling Hover
        if getattr(event, 'inaxes', None) != self.ax or len(self.z_flat) == 0:
            self.is_hovering = False
            if hasattr(self, 'cursor_marker') and self.cursor_marker.get_visible():
                self.cursor_marker.set_visible(False)
                self.status_lbl.setText("Hover over the graph to see values...")
                self.canvas.draw_idle()
            return

        try:
            if self.map_mode == '3d':
                xs, ys, _ = proj3d.proj_transform(self.x_flat, self.y_flat, self.z_flat, self.ax.get_proj())
                points2d = self.ax.transData.transform(np.column_stack([xs, ys]))
            else:
                points2d = self.ax.transData.transform(np.column_stack([self.x_flat, self.z_flat]))

            dists = (points2d[:, 0] - event.x)**2 + (points2d[:, 1] - event.y)**2
            min_idx = np.argmin(dists)
            
            if dists[min_idx] < 600: 
                self.is_hovering = True
                
                if self.map_mode == '3d':
                    self.hover_x = self.x_flat[min_idx]
                    self.hover_y = self.y_flat[min_idx]
                    best_z = self.z_flat[min_idx]
                    self.cursor_marker.set_data([self.hover_x], [self.hover_y])
                    self.cursor_marker.set_3d_properties([best_z])
                    rx = self.real_axis_x[self.hover_x]
                    ry = self.real_axis_y[self.hover_y]
                    lbl = f"Target Point: X = {rx:g}   |   Y = {ry:g}   |   Z = {best_z:.2f}"
                else:
                    best_x = self.x_flat[min_idx]
                    best_z = self.z_flat[min_idx]
                    self.cursor_marker.set_data([best_x], [best_z])
                    lbl = f"Target Point: X = {best_x:g}   |   Z (Curve) = {best_z:.2f}"

                self.cursor_marker.set_visible(True)
                self.status_lbl.setText(lbl)
                self.canvas.draw_idle()
            else:
                self.is_hovering = False
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
            with open(self.bin_path, "rb") as f:
                f.seek(addr)
                raw = f.read(size * bytes_per_value)
            return np.array(struct.unpack(f"{endian}{size}{axis_format}", raw))
        except:
            return np.arange(size)

    def read_map_3d(self):
        row = self.df.iloc[self.current_index]
        size_x = int(row['Size_X'])
        size_y = int(row['Size_Y'])
        map_z_hex = str(row['Map_Z_Addr']).strip()
        endian = self.z_format_3d[0]
        fmt_char = self.z_format_3d[-1]
        
        if fmt_char == 'f': bytes_per_value = 4
        elif fmt_char.lower() == 'h': bytes_per_value = 2
        else: bytes_per_value = 1
        
        with open(self.bin_path, "rb") as f:
            f.seek(int(map_z_hex, 16))
            raw_z_data = f.read(size_y * size_x * bytes_per_value)
            
        z_values = struct.unpack(f"{endian}{size_y * size_x}{fmt_char}", raw_z_data)
        matrix_z = np.array(z_values).reshape((size_y, size_x))
        axis_x = self.read_axis(str(row['Axis_X_Addr']).strip(), size_x, endian, self.ax_format)
        axis_y = self.read_axis(str(row['Axis_Y_Addr']).strip(), size_y, endian, self.ax_format)
        return matrix_z, axis_x, axis_y, size_y, size_x, map_z_hex

    def read_map_2d(self):
        row = self.df.iloc[self.current_index]
        size_x = int(row['Size_X'])
        curve_data_hex = str(row['Curve_Data_Addr']).strip()
        
        endian = self.z_format_2d[0]
        fmt_char = self.z_format_2d[-1]
        
        if fmt_char == 'f': bytes_per_value = 4
        elif fmt_char.lower() == 'h': bytes_per_value = 2
        else: bytes_per_value = 1
        
        with open(self.bin_path, "rb") as f:
            f.seek(int(curve_data_hex, 16))
            raw_z = f.read(size_x * bytes_per_value)
            
        z_values = struct.unpack(f"{endian}{size_x}{fmt_char}", raw_z)
        curve_z = np.array(z_values)
        axis_x = self.read_axis(str(row['Axis_X_Addr']).strip(), size_x, endian, self.ax_format)
        
        axis_y_dummy = np.array([1])
        size_y_dummy = 1
        
        return curve_z, axis_x, axis_y_dummy, size_y_dummy, size_x, curve_data_hex

    # --- RENDERING ---
    def draw_map(self):
        if self.df.empty: return
        try:
            if self.map_mode == '3d':
                raw_matrix, axis_x, axis_y, size_y, size_x, map_addr = self.read_map_3d()
                current_factor = self.factor_z_3d
                current_offset = self.offset_z_3d
            else:
                raw_matrix, axis_x, _, size_y, size_x, map_addr = self.read_map_2d()
                current_factor = self.factor_z_2d
                current_offset = self.offset_z_2d
                
            matrix_z = (raw_matrix * current_factor) + current_offset
            
            clean_axis_x = [str(round(v, 2)).rstrip('0').rstrip('.') for v in axis_x]
            if self.map_mode == '3d':
                clean_axis_y = [str(round(v, 2)).rstrip('0').rstrip('.') for v in axis_y]
                self.real_axis_y = axis_y
            
            self.real_axis_x = axis_x
            
            # Setup Zoom constraints
            self.map_size_x = size_x
            self.map_size_y = size_y
            self.z_min = matrix_z.min()
            self.z_max = matrix_z.max()
            
            if self.current_map_addr != map_addr:
                self.abs_center_x = (size_x - 1) / 2.0
                self.abs_center_y = (size_y - 1) / 2.0
                self.center_x = self.abs_center_x
                self.center_y = self.abs_center_y
                self.cam_zoom = 1.0 
                self.current_map_addr = map_addr
            
            title = f"Map {self.current_index + 1}/{self.total_maps} | Addr: {map_addr} | Factor: {current_factor}"
            self.lbl_title.setText(title)

            if self.view_mode == 'plot':
                self.ax.clear()
                
                if self.map_mode == '3d':
                    x_grid = np.arange(size_x)
                    y_grid = np.arange(size_y)
                    X, Y = np.meshgrid(x_grid, y_grid)
                    
                    self.x_flat = X.flatten()
                    self.y_flat = Y.flatten()
                    self.z_flat = matrix_z.flatten()
                    
                    self.ax.plot_surface(X, Y, matrix_z, cmap='jet', edgecolor='k', linewidth=0.3, alpha=0.9)
                    self.cursor_marker, = self.ax.plot([0], [0], [0], marker='o', color='red', markersize=8, zorder=10)
                    self.cursor_marker.set_visible(False)
                    
                    self.ax.set_xticks(x_grid)
                    self.ax.set_xticklabels(clean_axis_x, rotation=45, ha='right', fontsize=8)
                    self.ax.set_yticks(y_grid)
                    self.ax.set_yticklabels(clean_axis_y, fontsize=8)
                    
                    self.ax.set_xlabel('\nX Axis', labelpad=12)
                    self.ax.set_ylabel('\nY Axis', labelpad=12)
                    self.ax.set_zlabel('Z Data', labelpad=12)
                    
                    self.ax.invert_yaxis() 
                    try: self.ax.set_box_aspect((2.5, 2.0, 0.6))
                    except: pass
                    
                    self.ax.view_init(elev=self.start_elev, azim=self.start_azim)
                    self.apply_3d_zoom()
                    
                elif self.map_mode == '2d':
                    self.x_flat = axis_x
                    self.z_flat = matrix_z
                    
                    self.ax.plot(axis_x, matrix_z, marker='o', color='b', linewidth=2, markersize=5)
                    self.cursor_marker, = self.ax.plot([], [], marker='o', color='red', markersize=8, zorder=10)
                    self.cursor_marker.set_visible(False)
                    
                    self.ax.set_xlabel('X Axis')
                    self.ax.set_ylabel('Curve Data')
                    self.ax.grid(True, linestyle='--', alpha=0.7)

                self.canvas.draw_idle()
                
            elif self.view_mode == 'table':
                self.table.clear()
                self.table.setRowCount(size_y)
                self.table.setColumnCount(size_x)
                self.table.setHorizontalHeaderLabels(clean_axis_x)
                
                if self.map_mode == '3d':
                    self.table.setVerticalHeaderLabels(clean_axis_y)
                    for i in range(size_y):
                        for j in range(size_x):
                            item = QTableWidgetItem(str(round(matrix_z[i, j], 2)))
                            item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                            self.table.setItem(i, j, item)
                else:
                    self.table.setVerticalHeaderLabels(["Curve Data"])
                    for j in range(size_x):
                        item = QTableWidgetItem(str(round(matrix_z[j], 2)))
                        item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                        self.table.setItem(0, j, item)
                        
                self.table.resizeColumnsToContents()
                
        except Exception as e:
            if self.view_mode == 'plot':
                self.ax.clear()
                if hasattr(self.ax, 'text2D'):
                    self.ax.text2D(0.5, 0.5, f"Error:\n{str(e)}", transform=self.ax.transAxes, ha='center', color='red')
                else:
                    self.ax.text(0.5, 0.5, f"Error:\n{str(e)}", transform=self.ax.transAxes, ha='center', color='red')
                self.canvas.draw_idle()
            else:
                self.table.clear()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    viewer = DensoViewerApp()
    viewer.show()
    sys.exit(app.exec())