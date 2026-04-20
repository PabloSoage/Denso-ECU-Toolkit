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
                             QStyledItemDelegate, QInputDialog, QSplitter, QMenu)
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
import struct
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import os
import sys
class TagEditorDialog(QDialog):
    def __init__(self, current_tags, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Edit Tags")
        self.tags = list(current_tags)
        self.layout = QVBoxLayout(self)
        
        self.list_widget = QListWidget()
        self.list_widget.addItems(self.tags)
        self.layout.addWidget(self.list_widget)
        
        h_layout = QHBoxLayout()
        self.new_tag_input = QLineEdit()
        self.btn_add = QPushButton("Add Tag")
        self.btn_remove = QPushButton("Remove Selected")
        h_layout.addWidget(self.new_tag_input)
        h_layout.addWidget(self.btn_add)
        h_layout.addWidget(self.btn_remove)
        self.layout.addLayout(h_layout)
        
        self.btn_add.clicked.connect(self.add_tag)
        self.btn_remove.clicked.connect(self.remove_tag)
        
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        self.layout.addWidget(buttons)
        
    def add_tag(self):
        t = self.new_tag_input.text().strip()
        if t and t not in self.tags:
            self.tags.append(t)
            self.list_widget.addItem(t)
            self.new_tag_input.clear()
            
    def remove_tag(self):
        for item in self.list_widget.selectedItems():
            self.tags.remove(item.text())
            self.list_widget.takeItem(self.list_widget.row(item))

class DensoViewerApp(QMainWindow):
    def closeEvent(self, event):
        plt.close('all')
        super().closeEvent(event)

    def __init__(self):
        super().__init__()
        self.data_manager = DataManager()
        
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
                                
        success, msg = self.data_manager.load_csv(self.map_mode)
        
                                        
        if not success:
            self.map_listbox.clear()
            self.status_lbl.setText(msg)
            if "File not found" not in msg:
                QMessageBox.critical(self, "Error", msg)
            return
            
        self.update_tag_filter_menu()
        self.update_list()
        self.rebuild_plot_axes()
        self.draw_map()

    def rebuild_plot_axes(self):
        self.fig.clf()
        is_3d = False
        if hasattr(self, 'btn_main_mode') and self.btn_main_mode.text() == "Mode: Hex Dump":
            is_3d = self.hex_plot_mode == '3d'
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

        if is_3d:
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
        left_panel = QVBoxLayout()
        
        self.cmb_map_type = QComboBox()
        self.cmb_map_type.addItems(["3D Maps", "2D Maps", "Hexdump Tags", "All"])
        self.cmb_map_type.currentIndexChanged.connect(self.on_map_type_changed)
        left_panel.addWidget(self.cmb_map_type)
        
        if self.map_mode == '2d':
            self.cmb_map_type.setCurrentIndex(1)
        elif self.map_mode == 'tags':
            self.cmb_map_type.setCurrentIndex(2)

        left_panel.addWidget(QLabel("<b>Search Map Address/Tag:</b>"))

        search_layout = QHBoxLayout()
        self.search_box = QLineEdit()
        self.search_box.textChanged.connect(self.update_list)
        
        self.btn_tag_filter = QPushButton("Tags Filter")
        self.tag_filter_menu = QMenu(self)
        self.btn_tag_filter.setMenu(self.tag_filter_menu)
        
        search_layout.addWidget(self.search_box)
        search_layout.addWidget(self.btn_tag_filter)
        left_panel.addLayout(search_layout)
        
        self.map_listbox = QListWidget()
        self.map_listbox.itemSelectionChanged.connect(self.on_list_select)
        left_panel.addWidget(self.map_listbox)
        
        # Tags and project management
        hbox_tags = QHBoxLayout()

        self.btn_edit_tags = QPushButton("Edit Tags ▼")
        self.edit_tags_menu = QMenu(self)
        
        action_wrapper = self.edit_tags_menu.addAction("Map Tag")
        action_wrapper.triggered.connect(lambda: self.edit_specific_tag('wrapper'))
        
        action_map = self.edit_tags_menu.addAction("Z Data Tag")
        action_map.triggered.connect(lambda: self.edit_specific_tag('z'))
        
        action_x = self.edit_tags_menu.addAction("X Axis Tag")
        action_x.triggered.connect(lambda: self.edit_specific_tag('x'))
        
        action_y = self.edit_tags_menu.addAction("Y Axis Tag")
        action_y.triggered.connect(lambda: self.edit_specific_tag('y'))
        
        self.btn_edit_tags.setMenu(self.edit_tags_menu)
        hbox_tags.addWidget(self.btn_edit_tags)
        
        left_panel.addLayout(hbox_tags)
        
        hbox_proj = QHBoxLayout()
        btn_load_proj = QPushButton("Load Proj")
        btn_load_proj.clicked.connect(self.load_project)
        btn_save_proj = QPushButton("Save Proj")
        btn_save_proj.clicked.connect(self.save_project)
        hbox_proj.addWidget(btn_load_proj)
        hbox_proj.addWidget(btn_save_proj)
        left_panel.addLayout(hbox_proj)

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

        self.cb_show_original = QCheckBox("Show Original")
        self.cb_show_original.toggled.connect(self.on_show_original_toggled)
        toolbar_layout.addWidget(self.cb_show_original)

        self.btn_hex = QPushButton("Dec / Hex")
        self.btn_hex.clicked.connect(self.toggle_hex)
        self.btn_hex.setVisible(False)
        toolbar_layout.addWidget(self.btn_hex)
        
        self.btn_hex_plot_toggle = QPushButton("Hex Plot: ON")
        self.btn_hex_plot_toggle.clicked.connect(self.toggle_hex_plot)
        self.btn_hex_plot_toggle.setVisible(False)
        toolbar_layout.addWidget(self.btn_hex_plot_toggle)
        
        self.btn_hex_plot_mode = QPushButton("Plot Mode: 3D")
        self.btn_hex_plot_mode.clicked.connect(self.toggle_hex_plot_mode)
        self.btn_hex_plot_mode.setVisible(False)
        toolbar_layout.addWidget(self.btn_hex_plot_mode)
        
        self.btn_main_mode = QPushButton("Mode: Map Viewer")
        self.btn_main_mode.clicked.connect(self.toggle_main_mode)
        toolbar_layout.addWidget(self.btn_main_mode)
        
        self.btn_toggle = QPushButton("View: Plot")
        self.btn_toggle.clicked.connect(self.toggle_view)
        toolbar_layout.addWidget(self.btn_toggle)
        
        btn_map_settings = QPushButton("⚙ Map Settings")
        btn_map_settings.clicked.connect(self.open_custom_map_settings)
        toolbar_layout.addWidget(btn_map_settings)

        btn_settings = QPushButton("⚙ Global Settings")
        btn_settings.clicked.connect(self.open_settings)
        toolbar_layout.addWidget(btn_settings)
        
        right_panel.addLayout(toolbar_layout)
        
        self.stacked_widget = QSplitter(Qt.Orientation.Vertical)
        
        # Matplotlib Canvas
        self.fig = plt.figure(figsize=(8, 6))
        self.fig.subplots_adjust(left=0.05, right=0.95, bottom=0.08, top=0.92)
        
        self.ax = self.fig.add_subplot(111, projection='3d')
        self.ax.set_navigate(False)
        
        self.canvas = CustomCanvas(self.fig, self)
        self.canvas.mpl_connect('button_press_event', self.on_mouse_press)
        self.canvas.mpl_connect('button_release_event', self.on_mouse_release)
        self.canvas.mpl_connect('motion_notify_event', self.on_mouse_move)
        
        
        self.pg_canvas = PyQtGraphCanvas(self)
        self.pg_canvas.setVisible(False)
        
        self.plot_container = QWidget()
        self.plot_container_layout = QVBoxLayout(self.plot_container)
        self.plot_container_layout.setContentsMargins(0,0,0,0)
        self.plot_container_layout.addWidget(self.canvas)
        self.plot_container_layout.addWidget(self.pg_canvas)

        self.stacked_widget.addWidget(self.plot_container)
        
        self.bottom_stack = QStackedWidget()
        
        # Qt Table
        self.table = QTableWidget()
        self.table.itemChanged.connect(self.on_table_edit)
        self.bottom_stack.addWidget(self.table)
        
        # Hex Table
        self.hex_table = QTableView()
        self.hex_table.setItemDelegate(HexMapDelegate())
        self.hex_table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.hex_table.customContextMenuRequested.connect(self.show_hex_context_menu)
        # The selectionModel is created when setModel is called later
        self.bottom_stack.addWidget(self.hex_table)
        
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
        
        self.status_lbl = QLabel("Hover over the graph to see values...")
        self.status_lbl.setStyleSheet("background-color: #222; color: #FFF; font-weight: bold; font-size: 14px; padding: 8px; border-radius: 4px;")
        right_panel.addWidget(self.status_lbl)
        
        main_layout.addLayout(right_panel, 4) 

    # --- UI LOGIC ---
    def update_tag_filter_menu(self):
        if not hasattr(self, 'tag_filter_menu'): return
        self.tag_filter_menu.clear()
        all_tags = set()
        
        if not self.data_manager.df.empty and 'Tag' in self.data_manager.df.columns:
            for tag_str in self.data_manager.df['Tag'].fillna(''):
                for t in str(tag_str).split(','):
                    t = t.strip()
                    if t:
                        all_tags.add(t)
                
        for t in sorted(all_tags):
            action = self.tag_filter_menu.addAction(t)
            action.setCheckable(True)
            action.setChecked(t in self.active_tag_filters)
            action.triggered.connect(lambda checked, tag=t: self.on_tag_filter_toggled(tag, checked))

    def on_tag_filter_toggled(self, tag, checked):
        if checked:
            self.active_tag_filters.add(tag)
        else:
            self.active_tag_filters.discard(tag)
        self.update_list()

    def on_map_type_changed(self, idx):
        if idx == 0: new_mode = '3d'
        elif idx == 1: new_mode = '2d'
        elif idx == 2: new_mode = 'tags'
        else: new_mode = 'all'
        
        if new_mode != self.map_mode:
            self.map_mode = new_mode
            if self.btn_main_mode.text() == "Mode: Map Viewer":
                self.btn_hex_plot_mode.setVisible(self.map_mode == 'tags')
            self.load_data()

    def update_list(self):
        self.map_listbox.clear()
        self.filtered_indices = []
        if self.data_manager.df.empty: return
        
        search_term = self.search_box.text().lower()
        
        for idx, row in self.data_manager.df.iterrows():
            mtype = row.get('Map_Type', self.map_mode)
            
            # For 3D and Hexdump Tags, use Map_Z_Addr as the title. For 2D, Curve_Data_Addr
            addr_col = 'Map_Z_Addr' if mtype in ('3d', 'tags') else 'Curve_Data_Addr'
            addr = str(row.get(addr_col, '')).strip()
            tag = str(row.get('Tag', '')).strip()

            # Beautiful label indicating type
            prefix = {"3d": "3D Map", "2d": "2D Crv", "tags": "HexTag"}.get(mtype, "Map")
            
            display_text = f"{prefix} {idx+1}: {addr}"
            if tag:
                display_text += f" [{tag}]"

            term_match = (search_term in addr.lower() or search_term in tag.lower())
            
            tag_match = True
            if self.active_tag_filters:
                row_tags = [t.strip() for t in tag.split(',') if t.strip()]
                for f_tag in self.active_tag_filters:
                    if f_tag not in row_tags:
                        tag_match = False
                        break
                        
            if term_match and tag_match:
                item = QListWidgetItem(display_text)
                
                # Check for modifications
                try:
                    is_modified = False
                    if mtype == '3d':
                        sz_h_row = str(row.get('Wrapper_Addr', '')).strip()
                        cst = self.data_manager.custom_map_settings.get(sz_h_row, {})
                        fmt = cst.get('z_format', self.data_manager.z_format_3d)
                        fc = fmt[-1]
                        bpv = 4 if fc.lower() in ('f','i','l') else (2 if fc.lower() == 'h' else 1)
                        sx, sy = int(row.get('Size_X', 1)), int(row.get('Size_Y', 1))
                        addr_int = int(str(row.get('Map_Z_Addr', '0')).strip(), 16)
                        length = sx * sy * bpv
                        is_modified = self.data_manager.is_map_modified(addr_int, length)
                    elif mtype == '2d':
                        sz_h_row = str(row.get('Wrapper_Addr', '')).strip()
                        cst = self.data_manager.custom_map_settings.get(sz_h_row, {})
                        fmt = cst.get('z_format', self.data_manager.z_format_2d)
                        fc = fmt[-1]
                        bpv = 4 if fc.lower() in ('f','i','l') else (2 if fc.lower() == 'h' else 1)
                        sx = int(row.get('Size_X', 1))
                        addr_int = int(str(row.get('Curve_Data_Addr', '0')).strip(), 16)
                        length = sx * bpv
                        is_modified = self.data_manager.is_map_modified(addr_int, length)
                    if is_modified:
                        item.setForeground(QColor(255, 0, 0))
                except: pass
                
                self.map_listbox.addItem(item)
                self.filtered_indices.append(idx)

        if self.filtered_indices:
            self.sync_listbox_selection()

    def on_list_select(self):
        items = self.map_listbox.selectedIndexes()
        if items:
            visual_idx = items[0].row()
            if visual_idx < len(self.filtered_indices):
                self.data_manager.current_index = self.filtered_indices[visual_idx]
                self.draw_map()

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

    def on_show_original_toggled(self, checked):
        self.data_manager.show_modified = not checked
        self.draw_map()

    def sync_listbox_selection(self):
        if self.data_manager.current_index in self.filtered_indices:
            vis_idx = self.filtered_indices.index(self.data_manager.current_index)
            self.map_listbox.setCurrentRow(vis_idx)

    def toggle_main_mode(self):
        modes = ['Map Viewer', 'Hex Dump']
        current = self.btn_main_mode.text().replace("Mode: ", "")
        idx = modes.index(current)
        new_mode = modes[(idx + 1) % len(modes)]
        self.btn_main_mode.setText(f"Mode: {new_mode}")
        
        self.rebuild_plot_axes()
        
        if new_mode == 'Map Viewer':
            self.btn_toggle.setVisible(True)
            self.btn_hex_plot_toggle.setVisible(False)
            self.btn_hex_plot_mode.setVisible(self.map_mode == 'tags')
            
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
            
            # Hex Dump mode
            self.plot_container.setVisible(self.hex_plot_visible)
            self.bottom_stack.setVisible(True)
            self.bottom_stack.setCurrentIndex(1) # Hex Table
            self.apply_splitter_position()
            
        self.draw_map()

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
        if self.data_manager.df.empty: return
        
        row = self.data_manager.df.iloc[self.data_manager.current_index]
        wrapper_addr_hex = str(row['Wrapper_Addr']).strip()
        custom = getattr(self.data_manager, "custom_map_settings", {}).get(wrapper_addr_hex, {})
        
        dialog = QDialog(self)
        dialog.setWindowTitle(f"Custom Settings for Map: {wrapper_addr_hex}")
        layout = QVBoxLayout(dialog)
        
        def parse_fmt(f_str):
            if not f_str: return "16-bit", ">", False
            endian = "<" if "<" in f_str else ">"
            c = f_str[-1].lower()
            if c == 'f': size = "Float"
            elif c == 'b': size = "8-bit"
            elif c == 'i' or c == 'l': size = "32-bit"
            else: size = "16-bit" # default H/h
            signed = f_str[-1].islower()
            if size == "Float": signed = True
            return size, endian, signed
            
        def build_fmt(size_str, signed, is_little):
            endian = '<' if is_little else '>'
            if size_str == 'Float': char = 'f'
            elif size_str == '8-bit': char = 'b' if signed else 'B'
            elif size_str == '16-bit': char = 'h' if signed else 'H'
            else: char = 'i' if signed else 'I'
            return endian + char

        layout.addWidget(QLabel("<i>Leave empty or uncheck to use global settings.</i>"))

        cb_override = QCheckBox("Enable Custom Settings for this Map")
        cb_override.setChecked(wrapper_addr_hex in getattr(self.data_manager, "custom_map_settings", {}))
        layout.addWidget(cb_override)
        
        frame = QGroupBox("Custom Settings")
        ly_frame = QFormLayout(frame)
        
        glob_z = self.data_manager.z_format_3d if (self.map_mode == '3d' or (self.map_mode == 'tags' and self.hex_plot_mode == '3d')) else self.data_manager.z_format_2d
        glob_ax = self.data_manager.ax_format
        glob_f = self.factor_z_3d if (self.map_mode == '3d' or (self.map_mode == 'tags' and self.hex_plot_mode == '3d')) else self.factor_z_2d
        glob_o = self.offset_z_3d if (self.map_mode == '3d' or (self.map_mode == 'tags' and self.hex_plot_mode == '3d')) else self.offset_z_2d

        z_fmt = custom.get('z_format', glob_z)
        ax_fmt = custom.get('ax_format', glob_ax)
        c_factor = custom.get('factor', glob_f)
        c_offset = custom.get('offset', glob_o)
        
        sizeZ, endZ, signZ = parse_fmt(z_fmt)
        sizeA, endA, signA = parse_fmt('>' + ax_fmt if len(ax_fmt) == 1 else ax_fmt)
        
        cmb_z_size = QComboBox(); cmb_z_size.addItems(["8-bit", "16-bit", "32-bit", "Float"]); cmb_z_size.setCurrentText(sizeZ)
        cmb_a_size = QComboBox(); cmb_a_size.addItems(["8-bit", "16-bit", "32-bit", "Float"]); cmb_a_size.setCurrentText(sizeA)
        cb_endian = QCheckBox("Little Endian (LoHi)"); cb_endian.setChecked(endZ == '<')
        cb_signed = QCheckBox("Signed - Uncheck for Unsigned"); cb_signed.setChecked(signZ)
        
        spin_f = QDoubleSpinBox(); spin_f.setDecimals(5); spin_f.setSingleStep(0.001)
        spin_f.setRange(-10000, 10000); spin_f.setValue(c_factor)
        
        spin_o = QDoubleSpinBox(); spin_o.setDecimals(5); spin_o.setSingleStep(0.001)
        spin_o.setRange(-10000, 10000); spin_o.setValue(c_offset)
        
        ly_frame.addRow("Z / Curve Data Size:", cmb_z_size)
        ly_frame.addRow("Axis Data Size:", cmb_a_size)
        ly_frame.addWidget(cb_endian)
        ly_frame.addWidget(cb_signed)
        ly_frame.addRow("Z / Curve Factor:", spin_f)
        ly_frame.addRow("Z / Curve Offset:", spin_o)

        layout.addWidget(frame)

        def toggle_frame():
            frame.setEnabled(cb_override.isChecked())
        cb_override.toggled.connect(toggle_frame)
        toggle_frame()
        
        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        btns.accepted.connect(dialog.accept)
        btns.rejected.connect(dialog.reject)
        layout.addWidget(btns)
        
        if dialog.exec():
            if cb_override.isChecked():
                new_z = build_fmt(cmb_z_size.currentText(), cb_signed.isChecked(), cb_endian.isChecked())
                new_a = build_fmt(cmb_a_size.currentText(), cb_signed.isChecked(), cb_endian.isChecked())
                if not hasattr(self.data_manager, "custom_map_settings"):
                    self.data_manager.custom_map_settings = {}
                self.data_manager.custom_map_settings[wrapper_addr_hex] = {
                    'z_format': new_z,
                    'ax_format': new_a[-1],
                    'factor': spin_f.value(),
                    'offset': spin_o.value()
                }
            else:
                if hasattr(self.data_manager, "custom_map_settings") and wrapper_addr_hex in self.data_manager.custom_map_settings:
                    del self.data_manager.custom_map_settings[wrapper_addr_hex]
            
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
                
        gb_engine = QGroupBox("Render Engine")
        ly_engine = QHBoxLayout()
        self.rb_mpl = QRadioButton("Matplotlib (Slow, Hover)")
        self.rb_pg = QRadioButton("PyQtGraph (Fast, No Hover)")
        if self.render_engine == 'matplotlib': self.rb_mpl.setChecked(True)
        else: self.rb_pg.setChecked(True)
        ly_engine.addWidget(self.rb_mpl)
        ly_engine.addWidget(self.rb_pg)
        gb_engine.setLayout(ly_engine)
        vbox_f.addWidget(gb_engine)
        
        rb_m1 = QRadioButton("3D Maps")
        rb_m2 = QRadioButton("2D Curves")
        rb_m3 = QRadioButton("Hexdump Tags")
        rb_m4 = QRadioButton("All (Dropdown)")
        
        # We need a new state variable to know if we are in 'All' mode or a forced restriction from settings
        # Let's say if the dropdown is visible, we are in 'All' mode. By default let's use the combo state.
        if self.cmb_map_type.isVisible():
            rb_m4.setChecked(True)
        elif self.map_mode == 'tags':
            rb_m3.setChecked(True)
        elif self.map_mode == '2d':
            rb_m2.setChecked(True)
        else:
            rb_m1.setChecked(True)
            
        ly_mode.addWidget(rb_m1); ly_mode.addWidget(rb_m2); ly_mode.addWidget(rb_m3); ly_mode.addWidget(rb_m4)
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
        le_bin = add_file_row(vbox_f, "BIN File:", self.data_manager.bin_path)
        le_3d = add_file_row(vbox_f, "3D CSV:", self.data_manager.csv_3d_path)
        le_2d = add_file_row(vbox_f, "2D CSV:", self.data_manager.csv_2d_path)
        vbox_f.addStretch()
        tabs.addTab(tab_files, "Files & Mode")
        
        # TAB 2: FORMAT 
        tab_fmt = QWidget()
        vbox_fmt = QVBoxLayout(tab_fmt)
        
        def parse_fmt(f_str):
            if not f_str: return "16-bit", ">", False
            endian = "<" if "<" in f_str else ">"
            c = f_str[-1].lower()
            if c == 'f': size = "Float"
            elif c == 'b': size = "8-bit"
            elif c == 'i' or c == 'l': size = "32-bit"
            else: size = "16-bit" # default H/h
            signed = f_str[-1].islower()
            if size == 'Float': signed = True
            return size, endian, signed

        size3, end3, sign3 = parse_fmt(self.data_manager.z_format_3d)
        size2, end2, sign2 = parse_fmt(self.data_manager.z_format_2d)
        
        # Determine global values (fallback to 3D if they mismatch)
        is_little_endian = (end3 == "<")
        is_signed = sign3

        gb_global = QGroupBox("Global Rules")
        ly_global = QVBoxLayout()
        
        self.cb_endian = QCheckBox("Little Endian (LoHi) - Uncheck for Big Endian (HiLo)")
        self.cb_endian.setChecked(is_little_endian)
        ly_global.addWidget(self.cb_endian)
        
        self.cb_signed = QCheckBox("Signed - Uncheck for Unsigned")
        self.cb_signed.setChecked(is_signed)
        ly_global.addWidget(self.cb_signed)
        
        gb_global.setLayout(ly_global)
        vbox_fmt.addWidget(gb_global)

        gb_sizes = QGroupBox("Data Sizes")
        ly_sizes = QFormLayout()
        
        self.cmb_3d = QComboBox()
        self.cmb_3d.addItems(["8-bit", "16-bit", "32-bit", "Float"])
        self.cmb_3d.setCurrentText(size3)
        ly_sizes.addRow("3D Data Size:", self.cmb_3d)

        self.cmb_2d = QComboBox()
        self.cmb_2d.addItems(["8-bit", "16-bit", "32-bit", "Float"])
        self.cmb_2d.setCurrentText(size2)
        ly_sizes.addRow("2D Data Size:", self.cmb_2d)

        sz_ax_map = {'b': '8-bit', 'h': '16-bit', 'i': '32-bit', 'f': 'Float'}
        sz_a_char = self.data_manager.ax_format.lower() if self.data_manager.ax_format else 'h'
        size_a = sz_ax_map.get(sz_a_char, '16-bit')

        self.cmb_ax = QComboBox()
        self.cmb_ax.addItems(["8-bit", "16-bit", "32-bit", "Float"])
        self.cmb_ax.setCurrentText(size_a)
        ly_sizes.addRow("Axis Size:", self.cmb_ax)
        
        gb_sizes.setLayout(ly_sizes)
        vbox_fmt.addWidget(gb_sizes)

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
        
        self.cb_hl_custom = QCheckBox("Highlight Custom Tags in Hex Mode (Orange)")
        self.cb_hl_custom.setChecked(self.highlight_custom_tags)
        ly_tbl.addWidget(self.cb_hl_custom)
        
        self.cb_hl_custom = QCheckBox("Highlight Custom Tags in Hex Mode (Orange)")
        self.cb_hl_custom.setChecked(self.highlight_custom_tags)
        ly_tbl.addWidget(self.cb_hl_custom)
        
        ly_spark = QHBoxLayout()
        ly_spark.addWidget(QLabel("Sparkline Style:"))
        rb_sp1 = QRadioButton("Bars (WinOLS)")
        rb_sp2 = QRadioButton("Continuous Line")
        if self.sparkline_style == 'Bars': rb_sp1.setChecked(True)
        else: rb_sp2.setChecked(True)
        ly_spark.addWidget(rb_sp1); ly_spark.addWidget(rb_sp2)
        ly_tbl.addLayout(ly_spark)
        
        gb_hex_pos = QGroupBox("Hex Dump Plot Position")
        ly_hex_pos = QHBoxLayout()
        rb_pos_top = QRadioButton("Top")
        rb_pos_right = QRadioButton("Right")
        if self.hex_plot_position == 'top': rb_pos_top.setChecked(True)
        else: rb_pos_right.setChecked(True)
        ly_hex_pos.addWidget(rb_pos_top); ly_hex_pos.addWidget(rb_pos_right)
        gb_hex_pos.setLayout(ly_hex_pos)
        ly_tbl.addWidget(gb_hex_pos)
        
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
            # Update engine
            new_engine = 'matplotlib' if self.rb_mpl.isChecked() else 'pyqtgraph'
            engine_changed = (new_engine != self.render_engine)
            if engine_changed:
                self.render_engine = new_engine

            self.data_manager.bin_path = le_bin.text(); self.data_manager.csv_3d_path = le_3d.text(); self.data_manager.csv_2d_path = le_2d.text()
            
            if rb_m4.isChecked():
                self.cmb_map_type.setVisible(True)
                modes_list = ['3d', '2d', 'tags', 'all']
                if self.cmb_map_type.currentIndex() < len(modes_list):
                    new_mode = modes_list[self.cmb_map_type.currentIndex()]
                else:
                    new_mode = 'all'
            else:
                self.cmb_map_type.setVisible(False)
                if rb_m1.isChecked(): new_mode = '3d'
                elif rb_m2.isChecked(): new_mode = '2d'
                else: new_mode = 'tags'
                
            if new_mode != self.map_mode or getattr(self, 'last_dropdown_mode', None) != self.cmb_map_type.isVisible():
                self.last_dropdown_mode = self.cmb_map_type.isVisible()
                self.map_mode = new_mode
                if self.btn_main_mode.text() == "Mode: Map Viewer":
                    self.btn_hex_plot_mode.setVisible(self.map_mode == 'tags')
                self.load_data() 
            
            is_little = self.cb_endian.isChecked()
            is_signed = self.cb_signed.isChecked()
            endian = '<' if is_little else '>'
            
            def build_fmt(size_str, signed):
                if size_str == 'Float': return 'f'
                elif size_str == '8-bit': char = 'b' if signed else 'B'
                elif size_str == '16-bit': char = 'h' if signed else 'H'
                else: char = 'i' if signed else 'I'
                return char

            char_3d = build_fmt(self.cmb_3d.currentText(), is_signed)
            self.data_manager.z_format_3d = endian + char_3d
            
            char_2d = build_fmt(self.cmb_2d.currentText(), is_signed)
            self.data_manager.z_format_2d = endian + char_2d
            
            char_ax = build_fmt(self.cmb_ax.currentText(), is_signed)
            self.data_manager.ax_format = char_ax
            
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
            self.highlight_custom_tags = self.cb_hl_custom.isChecked()
            self.highlight_custom_tags = self.cb_hl_custom.isChecked()
            self.sparkline_style = 'Bars' if rb_sp1.isChecked() else 'Line'
            
            new_pos = 'top' if rb_pos_top.isChecked() else 'right'
            if new_pos != self.hex_plot_position:
                self.hex_plot_position = new_pos
                if self.btn_main_mode.text() == "Mode: Hex Dump":
                    self.apply_splitter_position()
            
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
            
            if getattr(self.ax, "name", "") == "3d" or getattr(self.ax, "name", "") == "3d":
                self.start_elev = self.ax.elev
                self.start_azim = self.ax.azim
            else:
                self.start_center_x_2d = self.center_x_2d
                self.start_center_y_2d = self.center_y_2d

    def on_mouse_release(self, event):
        self.dragging = False
        if getattr(self.ax, "name", "") == "3d" or getattr(self.ax, "name", "") == "3d":
            self.start_elev = self.ax.elev
            self.start_azim = self.ax.azim

    def on_mouse_move(self, event):
        if self.data_manager.df.empty and self.btn_main_mode.text() != "Mode: Hex Dump": return
        
        if self.dragging:
            if event.x is None or event.y is None: return
            
            if getattr(self.ax, "name", "") == "3d" or getattr(self.ax, "name", "") == "3d":
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
            if (self.map_mode == '3d' or (self.map_mode == 'tags' and self.hex_plot_mode == '3d')) or (self.btn_main_mode.text() == "Mode: Hex Dump" and self.hex_plot_mode == '3d'):
                xs, ys, _ = proj3d.proj_transform(self.x_flat, self.y_flat, self.z_flat, self.ax.get_proj())
                points2d = self.ax.transData.transform(np.column_stack([xs, ys]))
            else:
                points2d = self.ax.transData.transform(np.column_stack([self.x_flat, self.z_flat]))

            dists = (points2d[:, 0] - event.x)**2 + (points2d[:, 1] - event.y)**2
            min_idx = np.argmin(dists)
            
            if dists[min_idx] < 600: 
                self.is_hovering = True
                
                if (self.map_mode == '3d' or (self.map_mode == 'tags' and self.hex_plot_mode == '3d')) or (self.btn_main_mode.text() == "Mode: Hex Dump" and self.hex_plot_mode == '3d'):
                    self.hover_x = self.x_flat[min_idx]
                    self.hover_y = self.y_flat[min_idx]
                    best_z = self.z_flat[min_idx]
                    self.cursor_marker.set_data([self.hover_x], [self.hover_y])
                    self.cursor_marker.set_3d_properties([best_z])
                    rx = self.real_axis_x[self.hover_x]
                    ry = self.real_axis_y[self.hover_y]
                    
                    if self.display_hex:
                        v_hex = best_z if self.apply_factor_to_hex else self.raw_flat[min_idx]
                        fmt = self.data_manager.z_format_3d
                        lbl = f"Target: X = {rx:g}   |   Y = {ry:g}   |   Z (HEX) = {self.data_manager.val_to_hex(v_hex, fmt[-1], fmt[0])}"
                    else:
                        lbl = f"Target: X = {rx:g}   |   Y = {ry:g}   |   Z = {best_z:.2f}"
                else:
                    best_x = self.x_flat[min_idx]
                    best_z = self.z_flat[min_idx]
                    self.cursor_marker.set_data([best_x], [best_z])
                    if self.display_hex:
                        v_hex = best_z if self.apply_factor_to_hex else self.raw_flat[min_idx]
                        fmt = self.data_manager.z_format_2d
                        lbl = f"Target: X = {best_x:g}   |   Z (HEX) = {self.data_manager.val_to_hex(v_hex, fmt[-1], fmt[0])}"
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

    def on_hex_selection_changed(self, current, previous):
        if not current.isValid(): return
        
        if current.column() == self.hex_table_model.data_cols:
            self.status_lbl.setText("Hex Cursor: Row Profile")
            return
            
        bpc = self.hex_table_model.bytes_per_col
        addr = current.row() * 16 + current.column() * bpc
        self.status_lbl.setText(f"Hex Cursor: {addr:08X}  ({addr})")

    def goto_hex_address(self):
        if self.btn_main_mode.text() != "Mode: Hex Dump": return
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
                addr = (start_row + r) * 16 + (start_col + c) * bpc
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

    def update_hex_view(self):
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
            self.hex_table_model = HexTableModel(self.data_manager.bin_data, self.data_manager.map_array, self.data_manager.map_dicts, fmt, self.sparkline_style)
            self.hex_table.setModel(self.hex_table_model)
            self.hex_table.setFont(QFont("Courier New", 10))
            self.hex_table.selectionModel().currentChanged.connect(self.on_hex_selection_changed)
            self.hex_table.selectionModel().selectionChanged.connect(self.update_hex_plot)
        else:
            self.hex_table_model.update_settings(self.data_manager.bin_data, self.data_manager.map_array, self.data_manager.map_dicts, fmt, self.sparkline_style)
            
        bpc = self.hex_table_model.bytes_per_col
        for i in range(self.hex_table_model.data_cols):
            self.hex_table.setColumnWidth(i, 35 if bpc == 1 else (55 if bpc == 2 else 95))
        self.hex_table.setColumnWidth(self.hex_table_model.data_cols, 150)
            
        if not self.data_manager.df.empty:
            addr_col = 'Map_Z_Addr' if (self.map_mode == '3d' or (self.map_mode == 'tags' and self.hex_plot_mode == '3d')) else 'Curve_Data_Addr'
            curr_addr_hex = str(self.data_manager.df.iloc[self.data_manager.current_index].get(addr_col, '0')).strip()
            try:
                addr_int = int(curr_addr_hex, 16)
                idx = self.hex_table_model.index(addr_int // 16, (addr_int % 16) // bpc)
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

    def draw_map(self):
        if self.data_manager.df.empty:
            if self.btn_main_mode.text() == "Mode: Hex Dump":
                self.update_hex_view()
            return
        try:
            row = self.data_manager.df.iloc[self.data_manager.current_index] 
            wrapper_addr_hex = str(row['Wrapper_Addr']).strip()
            custom = getattr(self.data_manager, "custom_map_settings", {}).get(wrapper_addr_hex, {})

            current_type = row.get('Map_Type', self.map_mode)

            # Update toggle button visibility dynamically for 'All' mode
            if self.btn_main_mode.text() == "Mode: Map Viewer":
                self.btn_hex_plot_mode.setVisible(current_type == 'tags' or self.map_mode == 'tags')

            # Auto-rebuild axes if switching between 2D and 3D in 'All' mode    
            is_currently_3d = hasattr(self.ax, 'plot_surface')
            needs_3d = (current_type == '3d' or (current_type == 'tags' and self.hex_plot_mode == '3d'))
            if is_currently_3d != needs_3d:
                self.rebuild_plot_axes()
            current_type = row.get('Map_Type', self.map_mode)
            
            # Auto-rebuild axes if switching between 2D and 3D in 'All' mode    
            is_currently_3d = hasattr(self.ax, 'plot_surface')
            needs_3d = (current_type == '3d' or (current_type == 'tags' and self.hex_plot_mode == '3d'))
            if is_currently_3d != needs_3d:
                self.rebuild_plot_axes()
            current_type = row.get('Map_Type', self.map_mode)
            if current_type == 'tags':
                is_2d = self.hex_plot_mode == '2d'
                raw_matrix, axis_x, axis_y, size_y, size_x, map_addr = self.data_manager.read_map_tags(as_2d=is_2d)
                if is_2d:
                    current_factor = custom.get('factor', self.factor_z_2d)
                    current_offset = custom.get('offset', self.offset_z_2d)
                    current_fmt = custom.get('z_format', self.data_manager.z_format_2d)
                else:
                    current_factor = custom.get('factor', self.factor_z_3d)
                    current_offset = custom.get('offset', self.offset_z_3d)
                    current_fmt = custom.get('z_format', self.data_manager.z_format_3d)
            elif current_type == '3d':
                raw_matrix, axis_x, axis_y, size_y, size_x, map_addr = self.data_manager.read_map_3d()
                current_factor = custom.get('factor', self.factor_z_3d)
                current_offset = custom.get('offset', self.offset_z_3d)
                current_fmt = custom.get('z_format', self.data_manager.z_format_3d)
            else:
                raw_matrix, axis_x, _, size_y, size_x, map_addr = self.data_manager.read_map_2d()
                current_factor = custom.get('factor', self.factor_z_2d)
                current_offset = custom.get('offset', self.offset_z_2d)
                current_fmt = custom.get('z_format', self.data_manager.z_format_2d)
                
            matrix_z = (raw_matrix * current_factor) + current_offset
            
            clean_axis_x = [str(round(v, 2)).rstrip('0').rstrip('.') for v in axis_x]
            if (current_type == '3d' or (current_type == 'tags' and self.hex_plot_mode == '3d')):
                clean_axis_y = [str(round(v, 2)).rstrip('0').rstrip('.') for v in axis_y]
                self.real_axis_y = axis_y
            
            self.real_axis_x = axis_x

            self.map_size_x = size_x
            self.map_size_y = size_y
            self.z_min = matrix_z.min()
            self.z_max = matrix_z.max()

            # Axis Tags logic
            axis_x_addr = str(row.get('Axis_X_Addr', '')).strip().upper()
            x_tag = " ".join(self.data_manager.tags.get(axis_x_addr, {}).get("tags", [])) if axis_x_addr and axis_x_addr not in ('0', '0X0', '00000000') else ""
            self.x_label_str = f"X Axis [{x_tag}]" if x_tag else "X Axis"

            if (current_type == '3d' or (current_type == 'tags' and self.hex_plot_mode == '3d')):
                axis_y_addr = str(row.get('Axis_Y_Addr', '')).strip().upper()
                y_tag = " ".join(self.data_manager.tags.get(axis_y_addr, {}).get("tags", [])) if axis_y_addr and axis_y_addr not in ('0', '0X0', '00000000') else ""
                self.y_label_str = f"Y Axis [{y_tag}]" if y_tag else "Y Axis"
            else:
                self.y_label_str = "Y Axis"

            map_addr_col = 'Map_Z_Addr' if (current_type == '3d' or (current_type == 'tags' and self.hex_plot_mode == '3d')) else 'Curve_Data_Addr'
            m_addr = str(row.get(map_addr_col, '0')).strip().upper()
            m_tag = " ".join(self.data_manager.tags.get(m_addr, {}).get("tags", []))
            self.z_label_3d_str = f"Z Data [{m_tag}]" if m_tag else "Z Data"
            self.z_label_2d_str = f"Curve Data [{m_tag}]" if m_tag else "Curve Data"

            if self.data_manager.current_map_addr != map_addr:
                self.data_manager.current_map_addr = map_addr
                
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
            
            title = f"Map {self.data_manager.current_index + 1}/{self.data_manager.total_maps} | Addr: {map_addr} | Z: {current_fmt} | Factor: {current_factor}"
            self.lbl_title.setText(title)

            if self.btn_main_mode.text() == "Mode: Hex Dump":
                self.update_hex_view()
                self.update_hex_plot()
            else:
                if self.view_mode in ('plot', 'split'):
                    is_pg = (self.render_engine == 'pyqtgraph')
                    self.canvas.setVisible(not is_pg)
                    self.pg_canvas.setVisible(is_pg)

                    if is_pg:
                        if (current_type == '3d' or (current_type == 'tags' and self.hex_plot_mode == '3d')):
                            x_grid = np.arange(size_x)
                            y_grid = np.arange(size_y)
                            self.pg_canvas.draw_3d(x_grid, y_grid, matrix_z, clean_axis_x, clean_axis_y)
                        else:
                            self.pg_canvas.draw_2d(axis_x, matrix_z)
                    else:
                        self.ax.clear()

                        if (current_type == '3d' or (current_type == 'tags' and self.hex_plot_mode == '3d')):
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

                            self.ax.set_xlabel('\n' + self.x_label_str, labelpad=12)
                            self.ax.set_ylabel('\n' + self.y_label_str, labelpad=12)
                            self.ax.set_zlabel(self.z_label_3d_str, labelpad=12)

                            self.ax.invert_yaxis()
                            try: self.ax.set_box_aspect((2.5, 2.0, 0.6))
                            except: pass

                            self.ax.view_init(elev=self.start_elev, azim=self.start_azim)
                            self.apply_3d_zoom()

                        elif (current_type == '2d' or (current_type == 'tags' and self.hex_plot_mode == '2d')):
                            self.x_flat = axis_x
                            self.z_flat = matrix_z
                            self.raw_flat = raw_matrix

                            self.ax.plot(axis_x, matrix_z, marker='o', color='b', linewidth=2, markersize=5)
                            self.cursor_marker, = self.ax.plot([], [], marker='o', color='red', markersize=8, zorder=10)
                            self.cursor_marker.set_visible(False)

                            self.ax.set_xlabel(self.x_label_str)
                            self.ax.set_ylabel(self.z_label_2d_str)
                            self.ax.grid(True, linestyle='--', alpha=0.7)
                            self.apply_2d_zoom()

                        self.canvas.draw_idle()

            if self.view_mode in ('table', 'split'):
                self.is_updating_table = True
                self.table.clear()
                self.table.setRowCount(size_y)

                # Sum +1 for the Sparkline column
                self.table.setColumnCount(size_x + 1)

                headers = clean_axis_x + ["Profile"]
                self.table.setHorizontalHeaderLabels(headers)

                # Calculate the global min and max for proper scaling of green bars
                raw_min = raw_matrix.min()
                raw_max = raw_matrix.max()

                f_char = current_fmt[-1].lower()
                if f_char == 'f': bpv = 4
                elif f_char == 'h': bpv = 2
                elif f_char in ('i', 'l'): bpv = 4
                else: bpv = 1
                base_addr = int(map_addr, 16)

                if (current_type == '3d' or (current_type == 'tags' and self.hex_plot_mode == '3d')):
                    self.table.setVerticalHeaderLabels(clean_axis_y)
                    for i in range(size_y):
                        for j in range(size_x):
                            if self.display_hex:
                                v = matrix_z[i, j] if self.apply_factor_to_hex else raw_matrix[i, j]
                                val_str = self.data_manager.val_to_hex(v, current_fmt[-1], current_fmt[0])
                            else:
                                val_str = f"{matrix_z[i, j]:.2f}"

                            item = QTableWidgetItem(val_str)
                            item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                            if getattr(self.data_manager, 'show_modified', True) and self.data_manager._modified_bin_data:
                                cell_addr = base_addr + (i * size_x + j) * bpv
                                if self.data_manager._bin_data_cache[cell_addr:cell_addr+bpv] != self.data_manager._modified_bin_data[cell_addr:cell_addr+bpv]:
                                    item.setForeground(QColor(255, 0, 0))

                            if current_type != 'tags':
                                item.setData(Qt.ItemDataRole.UserRole, {
                                    "address": base_addr + (i * size_x + j) * bpv,
                                    "fmt_char": current_fmt[-1],
                                    "endian": current_fmt[0],
                                    "factor": current_factor,
                                    "offset": current_offset,
                                    "apply_factor_to_hex": self.apply_factor_to_hex,
                                    "display_hex": self.display_hex
                                })
                            else:
                                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)

                            self.table.setItem(i, j, item)

                        # Insert Sparkline in the last column
                        spark = SparklineWidget(raw_matrix[i, :], raw_min, raw_max, self.sparkline_style)
                        self.table.setCellWidget(i, size_x, spark)
                else:
                    self.table.setVerticalHeaderLabels(["Curve Data"])
                    for j in range(size_x):
                        if self.display_hex:
                            v = matrix_z[j] if self.apply_factor_to_hex else raw_matrix[j]
                            val_str = self.data_manager.val_to_hex(v, current_fmt[-1], current_fmt[0])
                        else:
                            val_str = f"{matrix_z[j]:.2f}"

                        item = QTableWidgetItem(val_str)
                        item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                        if getattr(self.data_manager, 'show_modified', True) and self.data_manager._modified_bin_data:
                            cell_addr = base_addr + (j) * bpv
                            if self.data_manager._bin_data_cache[cell_addr:cell_addr+bpv] != self.data_manager._modified_bin_data[cell_addr:cell_addr+bpv]:
                                item.setForeground(QColor(255, 0, 0))

                        if current_type != 'tags':
                            item.setData(Qt.ItemDataRole.UserRole, {
                                "address": base_addr + (j) * bpv,
                                "fmt_char": current_fmt[-1],
                                "endian": current_fmt[0],
                                "factor": current_factor,
                                "offset": current_offset,
                                "apply_factor_to_hex": self.apply_factor_to_hex,
                                "display_hex": self.display_hex
                            })
                        else:
                            item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)

                        self.table.setItem(0, j, item)

                    # Insert Sparkline 2D
                    spark = SparklineWidget(raw_matrix, raw_min, raw_max, self.sparkline_style)
                    self.table.setCellWidget(0, size_x, spark)

                self.table.resizeColumnsToContents()
                self.table.setColumnWidth(size_x, 150)
                self.is_updating_table = False

        except Exception as e:
            self.is_updating_table = False
            if self.view_mode in ('plot', 'split'):
                self.ax.clear()
                if hasattr(self.ax, 'text2D'):
                    self.ax.text2D(0.5, 0.5, f"Error:\n{str(e)}", transform=self.ax.transAxes, ha='center', color='red')
                else:
                    self.ax.text(0.5, 0.5, f"Error:\n{str(e)}", transform=self.ax.transAxes, ha='center', color='red')
                self.canvas.draw_idle()
            if self.view_mode in ('table', 'split'):
                self.table.clear()

    def show_hex_context_menu(self, pos):
        if self.btn_main_mode.text() != "Mode: Hex Dump": return
        idx = self.hex_table.indexAt(pos)
        if not idx.isValid(): return

        bpc = self.hex_table_model.bytes_per_col
        if idx.column() == self.hex_table_model.data_cols: return
        addr = idx.row() * 16 + idx.column() * bpc

        menu = QMenu(self)
        action_tag = menu.addAction("Tag Selection/Map...")

        action = menu.exec(self.hex_table.viewport().mapToGlobal(pos))
        if action == action_tag:
            indexes = self.hex_table.selectionModel().selectedIndexes()
            length = bpc

            addresses = []
            for ix in indexes:
                if ix.column() < self.hex_table_model.data_cols:
                    addresses.append(ix.row() * 16 + ix.column() * bpc)

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
                    self.load_data()
                else:
                    self.update_list()
                
                if hasattr(self.data_manager, 'current_map_addr') and self.data_manager.current_map_addr == base_addr_hex:
                    self.sync_listbox_selection()
                    
                self.update_hex_view()
    def edit_specific_tag(self, target):
        if self.data_manager.df.empty: return
        row = self.data_manager.df.iloc[self.data_manager.current_index]        
        
        if target == 'wrapper':
            addr_col = 'Wrapper_Addr'
            title_prefix = "Map"
        elif target == 'z':
            addr_col = 'Map_Z_Addr' if (self.map_mode == '3d' or (self.map_mode == 'tags' and self.hex_plot_mode == '3d')) else 'Curve_Data_Addr'
            title_prefix = "Z Data"
        elif target == 'x':
            addr_col = 'Axis_X_Addr'
            title_prefix = "X Axis"
        elif target == 'y':
            addr_col = 'Axis_Y_Addr'
            title_prefix = "Y Axis"
            if self.map_mode != '3d': return
            
        if addr_col not in row or not str(row[addr_col]).strip():
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
                QMessageBox.information(self, "Success", "Project loaded successfully.")
            else:
                QMessageBox.critical(self, "Error", f"Could not load project:\n{err}")


