import os
import subprocess
from typing import Dict, List
from pyfcstm.model import State, CompositeState, NormalState, PseudoState, Transition, Event

def generate_plantuml_statechart(statechart_data: Dict) -> str:
    """
    生成 PlantUML 状态图代码
    
    Args:
        statechart_data: 包含状态图信息的字典
        
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
    
    def process_state(state_dict: Dict, parent_name: str = None) -> List[str]:
        """处理单个状态及其子状态"""
        state_lines = []
        state_name = state_dict['name']
        
        # 确定状态类型和样式
        if 'states' in state_dict:  # Composite state
            state_type = "<<composite>>"
        elif state_name.startswith('*'):  # Pseudo state
            state_type = "<<pseudo>>"
        else:  # Normal state
            state_type = "<<normal>>"
        
        # 添加状态定义
        if parent_name:
            state_lines.append(f"state \"{state_name}\" as {state_name.replace(' ', '_')} {state_type} {{")
        else:
            state_lines.append(f"state \"{state_name}\" as {state_name.replace(' ', '_')} {state_type} {{")
        
        # 添加状态进入/退出动作
        if 'on entry' in state_dict:
            state_lines.append(f"    on entry / {state_dict['on entry']}")
        if 'on exit' in state_dict:
            state_lines.append(f"    on exit / {state_dict['on exit']}")
        
        # 处理子状态
        if 'states' in state_dict:
            for substate in state_dict['states']:
                state_lines.extend(process_state(substate, state_name))
        
        # 处理迁移
        if 'transitions' in state_dict:
            for transition in state_dict['transitions']:
                target = transition['target'].replace(' ', '_')
                event = transition['event']
                state_lines.append(f"    {state_name.replace(' ', '_')} --> {target} : {event}")
        
        state_lines.append("}")
        return state_lines
    
    # 处理根状态
    root_state = statechart_data['statechart']['root state']
    plantuml_code.extend(process_state(root_state))
    
    # 结束 PlantUML 代码
    plantuml_code.append("@enduml")
    
    return "\n".join(plantuml_code)

def show_state_graph(statechart_data: Dict):
    # 生成 PlantUML 代码
    plantuml_code = generate_plantuml_statechart(statechart_data)
    
    # 创建输出目录
    output_dir = "output"
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    
    # 保存 PlantUML 代码到文件
    puml_file = os.path.join(output_dir, "statechart.puml")
    with open(puml_file, "w", encoding="utf-8") as f:
        f.write(plantuml_code)
    
    # 设置 plantuml.jar 的路径
    plantuml_jar = "plantuml.jar"  # 确保 plantuml.jar 在正确的路径下
    
    try:
        # 调用 plantuml.jar 生成图片
        subprocess.run([
            "java",
            "-jar",
            plantuml_jar,
            puml_file,
            "-o", output_dir,  # 输出目录
            "-tpng",          # 生成 PNG 格式
            "-tsvg",          # 生成 SVG 格式
            "-tpdf"           # 生成 PDF 格式
        ], check=True)
        
        print(f"状态图已生成，保存在 {output_dir} 目录下")
        print(f"生成的文件：")
        print(f"- {os.path.join(output_dir, 'statechart.png')}")
        print(f"- {os.path.join(output_dir, 'statechart.svg')}")
        print(f"- {os.path.join(output_dir, 'statechart.pdf')}")
        
    except subprocess.CalledProcessError as e:
        print(f"生成图片时发生错误：{str(e)}")
    except FileNotFoundError:
        print("错误：找不到 plantuml.jar 文件")
    except Exception as e:
        print(f"发生未知错误：{str(e)}")

def generate_state_graph(statechart_data: Dict, output_format: str = "png") -> str:
    """
    生成状态图并返回生成的文件路径
    
    Args:
        statechart_data: 包含状态图信息的字典
        output_format: 输出格式，可选 "png", "svg", "pdf"
        
    Returns:
        str: 生成的文件路径
    """
    # 生成 PlantUML 代码
    plantuml_code = generate_plantuml_statechart(statechart_data)
    
    # 创建输出目录
    output_dir = "output"
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    
    # 保存 PlantUML 代码到文件
    puml_file = os.path.join(output_dir, "statechart.puml")
    with open(puml_file, "w", encoding="utf-8") as f:
        f.write(plantuml_code)
    
    # 设置 plantuml.jar 的路径
    plantuml_jar = "plantuml.jar"
    
    try:
        # 调用 plantuml.jar 生成图片
        subprocess.run([
            "java",
            "-jar",
            plantuml_jar,
            puml_file,
            "-o", output_dir,
            f"-t{output_format}"
        ], check=True)
        
        # 返回生成的文件路径
        output_file = os.path.join(output_dir, f"statechart.{output_format}")
        if os.path.exists(output_file):
            return output_file
        else:
            raise FileNotFoundError(f"生成的文件不存在：{output_file}")
            
    except subprocess.CalledProcessError as e:
        raise Exception(f"生成图片时发生错误：{str(e)}")
    except FileNotFoundError as e:
        raise Exception(f"找不到 plantuml.jar 文件：{str(e)}")
    except Exception as e:
        raise Exception(f"发生未知错误：{str(e)}")