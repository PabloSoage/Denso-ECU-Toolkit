"""Shows the RAM variable and consumer function linked to a map."""

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog,
    QFormLayout,
    QFrame,
    QLabel,
    QPushButton,
    QVBoxLayout,
)

CONFIDENCE_COLORS = {
    "high": "#5cb85c",
    "medium": "#f0ad4e",
    "low": "#d9534f",
}


class DtcTrackerDialog(QDialog):
    def __init__(self, dtc_info, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Diagnostic Link")
        self.setMinimumWidth(460)

        layout = QVBoxLayout(self)

        title = QLabel("<b>Forward dataflow from this map</b>")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        rule = QFrame()
        rule.setFrameShape(QFrame.Shape.HLine)
        rule.setFrameShadow(QFrame.Shadow.Sunken)
        layout.addWidget(rule)

        form = QFormLayout()
        form.addRow("Map / Curve Data:", self._value(dtc_info.get("map_data_addr")))
        form.addRow("Result RAM Variable:", self._value(dtc_info.get("ram_var"), "#d9534f"))
        form.addRow("Consumer Function:", self._value(dtc_info.get("dtc_func"), "#5cb85c"))

        confidence = str(dtc_info.get("confidence", "")).strip()
        if confidence:
            colour = CONFIDENCE_COLORS.get(confidence.lower(), "#333")
            form.addRow("Confidence:", self._value(confidence, colour))

        evidence = str(dtc_info.get("evidence", "")).strip()
        if evidence:
            form.addRow("Evidence:", self._value(evidence))

        layout.addLayout(form)

        # Stated plainly: this is a dataflow link, not proof of a diagnostic.
        note = QLabel(
            "<i>The RAM variable is where the interpolation result is stored. "
            "The consumer function is the first <b>other</b> function that reads "
            "it — it is a lead, not proof that it manages a DTC. Confirm it in "
            "Ghidra by checking the cross-references before patching anything.</i>"
        )
        note.setWordWrap(True)
        note.setStyleSheet(
            "background-color: #f8f9fa; color: #333; padding: 10px;"
            "border-radius: 5px; border: 1px solid #ccc;"
        )
        layout.addWidget(note)

        close = QPushButton("Close")
        close.clicked.connect(self.accept)
        layout.addWidget(close)

    @staticmethod
    def _value(text, colour=None):
        label = QLabel(
            f"<b style='color: {colour};'>{text or 'N/A'}</b>" if colour
            else f"<b>{text or 'N/A'}</b>"
        )
        label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        label.setWordWrap(True)
        return label
