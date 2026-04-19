from PyQt6.QtWidgets import QWidget
from PyQt6.QtCore import Qt, QPointF, QRectF
from PyQt6.QtGui import QPainter, QColor, QPolygonF, QBrush

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


