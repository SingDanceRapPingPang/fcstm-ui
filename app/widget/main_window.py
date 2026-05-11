from typing import Optional, Dict, List
import os
from pathlib import Path

import PyQt5.Qt
from PyQt5 import QtWidgets, QtGui, QtCore
from PyQt5.Qt import QMainWindow
from PyQt5.QtCore import Qt, QPoint
import qtawesome as qta
from pyfcstm.model import parse_dsl_node_to_state_machine
from pyfcstm.dsl import parse_with_grammar_entry
#from pyfcstm.entry

from app.ui import UIMainWindow
from ..model import State, StateManager
from app.utils.dsl_to_ui import dsl_to_state_manager, update_ui_from_state_manager
from .dialog_edit_state import DialogEditState
from .dialog_show_graph import DialogShowGraph
from app.utils.ui_to_dsl import state_manager_to_dsl
from .dialog_show_error import DialogShowError
from .dialog_reachability_val import DialogReachabilityVal
from .dialog_add_lifecycle import DialogAddLifecycle
from .dialog_add_transition import DialogAddTransition
from .dialog_simulate import DialogSimulate
from .dialog_exclusive_val import DialogExclusiveVal
from .dialog_sysdesim_validate import DialogSysdesimValidate
from .dialog_topology_verify import DialogTopologyVerify
from app.utils.xml_converter import (
    convert_xml_to_fcstm,
    format_sysdesim_conversion_report_table,
    get_fcstm_files_in_directory,
    write_sysdesim_conversion_report,
)
from app.utils.text_overflow import apply_text_overflow_handling, refresh_text_overflow
import re

class AppMainWindow(QMainWindow, UIMainWindow):
    state_manager: Optional[StateManager]

    def __init__(self):
        QMainWindow.__init__(self)
        self.setupUi(self)
        if hasattr(self, "label_current_state_machine"):
            self.label_current_state_machine.setProperty("fcstm_elide_text", True)
            self.label_current_state_machine.setWordWrap(False)
        apply_text_overflow_handling(self)
        self.at_page_initial = True
        #self.fcstm_state_chart = None
        self.code_file_path = "./"
        self.state_machine_file_path = "./"
        self.state_manager = None
        self.state_managers: List[StateManager] = []
        self._syncing_state_machine_tree = False

        # 初始化工具提示相关的实例变量
        self._current_tooltip_item = None
        self._current_tooltip_table = None

        self._init()

    def _init(self):
        #初始化窗口格式
        self._init_window_style()
        #初始化菜单栏
        self._init_menu_bar()
        #初始化导入状态机按钮
        self._init_import_state_chart()
        self._init_state_machine_files_panel()
        self._init_tree_all_state_context_menu()
        #初始化文本框变化操作
        self._init_edit_text_change()
        #初始化添加状态按钮
        self._init_button_state_machine_add_state()
        #初始化新建状态机按钮
        self._init_button_initial_new_state_machine()
        #展开所有状态按钮
        self._init_button_state_machine_expand_all()
        #折叠所有状态按钮
        self._init_button_state_machine_fold_all()
        #初始化生命周期按钮
        self._init_button_lifecycle()
        #初始化转移按钮
        self._init_button_transition()
        '''
        self._init_button_save_state()
        '''

    def _init_window_style(self):
        self.stackedWidget_state_machine.setCurrentIndex(0)
        self._init_tree_style()
        self._init_button_style()
        self._init_text_edit_style()
        self._init_table_style()

    def _init_menu_bar(self):
        """初始化菜单栏"""
        # 文件菜单
        self.menu_file.addAction(self.action_import_state_machine)

        # 工具菜单
        self.menu_tool.addAction(self.action_simulate)
        self.menu_tool.addAction(self.action_exclusive_val)
        self.menu_tool.addAction(self.action_graph_gen)
        self.menu_tool.addAction(self.action_reachability_val)
        self.action_topology_verify = QtWidgets.QAction("拓扑验证（可达/有穷/必达）", self)
        self.menu_tool.addAction(self.action_topology_verify)
        self.action_sysdesim_validate = QtWidgets.QAction("SysDeSim时间线验证", self)
        self.menu_tool.addAction(self.action_sysdesim_validate)

        # 连接菜单项信号
        self.action_import_state_machine.triggered.connect(self._import_statechart)

        self.action_graph_gen.triggered.connect(self._graph_gen)

        self.action_reachability_val.triggered.connect(self._reachability_validation)
        self.action_topology_verify.triggered.connect(self._topology_validation)

        self.action_simulate.triggered.connect(self._model_simulate)

        self.action_exclusive_val.triggered.connect(self._exclusive_validation)
        self.action_sysdesim_validate.triggered.connect(self._sysdesim_validation)

    def _init_import_state_chart(self):
        self._init_button_initial_import_state_machine()

    def _init_button_initial_import_state_machine(self):
        self.button_initial_import_state_machine.clicked.connect(lambda: self._import_statechart())

    def _init_button_initial_new_state_machine(self):
        self.button_initial_new_state_machine.clicked.connect(lambda: self._new_state_machine())

    def _new_state_machine(self):
        self.state_manager = StateManager()
        self._add_state_manager(self.state_manager, display_name="新建状态机", source_path="")
        if self.at_page_initial:
            self.stackedWidget_state_machine.setCurrentIndex(1)
            self.at_page_initial = False

    def _init_state_machine_files_panel(self):
        if hasattr(self, "tree_state_machine_files"):
            self.tree_state_machine_files.itemSelectionChanged.connect(
                self._on_state_machine_file_selection_changed
            )
            self.tree_state_machine_files.header().setStretchLastSection(True)
            self.tree_state_machine_files.setColumnHidden(1, True)
            self.tree_state_machine_files.setTextElideMode(Qt.ElideMiddle)
            self.tree_state_machine_files.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        if hasattr(self, "button_import_state_machine_files"):
            self.button_import_state_machine_files.clicked.connect(self._import_statechart)
        if hasattr(self, "button_remove_state_machine_file"):
            self.button_remove_state_machine_file.clicked.connect(self._remove_selected_state_machine)
        if hasattr(self, "button_clear_state_machine_files"):
            self.button_clear_state_machine_files.clicked.connect(self._clear_state_machines)

    def _state_manager_display_name(self, state_manager: StateManager, index: int) -> str:
        display_name = getattr(state_manager, "display_name", None)
        if display_name:
            return Path(display_name).stem
        source_file = getattr(state_manager, "source_file_path", None)
        if source_file:
            return Path(source_file).stem
        root_state = state_manager.get_root_state()
        if root_state:
            return root_state.name
        return f"状态机 {index + 1}"

    def _state_manager_source_text(self, state_manager: StateManager) -> str:
        return (
            getattr(state_manager, "origin_file_path", None)
            or getattr(state_manager, "source_file_path", None)
            or "内存模型"
        )

    def _add_state_manager(
        self,
        state_manager: StateManager,
        display_name: Optional[str] = None,
        source_path: Optional[str] = None,
        set_current: bool = True,
    ):
        if source_path is not None:
            state_manager.source_file_path = source_path
        if display_name is not None:
            state_manager.display_name = display_name
        elif not getattr(state_manager, "display_name", None):
            state_manager.display_name = self._state_manager_display_name(state_manager, len(self.state_managers))

        self.state_managers.append(state_manager)
        self._refresh_state_machine_files_panel()
        if set_current:
            self._set_current_state_manager(state_manager)

    def _refresh_state_machine_files_panel(self):
        if not hasattr(self, "tree_state_machine_files"):
            return

        self._syncing_state_machine_tree = True
        self.tree_state_machine_files.clear()
        group_items = {}
        for index, manager in enumerate(self.state_managers):
            source_text = self._state_manager_source_text(manager)
            group_key = source_text
            group_item = group_items.get(group_key)
            if group_item is None:
                group_label = Path(source_text).stem if source_text != "内存模型" else source_text
                group_item = QtWidgets.QTreeWidgetItem([group_label, source_text])
                group_item.setToolTip(0, source_text)
                group_items[group_key] = group_item
                self.tree_state_machine_files.addTopLevelItem(group_item)

            model_text = self._state_manager_display_name(manager, index)
            item = QtWidgets.QTreeWidgetItem([model_text, getattr(manager, "source_file_path", "") or ""])
            item.setToolTip(0, model_text)
            item.setToolTip(1, getattr(manager, "source_file_path", "") or "")
            item.setData(0, Qt.UserRole, manager)
            group_item.addChild(item)
            if manager is self.state_manager:
                self.tree_state_machine_files.setCurrentItem(item)
        self.tree_state_machine_files.expandAll()
        self._syncing_state_machine_tree = False

        if hasattr(self, "label_current_state_machine"):
            if self.state_manager is None:
                self.label_current_state_machine.setText("当前：未选择")
            else:
                try:
                    index = self.state_managers.index(self.state_manager)
                except ValueError:
                    index = 0
                self.label_current_state_machine.setText(
                    f"当前：{self._state_manager_display_name(self.state_manager, index)}"
                )
        refresh_text_overflow(self)

    def _set_current_state_manager(self, state_manager: Optional[StateManager]):
        self.state_manager = state_manager
        if state_manager is None:
            self.edit_var_def.clear()
            self.tree_all_state.clear()
            self._clear_tables()
            self._refresh_state_machine_files_panel()
            return

        update_ui_from_state_manager(self, state_manager)
        self._refresh_state_machine_files_panel()

    def _on_state_machine_file_selection_changed(self):
        if self._syncing_state_machine_tree:
            return
        item = self.tree_state_machine_files.currentItem()
        if item is None:
            return
        state_manager = item.data(0, Qt.UserRole)
        if state_manager is None and item.childCount() > 0:
            self.tree_state_machine_files.setCurrentItem(item.child(0))
            return
        if state_manager is not None and state_manager is not self.state_manager:
            self._set_current_state_manager(state_manager)

    def _remove_selected_state_machine(self):
        if not hasattr(self, "tree_state_machine_files"):
            return
        item = self.tree_state_machine_files.currentItem()
        if item is None:
            return
        state_manager = item.data(0, Qt.UserRole)
        if state_manager in self.state_managers:
            self.state_managers.remove(state_manager)
        self._set_current_state_manager(self.state_managers[0] if self.state_managers else None)

    def _clear_state_machines(self):
        self.state_managers.clear()
        self._set_current_state_manager(None)

    def _init_tree_style(self):
        self.tree_all_state.header().hide()
        self.tree_all_state.setTextElideMode(Qt.ElideNone)
        self.tree_all_state.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        #self.tree_all_state.setHorizontalScrollMode(QtWidgets.QAbstractItemView.ScrollPerPixel)
        self.tree_all_state.header().setMinimumSectionSize(800)
        self.tree_all_state.setAutoScroll(False)

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

    def _init_text_edit_style(self):
        # 设置字体为微软雅黑，大小为11号
        font = QtGui.QFont("微软雅黑", 11)

        # 设置字体
        self.edit_var_def.setFont(font)

        # 设置tab为4个空格
        self.edit_var_def.setTabStopWidth(
            QtGui.QFontMetrics(font).width(' ') * 4
        )

    def _init_table_style(self):
        """
        初始化表格样式
        """
        # 设置列宽拉伸模式，让所有列填满表格宽度
        header = self.table_transition.horizontalHeader()
        header.setStretchLastSection(True)  # 最后一列拉伸填满剩余空间
        header.setSectionResizeMode(QtWidgets.QHeaderView.Stretch)  # 所有列均匀拉伸

        # 禁止编辑表格内容
        self.table_transition.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)

        # 设置选择模式为整行选择
        self.table_transition.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)

        # 设置表格样式
        self.table_transition.setAlternatingRowColors(True)  # 交替行颜色
        self.table_transition.setGridStyle(QtCore.Qt.SolidLine)  # 网格线样式

        # 设置文本换行和自动调整行高
        self.table_transition.setWordWrap(True)  # 启用文本换行
        self.table_transition.verticalHeader().setSectionResizeMode(QtWidgets.QHeaderView.ResizeToContents)  # 行高自适应内容

        # 优化工具提示显示速度
        self.table_transition.setMouseTracking(True)  # 启用鼠标追踪
        # 禁用默认的工具提示行为，完全由事件过滤器控制
        self.table_transition.setAttribute(QtCore.Qt.WA_AlwaysShowToolTips, False)

        # 安装自定义事件过滤器以实现快速工具提示
        self.table_transition.installEventFilter(self)
        self.table_transition.viewport().installEventFilter(self)

        # 配置生命周期信息表格
        # 设置列宽拉伸模式，让所有列填满表格宽度
        header = self.table_lifecycle.horizontalHeader()
        header.setStretchLastSection(True)  # 最后一列拉伸填满剩余空间
        header.setSectionResizeMode(QtWidgets.QHeaderView.Stretch)  # 所有列均匀拉伸

        # 禁止编辑表格内容
        self.table_lifecycle.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)

        # 设置选择模式为整行选择
        self.table_lifecycle.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)

        # 设置表格样式
        self.table_lifecycle.setAlternatingRowColors(True)  # 交替行颜色
        self.table_lifecycle.setGridStyle(QtCore.Qt.SolidLine)  # 网格线样式

        # 设置文本换行和自动调整行高
        self.table_lifecycle.setWordWrap(True)  # 启用文本换行
        self.table_lifecycle.verticalHeader().setSectionResizeMode(QtWidgets.QHeaderView.ResizeToContents)  # 行高自适应内容

        # 优化工具提示显示速度
        self.table_lifecycle.setMouseTracking(True)  # 启用鼠标追踪
        # 禁用默认的工具提示行为，完全由事件过滤器控制
        self.table_lifecycle.setAttribute(QtCore.Qt.WA_AlwaysShowToolTips, False)

        # 安装自定义事件过滤器以实现快速工具提示
        self.table_lifecycle.installEventFilter(self)
        self.table_lifecycle.viewport().installEventFilter(self)

        # 设置生命周期表格的右键菜单
        self._init_lifecycle_context_menu()

        # 设置转移表格的右键菜单
        self._init_transition_context_menu()

        # 设置全局工具提示延迟时间（毫秒）
        QtWidgets.QApplication.instance().setAttribute(QtCore.Qt.AA_DisableWindowContextHelpButton, True)
        # 减少工具提示显示延迟，默认是700ms，我们设置为200ms
        self._setup_tooltip_timing()

    def _setup_tooltip_timing(self):
        """
        设置工具提示的显示和隐藏时间
        """
        # 获取应用程序实例
        app = QtWidgets.QApplication.instance()
        if app:
            # 设置工具提示的显示延迟为200毫秒（默认700毫秒）
            app.setAttribute(QtCore.Qt.AA_DisableWindowContextHelpButton, True)

        # 为表格设置更快的工具提示响应
        style_sheet = """
        QTableWidget {
            alternate-background-color: #f0f0f0;
        }
        QTableWidget::item:hover {
            background-color: #e0e0e0;
        }
        QToolTip {
            background-color: #ffffcc;
            color: #000000;
            border: 1px solid #999999;
            border-radius: 3px;
            padding: 5px;
            font-size: 9pt;
        }
        """
        self.table_transition.setStyleSheet(style_sheet)
        self.table_lifecycle.setStyleSheet(style_sheet)

    def _init_lifecycle_context_menu(self):
        """初始化生命周期表格的右键菜单"""
        self.table_lifecycle.setContextMenuPolicy(Qt.NoContextMenu)

    def _init_transition_context_menu(self):
        """初始化转移表格的右键菜单"""
        self.table_transition.setContextMenuPolicy(Qt.NoContextMenu)

    def _init_edit_text_change(self):
        # 连接变量定义文本框的内容变化信号
        self.edit_var_def.textChanged.connect(self._on_var_def_text_changed)

    def _init_tree_all_state_context_menu(self):
        self.tree_all_state.setContextMenuPolicy(Qt.CustomContextMenu)

        self.tree_all_state.customContextMenuRequested.connect(lambda pos: self.show_tree_all_state_context_menu(pos))

        # 连接树形控件的选择变化信号
        self.tree_all_state.itemSelectionChanged.connect(self._on_tree_item_selection_changed)

    def show_tree_all_state_context_menu(self, position: QPoint):
        item = self.tree_all_state.itemAt(position)
        if item is None:
            return

        state = item.data(0, Qt.UserRole)
        if state is None:
            return

        return

    def edit_state(self, item, state):
        self._add_state(father_state=None, is_edit=True)

    def add_sub_state(self, parent_item, parent_state):
        self._add_state(father_state=parent_state, is_edit=False)

    def delete_state(self, item, state: State):
        if state.name == self.state_manager.root_state.name:
            QtWidgets.QMessageBox.warning(
                self,
                "警告",
                "状态机根节点不能删除！",
                QtWidgets.QMessageBox.Ok
            )
            return

        reply = QtWidgets.QMessageBox.question(self, "删除确认", f"确定要删除状态 '{state.name}' 和其所有子状态，以及有关的转移吗？",
                                     QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No)

        if reply == QtWidgets.QMessageBox.Yes:

            self.state_manager.remove_state(state)
            parent_item = item.parent()
            if parent_item:
                parent_item.removeChild(item)
            else:
                index = self.tree_all_state.indexOfTopLevelItem(item)
                self.tree_all_state.takeTopLevelItem(index)

    def _init_button_state_machine_add_state(self):
        self.button_add_state.clicked.connect(lambda: self._buton_add_state())

    def _init_button_state_machine_expand_all(self):
        self.button_expand_all_state.setToolTip("展开所有")
        expand_icon = qta.icon('fa5s.angle-down', color='#000000')
        self.button_expand_all_state.setIcon(expand_icon)
        self.button_expand_all_state.setIconSize(PyQt5.Qt.QSize(25, 25))
        self.button_expand_all_state.clicked.connect(lambda: self._expand_all_state(self.tree_all_state))

    def _init_button_state_machine_fold_all(self):
        self.button_fold_all_state.setToolTip("折叠所有")
        fold_icon = qta.icon('fa5s.angle-up', color='#000000')
        self.button_fold_all_state.setIcon(fold_icon)
        self.button_fold_all_state.setIconSize(PyQt5.Qt.QSize(25, 25))
        self.button_fold_all_state.clicked.connect(lambda: self._fold_all_state(self.tree_all_state))

    def _expand_all_state(self, tree_widget: QtWidgets.QTreeWidget):
        tree_widget.expandAll()

    def _fold_all_state(self, tree_widget: QtWidgets.QTreeWidget):
        tree_widget.collapseAll()

    def _init_button_lifecycle(self):
        """初始化生命周期按钮"""
        self.button_lifecycle.clicked.connect(self._on_button_lifecycle_clicked)

    def _init_button_transition(self):
        """初始化转移按钮"""
        self.button_transition.clicked.connect(self._on_button_transition_clicked)

    def _on_button_lifecycle_clicked(self):
        """处理生命周期按钮点击事件"""
        try:
            # 检查是否有状态管理器
            if self.state_manager is None:
                QtWidgets.QMessageBox.warning(
                    self,
                    "警告",
                    "请先创建或导入状态机！",
                    QtWidgets.QMessageBox.Ok
                )
                return

            # 获取当前选中的状态
            current_state = self._get_pro_state()
            if current_state is None:
                QtWidgets.QMessageBox.warning(
                    self,
                    "警告",
                    "请先选择一个状态！",
                    QtWidgets.QMessageBox.Ok
                )
                return

            # 显示生命周期添加对话框
            dialog = DialogAddLifecycle(self, self.state_manager, current_state)
            if dialog.exec_() == QtWidgets.QDialog.Accepted:
                # 对话框已经在内部处理了数据添加，这里只需要刷新表格
                self._update_lifecycle_table(current_state.lifecycle)

        except Exception as e:
            QtWidgets.QMessageBox.critical(
                self,
                "错误",
                f"添加生命周期操作时发生错误：\n{str(e)}",
                QtWidgets.QMessageBox.Ok
            )

    def _on_button_transition_clicked(self):
        """处理转移按钮点击事件"""
        try:
            # 检查是否有状态管理器
            if self.state_manager is None:
                QtWidgets.QMessageBox.warning(
                    self,
                    "警告",
                    "请先创建或导入状态机！",
                    QtWidgets.QMessageBox.Ok
                )
                return

            # 获取当前选中的状态
            current_state = self._get_pro_state()
            if current_state is None:
                QtWidgets.QMessageBox.warning(
                    self,
                    "警告",
                    "请先选择一个状态！",
                    QtWidgets.QMessageBox.Ok
                )
                return

            # 显示转移添加对话框
            dialog = DialogAddTransition(self, self.state_manager, current_state)
            if dialog.exec_() == QtWidgets.QDialog.Accepted:
                # 对话框已经在内部处理了数据添加，这里只需要刷新表格
                self._update_transition_table(current_state.transitions)

        except Exception as e:
            QtWidgets.QMessageBox.critical(
                self,
                "错误",
                f"添加转移操作时发生错误：\n{str(e)}",
                QtWidgets.QMessageBox.Ok
            )

    def _buton_add_state(self):
        father_state = self._get_pro_state()
        if father_state is None and self.state_manager.get_root_state() is not None:
            QtWidgets.QMessageBox.critical(
                self,
                "错误",
                "状态机中只能有一个根状态",
                QtWidgets.QMessageBox.Ok
            )
            return
        else:
            self._add_state(father_state, False)

    def _add_state(self, father_state: Optional[State], is_edit = False):
        """
        保存状态信息，并使用QTreeWidget展示状态
        """
        try:
            if is_edit:
                # 获取当前编辑状态
                pro_state = self._get_pro_state()
                if pro_state is None:
                    QtWidgets.QMessageBox.warning(self, "提示", "请先选择要编辑的状态")
                    return

                dialog = DialogEditState(self, state_manager=self.state_manager, is_edit=True, initial_data=pro_state)
                if dialog.exec_() == QtWidgets.QDialog.Accepted:
                    state_data = dialog.get_state_data()
                    new_state_name = state_data["name"]
                    # 改变原状态的名字
                    try:
                        self.state_manager.rename_state(pro_state, new_state_name)
                        pro_state.extra_name = state_data["extra_name"]
                        pro_state.is_pseudo = state_data["is_pseudo"]
                        cur_tree_item = self.tree_all_state.currentItem()
                        cur_tree_item.setText(0, pro_state.display_name())
                        cur_tree_item.setToolTip(0, pro_state.get_full_path())
                    except Exception as e:
                        QtWidgets.QMessageBox.critical(
                            self,
                            "错误",
                            f"编辑状态时发生错误：\n{str(e)}",
                            QtWidgets.QMessageBox.Ok
                        )
                        return
            else:
                # 添加新状态
                dialog = DialogEditState(self, state_manager=self.state_manager, is_edit=False, initial_data=None, parent_state=father_state)
                if dialog.exec_() == QtWidgets.QDialog.Accepted:
                    state_data = dialog.get_state_data()
                    new_state_name = state_data["name"]
                    try:
                        new_state = State(
                            new_state_name,
                            extra_name=state_data["extra_name"],
                            is_pseudo=state_data["is_pseudo"],
                        )
                        if father_state is None and self.state_manager.get_root_state() is None:
                            self.state_manager.root_state = new_state
                        self.state_manager.add_state(father_state, new_state)
                        cur_state_item = QtWidgets.QTreeWidgetItem([new_state.display_name()])
                        cur_state_item.setToolTip(0, new_state.get_full_path())
                        cur_state_item.setData(0, Qt.UserRole, new_state)
                        # 如果是添加子状态：
                        if father_state is not None:
                            father_item = self.tree_all_state.currentItem()
                            father_item.addChild(cur_state_item)
                        else:
                            self.tree_all_state.addTopLevelItem(cur_state_item)
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
        """导入 fcstm 或 XML 文件"""
        try:
            # 检查上次使用的路径是否存在
            if not os.path.exists(self.state_machine_file_path):
                self.state_machine_file_path = "./"

            file_paths, _ = QtWidgets.QFileDialog.getOpenFileNames(
                self,
                "选择状态机文件",
                self.state_machine_file_path,
                "State Machine Files (*.fcstm *.xml);;FCSTM Files (*.fcstm);;XML Files (*.xml);;All Files (*)"
            )
            if not file_paths:
                return

            # 更新上次使用的路径
            self.state_machine_file_path = os.path.dirname(file_paths[0])

            try:
                imported_count = 0
                for file_path in file_paths:
                    # 判断文件类型
                    file_extension = os.path.splitext(file_path)[1].lower()

                    if file_extension == '.xml':
                        # XML文件需要先转换为FCSTM格式
                        before_count = len(self.state_managers)
                        self._import_xml_file(file_path)
                        imported_count += len(self.state_managers) - before_count
                    elif file_extension == '.fcstm':
                        # 直接导入FCSTM文件
                        self._import_fcstm_file(file_path, show_message=False)
                        imported_count += 1
                    else:
                        QtWidgets.QMessageBox.warning(
                            self,
                            "不支持的文件格式",
                            f"不支持的文件格式: {file_extension}\n仅支持 .fcstm 和 .xml 文件",
                            QtWidgets.QMessageBox.Ok
                        )

                if imported_count:
                    QtWidgets.QMessageBox.information(
                        self,
                        "导入成功",
                        f"成功导入 {imported_count} 个状态机模型。",
                        QtWidgets.QMessageBox.Ok
                    )

            except Exception as e:
                QtWidgets.QMessageBox.critical(
                    self,
                    "导入失败",
                    f"解析文件时发生错误：\n{str(e)}",
                    QtWidgets.QMessageBox.Ok
                )
                return

        except Exception as e:
            QtWidgets.QMessageBox.critical(
                self,
                "错误",
                f"导入状态机时发生未知错误：\n{str(e)}",
                QtWidgets.QMessageBox.Ok
            )

    def _import_fcstm_file(self, file_path: str, show_message: bool = True):
        """导入FCSTM文件"""
        # 使用DSL转换功能
        state_manager = dsl_to_state_manager(file_path)
        self._add_state_manager(
            state_manager,
            display_name=Path(file_path).stem,
            source_path=file_path,
            set_current=True,
        )

        if show_message:
            QtWidgets.QMessageBox.information(
                self,
                "导入成功",
                f"成功导入状态机文件：\n{os.path.basename(file_path)}",
                QtWidgets.QMessageBox.Ok
            )

    def _get_sysdesim_convert_options(self, xml_file_path: str, output_directory: str) -> Optional[Dict[str, object]]:
        dialog = QtWidgets.QDialog(self)
        dialog.setWindowTitle("SysDeSim 转换选项")
        dialog.setWindowFlags(dialog.windowFlags() & ~Qt.WindowContextHelpButtonHint)
        dialog.setMinimumWidth(640)
        dialog.resize(680, dialog.height())
        layout = QtWidgets.QVBoxLayout(dialog)

        form = QtWidgets.QFormLayout()
        edit_machine_name = QtWidgets.QLineEdit()
        edit_machine_id = QtWidgets.QLineEdit()
        spin_tick_duration = QtWidgets.QDoubleSpinBox()
        spin_tick_duration.setDecimals(3)
        spin_tick_duration.setRange(0, 1_000_000)
        spin_tick_duration.setSpecialValueText("自动")
        spin_tick_duration.setValue(0)
        check_report = QtWidgets.QCheckBox("生成 SysDeSim 转换诊断报告")
        check_report.setChecked(False)
        form.addRow("状态机名：", edit_machine_name)
        form.addRow("状态机ID：", edit_machine_id)
        form.addRow("tick(ms)：", spin_tick_duration)
        form.addRow("", check_report)
        layout.addLayout(form)

        note = QtWidgets.QLabel(
            "状态机名/ID 留空时使用 pyfcstm 默认选择。\n"
            "tick 为自动时不传 --tick-duration-ms。"
        )
        note.setWordWrap(False)
        layout.addWidget(note)

        button_box = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel)
        layout.addWidget(button_box)
        button_box.accepted.connect(dialog.accept)
        button_box.rejected.connect(dialog.reject)
        apply_text_overflow_handling(dialog)

        if dialog.exec_() != QtWidgets.QDialog.Accepted:
            return None

        return {
            "machine_name": edit_machine_name.text().strip() or None,
            "machine_id": edit_machine_id.text().strip() or None,
            "tick_duration_ms": spin_tick_duration.value() or None,
            "generate_report": check_report.isChecked(),
        }

    def _show_sysdesim_conversion_report(
        self,
        xml_file_path: str,
        output_directory: str,
        report_data: Optional[Dict[str, object]],
    ) -> Optional[str]:
        if not report_data:
            return None

        dialog = QtWidgets.QDialog(self)
        dialog.setWindowTitle("SysDeSim 转换诊断报告")
        dialog.setWindowFlags(dialog.windowFlags() & ~Qt.WindowContextHelpButtonHint)
        dialog.resize(900, 520)

        layout = QtWidgets.QVBoxLayout(dialog)
        text_report = QtWidgets.QPlainTextEdit()
        text_report.setReadOnly(True)
        text_report.setFont(QtGui.QFontDatabase.systemFont(QtGui.QFontDatabase.FixedFont))
        text_report.setPlainText(format_sysdesim_conversion_report_table(report_data))
        layout.addWidget(text_report, 1)

        saved_report_file = {"path": None}
        button_layout = QtWidgets.QHBoxLayout()
        button_save = QtWidgets.QPushButton("保存详细 JSON...")
        button_close = QtWidgets.QPushButton("关闭")
        button_layout.addStretch(1)
        button_layout.addWidget(button_save)
        button_layout.addWidget(button_close)
        layout.addLayout(button_layout)

        def _save_report():
            default_path = str(Path(output_directory) / f"{Path(xml_file_path).stem}_conversion_report.json")
            report_file, _ = QtWidgets.QFileDialog.getSaveFileName(
                dialog,
                "保存 SysDeSim 详细 JSON 报告",
                default_path,
                "JSON Files (*.json);;All Files (*)",
            )
            if not report_file:
                return
            if not report_file.lower().endswith(".json"):
                report_file += ".json"
            try:
                write_sysdesim_conversion_report(report_data, report_file)
                saved_report_file["path"] = report_file
                QtWidgets.QMessageBox.information(dialog, "保存成功", f"详细 JSON 报告已保存：\n{report_file}")
            except Exception as e:
                QtWidgets.QMessageBox.critical(
                    dialog,
                    "保存失败",
                    f"保存 SysDeSim 转换报告时发生错误：\n{str(e)}",
                    QtWidgets.QMessageBox.Ok,
                )

        button_save.clicked.connect(_save_report)
        button_close.clicked.connect(dialog.accept)
        apply_text_overflow_handling(dialog)
        dialog.exec_()
        return saved_report_file["path"]

    def _import_xml_file(self, xml_file_path: str):
        """导入XML文件并转换为FCSTM格式"""
        # 选择输出目录
        output_directory = QtWidgets.QFileDialog.getExistingDirectory(
            self,
            "选择FCSTM文件输出目录",
            self.state_machine_file_path,
            QtWidgets.QFileDialog.ShowDirsOnly
        )

        if not output_directory:
            return

        options = self._get_sysdesim_convert_options(xml_file_path, output_directory)
        if options is None:
            return

        try:
            # 转换XML到FCSTM
            generated_files, error_msg, report_data = convert_xml_to_fcstm(
                xml_file_path,
                output_directory,
                tick_duration_ms=options.get("tick_duration_ms"),
                machine_name=options.get("machine_name"),
                machine_id=options.get("machine_id"),
                generate_report=bool(options.get("generate_report")),
            )

            if error_msg:
                QtWidgets.QMessageBox.warning(
                    self,
                    "转换警告",
                    f"转换过程中出现警告：\n{error_msg}",
                    QtWidgets.QMessageBox.Ok
                )

            if not generated_files:
                QtWidgets.QMessageBox.critical(
                    self,
                    "转换失败",
                    "未能生成任何FCSTM文件",
                    QtWidgets.QMessageBox.Ok
                )
                return

            # 显示转换结果
            file_list = "\n".join([os.path.basename(f) for f in generated_files])
            first_manager = None
            for index, fcstm_file in enumerate(generated_files):
                manager = dsl_to_state_manager(fcstm_file)
                manager.origin_file_path = xml_file_path
                if first_manager is None:
                    first_manager = manager
                self._add_state_manager(
                    manager,
                    display_name=Path(fcstm_file).stem,
                    source_path=fcstm_file,
                    set_current=index == 0,
                )

            saved_report_file = self._show_sysdesim_conversion_report(
                xml_file_path,
                output_directory,
                report_data,
            )

            QtWidgets.QMessageBox.information(
                self,
                "转换成功",
                (
                    f"成功将XML文件转换为 {len(generated_files)} 个FCSTM文件并全部加载：\n{file_list}"
                    + (
                        f"\n\n转换报告：{saved_report_file}"
                        if saved_report_file else ""
                    )
                ),
                QtWidgets.QMessageBox.Ok
            )

        except Exception as e:
            QtWidgets.QMessageBox.critical(
                self,
                "转换失败",
                f"XML转换失败：\n{str(e)}",
                QtWidgets.QMessageBox.Ok
            )
            raise

    def _graph_gen(self):
        try:
            if not self.state_managers:
                QtWidgets.QMessageBox.warning(
                    self,
                    "警告",
                    "请先创建或导入状态机！",
                    QtWidgets.QMessageBox.Ok
                )
                return
            dialog_show_graph = DialogShowGraph(self, self.state_managers, self.state_manager)
            dialog_show_graph.exec_()

        except Exception as e:
            QtWidgets.QMessageBox.critical(
                self,
                "错误",
                f"生成状态图时发生错误：\n{str(e)}",
                QtWidgets.QMessageBox.Ok
            )

    def _reachability_validation(self):
        """状态可达性验证功能"""
        try:
            if not self.state_managers:
                QtWidgets.QMessageBox.warning(
                    self,
                    "警告",
                    "请先创建或导入状态机！",
                    QtWidgets.QMessageBox.Ok
                )
                return

            # 显示可达性验证对话框
            dialog = DialogReachabilityVal(self, self.state_managers, self.state_manager)
            dialog.exec_()

        except Exception as e:
            QtWidgets.QMessageBox.critical(
                self,
                "错误",
                f"可达性验证时发生错误：\n{str(e)}",
                QtWidgets.QMessageBox.Ok
            )

    def _topology_validation(self):
        """纯拓扑可达性、有穷性和必达性验证。"""
        try:
            if not self.state_managers:
                QtWidgets.QMessageBox.warning(
                    self,
                    "警告",
                    "请先创建或导入状态机！",
                    QtWidgets.QMessageBox.Ok
                )
                return

            dialog = DialogTopologyVerify(
                self,
                self.state_managers,
                self.state_manager,
                self._get_pro_state(),
            )
            dialog.exec_()

        except Exception as e:
            QtWidgets.QMessageBox.critical(
                self,
                "错误",
                f"拓扑验证时发生错误：\n{str(e)}",
                QtWidgets.QMessageBox.Ok
            )

    def _model_simulate(self):
        """模型仿真功能"""
        try:
            if not self.state_managers:
                QtWidgets.QMessageBox.warning(
                    self,
                    "警告",
                    "请先创建或导入状态机！",
                    QtWidgets.QMessageBox.Ok
                )
                return

            # 显示模型仿真对话框
            dialog = DialogSimulate(self, self.state_managers, self.state_manager)
            dialog.exec_()

        except Exception as e:
            QtWidgets.QMessageBox.critical(
                self,
                "错误",
                f"模型仿真时发生错误：\n{str(e)}",
                QtWidgets.QMessageBox.Ok
            )

    def _exclusive_validation(self):
        """互斥性验证功能"""
        try:
            if not self.state_managers:
                QtWidgets.QMessageBox.warning(
                    self,
                    "警告",
                    "请先创建或导入状态机！",
                    QtWidgets.QMessageBox.Ok
                )
                return

            # 显示互斥性验证对话框
            dialog = DialogExclusiveVal(self, self.state_managers, self.state_manager)
            dialog.exec_()

        except Exception as e:
            QtWidgets.QMessageBox.critical(
                self,
                "错误",
                f"互斥性验证时发生错误：\n{str(e)}",
                QtWidgets.QMessageBox.Ok
            )

    def _sysdesim_validation(self):
        """SysDeSim XML导入链路验证与状态共存查询"""
        try:
            imported_xml_managers = [
                manager
                for manager in self.state_managers
                if str(getattr(manager, "origin_file_path", "")).lower().endswith((".xml", ".xmi"))
            ]
            if not imported_xml_managers:
                QtWidgets.QMessageBox.warning(
                    self,
                    "缺少 SysDeSim 模型",
                    "请先在主页面导入 SysDeSim XML/XMI 模型。",
                    QtWidgets.QMessageBox.Ok,
                )
                return

            dialog = DialogSysdesimValidate(self, imported_xml_managers)
            dialog.exec_()

        except Exception as e:
            QtWidgets.QMessageBox.critical(
                self,
                "错误",
                f"SysDeSim 验证时发生错误：\n{str(e)}",
                QtWidgets.QMessageBox.Ok
            )

    def _on_tree_item_selection_changed(self):
        """
        当树形控件中的选择发生变化时，更新转移信息和生命周期信息表格
        """
        try:
            if self.state_manager is None:
                return

            current_state = self._get_pro_state()

            if current_state is None:
                # 如果没有选中项，清空表格
                self._clear_tables()
                return

            # 更新转移信息表格
            self._update_transition_table(current_state.transitions)
            # 更新生命周期信息表格
            self._update_lifecycle_table(current_state.lifecycle)

        except Exception as e:
            QtWidgets.QMessageBox.critical(
                self,
                "错误",
                f"更新状态信息时发生错误：\n{str(e)}",
                QtWidgets.QMessageBox.Ok
            )

    def _clear_tables(self):
        """
        清空转移信息和生命周期信息表格
        """
        # 清空转移表格
        if hasattr(self, 'table_transition'):
            self.table_transition.setRowCount(0)

        # 清空生命周期表格
        if hasattr(self, 'table_lifecycle'):
            self.table_lifecycle.setRowCount(0)

    def _update_transition_table(self, transitions):
        """
        更新转移信息表格
        transitions: List[Dict[str, str]] - 转移信息列表
        """
        if not hasattr(self, 'table_transition'):
            return

        # 设置表格列数和标题
        self.table_transition.setColumnCount(4)
        self.table_transition.setHorizontalHeaderLabels(["源状态", "目标状态", "事件", "条件"])

        # 设置行数
        self.table_transition.setRowCount(len(transitions))

        # 填充数据
        for row, transition in enumerate(transitions):
            # 源状态
            source_state_name = transition.get("source", "")
            source_item = QtWidgets.QTableWidgetItem(source_state_name)
            source_item.setTextAlignment(QtCore.Qt.AlignCenter)
            source_item.setToolTip(source_state_name)  # 添加工具提示
            self.table_transition.setItem(row, 0, source_item)

            # 目标状态
            target_state_name = transition.get("target", "")
            target_item = QtWidgets.QTableWidgetItem(target_state_name)
            target_item.setTextAlignment(QtCore.Qt.AlignCenter)
            target_item.setToolTip(target_state_name)  # 添加工具提示
            self.table_transition.setItem(row, 1, target_item)

            # 事件
            event_text = transition.get("event", "")
            event_item = QtWidgets.QTableWidgetItem(event_text)
            event_item.setTextAlignment(QtCore.Qt.AlignCenter)
            event_item.setToolTip(event_text)  # 添加工具提示
            self.table_transition.setItem(row, 2, event_item)

            # 条件
            condition_text = transition.get("condition", "")
            condition_item = QtWidgets.QTableWidgetItem(condition_text)
            condition_item.setTextAlignment(QtCore.Qt.AlignCenter)

            # 为条件项添加详细的工具提示，包括操作信息
            action_text = transition.get("action", "")
            if action_text:
                tooltip_text = f"条件: {condition_text}\n\n操作:\n{action_text}"
            else:
                tooltip_text = condition_text
            condition_item.setToolTip(tooltip_text)

            self.table_transition.setItem(row, 3, condition_item)

        # 列宽已通过拉伸模式自动调整，无需手动调整

    def _update_lifecycle_table(self, lifecycle):
        """
        更新生命周期信息表格
        lifecycle: List[Dict[str, str]] - 生命周期信息列表
        """
        if not hasattr(self, 'table_lifecycle'):
            return

        # 设置表格列数和标题
        self.table_lifecycle.setColumnCount(3)
        self.table_lifecycle.setHorizontalHeaderLabels(["类型", "名称", "是否抽象"])

        # 设置行数
        self.table_lifecycle.setRowCount(len(lifecycle))

        # 填充数据
        for row, lifecycle_item in enumerate(lifecycle):
            # 类型
            type_text = lifecycle_item.get("type", "")
            type_item = QtWidgets.QTableWidgetItem(type_text)
            type_item.setTextAlignment(QtCore.Qt.AlignCenter)
            type_item.setToolTip(type_text)  # 添加工具提示
            self.table_lifecycle.setItem(row, 0, type_item)

            # 名称 - 如果没有名称，显示"无"
            name_value = lifecycle_item.get("name", "")
            if not name_value or name_value.strip() == "":
                name_value = "无"
            name_item = QtWidgets.QTableWidgetItem(name_value)
            name_item.setTextAlignment(QtCore.Qt.AlignCenter)
            name_item.setToolTip(name_value)  # 添加工具提示
            self.table_lifecycle.setItem(row, 1, name_item)

            # 是否抽象 - 将布尔值转换为中文显示
            is_abstract_value = lifecycle_item.get("is_abstract", False)
            is_abstract_text = "是" if is_abstract_value else "否"
            is_abstract_item = QtWidgets.QTableWidgetItem(is_abstract_text)
            is_abstract_item.setTextAlignment(QtCore.Qt.AlignCenter)
            is_abstract_item.setToolTip(is_abstract_text)  # 添加工具提示

            # 构建详细的工具提示信息
            tooltip_parts = [is_abstract_text]

            # 添加操作信息（如果存在）
            action = lifecycle_item.get("action", "")
            if action and action.strip():
                tooltip_parts.append(f"操作:\n{action}")

            # 添加注释信息（如果存在）
            comment = lifecycle_item.get("comment", "")
            if comment and comment.strip():
                tooltip_parts.append(f"注释:\n{comment}")

            # 设置工具提示
            if len(tooltip_parts) > 1:
                tooltip_text = "\n\n".join(tooltip_parts)
                is_abstract_item.setToolTip(tooltip_text)

            self.table_lifecycle.setItem(row, 2, is_abstract_item)

        # 列宽已通过拉伸模式自动调整，无需手动调整

    def _get_state_by_name(self, state_name):
        """
        根据状态名称获取状态对象
        """
        if not self.state_manager or not state_name:
            return None
        return self.state_manager.get_state(state_name)

    def _on_var_def_text_changed(self):
        """
        当变量定义文本框内容变化时，保存到StateManager
        """
        try:
            if self.state_manager is None:
                return

            # 获取文本框内容并保存到StateManager
            var_def_text = self.edit_var_def.toPlainText()
            self.state_manager.variable_definitions = var_def_text

        except Exception as e:
            QtWidgets.QMessageBox.critical(
                self,
                "错误",
                f"保存变量定义时发生错误：\n{str(e)}",
                QtWidgets.QMessageBox.Ok
            )

    def _get_pro_state(self) -> Optional[State]:
        # 获得当前Tree中选择的item
        selected_state_item = self.tree_all_state.currentItem()
        # 若没有选中状态，则返回None
        if not selected_state_item:
            return None
        pro_state = selected_state_item.data(0, Qt.UserRole)
        return pro_state

    def _show_lifecycle_context_menu(self, position: QPoint):
        """显示生命周期表格的右键菜单"""
        try:
            # 检查是否有选中的状态
            current_state = self._get_pro_state()
            if current_state is None:
                return

            # 检查点击位置是否有有效的行
            item = self.table_lifecycle.itemAt(position)
            if item is None:
                return

            row = item.row()
            if row < 0 or row >= len(current_state.lifecycle):
                return

            # 创建右键菜单
            menu = QtWidgets.QMenu(self)
            edit_action = QtWidgets.QAction("修改生命周期", self)
            delete_action = QtWidgets.QAction("删除生命周期", self)

            # 连接菜单项信号
            edit_action.triggered.connect(lambda: self._edit_lifecycle(current_state, row))
            delete_action.triggered.connect(lambda: self._delete_lifecycle(current_state, row))

            menu.addAction(edit_action)
            menu.addAction(delete_action)

            # 显示菜单
            menu.exec_(self.table_lifecycle.viewport().mapToGlobal(position))

        except Exception as e:
            QtWidgets.QMessageBox.critical(
                self,
                "错误",
                f"显示生命周期菜单时发生错误：\n{str(e)}",
                QtWidgets.QMessageBox.Ok
            )

    def _edit_lifecycle(self, current_state: State, row: int):
        """编辑生命周期操作"""
        try:
            if row < 0 or row >= len(current_state.lifecycle):
                QtWidgets.QMessageBox.warning(self, "错误", "无效的生命周期操作！")
                return

            # 获取要编辑的生命周期数据
            lifecycle_data = current_state.lifecycle[row]

            # 显示编辑对话框
            dialog = DialogAddLifecycle(
                parent=self,
                state_manager=self.state_manager,
                current_state=current_state,
                is_edit=True,
                lifecycle_data=lifecycle_data,
                lifecycle_index=row
            )

            if dialog.exec_() == QtWidgets.QDialog.Accepted:
                # 刷新生命周期表格显示
                self._update_lifecycle_table(current_state.lifecycle)

        except Exception as e:
            QtWidgets.QMessageBox.critical(
                self,
                "错误",
                f"编辑生命周期操作时发生错误：\n{str(e)}",
                QtWidgets.QMessageBox.Ok
            )

    def _delete_lifecycle(self, current_state: State, row: int):
        """删除生命周期操作"""
        try:
            if row < 0 or row >= len(current_state.lifecycle):
                QtWidgets.QMessageBox.warning(self, "错误", "无效的生命周期操作！")
                return

            # 获取要删除的生命周期数据
            lifecycle_data = current_state.lifecycle[row]
            lifecycle_type = lifecycle_data.get("type", "")
            lifecycle_name = lifecycle_data.get("name", "")

            # 构建显示名称
            display_name = f"{lifecycle_type}"
            if lifecycle_name:
                display_name += f" ({lifecycle_name})"

            # 确认删除
            reply = QtWidgets.QMessageBox.question(
                self,
                "删除确认",
                f"确定要删除生命周期操作 '{display_name}' 吗？",
                QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No
            )

            if reply == QtWidgets.QMessageBox.Yes:
                # 删除生命周期操作
                del current_state.lifecycle[row]

                # 刷新生命周期表格显示
                self._update_lifecycle_table(current_state.lifecycle)

                QtWidgets.QMessageBox.information(self, "成功", "生命周期操作删除成功！")

        except Exception as e:
            QtWidgets.QMessageBox.critical(
                self,
                "错误",
                f"删除生命周期操作时发生错误：\n{str(e)}",
                QtWidgets.QMessageBox.Ok
            )

    def _show_transition_context_menu(self, position: QPoint):
        """显示转移表格的右键菜单"""
        try:
            # 检查是否有选中的状态
            current_state = self._get_pro_state()
            if current_state is None:
                return

            # 检查点击位置是否有有效的行
            item = self.table_transition.itemAt(position)
            if item is None:
                return

            row = item.row()
            if row < 0 or row >= len(current_state.transitions):
                return

            # 创建右键菜单
            menu = QtWidgets.QMenu(self)
            edit_action = QtWidgets.QAction("修改转移", self)
            delete_action = QtWidgets.QAction("删除转移", self)

            # 连接菜单项信号
            edit_action.triggered.connect(lambda: self._edit_transition(current_state, row))
            delete_action.triggered.connect(lambda: self._delete_transition(current_state, row))

            menu.addAction(edit_action)
            menu.addAction(delete_action)

            # 显示菜单
            menu.exec_(self.table_transition.viewport().mapToGlobal(position))

        except Exception as e:
            QtWidgets.QMessageBox.critical(
                self,
                "错误",
                f"显示转移菜单时发生错误：\n{str(e)}",
                QtWidgets.QMessageBox.Ok
            )

    def _edit_transition(self, current_state: State, row: int):
        """编辑转移"""
        try:
            if row < 0 or row >= len(current_state.transitions):
                QtWidgets.QMessageBox.warning(self, "错误", "无效的转移！")
                return

            # 获取要编辑的转移数据
            transition_data = current_state.transitions[row]

            # 显示编辑对话框
            dialog = DialogAddTransition(
                parent=self,
                state_manager=self.state_manager,
                current_state=current_state,
                is_edit=True,
                transition_data=transition_data,
                transition_index=row
            )

            if dialog.exec_() == QtWidgets.QDialog.Accepted:
                # 刷新转移表格显示
                self._update_transition_table(current_state.transitions)

        except Exception as e:
            QtWidgets.QMessageBox.critical(
                self,
                "错误",
                f"编辑转移时发生错误：\n{str(e)}",
                QtWidgets.QMessageBox.Ok
            )

    def _delete_transition(self, current_state: State, row: int):
        """删除转移"""
        try:
            if row < 0 or row >= len(current_state.transitions):
                QtWidgets.QMessageBox.warning(self, "错误", "无效的转移！")
                return

            # 获取要删除的转移数据
            transition_data = current_state.transitions[row]
            source_state = transition_data.get("source", "")
            target_state = transition_data.get("target", "")
            event = transition_data.get("event", "")

            # 构建显示名称
            display_name = f"{source_state} → {target_state}"
            if event:
                display_name += f" ({event})"

            # 确认删除
            reply = QtWidgets.QMessageBox.question(
                self,
                "删除确认",
                f"确定要删除转移 '{display_name}' 吗？",
                QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No
            )

            if reply == QtWidgets.QMessageBox.Yes:
                # 删除转移
                del current_state.transitions[row]

                # 刷新转移表格显示
                self._update_transition_table(current_state.transitions)

                QtWidgets.QMessageBox.information(self, "成功", "转移删除成功！")

        except Exception as e:
            QtWidgets.QMessageBox.critical(
                self,
                "错误",
                f"删除转移时发生错误：\n{str(e)}",
                QtWidgets.QMessageBox.Ok
            )
