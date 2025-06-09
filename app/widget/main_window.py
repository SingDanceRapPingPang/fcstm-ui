from typing import Optional
import os

import PyQt5.Qt
from PyQt5 import QtWidgets
from PyQt5.Qt import QMainWindow
from PyQt5.QtCore import Qt, QPoint
import qtawesome as qta
from pyfcstm.model import State, CompositeState, Statechart

from app.ui import UIMainWindow
from app.utils.c_code_editor import CCodeEditor
from app.utils.create_formLayout_dialog import create_formlayout_dialog
from app.utils.fcstm_state_chart import FcstmStateChart
from app.utils.export_to_word import export_statechart_to_word
from app.utils.export_to_excel import export_statechart_to_excel
from .dialog_edit_state import DialogEditState
from .dialog_show_graph import DialogShowGraph

class AppMainWindow(QMainWindow, UIMainWindow):
    
    fcstm_state_chart: Optional[FcstmStateChart]

    def __init__(self):
        QMainWindow.__init__(self)
        self.setupUi(self)
        self.at_page_initial = True
        self.fcstm_state_chart = None
        self.code_file_path = "./"
        self.state_machine_file_path = "./"
        self._init()

    def _init(self):
        #添加代码编辑器并设置格式
        self._init_code_editor()
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
        self._init_tree_state_machine_all_state_context_menu()
        #初始化tabWidget在点击代码生成后的初始化动作
        self._init_tab_widget_init()
        #初始化导出按钮
        self._init_button_state_machine_export()
        #初始化新建状态机按钮
        self._init_button_initial_new_state_machine()
        #初始化验证按钮
        self._init_button_state_machine_validation()
        #初始化图生成按钮
        self._init_button_state_machine_graph_gen()
        #保存代码按钮
        self._init_button_code_gen_code_save()
        #展开所有状态按钮
        self._init_button_state_machine_expand_all()
        self._init_button_code_gen_expand_all()
        #折叠所有状态按钮
        self._init_button_state_machine_fold_all()
        self._init_button_code_gen_fold_all()
        '''
        self._init_button_save_state()
        '''

    def _init_code_editor(self):
        """初始化代码编辑器"""
        # 创建代码编辑器
        self.code_editor = CCodeEditor(self.widget_code_ide)

        # 创建布局
        layout = QtWidgets.QVBoxLayout(self.widget_code_ide)
        layout.setContentsMargins(0, 0, 0, 0)  # 设置边距为0
        layout.addWidget(self.code_editor)

        # 设置示例代码（可选）
        self.code_editor.set_text("""#include <stdio.h>
    int main() {
        printf("Hello, world!\\n");
        return 0;
    }""")

    def _init_window_style(self):
        self._init_table_style()
        self._init_tree_style()
        self._init_button_style()

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
        state_chart = Statechart(name=state_machine_name[0], root_state=root_state, states=states)
        self.fcstm_state_chart = FcstmStateChart(self.tree_state_machine_all_state, state_chart)
        self.edit_state_machine_name.setText(state_machine_name[0])
        
        if self.at_page_initial:
            self.stackedWidget_state_machine.setCurrentIndex(1)
            self.at_page_initial = False

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
        self.tree_state_machine_all_state.setTextElideMode(Qt.ElideNone)
        self.tree_state_machine_all_state.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        #self.tree_state_machine_all_state.setHorizontalScrollMode(QtWidgets.QAbstractItemView.ScrollPerPixel)
        self.tree_state_machine_all_state.header().setMinimumSectionSize(800)
        self.tree_state_machine_all_state.setAutoScroll(False)
        
        self.tree_code_gen_all_state.header().hide()
        self.tree_code_gen_all_state.setTextElideMode(Qt.ElideNone)
        self.tree_code_gen_all_state.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        #self.tree_code_gen_all_state.setHorizontalScrollMode(QtWidgets.QAbstractItemView.ScrollPerPixel)
        self.tree_code_gen_all_state.header().setMinimumSectionSize(800)
        self.tree_code_gen_all_state.setAutoScroll(False)

    def _init_button_style(self):
        button_style = """
            QToolButton {
                border: none;
                background-color: #FFFACD;
                font-size: 20px;
                padding: 50px 16px 8px 16px;  /* 上 右 下 左 的内边距 */
                border-radius: 6px;
                spacing: 5px;  /* 图标和文字之间的间距 */
            }

            QToolButton:hover {
                background-color: #ADD8E6;
            }

            QToolButton:pressed {
                background-color: #ADD8E6;
            }
        """
        self.button_initial_new_state_machine.setMinimumSize(300, 300)
        self.button_initial_import_state_machine.setMinimumSize(300, 300)
        self.button_initial_new_state_machine.setStyleSheet(button_style)
        self.button_initial_import_state_machine.setStyleSheet(button_style)
        
        # 设置按钮图标和文字
        new_icon = qta.icon('fa5s.plus-circle', color='#000000')
        import_icon = qta.icon('fa5s.file-import', color='#000000')
        
        self.button_initial_new_state_machine.setIcon(new_icon)
        self.button_initial_import_state_machine.setIcon(import_icon)
        
        # 设置图标大小
        icon_size = 64
        self.button_initial_new_state_machine.setIconSize(PyQt5.Qt.QSize(icon_size, icon_size))
        self.button_initial_import_state_machine.setIconSize(PyQt5.Qt.QSize(icon_size, icon_size))
        
        # 设置文字在图标下方
        self.button_initial_new_state_machine.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)
        self.button_initial_import_state_machine.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)

    def _init_table_context_menus(self):
        # 设置表格的上下文菜单策略
        self.table_state_machine_event.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table_state_machine_transition.setContextMenuPolicy(Qt.CustomContextMenu)
        
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
        if table == self.table_state_machine_event:
            event_name = table.item(row, 0).text() if table.item(row, 0) is not None else None
            event_guard = table.item(row, 1).text() if table.item(row, 1) is not None else None

            #同步删除transition中的内容
            reply = QtWidgets.QMessageBox.question(self, "删除确认", f"删除'{event_name}'事件，会同时删除关联的迁移，确定要继续删除吗",
                                                   QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No)

            if reply == QtWidgets.QMessageBox.No:
                return
            self.fcstm_state_chart.del_event(self, event_name)

        elif table == self.table_state_machine_transition:
            transition_src_name = table.item(row, 0).text() if table.item(row, 0) is not None else None
            transition_event_name = table.item(row, 1).text() if table.item(row, 1) is not None else None
            transition_target_name = table.item(row, 2).text() if table.item(row, 2) is not None else None
            self.fcstm_state_chart.del_transition(self, transition_src_name, transition_event_name, transition_target_name)
        # 更新表格
        self._display_state_event_transition_details()

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
        dialog = QtWidgets.QDialog(self)
        dialog.setWindowTitle("编辑事件" if is_edit else "添加事件")
        layout = QtWidgets.QFormLayout(dialog)
        # 移除 "?" 按钮
        dialog.setWindowFlags(dialog.windowFlags() & ~Qt.WindowContextHelpButtonHint)
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
            Qt.Horizontal, dialog)
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
                old_event_name = self.table_state_machine_event.item(row, 0).text()
                self.fcstm_state_chart.edit_event(self, new_event_name, new_event_guard, old_event_name)
            else:
                self.fcstm_state_chart.add_event(self, new_event_name, new_event_guard)
            # 重新加载表格
            self._display_state_event_transition_details()

    def _show_transitions_dialog(self, is_edit=False, row=-1):
        """
        添加迁移或修改迁移对话框
        :param is_edit:
        :param row:
        :return:
        """
        dialog = QtWidgets.QDialog(self)
        dialog.setWindowTitle("编辑迁移" if is_edit else "添加迁移")
        layout = QtWidgets.QFormLayout(dialog)
        # 移除 "?" 按钮
        dialog.setWindowFlags(dialog.windowFlags() & ~Qt.WindowContextHelpButtonHint)
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
            Qt.Horizontal, dialog)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addRow(buttons)

        # 显示对话框并处理结果
        if dialog.exec_() == QtWidgets.QDialog.Accepted:
            new_data = [entry.text() for entry in entries]
            if (new_data[0] == '' or new_data[0] is None or
                new_data[1] == '' or new_data[1] is None or
                new_data[2] == '' or new_data[2] is None):
                QtWidgets.QMessageBox.warning(
                    self,
                    "警告",
                    "迁移目标状态或事件不能为空！",
                    QtWidgets.QMessageBox.Ok
                )
                return
            new_transition_src_name = new_data[0]
            new_transition_event_name = new_data[1]
            new_transition_target_name = new_data[2]
            new_transition_src_state = self.fcstm_state_chart.state_chart.states.get_by_name(new_transition_src_name)
            new_transition_event = self.fcstm_state_chart.state_chart.events.get_by_name(new_transition_event_name)
            new_transition_target_state = self.fcstm_state_chart.state_chart.states.get_by_name(new_transition_target_name)
            if new_transition_src_state is None or new_transition_event is None or new_transition_target_state is None:
                QtWidgets.QMessageBox.warning(
                    self,
                    "警告",
                    "迁移目标状态或事件不存在！",
                    QtWidgets.QMessageBox.Ok
                )
                return

            if is_edit:
                old_transition_src_name = self.table_state_machine_transition.item(row, 0).text()
                old_transition_event_name = self.table_state_machine_transition.item(row, 1).text()
                old_transition_target_name = self.table_state_machine_transition.item(row, 2).text()
                old_transition_src_state = self.fcstm_state_chart.state_chart.states.get_by_name(old_transition_src_name)
                old_transition_target_state = self.fcstm_state_chart.state_chart.states.get_by_name(old_transition_target_name)
                old_transition_event = self.fcstm_state_chart.state_chart.events.get_by_name(old_transition_event_name)

                self.fcstm_state_chart.edit_transition(self, old_transition_src_state, old_transition_target_state,
                                                       old_transition_event, new_transition_src_state,
                                                       new_transition_target_state, new_transition_event)

            else:
                self.fcstm_state_chart.add_transition(self, new_transition_src_state, new_transition_target_state,
                                                      new_transition_event)

            # 重新加载表格
            self._display_state_event_transition_details()

    def _init_button_state_machine_add_event(self):
        self.button_state_machine_add_event.clicked.connect(lambda: self._show_event_dialog(False))

    def _init_button_state_machine_add_transition(self):
        self.button_state_machine_add_transition.clicked.connect(lambda: self._show_transitions_dialog(False))

    def _init_tree_state_machine_all_state_context_menu(self):
        self.tree_state_machine_all_state.setContextMenuPolicy(Qt.CustomContextMenu)

        self.tree_state_machine_all_state.customContextMenuRequested.connect(lambda pos: self.show_tree_state_machine_all_state_context_menu(pos))

    def _init_tab_widget_init(self):
        self.tabWidget.currentChanged.connect(self._handle_tab_changed)

    def _handle_tab_changed(self, index):
        if index == 1 and self.fcstm_state_chart is not None:
            #填充tree_code_gen_all_state
            self.fcstm_state_chart.populate_tree_state_machine_all_state(self.tree_code_gen_all_state)
            self.tree_code_gen_all_state.expandAll()

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

        if state.id == self.fcstm_state_chart.state_chart.root_state.id:
            QtWidgets.QMessageBox.warning(
                self,
                "警告",
                "状态机根节点不能删除！",
                QtWidgets.QMessageBox.Ok
            )
            return

        reply = QtWidgets.QMessageBox.question(self, "删除确认", f"确定要删除状态 '{state.name}' 和其所有子状态，以及有关的迁移吗？",
                                     QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No)

        if reply == QtWidgets.QMessageBox.Yes:
            self.fcstm_state_chart.del_state(item, state)
            # 更新表格
            self._display_state_event_transition_details()

    def set_as_initial_state(self, state):
        parent_item = self.tree_state_machine_all_state.currentItem().parent()
        #如果是设置整个状态机的初始状态：
        #TODO:fcstm中statechart的root_state并不能设置
        if not parent_item:
            if self.fcstm_state_chart.state_chart.root_state.id == state.id:
                return
            QtWidgets.QMessageBox.warning(self, "操作无效", "状态机根节点不能修改")
            return

        parent_state = parent_item.data(0, Qt.UserRole)
        if isinstance(parent_state, CompositeState):
            self.fcstm_state_chart.change_initial_state(parent_state, state)

    def _init_button_state_machine_add_state(self):
        self.button_state_machine_add_state.clicked.connect(lambda: self._add_state(None, False))

    def _init_button_state_machine_export(self):
        self.button_state_machine_export.clicked.connect(lambda: self._export_statechart())

    def _init_button_state_machine_validation(self):
        self.button_state_machine_validation.clicked.connect(lambda: self._validate_statechart())

    def _init_button_state_machine_graph_gen(self):
        self.button_state_machine_graph_gen.clicked.connect(lambda: self._graph_gen())

    def _init_button_code_gen_code_save(self):
        self.button_code_gen_code_save.clicked.connect(lambda: self._save_c_code())

    def _init_button_state_machine_expand_all(self):
        self.button_state_machine_expand_all.setToolTip("展开所有")
        expand_icon = qta.icon('fa5s.angle-down', color='#000000')
        self.button_state_machine_expand_all.setIcon(expand_icon)
        self.button_state_machine_expand_all.setIconSize(PyQt5.Qt.QSize(25, 25))
        self.button_state_machine_expand_all.clicked.connect(lambda: self._expand_all_state(self.tree_state_machine_all_state))

    def _init_button_state_machine_fold_all(self):
        self.button_state_machine_fold_all.setToolTip("折叠所有")
        fold_icon = qta.icon('fa5s.angle-up', color='#000000')
        self.button_state_machine_fold_all.setIcon(fold_icon)
        self.button_state_machine_fold_all.setIconSize(PyQt5.Qt.QSize(25, 25))
        self.button_state_machine_fold_all.clicked.connect(lambda: self._fold_all_state(self.tree_state_machine_all_state))

    def _init_button_code_gen_expand_all(self):
        self.button_code_gen_expand_all.setToolTip("展开所有")
        expand_icon = qta.icon('fa5s.angle-down', color='#000000')
        self.button_code_gen_expand_all.setIcon(expand_icon)
        self.button_code_gen_expand_all.setIconSize(PyQt5.Qt.QSize(25, 25))
        self.button_code_gen_expand_all.clicked.connect(lambda: self._expand_all_state(self.tree_code_gen_all_state))

    def _init_button_code_gen_fold_all(self):
        self.button_code_gen_fold_all.setToolTip("折叠所有")
        fold_icon = qta.icon('fa5s.angle-up', color='#000000')
        self.button_code_gen_fold_all.setIcon(fold_icon)
        self.button_code_gen_fold_all.setIconSize(PyQt5.Qt.QSize(25, 25))
        self.button_code_gen_fold_all.clicked.connect(lambda: self._fold_all_state(self.tree_code_gen_all_state))

    def _save_c_code(self):
        try:
            # 检查上次使用的路径是否存在
            if not os.path.exists(self.code_file_path):
                self.code_file_path = "./"
                
            code = self.code_editor.get_text()
            if not code:
                QtWidgets.QMessageBox.warning(
                    self,
                    "警告",
                    "没有可保存的代码！",
                    QtWidgets.QMessageBox.Ok
                )
                return

            file_name, selected_filter = QtWidgets.QFileDialog.getSaveFileName(
                self,
                "保存代码文件",
                self.code_file_path,
                "C Source Files (*.c);;C Header Files (*.h);;All Files (*)",
                options=QtWidgets.QFileDialog.Options()
            )

            if file_name:
                # 更新上次使用的路径
                self.code_file_path = os.path.dirname(file_name)
                
                if selected_filter == "C Source Files (*.c)" and not file_name.endswith('.c'):
                    file_name += '.c'
                elif selected_filter == "C Header Files (*.h)" and not file_name.endswith('.h'):
                    file_name += '.h'

                try:
                    with open(file_name, 'w', encoding='utf-8') as f:
                        f.write(code)
                    QtWidgets.QMessageBox.information(
                        self,
                        "保存成功",
                        f"代码已成功保存到：\n{file_name}",
                        QtWidgets.QMessageBox.Ok
                    )
                except Exception as e:
                    QtWidgets.QMessageBox.critical(
                        self,
                        "保存失败",
                        f"保存文件时发生错误：\n{str(e)}",
                        QtWidgets.QMessageBox.Ok
                    )
        except Exception as e:
            QtWidgets.QMessageBox.critical(
                self,
                "错误",
                f"保存代码时发生错误：\n{str(e)}",
                QtWidgets.QMessageBox.Ok
            )

    def _expand_all_state(self, tree_widget: QtWidgets.QTreeWidget):
        tree_widget.expandAll()

    def _fold_all_state(self, tree_widget: QtWidgets.QTreeWidget):
        tree_widget.collapseAll()

    def _display_state_event_transition_details(self):
        try:
            if self.fcstm_state_chart is None:
                return

            # 更新 Events 表格
            self.table_state_machine_event.setRowCount(0)
            for event in self.fcstm_state_chart.state_chart.events:
                row = self.table_state_machine_event.rowCount()
                self.table_state_machine_event.insertRow(row)
                self.table_state_machine_event.setItem(row, 0, QtWidgets.QTableWidgetItem(event.name))
                self.table_state_machine_event.setItem(row, 1, QtWidgets.QTableWidgetItem(event.guard))

            # 更新 Transitions 表格
            self.table_state_machine_transition.setRowCount(0)
            for transition in self.fcstm_state_chart.state_chart.transitions:
                row = self.table_state_machine_transition.rowCount()
                self.table_state_machine_transition.insertRow(row)
                self.table_state_machine_transition.setItem(row, 0, QtWidgets.QTableWidgetItem(transition.src_state.name))
                self.table_state_machine_transition.setItem(row, 1, QtWidgets.QTableWidgetItem(transition.event.name))
                self.table_state_machine_transition.setItem(row, 2, QtWidgets.QTableWidgetItem(transition.dst_state.name))
        except Exception as e:
            QtWidgets.QMessageBox.critical(
                self,
                "错误",
                f"更新状态机详情时发生错误：\n{str(e)}",
                QtWidgets.QMessageBox.Ok
            )

    def _add_state(self, father_state: Optional[CompositeState], is_edit = False):
        """
        保存状态信息，并使用QTreeWidget展示状态
        """
        try:
            new_state = None
            if is_edit:
                # 获取当前编辑状态
                pro_state = self._get_pro_state()
                if pro_state is None:
                    return
                    
                dialog = DialogEditState(self, state_chart=self.fcstm_state_chart.state_chart, root_state= self.fcstm_state_chart.state_chart.root_state,
                                         is_edit=True, initial_data=pro_state)
                if dialog.exec_() == QtWidgets.QDialog.Accepted:
                    new_state = dialog.get_state()
                    if new_state is None:
                        QtWidgets.QMessageBox.warning(
                            self,
                            "警告",
                            "获取新状态信息失败！",
                            QtWidgets.QMessageBox.Ok
                        )
                        return
                    # 更新逻辑，删除原状态，并添加新状态
                    try:
                        self.fcstm_state_chart.edit_state(pro_state, new_state)
                    except Exception as e:
                        QtWidgets.QMessageBox.critical(
                            self,
                            "错误",
                            f"编辑状态时发生错误：\n{str(e)}",
                            QtWidgets.QMessageBox.Ok
                        )
                        return
            else:
                if father_state is not None and not isinstance(father_state, CompositeState):
                    QtWidgets.QMessageBox.warning(self, "错误", "只有composite类型能拥有子状态！")
                    return
                # 添加新状态
                dialog = DialogEditState(self, state_chart=self.fcstm_state_chart.state_chart, root_state= self.fcstm_state_chart.state_chart.root_state,
                                         is_edit=False, initial_data=None)
                if dialog.exec_() == QtWidgets.QDialog.Accepted:
                    new_state = dialog.get_state()
                    if new_state is None:
                        QtWidgets.QMessageBox.warning(
                            self,
                            "警告",
                            "获取新状态信息失败！",
                            QtWidgets.QMessageBox.Ok
                        )
                        return
                    try:
                        self.fcstm_state_chart.add_state(father_state, new_state)
                    except Exception as e:
                        QtWidgets.QMessageBox.critical(
                            self,
                            "错误",
                            f"添加状态时发生错误：\n{str(e)}",
                            QtWidgets.QMessageBox.Ok
                        )
                        return
        except Exception as e:
            QtWidgets.QMessageBox.critical(
                self,
                "错误",
                f"操作状态时发生未知错误：\n{str(e)}",
                QtWidgets.QMessageBox.Ok
            )

    def _import_statechart(self):
        """导入 StateChart 文件"""
        try:
            # 检查上次使用的路径是否存在
            if not os.path.exists(self.state_machine_file_path):
                self.state_machine_file_path = "./"
                
            file_path, _ = QtWidgets.QFileDialog.getOpenFileName(
                self, 
                "选择json文件", 
                self.state_machine_file_path, 
                "JSON Files (*.json);;All Files (*)"
            )
            if not file_path:
                return
                
            # 更新上次使用的路径
            self.state_machine_file_path = os.path.dirname(file_path)
            
            try:
                state_chart = Statechart.read_json(file_path)
            except Exception as e:
                QtWidgets.QMessageBox.critical(
                    self,
                    "导入失败",
                    f"读取JSON文件时发生错误：\n{str(e)}",
                    QtWidgets.QMessageBox.Ok
                )
                return

            self.fcstm_state_chart = FcstmStateChart(self.tree_state_machine_all_state, state_chart)
            try:
                self.fcstm_state_chart.legality_check(self)
            except Exception as e:
                QtWidgets.QMessageBox.warning(
                    self,
                    "警告",
                    f"状态机合法性检查发现问题：\n{str(e)}",
                    QtWidgets.QMessageBox.Ok
                )
                return

            if self.at_page_initial:
                self.stackedWidget_state_machine.setCurrentIndex(1)
                self.at_page_initial = False
            self.edit_state_machine_name.setText(self.fcstm_state_chart.state_chart.name)
            self.edit_state_machine_preamble.setPlainText('\n'.join(self.fcstm_state_chart.state_chart.preamble))
            self.tree_state_machine_all_state.expandAll()
            self._display_state_event_transition_details()
        except Exception as e:
            QtWidgets.QMessageBox.critical(
                self,
                "错误",
                f"导入状态机时发生未知错误：\n{str(e)}",
                QtWidgets.QMessageBox.Ok
            )

    def _export_statechart(self):
        try:
            # 检查上次使用的路径是否存在
            if not os.path.exists(self.state_machine_file_path):
                self.state_machine_file_path = "./"
                
            options = QtWidgets.QFileDialog.Options()
            file_name, selected_filter = QtWidgets.QFileDialog.getSaveFileName(
                self,
                "导出状态机",
                self.state_machine_file_path,
                "JSON Files (*.json);;Word Documents (*.docx);;Excel Files (*.xlsx);;All Files (*)",
                options=options
            )
            
            if not file_name:
                return
                
            # 更新上次使用的路径
            self.state_machine_file_path = os.path.dirname(file_name)
            
            # 更新状态机信息
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
                
            self.fcstm_state_chart.state_chart.name = state_machine_name
            if len(state_machine_preamble) > 0:
                self.fcstm_state_chart.state_chart.preamble = state_machine_preamble
                
            try:
                if selected_filter == "JSON Files (*.json)":
                    # 确保文件名以 .json 结尾
                    if not file_name.endswith('.json'):
                        file_name += '.json'
                    self.fcstm_state_chart.state_chart.to_json(file_name)
                    QtWidgets.QMessageBox.information(
                        self,
                        "导出成功",
                        f"状态机信息已成功导出到：\n{file_name}",
                        QtWidgets.QMessageBox.Ok
                    )
                elif selected_filter == "Word Documents (*.docx)":
                    # 确保文件名以 .docx 结尾
                    if not file_name.endswith('.docx'):
                        file_name += '.docx'
                    if export_statechart_to_word(self.fcstm_state_chart.state_chart, file_name):
                        QtWidgets.QMessageBox.information(
                            self,
                            "导出成功",
                            f"状态机信息已成功导出到：\n{file_name}",
                            QtWidgets.QMessageBox.Ok
                        )
                    else:
                        QtWidgets.QMessageBox.critical(
                            self,
                            "导出失败",
                            "导出Word文档时发生错误",
                            QtWidgets.QMessageBox.Ok
                        )
                elif selected_filter == "Excel Files (*.xlsx)":
                    # 确保文件名以 .xlsx 结尾
                    if not file_name.endswith('.xlsx'):
                        file_name += '.xlsx'
                    if export_statechart_to_excel(self.fcstm_state_chart.state_chart, file_name):
                        QtWidgets.QMessageBox.information(
                            self,
                            "导出成功",
                            f"状态机信息已成功导出到：\n{file_name}",
                            QtWidgets.QMessageBox.Ok
                        )
                    else:
                        QtWidgets.QMessageBox.critical(
                            self,
                            "导出失败",
                            "导出Excel文档时发生错误",
                            QtWidgets.QMessageBox.Ok
                        )
            except Exception as e:
                QtWidgets.QMessageBox.critical(
                    self,
                    "导出失败",
                    f"导出文件时发生错误：\n{str(e)}",
                    QtWidgets.QMessageBox.Ok
                )
        except Exception as e:
            QtWidgets.QMessageBox.critical(
                self,
                "错误",
                f"导出状态机时发生未知错误：\n{str(e)}",
                QtWidgets.QMessageBox.Ok
            )

    def _validate_statechart(self):
        try:
            if self.fcstm_state_chart is None:
                QtWidgets.QMessageBox.warning(
                    self,
                    "警告",
                    "请先创建或导入状态机！",
                    QtWidgets.QMessageBox.Ok
                )
                return

            self.fcstm_state_chart.state_chart.validate()
            QtWidgets.QMessageBox.information(self, "验证成功", "状态图验证通过，无错误。")
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "错误", f"具有以下错误：\n{str(e)}")

    def _graph_gen(self):
        try:
            if self.fcstm_state_chart is None:
                QtWidgets.QMessageBox.warning(
                    self,
                    "警告",
                    "请先创建或导入状态机！",
                    QtWidgets.QMessageBox.Ok
                )
                return

            dialog_show_graph = DialogShowGraph(self, self.fcstm_state_chart)
            dialog_show_graph.exec_()
        except Exception as e:
            QtWidgets.QMessageBox.critical(
                self,
                "错误",
                f"生成状态图时发生错误：\n{str(e)}",
                QtWidgets.QMessageBox.Ok
            )

    def _get_pro_state(self) -> Optional[State]:
        # 获得当前Tree中选择的item
        selected_state_item = self.tree_state_machine_all_state.currentItem()
        # 若没有选中状态，则报错
        if not selected_state_item:
            QtWidgets.QMessageBox.warning(self, "提示", "请先选择要编辑的状态")
            return None
        pro_state = selected_state_item.data(0, Qt.UserRole)
        return pro_state
    '''
        def get_state_dict(self, cur_state: NormalState):
        transition_list = []
        if cur_state.id in self.fcstm_state_chart.d_all_transition:
            for cur_transition in self.fcstm_state_chart.d_all_transition[cur_state.id]:
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
    '''
