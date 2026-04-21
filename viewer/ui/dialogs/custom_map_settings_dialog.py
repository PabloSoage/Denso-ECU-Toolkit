import sys
from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QLabel, QCheckBox, 
                             QGroupBox, QFormLayout, QComboBox, QDoubleSpinBox, 
                             QDialogButtonBox, QMessageBox)

class CustomMapSettingsDialog(QDialog):
    def __init__(self, main_window):
        super().__init__(main_window)
        self.main_window = main_window
        self.data_manager = main_window.data_manager
        self.init_ui()
        
    def init_ui(self):
        if self.main_window.data_manager.df.empty: return
        
        row = self.main_window.data_manager.df.iloc[self.main_window.data_manager.current_index]
        wrapper_addr_hex = str(row['Wrapper_Addr']).strip()
        custom = getattr(self.main_window.data_manager, "custom_map_settings", {}).get(wrapper_addr_hex, {})
        
        
        self.setWindowTitle(f"Custom Settings for Map: {wrapper_addr_hex}")
        layout = QVBoxLayout(self)
        
        def parse_fmt(f_str):
            if not f_str: return "16-bit", ">", False
            endian = "<" if "<" in f_str else ">"
            c = f_str[-1].lower()
            if c == 'f': size = "Float"
            elif c == 'b': size = "8-bit"
            elif c == 'i' or c == 'l': size = "32-bit"
            else: size = "16-bit" # default H/h
            signed = f_str[-1].islower()
            if size == "Float": signed = True
            return size, endian, signed
            
        def build_fmt(size_str, signed, is_little):
            endian = '<' if is_little else '>'
            if size_str == 'Float': char = 'f'
            elif size_str == '8-bit': char = 'b' if signed else 'B'
            elif size_str == '16-bit': char = 'h' if signed else 'H'
            else: char = 'i' if signed else 'I'
            return endian + char

        layout.addWidget(QLabel("<i>Leave empty or uncheck to use global settings.</i>"))

        cb_override = QCheckBox("Enable Custom Settings for this Map")
        cb_override.setChecked(wrapper_addr_hex in getattr(self.main_window.data_manager, "custom_map_settings", {}))
        layout.addWidget(cb_override)
        
        frame = QGroupBox("Custom Settings")
        ly_frame = QFormLayout(frame)
        
        current_type = row.get('Map_Type', self.main_window.map_mode)
        is_3d = (current_type == '3d' or (current_type == 'tags' and self.main_window.hex_plot_mode == '3d'))
        
        glob_z = self.main_window.data_manager.z_format_3d if is_3d else self.main_window.data_manager.z_format_2d
        glob_ax = self.main_window.data_manager.ax_format
        glob_f = self.main_window.factor_z_3d if is_3d else self.main_window.factor_z_2d
        glob_o = self.main_window.offset_z_3d if is_3d else self.main_window.offset_z_2d

        z_fmt = custom.get('z_format', glob_z)
        ax_fmt = custom.get('ax_format', glob_ax)
        c_factor = custom.get('factor', glob_f)
        c_offset = custom.get('offset', glob_o)
        
        sizeZ, endZ, signZ = parse_fmt(z_fmt)
        sizeA, endA, signA = parse_fmt('>' + ax_fmt if len(ax_fmt) == 1 else ax_fmt)
        
        cmb_z_size = QComboBox(); cmb_z_size.addItems(["8-bit", "16-bit", "32-bit", "Float"]); cmb_z_size.setCurrentText(sizeZ)
        cmb_a_size = QComboBox(); cmb_a_size.addItems(["8-bit", "16-bit", "32-bit", "Float"]); cmb_a_size.setCurrentText(sizeA)
        cb_endian = QCheckBox("Little Endian (LoHi)"); cb_endian.setChecked(endZ == '<')
        cb_signed = QCheckBox("Signed - Uncheck for Unsigned"); cb_signed.setChecked(signZ)
        
        spin_f = QDoubleSpinBox(); spin_f.setDecimals(5); spin_f.setSingleStep(0.001)
        spin_f.setRange(-10000, 10000); spin_f.setValue(c_factor)
        
        spin_o = QDoubleSpinBox(); spin_o.setDecimals(5); spin_o.setSingleStep(0.001)
        spin_o.setRange(-10000, 10000); spin_o.setValue(c_offset)
        
        ly_frame.addRow("Z / Curve Data Size:", cmb_z_size)
        ly_frame.addRow("Axis Data Size:", cmb_a_size)
        ly_frame.addWidget(cb_endian)
        ly_frame.addWidget(cb_signed)
        ly_frame.addRow("Z / Curve Factor:", spin_f)
        ly_frame.addRow("Z / Curve Offset:", spin_o)

        layout.addWidget(frame)

        def toggle_frame():
            frame.setEnabled(cb_override.isChecked())
        cb_override.toggled.connect(toggle_frame)
        toggle_frame()
        
        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)
        
        if self.exec():
            if cb_override.isChecked():
                new_z = build_fmt(cmb_z_size.currentText(), cb_signed.isChecked(), cb_endian.isChecked())
                new_a = build_fmt(cmb_a_size.currentText(), cb_signed.isChecked(), cb_endian.isChecked())
                if not hasattr(self.main_window.data_manager, "custom_map_settings"):
                    self.main_window.data_manager.custom_map_settings = {}
                self.main_window.data_manager.custom_map_settings[wrapper_addr_hex] = {
                    'z_format': new_z,
                    'ax_format': new_a[-1],
                    'factor': spin_f.value(),
                    'offset': spin_o.value()
                }
            else:
                if hasattr(self.main_window.data_manager, "custom_map_settings") and wrapper_addr_hex in self.main_window.data_manager.custom_map_settings:
                    del self.main_window.data_manager.custom_map_settings[wrapper_addr_hex]
            
            self.main_window.draw_map()

