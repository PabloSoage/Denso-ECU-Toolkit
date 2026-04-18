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
                             QTabWidget, QFileDialog, QMessageBox, QCheckBox, QTableView,
                             QStyledItemDelegate, QInputDialog)
from PyQt6.QtCore import Qt, QEvent, QPointF, QRectF, QAbstractTableModel, QModelIndex, QVariant
from PyQt6.QtGui import QPainter, QColor, QPolygonF, QBrush, QFont, QKeySequence, QShortcut

# ================= DEFAULT CONFIGURATION =================
DEFAULT_CSV_3D = "3d_maps_review.csv"
DEFAULT_CSV_2D = "2d_maps_review.csv"
DEFAULT_BIN = "115_e3a4d17c28.bin"       
# =========================================================

class SparklineWidget(QWidget):
    """Subclass that draws the sparklines at the end of each row"""
    def __init__(self, data_row, min_val, max_val, style='Bars'):
        super().__init__()
        self.data = data_row
        self.min_val = min_val
        self.max_val = max_val
        self.style = style
        self.setMinimumWidth(120)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        painter.fillRect(self.rect(), QColor(0, 0, 0))
        
        w = self.width()
        h = self.height()
        
        painter.setBrush(QBrush(QColor(0, 255, 0)))
        painter.setPen(Qt.PenStyle.NoPen)
        
        if self.max_val == self.min_val:
            if self.style == 'Line':
                poly = QPolygonF([QPointF(0, h), QPointF(w, h)])
                painter.drawPolygon(poly)
            else:
                num_bars = len(self.data)
                bar_w = w / num_bars
                for i in range(num_bars):
                    x = i * bar_w
                    painter.drawRect(QRectF(x, h - 2, max(1.0, bar_w - 0.5), 2))
            return

        if self.style == 'Line':
            pts = [QPointF(0, h)]
            for i, val in enumerate(self.data):
                x = i * (w / max(1, len(self.data) - 1))
                y = h - ((val - self.min_val) / (self.max_val - self.min_val)) * h
                pts.append(QPointF(x, y))
            pts.append(QPointF(w, h))
            painter.drawPolygon(QPolygonF(pts))
        else:
            # Bars mode (Individual rectangles like WinOLS)
            num_bars = len(self.data)
            bar_w = w / num_bars
            for i, val in enumerate(self.data):
                x = i * bar_w
                y_norm = (val - self.min_val) / (self.max_val - self.min_val)
                bar_h = y_norm * (h - 2)
                y = h - 1 - bar_h
                # Float rect instead of int to avoid rounding issues in separation and width. 
                # Slightly wider width by reducing the subtraction from 1 to 0.5.
                painter.drawRect(QRectF(x, y, max(1.0, bar_w - 0.5), bar_h))


class HexMapDelegate(QStyledItemDelegate):
    def paint(self, painter, option, index):
        spark_data = index.data(Qt.ItemDataRole.UserRole + 1)
        if spark_data:
            values = spark_data.get('values', [])
            style = spark_data.get('style', 'Bars')
            if not values:
                return

            painter.save()
            painter.fillRect(option.rect, QColor(0, 0, 0))
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)

            w = option.rect.width()
            h = option.rect.height()
            x_off = option.rect.x()
            y_off = option.rect.y()

            painter.setBrush(QBrush(QColor(0, 255, 0)))
            
            min_val = min(values)
            max_val = max(values)

            if min_val == max_val:
                if style == 'Line':
                    painter.setPen(QColor(0, 255, 0))
                    poly = QPolygonF([QPointF(x_off, y_off + h), QPointF(x_off + w, y_off + h)])
                    painter.drawPolygon(poly)
                else:
                    painter.setPen(Qt.PenStyle.NoPen)
                    num_bars = len(values)
                    bar_w = w / num_bars
                    for i in range(num_bars):
                        bx = x_off + i * bar_w
                        # Dibuja barritas de 2px de alto en la base para filas planas
                        painter.drawRect(QRectF(bx, y_off + h - 2, max(1.0, bar_w - 0.5), 2))
            else:
                painter.setPen(Qt.PenStyle.NoPen)
                if style == 'Line':
                    pts = [QPointF(x_off, y_off + h)]
                    for i, val in enumerate(values):
                        x = x_off + i * (w / max(1, len(values) - 1))
                        y = y_off + h - ((val - min_val) / (max_val - min_val)) * h
                        pts.append(QPointF(x, y))
                    pts.append(QPointF(x_off + w, y_off + h))
                    painter.drawPolygon(QPolygonF(pts))
                else:
                    num_bars = len(values)
                    bar_w = w / num_bars
                    for i, val in enumerate(values):
                        bx = x_off + i * bar_w
                        y_norm = (val - min_val) / (max_val - min_val)
                        bar_h = y_norm * (h - 2)
                        by = y_off + h - 1 - bar_h
                        painter.drawRect(QRectF(bx, by, max(1.0, bar_w - 0.5), bar_h))
            painter.restore()
            return

        # Draw background and text (default behavior)
        super().paint(painter, option, index)
            
        borders = index.data(Qt.ItemDataRole.UserRole)
        if borders:
            edges = borders.get('edges', 0)
            color = borders.get('color')
            tag = borders.get('tag', '')
                
            painter.save()
            pen = painter.pen()
            pen.setColor(color)
            pen.setWidth(2)
            painter.setPen(pen)
                
            rect = option.rect
            x = rect.x()
            y = rect.y()
            r = rect.right() - 1
            b = rect.bottom() - 1
            
            # Map outline
            if edges & 1: painter.drawLine(x, y, r, y)       # Top
            if edges & 2: painter.drawLine(x, b, r, b)       # Bottom
            if edges & 4: painter.drawLine(x, y, x, b)       # Left
            if edges & 8: painter.drawLine(r, y, r, b)       # Right
            
            # Draw tag if this is the start of the map
            if tag:
                font = painter.font()
                font.setPointSize(8)
                font.setBold(True)
                painter.setFont(font)
                fm = painter.fontMetrics()
                tw = fm.horizontalAdvance(tag) + 6
                th = fm.height() + 2
                
                tag_rect = QRectF(x, y, tw, th)
                painter.fillRect(tag_rect, QColor(0, 0, 0, 180)) # semi-transparent black
                painter.setPen(color) # colored text
                painter.drawText(tag_rect, Qt.AlignmentFlag.AlignCenter, tag)
                
            painter.restore()

class HexTableModel(QAbstractTableModel):
    def __init__(self, bin_data, map_array, map_dicts, fmt='>B', sparkline_style='Bars'):
        super().__init__()
        self.update_settings(bin_data, map_array, map_dicts, fmt, sparkline_style)

    def update_settings(self, bin_data, map_array, map_dicts, fmt, sparkline_style):
        self.bin_data = bin_data
        self.map_array = map_array
        self.map_dicts = map_dicts
        self.fmt = fmt
        self.endian = fmt[0]
        self.fmt_char = fmt[-1]
        
        if self.fmt_char.lower() == 'f': self.bytes_per_col = 4
        elif self.fmt_char.lower() == 'h': self.bytes_per_col = 2
        else: self.bytes_per_col = 1
            
        self.data_cols = max(1, 16 // self.bytes_per_col)
        self.sparkline_style = sparkline_style
        self.layoutChanged.emit()

    def rowCount(self, parent=QModelIndex()):
        if not self.bin_data: return 0
        return (len(self.bin_data) + 15) // 16

    def columnCount(self, parent=QModelIndex()):
        return self.data_cols + 1

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if role == Qt.ItemDataRole.DisplayRole:
            if orientation == Qt.Orientation.Horizontal:
                if section == self.data_cols:
                    return "Profile"
                return f"{section * self.bytes_per_col:02X}"
            else:
                return f"{section*16:08X}"
        return QVariant()

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid(): return QVariant()
        
        is_sparkline = (index.column() == self.data_cols)
        
        if is_sparkline:
            if role == Qt.ItemDataRole.UserRole + 1:
                row_addr = index.row() * 16
                end_addr = min(row_addr + 16, len(self.bin_data))
                val_bytes = self.bin_data[row_addr:end_addr]
                values = []
                for i in range(0, len(val_bytes), self.bytes_per_col):
                    chunk = val_bytes[i:i+self.bytes_per_col]
                    if len(chunk) < self.bytes_per_col: break
                    try:
                        val = struct.unpack(f"{self.endian}{self.fmt_char}", chunk)[0]
                        values.append(val)
                    except: pass
                if not values: return QVariant()
                return {'values': values, 'style': self.sparkline_style}
            return QVariant()
            
        col_offset = index.column() * self.bytes_per_col
        addr = index.row() * 16 + col_offset
        
        if role == Qt.ItemDataRole.DisplayRole:
            if addr + self.bytes_per_col <= len(self.bin_data):
                val_bytes = self.bin_data[addr:addr+self.bytes_per_col]
                if self.bytes_per_col == 1:
                    return f"{val_bytes[0]:02X}"
                elif self.bytes_per_col == 2:
                    val = struct.unpack(f"{self.endian}H", val_bytes)[0]
                    return f"{val:04X}"
                elif self.bytes_per_col == 4:
                    val = struct.unpack(f"{self.endian}I", val_bytes)[0]
                    return f"{val:08X}"
            return "??"
            
        elif role == Qt.ItemDataRole.UserRole:
            if not self.map_array or addr >= len(self.map_array): return QVariant()
            
            mid = self.map_array[addr]
            if mid == -1: return QVariant()
            
            # Check edge neighbors to determine outlines
            edges = 0
            if addr < 16 or self.map_array[addr - 16] != mid: edges |= 1 # Top
            if addr + 16 >= len(self.map_array) or self.map_array[addr + 16] != mid: edges |= 2 # Bottom
            if col_offset == 0 or addr == 0 or self.map_array[addr - self.bytes_per_col] != mid: edges |= 4 # Left
            if col_offset + self.bytes_per_col >= 16 or addr + self.bytes_per_col >= len(self.map_array) or self.map_array[addr + self.bytes_per_col] != mid: edges |= 8 # Right
            
            info = self.map_dicts.get(mid)
            if not info: return QVariant()
            
            tag = info['tag'] if info['addr'] == addr else ''
            return {'edges': edges, 'color': info['color'], 'tag': tag}
            
        elif role == Qt.ItemDataRole.TextAlignmentRole:
            return Qt.AlignmentFlag.AlignCenter
            
        return QVariant()

class CustomCanvas(FigureCanvas):
    def __init__(self, fig, parent):
        super().__init__(fig)
        self.parent_app = parent

    def wheelEvent(self, event):
        if self.parent_app.view_mode != 'plot': return
        if not self.underMouse(): return
        
        delta = event.angleDelta().y()
        if delta == 0: return
        zoom_in = delta > 0

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
            
        else:
            factor = 1.15 if zoom_in else 0.85
            old_zoom = self.parent_app.cam_zoom_2d
            self.parent_app.cam_zoom_2d = max(1.0, min(self.parent_app.cam_zoom_2d * factor, 50.0))
            
            if self.parent_app.cam_zoom_2d == 1.0:
                self.parent_app.center_x_2d = (self.parent_app.abs_xlim[0] + self.parent_app.abs_xlim[1]) / 2.0
                self.parent_app.center_y_2d = (self.parent_app.abs_ylim[0] + self.parent_app.abs_ylim[1]) / 2.0
            elif old_zoom != self.parent_app.cam_zoom_2d:
                d_zoom = self.parent_app.cam_zoom_2d / old_zoom
                ax = self.parent_app.ax
                inv = ax.transData.inverted()
                pos = getattr(event, 'position', lambda: event.pos())()
                x_mouse, y_mouse = inv.transform((pos.x(), self.height() - pos.y()))
                
                self.parent_app.center_x_2d = x_mouse - (x_mouse - self.parent_app.center_x_2d) / d_zoom
                self.parent_app.center_y_2d = y_mouse - (y_mouse - self.parent_app.center_y_2d) / d_zoom
            
            self.parent_app.apply_2d_zoom()


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
        
        self.map_mode = '3d'
        self.view_mode = 'plot' 
        self.display_hex = False 
        self.apply_factor_to_hex = False 
        self.sparkline_style = 'Bars'    
        self.highlight_3d = True
        self.highlight_2d = True
        self.bin_data = b""
        self.color_map = None
        
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
        self.abs_center_x = 0
        self.abs_center_y = 0
        self.center_x = 0
        self.center_y = 0
        
        self.cam_zoom_2d = 1.0
        self.abs_xlim = (0, 1)
        self.abs_ylim = (0, 1)
        self.center_x_2d = 0
        self.center_y_2d = 0
        
        self.is_hovering = False
        self.hover_x = 0
        self.hover_y = 0
        
        self.real_axis_x = []
        self.real_axis_y = []
        self.x_flat = []
        self.y_flat = []
        self.z_flat = []
        self.raw_flat = []
        
        self.init_ui()
        self.load_data()
        
        QApplication.instance().installEventFilter(self)

    def eventFilter(self, obj, event):
        if event.type() == QEvent.Type.Wheel:
            if hasattr(self, 'view_mode') and self.view_mode == 'plot':
                if hasattr(self, 'canvas') and self.canvas.underMouse():
                    self.canvas.wheelEvent(event)
                    return True 
        return super().eventFilter(obj, event)

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
        self.fig.clf()
        if self.map_mode == '3d':
            self.ax = self.fig.add_subplot(111, projection='3d')
            self.ax.set_navigate(False)
            try: self.ax.disable_mouse_rotation() 
            except AttributeError: pass
        else:
            self.ax = self.fig.add_subplot(111)
        self.canvas.draw_idle()

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
        
        self.btn_hex = QPushButton("Dec / Hex")
        self.btn_hex.clicked.connect(self.toggle_hex)
        self.btn_hex.setVisible(False)
        toolbar_layout.addWidget(self.btn_hex)
        
        self.btn_main_mode = QPushButton("Mode: Map Viewer")
        self.btn_main_mode.clicked.connect(self.toggle_main_mode)
        toolbar_layout.addWidget(self.btn_main_mode)
        
        self.btn_toggle = QPushButton("View: Plot")
        self.btn_toggle.clicked.connect(self.toggle_view)
        toolbar_layout.addWidget(self.btn_toggle)
        
        btn_settings = QPushButton("⚙ Settings")
        btn_settings.clicked.connect(self.open_settings)
        toolbar_layout.addWidget(btn_settings)
        
        right_panel.addLayout(toolbar_layout)
        
        self.stacked_widget = QStackedWidget()
        
        # Matplotlib Canvas
        self.fig = plt.figure(figsize=(8, 6))
        self.fig.subplots_adjust(left=0.05, right=0.95, bottom=0.08, top=0.92)
        
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
        
        # Hex Table
        self.hex_table = QTableView()
        self.hex_table.setItemDelegate(HexMapDelegate())
        self.hex_table.selectionModel() # Will assign in update_hex_view
        self.stacked_widget.addWidget(self.hex_table)
        
        right_panel.addWidget(self.stacked_widget, 1)
        
        # Shortcuts
        self.shortcut_g = QShortcut(QKeySequence("G"), self)
        self.shortcut_g.activated.connect(self.goto_hex_address)
        
        self.status_lbl = QLabel("Hover over the graph to see values...")
        self.status_lbl.setStyleSheet("background-color: #222; color: #FFF; font-weight: bold; font-size: 14px; padding: 8px; border-radius: 4px;")
        right_panel.addWidget(self.status_lbl)
        
        main_layout.addLayout(right_panel, 4) 

    # --- UI LOGIC ---
    def update_list(self):
        if self.df.empty: return
        search_term = self.search_box.text().lower()
        self.map_listbox.clear()
        self.filtered_indices = []
        
        addr_col = 'Map_Z_Addr' if self.map_mode == '3d' else 'Curve_Data_Addr'
        for idx, row in self.df.iterrows():
            addr = str(row.get(addr_col, '')).strip()
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

    def toggle_main_mode(self):
        modes = ['Map Viewer', 'Hex Dump']
        current = self.btn_main_mode.text().replace("Mode: ", "")
        idx = modes.index(current)
        new_mode = modes[(idx + 1) % len(modes)]
        self.btn_main_mode.setText(f"Mode: {new_mode}")
        
        if new_mode == 'Map Viewer':
            self.btn_toggle.setVisible(True)
            self.stacked_widget.setCurrentIndex(0 if self.view_mode == 'plot' else 1)
            self.btn_hex.setVisible(self.view_mode == 'table')
        else:
            self.btn_toggle.setVisible(False)
            self.btn_hex.setVisible(False)
            self.stacked_widget.setCurrentIndex(2) # Hex Table
        self.draw_map()

    def toggle_view(self):
        if self.view_mode == 'plot':
            self.view_mode = 'table'
            self.btn_toggle.setText("View: Table")
            if self.btn_main_mode.text() == "Mode: Map Viewer":
                self.stacked_widget.setCurrentIndex(1)
                self.btn_hex.setVisible(True)
        else:
            self.view_mode = 'plot'
            self.btn_toggle.setText("View: Plot")
            if self.btn_main_mode.text() == "Mode: Map Viewer":
                self.stacked_widget.setCurrentIndex(0)
                self.btn_hex.setVisible(False)
        self.draw_map()

    def toggle_hex(self):
        self.display_hex = not self.display_hex
        self.btn_hex.setStyleSheet("background-color: #ffcccc;" if self.display_hex else "")
        self.draw_map()

    def open_settings(self):
        dialog = QDialog(self)
        dialog.setWindowTitle("Settings")
        dialog.resize(450, 480)
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
        
        gb_z3d = QGroupBox("3D Data Format (Z)")
        ly_z3d = QVBoxLayout()
        rb_3d_h = QRadioButton("16-bit Big Endian (>H)")
        rb_3d_l = QRadioButton("16-bit Little Endian (<H)")
        rb_3d_b = QRadioButton("8-bit Unsigned (>B)")
        rb_3d_f = QRadioButton("32-bit Float (>f)")
        if self.z_format_3d == '>H': rb_3d_h.setChecked(True)
        elif self.z_format_3d == '<H': rb_3d_l.setChecked(True)
        elif self.z_format_3d == '>B': rb_3d_b.setChecked(True)
        else: rb_3d_f.setChecked(True)
        ly_z3d.addWidget(rb_3d_h); ly_z3d.addWidget(rb_3d_l); ly_z3d.addWidget(rb_3d_b); ly_z3d.addWidget(rb_3d_f)
        gb_z3d.setLayout(ly_z3d)
        vbox_fmt.addWidget(gb_z3d)

        gb_z2d = QGroupBox("2D Data Format (Curve)")
        ly_z2d = QVBoxLayout()
        rb_2d_h = QRadioButton("16-bit Big Endian (>H)")
        rb_2d_l = QRadioButton("16-bit Little Endian (<H)")
        rb_2d_b = QRadioButton("8-bit Unsigned (>B)")
        rb_2d_f = QRadioButton("32-bit Float (>f)")
        if self.z_format_2d == '>H': rb_2d_h.setChecked(True)
        elif self.z_format_2d == '<H': rb_2d_l.setChecked(True)
        elif self.z_format_2d == '>B': rb_2d_b.setChecked(True)
        else: rb_2d_f.setChecked(True)
        ly_z2d.addWidget(rb_2d_h); ly_z2d.addWidget(rb_2d_l); ly_z2d.addWidget(rb_2d_b); ly_z2d.addWidget(rb_2d_f)
        gb_z2d.setLayout(ly_z2d)
        vbox_fmt.addWidget(gb_z2d)
        
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
        
        # TAB 3: MATH, VIEW & CONTROLS
        tab_math = QWidget()
        vbox_m = QVBoxLayout(tab_math)
        
        gb_math = QGroupBox("Math (Applied to Z/Curve)")
        form_m = QFormLayout()
        
        spin_f_3d = QDoubleSpinBox()
        spin_f_3d.setDecimals(5)
        spin_f_3d.setSingleStep(0.001)
        spin_f_3d.setRange(-10000, 10000)
        spin_f_3d.setValue(self.factor_z_3d)
        
        spin_o_3d = QDoubleSpinBox()
        spin_o_3d.setRange(-10000, 10000)
        spin_o_3d.setValue(self.offset_z_3d)
        
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
        
        # Table and Hex Settings
        gb_tbl = QGroupBox("Table & Hex Settings")
        ly_tbl = QVBoxLayout()
        self.cb_hex_f = QCheckBox("Apply Factor/Offset to Hex View (Table)")
        self.cb_hex_f.setChecked(self.apply_factor_to_hex)
        ly_tbl.addWidget(self.cb_hex_f)
        
        self.cb_hl_3d = QCheckBox("Highlight 3D Maps in Hex Mode (Blue)")
        self.cb_hl_3d.setChecked(self.highlight_3d)
        ly_tbl.addWidget(self.cb_hl_3d)
        
        self.cb_hl_2d = QCheckBox("Highlight 2D Maps in Hex Mode (Green)")
        self.cb_hl_2d.setChecked(self.highlight_2d)
        ly_tbl.addWidget(self.cb_hl_2d)
        
        ly_spark = QHBoxLayout()
        ly_spark.addWidget(QLabel("Sparkline Style:"))
        rb_sp1 = QRadioButton("Bars (WinOLS)")
        rb_sp2 = QRadioButton("Continuous Line")
        if self.sparkline_style == 'Bars': rb_sp1.setChecked(True)
        else: rb_sp2.setChecked(True)
        ly_spark.addWidget(rb_sp1); ly_spark.addWidget(rb_sp2)
        ly_tbl.addLayout(ly_spark)
        gb_tbl.setLayout(ly_tbl)
        vbox_m.addWidget(gb_tbl)
        
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
        tabs.addTab(tab_math, "Math & View")
        
        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        btns.accepted.connect(dialog.accept)
        btns.rejected.connect(dialog.reject)
        layout.addWidget(btns)
        
        if dialog.exec():
            self.bin_path = le_bin.text(); self.csv_3d_path = le_3d.text(); self.csv_2d_path = le_2d.text()
            new_mode = '3d' if rb_m1.isChecked() else '2d'
            if new_mode != self.map_mode:
                self.map_mode = new_mode
                self.load_data() 
            
            if rb_3d_h.isChecked(): self.z_format_3d = '>H'
            elif rb_3d_l.isChecked(): self.z_format_3d = '<H'
            elif rb_3d_b.isChecked(): self.z_format_3d = '>B'
            else: self.z_format_3d = '>f'

            if rb_2d_h.isChecked(): self.z_format_2d = '>H'
            elif rb_2d_l.isChecked(): self.z_format_2d = '<H'
            elif rb_2d_b.isChecked(): self.z_format_2d = '>B'
            else: self.z_format_2d = '>f'
            
            if rb_a1.isChecked(): self.ax_format = 'f'
            else: self.ax_format = 'H'
            
            if rb_r1.isChecked(): self.rot_mode = 'Z'
            elif rb_r2.isChecked(): self.rot_mode = 'WinOLS'
            else: self.rot_mode = 'Tilt'
            
            self.factor_z_3d = spin_f_3d.value()
            self.offset_z_3d = spin_o_3d.value()
            self.factor_z_2d = spin_f_2d.value()
            self.offset_z_2d = spin_o_2d.value()
            
            self.apply_factor_to_hex = self.cb_hex_f.isChecked()
            self.highlight_3d = self.cb_hl_3d.isChecked()
            self.highlight_2d = self.cb_hl_2d.isChecked()
            self.sparkline_style = 'Bars' if rb_sp1.isChecked() else 'Line'
            
            self.draw_map()

    # --- 3D & 2D ZOOM LOGIC ---
    def apply_3d_zoom(self):
        if not hasattr(self, 'map_size_x'): return
        
        base_x = max(1, self.map_size_x - 1) * 1.15
        base_y = max(1, self.map_size_y - 1) * 1.15
        
        x_range = base_x / self.cam_zoom
        y_range = base_y / self.cam_zoom
        
        min_c_x = x_range / 2
        max_c_x = (self.map_size_x - 1) - x_range / 2
        self.center_x = (self.map_size_x - 1) / 2.0 if min_c_x > max_c_x else max(min_c_x, min(self.center_x, max_c_x))
            
        min_c_y = y_range / 2
        max_c_y = (self.map_size_y - 1) - y_range / 2
        self.center_y = (self.map_size_y - 1) / 2.0 if min_c_y > max_c_y else max(min_c_y, min(self.center_y, max_c_y))
            
        self.ax.set_xlim(self.center_x - x_range/2, self.center_x + x_range/2)
        self.ax.set_ylim(self.center_y + y_range/2, self.center_y - y_range/2)
        
        if self.z_min == self.z_max: self.ax.set_zlim(self.z_min - 1, self.z_max + 1)
        else: self.ax.set_zlim(self.z_min, self.z_max)
            
        self.ax.set_autoscale_on(False)
        self.canvas.draw_idle()

    def apply_2d_zoom(self):
        x_range = (self.abs_xlim[1] - self.abs_xlim[0]) / self.cam_zoom_2d
        y_range = (self.abs_ylim[1] - self.abs_ylim[0]) / self.cam_zoom_2d
        
        min_cx = self.abs_xlim[0] + x_range/2
        max_cx = self.abs_xlim[1] - x_range/2
        self.center_x_2d = max(min_cx, min(self.center_x_2d, max_cx))
        
        min_cy = self.abs_ylim[0] + y_range/2
        max_cy = self.abs_ylim[1] - y_range/2
        self.center_y_2d = max(min_cy, min(self.center_y_2d, max_cy))
        
        self.ax.set_xlim(self.center_x_2d - x_range/2, self.center_x_2d + x_range/2)
        self.ax.set_ylim(self.center_y_2d - y_range/2, self.center_y_2d + y_range/2)
        self.ax.set_autoscale_on(False)
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
                self.start_center_x_2d = self.center_x_2d
                self.start_center_y_2d = self.center_y_2d

    def on_mouse_release(self, event):
        self.dragging = False
        if self.map_mode == '3d':
            self.start_elev = self.ax.elev
            self.start_azim = self.ax.azim

    def on_mouse_move(self, event):
        if self.df.empty: return
        
        if self.dragging:
            if event.x is None or event.y is None: return
            
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
            
            else:
                dx_pixels = event.x - self.mouse_x
                dy_pixels = event.y - self.mouse_y
                
                inv = self.ax.transData.inverted()
                x0, y0 = inv.transform((0, 0))
                x1, y1 = inv.transform((1, 1))
                
                data_dx_per_pixel = x1 - x0
                data_dy_per_pixel = y1 - y0
                
                self.center_x_2d = self.start_center_x_2d - (dx_pixels * data_dx_per_pixel)
                self.center_y_2d = self.start_center_y_2d - (dy_pixels * data_dy_per_pixel)
                
                self.apply_2d_zoom()
            return
            
        else:
            self.mouse_x_data = event.xdata
            self.mouse_y_data = event.ydata
            
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
                    
                    if self.display_hex:
                        v_hex = best_z if self.apply_factor_to_hex else self.raw_flat[min_idx]
                        lbl = f"Target: X = {rx:g}   |   Y = {ry:g}   |   Z (HEX) = {self.val_to_hex(v_hex)}"
                    else:
                        lbl = f"Target: X = {rx:g}   |   Y = {ry:g}   |   Z = {best_z:.2f}"
                else:
                    best_x = self.x_flat[min_idx]
                    best_z = self.z_flat[min_idx]
                    self.cursor_marker.set_data([best_x], [best_z])
                    if self.display_hex:
                        v_hex = best_z if self.apply_factor_to_hex else self.raw_flat[min_idx]
                        lbl = f"Target: X = {best_x:g}   |   Z (HEX) = {self.val_to_hex(v_hex)}"
                    else:
                        lbl = f"Target: X = {best_x:g}   |   Z (Curve) = {best_z:.2f}"

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

    def val_to_hex(self, val):
        """Convert a value to its Hexadecimal representation"""
        fmt_char = self.z_format_3d[-1] if self.map_mode == '3d' else self.z_format_2d[-1]
        try:
            if fmt_char == 'f':
                packed = struct.pack('>f', float(val))
                i = struct.unpack('>I', packed)[0]
                return f"{i:08X}"
            elif fmt_char.lower() == 'h':
                return f"{int(round(float(val))) & 0xFFFF:04X}"
            else:
                return f"{int(round(float(val))) & 0xFF:02X}"
        except: return "ERR"

    # --- RENDERING ---
    def build_color_map(self):
        if not os.path.exists(self.bin_path): return
        try:
            with open(self.bin_path, "rb") as f:
                self.bin_data = f.read()
        except: return
        
        self.map_array = [-1] * len(self.bin_data)
        self.map_dicts = {}
        
        def get_bperval(fmt):
            f = fmt[-1].lower()
            if f == 'f': return 4
            elif f == 'h': return 2
            return 1
            
        map_id = 0
            
        if self.highlight_3d and os.path.exists(self.csv_3d_path):
            try:
                df3 = pd.read_csv(self.csv_3d_path, dtype=str)
                bpv = get_bperval(self.z_format_3d)
                for _, row in df3.iterrows():
                    addr_str = str(row.get('Map_Z_Addr', '0')).strip()
                    addr = int(addr_str, 16)
                    sx = int(row.get('Size_X', 1))
                    sy = int(row.get('Size_Y', 1))
                    length = sx * sy * bpv
                    if addr + length <= len(self.map_array):
                        for i in range(addr, addr + length):
                            self.map_array[i] = map_id
                        self.map_dicts[map_id] = {
                            'color': QColor(0, 191, 255), # DeepSkyBlue
                            'tag': f"3D {addr_str} {sx}x{sy}",
                            'addr': addr
                        }
                    map_id += 1
            except: pass
            
        if self.highlight_2d and os.path.exists(self.csv_2d_path):
            try:
                df2 = pd.read_csv(self.csv_2d_path, dtype=str)
                bpv = get_bperval(self.z_format_2d)
                for _, row in df2.iterrows():
                    addr_str = str(row.get('Curve_Data_Addr', '0')).strip()
                    addr = int(addr_str, 16)
                    sx = int(row.get('Size_X', 1))
                    length = sx * bpv
                    if addr + length <= len(self.map_array):
                        for i in range(addr, addr + length):
                            self.map_array[i] = map_id
                        self.map_dicts[map_id] = {
                            'color': QColor(50, 205, 50), # LimeGreen
                            'tag': f"2D {addr_str} {sx}x1",
                            'addr': addr
                        }
                    map_id += 1
            except: pass

    def on_hex_selection_changed(self, current, previous):
        if not current.isValid(): return
        
        if current.column() == self.hex_table_model.data_cols:
            self.status_lbl.setText("Hex Cursor: Row Profile")
            return
            
        bpc = self.hex_table_model.bytes_per_col
        addr = current.row() * 16 + current.column() * bpc
        self.status_lbl.setText(f"Hex Cursor: {addr:08X}  ({addr})")

    def goto_hex_address(self):
        if self.stacked_widget.currentIndex() != 2: return
        addr_str, ok = QInputDialog.getText(self, "Goto Address", "Enter Hex Address:")
        if ok and addr_str:
            try:
                addr = int(addr_str.replace('0x', ''), 16)
                if not hasattr(self, 'hex_table_model'): return
                bpc = self.hex_table_model.bytes_per_col
                row = addr // 16
                col = (addr % 16) // bpc
                idx = self.hex_table_model.index(row, col)
                self.hex_table.scrollTo(idx, QTableView.ScrollHint.PositionAtTop)
                self.hex_table.setCurrentIndex(idx)
            except: pass

    def update_hex_view(self):
        self.build_color_map()
        
        fmt = self.z_format_3d if self.map_mode == '3d' else self.z_format_2d
        
        if not hasattr(self, 'hex_table_model'):
            self.hex_table_model = HexTableModel(self.bin_data, self.map_array, self.map_dicts, fmt, self.sparkline_style)
            self.hex_table.setModel(self.hex_table_model)
            self.hex_table.setFont(QFont("Courier New", 10))
            self.hex_table.selectionModel().currentChanged.connect(self.on_hex_selection_changed)
        else:
            self.hex_table_model.update_settings(self.bin_data, self.map_array, self.map_dicts, fmt, self.sparkline_style)
            
        bpc = self.hex_table_model.bytes_per_col
        for i in range(self.hex_table_model.data_cols):
            self.hex_table.setColumnWidth(i, 35 if bpc == 1 else (55 if bpc == 2 else 95))
        self.hex_table.setColumnWidth(self.hex_table_model.data_cols, 150)
            
        if not self.df.empty:
            addr_col = 'Map_Z_Addr' if self.map_mode == '3d' else 'Curve_Data_Addr'
            curr_addr_hex = str(self.df.iloc[self.current_index].get(addr_col, '0')).strip()
            try:
                addr_int = int(curr_addr_hex, 16)
                idx = self.hex_table_model.index(addr_int // 16, (addr_int % 16) // bpc)
                self.hex_table.scrollTo(idx, QTableView.ScrollHint.PositionAtTop)
                self.hex_table.setCurrentIndex(idx)
            except: pass

    def draw_map(self):
        if self.df.empty: return
        try:
            if self.map_mode == '3d':
                raw_matrix, axis_x, axis_y, size_y, size_x, map_addr = self.read_map_3d()
                current_factor = self.factor_z_3d
                current_offset = self.offset_z_3d
                current_fmt = self.z_format_3d
            else:
                raw_matrix, axis_x, _, size_y, size_x, map_addr = self.read_map_2d()
                current_factor = self.factor_z_2d
                current_offset = self.offset_z_2d
                current_fmt = self.z_format_2d
                
            matrix_z = (raw_matrix * current_factor) + current_offset
            
            clean_axis_x = [str(round(v, 2)).rstrip('0').rstrip('.') for v in axis_x]
            if self.map_mode == '3d':
                clean_axis_y = [str(round(v, 2)).rstrip('0').rstrip('.') for v in axis_y]
                self.real_axis_y = axis_y
            
            self.real_axis_x = axis_x
            
            self.map_size_x = size_x
            self.map_size_y = size_y
            self.z_min = matrix_z.min()
            self.z_max = matrix_z.max()
            
            if self.current_map_addr != map_addr:
                self.current_map_addr = map_addr
                
                self.abs_center_x = (size_x - 1) / 2.0
                self.abs_center_y = (size_y - 1) / 2.0
                self.center_x = self.abs_center_x
                self.center_y = self.abs_center_y
                self.cam_zoom = 1.0 
                
                x_margin = (axis_x.max() - axis_x.min()) * 0.05
                if x_margin == 0: x_margin = 1.0
                y_margin = (matrix_z.max() - matrix_z.min()) * 0.05
                if y_margin == 0: y_margin = 1.0
                
                self.abs_xlim = (axis_x.min() - x_margin, axis_x.max() + x_margin)
                self.abs_ylim = (matrix_z.min() - y_margin, matrix_z.max() + y_margin)
                self.center_x_2d = (self.abs_xlim[0] + self.abs_xlim[1]) / 2.0
                self.center_y_2d = (self.abs_ylim[0] + self.abs_ylim[1]) / 2.0
                self.cam_zoom_2d = 1.0
            
            title = f"Map {self.current_index + 1}/{self.total_maps} | Addr: {map_addr} | Z: {current_fmt} | Factor: {current_factor}"
            self.lbl_title.setText(title)

            if self.btn_main_mode.text() == "Mode: Hex Dump":
                self.update_hex_view()
            elif self.view_mode == 'plot':
                self.ax.clear()
                
                if self.map_mode == '3d':
                    x_grid = np.arange(size_x)
                    y_grid = np.arange(size_y)
                    X, Y = np.meshgrid(x_grid, y_grid)
                    
                    self.x_flat = X.flatten()
                    self.y_flat = Y.flatten()
                    self.z_flat = matrix_z.flatten()
                    self.raw_flat = raw_matrix.flatten()
                    
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
                    self.raw_flat = raw_matrix
                    
                    self.ax.plot(axis_x, matrix_z, marker='o', color='b', linewidth=2, markersize=5)
                    self.cursor_marker, = self.ax.plot([], [], marker='o', color='red', markersize=8, zorder=10)
                    self.cursor_marker.set_visible(False)
                    
                    self.ax.set_xlabel('X Axis')
                    self.ax.set_ylabel('Curve Data')
                    self.ax.grid(True, linestyle='--', alpha=0.7)
                    self.apply_2d_zoom()

                self.canvas.draw_idle()
                
            elif self.view_mode == 'table':
                self.table.clear()
                self.table.setRowCount(size_y)
                
                # Sum +1 for the Sparkline column
                self.table.setColumnCount(size_x + 1)
                
                headers = clean_axis_x + ["Profile"]
                self.table.setHorizontalHeaderLabels(headers)
                
                # Calculate the global min and max for proper scaling of green bars
                raw_min = raw_matrix.min()
                raw_max = raw_matrix.max()
                
                if self.map_mode == '3d':
                    self.table.setVerticalHeaderLabels(clean_axis_y)
                    for i in range(size_y):
                        for j in range(size_x):
                            if self.display_hex:
                                v = matrix_z[i, j] if self.apply_factor_to_hex else raw_matrix[i, j]
                                val_str = self.val_to_hex(v)
                            else:
                                val_str = f"{matrix_z[i, j]:.2f}"
                                
                            item = QTableWidgetItem(val_str)
                            item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                            self.table.setItem(i, j, item)
                            
                        # Insert Sparkline in the last column
                        spark = SparklineWidget(raw_matrix[i, :], raw_min, raw_max, self.sparkline_style)
                        self.table.setCellWidget(i, size_x, spark)
                else:
                    self.table.setVerticalHeaderLabels(["Curve Data"])
                    for j in range(size_x):
                        if self.display_hex:
                            v = matrix_z[j] if self.apply_factor_to_hex else raw_matrix[j]
                            val_str = self.val_to_hex(v)
                        else:
                            val_str = f"{matrix_z[j]:.2f}"
                            
                        item = QTableWidgetItem(val_str)
                        item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                        self.table.setItem(0, j, item)
                        
                    # Insert Sparkline 2D
                    spark = SparklineWidget(raw_matrix, raw_min, raw_max, self.sparkline_style)
                    self.table.setCellWidget(0, size_x, spark)
                        
                self.table.resizeColumnsToContents()
                self.table.setColumnWidth(size_x, 150)
                
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
    viewer.showMaximized()
    sys.exit(app.exec())