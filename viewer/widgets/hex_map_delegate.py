from PyQt6.QtWidgets import QStyledItemDelegate
from PyQt6.QtCore import Qt, QRectF, QPointF
from PyQt6.QtGui import QPainter, QColor, QBrush, QPolygonF

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

