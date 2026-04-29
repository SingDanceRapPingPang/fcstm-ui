from pathlib import Path
from typing import List, Optional, Sequence, Union

from PyQt5 import QtWidgets
from PyQt5.Qt import QDialog
from PyQt5.QtCore import Qt
from pyfcstm.dsl import parse_with_grammar_entry
from pyfcstm.model import parse_dsl_node_to_state_machine

from ..model import State, StateManager
from ..ui import UIDialogReaVal
from app.utils.ui_to_dsl import state_manager_to_dsl
from app.utils.text_overflow import apply_text_overflow_handling, refresh_text_overflow


class DialogReachabilityVal(QDialog, UIDialogReaVal):
    def __init__(
        self,
        parent,
        state_managers: Union[StateManager, Sequence[StateManager]],
        current_state_manager: Optional[StateManager] = None,
    ):
        QDialog.__init__(self, parent)
        self.setupUi(self)
        apply_text_overflow_handling(self)
        self.setFixedSize(self.width(), self.height())
        if isinstance(state_managers, StateManager):
            self.state_managers = [state_managers]
        else:
            self.state_managers = list(state_managers or [])
        self.state_manager = current_state_manager if current_state_manager in self.state_managers else (
            self.state_managers[0] if self.state_managers else None
        )
        self._init()

    def _init(self):
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)
        self.setWindowTitle("状态可达性验证")
        self._populate_model_list()
        self._populate_state_list()
        self.combo_state_machine.currentIndexChanged.connect(self._on_model_changed)
        self.button_accept.clicked.connect(self._on_accept)
        self.button_cancle.clicked.connect(self.reject)

    def _display_name(self, state_manager: StateManager, index: int) -> str:
        display_name = getattr(state_manager, "display_name", None)
        if display_name:
            return Path(display_name).stem
        source_file = getattr(state_manager, "source_file_path", None)
        if source_file:
            return Path(source_file).stem
        root_state = state_manager.get_root_state()
        return root_state.name if root_state else f"状态机 {index + 1}"

    def _populate_model_list(self):
        self.combo_state_machine.clear()
        for index, state_manager in enumerate(self.state_managers):
            self.combo_state_machine.addItem(self._display_name(state_manager, index), state_manager)
        if self.state_manager in self.state_managers:
            self.combo_state_machine.setCurrentIndex(self.state_managers.index(self.state_manager))
        refresh_text_overflow(self)

    def _on_model_changed(self, index: int):
        self.state_manager = self.combo_state_machine.itemData(index)
        self._populate_state_list()

    def _populate_state_list(self):
        self.combo_source_state.clear()
        self.combo_destination_state.clear()
        if self.state_manager and self.state_manager.root_state:
            states = self._get_states_recursive(self.state_manager.root_state)
            self.combo_source_state.addItems(states)
            self.combo_destination_state.addItems(states)
        if self.combo_source_state.count() > 0:
            self.combo_source_state.setCurrentIndex(0)
            self.combo_destination_state.setCurrentIndex(1 if self.combo_destination_state.count() > 1 else 0)
        refresh_text_overflow(self)

    def _get_states_recursive(self, state: State) -> List[str]:
        states = [state.get_full_path()]
        for child in state.children:
            states.extend(self._get_states_recursive(child))
        return states

    def _format_path(self, concrete_path) -> str:
        lines = []
        for index, frame in enumerate(concrete_path or [], start=1):
            state_path = ".".join(frame.state.path) if frame.state is not None else "<end>"
            lines.append(f"{index}. {state_path} [depth={frame.depth}, cycle={frame.cycle}, type={frame.type}]")
            if frame.var_state:
                vars_text = ", ".join(f"{k}={v}" for k, v in sorted(frame.var_state.items()))
                lines.append(f"   vars: {vars_text}")
            if frame.events:
                lines.append(f"   events: {', '.join(frame.events)}")
        return "\n".join(lines)

    def _on_accept(self):
        try:
            from app.utils.verification import (
                build_complete_solution_for_frame,
                build_target_constraint,
                collect_target_frames,
                find_matching_target_frame,
                get_state_frame_types,
                resolve_state_path,
                run_validate_search,
            )
            from pyfcstm.solver import create_z3_vars_from_state_machine, solve as solve_constraints

            source_state = self.combo_source_state.currentText().strip()
            destination_state = self.combo_destination_state.currentText().strip()
            if not source_state or not destination_state:
                QtWidgets.QMessageBox.warning(self, "错误", "源状态和目标状态不能为空。")
                return

            dsl_code = state_manager_to_dsl(self.state_manager)
            ast_node = parse_with_grammar_entry(dsl_code, entry_name="state_machine_dsl")
            model = parse_dsl_node_to_state_machine(ast_node)

            max_path_length = self.spinBox_max_path_length.value()
            max_cycle_length = self.spinBox_max_cycle_length.value()
            max_solutions = self.spinBox_max_solutions.value()
            constraint = self.edit_constraint.text().strip() or None

            source_obj = resolve_state_path(model, source_state)
            destination_obj = resolve_state_path(model, destination_state)
            ctx = run_validate_search(
                state_machine=model,
                source_state=source_obj,
                constraint=constraint,
                max_path_length=max_path_length,
                max_cycle_length=max_cycle_length,
            )
            target_frames = collect_target_frames(
                ctx=ctx,
                target_state=destination_obj,
                target_frame_types=get_state_frame_types(destination_obj),
            )
            final_constraint = build_target_constraint(target_frames)
            solve_result = solve_constraints(final_constraint, max_solutions=max_solutions)

            if solve_result.status == "sat" and solve_result.solutions:
                result_message = [
                    "可达性验证结果: 可达",
                    f"源状态: {source_state}",
                    f"目标状态: {destination_state}",
                    f"最大路径长度: {max_path_length}",
                    f"最大周期长度: {max_cycle_length}",
                    f"找到 {len(solve_result.solutions)} 个解。",
                    "",
                ]
                for index, solution in enumerate(solve_result.solutions, start=1):
                    matched_frame = find_matching_target_frame(target_frames, solution)
                    if matched_frame is None:
                        continue
                    complete_solution = build_complete_solution_for_frame(model, matched_frame, solution)
                    concrete_path = matched_frame.to_concrete_frames(complete_solution)
                    result_message.append(f"路径 {index}:")
                    result_message.append(self._format_path(concrete_path))
                    result_message.append("")

                self._append_debug_sections(result_message, model, final_constraint)
                self._show_result("验证成功", "\n".join(result_message))
            elif solve_result.status == "unsat":
                result_message = [
                    "可达性验证结果: 不可达",
                    "",
                    f"源状态: {source_state}",
                    f"目标状态: {destination_state}",
                    f"最大路径长度: {max_path_length}",
                    f"最大周期长度: {max_cycle_length}",
                ]
                self._append_debug_sections(result_message, model, final_constraint)
                self._show_result("验证结果", "\n".join(result_message))
            else:
                QtWidgets.QMessageBox.warning(self, "验证结果", "Z3 求解器返回 unknown，无法确定可达性。")
        except ModuleNotFoundError as e:
            if e.name == "z3":
                QtWidgets.QMessageBox.critical(self, "依赖缺失", "缺少 z3-solver，请安装依赖后再使用验证功能。")
            else:
                raise
        except Exception as e:
            QtWidgets.QMessageBox.critical(
                self,
                "验证失败",
                f"可达性验证时发生错误:\n{str(e)}",
                QtWidgets.QMessageBox.Ok,
            )

    def _append_debug_sections(self, lines: List[str], model, final_constraint):
        if self.checkBox_show_variables.isChecked():
            from pyfcstm.solver import create_z3_vars_from_state_machine

            lines.extend(["", "Z3 变量:"])
            for name, var in sorted(create_z3_vars_from_state_machine(model).items()):
                lines.append(f"{name}: {var}")
        if self.checkBox_show_constraints.isChecked():
            lines.extend(["", "目标约束表达式:", str(final_constraint)])

    def _show_result(self, title: str, text: str):
        result_dialog = QtWidgets.QDialog(self)
        result_dialog.setWindowTitle(title)
        result_dialog.resize(760, 560)
        layout = QtWidgets.QVBoxLayout(result_dialog)
        text_edit = QtWidgets.QPlainTextEdit(result_dialog)
        text_edit.setReadOnly(True)
        text_edit.setPlainText(text)
        layout.addWidget(text_edit)
        button_box = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Ok, result_dialog)
        button_box.accepted.connect(result_dialog.accept)
        layout.addWidget(button_box)
        apply_text_overflow_handling(result_dialog)
        result_dialog.exec_()
