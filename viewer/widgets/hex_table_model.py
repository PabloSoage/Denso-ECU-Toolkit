import struct
from PyQt6.QtCore import Qt, QAbstractTableModel, QModelIndex, QVariant

class HexTableModel(QAbstractTableModel):
    def __init__(self, bin_data, map_array, map_dicts, fmt='>B', sparkline_style='Bars', row_width=16):
        super().__init__()
        self.update_settings(bin_data, map_array, map_dicts, fmt, sparkline_style, row_width)

    def update_settings(self, bin_data, map_array, map_dicts, fmt, sparkline_style, row_width=16):
        self.beginResetModel()
        self.bin_data = bin_data
        self.map_array = map_array
        self.map_dicts = map_dicts
        self.fmt = fmt
        self.row_width = row_width
        self.endian = fmt[0]
        self.fmt_char = fmt[-1]
        
        if self.fmt_char.lower() == 'f': self.bytes_per_col = 4
        elif self.fmt_char.lower() == 'h': self.bytes_per_col = 2
        else: self.bytes_per_col = 1
            
        self.data_cols = max(1, self.row_width // self.bytes_per_col)
        self.sparkline_style = sparkline_style
        self.endResetModel()

    def rowCount(self, parent=QModelIndex()):
        if not self.bin_data: return 0
        return (len(self.bin_data) + self.row_width - 1) // self.row_width

    def columnCount(self, parent=QModelIndex()):
        return self.data_cols + 1

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if role == Qt.ItemDataRole.DisplayRole:
            if orientation == Qt.Orientation.Horizontal:
                if section == self.data_cols:
                    return "Profile"
                return f"{section * self.bytes_per_col:02X}"
            else:
                return f"{section*self.row_width:08X}"
        return QVariant()

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid(): return QVariant()
        
        is_sparkline = (index.column() == self.data_cols)
        
        if is_sparkline:
            if role == Qt.ItemDataRole.UserRole + 1:
                row_addr = index.row() * self.row_width
                end_addr = min(row_addr + self.row_width, len(self.bin_data))
                val_bytes = self.bin_data[row_addr:end_addr]
                values = []
                for i in range(0, len(val_bytes), self.bytes_per_col):
                    chunk = val_bytes[i:i+self.bytes_per_col]
                    if len(chunk) < self.bytes_per_col: break
                    try:
                        val = struct.unpack(f"{self.endian}{self.fmt_char}", chunk)[0]
                        values.append(val)
                    except: pass
                if not values: return QVariant()
                return {'values': values, 'style': self.sparkline_style}
            return QVariant()
            
        col_offset = index.column() * self.bytes_per_col
        addr = index.row() * self.row_width + col_offset
        
        if role == Qt.ItemDataRole.DisplayRole:
            if addr + self.bytes_per_col <= len(self.bin_data):
                val_bytes = self.bin_data[addr:addr+self.bytes_per_col]
                if self.bytes_per_col == 1:
                    return f"{val_bytes[0]:02X}"
                elif self.bytes_per_col == 2:
                    val = struct.unpack(f"{self.endian}H", val_bytes)[0]
                    return f"{val:04X}"
                elif self.bytes_per_col == 4:
                    val = struct.unpack(f"{self.endian}I", val_bytes)[0]
                    return f"{val:08X}"
            return "??"
            
        elif role == Qt.ItemDataRole.UserRole:
            if not self.map_array or addr >= len(self.map_array): return QVariant()
            
            mid = self.map_array[addr]
            if mid == -1: return QVariant()
            
            # Check edge neighbors to determine outlines
            edges = 0
            if addr < self.row_width or self.map_array[addr - self.row_width] != mid: edges |= 1 # Top
            if addr + self.row_width >= len(self.map_array) or self.map_array[addr + self.row_width] != mid: edges |= 2 # Bottom
            if col_offset == 0 or addr == 0 or self.map_array[addr - self.bytes_per_col] != mid: edges |= 4 # Left
            if col_offset + self.bytes_per_col >= self.row_width or addr + self.bytes_per_col >= len(self.map_array) or self.map_array[addr + self.bytes_per_col] != mid: edges |= 8 # Right
            
            info = self.map_dicts.get(mid)
            if not info: return QVariant()
            
            tag = info['tag'] if info['addr'] == addr else ''
            return {'edges': edges, 'color': info['color'], 'tag': tag}
            
        elif role == Qt.ItemDataRole.TextAlignmentRole:
            return Qt.AlignmentFlag.AlignCenter
            
        return QVariant()

