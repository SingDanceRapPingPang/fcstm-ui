import pytest
from PyQt5 import QtWidgets
from PyQt5.QtCore import Qt
from app.utils.fcstm_state_chart import FcstmStateChart
from pyfcstm.model import (
    State,
    CompositeState,
    NormalState,
    Event,
    Transition,
    Statechart,
    StateType
)

class TestFcstmStateChart:

    @pytest.fixture
    def state_chart(self):
        root_state = CompositeState(name="初始状态")
        state1 = NormalState(name="状态1")
        state2 = NormalState(name="状态2")
        root_state.states.add(state1)
        root_state.states.add(state2)
        states = [root_state, state1, state2]
        state_chart = Statechart(name="测试状态图", root_state=root_state, states=states)

        return state_chart

    @pytest.fixture
    def fcstm_state_chart(self, qtbot, state_chart):
        tree_widget = QtWidgets.QTreeWidget()
        qtbot.addWidget(tree_widget)
        return FcstmStateChart(tree_widget, state_chart)


    def test_init(self, fcstm_state_chart, state_chart):
        """测试初始化"""
        assert fcstm_state_chart.state_chart == state_chart
        assert isinstance(fcstm_state_chart.d_all_event, dict)
        assert isinstance(fcstm_state_chart.d_all_transition, dict)
        assert isinstance(fcstm_state_chart.d_id_father_state, dict)
        assert fcstm_state_chart.tree_widget.topLevelItem is not None
        assert fcstm_state_chart.tree_widget.topLevelItem(0).data(0, Qt.UserRole) == state_chart.root_state

    def test_add_event(self, fcstm_state_chart, qtbot):
        """测试添加事件"""
        # 获取根状态
        root_item = fcstm_state_chart.tree_widget.topLevelItem(0)
        root_state = root_item.data(0, Qt.UserRole)

        # 添加事件
        fcstm_state_chart.add_event(None, root_state, "测试事件", "count > 0")

        # 验证事件是否添加成功
        assert root_state.id in fcstm_state_chart.d_all_event
        assert len(fcstm_state_chart.d_all_event[root_state.id]) == 1
        event = fcstm_state_chart.d_all_event[root_state.id][0]
        assert event.name == "测试事件"
        assert event.guard == "count > 0"

        # 测试添加重复事件名
        fcstm_state_chart.add_event(None, root_state, "测试事件", "count > 1")
        assert len(fcstm_state_chart.d_all_event[root_state.id]) == 1


    def test_edit_event(self, fcstm_state_chart):
        """测试编辑事件"""
        # 获取根状态
        root_item = fcstm_state_chart.tree_widget.topLevelItem(0)
        root_state = root_item.data(0, Qt.UserRole)

        # 先添加一个事件
        fcstm_state_chart.add_event(None, root_state, "原始事件", "count > 0")

        # 编辑事件
        fcstm_state_chart.edit_event(None, root_state, "新事件名", "count > 1", "原始事件")

        # 验证事件是否修改成功
        assert root_state.id in fcstm_state_chart.d_all_event
        event = fcstm_state_chart.d_all_event[root_state.id][0]
        assert event.name == "新事件名"
        assert event.guard == "count > 1"


    def test_add_transition(self, fcstm_state_chart):
        """测试添加迁移"""
        # 获取根状态和子状态
        root_item = fcstm_state_chart.tree_widget.topLevelItem(0)
        root_state = root_item.data(0, Qt.UserRole)
        state1 = root_item.child(0).data(0, Qt.UserRole)

        # 添加事件
        event = Event("测试事件", "count > 0")
        fcstm_state_chart.state_chart.events.add(event)

        # 添加迁移
        fcstm_state_chart.add_transition(root_state, state1, event)

        # 验证迁移是否添加成功
        assert root_state.id in fcstm_state_chart.d_all_transition
        assert len(fcstm_state_chart.d_all_transition[root_state.id]) == 1
        transition = fcstm_state_chart.d_all_transition[root_state.id][0]
        assert transition.src_state == root_state
        assert transition.dst_state == state1
        assert transition.event == event


    def test_edit_transition(self, fcstm_state_chart):
        """测试编辑迁移"""
        # 获取根状态和子状态
        root_item = fcstm_state_chart.tree_widget.topLevelItem(0)
        root_state = root_item.data(0, Qt.UserRole)
        state1 = root_item.child(0).data(0, Qt.UserRole)
        state2 = root_item.child(1).data(0, Qt.UserRole)

        # 添加事件
        event1 = Event("事件1", "count > 0")
        event2 = Event("事件2", "count > 1")
        fcstm_state_chart.state_chart.events.add(event1)
        fcstm_state_chart.state_chart.events.add(event2)

        # 添加迁移
        fcstm_state_chart.add_transition(root_state, state1, event1)

        # 编辑迁移
        fcstm_state_chart.edit_transition(root_state, state1.name, event1.name, state2.name, event2.name)

        # 验证迁移是否修改成功
        transition = fcstm_state_chart.d_all_transition[root_state.id][0]
        print(transition.dst_state.name, transition.event.name)
        assert transition.dst_state == state2
        assert transition.event == event2


    def test_del_event(self, fcstm_state_chart):
        """测试删除事件"""
        # 获取根状态
        root_item = fcstm_state_chart.tree_widget.topLevelItem(0)
        root_state = root_item.data(0, Qt.UserRole)

        # 添加事件
        fcstm_state_chart.add_event(None, root_state, "测试事件", "count > 0")

        # 删除事件
        fcstm_state_chart.del_event(root_state, "测试事件")

        # 验证事件是否删除成功
        assert root_state.id not in fcstm_state_chart.d_all_event or len(fcstm_state_chart.d_all_event[root_state.id]) == 0


    def test_del_transition(self, fcstm_state_chart):
        """测试删除迁移"""
        # 获取根状态和子状态
        root_item = fcstm_state_chart.tree_widget.topLevelItem(0)
        root_state = root_item.data(0, Qt.UserRole)
        state1 = root_item.child(0).data(0, Qt.UserRole)

        # 添加事件和迁移
        event = Event("测试事件", "count > 0")
        fcstm_state_chart.state_chart.events.add(event)
        fcstm_state_chart.add_transition(root_state, state1, event)

        # 删除迁移
        fcstm_state_chart.del_transition(root_state, "测试事件", "状态1")

        # 验证迁移是否删除成功
        assert root_state.id not in fcstm_state_chart.d_all_transition or len(
            fcstm_state_chart.d_all_transition[root_state.id]) == 0


    def test_add_state(self, fcstm_state_chart):
        """测试添加状态"""
        # 获取根状态

        root_item = fcstm_state_chart.tree_widget.topLevelItem(0)
        root_state = root_item.data(0, Qt.UserRole)
        fcstm_state_chart.tree_widget.setCurrentItem(root_item)

        # 添加新状态
        new_state = NormalState(name="新状态")
        fcstm_state_chart.add_state(root_state, new_state)

        # 验证状态是否添加成功
        assert new_state in root_state.states
        assert new_state.id in fcstm_state_chart.d_id_father_state
        assert fcstm_state_chart.d_id_father_state[new_state.id] == root_state

        # 验证树中是否显示新状态
        child_item = root_item.child(2)  # 第三个子项
        assert child_item is not None
        assert child_item.text(0) == "新状态"
        assert child_item.data(0, Qt.UserRole) == new_state


    def test_edit_state(self, fcstm_state_chart):
        """测试编辑状态"""
        # 获取根状态
        root_item = fcstm_state_chart.tree_widget.topLevelItem(0)
        fcstm_state_chart.tree_widget.setCurrentItem(root_item)
        root_state = root_item.data(0, Qt.UserRole)
        child_state = NormalState(name="child_state")
        child_item = None
        fcstm_state_chart.add_state(root_state, child_state)
        for item_index in range(root_item.childCount()):
            cur_child_item = root_item.child(item_index)
            cur_child_state = cur_child_item.data(0, Qt.UserRole)
            child_item = cur_child_item if cur_child_state.id == child_state.id else None

        new_child_state = NormalState(name="new_child_state", id_=child_state.id)
        # 编辑状态
        fcstm_state_chart.tree_widget.setCurrentItem(child_item)
        fcstm_state_chart.edit_state(child_state, new_child_state)

        # 验证状态是否修改成功
        assert child_item is not None
        assert child_item.text(0) == "new_child_state"
        assert child_item.data(0, Qt.UserRole) == new_child_state
        assert new_child_state in fcstm_state_chart.state_chart.states
        assert new_child_state in root_state.states


    def test_del_state(self, fcstm_state_chart):
        """测试删除状态"""
        # 获取根状态和子状态
        root_item = fcstm_state_chart.tree_widget.topLevelItem(0)
        root_state = root_item.data(0, Qt.UserRole)
        state1 = root_item.child(0).data(0, Qt.UserRole)

        # 添加事件和迁移
        event = Event("测试事件", "count > 0")
        fcstm_state_chart.state_chart.events.add(event)
        fcstm_state_chart.add_transition(state1, root_state, event)

        # 删除状态
        fcstm_state_chart.del_state(root_item.child(0), state1)

        # 验证状态是否删除成功
        assert state1 not in root_state.states
        assert state1.id not in fcstm_state_chart.d_id_father_state
        assert state1.id not in fcstm_state_chart.d_all_event
        assert state1.id not in fcstm_state_chart.d_all_transition
        assert state1 not in fcstm_state_chart.state_chart.states