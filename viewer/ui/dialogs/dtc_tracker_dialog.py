from PyQt6.QtWidgets import QDialog, QVBoxLayout, QFormLayout, QLabel, QPushButton, QFrame
from PyQt6.QtCore import Qt

class DtcTrackerDialog(QDialog):
    def __init__(self, dtc_info, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Diagnostic Link (DTC Tracker)")
        self.setMinimumWidth(400)
        
        layout = QVBoxLayout(self)
        
        # Título
        title = QLabel("<b>DTC Forward Taint Analysis</b>")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)
        
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setFrameShadow(QFrame.Shadow.Sunken)
        layout.addWidget(line)
        
        # Formulario de datos
        form = QFormLayout()
        
        lbl_sensor = QLabel(f"<b>{dtc_info.get('map_data_addr', 'N/A')}</b>")
        lbl_sensor.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        form.addRow("Sensor / Map Curve:", lbl_sensor)
        
        lbl_ram = QLabel(f"<b style='color: #d9534f;'>{dtc_info.get('ram_var', 'N/A')}</b>")
        lbl_ram.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        form.addRow("Associated RAM Flag:", lbl_ram)
        
        lbl_func = QLabel(f"<b style='color: #5cb85c;'>{dtc_info.get('dtc_func', 'N/A')}</b>")
        lbl_func.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        form.addRow("Diagnostic Task Func:", lbl_func)
        
        layout.addLayout(form)
        
        # Tip
        tip_box = QLabel(
            "<i><b>Tip for DTC Off:</b> Check cross-references for "
            f"{dtc_info.get('dtc_func', 'this function')} to locate and patch "
            "the branch instructions triggering the fault state.</i>"
        )
        tip_box.setWordWrap(True)
        tip_box.setStyleSheet("background-color: #f8f9fa; color: #333; padding: 10px; border-radius: 5px; border: 1px solid #ccc;")
        layout.addWidget(tip_box)
        
        # Botón de cierre
        btn_close = QPushButton("Close")
        btn_close.clicked.connect(self.accept)
        layout.addWidget(btn_close)
