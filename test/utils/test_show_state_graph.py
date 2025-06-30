import pytest
from pyfcstm.model import Statechart, CompositeState, NormalState, PseudoState, Event, Transition


class TestShowStateGraph:
    @pytest.fixture
    def sample_statechart(self):
        """创建一个包含各种类型状态的测试用状态机"""
        # 创建事件
        event1 = Event("event1", "count > 0")
        event2 = Event("event2", "count < 10")
        event3 = Event("event3", "true")

        # 创建状态
        root_state = CompositeState(name="根状态")
        state1 = NormalState(name="状态1")
        state2 = NormalState(name="状态2")
        state3 = CompositeState(name="复合状态")
        state4 = NormalState(name="状态4")
        pseudo_state = PseudoState(name="初始状态")

        # 设置状态动作
        state1.on_entry = "entry_action1"
        state1.on_exit = "exit_action1"
        state2.on_entry = "entry_action2"
        state3.on_entry = "entry_action3"
        state4.on_entry = "entry_action4"
        all_states = [root_state, state1, state2, state3, state4, pseudo_state]

        # 构建状态层次
        root_state.states.add(state1)
        root_state.states.add(state2)
        root_state.states.add(state3)
        state3.states.add(state4)
        state3.states.add(pseudo_state)

        # 创建迁移
        transition1 = Transition(state1, state2, event1)
        transition2 = Transition(state2, state3, event2)
        transition3 = Transition(state3, state1, event3)
        transition4 = Transition(pseudo_state, state4, event1)

        # 创建状态图
        statechart = Statechart(name="测试状态机", root_state=root_state, states=all_states)

        statechart.events.add(event1)
        statechart.events.add(event2)
        statechart.events.add(event3)

        statechart.transitions.add(transition1)
        statechart.transitions.add(transition2)
        statechart.transitions.add(transition3)
        statechart.transitions.add(transition4)

        return statechart

    @pytest.fixture
    def expected_plantuml(self):
        """预期的 PlantUML 代码"""
        excepted_pluntuml = [

        ]
        return """@startuml
        
        !define COMPOSITE_STATE_COLOR #FFD700
        !define NORMAL_STATE_COLOR #90EE90
        !define PSEUDO_STATE_COLOR #FFA07A
        
        skinparam state {
            BackgroundColor<<composite>> COMPOSITE_STATE_COLOR
            BackgroundColor<<normal>> NORMAL_STATE_COLOR
            BackgroundColor<<pseudo>> PSEUDO_STATE_COLOR
            BorderColor Black
            FontColor Black
        }
        
        [*] --> 根状态
        state "根状态" as 根状态 <<composite>> {
            state "状态1" as 状态1 <<normal>>
            state "状态2" as 状态2 <<normal>> 
            state "复合状态" as 复合状态 <<composite>> {
                state "状态4" as 状态4 <<normal>>
                state "初始状态" as 初始状态 <<pseudo>> {
                }
            }
        }
        状态1 --> 状态2 : event1
        状态2 --> 复合状态 : event2
        复合状态 --> 状态1 : event3
        初始状态 --> 状态4 : event1
        @enduml"""

    def test_generate_plantuml_statechart(self, sample_statechart, expected_plantuml):
        """测试状态图生成 PlantUML 代码"""
        from app.utils.show_state_graph import ShowStateGraph

        # 生成 PlantUML 代码
        generated_plantuml = ShowStateGraph.generate_plantuml_statechart(sample_statechart)

        def normalize_plantuml(plantuml: str) -> str:
            return "\n".join(line.strip() for line in plantuml.splitlines() if line.strip())

        normalized_generated = normalize_plantuml(generated_plantuml)
        normalized_expected = normalize_plantuml(expected_plantuml)

        # 比较生成的代码和预期代码
        assert normalized_generated == normalized_expected, \
            f"生成的 PlantUML 代码与预期不符：\n" \
            f"预期：\n{normalized_expected}\n" \
            f"实际：\n{normalized_generated}"