from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QLabel, QCheckBox, 
                             QGroupBox, QFormLayout, QComboBox, QDoubleSpinBox, 
                             QDialogButtonBox, QTabWidget, QWidget, QHBoxLayout,
                             QRadioButton, QLineEdit, QPushButton, QFileDialog)

class SettingsDialog(QDialog):
    def __init__(self, main_window):
        super().__init__(main_window)
        self.main_window = main_window
        self.data_manager = main_window.data_manager
        self.init_ui()
        
    def init_ui(self):
        
        self.setWindowTitle("Settings")
        self.resize(450, 480)
        layout = QVBoxLayout(self)
        
        tabs = QTabWidget()
        layout.addWidget(tabs)
        
        # TAB 1: FILES & MODE
        tab_files = QWidget()
        vbox_f = QVBoxLayout(tab_files)
        
        gb_mode = QGroupBox("Visualization Mode")
        ly_mode = QHBoxLayout()
                
        gb_engine = QGroupBox("Render Engine")
        ly_engine = QHBoxLayout()
        self.main_window.rb_mpl = QRadioButton("Matplotlib (Slow, Hover)")
        self.main_window.rb_pg = QRadioButton("PyQtGraph (Fast, No Hover)")
        if self.main_window.render_engine == 'matplotlib': self.main_window.rb_mpl.setChecked(True)
        else: self.main_window.rb_pg.setChecked(True)
        ly_engine.addWidget(self.main_window.rb_mpl)
        ly_engine.addWidget(self.main_window.rb_pg)
        gb_engine.setLayout(ly_engine)
        vbox_f.addWidget(gb_engine)
        
        rb_m1 = QRadioButton("3D Maps")
        rb_m2 = QRadioButton("2D Curves")
        rb_m3 = QRadioButton("Hexdump Tags")
        rb_m4 = QRadioButton("All (Dropdown)")
        
        # We need a new state variable to know if we are in 'All' mode or a forced restriction from settings
        # Let's say if the dropdown is visible, we are in 'All' mode. By default let's use the combo state.
        if self.main_window.cmb_map_type.isVisible():
            rb_m4.setChecked(True)
        elif self.main_window.map_mode == 'tags':
            rb_m3.setChecked(True)
        elif self.main_window.map_mode == '2d':
            rb_m2.setChecked(True)
        else:
            rb_m1.setChecked(True)
            
        ly_mode.addWidget(rb_m1); ly_mode.addWidget(rb_m2); ly_mode.addWidget(rb_m3); ly_mode.addWidget(rb_m4)
        gb_mode.setLayout(ly_mode)
        vbox_f.addWidget(gb_mode)
        
        gb_main = QGroupBox("Main Application Mode")
        ly_main = QHBoxLayout()
        rb_main_map = QRadioButton("Map Viewer")
        rb_main_hex = QRadioButton("Hex Dump")
        if self.main_window.btn_main_mode.text() == "Mode: Hex Dump":
            rb_main_hex.setChecked(True)
        else:
            rb_main_map.setChecked(True)
        ly_main.addWidget(rb_main_map); ly_main.addWidget(rb_main_hex)
        gb_main.setLayout(ly_main)
        vbox_f.addWidget(gb_main)

        def add_file_row(parent, label, current_path):
            lay = QHBoxLayout()
            lay.addWidget(QLabel(label))
            le = QLineEdit(current_path)
            btn = QPushButton("...")
            btn.setFixedWidth(30)
            def browse():
                path, _ = QFileDialog.getOpenFileName(self, "Select File")
                if path: le.setText(path)
            btn.clicked.connect(browse)
            lay.addWidget(le)
            lay.addWidget(btn)
            parent.addLayout(lay)
            return le
            
        vbox_f.addWidget(QLabel("<b>Paths:</b>"))
        le_bin = add_file_row(vbox_f, "BIN File:", self.main_window.data_manager.bin_path)
        le_3d = add_file_row(vbox_f, "3D CSV:", self.main_window.data_manager.csv_3d_path)
        le_2d = add_file_row(vbox_f, "2D CSV:", self.main_window.data_manager.csv_2d_path)
        le_dtc = add_file_row(vbox_f, "DTC CSV:", getattr(self.main_window.data_manager, 'csv_dtc_path', ''))
        vbox_f.addStretch()
        tabs.addTab(tab_files, "Files & Mode")
        
        # TAB 2: FORMAT 
        tab_fmt = QWidget()
        vbox_fmt = QVBoxLayout(tab_fmt)
        
        def parse_fmt(f_str):
            if not f_str: return "16-bit", ">", False
            endian = "<" if "<" in f_str else ">"
            c = f_str[-1].lower()
            if c == 'f': size = "Float"
            elif c == 'b': size = "8-bit"
            elif c == 'i' or c == 'l': size = "32-bit"
            else: size = "16-bit" # default H/h
            signed = f_str[-1].islower()
            if size == 'Float': signed = True
            return size, endian, signed

        size3, end3, sign3 = parse_fmt(self.main_window.data_manager.z_format_3d)
        size2, end2, sign2 = parse_fmt(self.main_window.data_manager.z_format_2d)
        
        # Determine global values (fallback to 3D if they mismatch)
        is_little_endian = (end3 == "<")
        is_signed = sign3

        gb_global = QGroupBox("Global Rules")
        ly_global = QVBoxLayout()
        
        self.main_window.cb_endian = QCheckBox("Little Endian (LoHi) - Uncheck for Big Endian (HiLo)")
        self.main_window.cb_endian.setChecked(is_little_endian)
        ly_global.addWidget(self.main_window.cb_endian)
        
        self.main_window.cb_signed = QCheckBox("Signed - Uncheck for Unsigned")
        self.main_window.cb_signed.setChecked(is_signed)
        ly_global.addWidget(self.main_window.cb_signed)
        
        gb_global.setLayout(ly_global)
        vbox_fmt.addWidget(gb_global)

        gb_sizes = QGroupBox("Data Sizes")
        ly_sizes = QFormLayout()
        
        self.main_window.cmb_3d = QComboBox()
        self.main_window.cmb_3d.addItems(["8-bit", "16-bit", "32-bit", "Float"])
        self.main_window.cmb_3d.setCurrentText(size3)
        ly_sizes.addRow("3D Data Size:", self.main_window.cmb_3d)

        self.main_window.cmb_2d = QComboBox()
        self.main_window.cmb_2d.addItems(["8-bit", "16-bit", "32-bit", "Float"])
        self.main_window.cmb_2d.setCurrentText(size2)
        ly_sizes.addRow("2D Data Size:", self.main_window.cmb_2d)

        sz_ax_map = {'b': '8-bit', 'h': '16-bit', 'i': '32-bit', 'f': 'Float'}
        sz_a_char = self.main_window.data_manager.ax_format.lower() if self.main_window.data_manager.ax_format else 'h'
        size_a = sz_ax_map.get(sz_a_char, '16-bit')

        self.main_window.cmb_ax = QComboBox()
        self.main_window.cmb_ax.addItems(["8-bit", "16-bit", "32-bit", "Float"])
        self.main_window.cmb_ax.setCurrentText(size_a)
        ly_sizes.addRow("Axis Size:", self.main_window.cmb_ax)
        
        gb_sizes.setLayout(ly_sizes)
        vbox_fmt.addWidget(gb_sizes)

        vbox_fmt.addStretch()
        tabs.addTab(tab_fmt, "Format")
        
        # TAB 3: MATH, VIEW & CONTROLS
        tab_math = QWidget()
        vbox_m = QVBoxLayout(tab_math)
        
        gb_math = QGroupBox("Math (Applied to Z/Curve)")
        form_m = QFormLayout()
        
        spin_f_3d = QDoubleSpinBox()
        spin_f_3d.setDecimals(5)
        spin_f_3d.setSingleStep(0.001)
        spin_f_3d.setRange(-10000, 10000)
        spin_f_3d.setValue(self.main_window.factor_z_3d)
        
        spin_o_3d = QDoubleSpinBox()
        spin_o_3d.setRange(-10000, 10000)
        spin_o_3d.setValue(self.main_window.offset_z_3d)
        
        spin_f_2d = QDoubleSpinBox()
        spin_f_2d.setDecimals(5)
        spin_f_2d.setSingleStep(0.001)
        spin_f_2d.setRange(-10000, 10000)
        spin_f_2d.setValue(self.main_window.factor_z_2d)
        
        spin_o_2d = QDoubleSpinBox()
        spin_o_2d.setRange(-10000, 10000)
        spin_o_2d.setValue(self.main_window.offset_z_2d)
        
        form_m.addRow("Factor 3D:", spin_f_3d)
        form_m.addRow("Offset 3D:", spin_o_3d)
        form_m.addRow("Factor 2D:", spin_f_2d)
        form_m.addRow("Offset 2D:", spin_o_2d)
        gb_math.setLayout(form_m)
        vbox_m.addWidget(gb_math)
        
        # Table and Hex Settings
        gb_tbl = QGroupBox("Table & Hex Settings")
        ly_tbl = QVBoxLayout()
        self.main_window.cb_hex_f = QCheckBox("Apply Factor/Offset to Hex View (Table)")
        self.main_window.cb_hex_f.setChecked(self.main_window.apply_factor_to_hex)
        ly_tbl.addWidget(self.main_window.cb_hex_f)
        
        self.main_window.cb_hl_3d = QCheckBox("Highlight 3D Maps in Hex Mode (Blue)")
        self.main_window.cb_hl_3d.setChecked(self.main_window.highlight_3d)
        ly_tbl.addWidget(self.main_window.cb_hl_3d)
        
        self.main_window.cb_hl_2d = QCheckBox("Highlight 2D Maps in Hex Mode (Green)")
        self.main_window.cb_hl_2d.setChecked(self.main_window.highlight_2d)
        ly_tbl.addWidget(self.main_window.cb_hl_2d)
        
        self.main_window.cb_hl_custom = QCheckBox("Highlight Custom Tags in Hex Mode (Orange)")
        self.main_window.cb_hl_custom.setChecked(self.main_window.highlight_custom_tags)
        ly_tbl.addWidget(self.main_window.cb_hl_custom)
        
        self.main_window.cb_hl_custom = QCheckBox("Highlight Custom Tags in Hex Mode (Orange)")
        self.main_window.cb_hl_custom.setChecked(self.main_window.highlight_custom_tags)
        ly_tbl.addWidget(self.main_window.cb_hl_custom)
        
        ly_spark = QHBoxLayout()
        ly_spark.addWidget(QLabel("Sparkline Style:"))
        rb_sp1 = QRadioButton("Bars (WinOLS)")
        rb_sp2 = QRadioButton("Continuous Line")
        if self.main_window.sparkline_style == 'Bars': rb_sp1.setChecked(True)
        else: rb_sp2.setChecked(True)
        ly_spark.addWidget(rb_sp1); ly_spark.addWidget(rb_sp2)
        ly_tbl.addLayout(ly_spark)
        
        gb_hex_pos = QGroupBox("Hex Dump Plot Position")
        ly_hex_pos = QHBoxLayout()
        rb_pos_top = QRadioButton("Top")
        rb_pos_right = QRadioButton("Right")
        if self.main_window.hex_plot_position == 'top': rb_pos_top.setChecked(True)
        else: rb_pos_right.setChecked(True)
        ly_hex_pos.addWidget(rb_pos_top); ly_hex_pos.addWidget(rb_pos_right)
        gb_hex_pos.setLayout(ly_hex_pos)
        ly_tbl.addWidget(gb_hex_pos)
        
        gb_tbl.setLayout(ly_tbl)
        vbox_m.addWidget(gb_tbl)
        
        gb_r = QGroupBox("3D Mouse Rotation Mode")
        ly_r = QVBoxLayout()
        rb_r1 = QRadioButton("Z-Axis Only (WinOLS Azimuth)")
        rb_r2 = QRadioButton("WinOLS Style (Azimuth & Tilt)")
        rb_r3 = QRadioButton("Tilt Only (Elevation)")
        if self.main_window.rot_mode == 'Z': rb_r1.setChecked(True)
        elif self.main_window.rot_mode == 'WinOLS': rb_r2.setChecked(True)
        else: rb_r3.setChecked(True)
        ly_r.addWidget(rb_r1); ly_r.addWidget(rb_r2); ly_r.addWidget(rb_r3)
        gb_r.setLayout(ly_r)
        vbox_m.addWidget(gb_r)
        
        vbox_m.addStretch()
        tabs.addTab(tab_math, "Math & View")
        
        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)
        
        if self.exec():
            if rb_main_hex.isChecked() and self.main_window.btn_main_mode.text() != "Mode: Hex Dump":
                self.main_window.btn_main_mode.setText("Mode: Map Viewer")
                self.main_window.toggle_main_mode()
            elif rb_main_map.isChecked() and self.main_window.btn_main_mode.text() == "Mode: Hex Dump":
                self.main_window.btn_main_mode.setText("Mode: Hex Dump")
                self.main_window.toggle_main_mode()

            # Update engine
            new_engine = 'matplotlib' if self.main_window.rb_mpl.isChecked() else 'pyqtgraph'
            engine_changed = (new_engine != self.main_window.render_engine)
            if engine_changed:
                self.main_window.render_engine = new_engine

            self.main_window.data_manager.bin_path = le_bin.text()
            self.main_window.data_manager.csv_3d_path = le_3d.text()
            self.main_window.data_manager.csv_2d_path = le_2d.text()
            self.main_window.data_manager.csv_dtc_path = le_dtc.text()
            self.main_window.data_manager.load_dtc_csv()
            
            if rb_m4.isChecked():
                self.main_window.cmb_map_type.setVisible(True)
                modes_list = ['3d', '2d', 'tags', 'all']
                if self.main_window.cmb_map_type.currentIndex() < len(modes_list):
                    new_mode = modes_list[self.main_window.cmb_map_type.currentIndex()]
                else:
                    new_mode = 'all'
            else:
                self.main_window.cmb_map_type.setVisible(False)
                if rb_m1.isChecked(): new_mode = '3d'
                elif rb_m2.isChecked(): new_mode = '2d'
                else: new_mode = 'tags'
                
            if new_mode != self.main_window.map_mode or getattr(self, 'last_dropdown_mode', None) != self.main_window.cmb_map_type.isVisible():
                self.main_window.last_dropdown_mode = self.main_window.cmb_map_type.isVisible()
                self.main_window.map_mode = new_mode
                if self.main_window.btn_main_mode.text() == "Mode: Map Viewer":
                    self.main_window.btn_hex_plot_mode.setVisible(self.main_window.map_mode == 'tags')
                self.main_window.load_data() 
            
            is_little = self.main_window.cb_endian.isChecked()
            is_signed = self.main_window.cb_signed.isChecked()
            endian = '<' if is_little else '>'
            
            def build_fmt(size_str, signed):
                if size_str == 'Float': return 'f'
                elif size_str == '8-bit': char = 'b' if signed else 'B'
                elif size_str == '16-bit': char = 'h' if signed else 'H'
                else: char = 'i' if signed else 'I'
                return char

            char_3d = build_fmt(self.main_window.cmb_3d.currentText(), is_signed)
            self.main_window.data_manager.z_format_3d = endian + char_3d
            
            char_2d = build_fmt(self.main_window.cmb_2d.currentText(), is_signed)
            self.main_window.data_manager.z_format_2d = endian + char_2d
            
            char_ax = build_fmt(self.main_window.cmb_ax.currentText(), is_signed)
            self.main_window.data_manager.ax_format = char_ax
            
            if rb_r1.isChecked(): self.main_window.rot_mode = 'Z'
            elif rb_r2.isChecked(): self.main_window.rot_mode = 'WinOLS'
            else: self.main_window.rot_mode = 'Tilt'
            
            self.main_window.factor_z_3d = spin_f_3d.value()
            self.main_window.offset_z_3d = spin_o_3d.value()
            self.main_window.factor_z_2d = spin_f_2d.value()
            self.main_window.offset_z_2d = spin_o_2d.value()
            
            self.main_window.apply_factor_to_hex = self.main_window.cb_hex_f.isChecked()
            self.main_window.highlight_3d = self.main_window.cb_hl_3d.isChecked()
            self.main_window.highlight_2d = self.main_window.cb_hl_2d.isChecked()
            self.main_window.highlight_custom_tags = self.main_window.cb_hl_custom.isChecked()
            self.main_window.highlight_custom_tags = self.main_window.cb_hl_custom.isChecked()
            self.main_window.sparkline_style = 'Bars' if rb_sp1.isChecked() else 'Line'
            
            new_pos = 'top' if rb_pos_top.isChecked() else 'right'
            if new_pos != self.main_window.hex_plot_position:
                self.main_window.hex_plot_position = new_pos
                if self.main_window.btn_main_mode.text() == "Mode: Hex Dump":
                    self.main_window.apply_splitter_position()
            
            self.main_window.draw_map()

