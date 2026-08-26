"""Add/remove the free-text tags attached to an address."""

from PyQt6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLineEdit,
    QListWidget,
    QPushButton,
    QVBoxLayout,
)


class TagEditorDialog(QDialog):
    def __init__(self, current_tags, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Edit Tags")
        self.setMinimumWidth(380)
        self.tags = list(current_tags)

        layout = QVBoxLayout(self)

        self.list_widget = QListWidget()
        self.list_widget.addItems(self.tags)
        layout.addWidget(self.list_widget)

        row = QHBoxLayout()
        self.new_tag_input = QLineEdit()
        self.new_tag_input.setPlaceholderText("New tag, then Enter…")
        self.new_tag_input.returnPressed.connect(self.add_tag)
        self.btn_add = QPushButton("Add Tag")
        self.btn_add.clicked.connect(self.add_tag)
        self.btn_remove = QPushButton("Remove Selected")
        self.btn_remove.clicked.connect(self.remove_tag)
        row.addWidget(self.new_tag_input)
        row.addWidget(self.btn_add)
        row.addWidget(self.btn_remove)
        layout.addLayout(row)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self.new_tag_input.setFocus()

    def add_tag(self):
        # Commas separate tags everywhere else, so splitting here lets a whole
        # set be pasted in at once instead of creating one tag containing commas.
        for part in self.new_tag_input.text().split(","):
            tag = part.strip()
            if tag and tag not in self.tags:
                self.tags.append(tag)
                self.list_widget.addItem(tag)
        self.new_tag_input.clear()

    def remove_tag(self):
        for item in self.list_widget.selectedItems():
            if item.text() in self.tags:
                self.tags.remove(item.text())
            self.list_widget.takeItem(self.list_widget.row(item))
