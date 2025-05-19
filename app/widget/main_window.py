from PyQt5.Qt import QMainWindow
from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtCore import QTimerEvent, Qt, QPoint
from app.ui import UIMainWindow
from pyfcstm.model import State, NormalState, CompositeState, PseudoState, Event, Transition, Statechart
from typing import Optional, List, Dict
from .dialog_edit_state import DialogEditState
from app.utils.create_formLayout_dialog import create_formlayout_dialog
from app.utils.show_state_graph import show_state_graph

class AppMainWindow(QMainWindow, UIMainWindow):
    d_all_transition: Dict[str, List[Transition]]

    d_all_event: Dict[str, List[Event]] #state.id: event

    d_id_father_state: Dict[str, Optional[CompositeState]]

    def __init__(self):
        QMainWindow.__init__(self)
        self.setupUi(self)
        self.state_chart: Optional[Statechart] = None
        self.at_page_initial = True
        self.d_all_event = {} # state.id: event

        self.d_all_transition = {} # state.id: transition

        self.d_id_father_state = {} #state.id: state(father)

        self._init()

    def _init(self):
        #初始化窗口格式
        self._init_window_style()
        #初始化event和transition表格的上下文菜单
        self._init_table_context_menus()
        #初始化添加事件和添加迁移按钮
        self._init_button_state_machine_add_event()
        self._init_button_state_machine_add_transition()
        #初始化添加状态按钮
        self._init_button_state_machine_add_state()
        #初始化导入状态机按钮
        self._init_import_state_chart()
        #初始化tree_state_machine_all_state点击和上下文菜单
        self._init_tree_state_machine_all_state()
        self._init_tree_state_machine_all_state_context_menu()
        #初始化导出按钮
        self._init_button_state_machine_export()
        #初始化新建状态机按钮
        self._init_button_initial_new_state_machine()
        #初始化验证按钮
        self._init_button_state_machine_validation()
        #初始化图生成按钮
        self._init_button_state_machine_graph_gen()
        '''
        self._init_button_save_state()
        '''

    def _init_window_style(self):
        self._init_table_style()
        self._init_tree_style()

    def _init_import_state_chart(self):
        self._init_button_initial_import_state_machine()
        self._init_button_state_machine_import_state()

    def _init_button_initial_import_state_machine(self):
        self.button_initial_import_state_machine.clicked.connect(lambda: self._import_statechart())

    def _init_button_state_machine_import_state(self):
        self.button_state_machine_import_state.clicked.connect(lambda: self._import_statechart())

    def _init_button_initial_new_state_machine(self):
        self.button_initial_new_state_machine.clicked.connect(lambda: self._new_state_machine())

    def _new_state_machine(self):
        # 弹出dialog，输入状态机名称和状态机描述，然后进入到初始页面
        label_data = ["状态机名称"]
        edit_data = ['']
        success, state_machine_name = create_formlayout_dialog(self, "新建状态机", label_data, edit_data)
        if not success:
            return
        if state_machine_name is None or len(state_machine_name) == 0 or state_machine_name[0] == '':
            QtWidgets.QMessageBox.warning(
                self,
                "警告",
                "状态机名称不能为空！",
                QtWidgets.QMessageBox.Ok
            )
            return
        root_state = CompositeState(name="初始状态")
        states = [root_state]
        self.state_chart = Statechart(name=state_machine_name[0], root_state=root_state, states=states)
        self.edit_state_machine_name.setText(state_machine_name[0])
        item = QtWidgets.QTreeWidgetItem([root_state.name])
        item.setData(0, Qt.UserRole, root_state)
        self.tree_state_machine_all_state.addTopLevelItem(item)
        if self.at_page_initial:
            self.stackedWidget_state_machine.setCurrentIndex(1)
            self.at_page_initial = False
        for i in range(self.tree_state_machine_all_state.topLevelItemCount()):
            print(f"Top level {i}: {self.tree_state_machine_all_state.topLevelItem(i).text(0)}")

    def _init_table_style(self):
        # 让table中的所有列等比例填充窗口
        event_header = self.table_state_machine_event.horizontalHeader()
        event_header.setSectionResizeMode(QtWidgets.QHeaderView.Stretch)
        transition_header = self.table_state_machine_transition.horizontalHeader()
        transition_header.setSectionResizeMode(QtWidgets.QHeaderView.Stretch)
        #首先让页面显示在导入状态机和新建状态机页面
        self.stackedWidget_state_machine.setCurrentIndex(0)

    def _init_tree_style(self):
        self.tree_state_machine_all_state.header().hide()
        #self.tree_state_machine_all_state.setIndentation(0)
        self.tree_code_gen_all_state.header().hide()
        #self.tree_code_gen_all_state.setIndentation(0)

    def _init_table_context_menus(self):
        # 设置表格的上下文菜单策略
        self.table_state_machine_event.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.table_state_machine_transition.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        
        # 连接自定义上下文菜单信号
        self.table_state_machine_event.customContextMenuRequested.connect(
            lambda pos: self._show_table_context_menu(pos, self.table_state_machine_event))
        self.table_state_machine_transition.customContextMenuRequested.connect(
            lambda pos: self._show_table_context_menu(pos, self.table_state_machine_transition))

    def _show_table_context_menu(self, pos, table):
        # 获取点击的项
        item = table.itemAt(pos)
        if not item:
            return
        # 创建上下文菜单
        context_menu = QtWidgets.QMenu(self)
        edit_action = context_menu.addAction("编辑")
        delete_action = context_menu.addAction("删除")

        # 获取全局坐标
        global_pos = table.mapToGlobal(pos)

        # 显示菜单并获取选择的动作
        action = context_menu.exec_(global_pos)

        if action == edit_action:
            self._edit_item(table, item.row())
        elif action == delete_action:
            self._delete_item(table, item.row())

    def _delete_item(self, table, row):
        # 获取待处理的状态
        pro_state = self._get_pro_state()
        # 获取待处理的状态
        if pro_state is None:
            table.removeRow(row)
            return

        if table == self.table_state_machine_event:
            event_name = table.item(row, 0).text() if table.item(row, 0) is not None else None
            event_guard = table.item(row, 1).text() if table.item(row, 1) is not None else None

            #同步删除transition中的内容
            reply = QtWidgets.QMessageBox.question(self, "删除确认", f"删除'{event_name}'事件，会同时删除关联的迁移，确定要继续删除吗",
                                                   QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No)

            if reply == QtWidgets.QMessageBox.No:
                return
            if pro_state.id in self.d_all_event:
                del_event = None
                for cur_event in self.d_all_event[pro_state.id]:
                    if cur_event.name == event_name:
                        del_event = cur_event
                        if cur_event in self.state_chart.events:
                            del self.state_chart.events[cur_event]

                if del_event is not None:
                    self.d_all_event[pro_state.id].remove(del_event)
                    if pro_state.id in self.d_all_transition:
                        for cur_transition in self.d_all_transition[pro_state.id][:]:
                            if cur_transition.event_id == del_event.id:
                                self.d_all_transition[pro_state.id].remove(cur_transition)
                                del self.state_chart.transitions[cur_transition]



        elif table == self.table_state_machine_transition:
            transition_event = table.item(row, 0).text() if table.item(row, 0) is not None else None
            transition_target_name = table.item(row, 1).text() if table.item(row, 1) is not None else None

            transition_target_state = self.state_chart.states.get_by_name(transition_target_name)

            if pro_state.id in self.d_all_transition:
                del_transition = None
                for cur_transition in self.d_all_transition[pro_state.id]:
                    cur_event_id = cur_transition.event_id
                    cur_event = self.state_chart.events.get(cur_event_id)

                    if (cur_event and cur_transition.src_state_id == pro_state.id and
                            cur_transition.dst_state_id == transition_target_state.id and
                            cur_event.name == transition_event):
                        del_transition = cur_transition
                        break
                if del_transition is not None:
                    self.d_all_transition[pro_state.id].remove(del_transition)
                    del self.state_chart.transitions[del_transition]
        # 更新表格
        cur_state_item = self.tree_state_machine_all_state.currentItem()
        self._display_state_event_transition_details(cur_state_item)

    def _edit_item(self, table, row):
        if table == self.table_state_machine_event:
            self._show_event_dialog(True, row)
        elif table == self.table_state_machine_transition:
            self._show_transitions_dialog(True, row)

    def _show_event_dialog(self, is_edit=False, row=-1):
        """
        添加事件或修改事件对话框
        :param is_edit:
        :param row:
        :return:
        """
        # 获取待处理的状态
        pro_state = self._get_pro_state()
        if pro_state is None:
            return

        dialog = QtWidgets.QDialog(self)
        dialog.setWindowTitle("编辑事件" if is_edit else "添加事件")
        layout = QtWidgets.QFormLayout(dialog)
        # 移除 "?" 按钮
        dialog.setWindowFlags(dialog.windowFlags() & ~QtCore.Qt.WindowContextHelpButtonHint)
        # 创建输入框
        entries = []
        if is_edit:
            data = [self.table_state_machine_event.item(row, col).text() if self.table_state_machine_event.item(row, col) is not None else None
                   for col in range(self.table_state_machine_event.columnCount())]
        else:
            data = [""] * self.table_state_machine_event.columnCount()

        # 为每一列创建输入框
        for col in range(self.table_state_machine_event.columnCount()):
            header = self.table_state_machine_event.horizontalHeaderItem(col).text()
            line_edit = QtWidgets.QLineEdit(data[col])
            layout.addRow(header, line_edit)
            entries.append(line_edit)

        # 添加确定和取消按钮
        buttons = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel,
            QtCore.Qt.Horizontal, dialog)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addRow(buttons)

        # 显示对话框并处理结果
        if dialog.exec_() == QtWidgets.QDialog.Accepted:
            new_data = [entry.text() for entry in entries]
            #检验输入规范性
            if new_data[0] == '' or new_data[0] is None:
                QtWidgets.QMessageBox.warning(
                    self,
                    "警告",
                    "事件名称不能为空！",
                    QtWidgets.QMessageBox.Ok
                )
                return

            new_event_name = new_data[0]
            new_event_guard = new_data[1]
            if is_edit:
                is_validate = True
                old_event_name = self.table_state_machine_event.item(row, 0).text()
                old_event = None

                if pro_state.id in self.d_all_event:
                    for cur_event in self.d_all_event[pro_state.id]:
                        if cur_event.name == old_event_name:
                            old_event = cur_event
                        if new_event_name == cur_event.name and old_event_name != cur_event.name:
                            is_validate = False

                if not is_validate:
                    QtWidgets.QMessageBox.warning(
                        self,
                        "警告",
                        "事件名称已经存在！",
                        QtWidgets.QMessageBox.Ok
                    )
                    return
                if old_event is not None:
                        # 输入的事件名称不能已经存在
                        old_event.name = new_event_name
                        old_event.guard = new_event_guard
            else:
                is_validate = True
                if pro_state.id in self.d_all_event:
                    for cur_event in self.d_all_event[pro_state.id]:
                        if new_event_name == cur_event.name:
                            is_validate = False

                if not is_validate:
                    QtWidgets.QMessageBox.warning(
                        self,
                        "警告",
                        "事件名称已经存在！",
                        QtWidgets.QMessageBox.Ok
                    )
                    return
                new_event = Event(new_event_name, new_event_guard)
                if pro_state.id not in self.d_all_event:
                    self.d_all_event[pro_state.id] = []
                self.d_all_event[pro_state.id].append(new_event)
                self.state_chart.events.add(new_event)
            # 重新加载表格
            cur_state_item = self.tree_state_machine_all_state.currentItem()
            self._display_state_event_transition_details(cur_state_item)

    def _show_transitions_dialog(self, is_edit=False, row=-1):
        """
        添加迁移或修改迁移对话框
        :param is_edit:
        :param row:
        :return:
        """
        # 获取代处理的状态
        pro_state = self._get_pro_state()
        if pro_state is None:
            return

        dialog = QtWidgets.QDialog(self)
        dialog.setWindowTitle("编辑迁移" if is_edit else "添加迁移")
        layout = QtWidgets.QFormLayout(dialog)
        # 移除 "?" 按钮
        dialog.setWindowFlags(dialog.windowFlags() & ~QtCore.Qt.WindowContextHelpButtonHint)
        # 创建输入框
        entries = []
        if is_edit:
            data = [self.table_state_machine_transition.item(row, col).text() if self.table_state_machine_transition.item(row, col) is not None else None
                    for col in range(self.table_state_machine_transition.columnCount())]
        else:
            data = [""] * self.table_state_machine_transition.columnCount()

        # 为每一列创建输入框
        for col in range(self.table_state_machine_transition.columnCount()):
            header = self.table_state_machine_transition.horizontalHeaderItem(col).text()
            line_edit = QtWidgets.QLineEdit(data[col])
            layout.addRow(header, line_edit)
            entries.append(line_edit)

        # 添加确定和取消按钮
        buttons = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel,
            QtCore.Qt.Horizontal, dialog)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addRow(buttons)

        # 显示对话框并处理结果
        if dialog.exec_() == QtWidgets.QDialog.Accepted:
            new_data = [entry.text() for entry in entries]
            if (new_data[0] == '' or new_data[0] is None or
                new_data[1] == '' or new_data[1] is None):
                QtWidgets.QMessageBox.warning(
                    self,
                    "警告",
                    "迁移目标状态或事件不能为空！",
                    QtWidgets.QMessageBox.Ok
                )
                return
            new_transition_event_name = new_data[0]
            new_transition_target_name = new_data[1]
            new_transition_event = self.state_chart.events.get_by_name(new_transition_event_name)
            new_transition_target_state = self.state_chart.states.get_by_name(new_transition_target_name)
            if not new_transition_event or not new_transition_target_state:
                QtWidgets.QMessageBox.warning(
                    self,
                    "警告",
                    "迁移目标状态或事件不存在！",
                    QtWidgets.QMessageBox.Ok
                )
                return

            if is_edit:
                old_transition_event_name = self.table_state_machine_transition.item(row, 0).text()
                old_transition_target_name = self.table_state_machine_transition.item(row, 1).text()

                old_transition_target_state = self.state_chart.states.get_by_name(old_transition_target_name)
                old_transition = None
                if pro_state.id in self.d_all_transition:

                    for cur_transition in self.d_all_transition[pro_state.id]:
                        cur_event_id = cur_transition.event_id
                        cur_event = self.state_chart.events.get(cur_event_id)

                        if (cur_event and cur_transition.src_state_id == pro_state.id and
                                cur_transition.dst_state_id == old_transition_target_state.id and
                                cur_event.name == old_transition_event_name):
                            old_transition = cur_transition
                            break

                if old_transition is not None:
                    old_transition.dst_state = self.state_chart.states.get_by_name(new_transition_target_name)
                    old_transition.event = self.state_chart.events.get_by_name(new_transition_event_name)
            else:
                new_transition = Transition(pro_state, new_transition_target_state, new_transition_event)
                self.state_chart.transitions.add(new_transition)
                if pro_state.id not in self.d_all_transition:
                    self.d_all_transition[pro_state.id] = []
                self.d_all_transition[pro_state.id].append(new_transition)

            # 重新加载表格
            cur_state_item = self.tree_state_machine_all_state.currentItem()
            self._display_state_event_transition_details(cur_state_item)

    def _init_button_state_machine_add_event(self):
        self.button_state_machine_add_event.clicked.connect(lambda: self._show_event_dialog(False))

    def _init_button_state_machine_add_transition(self):
        self.button_state_machine_add_transition.clicked.connect(lambda: self._show_transitions_dialog(False))

    def _init_tree_state_machine_all_state_context_menu(self):
        self.tree_state_machine_all_state.setContextMenuPolicy(Qt.CustomContextMenu)

        self.tree_state_machine_all_state.customContextMenuRequested.connect(lambda pos: self.show_tree_state_machine_all_state_context_menu(pos))

    def show_tree_state_machine_all_state_context_menu(self, position: QPoint):
        item = self.tree_state_machine_all_state.itemAt(position)
        if item is None:
            return

        state = item.data(0, Qt.UserRole)
        if state is None:
            return

        menu = QtWidgets.QMenu()
        edit_action = QtWidgets.QAction("修改状态", self)
        add_action = QtWidgets.QAction("添加子状态", self)
        delete_action = QtWidgets.QAction("删除状态", self)
        set_initial_action = QtWidgets.QAction("设为初始状态", self)

        edit_action.triggered.connect(lambda: self.edit_state(item, state))
        add_action.triggered.connect(lambda: self.add_sub_state(item, state))
        delete_action.triggered.connect(lambda: self.delete_state(item, state))
        set_initial_action.triggered.connect(lambda: self.set_as_initial_state(state))

        menu.addAction(edit_action)
        menu.addAction(add_action)
        menu.addAction(delete_action)
        menu.addAction(set_initial_action)

        menu.exec_(self.tree_state_machine_all_state.viewport().mapToGlobal(position))

    def edit_state(self, item, state):
        self._add_state(father_state=None, is_edit=True)

    def add_sub_state(self, parent_item, parent_state):
        self._add_state(father_state=parent_state, is_edit=False)

    def delete_state(self, item, state):

        def recursive_delete_state(cur_state: State):
            if cur_state is None:
                return
            #删除与当前状态关联的事件和迁移
            if cur_state.id in self.d_all_event:
                for cur_event in self.d_all_event[cur_state.id]:
                    del self.state_chart.events[cur_event]
                del self.d_all_event[cur_state.id]

            if cur_state.id in self.d_all_transition:
                for cur_transition in self.d_all_transition[cur_state.id]:
                    del self.state_chart.transitions[cur_transition]
                del self.d_all_transition[cur_state.id]

            if cur_state.id in self.d_id_father_state:
                del self.d_id_father_state[cur_state.id]

            del self.state_chart.states[cur_state]
            if isinstance(cur_state, CompositeState):
                for son_state in cur_state.states:
                    recursive_delete_state(son_state)

        if state.id == self.state_chart.root_state.id:
            QtWidgets.QMessageBox.warning(
                self,
                "警告",
                "状态机根节点不能删除！",
                QtWidgets.QMessageBox.Ok
            )
            return

        reply = QtWidgets.QMessageBox.question(self, "删除确认", f"确定要删除状态 '{state.name}' 及其所有子状态吗？",
                                     QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No)

        if reply == QtWidgets.QMessageBox.Yes:
            parent_item = item.parent()
            if parent_item:
                parent_state = parent_item.data(0, Qt.UserRole)
                del parent_state.states[state]
                parent_item.removeChild(item)
            else:
                index = self.tree_state_machine_all_state.indexOfTopLevelItem(item)
                self.tree_state_machine_all_state.takeTopLevelItem(index)

            # 如果待删除状态为CompositeState的话，要递归删除子状态以及相关的迁移和事件
            if isinstance(state, CompositeState):
                recursive_delete_state(state)

    def set_as_initial_state(self, state):
        parent_item = self.tree_state_machine_all_state.currentItem().parent()
        #如果是设置整个状态机的初始状态：
        if not parent_item:
            if self.state_chart.root_state.id == state.id:
                return
            QtWidgets.QMessageBox.warning(self, "操作无效", "状态机根节点不能修改")
            return

        parent_state = parent_item.data(0, Qt.UserRole)
        if isinstance(parent_state, CompositeState):
            parent_state.initial_state = state
            QtWidgets.QMessageBox.information(self, "成功", f"{state.name} 已被设为初始状态")

    def _init_button_state_machine_add_state(self):
        self.button_state_machine_add_state.clicked.connect(lambda: self._add_state(None, False))

    def _init_button_state_machine_export(self):
        self.button_state_machine_export.clicked.connect(lambda: self._export_statechart())

    def _init_button_state_machine_validation(self):
        self.button_state_machine_validation.clicked.connect(lambda: self._validate_statechart())

    def _init_button_state_machine_graph_gen(self):
        self.button_state_machine_graph_gen.clicked.connect(lambda: self._graph_gen())

    def _init_tree_state_machine_all_state(self):
        self.tree_state_machine_all_state.itemClicked.connect(
            lambda item, _: self._display_state_event_transition_details(item)
        )

    def _display_state_event_transition_details(self, item):
        cur_state = item.data(0, Qt.UserRole)
        if not cur_state:
            return
        # 更新 Events 表格
        self.table_state_machine_event.setRowCount(0)
        if cur_state.id in self.d_all_event:
            for event in self.d_all_event[cur_state.id]:
                row = self.table_state_machine_event.rowCount()
                self.table_state_machine_event.insertRow(row)
                self.table_state_machine_event.setItem(row, 0, QtWidgets.QTableWidgetItem(event.name))
                self.table_state_machine_event.setItem(row, 1, QtWidgets.QTableWidgetItem(event.guard))

        # 更新 Transitions 表格
        self.table_state_machine_transition.setRowCount(0)
        if cur_state.id in self.d_all_transition:
            for transition in self.d_all_transition[cur_state.id]:
                row = self.table_state_machine_transition.rowCount()
                self.table_state_machine_transition.insertRow(row)
                self.table_state_machine_transition.setItem(row, 0, QtWidgets.QTableWidgetItem(transition.event.name))
                self.table_state_machine_transition.setItem(row, 1,
                                                            QtWidgets.QTableWidgetItem(transition.dst_state.name))

    def _add_state(self, father_state: Optional[CompositeState], is_edit = False):
        """
        保存状态信息，并使用QTreeWidget展示状态
        """
        new_state = None
        if is_edit:
            # 获取当前编辑状态
            pro_state = self._get_pro_state()
            dialog = DialogEditState(self, state_chart=self.state_chart, root_state= self.state_chart.root_state,
                                     is_edit=True, initial_data=pro_state)
            if dialog.exec_() == QtWidgets.QDialog.Accepted:
                new_state = dialog.get_state()
                # 更新逻辑，删除原状态，并添加新状态
                del self.state_chart.states[pro_state]
                self.state_chart.states.add(new_state)
                cur_tree_item = self.tree_state_machine_all_state.currentItem()
                cur_tree_item.setText(0, new_state.name)
                cur_tree_item.setData(0, Qt.UserRole, new_state)
        else:
            if father_state is not None and not isinstance(father_state, CompositeState):
                QtWidgets.QMessageBox.warning(self, "错误", "只有composite类型能拥有子状态！")
                return
            # 添加新状态
            dialog = DialogEditState(self, state_chart=self.state_chart, root_state= self.state_chart.root_state,
                                     is_edit=False, initial_data=None)
            if dialog.exec_() == QtWidgets.QDialog.Accepted:
                new_state = dialog.get_state()

                cur_state_item = QtWidgets.QTreeWidgetItem([new_state.name])
                cur_state_item.setData(0, Qt.UserRole, new_state)
                self.state_chart.states.add(new_state)
                # 如果是添加子状态：
                if father_state is not None:
                    father_item = self.tree_state_machine_all_state.currentItem()
                    self.d_id_father_state[new_state.id] = father_state
                    father_state.states.add(new_state)
                    father_item.addChild(cur_state_item)
                else:
                    self.d_id_father_state[new_state.id] = None
                    self.tree_state_machine_all_state.addTopLevelItem(cur_state_item)

        '''
        if new_state is not None:
            max_time_lock = new_state.max_time_lock
            if max_time_lock is not None:
                max_time_lock_event = Event('max_time', f"{new_state.name}_count > {max_time_lock}")
                self.d_all_event[new_state.id].append(max_time_lock_event)
                self.state_chart.events.add(max_time_lock_event)
        '''
        #重置输入框
        #self._reset_input_fields()

    def _import_statechart(self):
        """导入 StateChart 文件"""
        file_path, _ = QtWidgets.QFileDialog.getOpenFileName(self, "选择json文件", "./", "JSON Files (*.json);;All Files (*)")
        if not file_path:
            return
        self.state_chart = Statechart.read_json(file_path)
        self.d_all_event.clear()
        self.d_all_transition.clear()
        self.d_id_father_state.clear()
        self.tree_state_machine_all_state.clear()
        #在导入时，要根据transition来定位哪个事件和迁移属于哪个状态
        for cur_transition in self.state_chart.transitions:
            src_state = cur_transition.src_state
            dst_state = cur_transition.dst_state
            event = cur_transition.event
            #TODO:出错时处理
            if src_state is None or dst_state is None or event is None:
                continue
            if src_state.id not in self.d_all_transition:
                self.d_all_transition[src_state.id] = []
            if src_state.id not in self.d_all_event:
                self.d_all_event[src_state.id] = []
            self.d_all_transition[src_state.id].append(cur_transition)
            self.d_all_event[src_state.id].append(event)

        if self.at_page_initial:
            self.stackedWidget_state_machine.setCurrentIndex(1)
            self.at_page_initial = False
        self.edit_state_machine_name.setText(self.state_chart.name)
        self.edit_state_machine_preamble.setPlainText('\n'.join(self.state_chart.preamble))
        #根据导入状态机的信息填充tree_state_machine_all_state
        self._populate_tree_state_machine_all_state(self.tree_state_machine_all_state, self.state_chart.root_state)

    def _populate_tree_state_machine_all_state(self, tree_widget: QtWidgets.QTreeWidget, root_state: CompositeState):
        tree_widget.clear()

        def add_state_to_tree(parent_item, state):
            item = QtWidgets.QTreeWidgetItem([state.name])
            item.setData(0, Qt.UserRole, state)

            if parent_item:
                parent_state = parent_item.data(0, Qt.UserRole)
                self.d_id_father_state[state.id] = parent_state
                parent_item.addChild(item)
            else:
                tree_widget.addTopLevelItem(item)
            if isinstance(state, CompositeState):
                for child_state in state.states:
                    add_state_to_tree(item, child_state)

        add_state_to_tree(None, root_state)
        tree_widget.expandAll()

    def _export_statechart(self):
        self.show_state_machine_graph()
        options = QtWidgets.QFileDialog.Options()
        # 弹出保存文件对话框，默认扩展名为 .json
        file_name, _ = QtWidgets.QFileDialog.getSaveFileName(
            self,
            "保存为JSON文件",
            "./",
            "JSON Files (*.json);;All Files (*)",
            options=options
        )
        if file_name:
            # 确保文件名以 .json 结尾
            if not file_name.endswith('.json'):
                file_name += '.json'
            state_machine_name = self.edit_state_machine_name.text()
            state_machine_preamble = self.edit_state_machine_preamble.toPlainText().splitlines()
            if state_machine_name == '' or state_machine_name is None:
                QtWidgets.QMessageBox.warning(
                    self,
                    "警告",
                    "状态机名称不能为空！",
                    QtWidgets.QMessageBox.Ok
                )
                return
            self.state_chart.name = state_machine_name
            if len(state_machine_preamble) > 0:
                self.state_chart.preamble = state_machine_preamble
            self.state_chart.to_json(file_name)

    def _validate_statechart(self):
        try:
            self.state_chart.validate()
            QtWidgets.QMessageBox.information(self, "验证成功", "状态图验证通过，无错误。")
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "错误", f"具有以下错误：\n{str(e)}")

    def _graph_gen(self):
        pass

    def show_state_machine_graph(self):
        state_machine_data = {
            'name': self.state_chart.name,
            'preamble': 'n'.join(self.state_chart.preamble),
            'root state': self.get_state_dict(self.state_chart.root_state)
        }
        state_machine = {
            'statechart': state_machine_data,
        }
        show_state_graph(state_machine)

    def get_state_dict(self, cur_state: NormalState):
        transition_list = []
        if cur_state.id in self.d_all_transition:
            for cur_transition in self.d_all_transition[cur_state.id]:
                cur_transition_dict = {
                    'target': cur_transition.dst_state.name,
                    'event': cur_transition.event.name
                }
                transition_list.append(cur_transition_dict)

        states_list = []
        if isinstance(cur_state, CompositeState):
            for sub_state in cur_state.states:
                cur_sub_state_dict = self.get_state_dict(sub_state)
                states_list.append(cur_sub_state_dict)

        cur_state_dict = {
            'name': cur_state.name
        }
        if isinstance(cur_state, CompositeState):
            cur_state_dict['states'] = states_list
            if cur_state.initial_state_id is not None:
                cur_state_dict['initial'] = cur_state.initial_state.name

        cur_state_dict['transitions'] = transition_list
        if cur_state.on_entry is not None:
            cur_state_dict['on entry'] = cur_state.on_entry
        if cur_state.on_exit is not None:
            cur_state_dict['on exit'] = cur_state.on_exit
        return cur_state_dict

    def _get_pro_state(self) -> Optional[State]:
        # 获得当前Tree中选择的item
        selected_state_item = self.tree_state_machine_all_state.currentItem()
        # 若没有选中状态，则报错
        if not selected_state_item:
            QtWidgets.QMessageBox.warning(self, "提示", "请先选择要编辑的状态")
            return None
        pro_state = selected_state_item.data(0, Qt.UserRole)
        return pro_state

