import yaml
from sismic.io import load_yaml
from sismic.view import view
# 颜色映射（不同类型的状态对应不同颜色）
state_type_colors = {
    "Normal": "lightblue",
    "Composite": "yellow",
    "Pseudo": "red"
}

# 读取 statechart.yaml
with open("../ui/ui/export_data/S1_states.yaml", "r", encoding="utf-8") as file:
    statechart = load_yaml(file)

# 遍历状态，为不同类型的状态赋予不同颜色
for state in statechart.states:
    # 获取状态类型，默认为 "Normal"
    state_type = state.type if hasattr(state, "type") else "Normal"

    # 获取对应颜色（如果类型未知，则用灰色）
    color = state_type_colors.get(state_type, "gray")

    # 设置 Graphviz 样式
    state.metadata["style"] = "filled"
    state.metadata["fillcolor"] = color

# 生成状态机图（带颜色）
view(statechart, format="png", filename="statechart_colored.png")