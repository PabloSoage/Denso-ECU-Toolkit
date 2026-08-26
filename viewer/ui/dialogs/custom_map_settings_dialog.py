"""Per-map overrides for data format, factor and offset."""

from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QLabel,
    QMessageBox,
    QVBoxLayout,
)

from ...core import formats

SIZE_CHOICES = list(formats.SIZE_LABELS)


class CustomMapSettingsDialog(QDialog):
    def __init__(self, main_window):
        super().__init__(main_window)
        self.main_window = main_window
        self.data_manager = main_window.data_manager
        self.init_ui()

    def init_ui(self):
        mw = self.main_window
        dm = self.data_manager

        row = mw.current_row()
        if row is None:
            QMessageBox.information(self, "No Map", "Select a map first.")
            return

        # Overrides are stored under the data address; older projects that keyed
        # them by call site are still read, but rewritten canonically on save.
        key = dm.canonical_key(row)
        current = dm.custom_settings_for(row)

        self.setWindowTitle(f"Custom Settings for Map: {key}")
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("<i>Uncheck to fall back to the global settings.</i>"))

        enable = QCheckBox("Enable Custom Settings for this Map")
        enable.setChecked(bool(current))
        layout.addWidget(enable)

        is_3d = mw.row_is_3d(row)
        z_format = current.get("z_format", dm.z_format_3d if is_3d else dm.z_format_2d)
        ax_format = current.get("ax_format", dm.ax_format)
        factor = current.get("factor", mw.factor_z_3d if is_3d else mw.factor_z_2d)
        offset = current.get("offset", mw.offset_z_3d if is_3d else mw.offset_z_2d)

        z_size, z_order, z_signed = formats.describe(z_format)
        ax_size, _, _ = formats.describe(ax_format)

        group = QGroupBox("Custom Settings")
        form = QFormLayout(group)

        cmb_z = QComboBox()
        cmb_z.addItems(SIZE_CHOICES)
        cmb_z.setCurrentText(z_size)

        cmb_ax = QComboBox()
        cmb_ax.addItems(SIZE_CHOICES)
        cmb_ax.setCurrentText(ax_size)

        cb_little = QCheckBox("Little Endian (LoHi)")
        cb_little.setChecked(z_order == "<")
        cb_signed = QCheckBox("Signed - Uncheck for Unsigned")
        cb_signed.setChecked(z_signed)

        spin_factor = self._spin(factor)
        spin_offset = self._spin(offset)

        form.addRow("Z / Curve Data Size:", cmb_z)
        form.addRow("Axis Data Size:", cmb_ax)
        form.addRow(cb_little)
        form.addRow(cb_signed)
        form.addRow("Z / Curve Factor:", spin_factor)
        form.addRow("Z / Curve Offset:", spin_offset)
        layout.addWidget(group)

        enable.toggled.connect(group.setEnabled)
        group.setEnabled(enable.isChecked())

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        if not self.exec():
            return

        if enable.isChecked():
            order = "<" if cb_little.isChecked() else ">"
            signed = cb_signed.isChecked()
            dm.set_custom_setting(
                row,
                z_format=order + formats.build(cmb_z.currentText(), signed),
                ax_format=formats.build(cmb_ax.currentText(), signed),
                factor=spin_factor.value(),
                offset=spin_offset.value(),
            )
        else:
            # Clear every identity, not just the canonical one, so a legacy
            # override does not survive the user switching it off.
            for identity in dm.identity_keys(row):
                dm.custom_map_settings.pop(identity, None)

        mw.draw_map()

    @staticmethod
    def _spin(value):
        spin = QDoubleSpinBox()
        spin.setDecimals(5)
        spin.setSingleStep(0.001)
        spin.setRange(-1_000_000, 1_000_000)
        spin.setValue(value)
        return spin
