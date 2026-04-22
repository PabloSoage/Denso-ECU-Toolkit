import os
from PyQt6.QtWidgets import (QCheckBox, QWidget, QVBoxLayout, QHBoxLayout, QComboBox, 
                             QLabel, QLineEdit, QPushButton, QMenu, QListWidget, QListWidgetItem, QInputDialog, QMessageBox)

class LeftPanelWidget(QWidget):
    def __init__(self, main_window):
        super().__init__()
        self.main_window = main_window
        self.data_manager = main_window.data_manager
        
        self.init_ui()

    def init_ui(self):
        self.layout = QVBoxLayout(self)
        
        self.main_window.cmb_map_type = QComboBox()
        self.main_window.cmb_map_type.addItems(["3D Maps", "2D Maps", "Hexdump Tags", "All"])
        self.main_window.cmb_map_type.currentIndexChanged.connect(self.main_window.on_map_type_changed)
        self.layout.addWidget(self.main_window.cmb_map_type)
        
        if self.main_window.map_mode == '2d':
            self.main_window.cmb_map_type.setCurrentIndex(1)
        elif self.main_window.map_mode == 'tags':
            self.main_window.cmb_map_type.setCurrentIndex(2)

        self.layout.addWidget(QLabel("<b>Search Map Address/Tag:</b>"))

        search_layout = QHBoxLayout()
        self.main_window.search_box = QLineEdit()
        self.main_window.search_box.textChanged.connect(self.main_window.update_list)
        
        self.main_window.btn_tag_filter = QPushButton("Tags Filter")
        self.main_window.tag_filter_menu = QMenu(self)
        self.main_window.btn_tag_filter.setMenu(self.main_window.tag_filter_menu)
        
        search_layout.addWidget(self.main_window.search_box)
        search_layout.addWidget(self.main_window.btn_tag_filter)
        self.layout.addLayout(search_layout)

        self.main_window.cb_smart_filter = QCheckBox("Smart Axis Filter (Hide Noise)")
        self.main_window.cb_smart_filter.setChecked(False)
        self.main_window.cb_smart_filter.toggled.connect(lambda checked: self.main_window.update_list())
        self.layout.addWidget(self.main_window.cb_smart_filter)
        
        self.main_window.map_listbox = QListWidget()
        self.main_window.map_listbox.itemSelectionChanged.connect(self.main_window.on_list_select)
        self.layout.addWidget(self.main_window.map_listbox)
        
        # Tags and project management
        hbox_tags = QHBoxLayout()

        self.main_window.btn_edit_tags = QPushButton("Edit Tags ▼")
        self.main_window.edit_tags_menu = QMenu(self)
        
        action_wrapper = self.main_window.edit_tags_menu.addAction("Map Tag")
        action_wrapper.triggered.connect(lambda: self.main_window.edit_specific_tag('wrapper'))
        
        action_map = self.main_window.edit_tags_menu.addAction("Z Data Tag")
        action_map.triggered.connect(lambda: self.main_window.edit_specific_tag('z'))
        
        action_x = self.main_window.edit_tags_menu.addAction("X Axis Tag")
        action_x.triggered.connect(lambda: self.main_window.edit_specific_tag('x'))
        
        action_y = self.main_window.edit_tags_menu.addAction("Y Axis Tag")
        action_y.triggered.connect(lambda: self.main_window.edit_specific_tag('y'))
        
        self.main_window.btn_edit_tags.setMenu(self.main_window.edit_tags_menu)
        hbox_tags.addWidget(self.main_window.btn_edit_tags)
        
        self.main_window.btn_edit_dims = QPushButton("Edit Dimensions")
        self.main_window.btn_edit_dims.clicked.connect(self.main_window.edit_current_tag_dimensions)
        self.main_window.btn_edit_dims.setVisible(False)
        hbox_tags.addWidget(self.main_window.btn_edit_dims)
        
        self.layout.addLayout(hbox_tags)
        
        hbox_proj = QHBoxLayout()
        btn_load_proj = QPushButton("Load Proj")
        btn_load_proj.clicked.connect(self.main_window.load_project)
        btn_save_proj = QPushButton("Save Proj")
        btn_save_proj.clicked.connect(self.main_window.save_project)
        hbox_proj.addWidget(btn_load_proj)
        hbox_proj.addWidget(btn_save_proj)
        self.layout.addLayout(hbox_proj)

        hbox_bin = QHBoxLayout()
        self.main_window.btn_export_bin = QPushButton("Export Mod. Bin")
        self.main_window.btn_export_bin.setToolTip("Export the binary with all your modifications")
        self.main_window.btn_export_bin.clicked.connect(self.main_window.export_modified_bin)
        self.main_window.btn_load_ref = QPushButton("Load Ref. Bin")
        self.main_window.btn_load_ref.setToolTip("Load an external binary to use for Ext. Ref comparisons")
        self.main_window.btn_load_ref.clicked.connect(self.main_window.load_reference_bin)
        hbox_bin.addWidget(self.main_window.btn_export_bin)
        hbox_bin.addWidget(self.main_window.btn_load_ref)
        self.layout.addLayout(hbox_bin)

