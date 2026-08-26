"""Bottom toolbar: status read-out, comparison mode and map navigation."""

from PyQt6.QtWidgets import QComboBox, QHBoxLayout, QLabel, QPushButton, QWidget

from ...core.state import CompareMode


class ToolbarWidget(QWidget):
    def __init__(self, main_window):
        super().__init__()
        self.main_window = main_window
        self.init_ui()

    def init_ui(self):
        mw = self.main_window
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        mw.status_lbl = QLabel("Hover over the graph to see values...")
        mw.status_lbl.setStyleSheet(
            "background-color: #222; color: #FFF; font-weight: bold;"
            "font-size: 14px; padding: 8px; border-radius: 4px;"
        )

        # Built from the enum, so combo order and enum values cannot drift apart.
        mw.cmb_compare_mode = QComboBox()
        mw.cmb_compare_mode.addItems(CompareMode.labels())
        mw.cmb_compare_mode.setCurrentIndex(int(mw.compare_mode))
        mw.cmb_compare_mode.currentIndexChanged.connect(mw.on_compare_mode_changed)

        mw.btn_set_ref = QPushButton("Set Reference Map")
        mw.btn_set_ref.setToolTip("Set current map as Reference for comparison")
        mw.btn_set_ref.clicked.connect(mw.set_reference_map)

        mw.btn_prev_map = QPushButton("<- Prev Map")
        mw.btn_prev_map.clicked.connect(mw.prev_map)

        mw.btn_next_map = QPushButton("Next Map ->")
        mw.btn_next_map.clicked.connect(mw.next_map)

        layout.addWidget(mw.status_lbl, 1)
        layout.addWidget(mw.cmb_compare_mode)
        layout.addWidget(mw.btn_set_ref)
        layout.addWidget(mw.btn_prev_map)
        layout.addWidget(mw.btn_next_map)
