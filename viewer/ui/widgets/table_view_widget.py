from PyQt6.QtWidgets import QWidget, QSplitter, QTableWidget, QAbstractItemView, QTableView, QStackedWidget
from PyQt6.QtCore import Qt
from widgets.hex_map_delegate import HexMapDelegate

class TableViewWidget(QStackedWidget):
    def __init__(self, main_window):
        super().__init__()
        self.main_window = main_window
        self.init_ui()

    def init_ui(self):
        # Qt Table
        self.table_split = QSplitter(Qt.Orientation.Horizontal)
        self.main_window.table = QTableWidget()
        self.main_window.table.itemChanged.connect(self.main_window.on_table_edit)
        self.main_window.table_orig = QTableWidget()
        self.main_window.table_orig.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.main_window.table_orig.setVisible(False)
        self.table_split.addWidget(self.main_window.table)
        self.table_split.addWidget(self.main_window.table_orig)
        self.addWidget(self.table_split)
        
        self.main_window.table.verticalScrollBar().valueChanged.connect(self.main_window.table_orig.verticalScrollBar().setValue)
        self.main_window.table_orig.verticalScrollBar().valueChanged.connect(self.main_window.table.verticalScrollBar().setValue)
        self.main_window.table.horizontalScrollBar().valueChanged.connect(self.main_window.table_orig.horizontalScrollBar().setValue)
        self.main_window.table_orig.horizontalScrollBar().valueChanged.connect(self.main_window.table.horizontalScrollBar().setValue)

        # Hex Table
        self.main_window.hex_table = QTableView()
        self.main_window.hex_table.setItemDelegate(HexMapDelegate())
        self.main_window.hex_table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.main_window.hex_table.customContextMenuRequested.connect(self.main_window.show_hex_context_menu)
        self.addWidget(self.main_window.hex_table)
        
        self.main_window.table_split = self.table_split
