from PyQt6.QtWidgets import QWidget, QHBoxLayout, QPushButton, QLabel, QSpinBox

class TopControlsWidget(QWidget):
    def __init__(self, main_window):
        super().__init__()
        self.main_window = main_window
        self.init_ui()

    def init_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        self.main_window.lbl_title = QLabel("Map Info")
        self.main_window.lbl_title.setStyleSheet("font-size: 14px; font-weight: bold;")
        layout.addWidget(self.main_window.lbl_title)
        
        self.main_window.btn_dtc_info = QPushButton("DTC Link")
        self.main_window.btn_dtc_info.setStyleSheet("background-color: #ffcc00; color: #000; font-weight: bold;")
        self.main_window.btn_dtc_info.clicked.connect(self.main_window.show_dtc_tracker)
        self.main_window.btn_dtc_info.setVisible(False)
        layout.addWidget(self.main_window.btn_dtc_info)
        
        layout.addStretch()

        self.main_window.spin_hex_cols = QSpinBox()
        self.main_window.spin_hex_cols.setRange(1, 256)
        self.main_window.spin_hex_cols.setValue(16)
        self.main_window.spin_hex_cols.setPrefix("Cols: ")
        self.main_window.spin_hex_cols.setVisible(False)
        self.main_window.spin_hex_cols.valueChanged.connect(self.main_window.on_hex_cols_changed)
        layout.addWidget(self.main_window.spin_hex_cols)

        self.main_window.btn_hex = QPushButton("Dec / Hex")
        self.main_window.btn_hex.clicked.connect(self.main_window.toggle_hex)
        self.main_window.btn_hex.setVisible(False)
        layout.addWidget(self.main_window.btn_hex)
        
        self.main_window.btn_hex_plot_toggle = QPushButton("Hex Plot: ON")
        self.main_window.btn_hex_plot_toggle.clicked.connect(self.main_window.toggle_hex_plot)
        self.main_window.btn_hex_plot_toggle.setVisible(False)
        layout.addWidget(self.main_window.btn_hex_plot_toggle)
        
        self.main_window.btn_hex_plot_mode = QPushButton("Plot Mode: 3D")
        self.main_window.btn_hex_plot_mode.clicked.connect(self.main_window.toggle_hex_plot_mode)
        self.main_window.btn_hex_plot_mode.setVisible(False)
        layout.addWidget(self.main_window.btn_hex_plot_mode)
        
        self.main_window.btn_main_mode = QPushButton("Mode: Map Viewer")
        self.main_window.btn_main_mode.clicked.connect(self.main_window.toggle_main_mode)
        self.main_window.btn_main_mode.setVisible(False)
        layout.addWidget(self.main_window.btn_main_mode)
        
        self.main_window.btn_toggle = QPushButton("View: Plot")
        self.main_window.btn_toggle.clicked.connect(self.main_window.toggle_view)
        layout.addWidget(self.main_window.btn_toggle)

        btn_map_settings = QPushButton("⚙ Map Settings")
        btn_map_settings.clicked.connect(self.main_window.open_custom_map_settings)
        layout.addWidget(btn_map_settings)

        btn_settings = QPushButton("⚙ Global Settings")
        btn_settings.clicked.connect(self.main_window.open_settings)
        layout.addWidget(btn_settings)
