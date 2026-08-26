"""Main application window.

Holds UI state as explicit enums (see :mod:`viewer.core.state`) and delegates
list handling, rendering and mouse interaction to the managers. Widgets render
state; they never store it.
"""

import os

import matplotlib.pyplot as plt
import numpy as np
from PyQt6.QtCore import QEvent, Qt, QTimer
from PyQt6.QtGui import QColor, QFont, QKeySequence, QShortcut
from PyQt6.QtWidgets import (
    QApplication,
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QInputDialog,
    QMainWindow,
    QMenu,
    QMessageBox,
    QSplitter,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from ..core import formats
from ..core.data_manager import BinaryUnavailable, DataManager, parse_address
from ..core.integrity import CHECKSUM_WARNING
from ..core.state import (
    AppMode,
    CompareMode,
    HexPlotPosition,
    MapMode,
    PlotDim,
    RotationMode,
    SparklineStyle,
    ViewMode,
)
from .components.hex_table_model import HexTableModel
from .dialogs.tag_editor_dialog import TagEditorDialog
from .managers.map_list_manager import MapListManager
from .managers.map_renderer import MapRenderer
from .managers.mouse_events_manager import MouseEventsManager
from .panels.table_view_widget import HEX_TABLE_PAGE, MAP_TABLE_PAGE

#: Delay before a search-box keystroke rebuilds the list. Rebuilding is O(rows)
#: and, with the axis filter on, decodes two axes per row -- roughly 7,700
#: unpacks over the 3,876-row candidate CSV. Debouncing keeps typing responsive.
SEARCH_DEBOUNCE_MS = 200

CUSTOM_TAG_COLOR = (255, 165, 0)


class DensoViewerApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.data_manager = DataManager()
        self.map_renderer = MapRenderer(self)
        self.map_list_manager = MapListManager(self)
        self.mouse_events_manager = MouseEventsManager(self)

        self.setWindowTitle("Denso Map Viewer")
        self.resize(1400, 850)

        # --- Application state -------------------------------------------
        self.app_mode = AppMode.MAP_VIEWER
        self.map_mode = MapMode.THREE_D
        self.view_mode = ViewMode.PLOT
        self.hex_plot_dim = PlotDim.D3
        self.compare_mode = CompareMode.NORMAL
        self.rot_mode = RotationMode.Z_ONLY
        self.sparkline_style = SparklineStyle.BARS
        self.hex_plot_position = HexPlotPosition.TOP
        self.render_engine = "matplotlib"

        self.is_updating_table = False
        self.display_hex = False
        self.apply_factor_to_hex = False
        self.highlight_3d = True
        self.highlight_2d = True
        self.highlight_custom_tags = True
        self.hex_row_width = 16
        self.hex_plot_visible = True
        self.map_type_dropdown_visible = True
        self.active_tag_filters = set()
        self.filtered_indices = []
        self.color_map = None

        self.factor_z_3d = 0.0025
        self.offset_z_3d = 0.0
        self.factor_z_2d = 1.0
        self.offset_z_2d = 0.0

        # --- Camera / hover tracking -------------------------------------
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

        self.reference_matrix = None
        self.reference_axis_x = None
        self.reference_axis_y = None
        self.reference_size_x = 0
        self.reference_size_y = 0

        self._search_timer = QTimer(self)
        self._search_timer.setSingleShot(True)
        self._search_timer.setInterval(SEARCH_DEBOUNCE_MS)
        self._search_timer.timeout.connect(self.update_list)

        self.init_ui()
        self.data_manager.load_dtc_csv()
        self._startup_binary_check()
        self.load_data()

        QApplication.instance().installEventFilter(self)

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def closeEvent(self, event):
        plt.close("all")
        super().closeEvent(event)

    def eventFilter(self, obj, event):
        wheel_over_canvas = (
            event.type() == QEvent.Type.Wheel
            and self.view_mode is ViewMode.PLOT
            and getattr(self, "canvas", None) is not None
            and self.canvas.underMouse()
        )
        if wheel_over_canvas:
            self.canvas.wheelEvent(event)
            return True
        return super().eventFilter(obj, event)

    def _startup_binary_check(self):
        """Say so at launch when the calibration binary is missing.

        The default binary lives in a separate private repository, so a fresh
        clone legitimately has no image. Silently showing an empty viewer sent
        people hunting for a bug that was not there.
        """
        ok, message = self.data_manager.load_binary()
        if ok:
            return
        self.status_lbl.setText(f"No binary loaded — {message}")
        QMessageBox.information(
            self,
            "No calibration binary",
            f"{message}\n\n"
            "The map list and hex view need a firmware image.\n"
            "Load one from ⚙ Global Settings → BIN File, or clone the research "
            "repository into research/ if you have access to it.",
        )

    # ------------------------------------------------------------------
    # Data flow
    # ------------------------------------------------------------------

    def load_data(self, auto_scroll=True):
        success, message = self.data_manager.load_csv(
            self.map_mode.value, potential_mode=self.app_mode is AppMode.POTENTIAL_MAPS
        )

        if not success:
            self.map_listbox.clear()
            self.filtered_indices = []
            self.status_lbl.setText(message)
            self.rebuild_plot_axes()
            self.map_renderer.clear(message)
            return

        if message:
            self.status_lbl.setText(message)

        self.update_tag_filter_menu()
        self.update_list()
        self.rebuild_plot_axes()
        self.draw_map(auto_scroll=auto_scroll)

    def current_row(self):
        return self.data_manager.current_row()

    def row_is_3d(self, row):
        """Whether a row should be drawn as a surface rather than a curve."""
        if row is None:
            return self.map_mode is not MapMode.TWO_D
        map_type = row.get("Map_Type", "3d")
        if map_type == "tags":
            return self.hex_plot_dim is PlotDim.D3
        return map_type == "3d"

    # ------------------------------------------------------------------
    # Plot scaffolding
    # ------------------------------------------------------------------

    def _sync_3d_axes(self, *_args, **_kwargs):
        if not hasattr(self, "ax") or not hasattr(self, "ax2"):
            return
        if self.ax.elev != self.ax2.elev or self.ax.azim != self.ax2.azim:
            self.ax2.view_init(elev=self.ax.elev, azim=self.ax.azim)
            self.canvas.draw_idle()

    def rebuild_plot_axes(self):
        """Recreate the matplotlib axes for the current dimensionality/layout."""
        self.fig.clf()

        if self.app_mode is AppMode.HEX_DUMP:
            is_3d = self.hex_plot_dim is PlotDim.D3
            is_twin = False
        else:
            is_3d = self.row_is_3d(self.current_row())
            is_twin = self.compare_mode.is_twin

        if hasattr(self, "ax2"):
            del self.ax2

        if is_3d:
            if is_twin:
                self.ax = self.fig.add_subplot(121, projection="3d")
                self.ax2 = self.fig.add_subplot(122, projection="3d")
                self.ax2.set_navigate(False)
                self._disable_rotation(self.ax2)
            else:
                self.ax = self.fig.add_subplot(111, projection="3d")
            self.ax.set_navigate(False)
            self._disable_rotation(self.ax)
        else:
            self.ax = self.fig.add_subplot(111)
            self.ax.set_navigate(False)

        self.canvas.draw_idle()

    @staticmethod
    def _disable_rotation(axes):
        # Removed from matplotlib 3.10; the app drives rotation itself either way.
        disable = getattr(axes, "disable_mouse_rotation", None)
        if callable(disable):
            disable()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def init_ui(self):
        from .panels.left_panel_widget import LeftPanelWidget
        from .panels.plot_container_widget import PlotContainerWidget
        from .panels.table_view_widget import TableViewWidget
        from .panels.toolbar_widget import ToolbarWidget
        from .panels.top_controls_widget import TopControlsWidget

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)

        self.left_panel_widget = LeftPanelWidget(self)
        main_layout.addWidget(self.left_panel_widget, 1)

        right_panel = QVBoxLayout()
        self.top_controls_widget = TopControlsWidget(self)
        right_panel.addWidget(self.top_controls_widget)

        self.stacked_widget = QSplitter(Qt.Orientation.Vertical)
        self.plot_container = PlotContainerWidget(self)
        self.stacked_widget.addWidget(self.plot_container)
        self.bottom_stack = TableViewWidget(self)
        self.stacked_widget.addWidget(self.bottom_stack)
        self.stacked_widget.setSizes([600, 400])
        right_panel.addWidget(self.stacked_widget, 1)

        self.shortcut_g = QShortcut(QKeySequence("G"), self)
        self.shortcut_g.activated.connect(self.goto_hex_address)

        self.toolbar_widget = ToolbarWidget(self)
        right_panel.addWidget(self.toolbar_widget)

        main_layout.addLayout(right_panel, 4)

        self._sync_mode_widgets()

    # ------------------------------------------------------------------
    # Mode switching
    # ------------------------------------------------------------------

    def toggle_main_mode(self):
        self.set_app_mode(self.app_mode.next)

    def set_app_mode(self, mode):
        """Switch top-level mode and re-sync every dependent widget.

        Replaces the old approach of writing the *previous* mode into the button
        label and calling the cycle function so it landed on the wanted one.
        """
        if mode is self.app_mode:
            self._sync_mode_widgets()
            return
        self.app_mode = mode
        self._sync_mode_widgets()
        self.rebuild_plot_axes()
        self.load_data()

    def _sync_mode_widgets(self):
        """Make every widget reflect the current state. Single source of truth."""
        self.btn_main_mode.setText(self.app_mode.label)
        self.btn_toggle.setText(self.view_mode.label)
        self.btn_hex_plot_mode.setText(self.hex_plot_dim.label)
        self.btn_hex_plot_toggle.setText("Hex Plot: ON" if self.hex_plot_visible else "Hex Plot: OFF")
        self.cmb_map_type.setVisible(self.map_type_dropdown_visible)

        in_hex = self.app_mode is AppMode.HEX_DUMP
        self.btn_toggle.setVisible(not in_hex)
        self.btn_hex_plot_toggle.setVisible(in_hex)
        self.spin_hex_cols.setVisible(in_hex)
        self.btn_edit_dims.setVisible(self.map_mode in (MapMode.TAGS, MapMode.ALL))

        if in_hex:
            self.btn_hex.setVisible(False)
            self.btn_hex_plot_mode.setVisible(self.hex_plot_visible)
            self.plot_container.setVisible(self.hex_plot_visible)
            self.bottom_stack.setVisible(True)
            self.bottom_stack.setCurrentIndex(HEX_TABLE_PAGE)
            self.apply_splitter_position()
        else:
            self.btn_hex_plot_mode.setVisible(
                self.map_mode is MapMode.TAGS and self.app_mode is not AppMode.POTENTIAL_MAPS
            )
            self.stacked_widget.setOrientation(Qt.Orientation.Vertical)
            self.stacked_widget.insertWidget(0, self.plot_container)
            self.stacked_widget.insertWidget(1, self.bottom_stack)
            self.stacked_widget.setSizes([600, 400])

            self.plot_container.setVisible(self.view_mode.shows_plot)
            self.bottom_stack.setVisible(self.view_mode.shows_table)
            self.btn_hex.setVisible(self.view_mode.shows_table)
            if self.view_mode.shows_table:
                self.bottom_stack.setCurrentIndex(MAP_TABLE_PAGE)

    def set_map_mode(self, mode):
        if mode is self.map_mode:
            return
        self.map_mode = mode
        self._sync_mode_widgets()
        self.load_data()

    def toggle_view(self):
        self.view_mode = self.view_mode.next
        self._sync_mode_widgets()
        self.draw_map()

    def toggle_hex(self):
        self.display_hex = not self.display_hex
        self.btn_hex.setStyleSheet("background-color: #ffcccc;" if self.display_hex else "")
        self.draw_map()

    def toggle_hex_plot(self):
        self.hex_plot_visible = not self.hex_plot_visible
        self._sync_mode_widgets()
        if self.app_mode is AppMode.HEX_DUMP and self.hex_plot_visible:
            self.update_hex_plot()

    def toggle_hex_plot_mode(self):
        self.hex_plot_dim = self.hex_plot_dim.other
        self._sync_mode_widgets()
        self.rebuild_plot_axes()
        if self.app_mode is AppMode.HEX_DUMP:
            if self.hex_plot_visible:
                self.update_hex_plot()
        else:
            self.draw_map()

    def apply_splitter_position(self):
        if self.app_mode is not AppMode.HEX_DUMP:
            return
        if self.hex_plot_position is HexPlotPosition.TOP:
            self.stacked_widget.setOrientation(Qt.Orientation.Vertical)
            self.stacked_widget.insertWidget(0, self.plot_container)
            self.stacked_widget.insertWidget(1, self.bottom_stack)
            self.stacked_widget.setSizes([600, 400])
        else:
            self.stacked_widget.setOrientation(Qt.Orientation.Horizontal)
            self.stacked_widget.insertWidget(0, self.bottom_stack)
            self.stacked_widget.insertWidget(1, self.plot_container)
            self.stacked_widget.setSizes([400, 600])

    def on_hex_cols_changed(self, value):
        self.hex_row_width = value
        if self.app_mode is AppMode.HEX_DUMP:
            self.update_hex_view()

    # ------------------------------------------------------------------
    # List delegation
    # ------------------------------------------------------------------

    def request_list_update(self):
        """Debounced entry point used by the search box."""
        self._search_timer.start()

    def update_tag_filter_menu(self):
        self.map_list_manager.update_tag_filter_menu()

    def on_tag_filter_toggled(self, tag, checked):
        self.map_list_manager.on_tag_filter_toggled(tag, checked)

    def on_map_type_changed(self, idx):
        self.set_map_mode(MapMode.from_combo_index(idx))

    def update_list(self):
        self.map_list_manager.update_list()

    def on_list_select(self):
        self.map_list_manager.on_list_select()

    def sync_listbox_selection(self):
        self.map_list_manager.sync_listbox_selection()

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

    # ------------------------------------------------------------------
    # Comparison
    # ------------------------------------------------------------------

    def on_compare_mode_changed(self, idx):
        mode = CompareMode.from_index(idx)
        if mode.uses_external_bin and not self.data_manager.reference_bin_data:
            QMessageBox.warning(
                self,
                "No External Reference",
                "Load an external reference binary first with 'Load Ref. Bin'.\n"
                "Falling back to comparison against the original binary.",
            )
            mode = CompareMode.DIFF_ORIGINAL if mode.subtracts else CompareMode.TWIN_ORIGINAL
            self.cmb_compare_mode.blockSignals(True)
            self.cmb_compare_mode.setCurrentIndex(int(mode))
            self.cmb_compare_mode.blockSignals(False)

        if mode.uses_reference_map and self.reference_matrix is None:
            QMessageBox.warning(
                self,
                "No Reference Map",
                "Select a map and press 'Set Reference Map' before comparing against it.",
            )

        self.compare_mode = mode
        self.data_manager.show_modified = mode.shows_modified_bin
        self.rebuild_plot_axes()
        self.draw_map()

    def set_reference_map(self):
        row = self.current_row()
        if row is None:
            QMessageBox.information(self, "No Map", "Select a map first.")
            return
        try:
            matrix, axis_x, axis_y, size_y, size_x, _ = self.data_manager.read_map(
                row, as_2d=not self.row_is_3d(row)
            )
        except (ValueError, BinaryUnavailable) as exc:
            QMessageBox.warning(self, "Error", f"Failed to set reference:\n{exc}")
            return

        self.reference_matrix = matrix.copy()
        self.reference_axis_x = np.array(axis_x, copy=True)
        self.reference_axis_y = np.array(axis_y, copy=True)
        self.reference_size_x = size_x
        self.reference_size_y = size_y
        QMessageBox.information(self, "Reference Set", f"Reference map set (shape {matrix.shape}).")
        if self.compare_mode.uses_reference_map:
            self.draw_map()

    # ------------------------------------------------------------------
    # Dialogs
    # ------------------------------------------------------------------

    def open_custom_map_settings(self):
        from .dialogs.custom_map_settings_dialog import CustomMapSettingsDialog

        CustomMapSettingsDialog(self)

    def open_settings(self):
        from .dialogs.settings_dialog import SettingsDialog

        SettingsDialog(self)

    def show_dtc_tracker(self):
        from .dialogs.dtc_tracker_dialog import DtcTrackerDialog

        row = self.current_row()
        info = self.data_manager.dtc_for(row) if row is not None else None
        if info:
            DtcTrackerDialog(info, self).exec()

    # ------------------------------------------------------------------
    # Mouse delegation
    # ------------------------------------------------------------------

    def apply_3d_zoom(self):
        self.mouse_events_manager.apply_3d_zoom()

    def apply_2d_zoom(self):
        self.mouse_events_manager.apply_2d_zoom()

    def on_mouse_press(self, event):
        self.mouse_events_manager.on_mouse_press(event)

    def on_mouse_release(self, event):
        self.mouse_events_manager.on_mouse_release(event)

    def on_mouse_move(self, event):
        self.mouse_events_manager.on_mouse_move(event)

    # ------------------------------------------------------------------
    # Hex view
    # ------------------------------------------------------------------

    def hex_address_at(self, row, column):
        """Byte offset of a hex-table cell."""
        return row * self.hex_row_width + column * self.hex_table_model.bytes_per_col

    def on_hex_selection_changed(self, current, _previous):
        if not current.isValid():
            return
        if current.column() == self.hex_table_model.data_cols:
            self.status_lbl.setText("Hex Cursor: Row Profile")
            return
        address = self.hex_address_at(current.row(), current.column())
        self.status_lbl.setText(f"Hex Cursor: {address:08X}  ({address})")

    def goto_hex_address(self):
        if self.app_mode is not AppMode.HEX_DUMP:
            return
        text, ok = QInputDialog.getText(self, "Goto Address", "Enter Hex Address:")
        if not (ok and text):
            return
        try:
            address = int(text.strip().replace("0x", "").replace("0X", ""), 16)
        except ValueError:
            QMessageBox.warning(self, "Invalid Address", f"'{text}' is not a hexadecimal number.")
            return
        if not hasattr(self, "hex_table_model"):
            return
        bytes_per_col = self.hex_table_model.bytes_per_col
        index = self.hex_table_model.index(
            address // self.hex_row_width, (address % self.hex_row_width) // bytes_per_col
        )
        if not index.isValid():
            QMessageBox.warning(self, "Out of Range", f"0x{address:X} is beyond the end of the binary.")
            return
        self.hex_table.scrollTo(index, QTableView.ScrollHint.PositionAtTop)
        self.hex_table.setCurrentIndex(index)

    def _hex_selection_bounds(self):
        """``(start_row, end_row, start_col, end_col)`` for the hex plot, or None."""
        model = self.hex_table_model
        selection = self.hex_table.selectionModel()
        indexes = [i for i in selection.selectedIndexes() if i.column() < model.data_cols]

        if len(indexes) > 1:
            return (
                min(i.row() for i in indexes),
                max(i.row() for i in indexes),
                min(i.column() for i in indexes),
                max(i.column() for i in indexes),
            )

        if indexes:
            start_row = indexes[0].row()
        else:
            current = selection.currentIndex()
            if not current.isValid():
                return None
            start_row = current.row()
        return start_row, start_row + 15, 0, model.data_cols - 1

    def update_hex_plot(self, *_args):
        if self.app_mode is not AppMode.HEX_DUMP or not self.hex_plot_visible:
            return
        # The model only exists once the hex view has been built at least once.
        if getattr(self, "hex_table_model", None) is None:
            return
        bounds = self._hex_selection_bounds()
        if bounds is None:
            return
        start_row, end_row, start_col, end_col = bounds

        size_y = end_row - start_row + 1
        size_x = end_col - start_col + 1
        if size_y <= 0 or size_x <= 0:
            return

        model = self.hex_table_model
        data = self.data_manager.bin_data
        fmt = model.fmt
        bytes_per_col = model.bytes_per_col

        is_3d = self.hex_plot_dim is PlotDim.D3
        factor = self.factor_z_3d if is_3d else self.factor_z_2d
        offset = self.offset_z_3d if is_3d else self.offset_z_2d

        raw_matrix = np.zeros((size_y, size_x))
        for r in range(size_y):
            address = self.hex_address_at(start_row + r, start_col)
            available = max(0, min(size_x, (len(data) - address) // bytes_per_col))
            if available <= 0:
                continue
            try:
                raw_matrix[r, :available] = formats.unpack_array(data, fmt, available, address)
            except ValueError:
                continue
        matrix_z = raw_matrix * factor + offset

        self.ax.clear()
        cursor_addr = self.hex_address_at(start_row, start_col)
        self.lbl_title.setText(
            f"Hex Plot ({self.hex_plot_dim.value.upper()}) | Cursor: {cursor_addr:08X} | "
            f"Area: {size_x} col x {size_y} row"
        )

        if is_3d:
            if size_x > 1 and size_y > 1:
                self._draw_hex_surface(matrix_z, raw_matrix, size_x, size_y)
            else:
                self.ax.text2D(
                    0.5,
                    0.5,
                    "Select at least a 2x2 area in the hex table for a 3D plot",
                    transform=self.ax.transAxes,
                    ha="center",
                    color="red",
                )
                self.x_flat = []
        else:
            self._draw_hex_curve(matrix_z, raw_matrix)

        marker_args = ([0], [0], [0]) if is_3d else ([0], [0])
        self.cursor_marker, = self.ax.plot(*marker_args, marker="o", color="red", markersize=8, zorder=10)
        self.cursor_marker.set_visible(False)
        self.canvas.draw_idle()

    def _draw_hex_surface(self, matrix_z, raw_matrix, size_x, size_y):
        grid_x, grid_y = np.meshgrid(np.arange(size_x), np.arange(size_y))
        self.x_flat = grid_x.flatten()
        self.y_flat = grid_y.flatten()
        self.z_flat = matrix_z.flatten()
        self.raw_flat = raw_matrix.flatten()
        self.real_axis_x = np.arange(size_x)
        self.real_axis_y = np.arange(size_y)

        self.ax.plot_surface(grid_x, grid_y, matrix_z, cmap="jet", edgecolor="k", linewidth=0.3, alpha=0.9)
        self.ax.invert_yaxis()
        self._set_box_aspect(self.ax)
        self.ax.view_init(elev=self.start_elev, azim=self.start_azim)

        self.map_size_x = size_x
        self.map_size_y = size_y
        self.z_min = matrix_z.min()
        self.z_max = matrix_z.max()
        self.cam_zoom = 1.0
        self.center_x = (size_x - 1) / 2.0
        self.center_y = (size_y - 1) / 2.0

    def _draw_hex_curve(self, matrix_z, raw_matrix):
        flat_z = matrix_z.flatten()
        self.x_flat = np.arange(len(flat_z))
        self.z_flat = flat_z
        self.raw_flat = raw_matrix.flatten()
        self.ax.plot(self.x_flat, flat_z, marker="o", color="b", linewidth=2, markersize=5)
        self.ax.grid(True, linestyle="--", alpha=0.7)

        x_margin = max(1, len(flat_z) * 0.05)
        y_margin = max(1, (flat_z.max() - flat_z.min()) * 0.05)
        self.abs_xlim = (-x_margin, len(flat_z) - 1 + x_margin)
        self.abs_ylim = (flat_z.min() - y_margin, flat_z.max() + y_margin)
        self.cam_zoom_2d = 1.0
        self.center_x_2d = sum(self.abs_xlim) / 2.0
        self.center_y_2d = sum(self.abs_ylim) / 2.0

    @staticmethod
    def _set_box_aspect(axes):
        setter = getattr(axes, "set_box_aspect", None)
        if callable(setter):
            setter((2.5, 2.0, 0.6))

    def update_hex_view(self, auto_scroll=True):
        self.data_manager.build_color_map(
            highlight_3d=self.highlight_3d,
            highlight_2d=self.highlight_2d,
            highlight_custom=self.highlight_custom_tags,
        )
        self.data_manager.map_dicts = {
            key: {"color": QColor(*value["color"]), "tag": value["tag"], "addr": value["addr"]}
            for key, value in self.data_manager.map_dicts_tuples.items()
        }

        row = self.current_row()
        fmt = self.data_manager.z_format_3d if self.row_is_3d(row) else self.data_manager.z_format_2d

        if not hasattr(self, "hex_table_model"):
            self.hex_table_model = HexTableModel(
                self.data_manager.bin_data,
                self.data_manager.map_array,
                self.data_manager.map_dicts,
                fmt,
                self.sparkline_style.value,
                self.hex_row_width,
            )
            self.hex_table.setModel(self.hex_table_model)
            self.hex_table.setFont(QFont("Courier New", 10))
            self.hex_table.selectionModel().currentChanged.connect(self.on_hex_selection_changed)
            self.hex_table.selectionModel().selectionChanged.connect(self.update_hex_plot)
        else:
            self.hex_table_model.update_settings(
                self.data_manager.bin_data,
                self.data_manager.map_array,
                self.data_manager.map_dicts,
                fmt,
                self.sparkline_style.value,
                self.hex_row_width,
            )

        bytes_per_col = self.hex_table_model.bytes_per_col
        width = {1: 35, 2: 55}.get(bytes_per_col, 95)
        for column in range(self.hex_table_model.data_cols):
            self.hex_table.setColumnWidth(column, width)
        self.hex_table.setColumnWidth(self.hex_table_model.data_cols, 150)

        if auto_scroll and row is not None:
            address = parse_address(row.get("Data_Addr", ""))
            if address is not None:
                index = self.hex_table_model.index(
                    address // self.hex_row_width, (address % self.hex_row_width) // bytes_per_col
                )
                if index.isValid():
                    self.hex_table.scrollTo(index, QTableView.ScrollHint.PositionAtTop)
                    self.hex_table.setCurrentIndex(index)

    # ------------------------------------------------------------------
    # Editing
    # ------------------------------------------------------------------

    def on_table_edit(self, item):
        if self.is_updating_table:
            return
        meta = item.data(Qt.ItemDataRole.UserRole)
        if not meta:
            return

        text = item.text().strip()
        try:
            value = int(text, 16) if meta["display_hex"] else float(text)
        except ValueError:
            QMessageBox.warning(
                self,
                "Invalid Input",
                f"'{text}' is not a valid {'hexadecimal' if meta['display_hex'] else 'numeric'} value.",
            )
            QTimer.singleShot(0, self.draw_map)
            return

        if meta["display_hex"] and not meta["apply_factor_to_hex"]:
            raw_value = value
        elif meta["factor"] == 0:
            QMessageBox.warning(self, "Edit Failed", "Factor is zero; the raw value cannot be derived.")
            QTimer.singleShot(0, self.draw_map)
            return
        else:
            raw_value = (value - meta["offset"]) / meta["factor"]

        success, error = self.data_manager.apply_edit(meta["address"], raw_value, meta["fmt"])
        if not success:
            QMessageBox.warning(self, "Edit Failed", error)
        QTimer.singleShot(0, self.draw_map)
        QTimer.singleShot(0, self.update_list)

    def draw_map(self, auto_scroll=True):
        self.map_renderer.draw_map(auto_scroll)

    # ------------------------------------------------------------------
    # Hex context menu (tagging)
    # ------------------------------------------------------------------

    def _selected_hex_chunks(self, fallback_address, bytes_per_col):
        """Merge the selected cells into contiguous ``(start, length)`` chunks."""
        indexes = self.hex_table.selectionModel().selectedIndexes()
        addresses = sorted(
            self.hex_address_at(i.row(), i.column())
            for i in indexes
            if i.column() < self.hex_table_model.data_cols
        )
        if not addresses:
            return [(fallback_address, bytes_per_col)]

        chunks = []
        start = previous = addresses[0]
        for address in addresses[1:]:
            if address == previous + bytes_per_col:
                previous = address
            else:
                chunks.append((start, previous - start + bytes_per_col))
                start = previous = address
        chunks.append((start, previous - start + bytes_per_col))
        return chunks

    def _existing_custom_tag_at(self, address):
        """Base address of the custom tag covering ``address``, if any."""
        map_array = self.data_manager.map_array
        if map_array is None or address >= len(map_array):
            return None
        map_id = int(map_array[address])
        if map_id == -1:
            return None
        info = self.data_manager.map_dicts_tuples.get(map_id, {})
        if info.get("color") != CUSTOM_TAG_COLOR:
            return None
        base = info.get("addr")
        return f"{base:08X}" if base is not None else None

    def show_hex_context_menu(self, pos):
        if self.app_mode is not AppMode.HEX_DUMP:
            return
        index = self.hex_table.indexAt(pos)
        if not index.isValid() or index.column() == self.hex_table_model.data_cols:
            return

        bytes_per_col = self.hex_table_model.bytes_per_col
        address = self.hex_address_at(index.row(), index.column())

        menu = QMenu(self)
        action_tag = menu.addAction("Tag Selection/Map...")
        action_dims = menu.addAction("Edit Tag Dimensions (3D)...")
        chosen = menu.exec(self.hex_table.viewport().mapToGlobal(pos))

        if chosen == action_tag:
            self._tag_hex_selection(address, bytes_per_col)
        elif chosen == action_dims:
            self._edit_hex_tag_dimensions(address, bytes_per_col)

    def _tag_hex_selection(self, address, bytes_per_col):
        chunks = self._selected_hex_chunks(address, bytes_per_col)
        selected = self.hex_table.selectionModel().selectedIndexes()

        base_addr_hex = None
        if len(selected) <= 1:
            existing = self._existing_custom_tag_at(address)
            if existing:
                stored = (self.data_manager.hexdump_tags.get(existing)
                          or self.data_manager.tags.get(existing, {}))
                if stored:
                    base_addr_hex = existing
                    chunks = stored.get("chunks") or [(int(existing, 16), stored.get("length", 1))]
        if not base_addr_hex:
            base_addr_hex = f"{chunks[0][0]:08X}"

        stored = self.data_manager.hexdump_tags.get(base_addr_hex, {})
        dialog = TagEditorDialog(stored.get("tags", []), self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        if dialog.tags:
            self.data_manager.hexdump_tags[base_addr_hex] = {
                "tags": dialog.tags,
                "length": sum(length for _, length in chunks),
                "chunks": chunks,
            }
        else:
            self.data_manager.hexdump_tags.pop(base_addr_hex, None)

        self._refresh_after_tag_change(base_addr_hex)

    def _edit_hex_tag_dimensions(self, address, bytes_per_col):
        base_addr_hex = self._existing_custom_tag_at(address) or f"{address:08X}"
        settings = self.data_manager.custom_map_settings.get(base_addr_hex, {})
        dims = self._ask_dimensions(settings.get("Size_X", 16), settings.get("Size_Y", 1))
        if dims is None:
            return
        self.data_manager.custom_map_settings.setdefault(base_addr_hex, {}).update(
            {"Size_X": dims[0], "Size_Y": dims[1]}
        )
        self._refresh_after_tag_change(base_addr_hex, rebuild_colors=False)

    def _ask_dimensions(self, current_x, current_y):
        value_x, ok_x = QInputDialog.getInt(
            self, "Edit Dimensions", "Size X (Columns):", int(current_x), 1, 1000
        )
        if not ok_x:
            return None
        value_y, ok_y = QInputDialog.getInt(
            self, "Edit Dimensions", "Size Y (Rows):", int(current_y), 1, 1000
        )
        if not ok_y:
            return None
        return value_x, value_y

    def _refresh_after_tag_change(self, base_addr_hex, rebuild_colors=True):
        if rebuild_colors:
            self.data_manager.build_color_map(
                highlight_3d=self.highlight_3d,
                highlight_2d=self.highlight_2d,
                highlight_custom=self.highlight_custom_tags,
            )
            self.update_tag_filter_menu()

        if self.map_mode in (MapMode.TAGS, MapMode.ALL):
            self.load_data(auto_scroll=False)
        else:
            self.update_list()

        if self.data_manager.current_map_addr == base_addr_hex:
            self.sync_listbox_selection()

        if self.app_mode is AppMode.HEX_DUMP:
            self.update_hex_view(auto_scroll=False)
        self.draw_map(auto_scroll=False)

    def edit_current_tag_dimensions(self):
        row = self.current_row()
        if row is None or row.get("Map_Type", "") != "tags":
            QMessageBox.information(self, "Info", "Select a Tag to edit its dimensions.")
            return

        base_addr_hex = str(row["Data_Addr"]).strip()
        settings = self.data_manager.custom_settings_for(row)
        width = self.data_manager.value_size_for(row)
        elements = max(1, int(row.get("Tag_Length", 1) or 1) // width)

        default_x = settings.get("Size_X", min(elements, 16))
        default_y = settings.get("Size_Y", max(1, elements // max(int(default_x), 1)))
        dims = self._ask_dimensions(default_x, default_y)
        if dims is None:
            return

        self.data_manager.set_custom_setting(row, Size_X=dims[0], Size_Y=dims[1])
        self.data_manager.df.loc[self.data_manager.current_index, "Size_X"] = str(dims[0])
        self.data_manager.df.loc[self.data_manager.current_index, "Size_Y"] = str(dims[1])

        self.update_list()
        if self.data_manager.current_map_addr == base_addr_hex:
            self.sync_listbox_selection()
        self.draw_map()

    def edit_specific_tag(self, target):
        row = self.current_row()
        if row is None:
            return

        is_3d = self.row_is_3d(row)
        column, title = {
            "wrapper": ("Wrapper_Addr", "Map"),
            "z": ("Data_Addr", "Z Data" if is_3d else "Curve Data"),
            "x": ("Axis_X_Addr", "X Axis"),
            "y": ("Axis_Y_Addr", "Y Axis"),
        }.get(target, (None, ""))

        if column is None or (target == "y" and not is_3d):
            return

        address = str(row.get(column, "")).strip().upper()
        if not address or address in ("0", "0X0", "00000000"):
            QMessageBox.information(self, "No Address", f"This map has no {title} address to tag.")
            return

        stored = self.data_manager.tags.get(address, {})
        dialog = TagEditorDialog(stored.get("tags", []), self)
        dialog.setWindowTitle(f"Edit {title} Tags ({address})")
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        if dialog.tags:
            self.data_manager.tags[address] = {"tags": dialog.tags, "length": stored.get("length", 1)}
        else:
            self.data_manager.tags.pop(address, None)

        if "Tag" in self.data_manager.df.columns:
            self.data_manager.df.loc[self.data_manager.current_index, "Tag"] = ", ".join(dialog.tags)

        self.data_manager.build_color_map(
            highlight_3d=self.highlight_3d,
            highlight_2d=self.highlight_2d,
            highlight_custom=self.highlight_custom_tags,
        )
        self.update_tag_filter_menu()
        self.update_list()
        self.sync_listbox_selection()
        if self.app_mode is AppMode.HEX_DUMP:
            self.update_hex_view()
        self.draw_map()

    # ------------------------------------------------------------------
    # Files
    # ------------------------------------------------------------------

    def export_modified_bin(self):
        if not self.data_manager.has_binary:
            QMessageBox.warning(self, "Export Failed", "No binary is loaded.")
            return
        if not self.data_manager.has_edits:
            QMessageBox.information(self, "Nothing to Export", "The binary has no modifications.")
            return

        total, regions, lines = self.data_manager.export_summary()
        confirm = QMessageBox(self)
        confirm.setIcon(QMessageBox.Icon.Warning)
        confirm.setWindowTitle("Export Modified Binary")
        confirm.setText(f"{total} byte(s) changed across {regions} region(s).")
        confirm.setInformativeText(CHECKSUM_WARNING)
        confirm.setDetailedText("\n".join(lines))
        confirm.setStandardButtons(QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Cancel)
        confirm.setDefaultButton(QMessageBox.StandardButton.Cancel)
        if confirm.exec() != QMessageBox.StandardButton.Save:
            return

        file_path, _ = QFileDialog.getSaveFileName(
            self, "Export Modified Bin", "", "Binary Files (*.bin);;All Files (*)"
        )
        if not file_path:
            return
        success, error = self.data_manager.write_modified_bin(file_path)
        if success:
            QMessageBox.information(
                self,
                "Exported",
                f"Written to:\n{file_path}\n\nChecksums were NOT recalculated.",
            )
        else:
            QMessageBox.critical(self, "Error", f"Failed to export:\n{error}")

    def load_reference_bin(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Select Reference Bin", "", "Binary Files (*.bin);;All Files (*)"
        )
        if not file_path:
            return
        success, error = self.data_manager.load_reference_bin(file_path)
        if success:
            QMessageBox.information(self, "Loaded", f"Reference binary:\n{os.path.basename(file_path)}")
            self.draw_map()
        else:
            QMessageBox.critical(self, "Error", f"Failed to load reference bin:\n{error}")

    def save_project(self):
        path, _ = QFileDialog.getSaveFileName(self, "Save Project", "", "Denso Project (*.dproj *.json)")
        if not path:
            return
        success, error = self.data_manager.save_project(path)
        if success:
            QMessageBox.information(self, "Saved", "Project saved successfully.")
        else:
            QMessageBox.critical(self, "Error", f"Could not save project:\n{error}")

    def load_project(self):
        path, _ = QFileDialog.getOpenFileName(self, "Load Project", "", "Denso Project (*.dproj *.json)")
        if not path:
            return
        success, warning = self.data_manager.load_project(path)
        if not success:
            QMessageBox.critical(self, "Error", f"Could not load project:\n{warning}")
            return

        self.data_manager.load_dtc_csv()
        self.load_data()
        if warning:
            QMessageBox.warning(self, "Project Loaded With Warnings", warning)
        else:
            QMessageBox.information(self, "Loaded", "Project loaded successfully.")
