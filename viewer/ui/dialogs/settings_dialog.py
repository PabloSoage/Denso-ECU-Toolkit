"""Global settings: file paths, data formats, maths and view preferences."""

from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from ...core import formats
from ...core.state import (
    AppMode,
    HexPlotPosition,
    MapMode,
    RotationMode,
    SparklineStyle,
)

SIZE_CHOICES = list(formats.SIZE_LABELS)


class SettingsDialog(QDialog):
    def __init__(self, main_window):
        super().__init__(main_window)
        self.main_window = main_window
        self.data_manager = main_window.data_manager
        self.init_ui()

    # ------------------------------------------------------------------

    def init_ui(self):
        self.setWindowTitle("Settings")
        self.resize(470, 520)
        layout = QVBoxLayout(self)

        tabs = QTabWidget()
        tabs.addTab(self._files_tab(), "Files & Mode")
        tabs.addTab(self._format_tab(), "Format")
        tabs.addTab(self._view_tab(), "Math & View")
        layout.addWidget(tabs)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        if self.exec():
            self._apply()

    # ------------------------------------------------------------------
    # Tabs
    # ------------------------------------------------------------------

    def _files_tab(self):
        mw = self.main_window
        dm = self.data_manager

        tab = QWidget()
        box = QVBoxLayout(tab)

        engine = QGroupBox("Render Engine")
        engine_row = QHBoxLayout()
        self.rb_matplotlib = QRadioButton("Matplotlib (slower, hover tooltips)")
        self.rb_pyqtgraph = QRadioButton("PyQtGraph + OpenGL (fast, no hover)")
        self.rb_matplotlib.setChecked(mw.render_engine == "matplotlib")
        self.rb_pyqtgraph.setChecked(mw.render_engine != "matplotlib")
        engine_row.addWidget(self.rb_matplotlib)
        engine_row.addWidget(self.rb_pyqtgraph)
        engine.setLayout(engine_row)
        box.addWidget(engine)

        map_type = QGroupBox("Map List Contents")
        map_row = QHBoxLayout()
        self.rb_map_modes = {
            MapMode.THREE_D: QRadioButton("3D Maps"),
            MapMode.TWO_D: QRadioButton("2D Curves"),
            MapMode.TAGS: QRadioButton("Hexdump Tags"),
        }
        self.rb_map_dropdown = QRadioButton("All (dropdown)")
        # State comes from the flag, not from whether a combo box happens to be
        # visible -- which is how this used to be decided.
        if mw.map_type_dropdown_visible:
            self.rb_map_dropdown.setChecked(True)
        else:
            self.rb_map_modes.get(mw.map_mode, self.rb_map_modes[MapMode.THREE_D]).setChecked(True)
        for button in self.rb_map_modes.values():
            map_row.addWidget(button)
        map_row.addWidget(self.rb_map_dropdown)
        map_type.setLayout(map_row)
        box.addWidget(map_type)

        app_mode = QGroupBox("Main Application Mode")
        app_row = QHBoxLayout()
        self.rb_app_modes = {mode: QRadioButton(mode.value) for mode in AppMode}
        self.rb_app_modes[mw.app_mode].setChecked(True)
        for button in self.rb_app_modes.values():
            app_row.addWidget(button)
        app_mode.setLayout(app_row)
        box.addWidget(app_mode)

        box.addWidget(QLabel("<b>Paths:</b>"))
        self.le_bin = self._file_row(box, "BIN File:", dm.bin_path, "Binary Files (*.bin);;All Files (*)")
        self.le_3d = self._file_row(box, "3D CSV:", dm.csv_3d_path, "CSV Files (*.csv)")
        self.le_2d = self._file_row(box, "2D CSV:", dm.csv_2d_path, "CSV Files (*.csv)")
        self.le_dtc = self._file_row(box, "DTC CSV:", dm.csv_dtc_path, "CSV Files (*.csv)")
        self.le_potential = self._file_row(box, "Potential CSV:", dm.csv_potential_path, "CSV Files (*.csv)")
        box.addStretch()
        return tab

    def _file_row(self, parent_layout, label, current_path, file_filter):
        row = QHBoxLayout()
        row.addWidget(QLabel(label))
        line = QLineEdit(current_path)
        browse = QPushButton("...")
        browse.setFixedWidth(30)

        def pick():
            path, _ = QFileDialog.getOpenFileName(self, f"Select {label}", "", file_filter)
            if path:
                line.setText(path)

        browse.clicked.connect(pick)
        row.addWidget(line)
        row.addWidget(browse)
        parent_layout.addLayout(row)
        return line

    def _format_tab(self):
        dm = self.data_manager
        tab = QWidget()
        box = QVBoxLayout(tab)

        size_3d, order_3d, signed_3d = formats.describe(dm.z_format_3d)
        size_2d, _, _ = formats.describe(dm.z_format_2d)
        size_ax, _, _ = formats.describe(dm.ax_format)

        rules = QGroupBox("Global Rules")
        rules_box = QVBoxLayout()
        self.cb_little_endian = QCheckBox("Little Endian (LoHi) — uncheck for Big Endian (HiLo)")
        self.cb_little_endian.setToolTip("Denso SH705x calibrations are big endian.")
        self.cb_little_endian.setChecked(order_3d == "<")
        self.cb_signed = QCheckBox("Signed — uncheck for Unsigned")
        self.cb_signed.setChecked(signed_3d)
        rules_box.addWidget(self.cb_little_endian)
        rules_box.addWidget(self.cb_signed)
        rules.setLayout(rules_box)
        box.addWidget(rules)

        sizes = QGroupBox("Data Sizes")
        form = QFormLayout()
        self.cmb_3d = self._size_combo(size_3d)
        self.cmb_2d = self._size_combo(size_2d)
        self.cmb_ax = self._size_combo(size_ax)
        form.addRow("3D Data Size:", self.cmb_3d)
        form.addRow("2D Data Size:", self.cmb_2d)
        form.addRow("Axis Size:", self.cmb_ax)
        sizes.setLayout(form)
        box.addWidget(sizes)

        box.addStretch()
        return tab

    @staticmethod
    def _size_combo(current):
        combo = QComboBox()
        combo.addItems(SIZE_CHOICES)
        combo.setCurrentText(current)
        return combo

    def _view_tab(self):
        mw = self.main_window
        tab = QWidget()
        box = QVBoxLayout(tab)

        maths = QGroupBox("Math (applied to Z / Curve)")
        form = QFormLayout()
        self.spin_factor_3d = self._spin(mw.factor_z_3d)
        self.spin_offset_3d = self._spin(mw.offset_z_3d)
        self.spin_factor_2d = self._spin(mw.factor_z_2d)
        self.spin_offset_2d = self._spin(mw.offset_z_2d)
        form.addRow("Factor 3D:", self.spin_factor_3d)
        form.addRow("Offset 3D:", self.spin_offset_3d)
        form.addRow("Factor 2D:", self.spin_factor_2d)
        form.addRow("Offset 2D:", self.spin_offset_2d)
        maths.setLayout(form)
        box.addWidget(maths)

        table = QGroupBox("Table & Hex Settings")
        table_box = QVBoxLayout()
        self.cb_factor_in_hex = QCheckBox("Apply Factor/Offset to Hex View (Table)")
        self.cb_factor_in_hex.setChecked(mw.apply_factor_to_hex)
        self.cb_highlight_3d = QCheckBox("Highlight 3D Maps in Hex Mode (blue)")
        self.cb_highlight_3d.setChecked(mw.highlight_3d)
        self.cb_highlight_2d = QCheckBox("Highlight 2D Maps in Hex Mode (green)")
        self.cb_highlight_2d.setChecked(mw.highlight_2d)
        # Exactly one of these -- the previous version created it twice, so the
        # dialog showed two identical checkboxes and only the second one worked.
        self.cb_highlight_custom = QCheckBox("Highlight Custom Tags in Hex Mode (orange)")
        self.cb_highlight_custom.setChecked(mw.highlight_custom_tags)
        for widget in (
            self.cb_factor_in_hex,
            self.cb_highlight_3d,
            self.cb_highlight_2d,
            self.cb_highlight_custom,
        ):
            table_box.addWidget(widget)

        spark_row = QHBoxLayout()
        spark_row.addWidget(QLabel("Sparkline Style:"))
        self.rb_spark_bars = QRadioButton("Bars (WinOLS)")
        self.rb_spark_line = QRadioButton("Continuous Line")
        self.rb_spark_bars.setChecked(mw.sparkline_style is SparklineStyle.BARS)
        self.rb_spark_line.setChecked(mw.sparkline_style is SparklineStyle.LINE)
        spark_row.addWidget(self.rb_spark_bars)
        spark_row.addWidget(self.rb_spark_line)
        table_box.addLayout(spark_row)

        position = QGroupBox("Hex Dump Plot Position")
        position_row = QHBoxLayout()
        self.rb_plot_top = QRadioButton("Top")
        self.rb_plot_right = QRadioButton("Right")
        self.rb_plot_top.setChecked(mw.hex_plot_position is HexPlotPosition.TOP)
        self.rb_plot_right.setChecked(mw.hex_plot_position is HexPlotPosition.RIGHT)
        position_row.addWidget(self.rb_plot_top)
        position_row.addWidget(self.rb_plot_right)
        position.setLayout(position_row)
        table_box.addWidget(position)

        table.setLayout(table_box)
        box.addWidget(table)

        rotation = QGroupBox("3D Mouse Rotation Mode")
        rotation_box = QVBoxLayout()
        self.rb_rotation = {
            RotationMode.Z_ONLY: QRadioButton("Z-Axis Only (WinOLS azimuth)"),
            RotationMode.WINOLS: QRadioButton("WinOLS Style (azimuth & tilt)"),
            RotationMode.TILT: QRadioButton("Tilt Only (elevation)"),
        }
        self.rb_rotation[mw.rot_mode].setChecked(True)
        for button in self.rb_rotation.values():
            rotation_box.addWidget(button)
        rotation.setLayout(rotation_box)
        box.addWidget(rotation)

        box.addStretch()
        return tab

    @staticmethod
    def _spin(value):
        spin = QDoubleSpinBox()
        spin.setDecimals(5)
        spin.setSingleStep(0.001)
        spin.setRange(-1_000_000, 1_000_000)
        spin.setValue(value)
        return spin

    # ------------------------------------------------------------------
    # Apply
    # ------------------------------------------------------------------

    def _apply(self):
        mw = self.main_window
        dm = self.data_manager

        mw.render_engine = "matplotlib" if self.rb_matplotlib.isChecked() else "pyqtgraph"

        binary_changed = self.le_bin.text() != dm.bin_path
        dm.bin_path = self.le_bin.text()
        dm.csv_3d_path = self.le_3d.text()
        dm.csv_2d_path = self.le_2d.text()
        dm.csv_dtc_path = self.le_dtc.text()
        dm.csv_potential_path = self.le_potential.text()
        dm.load_dtc_csv()

        if binary_changed:
            ok, message = dm.load_binary()
            mw.status_lbl.setText(message if message else "Binary loaded.")
            if not ok:
                QMessageBox.warning(mw, "Binary Not Loaded", message)

        order = "<" if self.cb_little_endian.isChecked() else ">"
        signed = self.cb_signed.isChecked()
        dm.z_format_3d = order + formats.build(self.cmb_3d.currentText(), signed)
        dm.z_format_2d = order + formats.build(self.cmb_2d.currentText(), signed)
        dm.ax_format = formats.build(self.cmb_ax.currentText(), signed)

        mw.factor_z_3d = self.spin_factor_3d.value()
        mw.offset_z_3d = self.spin_offset_3d.value()
        mw.factor_z_2d = self.spin_factor_2d.value()
        mw.offset_z_2d = self.spin_offset_2d.value()

        mw.apply_factor_to_hex = self.cb_factor_in_hex.isChecked()
        mw.highlight_3d = self.cb_highlight_3d.isChecked()
        mw.highlight_2d = self.cb_highlight_2d.isChecked()
        mw.highlight_custom_tags = self.cb_highlight_custom.isChecked()
        mw.sparkline_style = (
            SparklineStyle.BARS if self.rb_spark_bars.isChecked() else SparklineStyle.LINE
        )
        mw.rot_mode = next(
            (mode for mode, button in self.rb_rotation.items() if button.isChecked()),
            RotationMode.Z_ONLY,
        )

        new_position = HexPlotPosition.TOP if self.rb_plot_top.isChecked() else HexPlotPosition.RIGHT
        position_changed = new_position is not mw.hex_plot_position
        mw.hex_plot_position = new_position

        mw.map_type_dropdown_visible = self.rb_map_dropdown.isChecked()
        if self.rb_map_dropdown.isChecked():
            new_map_mode = MapMode.from_combo_index(mw.cmb_map_type.currentIndex())
        else:
            new_map_mode = next(
                (mode for mode, button in self.rb_map_modes.items() if button.isChecked()),
                MapMode.THREE_D,
            )

        new_app_mode = next(
            (mode for mode, button in self.rb_app_modes.items() if button.isChecked()),
            AppMode.MAP_VIEWER,
        )

        # A direct assignment: no more setting the button to the *previous* mode
        # and calling the cycle handler so it lands on the wanted one.
        map_mode_changed = new_map_mode is not mw.map_mode
        mw.map_mode = new_map_mode

        if new_app_mode is not mw.app_mode:
            mw.set_app_mode(new_app_mode)
        else:
            mw._sync_mode_widgets()
            if position_changed:
                mw.apply_splitter_position()
            if map_mode_changed or binary_changed:
                mw.load_data()
            else:
                mw.draw_map()
