"""Paints map outlines and row sparklines over the hex table."""

from PyQt6.QtCore import QRectF, Qt
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import QStyledItemDelegate

from .sparkline_widget import paint_sparkline

TAG_BACKGROUND = QColor(0, 0, 0, 180)
TAG_FONT_SIZE = 8
OUTLINE_WIDTH = 2

TOP, BOTTOM, LEFT, RIGHT = 1, 2, 4, 8


class HexMapDelegate(QStyledItemDelegate):
    def paint(self, painter, option, index):
        spark = index.data(Qt.ItemDataRole.UserRole + 1)
        if spark:
            paint_sparkline(painter, QRectF(option.rect), spark["values"], spark["style"])
            return

        super().paint(painter, option, index)

        overlay = index.data(Qt.ItemDataRole.UserRole)
        if not overlay:
            return

        edges = overlay.get("edges", 0)
        colour = overlay.get("color")
        tag = overlay.get("tag", "")

        painter.save()
        pen = painter.pen()
        pen.setColor(colour)
        pen.setWidth(OUTLINE_WIDTH)
        painter.setPen(pen)

        rect = option.rect
        x, y = rect.x(), rect.y()
        right, bottom = rect.right() - 1, rect.bottom() - 1

        if edges & TOP:
            painter.drawLine(x, y, right, y)
        if edges & BOTTOM:
            painter.drawLine(x, bottom, right, bottom)
        if edges & LEFT:
            painter.drawLine(x, y, x, bottom)
        if edges & RIGHT:
            painter.drawLine(right, y, right, bottom)

        # The label is drawn once, on the map's first byte.
        if tag:
            font = painter.font()
            font.setPointSize(TAG_FONT_SIZE)
            font.setBold(True)
            painter.setFont(font)
            metrics = painter.fontMetrics()
            label_rect = QRectF(x, y, metrics.horizontalAdvance(tag) + 6, metrics.height() + 2)
            painter.fillRect(label_rect, TAG_BACKGROUND)
            painter.setPen(colour)
            painter.drawText(label_rect, Qt.AlignmentFlag.AlignCenter, tag)

        painter.restore()
