import json
from ruamel.yaml import YAML
from sismic.io import import_from_yaml, export_to_plantuml
from io import StringIO

def show_state_graph(state_chart_dict: dict):
    yml = YAML()
    stream = StringIO()
    yml.dump(state_chart_dict, stream)
    yaml_string = stream.getvalue()
    print(yaml_string)
    state_chart_sismic = import_from_yaml(yaml_string)
    plantuml_text = export_to_plantuml(
        state_chart_sismic,
        filepath = 'statechart.puml',
        statechart_name=True,
        statechart_description=True,
        statechart_preamble=True,
        state_contracts=True,
        transition_contracts=True,
        transition_action=True,
    )