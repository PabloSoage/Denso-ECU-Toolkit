"""Stacked bottom area: the map table (page 0) and the hex table (page 1)."""

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QSplitter,
    QStackedWidget,
    QTableView,
    QTableWidget,
)

from ..components.hex_map_delegate import HexMapDelegate

MAP_TABLE_PAGE = 0
HEX_TABLE_PAGE = 1


class TableViewWidget(QStackedWidget):
    def __init__(self, main_window):
        super().__init__()
        self.main_window = main_window
        self.init_ui()

    def init_ui(self):
        mw = self.main_window

        self.table_split = QSplitter(Qt.Orientation.Horizontal)
        mw.table = QTableWidget()
        mw.table.itemChanged.connect(mw.on_table_edit)
        mw.table_orig = QTableWidget()
        mw.table_orig.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        mw.table_orig.setVisible(False)
        self.table_split.addWidget(mw.table)
        self.table_split.addWidget(mw.table_orig)
        self.addWidget(self.table_split)

        self._link_scrollbars(mw.table, mw.table_orig)

        mw.hex_table = QTableView()
        mw.hex_table.setItemDelegate(HexMapDelegate())
        mw.hex_table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        mw.hex_table.customContextMenuRequested.connect(mw.show_hex_context_menu)
        self.addWidget(mw.hex_table)

        mw.table_split = self.table_split

    @staticmethod
    def _link_scrollbars(left, right):
        """Keep the two comparison tables scrolled together.

        The value guard is what stops the two signals bouncing off each other.
        """

        def mirror(target):
            def handler(value):
                if target.value() != value:
                    target.setValue(value)

            return handler

        for accessor in ("verticalScrollBar", "horizontalScrollBar"):
            left_bar = getattr(left, accessor)()
            right_bar = getattr(right, accessor)()
            left_bar.valueChanged.connect(mirror(right_bar))
            right_bar.valueChanged.connect(mirror(left_bar))
