"""Camera control and hover read-out for the matplotlib canvas."""

import numpy as np
from mpl_toolkits.mplot3d import proj3d

from ...core.state import AppMode, RotationMode

#: Squared pixel distance within which the cursor snaps to a data point.
HOVER_SNAP_RADIUS_SQ = 600

ROTATION_SENSITIVITY = 0.4

IDLE_MESSAGE = "Hover over the graph to see values..."


def _is_3d(axes):
    return getattr(axes, "name", "") == "3d"


class MouseEventsManager:
    def __init__(self, main_window):
        self.main_window = main_window

    # ------------------------------------------------------------------
    # Zoom / limits
    # ------------------------------------------------------------------

    def apply_3d_zoom(self):
        mw = self.main_window
        if not hasattr(mw, "map_size_x"):
            return

        span_x = max(1, mw.map_size_x - 1) * 1.15 / mw.cam_zoom
        span_y = max(1, mw.map_size_y - 1) * 1.15 / mw.cam_zoom

        mw.center_x = self._clamp_centre(mw.center_x, span_x, mw.map_size_x)
        mw.center_y = self._clamp_centre(mw.center_y, span_y, mw.map_size_y)

        mw.ax.set_xlim(mw.center_x - span_x / 2, mw.center_x + span_x / 2)
        mw.ax.set_ylim(mw.center_y + span_y / 2, mw.center_y - span_y / 2)
        self._set_zlim(mw.ax, mw.z_min, mw.z_max)
        mw.ax.set_autoscale_on(False)

        if hasattr(mw, "ax2"):
            mw.ax2.set_xlim(mw.center_x - span_x / 2, mw.center_x + span_x / 2)
            mw.ax2.set_ylim(mw.center_y + span_y / 2, mw.center_y - span_y / 2)
            self._set_zlim(mw.ax2, getattr(mw, "z_orig_min", mw.z_min), getattr(mw, "z_orig_max", mw.z_max))
            mw.ax2.set_autoscale_on(False)

        mw.canvas.draw_idle()

    @staticmethod
    def _clamp_centre(centre, span, size):
        """Keep the viewport inside the map, or centre it when it does not fit."""
        low = span / 2
        high = (size - 1) - span / 2
        if low > high:
            return (size - 1) / 2.0
        return max(low, min(centre, high))

    @staticmethod
    def _set_zlim(axes, low, high):
        # A flat map has zero height; matplotlib refuses a degenerate limit.
        if low == high:
            axes.set_zlim(low - 1, high + 1)
        else:
            axes.set_zlim(low, high)

    def apply_2d_zoom(self):
        mw = self.main_window
        span_x = (mw.abs_xlim[1] - mw.abs_xlim[0]) / mw.cam_zoom_2d
        span_y = (mw.abs_ylim[1] - mw.abs_ylim[0]) / mw.cam_zoom_2d

        mw.center_x_2d = max(mw.abs_xlim[0] + span_x / 2, min(mw.center_x_2d, mw.abs_xlim[1] - span_x / 2))
        mw.center_y_2d = max(mw.abs_ylim[0] + span_y / 2, min(mw.center_y_2d, mw.abs_ylim[1] - span_y / 2))

        mw.ax.set_xlim(mw.center_x_2d - span_x / 2, mw.center_x_2d + span_x / 2)
        mw.ax.set_ylim(mw.center_y_2d - span_y / 2, mw.center_y_2d + span_y / 2)
        mw.ax.set_autoscale_on(False)
        mw.canvas.draw_idle()

    # ------------------------------------------------------------------
    # Drag
    # ------------------------------------------------------------------

    def on_mouse_press(self, event):
        if event.button != 1:
            return
        mw = self.main_window
        mw.dragging = True
        mw.mouse_x = event.x
        mw.mouse_y = event.y
        if _is_3d(mw.ax):
            mw.start_elev = mw.ax.elev
            mw.start_azim = mw.ax.azim
        else:
            mw.start_center_x_2d = mw.center_x_2d
            mw.start_center_y_2d = mw.center_y_2d

    def on_mouse_release(self, _event):
        mw = self.main_window
        mw.dragging = False
        if _is_3d(mw.ax):
            mw.start_elev = mw.ax.elev
            mw.start_azim = mw.ax.azim

    def on_mouse_move(self, event):
        mw = self.main_window
        if mw.data_manager.df.empty and mw.app_mode is not AppMode.HEX_DUMP:
            return

        if mw.dragging:
            if event.x is None or event.y is None:
                return
            if _is_3d(mw.ax):
                self._rotate(event)
            else:
                self._pan(event)
            return

        mw.mouse_x_data = event.xdata
        mw.mouse_y_data = event.ydata
        self._update_hover(event)

    def _rotate(self, event):
        mw = self.main_window
        dx = event.x - mw.mouse_x
        dy = event.y - mw.mouse_y
        elev, azim = mw.start_elev, mw.start_azim

        if mw.rot_mode in (RotationMode.WINOLS, RotationMode.TILT):
            elev = max(-90, min(90, mw.start_elev - dy * ROTATION_SENSITIVITY))
        if mw.rot_mode in (RotationMode.WINOLS, RotationMode.Z_ONLY):
            azim = mw.start_azim - dx * ROTATION_SENSITIVITY

        mw.ax.view_init(elev=elev, azim=azim)
        mw._sync_3d_axes()
        mw.canvas.draw_idle()

    def _pan(self, event):
        mw = self.main_window
        inverse = mw.ax.transData.inverted()
        x0, y0 = inverse.transform((0, 0))
        x1, y1 = inverse.transform((1, 1))

        mw.center_x_2d = mw.start_center_x_2d - (event.x - mw.mouse_x) * (x1 - x0)
        mw.center_y_2d = mw.start_center_y_2d - (event.y - mw.mouse_y) * (y1 - y0)
        self.apply_2d_zoom()

    # ------------------------------------------------------------------
    # Hover
    # ------------------------------------------------------------------

    def _clear_hover(self):
        mw = self.main_window
        mw.is_hovering = False
        marker = getattr(mw, "cursor_marker", None)
        if marker is not None and marker.get_visible():
            marker.set_visible(False)
            mw.status_lbl.setText(IDLE_MESSAGE)
            mw.canvas.draw_idle()

    def _update_hover(self, event):
        mw = self.main_window
        if getattr(event, "inaxes", None) is not mw.ax or len(mw.z_flat) == 0:
            self._clear_hover()
            return
        if getattr(mw, "cursor_marker", None) is None:
            return

        is_3d = _is_3d(mw.ax)
        try:
            if is_3d:
                xs, ys, _ = proj3d.proj_transform(mw.x_flat, mw.y_flat, mw.z_flat, mw.ax.get_proj())
                points = mw.ax.transData.transform(np.column_stack([xs, ys]))
            else:
                points = mw.ax.transData.transform(np.column_stack([mw.x_flat, mw.z_flat]))
        except (ValueError, TypeError):
            # Shapes can briefly disagree between a data reload and a redraw.
            self._clear_hover()
            return

        distances = (points[:, 0] - event.x) ** 2 + (points[:, 1] - event.y) ** 2
        nearest = int(np.argmin(distances))
        if distances[nearest] >= HOVER_SNAP_RADIUS_SQ:
            self._clear_hover()
            return

        mw.is_hovering = True
        label = self._hover_label_3d(nearest) if is_3d else self._hover_label_2d(nearest)
        mw.cursor_marker.set_visible(True)
        mw.status_lbl.setText(label)
        mw.canvas.draw_idle()

    def _hover_value_text(self, index, value, fmt):
        """Formatted Z read-out, honouring the hex / factor toggles."""
        mw = self.main_window
        if not mw.display_hex:
            return f"{value:.2f}"
        raw = value if mw.apply_factor_to_hex else mw.raw_flat[index]
        return mw.data_manager.val_to_hex(raw, fmt)

    def _hover_label_3d(self, index):
        mw = self.main_window
        mw.hover_x = mw.x_flat[index]
        mw.hover_y = mw.y_flat[index]
        value = mw.z_flat[index]

        mw.cursor_marker.set_data([mw.hover_x], [mw.hover_y])
        mw.cursor_marker.set_3d_properties([value])

        real_x = self._axis_value(mw.real_axis_x, mw.hover_x)
        real_y = self._axis_value(mw.real_axis_y, mw.hover_y)
        text = self._hover_value_text(index, value, mw.data_manager.z_format_3d)
        suffix = " (HEX)" if mw.display_hex else ""
        return f"Target: X = {real_x:g}   |   Y = {real_y:g}   |   Z{suffix} = {text}"

    def _hover_label_2d(self, index):
        mw = self.main_window
        x_value = mw.x_flat[index]
        value = mw.z_flat[index]
        mw.cursor_marker.set_data([x_value], [value])

        text = self._hover_value_text(index, value, mw.data_manager.z_format_2d)
        suffix = " (HEX)" if mw.display_hex else " (Curve)"
        return f"Target: X = {x_value:g}   |   Z{suffix} = {text}"

    @staticmethod
    def _axis_value(axis, position):
        """Real axis value at a grid position, falling back to the index."""
        try:
            index = int(position)
        except (TypeError, ValueError):
            return float("nan")
        if axis is None or index < 0 or index >= len(axis):
            return float(index)
        return float(axis[index])
