from PyQt5.QtWidgets import (
    QApplication, QWidget, QListWidget, QListWidgetItem, QMenu, QDialog,
    QVBoxLayout, QPushButton, QLineEdit, QLabel
)
from PyQt5.QtCore import Qt
import sys

# 状态类型定义
COMPOSITE = 'CompositeState'
NORMAL = 'NormalState'
PSEUDO = 'PseudoState'

class StateItem(QListWidgetItem):
    def __init__(self, name, state_type, parent=None):
        super().__init__(name, parent)
        self.state_type = state_type
        self.name = name
        self.children = []
        self.expanded = False


class StateEditorDialog(QDialog):
    def __init__(self, title="编辑状态", default_name=""):
        super().__init__()
        self.setWindowTitle(title)
        self.layout = QVBoxLayout()
        self.name_input = QLineEdit(default_name)
        self.layout.addWidget(QLabel("状态名称:"))
        self.layout.addWidget(self.name_input)
        self.ok_button = QPushButton("确定")
        self.ok_button.clicked.connect(self.accept)
        self.layout.addWidget(self.ok_button)
        self.setLayout(self.layout)

    def get_name(self):
        return self.name_input.text()


class StateManager(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("状态管理")
        self.list_widget = QListWidget()
        self.list_widget.setContextMenuPolicy(Qt.CustomContextMenu)
        self.list_widget.customContextMenuRequested.connect(self.show_context_menu)
        self.list_widget.itemClicked.connect(self.toggle_expand)

        layout = QVBoxLayout()
        layout.addWidget(self.list_widget)
        self.setLayout(layout)

        # 示例数据
        self.add_state("复合状态 A", COMPOSITE)
        self.add_state("普通状态 B", NORMAL)

    def add_state(self, name, state_type, parent_item=None):
        item = StateItem(name, state_type)
        if parent_item:
            parent_item.children.append(item)
            if parent_item.expanded:
                index = self.list_widget.row(parent_item) + len(parent_item.children)
                self.list_widget.insertItem(index, f"  ↳ {item.name}")
        else:
            self.list_widget.addItem(item)

    def toggle_expand(self, item):
        if isinstance(item, StateItem) and item.state_type == COMPOSITE:
            item.expanded = not item.expanded
            row = self.list_widget.row(item)
            if item.expanded:
                for i, child in enumerate(item.children):
                    self.list_widget.insertItem(row + 1 + i, f"  ↳ {child.name}")
            else:
                for _ in item.children:
                    self.list_widget.takeItem(row + 1)

    def show_context_menu(self, position):
        item = self.list_widget.itemAt(position)
        if not isinstance(item, StateItem):
            return

        menu = QMenu()
        if item.state_type == COMPOSITE:
            menu.addAction("添加子状态", lambda: self.edit_and_add_child(item))
        menu.addAction("修改状态", lambda: self.edit_state(item))
        menu.addAction("删除状态", lambda: self.delete_state(item))
        menu.exec_(self.list_widget.viewport().mapToGlobal(position))

    def edit_and_add_child(self, parent_item):
        dialog = StateEditorDialog("添加子状态")
        if dialog.exec_() == QDialog.Accepted:
            name = dialog.get_name()
            self.add_state(name, NORMAL, parent_item)

    def edit_state(self, item):
        dialog = StateEditorDialog("修改状态", item.name)
        if dialog.exec_() == QDialog.Accepted:
            new_name = dialog.get_name()
            item.setText(new_name)
            item.name = new_name

    def delete_state(self, item):
        row = self.list_widget.row(item)
        self.list_widget.takeItem(row)

app = QApplication(sys.argv)
win = StateManager()
win.show()
sys.exit(app.exec_())
