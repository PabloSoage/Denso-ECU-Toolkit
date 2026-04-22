import sys
import os
import struct
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from mpl_toolkits.mplot3d import proj3d

from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
                             QListWidget, QListWidgetItem, QLineEdit, QPushButton, QLabel, QStackedWidget,
                             QTableWidget, QTableWidgetItem, QGroupBox, QRadioButton,
                             QFormLayout, QDialog, QDialogButtonBox, QDoubleSpinBox,
                             QTabWidget, QFileDialog, QMessageBox, QCheckBox, QTableView, QComboBox, QComboBox,
                             QStyledItemDelegate, QInputDialog, QSplitter, QMenu, QAbstractItemView, QSpinBox)
from PyQt6.QtCore import Qt, QEvent, QPointF, QRectF, QAbstractTableModel, QModelIndex, QVariant
from PyQt6.QtGui import QAction, QPainter, QColor, QPolygonF, QBrush, QFont, QKeySequence, QShortcut

# ================= DEFAULT CONFIGURATION =================
DEFAULT_CSV_3D = "3d_maps_review.csv"
DEFAULT_CSV_2D = "2d_maps_review.csv"
DEFAULT_BIN = "115_e3a4d17c28.bin"       
# =========================================================

from widgets.sparkline_widget import SparklineWidget
from widgets.hex_map_delegate import HexMapDelegate
from widgets.hex_table_model import HexTableModel
from widgets.custom_canvas import CustomCanvas
from widgets.pyqtgraph_canvas import PyQtGraphCanvas
from core.data_manager import DataManager
from ui.dialogs.tag_editor_dialog import TagEditorDialog
from ui.managers.map_renderer import MapRenderer

import struct
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import os
import sys

class DensoViewerApp(QMainWindow):
    def closeEvent(self, event):
        plt.close('all')
        super().closeEvent(event)

    def __init__(self):
        super().__init__()
        self.data_manager = DataManager()
        self.map_renderer = MapRenderer(self)
        
        from ui.managers.map_list_manager import MapListManager
        from ui.managers.mouse_events_manager import MouseEventsManager
        
        self.map_list_manager = MapListManager(self)
        self.mouse_events_manager = MouseEventsManager(self)
        
        self.setWindowTitle("Denso Map Viewer")
        self.resize(1400, 850)
        
        # --- File Paths ---
        self.data_manager.bin_path = DEFAULT_BIN
        self.data_manager.csv_3d_path = DEFAULT_CSV_3D
        self.data_manager.csv_2d_path = DEFAULT_CSV_2D
        
        # --- State Variables ---
        self.data_manager.df = pd.DataFrame()
        self.data_manager.current_index = 0
        self.data_manager.total_maps = 0
        self.data_manager.current_map_addr = ""
        
        self.is_updating_table = False
        
        self.render_engine = 'matplotlib'
        self.map_mode = '3d'
        self.view_mode = 'plot' 
        self.display_hex = False 
        self.apply_factor_to_hex = False 
        self.sparkline_style = 'Bars'    
        self.highlight_3d = True
        self.highlight_2d = True
        self.highlight_custom_tags = True
        self.hex_row_width = 16
        self.active_tag_filters = set()
        self.hex_plot_visible = True
        self.hex_plot_mode = '3d'
        self.hex_plot_position = 'top'
        self.data_manager.bin_data = b""
        self.color_map = None
        
        # --- Independized Factors ---
        self.factor_z_3d = 0.0025
        self.offset_z_3d = 0.0
        self.factor_z_2d = 1.0
        self.offset_z_2d = 0.0
        
        self.data_manager.z_format_3d = '>H'
        self.data_manager.z_format_2d = '>f'
        self.data_manager.ax_format = 'f'
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
        self.data_manager.load_dtc_csv()
        self.load_data()
        
        QApplication.instance().installEventFilter(self)

    def eventFilter(self, obj, event):
        if event.type() == QEvent.Type.Wheel:
            if hasattr(self, 'view_mode') and self.view_mode == 'plot':
                if hasattr(self, 'canvas') and self.canvas.underMouse():
                    self.canvas.wheelEvent(event)
                    return True 
        return super().eventFilter(obj, event)

    def load_data(self, auto_scroll=True):
        current_main_mode = getattr(self, 'btn_main_mode', None)
        mode_str = current_main_mode.text().replace("Mode: ", "") if current_main_mode else "Map Viewer"
        
        success, msg = self.data_manager.load_csv(self.map_mode, main_mode=mode_str)
        
        if not success:
            self.map_listbox.clear()
            self.status_lbl.setText(msg)
            if "not found" not in msg:
                QMessageBox.critical(self, "Error", msg)
            return
            
        self.update_tag_filter_menu()
        self.update_list()
        self.rebuild_plot_axes()
        self.draw_map(auto_scroll=auto_scroll)

    def _sync_3d_axes(self, *args, **kwargs):
        if not hasattr(self, 'ax') or not hasattr(self, 'ax2'): return
        try:
            if self.ax.elev != self.ax2.elev or self.ax.azim != self.ax2.azim:
                self.ax2.view_init(elev=self.ax.elev, azim=self.ax.azim)
                self.canvas.draw_idle()
        except: pass

    def rebuild_plot_axes(self):
        self.fig.clf()
        is_3d = False
        cmp_idx = getattr(self, "cmb_compare_mode", None)
        is_twin = cmp_idx and cmp_idx.currentIndex() in (5, 6, 8)

        if hasattr(self, 'btn_main_mode') and self.btn_main_mode.text() == "Mode: Hex Dump":
            is_3d = self.hex_plot_mode == '3d'
            is_twin = False
        else:
            if not getattr(self, "data_manager", None) or getattr(self.data_manager, "df", None) is None or self.data_manager.df.empty:
                is_3d = (self.map_mode == '3d' or (self.map_mode == 'tags' and self.hex_plot_mode == '3d'))
            else:
                try:
                    row = self.data_manager.df.iloc[self.data_manager.current_index]
                    current_type = row.get('Map_Type', self.map_mode)
                    is_3d = (current_type == '3d' or (current_type == 'tags' and self.hex_plot_mode == '3d'))
                except Exception:
                    is_3d = (self.map_mode == '3d' or (self.map_mode == 'tags' and self.hex_plot_mode == '3d'))

        if hasattr(self, 'ax2'): del self.ax2

        if is_3d:
            if is_twin:
                self.ax = self.fig.add_subplot(121, projection='3d')
                self.ax2 = self.fig.add_subplot(122, projection='3d')
                self.ax2.set_navigate(False)
                try: self.ax2.disable_mouse_rotation()
                except AttributeError: pass
            else:
                self.ax = self.fig.add_subplot(111, projection='3d')
            self.ax.set_navigate(False)
            try: self.ax.disable_mouse_rotation()
            except AttributeError: pass
        else:
            self.ax = self.fig.add_subplot(111)
            self.ax.set_navigate(False)
        self.canvas.draw_idle()

    def init_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)
        
        # --- LEFT PANEL ---
        from ui.widgets.left_panel_widget import LeftPanelWidget
        self.left_panel_widget = LeftPanelWidget(self)
        main_layout.addWidget(self.left_panel_widget, 1)

        # --- RIGHT PANEL ---
        right_panel = QVBoxLayout()
        
        from ui.widgets.top_controls_widget import TopControlsWidget
        self.top_controls_widget = TopControlsWidget(self)
        right_panel.addWidget(self.top_controls_widget)
        
        self.stacked_widget = QSplitter(Qt.Orientation.Vertical)
        
        # Plot Container
        from ui.widgets.plot_container_widget import PlotContainerWidget
        self.plot_container = PlotContainerWidget(self)
        self.stacked_widget.addWidget(self.plot_container)
        
        # Bottom Stack (Table / Hex Table)
        from ui.widgets.table_view_widget import TableViewWidget
        self.bottom_stack = TableViewWidget(self)
        self.stacked_widget.addWidget(self.bottom_stack)
        
        # Adjust Splitter Sizes (Plot gets roughly 60%, Table 40%)
        self.stacked_widget.setSizes([600, 400])
        
        if self.view_mode in ('plot', 'split'):
            self.plot_container.setVisible(True)
            if self.view_mode == 'plot':
                self.bottom_stack.setVisible(False)
            else:
                self.bottom_stack.setVisible(True)
                self.bottom_stack.setCurrentIndex(0)
                self.btn_hex.setVisible(True)
        else:
            self.plot_container.setVisible(False)
            self.bottom_stack.setVisible(True)
            self.bottom_stack.setCurrentIndex(0)
            self.btn_hex.setVisible(True)
        
        right_panel.addWidget(self.stacked_widget, 1)
        
        # Shortcuts
        self.shortcut_g = QShortcut(QKeySequence("G"), self)
        self.shortcut_g.activated.connect(self.goto_hex_address)
        
        from ui.widgets.toolbar_widget import ToolbarWidget
        self.toolbar_widget = ToolbarWidget(self)
        right_panel.addWidget(self.toolbar_widget)
        
        main_layout.addLayout(right_panel, 4) 

    # --- UI LOGIC ---
    def update_tag_filter_menu(self):
        self.map_list_manager.update_tag_filter_menu()

    def on_tag_filter_toggled(self, tag, checked):
        self.map_list_manager.on_tag_filter_toggled(tag, checked)

    def on_map_type_changed(self, idx):
        self.map_list_manager.on_map_type_changed(idx)

    def update_list(self):
        self.map_list_manager.update_list()

    def on_list_select(self):
        self.map_list_manager.on_list_select()

    def prev_map(self):
        if self.data_manager.current_index > 0:
            self.data_manager.current_index -= 1
            self.sync_listbox_selection()
            self.draw_map()

    def next_map(self):
        if self.data_manager.current_index < self.data_manager.total_maps - 1:
            self.data_manager.current_index += 1
            self.sync_listbox_selection()
            self.draw_map()

    def on_compare_mode_changed(self, idx):
        self.data_manager.show_modified = (idx != 1)
        if idx in (7, 8) and not self.data_manager._reference_bin_data:
            QMessageBox.warning(self, "No External Reference", "Please load an external reference binary first using 'Load Ref. Bin'. Falling back to Original Bin comparison.")
        self.rebuild_plot_axes()
        self.draw_map()

    def set_reference_map(self):
        if self.data_manager.df.empty: return
        current_type = self.data_manager.df.iloc[self.data_manager.current_index].get('Map_Type', self.map_mode)

        try:
            if current_type == 'tags':
                is_2d = self.hex_plot_mode == '2d'
                raw_matrix, axis_x, axis_y, size_y, size_x, map_addr = self.data_manager.read_map_tags(as_2d=is_2d)
            elif current_type == '3d':
                raw_matrix, axis_x, axis_y, size_y, size_x, map_addr = self.data_manager.read_map_3d()
            else:
                raw_matrix, axis_x, axis_y, size_y, size_x, map_addr = self.data_manager.read_map_2d()

            self.reference_matrix = raw_matrix.copy()
            self.reference_axis_x = axis_x.copy()
            self.reference_axis_y = axis_y.copy()
            self.reference_size_x = size_x
            self.reference_size_y = size_y
            QMessageBox.information(self, "Reference Set", f"Reference map set (Shape: {raw_matrix.shape}).")
            if getattr(self, "cmb_compare_mode", None) and self.cmb_compare_mode.currentIndex() == 4:
                self.draw_map()
        except Exception as e:
            import traceback
            traceback.print_exc()
            QMessageBox.warning(self, "Error", f"Failed to set reference: {str(e)}")

    def sync_listbox_selection(self):
        self.map_list_manager.sync_listbox_selection()

    def toggle_main_mode(self):
        modes = ['Map Viewer', 'Hex Dump', 'Potential Maps']
        current = self.btn_main_mode.text().replace("Mode: ", "")
        idx = modes.index(current)
        new_mode = modes[(idx + 1) % len(modes)]
        self.btn_main_mode.setText(f"Mode: {new_mode}")
        
        self.rebuild_plot_axes()
        
        if new_mode in ('Map Viewer', 'Potential Maps'):
            self.btn_toggle.setVisible(True)
            self.btn_hex_plot_toggle.setVisible(False)
            self.btn_hex_plot_mode.setVisible(self.map_mode == 'tags' and new_mode != 'Potential Maps')
            self.spin_hex_cols.setVisible(False)
            
            # Reset splitter order for map viewer
            self.stacked_widget.setOrientation(Qt.Orientation.Vertical)
            self.stacked_widget.insertWidget(0, self.plot_container)
            self.stacked_widget.insertWidget(1, self.bottom_stack)
            self.stacked_widget.setSizes([600, 400])
            
            if self.view_mode in ('plot', 'split'):
                self.plot_container.setVisible(True)
                if self.view_mode == 'plot':
                    self.bottom_stack.setVisible(False)
                    self.btn_hex.setVisible(False)
                else:
                    self.bottom_stack.setVisible(True)
                    self.bottom_stack.setCurrentIndex(0) # Table
                    self.btn_hex.setVisible(True)
            else:
                self.plot_container.setVisible(False)
                self.bottom_stack.setVisible(True)
                self.bottom_stack.setCurrentIndex(0) # Table
                self.btn_hex.setVisible(True)
        else:
            self.btn_toggle.setVisible(False)
            self.btn_hex.setVisible(False)
            self.btn_hex_plot_toggle.setVisible(True)
            self.btn_hex_plot_mode.setVisible(self.hex_plot_visible)
            self.spin_hex_cols.setVisible(True)
            
            # Hex Dump mode
            self.plot_container.setVisible(self.hex_plot_visible)
            self.bottom_stack.setVisible(True)
            self.bottom_stack.setCurrentIndex(1) # Hex Table
            self.apply_splitter_position()
            
        self.load_data()

    def on_hex_cols_changed(self, val):
        self.hex_row_width = val
        if self.btn_main_mode.text() == "Mode: Hex Dump":
            self.update_hex_view()

    def toggle_hex_plot(self):
        self.hex_plot_visible = not self.hex_plot_visible
        self.btn_hex_plot_toggle.setText("Hex Plot: ON" if self.hex_plot_visible else "Hex Plot: OFF")
        self.btn_hex_plot_mode.setVisible(self.hex_plot_visible)
        
        if self.btn_main_mode.text() == "Mode: Hex Dump":
            self.plot_container.setVisible(self.hex_plot_visible)
            if self.hex_plot_visible:
                self.apply_splitter_position()
                self.update_hex_plot()

    def toggle_hex_plot_mode(self):
        if self.hex_plot_mode == '3d':
            self.hex_plot_mode = '2d'
            self.btn_hex_plot_mode.setText("Plot Mode: 2D")
        else:
            self.hex_plot_mode = '3d'
            self.btn_hex_plot_mode.setText("Plot Mode: 3D")
            
        self.rebuild_plot_axes()
        if self.btn_main_mode.text() == "Mode: Hex Dump":
            if self.hex_plot_visible:
                self.update_hex_plot()
        else:
            self.draw_map()

    def apply_splitter_position(self):
        if self.btn_main_mode.text() == "Mode: Hex Dump":
            if self.hex_plot_position == 'top':
                self.stacked_widget.setOrientation(Qt.Orientation.Vertical)
                self.stacked_widget.insertWidget(0, self.plot_container)
                self.stacked_widget.insertWidget(1, self.bottom_stack)
                self.stacked_widget.setSizes([600, 400])
            else:
                self.stacked_widget.setOrientation(Qt.Orientation.Horizontal)
                self.stacked_widget.insertWidget(0, self.bottom_stack)
                self.stacked_widget.insertWidget(1, self.plot_container)
                self.stacked_widget.setSizes([400, 600])

    def toggle_view(self):
        modes = ['plot', 'table', 'split']
        idx = modes.index(self.view_mode)
        self.view_mode = modes[(idx + 1) % len(modes)]

        if self.view_mode == 'plot':
            self.btn_toggle.setText("View: Plot")
            if self.btn_main_mode.text() == "Mode: Map Viewer":
                self.plot_container.setVisible(True)
                self.bottom_stack.setVisible(False)
                self.btn_hex.setVisible(False)
        elif self.view_mode == 'table':
            self.btn_toggle.setText("View: Table")
            if self.btn_main_mode.text() == "Mode: Map Viewer":
                self.plot_container.setVisible(False)
                self.bottom_stack.setVisible(True)
                self.bottom_stack.setCurrentIndex(0)
                self.btn_hex.setVisible(True)
        else: # split
            self.btn_toggle.setText("View: Split")
            if self.btn_main_mode.text() == "Mode: Map Viewer":
                self.plot_container.setVisible(True)
                self.bottom_stack.setVisible(True)
                self.bottom_stack.setCurrentIndex(0)
                self.btn_hex.setVisible(True)
        self.draw_map()

    def toggle_hex(self):
        self.display_hex = not self.display_hex
        self.btn_hex.setStyleSheet("background-color: #ffcccc;" if self.display_hex else "")
        self.draw_map()

    def open_custom_map_settings(self):
        from ui.dialogs.custom_map_settings_dialog import CustomMapSettingsDialog
        CustomMapSettingsDialog(self)

    def open_settings(self):
        from ui.dialogs.settings_dialog import SettingsDialog
        SettingsDialog(self)

    # --- 3D & 2D ZOOM LOGIC ---
    def apply_3d_zoom(self):
        self.mouse_events_manager.apply_3d_zoom()

    def apply_2d_zoom(self):
        self.mouse_events_manager.apply_2d_zoom()

    # --- MATPLOTLIB EVENTS (HOVER & ROTATION) ---
    def on_mouse_press(self, event):
        self.mouse_events_manager.on_mouse_press(event)

    def on_mouse_release(self, event):
        self.mouse_events_manager.on_mouse_release(event)

    def on_mouse_move(self, event):
        self.mouse_events_manager.on_mouse_move(event)

    def on_hex_selection_changed(self, current, previous):
        if not current.isValid(): return
        
        if current.column() == self.hex_table_model.data_cols:
            self.status_lbl.setText("Hex Cursor: Row Profile")
            return
            
        bpc = self.hex_table_model.bytes_per_col
        addr = current.row() * self.hex_row_width + current.column() * bpc
        self.status_lbl.setText(f"Hex Cursor: {addr:08X}  ({addr})")

    def goto_hex_address(self):
        if self.btn_main_mode.text() != "Mode: Hex Dump": return
        addr_str, ok = QInputDialog.getText(self, "Goto Address", "Enter Hex Address:")
        if ok and addr_str:
            try:
                addr = int(addr_str.replace('0x', ''), 16)
                if not hasattr(self, 'hex_table_model'): return
                bpc = self.hex_table_model.bytes_per_col
                row = addr // self.hex_row_width
                col = (addr % self.hex_row_width) // bpc
                idx = self.hex_table_model.index(row, col)
                self.hex_table.scrollTo(idx, QTableView.ScrollHint.PositionAtTop)
                self.hex_table.setCurrentIndex(idx)
            except: pass

    def update_hex_plot(self, selected=None, deselected=None):
        if self.btn_main_mode.text() != "Mode: Hex Dump":
            return
            
        if not self.hex_plot_visible:
            return
            
        model = self.hex_table_model
        sel_model = self.hex_table.selectionModel()
        indexes = sel_model.selectedIndexes()
        
        # Exclude sparkline column
        indexes = [idx for idx in indexes if idx.column() < model.data_cols]
        
        if not indexes:
            # Try to grab the current index
            curr = sel_model.currentIndex()
            start_row = curr.row() if curr.isValid() else 0
            end_row = start_row + 15
            start_col = 0
            end_col = model.data_cols - 1
            if start_row == 0 and not curr.isValid():
                # Avoid plotting if no valid data
                pass
        elif len(indexes) == 1:
            start_row = indexes[0].row()
            end_row = start_row + 15
            start_col = 0
            end_col = model.data_cols - 1
        else:
            start_row = min(idx.row() for idx in indexes)
            end_row = max(idx.row() for idx in indexes)
            start_col = min(idx.column() for idx in indexes)
            end_col = max(idx.column() for idx in indexes)
            
        size_y = end_row - start_row + 1
        size_x = end_col - start_col + 1
        
        if size_y <= 0 or size_x <= 0:
            return
            
        matrix_z = np.zeros((size_y, size_x))
        raw_matrix = np.zeros((size_y, size_x))
        
        bpc = model.bytes_per_col
        fmt_char = model.fmt_char
        endian = model.endian
        
        plot_mode = self.hex_plot_mode
        factor = self.factor_z_3d if plot_mode == '3d' else self.factor_z_2d
        offset = self.offset_z_3d if plot_mode == '3d' else self.offset_z_2d
        
        for r in range(size_y):
            for c in range(size_x):
                addr = (start_row + r) * self.hex_row_width + (start_col + c) * bpc
                if addr + bpc <= len(self.data_manager.bin_data):
                    val_bytes = self.data_manager.bin_data[addr:addr+bpc]
                    try:
                        v = struct.unpack(f"{endian}{fmt_char}", val_bytes)[0]
                        raw_matrix[r, c] = v
                        matrix_z[r, c] = v * factor + offset
                    except: pass
        
        self.ax.clear()
        
        main_addr = start_row*16 + start_col*bpc
        self.lbl_title.setText(f"Hex Plot ({plot_mode.upper()}) | Cursor: {main_addr:08X} | Area: {size_x} col x {size_y} row")
        
        if plot_mode == '3d':
            if size_x > 1 and size_y > 1:
                x_grid = np.arange(size_x)
                y_grid = np.arange(size_y)
                X, Y = np.meshgrid(x_grid, y_grid)
                self.x_flat = X.flatten()
                self.y_flat = Y.flatten()
                self.z_flat = matrix_z.flatten()
                self.raw_flat = raw_matrix.flatten()
                
                self.real_axis_x = np.arange(size_x)
                self.real_axis_y = np.arange(size_y)
                
                self.ax.plot_surface(X, Y, matrix_z, cmap='jet', edgecolor='k', linewidth=0.3, alpha=0.9)
                self.ax.invert_yaxis()
                try: self.ax.set_box_aspect((2.5, 2.0, 0.6))
                except: pass
                self.ax.view_init(elev=self.start_elev, azim=self.start_azim)
                
                self.map_size_x = size_x
                self.map_size_y = size_y
                self.z_min = matrix_z.min()
                self.z_max = matrix_z.max()
                self.cam_zoom = 1.0
                self.center_x = (size_x - 1) / 2.0
                self.center_y = (size_y - 1) / 2.0
                
            else:
                self.ax.text2D(0.5, 0.5, "Select a larger area in the hex table\n(At least 2x2 cells) for 3D", transform=self.ax.transAxes, ha='center', color='red')
                self.x_flat = []
        else:
            flat_z = matrix_z.flatten()
            flat_raw = raw_matrix.flatten()
            self.x_flat = np.arange(len(flat_z))
            self.z_flat = flat_z
            self.raw_flat = flat_raw
            self.ax.plot(self.x_flat, flat_z, marker='o', color='b', linewidth=2, markersize=5)
            self.ax.grid(True, linestyle='--', alpha=0.7)
            
            x_margin = max(1, len(flat_z) * 0.05)
            y_margin = max(1, (matrix_z.max() - matrix_z.min()) * 0.05)
            self.abs_xlim = (-x_margin, len(flat_z) - 1 + x_margin)
            self.abs_ylim = (matrix_z.min() - y_margin, matrix_z.max() + y_margin)
            self.cam_zoom_2d = 1.0
            self.center_x_2d = (self.abs_xlim[0] + self.abs_xlim[1]) / 2.0
            self.center_y_2d = (self.abs_ylim[0] + self.abs_ylim[1]) / 2.0
            
        if plot_mode == '3d':
            self.cursor_marker, = self.ax.plot([0], [0], [0], marker='o', color='red', markersize=8, zorder=10)
        else:
            self.cursor_marker, = self.ax.plot([0], [0], marker='o', color='red', markersize=8, zorder=10)
        self.cursor_marker.set_visible(False)
        self.canvas.draw_idle()

    def update_hex_view(self, auto_scroll=True):
        self.data_manager.build_color_map(
            highlight_3d=self.highlight_3d, 
            highlight_2d=self.highlight_2d, 
            highlight_custom=getattr(self, 'highlight_custom_tags', True)
        )
                
        # Convert QColor from tuples
        map_dicts_qcolor = {}
        for k, v in self.data_manager.map_dicts_tuples.items():
            r, g, b = v['color']
            map_dicts_qcolor[k] = {
                'color': QColor(r, g, b),
                'tag': v['tag'],
                'addr': v['addr']
            }
        self.data_manager.map_dicts = map_dicts_qcolor
                
        fmt = self.data_manager.z_format_3d if (self.map_mode == '3d' or (self.map_mode == 'tags' and self.hex_plot_mode == '3d')) else self.data_manager.z_format_2d
        
        if not hasattr(self, 'hex_table_model'):
            self.hex_table_model = HexTableModel(self.data_manager.bin_data, self.data_manager.map_array, self.data_manager.map_dicts, fmt, self.sparkline_style, getattr(self, 'hex_row_width', 16))
            self.hex_table.setModel(self.hex_table_model)
            self.hex_table.setFont(QFont("Courier New", 10))
            self.hex_table.selectionModel().currentChanged.connect(self.on_hex_selection_changed)
            self.hex_table.selectionModel().selectionChanged.connect(self.update_hex_plot)
        else:
            self.hex_table_model.update_settings(self.data_manager.bin_data, self.data_manager.map_array, self.data_manager.map_dicts, fmt, self.sparkline_style, getattr(self, 'hex_row_width', 16))
            
        bpc = self.hex_table_model.bytes_per_col
        for i in range(self.hex_table_model.data_cols):
            self.hex_table.setColumnWidth(i, 35 if bpc == 1 else (55 if bpc == 2 else 95))
        self.hex_table.setColumnWidth(self.hex_table_model.data_cols, 150)
            
        if auto_scroll and not self.data_manager.df.empty:
            addr_col = 'Map_Z_Addr' if (self.map_mode == '3d' or (self.map_mode == 'tags' and self.hex_plot_mode == '3d')) else 'Curve_Data_Addr'
            curr_addr_hex = str(self.data_manager.df.iloc[self.data_manager.current_index].get(addr_col, '0')).strip()
            try:
                addr_int = int(curr_addr_hex, 16)
                idx = self.hex_table_model.index(addr_int // self.hex_row_width, (addr_int % self.hex_row_width) // bpc)
                self.hex_table.scrollTo(idx, QTableView.ScrollHint.PositionAtTop)
                self.hex_table.setCurrentIndex(idx)
            except: pass

    def on_table_edit(self, item):
        if self.is_updating_table or not hasattr(self, 'data_manager'): return
        meta = item.data(Qt.ItemDataRole.UserRole)
        if not meta: return
        
        try:
            val_str = item.text().strip()
            
            if meta["display_hex"]:
                base = 16
                # If negative hex representation, maybe handle it.
                val = int(val_str, 16)
            else:
                val = float(val_str)
                
            if meta["display_hex"] and not meta["apply_factor_to_hex"]:
                raw_val = val
            else:
                raw_val = (val - meta["offset"]) / meta["factor"]

            success = self.data_manager.apply_edit(
                meta["address"], 
                old_val=None, 
                new_val=raw_val, 
                format_char=meta["fmt_char"], 
                endian=meta["endian"]
            )
            
            if success:
                # Re-draw the entire map immediately to show the updated value, correct coloring (if applied), and update the graph
                # But block signals or do it via a delayed call to avoid re-triggering while editing
                import PyQt6.QtCore as QtCore
                QTimer = QtCore.QTimer
                QTimer.singleShot(0, self.draw_map)
                QTimer.singleShot(0, self.update_list)
            else:
                QMessageBox.warning(self, "Edit Failed", "Could not apply edit to the binary data.")
        except ValueError:
            QMessageBox.warning(self, "Invalid Input", "Please enter a valid numeric value.")
            # Trigger a re-draw to restore the old value
            import PyQt6.QtCore as QtCore
            QTimer = QtCore.QTimer
            QTimer.singleShot(0, self.draw_map)

    def draw_map(self, auto_scroll=True):
        self.map_renderer.draw_map(auto_scroll)

    def show_hex_context_menu(self, pos):
        if self.btn_main_mode.text() != "Mode: Hex Dump": return
        idx = self.hex_table.indexAt(pos)
        if not idx.isValid(): return

        bpc = self.hex_table_model.bytes_per_col
        if idx.column() == self.hex_table_model.data_cols: return
        addr = idx.row() * self.hex_row_width + idx.column() * bpc

        menu = QMenu(self)
        action_tag = menu.addAction("Tag Selection/Map...")
        action_edit_dim = None
        
        # Only show Edit Dimensions if right-clicking an existing tag or a selection that might become one
        # Let's show it if we are in tags mode or all mode
        if self.map_mode in ('tags', 'all'):
            action_edit_dim = menu.addAction("Edit Tag Dimensions (3D)...")

        action = menu.exec(self.hex_table.viewport().mapToGlobal(pos))
        if action == action_tag:
            indexes = self.hex_table.selectionModel().selectedIndexes()
            length = bpc

            addresses = []
            for ix in indexes:
                if ix.column() < self.hex_table_model.data_cols:
                    addresses.append(ix.row() * self.hex_row_width + ix.column() * bpc)

            chunks = []
            if addresses:
                addresses.sort()
                c_start = addresses[0]
                c_prev = addresses[0]
                for a in addresses[1:]:
                    if a == c_prev + bpc:
                        c_prev = a
                    else:
                        chunks.append((c_start, (c_prev - c_start) + bpc))
                        c_start = a
                        c_prev = a
                chunks.append((c_start, (c_prev - c_start) + bpc))
            else:
                chunks.append((addr, bpc))

            # Special logic: if user just right-clicked a single cell (or nothing),
            # check if it belongs to an existing custom tag to edit it instead of creating a 1-byte tag.
            base_addr_hex = None
            if len(indexes) <= 1:
                mid = self.data_manager.map_array[addr] if addr < len(self.data_manager.map_array) else -1
                if mid != -1:
                    info = self.data_manager.map_dicts_tuples.get(mid, {})
                    if info.get('color') == (255, 165, 0): # Custom tag check
                        b_addr = info.get('addr')
                        if b_addr is not None:
                            b_hex = f"{b_addr:08X}"
                            tag_data = self.data_manager.hexdump_tags.get(b_hex, self.data_manager.tags.get(b_hex, {}))
                            if tag_data:
                                base_addr_hex = b_hex
                                chunks = tag_data.get("chunks", [(b_addr, tag_data.get("length", 1))])

            if not base_addr_hex:
                base_addr_hex = f"{chunks[0][0]:08X}"

            if not hasattr(self.data_manager, 'hexdump_tags'):
                self.data_manager.hexdump_tags = {}

            tag_data = self.data_manager.hexdump_tags.get(base_addr_hex, {})
            current_tags = tag_data.get("tags", [])

            dlg = TagEditorDialog(current_tags, self)
            if dlg.exec() == QDialog.DialogCode.Accepted:
                if not dlg.tags:
                    # If empty tags, user wants to remove it
                    if base_addr_hex in self.data_manager.hexdump_tags:
                        del self.data_manager.hexdump_tags[base_addr_hex]
                else:
                    total_len = sum(l for _, l in chunks)
                    self.data_manager.hexdump_tags[base_addr_hex] = {
                        "tags": dlg.tags,
                        "length": total_len,
                        "chunks": chunks
                    }

                addr_col = 'Map_Z_Addr' if (self.map_mode == '3d' or (self.map_mode == 'tags' and self.hex_plot_mode == '3d')) else 'Curve_Data_Addr'
                if not self.data_manager.df.empty:
                    df = self.data_manager.df
                    for c_start, _ in chunks:
                        c_hex = f"{c_start:08X}"
                        match_idx = df.index[df[addr_col].str.strip().str.upper() == c_hex]
                        if not match_idx.empty:
                            df.loc[match_idx, 'Tag'] = ", ".join(dlg.tags)

                self.data_manager.build_color_map(highlight_3d=self.highlight_3d, highlight_2d=self.highlight_2d, highlight_custom=getattr(self, 'highlight_custom_tags', True))
                self.update_tag_filter_menu()
                # Re-load the csv correctly to update dataframe for tags mode
                if self.map_mode in ('tags', 'all'):
                    self.load_data(auto_scroll=False)
                else:
                    self.update_list()
                
                if hasattr(self.data_manager, 'current_map_addr') and self.data_manager.current_map_addr == base_addr_hex:
                    self.sync_listbox_selection()
                    
                self.update_hex_view(auto_scroll=False)
                self.draw_map(auto_scroll=False)

        elif action_edit_dim and action == action_edit_dim:
            indexes = self.hex_table.selectionModel().selectedIndexes()
            if not indexes: return
            
            base_addr_hex = None
            if len(indexes) <= 1:
                mid = self.data_manager.map_array[addr] if addr < len(self.data_manager.map_array) else -1
                if mid != -1:
                    info = self.data_manager.map_dicts_tuples.get(mid, {})
                    if info.get('color') == (255, 165, 0): # Custom tag check
                        b_addr = info.get('addr')
                        if b_addr is not None:
                            base_addr_hex = f"{b_addr:08X}"
                            
            if not base_addr_hex:
                # Use current index as base address if no tag selected
                addr_tmp = indexes[0].row() * self.hex_row_width + indexes[0].column() * bpc
                base_addr_hex = f"{addr_tmp:08X}"
                
            custom = self.data_manager.custom_map_settings.get(base_addr_hex, {})
            current_sx = custom.get('Size_X', 16)
            current_sy = custom.get('Size_Y', 1)
            
            val_x, ok1 = QInputDialog.getInt(self, "Edit Dimensions", "Size X (Columns):", int(current_sx), 1, 1000)
            if ok1:
                val_y, ok2 = QInputDialog.getInt(self, "Edit Dimensions", "Size Y (Rows):", int(current_sy), 1, 1000)
                if ok2:
                    if base_addr_hex not in self.data_manager.custom_map_settings:
                        self.data_manager.custom_map_settings[base_addr_hex] = {}
                    self.data_manager.custom_map_settings[base_addr_hex]['Size_X'] = val_x
                    self.data_manager.custom_map_settings[base_addr_hex]['Size_Y'] = val_y
                    
                    if self.map_mode in ('tags', 'all'):
                        self.load_data(auto_scroll=False)
                    else:
                        self.update_list()
                    
                    if hasattr(self.data_manager, 'current_map_addr') and self.data_manager.current_map_addr == base_addr_hex:
                        self.sync_listbox_selection()
                    self.update_hex_view(auto_scroll=False)
                    self.draw_map(auto_scroll=False)

    def edit_current_tag_dimensions(self):
        if self.data_manager.df.empty: return
        row = self.data_manager.df.iloc[self.data_manager.current_index]
        if row.get('Map_Type', '') != 'tags':
            QMessageBox.information(self, "Info", "Select a Tag to edit its dimensions.")
            return
            
        base_addr_hex = str(row['Map_Z_Addr']).strip()
        
        custom = self.data_manager.custom_map_settings.get(base_addr_hex, {})
        length = int(row.get('Tag_Length', 1))
        
        bpc = 1
        fmt_char = custom.get('z_format', self.data_manager.z_format_3d)[-1]
        if fmt_char == 'f': bpc = 4
        elif fmt_char.lower() == 'h': bpc = 2
        elif fmt_char.lower() in ('i', 'l'): bpc = 4
        
        num_elements = length // bpc
        if num_elements == 0: num_elements = 1

        current_sx = custom.get('Size_X', min(num_elements, 16))
        current_sy = custom.get('Size_Y', max(1, num_elements // max(current_sx, 1)))

        val_x, ok1 = QInputDialog.getInt(self, "Edit Dimensions", "Size X (Columns):", int(current_sx), 1, 1000)
        if ok1:
            val_y, ok2 = QInputDialog.getInt(self, "Edit Dimensions", "Size Y (Rows):", int(current_sy), 1, 1000)
            if ok2:
                if base_addr_hex not in self.data_manager.custom_map_settings:
                    self.data_manager.custom_map_settings[base_addr_hex] = {}
                self.data_manager.custom_map_settings[base_addr_hex]['Size_X'] = val_x
                self.data_manager.custom_map_settings[base_addr_hex]['Size_Y'] = val_y
                
                # Apply changes to current dataframe
                self.data_manager.df.loc[self.data_manager.current_index, 'Size_X'] = str(val_x)
                self.data_manager.df.loc[self.data_manager.current_index, 'Size_Y'] = str(val_y)

                self.update_list()
                if hasattr(self.data_manager, 'current_map_addr') and self.data_manager.current_map_addr == base_addr_hex:
                    self.sync_listbox_selection()
                self.draw_map()

    def edit_specific_tag(self, target):
        if self.data_manager.df.empty: return
        row = self.data_manager.df.iloc[self.data_manager.current_index]        
        current_type = row.get('Map_Type', self.map_mode)
        
        if target == 'wrapper':
            addr_col = 'Wrapper_Addr'
            title_prefix = "Map"
        elif target == 'z':
            addr_col = 'Map_Z_Addr' if (current_type == '3d' or (current_type == 'tags' and self.hex_plot_mode == '3d')) else 'Curve_Data_Addr'
            title_prefix = "Z Data"
        elif target == 'x':
            addr_col = 'Axis_X_Addr'
            title_prefix = "X Axis"
        elif target == 'y':
            addr_col = 'Axis_Y_Addr'
            title_prefix = "Y Axis"
            if current_type != '3d' and not (current_type == 'tags' and self.hex_plot_mode == '3d'): return
            
        if addr_col not in row or pd.isna(row[addr_col]) or not str(row[addr_col]).strip():
            return

        addr = str(row[addr_col]).strip().upper()
        if not addr or addr in ('0', '0X0', '00000000'): 
            return

        tag_data = self.data_manager.tags.get(addr, {})
        current_tags = tag_data.get("tags", [])

        dlg = TagEditorDialog(current_tags, self)
        dlg.setWindowTitle(f"Edit {title_prefix} Tags ({addr})")
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self.data_manager.tags[addr] = {"tags": dlg.tags, "length": tag_data.get("length", 1)}
            
            if target == 'wrapper':
                self.data_manager.df.loc[self.data_manager.current_index, 'Tag'] = ", ".join(dlg.tags)
                
            self.data_manager.build_color_map(highlight_3d=self.highlight_3d, highlight_2d=self.highlight_2d, highlight_custom=self.highlight_custom_tags)
            self.update_tag_filter_menu()
            
            if target == 'wrapper':
                self.update_list()
                if hasattr(self.data_manager, 'current_map_addr') and self.data_manager.current_map_addr == addr:
                    self.sync_listbox_selection()
            
            self.update_hex_view()
            self.draw_map()

    def export_modified_bin(self):
        self.data_manager._ensure_bin_loaded()
        if not self.data_manager._modified_bin_data:
            QMessageBox.warning(self, "Export Failed", "No modifications have been done yet.")
            return
            
        file_path, _ = QFileDialog.getSaveFileName(self, "Export Modified Bin", "", "Binary Files (*.bin);;All Files (*)")
        if file_path:
            try:
                with open(file_path, "wb") as f:
                    f.write(self.data_manager._modified_bin_data)
                QMessageBox.information(self, "Success", f"Successfully exported modified bin to:\n{file_path}")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to export bin:\n{e}")

    def load_reference_bin(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Select Reference Bin", "", "Binary Files (*.bin);;All Files (*)")
        if file_path:
            try:
                with open(file_path, "rb") as f:
                    self.data_manager._reference_bin_data = f.read()
                QMessageBox.information(self, "Success", f"Successfully loaded external reference bin:\n{os.path.basename(file_path)}")
                self.draw_map()
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to load reference bin:\n{e}")

    def save_project(self):
        path, _ = QFileDialog.getSaveFileName(self, "Save Project", "", "Denso Project (*.dproj *.json)")
        if path:
            success, err = self.data_manager.save_project(path)
            if success:
                QMessageBox.information(self, "Success", "Project saved successfully.")
            else:
                QMessageBox.critical(self, "Error", f"Could not save project:\n{err}")

    def load_project(self):
        path, _ = QFileDialog.getOpenFileName(self, "Load Project", "", "Denso Project (*.dproj *.json)")
        if path:
            success, err = self.data_manager.load_project(path)
            if success:
                self.load_data()
                self.update_list()
                self.sync_listbox_selection()
                self.data_manager.load_dtc_csv()
                QMessageBox.information(self, "Success", "Project loaded successfully.")
            else:
                QMessageBox.critical(self, "Error", f"Could not load project:\n{err}")

    def show_dtc_tracker(self):
        from ui.dialogs.dtc_tracker_dialog import DtcTrackerDialog
        row = self.data_manager.df.iloc[self.data_manager.current_index]
        wrapper_addr_hex = str(row.get('Wrapper_Addr', '')).strip()
        dtc_info = self.data_manager.dtc_data.get(wrapper_addr_hex)
        if dtc_info:
            dlg = DtcTrackerDialog(dtc_info, self)
            dlg.exec()