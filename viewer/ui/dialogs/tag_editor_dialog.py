from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QListWidget, QHBoxLayout, 
                             QLineEdit, QPushButton, QDialogButtonBox)

class TagEditorDialog(QDialog):
    def __init__(self, current_tags, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Edit Tags")
        self.tags = list(current_tags)
        self.layout = QVBoxLayout(self)
        
        self.list_widget = QListWidget()
        self.list_widget.addItems(self.tags)
        self.layout.addWidget(self.list_widget)
        
        h_layout = QHBoxLayout()
        self.new_tag_input = QLineEdit()
        self.btn_add = QPushButton("Add Tag")
        self.btn_remove = QPushButton("Remove Selected")
        h_layout.addWidget(self.new_tag_input)
        h_layout.addWidget(self.btn_add)
        h_layout.addWidget(self.btn_remove)
        self.layout.addLayout(h_layout)
        
        self.btn_add.clicked.connect(self.add_tag)
        self.btn_remove.clicked.connect(self.remove_tag)
        
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        self.layout.addWidget(buttons)
        
    def add_tag(self):
        t = self.new_tag_input.text().strip()
        if t and t not in self.tags:
            self.tags.append(t)
            self.list_widget.addItem(t)
            self.new_tag_input.clear()
            
    def remove_tag(self):
        for item in self.list_widget.selectedItems():
            self.tags.remove(item.text())
            self.list_widget.takeItem(self.list_widget.row(item))
