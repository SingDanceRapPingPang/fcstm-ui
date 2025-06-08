from pyfcstm.model import (
    State,
    CompositeState,
    Event,
    Transition,
    Statechart
)
from typing import Dict, List, Optional
from PyQt5 import QtWidgets
from PyQt5.QtCore import Qt
from vtkmodules.numpy_interface.dataset_adapter import NoneArray
import qtawesome as qta


class FcstmStateChart:
    """fcstm，事件和迁移都挂在状态下"""
    d_id_father_state: Dict[str, Optional[CompositeState]]

    def __init__(self, tree_widget: QtWidgets.QTreeWidget, state_chart: Statechart):
        self._state_chart = state_chart

        self.d_id_father_state = {}  # state.id: state(father)
        self.tree_widget = tree_widget
        self.tree_widget.clear()

        if self._state_chart is not None:
            self.__init_fcstm()

    def __init_fcstm(self):

        self.populate_tree_state_machine_all_state(self.tree_widget)

    def populate_tree_state_machine_all_state(self, tree_widget: QtWidgets.QTreeWidget):
        tree_widget.clear()

        def add_state_to_tree(parent_item, state):
            # 检查是否为父状态的初始状态
            if parent_item:
                parent_state = parent_item.data(0, Qt.UserRole)
                if isinstance(parent_state, CompositeState) and parent_state.initial_state_id == state.id:
                    # 创建带有图标的文本
                    icon = qta.icon('fa5s.play', color='#4169E1')  # 使用皇家蓝颜色
                    item = QtWidgets.QTreeWidgetItem([state.name])
                    item.setIcon(0, icon)
                else:
                    item = QtWidgets.QTreeWidgetItem([state.name])
            elif self.state_chart.root_state_id == state.id:
                # 创建带有图标的文本
                icon = qta.icon('fa5s.play', color='#4169E1')  # 使用皇家蓝颜色
                item = QtWidgets.QTreeWidgetItem([state.name])
                item.setIcon(0, icon)
            else:
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

        add_state_to_tree(None, self._state_chart.root_state)

    @property
    def state_chart(self) -> Statechart:
        return self._state_chart

    def add_event(self, parent_widget, new_event_name: str, new_event_guard: str):
        """新增事件"""
        is_validate = True
        for cur_event in self.state_chart.events:
            if new_event_name == cur_event.name:
                is_validate = False

        if not is_validate:
            self.warning_message(parent_widget, "事件名称已经存在！")
            return
        new_event = Event(new_event_name, new_event_guard)
        self.state_chart.events.add(new_event)

    def edit_event(self, parent_widget, new_event_name: str,
                   new_event_guard: str, old_event_name: str):
        """修改事件"""
        is_validate = True
        old_event = self.state_chart.events.get_by_name(old_event_name)
        if not old_event:
            self.warning_message(parent_widget, "待编辑的事件不存在！")
            return
        if self.state_chart.events.get_by_name(new_event_name) and old_event_name != new_event_name:
            is_validate = False
        #找到待修改的旧事件，并判断修改是否合法
        #不合法：修改的事件名称已经存在
        if not is_validate:
            self.warning_message(parent_widget, "事件名称已经存在！")
            return

        if old_event is not None:
            # 输入的事件名称不能已经存在
            old_event.name = new_event_name
            old_event.guard = new_event_guard

    def add_transition(self, parent_widget, new_transition_src_state: State, new_transition_target_state: State, new_transition_event: Event):
        for cur_transition in self.state_chart.transitions:
            if (cur_transition.src_state_id == new_transition_src_state.id and cur_transition.dst_state_id == new_transition_target_state.id
            and cur_transition.event_id == new_transition_event.id):
                self.warning_message(parent_widget, "迁移已经存在！")
                return

        new_transition = Transition(new_transition_src_state, new_transition_target_state, new_transition_event)
        self.state_chart.transitions.add(new_transition)

    def edit_transition(self, parent_widget, old_transition_src_state: State, old_transition_target_state: State, old_transition_event: Event,
                        new_transition_src_state: State, new_transition_target_state: State, new_transition_event: Event):
        old_transition = None
        #找到旧的迁移
        for cur_transition in self.state_chart.transitions:
            if (cur_transition.src_state_id == old_transition_src_state.id and cur_transition.dst_state_id == old_transition_target_state.id
            and cur_transition.event_id == old_transition_event.id):
                old_transition = cur_transition
        if old_transition is None:
            self.warning_message(parent_widget, "待编辑的迁移不存在！")
            return
        #判断新迁移是否已经存在
        for cur_transition in self.state_chart.transitions:
            if(cur_transition.src_state_id == new_transition_src_state.id and cur_transition.dst_state_id == new_transition_target_state.id
            and cur_transition.event_id == new_transition_event.id):
                self.warning_message(parent_widget, "编辑后的迁移已经存在！")
                return

        old_transition.src_state = new_transition_src_state
        old_transition.dst_state = new_transition_target_state
        old_transition.event = new_transition_event

    def del_event(self, parent_widget, event_name: str):
        """删除特定状态下指定名字的事件，以及与该事件相关的迁移"""
        del_event = self.state_chart.events.get_by_name(event_name)
        if not del_event:
            return
        # 创建一个列表来存储要删除的transition
        transitions_to_delete = []
        for cur_transition in self.state_chart.transitions:
            if cur_transition.event_id == del_event.id:
                transitions_to_delete.append(cur_transition)
        
        # 删除找到的transitions
        for transition in transitions_to_delete:
            del self.state_chart.transitions[transition]

        del self.state_chart.events[del_event]

    def del_transition(self, parent_widget, transition_src_name: str, transition_event_name: str, transition_target_name: str):
        """删除特定状态下指定名字迁移"""
        transition_src_state = self.state_chart.states.get_by_name(transition_src_name)
        transition_target_state = self.state_chart.states.get_by_name(transition_target_name)
        transition_event = self.state_chart.events.get_by_name(transition_event_name)
        #导入有问题时的删除
        del_transition = None
        for cur_transition in self.state_chart.transitions:
            if (cur_transition.src_state_id == transition_src_state.id and cur_transition.dst_state_id == transition_target_state.id
            and cur_transition.event_id == transition_event.id):
                del_transition = cur_transition
        if del_transition is None:
            return
        del self.state_chart.transitions[del_transition]

    def add_state(self, father_state: CompositeState, new_state: State):
        """添加状态"""
        cur_state_item = QtWidgets.QTreeWidgetItem([new_state.name])
        cur_state_item.setData(0, Qt.UserRole, new_state)
        self.state_chart.states.add(new_state)
        # 如果是添加子状态：
        if father_state is not None:
            father_item = self.tree_widget.currentItem()
            self.d_id_father_state[new_state.id] = father_state
            father_state.states.add(new_state)
            father_item.addChild(cur_state_item)
        else:
            self.d_id_father_state[new_state.id] = None
            self.tree_widget.addTopLevelItem(cur_state_item)

    def edit_state(self, pro_state: State, new_state: State):
        del self.state_chart.states[pro_state]
        self.state_chart.states.add(new_state)
        cur_tree_item = self.tree_widget.currentItem()
        cur_tree_item.setText(0, new_state.name)
        cur_tree_item.setData(0, Qt.UserRole, new_state)

    def del_state(self, tree_item, state: State):
        """删除状态，如果状态是composite类型的话，要递归删除所有子状态"""
        def recursive_delete_state(cur_state: State):
            if cur_state is None:
                return
            #删除与当前状态关联的所有迁移
            transitions_to_delete = []
            for cur_transition in self.state_chart.transitions:
                if cur_transition.src_state_id == cur_state.id or cur_transition.dst_state_id == cur_state.id:
                    transitions_to_delete.append(cur_transition)
            # 删除找到的transitions
            for transition in transitions_to_delete:
                del self.state_chart.transitions[transition]

            if cur_state.id in self.d_id_father_state:
                del self.d_id_father_state[cur_state.id]

            del self.state_chart.states[cur_state]
            #递归删除所有子状态的信息
            if isinstance(cur_state, CompositeState):
                for son_state in cur_state.states:
                    recursive_delete_state(son_state)

        parent_item = tree_item.parent()
        if parent_item:
            parent_state = parent_item.data(0, Qt.UserRole)
            del parent_state.states[state]
            parent_item.removeChild(tree_item)
        else:
            index = self.tree_widget.indexOfTopLevelItem(tree_item)
            self.tree_widget.takeTopLevelItem(index)
        #删除state的所有相关信息
        recursive_delete_state(state)

    def change_initial_state(self, father_state: CompositeState, new_initial_state: State):
        """
        修改复合状态的初始状态

        Args:
            father_state: 要修改的复合状态
            new_initial_state: 新的初始状态
        """
        cur_tree_item = self.tree_widget.currentItem()
        # 更新复合状态的初始状态ID
        if father_state.initial_state_id is not None:
            father_state_item = cur_tree_item.parent()
            for i in range(father_state_item.childCount()):
                child_item = father_state_item.child(i)
                child_state = child_item.data(0, Qt.UserRole)
                if child_state.id == father_state.initial_state_id:
                    child_item.setText(0, f"{child_state.name}")
        icon = qta.icon('fa5s.play', color='#4169E1')

        father_state.initial_state = new_initial_state
        cur_tree_item.setIcon(0, icon)

    def warning_message(self, parent_widget, message: str):
        QtWidgets.QMessageBox.warning(
            parent_widget,
            "警告",
            message,
            QtWidgets.QMessageBox.Ok
        )

    def legality_check(self, parent_widget):
        illegal_transitions = []
        warning_str = []
        for cur_transition in self.state_chart.transitions:
            cur_transition_src_state = cur_transition.src_state
            cur_transition_dst_state = cur_transition.dst_state
            cur_transition_event = cur_transition.event
            if (not cur_transition_src_state or not cur_transition_dst_state or
            not cur_transition_event):
                illegal_transitions.append(cur_transition)
                cur_str = (f'{cur_transition_src_state.name if cur_transition_src_state is not None else ""}'
                           f'-->{cur_transition_dst_state.name if cur_transition_dst_state is not None else ""}, '
                           f'事件:{cur_transition_event.name if cur_transition_event is not None else ""}')
                warning_str.append(cur_str)

        if illegal_transitions:
            self.warning_message(parent_widget, f"以下不合法的迁移将被删除: {"".join(warning_str)}")
