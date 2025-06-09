import os
import subprocess
from typing import Dict, List
from pyfcstm.model import State, CompositeState, NormalState, PseudoState, Transition, Event, Statechart
from app.utils.fcstm_state_chart import FcstmStateChart
from plantumlcli import LocalPlantuml
from app.config import PLANTUML_JAR_PATH


class ShowStateGraph:
    @classmethod
    def generate_plantuml_statechart(cls, fcstm_state_chart: FcstmStateChart) -> str:
        """
        生成 PlantUML 状态图代码

        Args:
            fcstm_state_chart: FcstmStateChart

        Returns:
            str: PlantUML 代码
        """
        # 开始 PlantUML 代码
        plantuml_code = ["@startuml", ""]

        # 添加样式定义
        plantuml_code.extend([
            "!define COMPOSITE_STATE_COLOR #FFD700",  # 金色
            "!define NORMAL_STATE_COLOR #90EE90",     # 浅绿色
            "!define PSEUDO_STATE_COLOR #FFA07A",     # 浅橙色
            "",
            "skinparam state {",
            "    BackgroundColor<<composite>> COMPOSITE_STATE_COLOR",
            "    BackgroundColor<<normal>> NORMAL_STATE_COLOR",
            "    BackgroundColor<<pseudo>> PSEUDO_STATE_COLOR",
            "    BorderColor Black",
            "    FontColor Black",
            "}",
            ""
        ])

        def process_state(state: State, is_root_state: bool = False) -> List[str]:
            """处理单个状态及其子状态"""
            state_lines = []
            state_name = state.name

            # 确定状态类型和样式
            if isinstance(state, CompositeState):
                state_type = "<<composite>>"
            elif isinstance(state, PseudoState):
                state_type = "<<pseudo>>"
            else:  # NormalState
                state_type = "<<normal>>"

            if is_root_state:
                state_lines.append(f"[*] --> {state_name.replace(' ', '_')}")  # 添加初始箭头
                state_lines.append(f"state \"{state_name}\" as {state_name.replace(' ', '_')} {state_type} {{")
            else:
                state_lines.append(f"state \"{state_name}\" as {state_name.replace(' ', '_')} {state_type} {{")
            '''
            # 添加状态进入/退出动作
            if state.on_entry:
                state_lines.append(f"    entry / {state.on_entry}")
            if state.on_exit:
                state_lines.append(f"    exit / {state.on_exit}")
            '''


            # 处理子状态
            if isinstance(state, CompositeState):
                for sub_state in state.states:
                    if sub_state.id == state.initial_state_id:
                        state_lines.extend(process_state(sub_state, True))
                    else:
                        state_lines.extend(process_state(sub_state, False))

            state_lines.append("}")
            return state_lines

        for state in fcstm_state_chart.state_chart.states:
            if isinstance(state, CompositeState) and fcstm_state_chart.d_id_father_state.get(state.id, None) is None:
                # 处理根状态
                if state.id == fcstm_state_chart.state_chart.root_state_id:
                    plantuml_code.extend(process_state(state, True))
                else:
                    plantuml_code.extend(process_state(state, False))
        # 处理迁移
        for transition in fcstm_state_chart.state_chart.transitions:
            src_state = transition.src_state.name.replace(' ', '_')
            target_state = transition.dst_state.name.replace(' ', '_')
            event = transition.event.name
            plantuml_code.append(f"    {src_state} --> {target_state} : {event}")
        # 结束 PlantUML 代码
        plantuml_code.append("@enduml")

        return "\n".join(plantuml_code)

    @classmethod
    def show_state_graph(cls, fcstm_state_chart: FcstmStateChart, png_file):
        # 生成 PlantUML 代码
        plantuml_code = cls.generate_plantuml_statechart(fcstm_state_chart)
        print(plantuml_code)
        local = LocalPlantuml.autoload(plantuml=PLANTUML_JAR_PATH)
        # print(local.dump_txt(code))  # print text graph of code
        local.dump(png_file, 'png', plantuml_code)  # save png to /my/path/source_local.png
        # 保存 PlantUML 代码到文件