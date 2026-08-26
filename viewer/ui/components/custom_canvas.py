"""Matplotlib canvas with wheel-driven zoom that keeps the hovered point fixed."""

from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas

from ...core.state import ViewMode

ZOOM_IN_FACTOR = 1.15
ZOOM_OUT_FACTOR = 0.85
MAX_ZOOM_3D = 15.0
MAX_ZOOM_2D = 50.0


class CustomCanvas(FigureCanvas):
    def __init__(self, fig, parent):
        super().__init__(fig)
        self.parent_app = parent

    def wheelEvent(self, event):
        app = self.parent_app
        if app.view_mode is not ViewMode.PLOT or not self.underMouse():
            return

        delta = event.angleDelta().y()
        if delta == 0:
            return
        zoom_in = delta > 0
        factor = ZOOM_IN_FACTOR if zoom_in else ZOOM_OUT_FACTOR

        if getattr(app.ax, "name", "") == "3d":
            self._zoom_3d(app, factor, zoom_in)
        else:
            self._zoom_2d(app, factor, self._event_data_pos(event))

    def _event_data_pos(self, event):
        """Wheel position in data coordinates, or ``None`` if it cannot be mapped.

        Qt measures y downwards from the top, matplotlib upwards from the
        bottom, hence the flip against the canvas height.
        """
        position = getattr(event, "position", None)
        point = position() if callable(position) else event.pos()
        try:
            x, y = self.parent_app.ax.transData.inverted().transform(
                (point.x(), self.height() - point.y())
            )
        except (ValueError, TypeError):
            return None
        return float(x), float(y)

    @staticmethod
    def _zoom_3d(app, factor, zoom_in):
        old_zoom = app.cam_zoom
        app.cam_zoom = max(1.0, min(old_zoom * factor, MAX_ZOOM_3D))

        if app.cam_zoom == 1.0:
            app.center_x = app.abs_center_x
            app.center_y = app.abs_center_y
        elif old_zoom != app.cam_zoom:
            ratio = app.cam_zoom / old_zoom
            # Zooming in holds the hovered cell still; zooming out drifts back
            # towards the middle of the map.
            anchor_x, anchor_y = (
                (app.hover_x, app.hover_y) if zoom_in and app.is_hovering
                else (app.abs_center_x, app.abs_center_y)
            )
            app.center_x = anchor_x - (anchor_x - app.center_x) / ratio
            app.center_y = anchor_y - (anchor_y - app.center_y) / ratio

        app.apply_3d_zoom()

    @staticmethod
    def _zoom_2d(app, factor, anchor):
        old_zoom = app.cam_zoom_2d
        app.cam_zoom_2d = max(1.0, min(old_zoom * factor, MAX_ZOOM_2D))

        if app.cam_zoom_2d == 1.0:
            app.center_x_2d = sum(app.abs_xlim) / 2.0
            app.center_y_2d = sum(app.abs_ylim) / 2.0
        elif old_zoom != app.cam_zoom_2d:
            ratio = app.cam_zoom_2d / old_zoom
            anchor_x, anchor_y = anchor if anchor else (
                sum(app.abs_xlim) / 2.0,
                sum(app.abs_ylim) / 2.0,
            )
            app.center_x_2d = anchor_x - (anchor_x - app.center_x_2d) / ratio
            app.center_y_2d = anchor_y - (anchor_y - app.center_y_2d) / ratio

        app.apply_2d_zoom()
