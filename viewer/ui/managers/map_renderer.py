"""Turns the selected map into a plot and a table.

Previously a single 470-line method inside one bare ``try/except`` that rendered
every failure as the same opaque "Error:" string on the canvas. Split into
prepare / plot / table so a decode failure can say which stage broke and why.
"""

from dataclasses import dataclass, field

import numpy as np
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import QTableWidgetItem

from ...core import formats
from ...core.data_manager import BinaryUnavailable, parse_address
from ...core.state import AppMode
from ..components.sparkline_widget import SparklineWidget

MODIFIED_COLOR = QColor(255, 0, 0)
BASELINE_TEXT_COLOR = QColor(80, 80, 80)


@dataclass
class MapView:
    """Everything one render pass needs, decoded once."""

    matrix: np.ndarray
    raw: np.ndarray
    axis_x: np.ndarray
    axis_y: np.ndarray
    size_x: int
    size_y: int
    address: str
    fmt: str
    factor: float
    offset: float
    is_3d: bool

    is_tag_block: bool = False
    baseline: np.ndarray = None
    baseline_axis_x: np.ndarray = None
    baseline_axis_y: np.ndarray = None
    baseline_size_x: int = 0
    baseline_size_y: int = 0

    labels: dict = field(default_factory=dict)

    @property
    def has_baseline(self):
        return self.baseline is not None

    @property
    def value_width(self):
        return formats.value_size(self.fmt)


def _tick_labels(values):
    """Axis tick text without trailing zeros: ``1500.0`` -> ``1500``."""
    return [str(round(float(v), 2)).rstrip("0").rstrip(".") for v in values]


class MapRenderer:
    def __init__(self, main_window):
        self.main_window = main_window

    # ------------------------------------------------------------------
    # Entry point
    # ------------------------------------------------------------------

    def draw_map(self, auto_scroll=True):
        mw = self.main_window

        if mw.app_mode is AppMode.HEX_DUMP:
            mw.update_hex_view(auto_scroll=auto_scroll)
            mw.update_hex_plot()
            return

        row = mw.current_row()
        if row is None:
            self.clear("No map selected.")
            return

        mw.btn_dtc_info.setVisible(mw.data_manager.dtc_for(row) is not None)

        try:
            view = self._prepare(row)
        except (BinaryUnavailable, ValueError) as exc:
            self.clear(str(exc))
            mw.status_lbl.setText(str(exc))
            return

        # Switching between a curve and a surface needs different axes objects.
        if getattr(mw, "_last_dim_3d", None) != view.is_3d:
            mw.rebuild_plot_axes()
        mw._last_dim_3d = view.is_3d

        self._publish_state(view)

        if mw.view_mode.shows_plot:
            self._render_plot(view)
        if mw.view_mode.shows_table:
            self._render_table(view)

    def clear(self, message=""):
        """Blank the plot and table, optionally showing why."""
        mw = self.main_window
        if getattr(mw, "ax", None) is not None:
            mw.ax.clear()
            if message:
                text_fn = getattr(mw.ax, "text2D", mw.ax.text)
                text_fn(0.5, 0.5, message, transform=mw.ax.transAxes, ha="center",
                        va="center", color="red", wrap=True)
            mw.canvas.draw_idle()
        if getattr(mw, "table", None) is not None:
            mw.is_updating_table = True
            mw.table.clear()
            mw.table.setRowCount(0)
            mw.table.setColumnCount(0)
            mw.is_updating_table = False
        if getattr(mw, "table_orig", None) is not None:
            mw.table_orig.setVisible(False)

    # ------------------------------------------------------------------
    # Preparation
    # ------------------------------------------------------------------

    def _prepare(self, row):
        mw = self.main_window
        dm = mw.data_manager

        is_3d = mw.row_is_3d(row)
        raw, axis_x, axis_y, size_y, size_x, address = dm.read_map(row, as_2d=not is_3d)

        custom = dm.custom_settings_for(row)
        if is_3d:
            factor = custom.get("factor", mw.factor_z_3d)
            offset = custom.get("offset", mw.offset_z_3d)
            fmt = custom.get("z_format", dm.z_format_3d)
        else:
            factor = custom.get("factor", mw.factor_z_2d)
            offset = custom.get("offset", mw.offset_z_2d)
            fmt = custom.get("z_format", dm.z_format_2d)

        view = MapView(
            matrix=raw * factor + offset,
            raw=raw,
            axis_x=axis_x,
            axis_y=axis_y,
            size_x=size_x,
            size_y=size_y,
            address=address,
            fmt=fmt,
            factor=factor,
            offset=offset,
            is_3d=is_3d,
            is_tag_block=row.get("Map_Type", "") == "tags",
        )
        self._attach_baseline(view, row)
        self._attach_labels(view, row)
        return view

    def _attach_baseline(self, view, row):
        """Populate the comparison side and apply diff/percent transforms."""
        mw = self.main_window
        mode = mw.compare_mode
        if not mode.is_comparison:
            return

        if mode.uses_reference_map:
            if mw.reference_matrix is None:
                return
            baseline = mw.reference_matrix * view.factor + view.offset
            view.baseline_axis_x = mw.reference_axis_x
            view.baseline_axis_y = mw.reference_axis_y
            view.baseline_size_x = mw.reference_size_x
            view.baseline_size_y = mw.reference_size_y
        else:
            try:
                result = mw.data_manager.read_map_baseline(row, mode.baseline, as_2d=not view.is_3d)
            except (BinaryUnavailable, ValueError):
                return
            if result is None:
                return
            baseline_raw, base_x, base_y, base_sy, base_sx, _ = result
            baseline = baseline_raw * view.factor + view.offset
            view.baseline_axis_x = base_x
            view.baseline_axis_y = base_y
            view.baseline_size_x = base_sx
            view.baseline_size_y = base_sy

        view.baseline = baseline

        if mode.subtracts:
            view.matrix = view.matrix - self._conform(baseline, view.matrix)
        elif mode.is_percent:
            aligned = self._conform(baseline, view.matrix)
            safe = np.where(aligned == 0, 1e-9, aligned)
            view.matrix = (view.matrix - aligned) / safe * 100.0

    @staticmethod
    def _conform(baseline, target):
        """Fit ``baseline`` to ``target``'s shape, zero-padding what is missing.

        Comparing maps of different dimensions is legitimate (a reference map
        from a different calibration), so a shape mismatch must not abort the
        render.
        """
        if baseline.shape == target.shape:
            return baseline
        conformed = np.zeros_like(target, dtype=float)
        if baseline.ndim == target.ndim == 2:
            rows = min(baseline.shape[0], target.shape[0])
            cols = min(baseline.shape[1], target.shape[1])
            conformed[:rows, :cols] = baseline[:rows, :cols]
        elif baseline.ndim == target.ndim == 1:
            count = min(baseline.shape[0], target.shape[0])
            conformed[:count] = baseline[:count]
        return conformed

    def _attach_labels(self, view, row):
        """Axis captions carrying any user tag attached to that address."""
        tags = self.main_window.data_manager.tags

        def tag_for(column):
            address = str(row.get(column, "")).strip().upper()
            if not address or address in ("0", "0X0", "00000000"):
                return ""
            return " ".join(tags.get(address, {}).get("tags", []))

        x_tag = tag_for("Axis_X_Addr")
        y_tag = tag_for("Axis_Y_Addr") if view.is_3d else ""
        z_tag = tag_for("Data_Addr")

        view.labels = {
            "x": f"X Axis [{x_tag}]" if x_tag else "X Axis",
            "y": f"Y Axis [{y_tag}]" if y_tag else "Y Axis",
            "z": (f"Z Data [{z_tag}]" if z_tag else "Z Data") if view.is_3d
                 else (f"Curve Data [{z_tag}]" if z_tag else "Curve Data"),
        }

    def _publish_state(self, view):
        """Copy render state onto the window for the hover/zoom handlers."""
        mw = self.main_window
        mw.real_axis_x = view.axis_x
        mw.real_axis_y = view.axis_y
        mw.map_size_x = view.size_x
        mw.map_size_y = view.size_y
        mw.z_min = float(view.matrix.min())
        mw.z_max = float(view.matrix.max())
        mw.x_label_str = view.labels["x"]
        mw.y_label_str = view.labels["y"]
        mw.z_label_3d_str = view.labels["z"]
        mw.z_label_2d_str = view.labels["z"]

        if mw.compare_mode.is_twin and view.has_baseline:
            mw.z_orig_min = float(view.baseline.min())
            mw.z_orig_max = float(view.baseline.max())
        else:
            mw.z_orig_min = mw.z_min
            mw.z_orig_max = mw.z_max

        # Reset the camera only when the selection actually changed.
        if mw.data_manager.current_map_addr != view.address:
            mw.data_manager.current_map_addr = view.address
            self._reset_camera(view)

        mw.lbl_title.setText(
            f"Map {mw.data_manager.current_index + 1}/{mw.data_manager.total_maps} | "
            f"Addr: {view.address} | Z: {view.fmt} | Factor: {view.factor}"
        )

    def _reset_camera(self, view):
        mw = self.main_window
        mw.abs_center_x = (view.size_x - 1) / 2.0
        mw.abs_center_y = (view.size_y - 1) / 2.0
        mw.center_x = mw.abs_center_x
        mw.center_y = mw.abs_center_y
        mw.cam_zoom = 1.0

        x_margin = (view.axis_x.max() - view.axis_x.min()) * 0.05 or 1.0
        y_margin = (view.matrix.max() - view.matrix.min()) * 0.05 or 1.0
        mw.abs_xlim = (view.axis_x.min() - x_margin, view.axis_x.max() + x_margin)
        mw.abs_ylim = (view.matrix.min() - y_margin, view.matrix.max() + y_margin)
        mw.center_x_2d = sum(mw.abs_xlim) / 2.0
        mw.center_y_2d = sum(mw.abs_ylim) / 2.0
        mw.cam_zoom_2d = 1.0

    # ------------------------------------------------------------------
    # Plot
    # ------------------------------------------------------------------

    def _render_plot(self, view):
        mw = self.main_window
        use_pyqtgraph = mw.render_engine == "pyqtgraph"
        mw.canvas.setVisible(not use_pyqtgraph)
        mw.pg_canvas.setVisible(use_pyqtgraph)

        if use_pyqtgraph:
            if view.is_3d:
                mw.pg_canvas.draw_3d(
                    np.arange(view.size_x),
                    np.arange(view.size_y),
                    view.matrix,
                    _tick_labels(view.axis_x),
                    _tick_labels(view.axis_y),
                )
            else:
                mw.pg_canvas.draw_2d(view.axis_x, view.matrix)
            return

        mw.ax.clear()
        if hasattr(mw, "ax2"):
            mw.ax2.clear()

        if view.is_3d:
            self._render_surface(view)
        else:
            self._render_curve(view)
        mw.canvas.draw_idle()

    def _render_surface(self, view):
        mw = self.main_window
        grid_x, grid_y = np.meshgrid(np.arange(view.size_x), np.arange(view.size_y))

        mw.x_flat = grid_x.flatten()
        mw.y_flat = grid_y.flatten()
        mw.z_flat = view.matrix.flatten()
        mw.raw_flat = view.raw.flatten()

        mw.ax.plot_surface(grid_x, grid_y, view.matrix, cmap="jet",
                           edgecolor="k", linewidth=0.3, alpha=0.9)
        mw.cursor_marker, = mw.ax.plot([0], [0], [0], marker="o", color="red",
                                       markersize=8, zorder=10)
        mw.cursor_marker.set_visible(False)

        if mw.compare_mode.is_twin and view.has_baseline and hasattr(mw, "ax2"):
            mw.ax.set_title("Modified Map", fontsize=10, pad=0)
            mw.ax2.set_title(mw.compare_mode.baseline_title, fontsize=10, pad=0)
            self._render_baseline_surface(view)

        self._decorate_surface(mw.ax, view, _tick_labels(view.axis_x), _tick_labels(view.axis_y))
        mw.apply_3d_zoom()

    def _render_baseline_surface(self, view):
        mw = self.main_window
        if view.baseline_size_x and view.baseline.shape == (view.baseline_size_y, view.baseline_size_x):
            size_x, size_y = view.baseline_size_x, view.baseline_size_y
            ticks_x = _tick_labels(view.baseline_axis_x)
            ticks_y = _tick_labels(view.baseline_axis_y)
        else:
            size_x, size_y = view.size_x, view.size_y
            ticks_x = _tick_labels(view.axis_x)
            ticks_y = _tick_labels(view.axis_y)

        grid_x, grid_y = np.meshgrid(np.arange(size_x), np.arange(size_y))
        matrix = self._conform(view.baseline, np.zeros((size_y, size_x)))
        mw.ax2.plot_surface(grid_x, grid_y, matrix, cmap="coolwarm",
                            edgecolor="white", linewidth=0.3, alpha=0.9)
        self._decorate_surface(mw.ax2, view, ticks_x, ticks_y)

    def _decorate_surface(self, axes, view, ticks_x, ticks_y):
        mw = self.main_window
        axes.set_xticks(np.arange(len(ticks_x)))
        axes.set_xticklabels(ticks_x, rotation=45, ha="right", fontsize=8)
        axes.set_yticks(np.arange(len(ticks_y)))
        axes.set_yticklabels(ticks_y, fontsize=8)
        axes.set_xlabel("\n" + view.labels["x"], labelpad=12)
        axes.set_ylabel("\n" + view.labels["y"], labelpad=12)
        axes.set_zlabel(view.labels["z"], labelpad=12)
        axes.invert_yaxis()
        setter = getattr(axes, "set_box_aspect", None)
        if callable(setter):
            setter((2.5, 2.0, 0.6))
        axes.view_init(elev=mw.start_elev, azim=mw.start_azim)

    def _render_curve(self, view):
        mw = self.main_window
        mw.x_flat = view.axis_x
        mw.z_flat = view.matrix
        mw.raw_flat = view.raw

        if mw.compare_mode.is_twin and view.has_baseline:
            baseline_axis = (
                view.baseline_axis_x
                if view.baseline_axis_x is not None and len(view.baseline_axis_x) == len(view.baseline)
                else view.axis_x
            )
            mw.ax.plot(baseline_axis, view.baseline, marker="s", color="#888888",
                       linestyle="--", linewidth=1.5, markersize=4,
                       label=mw.compare_mode.baseline_title)
            mw.ax.plot(view.axis_x, view.matrix, marker="o", color="b",
                       linewidth=2, markersize=5, label="Modified")
            mw.ax.legend(loc="best")
        else:
            mw.ax.plot(view.axis_x, view.matrix, marker="o", color="b",
                       linewidth=2, markersize=5)

        mw.cursor_marker, = mw.ax.plot([], [], marker="o", color="red", markersize=8, zorder=10)
        mw.cursor_marker.set_visible(False)
        mw.ax.set_xlabel(view.labels["x"])
        mw.ax.set_ylabel(view.labels["z"])
        mw.ax.grid(True, linestyle="--", alpha=0.7)
        mw.apply_2d_zoom()

    # ------------------------------------------------------------------
    # Table
    # ------------------------------------------------------------------

    def _render_table(self, view):
        mw = self.main_window
        mw.is_updating_table = True
        try:
            mw.table.clear()
            mw.table.setRowCount(view.size_y)
            mw.table.setColumnCount(view.size_x + 1)  # +1 for the sparkline column
            mw.table.setHorizontalHeaderLabels(_tick_labels(view.axis_x) + ["Profile"])
            mw.table.setVerticalHeaderLabels(
                _tick_labels(view.axis_y) if view.is_3d else ["Curve Data"]
            )

            matrix = np.atleast_2d(view.matrix)
            raw = np.atleast_2d(view.raw)
            raw_min, raw_max = float(raw.min()), float(raw.max())
            base_address = parse_address(view.address)
            editable = self._cells_are_editable(view)

            for r in range(view.size_y):
                for c in range(view.size_x):
                    index = r * view.size_x + c
                    address = None if base_address is None else base_address + index * view.value_width
                    mw.table.setItem(r, c, self._make_item(view, matrix[r, c], raw[r, c], address, editable))
                mw.table.setCellWidget(
                    r, view.size_x,
                    SparklineWidget(raw[r, :], raw_min, raw_max, mw.sparkline_style.value),
                )

            self._render_baseline_table(view)
            mw.table.resizeColumnsToContents()
            mw.table.setColumnWidth(view.size_x, 150)
        finally:
            mw.is_updating_table = False

    def _cells_are_editable(self, view):
        """Editing is only meaningful on a confirmed map shown as-is.

        Hexdump tags are excluded because a tag can span several disjoint
        chunks, so a cell's position in the grid does not map back to a single
        contiguous address range.
        """
        mw = self.main_window
        return not (
            mw.compare_mode.is_comparison
            or mw.app_mode.is_read_only
            or view.is_tag_block
            or view.address == ""
        )

    def _make_item(self, view, value, raw_value, address, editable):
        mw = self.main_window
        if mw.display_hex:
            source = value if mw.apply_factor_to_hex else raw_value
            text = mw.data_manager.val_to_hex(source, view.fmt)
        else:
            text = f"{value:.2f}"

        item = QTableWidgetItem(text)
        item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)

        if address is not None and mw.data_manager.is_map_modified(address, view.value_width):
            item.setForeground(MODIFIED_COLOR)

        if editable and address is not None:
            item.setData(Qt.ItemDataRole.UserRole, {
                "address": address,
                "fmt": view.fmt,
                "factor": view.factor,
                "offset": view.offset,
                "apply_factor_to_hex": mw.apply_factor_to_hex,
                "display_hex": mw.display_hex,
            })
        else:
            item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        return item

    def _render_baseline_table(self, view):
        mw = self.main_window
        if not (mw.compare_mode.is_twin and view.has_baseline):
            mw.table_orig.setVisible(False)
            return

        baseline = np.atleast_2d(view.baseline)
        size_y, size_x = baseline.shape

        mw.table_orig.setVisible(True)
        mw.table_orig.clear()
        mw.table_orig.setRowCount(size_y)
        mw.table_orig.setColumnCount(size_x)

        axis_x = view.baseline_axis_x if view.baseline_axis_x is not None else view.axis_x
        axis_y = view.baseline_axis_y if view.baseline_axis_y is not None else view.axis_y
        mw.table_orig.setHorizontalHeaderLabels(_tick_labels(axis_x)[:size_x])
        mw.table_orig.setVerticalHeaderLabels(
            _tick_labels(axis_y)[:size_y] if view.is_3d else ["Curve Data"]
        )

        for r in range(size_y):
            for c in range(size_x):
                value = baseline[r, c]
                text = (mw.data_manager.val_to_hex(value, view.fmt)
                        if mw.display_hex else f"{value:.2f}")
                item = QTableWidgetItem(text)
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                item.setForeground(BASELINE_TEXT_COLOR)
                mw.table_orig.setItem(r, c, item)

        mw.table_orig.resizeColumnsToContents()
