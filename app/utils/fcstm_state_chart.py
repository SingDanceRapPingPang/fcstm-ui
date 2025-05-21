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

class FcstmStateChart:
    """fcstm，事件和迁移都挂在状态下"""
    d_all_transition: Dict[str, List[Transition]]
    d_all_event: Dict[str, List[Event]]
    d_id_father_state: Dict[str, Optional[CompositeState]]

    def __init__(self, tree_widget: QtWidgets.QTreeWidget, state_chart: Statechart):
        self._state_chart = state_chart

        self.d_all_event = {}  # state.id: [event]
        self.d_all_transition = {}  # state.id: [transition]
        self.d_id_father_state = {}  # state.id: state(father)
        self.tree_widget = tree_widget
        self.tree_widget.clear()

        if self._state_chart is not None:
            self.__init_fcstm()

    def __init_fcstm(self):
        for cur_transition in self._state_chart.transitions:
            src_state = cur_transition.src_state
            dst_state = cur_transition.dst_state
            event = cur_transition.event
            if src_state is None or dst_state is None or event is None:
                continue
            if src_state.id not in self.d_all_transition:
                self.d_all_transition[src_state.id] = []
            if src_state.id not in self.d_all_event:
                self.d_all_event[src_state.id] = []
            self.d_all_transition[src_state.id].append(cur_transition)
            self.d_all_event[src_state.id].append(event)
        self._populate_tree_state_machine_all_state()

    def _populate_tree_state_machine_all_state(self):
        self.tree_widget.clear()

        def add_state_to_tree(parent_item, state):
            item = QtWidgets.QTreeWidgetItem([state.name])
            item.setData(0, Qt.UserRole, state)

            if parent_item:
                parent_state = parent_item.data(0, Qt.UserRole)
                self.d_id_father_state[state.id] = parent_state
                parent_item.addChild(item)
            else:
                self.tree_widget.addTopLevelItem(item)
            if isinstance(state, CompositeState):
                for child_state in state.states:
                    add_state_to_tree(item, child_state)

        add_state_to_tree(None, self._state_chart.root_state)

    @property
    def state_chart(self) -> Statechart:
        return self._state_chart

    def add_event(self, parent_widget, pro_state: State, new_event_name: str, new_event_guard: str):
        """新增事件"""
        is_validate = True
        if pro_state.id in self.d_all_event:
            for cur_event in self.d_all_event[pro_state.id]:
                if new_event_name == cur_event.name:
                    is_validate = False

        if not is_validate:
            QtWidgets.QMessageBox.warning(
                parent_widget,
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

    def edit_event(self, parent_widget, pro_state: State, new_event_name: str,
                   new_event_guard: str, old_event_name: str):
        """修改事件"""
        is_validate = True
        old_event = None
        #找到待修改的旧事件，并判断修改是否合法
        #不合法：修改的事件名称已经存在
        if pro_state.id in self.d_all_event:
            for cur_event in self.d_all_event[pro_state.id]:
                if cur_event.name == old_event_name:
                    old_event = cur_event
                if new_event_name == cur_event.name and old_event_name != cur_event.name:
                    is_validate = False

        if not is_validate:
            QtWidgets.QMessageBox.warning(
                parent_widget,
                "警告",
                "事件名称已经存在！",
                QtWidgets.QMessageBox.Ok
            )
            return

        if old_event is not None:
            # 输入的事件名称不能已经存在
            old_event.name = new_event_name
            old_event.guard = new_event_guard

    def add_transition(self, pro_state: State, new_transition_target_state: State, new_transition_event: Event):
        new_transition = Transition(pro_state, new_transition_target_state, new_transition_event)
        self.state_chart.transitions.add(new_transition)
        if pro_state.id not in self.d_all_transition:
            self.d_all_transition[pro_state.id] = []
        self.d_all_transition[pro_state.id].append(new_transition)

    def edit_transition(self, pro_state: State, old_transition_target_name: str, old_transition_event_name: str,
                        new_transition_target_name: str, new_transition_event_name: str):
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

    def del_event(self, pro_state: State, event_name: str):
        """删除特定状态下指定名字的事件，以及与该事件相关的迁移"""
        #根据event_name找到待删除的状态
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

    def del_transition(self, pro_state: State, transition_event: str, transition_target_name: str):
        """删除特定状态下指定名字迁移"""
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