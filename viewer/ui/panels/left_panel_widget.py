"""Left panel: map type, search, tag filters, the map list and file actions."""

from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QMenu,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ...core.state import MapMode

MAP_TYPE_LABELS = ["3D Maps", "2D Maps", "Hexdump Tags", "All"]


class LeftPanelWidget(QWidget):
    def __init__(self, main_window):
        super().__init__()
        self.main_window = main_window
        self.init_ui()

    def init_ui(self):
        mw = self.main_window
        layout = QVBoxLayout(self)

        mw.cmb_map_type = QComboBox()
        mw.cmb_map_type.addItems(MAP_TYPE_LABELS)
        mw.cmb_map_type.setCurrentIndex(mw.map_mode.combo_index)
        mw.cmb_map_type.currentIndexChanged.connect(mw.on_map_type_changed)
        layout.addWidget(mw.cmb_map_type)

        layout.addWidget(QLabel("<b>Search Map Address/Tag:</b>"))

        search_layout = QHBoxLayout()
        mw.search_box = QLineEdit()
        mw.search_box.setPlaceholderText("Address or tag…")
        mw.search_box.setClearButtonEnabled(True)
        # Debounced: rebuilding the list decodes axes for every candidate row.
        mw.search_box.textChanged.connect(mw.request_list_update)
        search_layout.addWidget(mw.search_box)

        mw.btn_tag_filter = QPushButton("Tags Filter")
        mw.tag_filter_menu = QMenu(self)
        mw.btn_tag_filter.setMenu(mw.tag_filter_menu)
        search_layout.addWidget(mw.btn_tag_filter)
        layout.addLayout(search_layout)

        mw.cb_smart_filter = QCheckBox("Smart Axis Filter (Hide Noise)")
        mw.cb_smart_filter.setToolTip(
            "Hide candidates whose axes are not monotonic — the cheapest way to\n"
            "separate real calibration maps from structural coincidences."
        )
        mw.cb_smart_filter.setChecked(False)
        mw.cb_smart_filter.toggled.connect(lambda _checked: mw.update_list())
        layout.addWidget(mw.cb_smart_filter)

        mw.map_listbox = QListWidget()
        mw.map_listbox.itemSelectionChanged.connect(mw.on_list_select)
        layout.addWidget(mw.map_listbox)

        layout.addLayout(self._tag_buttons())
        layout.addLayout(self._project_buttons())
        layout.addLayout(self._binary_buttons())

    def _tag_buttons(self):
        mw = self.main_window
        row = QHBoxLayout()

        mw.btn_edit_tags = QPushButton("Edit Tags ▼")
        mw.edit_tags_menu = QMenu(self)
        for label, target in (
            ("Map Tag", "wrapper"),
            ("Z Data Tag", "z"),
            ("X Axis Tag", "x"),
            ("Y Axis Tag", "y"),
        ):
            action = mw.edit_tags_menu.addAction(label)
            action.triggered.connect(lambda _checked, t=target: mw.edit_specific_tag(t))
        mw.btn_edit_tags.setMenu(mw.edit_tags_menu)
        row.addWidget(mw.btn_edit_tags)

        mw.btn_edit_dims = QPushButton("Edit Dimensions")
        mw.btn_edit_dims.clicked.connect(mw.edit_current_tag_dimensions)
        mw.btn_edit_dims.setVisible(mw.map_mode in (MapMode.TAGS, MapMode.ALL))
        row.addWidget(mw.btn_edit_dims)
        return row

    def _project_buttons(self):
        mw = self.main_window
        row = QHBoxLayout()
        load = QPushButton("Load Proj")
        load.clicked.connect(mw.load_project)
        save = QPushButton("Save Proj")
        save.clicked.connect(mw.save_project)
        row.addWidget(load)
        row.addWidget(save)
        return row

    def _binary_buttons(self):
        mw = self.main_window
        row = QHBoxLayout()

        mw.btn_export_bin = QPushButton("Export Mod. Bin")
        mw.btn_export_bin.setToolTip(
            "Write the patched binary. Checksums are NOT recalculated —\n"
            "you will be shown what changed before anything is written."
        )
        mw.btn_export_bin.clicked.connect(mw.export_modified_bin)
        row.addWidget(mw.btn_export_bin)

        mw.btn_load_ref = QPushButton("Load Ref. Bin")
        mw.btn_load_ref.setToolTip("Load an external binary for Ext. Ref comparisons")
        mw.btn_load_ref.clicked.connect(mw.load_reference_bin)
        row.addWidget(mw.btn_load_ref)
        return row
