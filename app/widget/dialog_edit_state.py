from PyQt5.Qt import QDialog
from PyQt5 import QtWidgets
from PyQt5.QtCore import Qt

from ..ui import UIDialogEditState
from typing import Optional
from ..model import State, StateManager
from app.utils.text_overflow import apply_text_overflow_handling, refresh_text_overflow

class DialogEditState(QDialog, UIDialogEditState):
    def __init__(self, parent, state_manager: StateManager,
                 is_edit=False, initial_data: Optional[State] = None,
                 parent_state: Optional[State] = None):
        QDialog.__init__(self, parent)
        self.setupUi(self)
        apply_text_overflow_handling(self)
        self.is_edit = is_edit
        self.initial_data = initial_data
        self.state_manager = state_manager
        self.parent_state = parent_state  # 新增：父状态上下文

        self._init()

    def _init(self):
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)
        self._init_ui()
        self._init_button_accept()
        self._init_button_reject()

    def _init_ui(self):
        self.label_extra_name = QtWidgets.QLabel("显示名", self.frame_state_info_edit)
        self.edit_extra_name = QtWidgets.QLineEdit(self.frame_state_info_edit)
        self.check_pseudo_state = QtWidgets.QCheckBox("伪状态", self.frame_state_info_edit)
        self.gridLayout_6.addWidget(self.label_extra_name, 1, 0, 1, 1)
        self.gridLayout_6.addWidget(self.edit_extra_name, 1, 1, 1, 1)
        self.gridLayout_6.addWidget(self.check_pseudo_state, 2, 1, 1, 1)
        self.resize(max(self.width(), 360), self.height() + 80)

        if self.is_edit:
            self.setWindowTitle("修改状态名称")
            if self.initial_data:
                # 预填充内容
                self.edit_state_name.setText(self.initial_data.name)
                self.edit_extra_name.setText(self.initial_data.extra_name or "")
                self.check_pseudo_state.setChecked(bool(self.initial_data.is_pseudo))
        else:
            self.setWindowTitle("添加状态")
        apply_text_overflow_handling(self)
        refresh_text_overflow(self)

    def _init_button_accept(self):
        self.button_accept.clicked.connect(self._on_accept)

    def _on_accept(self):
        state_name = self.edit_state_name.text().strip()
        if not state_name or state_name == '':
            QtWidgets.QMessageBox.warning(self, "错误", "状态名不能为空！")
            return

        # 检查同一父状态下是否有重复名称
        if self.is_edit:
            # 编辑状态：检查同一父状态下是否有其他同名状态
            if self.initial_data and self.initial_data.parent:
                existing_sibling = self.initial_data.parent.find_child_by_name(state_name)
                if existing_sibling and existing_sibling != self.initial_data:
                    QtWidgets.QMessageBox.warning(self, "错误", f"父状态 '{self.initial_data.parent.name}' 下已存在名为 '{state_name}' 的子状态！")
                    return
        else:
            # 添加状态：检查指定父状态下是否已有同名子状态
            if self.parent_state:
                if self.parent_state.find_child_by_name(state_name):
                    QtWidgets.QMessageBox.warning(self, "错误", f"父状态 '{self.parent_state.name}' 下已存在名为 '{state_name}' 的子状态！")
                    return
            else:
                # 添加根状态：检查是否已有根状态
                if self.state_manager.root_state is not None:
                    QtWidgets.QMessageBox.warning(self, "错误", "状态机中只能有一个根状态！")
                    return

        self.accept()

    def _init_button_reject(self):
        self.button_cancle.clicked.connect(self.reject)

    def get_state_name(self) -> str:
        name = self.edit_state_name.text()
        return name

    def get_state_data(self) -> dict:
        return {
            "name": self.edit_state_name.text().strip(),
            "extra_name": self.edit_extra_name.text().strip() or None,
            "is_pseudo": self.check_pseudo_state.isChecked(),
        }
