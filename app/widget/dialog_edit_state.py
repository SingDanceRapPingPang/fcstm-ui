from PyQt5.Qt import QDialog
from PyQt5 import QtWidgets
from PyQt5.QtWidgets import QWidget

from ..ui import UIDialogEditState
from typing import Optional
from pyfcstm.model import NormalState, CompositeState, PseudoState, Statechart, State

class DialogEditState(QDialog, UIDialogEditState):
    def __init__(self, parent, state_chart: Statechart, root_state :Optional[CompositeState] = None,
                 is_edit=False, initial_data: Optional[State] = None):
        QDialog.__init__(self, parent)
        self.setupUi(self)
        self.setFixedSize(self.width(), self.height())

        self.root_state = root_state
        self.is_edit = is_edit
        self.initial_data = initial_data
        self.state_chart = state_chart

        self._init()

    def _init(self):
        self._init_ui()
        self._init_button_accept()
        self._init_button_reject()

    def _init_ui(self):
        if self.is_edit:
            self.setWindowTitle("修改状态")
            if self.initial_data:
                # 预填充内容
                self.edit_state_name.setText(self.initial_data.name)
                self.edit_state_description.setText(self.initial_data.description)
                self.combo_state_type.setCurrentText(self.initial_data.type.value.lower())
                if self.initial_data.min_time_lock is not None:
                    self.edit_min_time.setText(str(self.initial_data.min_time_lock))
                if self.initial_data.max_time_lock is not None:
                    self.edit_max_time.setText(str(self.initial_data.max_time_lock))
                self.edit_state_entry.setText(self.initial_data.on_entry)
                self.edit_state_during.setText(self.initial_data.on_during)
                self.edit_state_exit.setText(self.initial_data.on_exit)
        else:
            self.setWindowTitle("添加状态")

    def _init_button_accept(self):
        self.button_accept.clicked.connect(self._on_accept)

    def _on_accept(self):
        state_name = self.edit_state_name.text().strip()
        type = self.combo_state_type.currentText()
        if not state_name or state_name == '':
            QtWidgets.QMessageBox.warning(self, "错误", "状态名不能为空！")
            return
        if (self.state_chart.states.get_by_name(state_name) and
                (self.initial_data is None or self.initial_data.name != state_name)):
            QtWidgets.QMessageBox.warning(self, "错误", "状态名已经存在！")
            return
        if not self.safe_int(self.edit_min_time.text()) or not self.safe_int(self.edit_max_time.text()):
            QtWidgets.QMessageBox.warning(self, "错误", "最小停留时间和最大停留时间应为整数！")
            return
        if (isinstance(self.initial_data, CompositeState) and len(self.initial_data.states)
            and (type == 'normal' or type == 'pseudo')):
            QtWidgets.QMessageBox.warning(self, "错误", f"原状态{self.initial_data.name}含有子状态，类型应为composite")
            return
        if self.initial_data is not None and self.initial_data.id == self.root_state.id and (type == 'normal' or type == 'pseudo'):
            QtWidgets.QMessageBox.warning(self, "错误", "初始状态类型应为composite")
            return

        self.accept()

    def _init_button_reject(self):
        self.button_cancle.clicked.connect(self.reject)

    def get_state(self):
        name = self.edit_state_name.text()
        description = self.edit_state_description.toPlainText()
        type = self.combo_state_type.currentText()
        minTimeLock = None if self.edit_min_time.text() == '' else int(self.edit_min_time.text())
        maxTimeLock = None if self.edit_max_time.text() == '' else int(self.edit_max_time.text())
        entry = self.edit_state_entry.toPlainText()
        during = self.edit_state_during.toPlainText()
        exit = self.edit_state_exit.toPlainText()

        if type == 'composite':
            new_state_initial_state = None
            new_state_id = None
            new_state_states = None
            if self.initial_data is not None and isinstance(self.initial_data, CompositeState):
                new_state_initial_state = self.initial_data.initial_state_id
                new_state_id = self.initial_data.id
                new_state_states = self.initial_data.states
            new_state = CompositeState(name=name, initial_state=new_state_initial_state, description=description,
                                       min_time_lock=minTimeLock, max_time_lock=maxTimeLock, on_entry=entry,
                                       on_during=during, on_exit=exit, id_=new_state_id if self.is_edit else None,
                                       states=new_state_states)
        elif type == 'normal':
            new_state = NormalState(name=name, description=description, min_time_lock=minTimeLock,
                                    max_time_lock=maxTimeLock, on_entry=entry, on_during=during,
                                    on_exit=exit, id_ = self.initial_data.id if self.is_edit else None)
        else:
            new_state = PseudoState(name=name, description=description, min_time_lock=minTimeLock,
                                    max_time_lock=maxTimeLock, on_entry=entry, on_during=during,
                                    on_exit=exit, id_ = self.initial_data.id if self.is_edit else None)
        return new_state

    def safe_int(self, val: str) -> bool:
        try:
            if val:
                _ = int(val)
            return True
        except ValueError:
            return False
