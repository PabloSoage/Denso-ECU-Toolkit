"""Row profile drawn at the end of each table row (WinOLS-style)."""

from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import QBrush, QColor, QPainter, QPolygonF
from PyQt6.QtWidgets import QWidget

BACKGROUND = QColor(0, 0, 0)
TRACE = QColor(0, 255, 0)
FLAT_BAR_HEIGHT = 2


def paint_sparkline(painter, rect, values, style="Bars", low=None, high=None):
    """Draw a sparkline for ``values`` into ``rect``.

    ``low``/``high`` set the vertical scale. The map table passes the whole
    map's range so that rows stay comparable with each other; the hex view
    leaves them out and scales each row independently.

    Shared by the standalone widget and the hex-view delegate, which previously
    carried two near-identical copies of this drawing code that had already
    drifted apart in their handling of flat rows.
    """
    values = list(values)
    if not values:
        return

    low = min(values) if low is None else low
    high = max(values) if high is None else high

    painter.save()
    painter.fillRect(rect, BACKGROUND)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setBrush(QBrush(TRACE))

    left, top = rect.x(), rect.y()
    width, height = rect.width(), rect.height()

    if low == high:
        # A flat row still deserves a baseline, or the eye reads it as missing.
        if style == "Line":
            painter.setPen(TRACE)
            painter.drawLine(int(left), int(top + height), int(left + width), int(top + height))
        else:
            painter.setPen(Qt.PenStyle.NoPen)
            bar_width = width / len(values)
            for index in range(len(values)):
                painter.drawRect(QRectF(
                    left + index * bar_width,
                    top + height - FLAT_BAR_HEIGHT,
                    max(1.0, bar_width - 0.5),
                    FLAT_BAR_HEIGHT,
                ))
        painter.restore()
        return

    span = high - low
    painter.setPen(Qt.PenStyle.NoPen)

    def normalised(value):
        # Clamp: a per-map scale can legitimately be exceeded by a stale row.
        return max(0.0, min(1.0, (value - low) / span))

    if style == "Line":
        divisor = max(1, len(values) - 1)
        points = [QPointF(left, top + height)]
        points += [
            QPointF(left + index * (width / divisor), top + height - normalised(value) * height)
            for index, value in enumerate(values)
        ]
        points.append(QPointF(left + width, top + height))
        painter.drawPolygon(QPolygonF(points))
    else:
        bar_width = width / len(values)
        for index, value in enumerate(values):
            bar_height = normalised(value) * (height - FLAT_BAR_HEIGHT)
            painter.drawRect(QRectF(
                left + index * bar_width,
                top + height - 1 - bar_height,
                max(1.0, bar_width - 0.5),
                bar_height,
            ))

    painter.restore()


class SparklineWidget(QWidget):
    """Sparkline for one row of a map table, scaled to the whole map's range."""

    def __init__(self, data_row, min_val, max_val, style="Bars"):
        super().__init__()
        self.data = list(data_row)
        self.min_val = min_val
        self.max_val = max_val
        self.style = style
        self.setMinimumWidth(120)

    def paintEvent(self, _event):
        painter = QPainter(self)
        paint_sparkline(
            painter, QRectF(self.rect()), self.data, self.style, self.min_val, self.max_val
        )
