from PyQt6.QtWidgets import QWidget, QHBoxLayout, QPushButton, QComboBox, QLabel

class ToolbarWidget(QWidget):
    def __init__(self, main_window):
        super().__init__()
        self.main_window = main_window
        self.init_ui()

    def init_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        self.main_window.status_lbl = QLabel("Hover over the graph to see values...")
        self.main_window.status_lbl.setStyleSheet("background-color: #222; color: #FFF; font-weight: bold; font-size: 14px; padding: 8px; border-radius: 4px;")
        
        self.main_window.cmb_compare_mode = QComboBox()
        self.main_window.cmb_compare_mode.addItems([
            "View: Normal",
            "View: Show Original",
            "Compare: Difference (Mod - Orig)",
            "Compare: Difference (%)",
            "Compare: Vs Reference Map",
            "Twin: Side-by-Side (Mod vs Orig)",
            "Twin: Side-by-Side (Mod vs Ref Map)",
            "Compare: Difference (Mod - Ext. Bin)",
            "Twin: Side-by-Side (Mod vs Ext. Bin)"
        ])
        self.main_window.cmb_compare_mode.currentIndexChanged.connect(self.main_window.on_compare_mode_changed)

        self.main_window.btn_set_ref = QPushButton("Set Reference Map")
        self.main_window.btn_set_ref.setToolTip("Set current map as Reference for comparison")
        self.main_window.btn_set_ref.clicked.connect(self.main_window.set_reference_map)

        self.main_window.btn_prev_map = QPushButton("<- Prev Map")
        self.main_window.btn_prev_map.clicked.connect(self.main_window.prev_map)
        
        self.main_window.btn_next_map = QPushButton("Next Map ->")
        self.main_window.btn_next_map.clicked.connect(self.main_window.next_map)

        layout.addWidget(self.main_window.status_lbl, 1)
        layout.addWidget(self.main_window.cmb_compare_mode)
        layout.addWidget(self.main_window.btn_set_ref)
        layout.addWidget(self.main_window.btn_prev_map)
        layout.addWidget(self.main_window.btn_next_map)
