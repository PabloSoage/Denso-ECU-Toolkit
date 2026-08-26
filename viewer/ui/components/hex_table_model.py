"""Lazy table model over the whole ROM.

Only the visible cells are ever decoded, so a 1.5 MB image maps instantly.
"""

from PyQt6.QtCore import QAbstractTableModel, QModelIndex, Qt

from ...core import formats

#: Extra column appended after the data columns, holding the row sparkline.
PROFILE_HEADER = "Profile"


class HexTableModel(QAbstractTableModel):
    def __init__(self, bin_data, map_array, map_dicts, fmt=">B", sparkline_style="Bars", row_width=16):
        super().__init__()
        self.bin_data = b""
        self.map_array = None
        self.map_dicts = {}
        self.fmt = formats.DEFAULT_FORMAT
        self.row_width = row_width
        self.bytes_per_col = 1
        self.data_cols = 1
        self.sparkline_style = sparkline_style
        self.update_settings(bin_data, map_array, map_dicts, fmt, sparkline_style, row_width)

    def update_settings(self, bin_data, map_array, map_dicts, fmt, sparkline_style, row_width=16):
        self.beginResetModel()
        self.bin_data = bin_data if bin_data is not None else b""
        self.map_array = map_array
        self.map_dicts = map_dicts or {}
        self.fmt = formats.normalise(fmt)
        self.row_width = max(1, int(row_width))
        # value_size knows about 32-bit integers; the old inline chain did not,
        # so choosing "32-bit" used to lay the grid out one byte per column.
        self.bytes_per_col = formats.value_size(self.fmt)
        self.data_cols = max(1, self.row_width // self.bytes_per_col)
        self.sparkline_style = sparkline_style
        self.endResetModel()

    @property
    def endian(self):
        return formats.byte_order(self.fmt)

    @property
    def fmt_char(self):
        return formats.type_char(self.fmt)

    # ------------------------------------------------------------------

    def rowCount(self, parent=QModelIndex()):
        if parent.isValid() or not self.bin_data:
            return 0
        return (len(self.bin_data) + self.row_width - 1) // self.row_width

    def columnCount(self, parent=QModelIndex()):
        if parent.isValid():
            return 0
        return self.data_cols + 1

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if role != Qt.ItemDataRole.DisplayRole:
            return None
        if orientation == Qt.Orientation.Horizontal:
            if section == self.data_cols:
                return PROFILE_HEADER
            return f"{section * self.bytes_per_col:02X}"
        return f"{section * self.row_width:08X}"

    def _address(self, index):
        return index.row() * self.row_width + index.column() * self.bytes_per_col

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None

        if index.column() == self.data_cols:
            return self._sparkline_data(index) if role == Qt.ItemDataRole.UserRole + 1 else None

        if role == Qt.ItemDataRole.TextAlignmentRole:
            return Qt.AlignmentFlag.AlignCenter
        if role == Qt.ItemDataRole.DisplayRole:
            return self._cell_text(self._address(index))
        if role == Qt.ItemDataRole.UserRole:
            return self._overlay(index)
        return None

    def _cell_text(self, address):
        if address + self.bytes_per_col > len(self.bin_data):
            return "??"
        chunk = bytes(self.bin_data[address:address + self.bytes_per_col])
        # Always shown as raw hex digits: this is a hex dump, not a value view.
        return chunk.hex().upper() if self.endian == ">" else chunk[::-1].hex().upper()

    def _sparkline_data(self, index):
        start = index.row() * self.row_width
        end = min(start + self.row_width, len(self.bin_data))
        try:
            count = (end - start) // self.bytes_per_col
            if count <= 0:
                return None
            values = formats.unpack_array(self.bin_data, self.fmt, count, start)
        except ValueError:
            return None
        return {"values": list(values), "style": self.sparkline_style}

    def _overlay(self, index):
        """Border mask + colour for the map this byte belongs to, if any."""
        map_array = self.map_array
        if map_array is None or len(map_array) == 0:
            return None

        address = self._address(index)
        if address >= len(map_array):
            return None

        map_id = int(map_array[address])
        if map_id == -1:
            return None

        info = self.map_dicts.get(map_id)
        if not info:
            return None

        def same(other):
            return 0 <= other < len(map_array) and int(map_array[other]) == map_id

        edges = 0
        if not same(address - self.row_width):
            edges |= 1  # top
        if not same(address + self.row_width):
            edges |= 2  # bottom
        if index.column() == 0 or not same(address - self.bytes_per_col):
            edges |= 4  # left
        if index.column() == self.data_cols - 1 or not same(address + self.bytes_per_col):
            edges |= 8  # right

        return {
            "edges": edges,
            "color": info["color"],
            "tag": info["tag"] if info["addr"] == address else "",
        }
