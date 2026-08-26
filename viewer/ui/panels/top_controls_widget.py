"""Top row: title, DTC link, and the view/mode toggles."""

from PyQt6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QSpinBox, QWidget


class TopControlsWidget(QWidget):
    def __init__(self, main_window):
        super().__init__()
        self.main_window = main_window
        self.init_ui()

    def init_ui(self):
        mw = self.main_window
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        mw.lbl_title = QLabel("Map Info")
        mw.lbl_title.setStyleSheet("font-size: 14px; font-weight: bold;")
        layout.addWidget(mw.lbl_title)

        mw.btn_dtc_info = QPushButton("DTC Link")
        mw.btn_dtc_info.setStyleSheet("background-color: #ffcc00; color: #000; font-weight: bold;")
        mw.btn_dtc_info.setToolTip("Show the RAM variable and consumer function linked to this map")
        mw.btn_dtc_info.clicked.connect(mw.show_dtc_tracker)
        mw.btn_dtc_info.setVisible(False)
        layout.addWidget(mw.btn_dtc_info)

        layout.addStretch()

        mw.spin_hex_cols = QSpinBox()
        mw.spin_hex_cols.setRange(1, 256)
        mw.spin_hex_cols.setValue(mw.hex_row_width)
        mw.spin_hex_cols.setPrefix("Cols: ")
        mw.spin_hex_cols.valueChanged.connect(mw.on_hex_cols_changed)
        layout.addWidget(mw.spin_hex_cols)

        mw.btn_hex = QPushButton("Dec / Hex")
        mw.btn_hex.clicked.connect(mw.toggle_hex)
        layout.addWidget(mw.btn_hex)

        mw.btn_hex_plot_toggle = QPushButton("Hex Plot: ON")
        mw.btn_hex_plot_toggle.clicked.connect(mw.toggle_hex_plot)
        layout.addWidget(mw.btn_hex_plot_toggle)

        mw.btn_hex_plot_mode = QPushButton("Plot Mode: 3D")
        mw.btn_hex_plot_mode.clicked.connect(mw.toggle_hex_plot_mode)
        layout.addWidget(mw.btn_hex_plot_mode)

        # Kept visible: cycling the mode directly is what the settings dialog
        # used to fake by rewriting this button's label to the previous mode.
        mw.btn_main_mode = QPushButton("Mode: Map Viewer")
        mw.btn_main_mode.setToolTip("Cycle: Map Viewer -> Hex Dump -> Potential Maps")
        mw.btn_main_mode.clicked.connect(mw.toggle_main_mode)
        layout.addWidget(mw.btn_main_mode)

        mw.btn_toggle = QPushButton("View: Plot")
        mw.btn_toggle.clicked.connect(mw.toggle_view)
        layout.addWidget(mw.btn_toggle)

        btn_map_settings = QPushButton("⚙ Map Settings")
        btn_map_settings.clicked.connect(mw.open_custom_map_settings)
        layout.addWidget(btn_map_settings)

        btn_settings = QPushButton("⚙ Global Settings")
        btn_settings.clicked.connect(mw.open_settings)
        layout.addWidget(btn_settings)
