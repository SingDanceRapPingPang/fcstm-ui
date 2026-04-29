from typing import List, Optional, Tuple

from PyQt5 import QtWidgets
from PyQt5.QtCore import Qt
from pyfcstm.dsl import ALL, EXIT_STATE, INIT_STATE, parse_with_grammar_entry
from pyfcstm.dsl import node as dsl_nodes
from pyfcstm.model import StateMachine, parse_dsl_node_to_state_machine

from ..model import State as UiState
from ..model import StateManager


def parse_fcstm_file(file_path: str) -> Tuple[dsl_nodes.StateMachineDSLProgram, StateMachine, str]:
    with open(file_path, "r", encoding="utf-8") as f:
        dsl_content = f.read()

    ast_node = parse_with_grammar_entry(dsl_content, entry_name="state_machine_dsl")
    state_machine = parse_dsl_node_to_state_machine(ast_node)
    variable_definitions = "\n".join(str(item) for item in ast_node.definitions)
    return ast_node, state_machine, variable_definitions


def _state_ref_to_text(value) -> str:
    if value is INIT_STATE:
        return "[*]"
    if value is EXIT_STATE:
        return "[*]"
    if value is ALL:
        return "*"
    return str(value)


def _operation_block_to_text(operations) -> str:
    return "\n".join(str(item) for item in (operations or []))


def _transition_to_dict(transition: dsl_nodes.TransitionDefinition, *, forced: bool = False) -> dict:
    raw = str(transition)
    event = ""
    if transition.event_id is not None:
        marker = "::" if " :: " in raw else ":"
        event = f"{marker} {transition.event_id}"

    return {
        "source": ("! " if forced else "") + _state_ref_to_text(transition.from_state),
        "target": _state_ref_to_text(transition.to_state),
        "event": event,
        "condition": str(transition.condition_expr) if transition.condition_expr is not None else "",
        "action": _operation_block_to_text(getattr(transition, "post_operations", [])),
        "raw": raw,
        "is_forced": forced,
    }


def _force_transition_to_dict(transition: dsl_nodes.ForceTransitionDefinition) -> dict:
    raw = str(transition)
    event = ""
    if transition.event_id is not None:
        marker = "::" if " :: " in raw else ":"
        event = f"{marker} {transition.event_id}"

    return {
        "source": "! " + _state_ref_to_text(transition.from_state),
        "target": _state_ref_to_text(transition.to_state),
        "event": event,
        "condition": str(transition.condition_expr) if transition.condition_expr is not None else "",
        "action": "",
        "raw": raw,
        "is_forced": True,
    }


def _lifecycle_to_dict(stage: str, item, *, is_aspect: bool = False) -> dict:
    aspect = getattr(item, "aspect", None)
    lifecycle_type = stage
    if aspect:
        lifecycle_type = f"{lifecycle_type} {aspect}"
    if is_aspect:
        lifecycle_type = f">> {lifecycle_type}"

    is_abstract = "Abstract" in type(item).__name__
    ref = getattr(item, "ref", None)
    return {
        "type": lifecycle_type,
        "name": getattr(item, "name", None) or "",
        "action": _operation_block_to_text(getattr(item, "operations", [])),
        "is_abstract": is_abstract,
        "comment": getattr(item, "doc", None) or "",
        "ref": str(ref) if ref is not None else "",
        "raw": str(item),
    }


def _event_to_dict(event: dsl_nodes.EventDefinition) -> dict:
    return {
        "name": event.name,
        "extra_name": event.extra_name or "",
        "raw": str(event),
    }


def convert_ast_state_to_ui_state(
    ast_state: dsl_nodes.StateDefinition,
    parent_state: Optional[UiState] = None,
) -> UiState:
    transitions = [_transition_to_dict(item) for item in ast_state.transitions]
    force_transitions = [_force_transition_to_dict(item) for item in ast_state.force_transitions]

    lifecycle = []
    lifecycle.extend(_lifecycle_to_dict("enter", item) for item in ast_state.enters)
    lifecycle.extend(_lifecycle_to_dict("during", item) for item in ast_state.durings)
    lifecycle.extend(_lifecycle_to_dict("exit", item) for item in ast_state.exits)
    lifecycle.extend(_lifecycle_to_dict("during", item, is_aspect=True) for item in ast_state.during_aspects)

    ui_state = UiState(
        name=ast_state.name,
        transitions=[*force_transitions, *transitions],
        lifecycle=lifecycle,
        parent=parent_state,
        children=[],
        events=[_event_to_dict(item) for item in ast_state.events],
        force_transitions=force_transitions,
        extra_name=ast_state.extra_name,
        is_pseudo=bool(ast_state.is_pseudo),
    )

    for child_ast_state in ast_state.substates:
        ui_state.add_child(convert_ast_state_to_ui_state(child_ast_state, ui_state))

    return ui_state


def convert_state_machine_to_state_manager(
    ast_node: dsl_nodes.StateMachineDSLProgram,
    variable_definitions: str = "",
) -> StateManager:
    root_state = convert_ast_state_to_ui_state(ast_node.root_state)
    state_manager = StateManager(root_state)
    state_manager.variable_definitions = variable_definitions
    return state_manager


def dsl_to_state_manager(file_path: str) -> StateManager:
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            original_dsl_code = f.read()

        ast_node, _, variable_definitions = parse_fcstm_file(file_path)
        state_manager = convert_state_machine_to_state_manager(ast_node, variable_definitions)
        state_manager.original_dsl_code = original_dsl_code
        state_manager.source_file_path = file_path
        return state_manager
    except Exception as e:
        raise Exception(f"DSL到StateManager转换失败: {str(e)}")


def update_ui_from_state_manager(main_window, state_manager: StateManager):
    main_window.edit_var_def.setPlainText(state_manager.variable_definitions)
    main_window.tree_all_state.clear()

    def add_state_to_tree(state: UiState, parent_item=None):
        item = QtWidgets.QTreeWidgetItem([state.display_name()])
        item.setData(0, Qt.UserRole, state)
        item.setToolTip(0, state.get_full_path())

        if parent_item:
            parent_item.addChild(item)
        else:
            main_window.tree_all_state.addTopLevelItem(item)

        for child_state in state.children:
            add_state_to_tree(child_state, item)

    if state_manager.root_state:
        add_state_to_tree(state_manager.root_state)

    main_window.tree_all_state.expandAll()

    if main_window.at_page_initial:
        main_window.stackedWidget_state_machine.setCurrentIndex(1)
        main_window.at_page_initial = False
