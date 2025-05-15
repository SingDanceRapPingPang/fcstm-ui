from PyQt5 import QtWidgets
import yaml

if __name__ == '__main__':
    file_path = "./app/ui/ui/export_data/S0_statemachine.yaml"

    with open(file_path, 'r', encoding='utf-8') as file:
        state_chart = yaml.safe_load(file)  # 解析 YAML 文件

    # 获取状态机名称和描述
    statechart_info = state_chart.get("statechart", {})
    print(state_chart)