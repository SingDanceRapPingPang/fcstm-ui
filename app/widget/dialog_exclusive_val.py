from pathlib import Path
from typing import List, Optional, Sequence, Tuple, Union

from PyQt5 import QtWidgets
from PyQt5.Qt import QDialog
from PyQt5.QtCore import Qt
from pyfcstm.dsl import parse_with_grammar_entry
from pyfcstm.model import StateMachine, parse_dsl_node_to_state_machine

from app.utils.ui_to_dsl import state_manager_to_dsl
from app.utils.text_overflow import apply_text_overflow_handling, refresh_text_overflow
from ..model import State, StateManager
from ..ui import UIDialogExclusiveVal


class DialogExclusiveVal(QDialog, UIDialogExclusiveVal):
    def __init__(
        self,
        parent,
        state_managers: Union[StateManager, Sequence[StateManager]],
        current_state_manager: Optional[StateManager] = None,
    ):
        super().__init__(parent)
        self.setupUi(self)
        apply_text_overflow_handling(self)
        if isinstance(state_managers, StateManager):
            self.state_managers = [state_managers]
        else:
            self.state_managers = list(state_managers or [])
        self.state_manager = (
            current_state_manager
            if current_state_manager in self.state_managers
            else (self.state_managers[0] if self.state_managers else None)
        )
        self.model_data: List[Tuple[str, str, StateMachine, str, str]] = []
        self._init()

    def _init(self):
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)
        self.setWindowTitle("状态路径互斥性验证")
        self.table_models.setColumnCount(4)
        self.table_models.setHorizontalHeaderLabels(["子状态机", "源状态", "目标状态", "来源"])
        self.table_models.horizontalHeader().setStretchLastSection(True)
        self.table_models.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self.table_models.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)

        self._populate_model_list()
        self._populate_state_list()
        self.combo_state_machine.currentIndexChanged.connect(self._on_model_changed)
        self.button_add_path.clicked.connect(self._on_add_path)
        self.button_remove_model.clicked.connect(self._on_remove_model)
        self.button_clear_models.clicked.connect(self._on_clear_models)
        self.button_accept.clicked.connect(self._on_accept)
        self.button_cancel.clicked.connect(self.reject)

    def _display_name(self, state_manager: StateManager, index: int) -> str:
        display_name = getattr(state_manager, "display_name", None)
        if display_name:
            return Path(display_name).stem
        source_file = getattr(state_manager, "source_file_path", None)
        if source_file:
            return Path(source_file).stem
        root_state = state_manager.get_root_state()
        return root_state.name if root_state else f"状态机 {index + 1}"

    def _source_name(self, state_manager: StateManager) -> str:
        source = (
            getattr(state_manager, "origin_file_path", None)
            or getattr(state_manager, "source_file_path", None)
            or ""
        )
        return Path(source).stem if source else "已导入模型"

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
            states = self._state_paths_from_ui_state(self.state_manager.root_state)
            self.combo_source_state.addItems(states)
            self.combo_destination_state.addItems(states)
            if len(states) > 1:
                self.combo_destination_state.setCurrentIndex(1)
        refresh_text_overflow(self)

    def _state_paths_from_ui_state(self, state: State) -> List[str]:
        states = [state.get_full_path()]
        for child in state.children:
            states.extend(self._state_paths_from_ui_state(child))
        return states

    def _model_from_manager(self, state_manager: StateManager) -> StateMachine:
        dsl_code = state_manager_to_dsl(state_manager)
        ast_node = parse_with_grammar_entry(dsl_code, entry_name="state_machine_dsl")
        return parse_dsl_node_to_state_machine(ast_node)

    def _on_add_path(self):
        try:
            if self.state_manager is None:
                QtWidgets.QMessageBox.warning(self, "警告", "请先选择子状态机。")
                return
            src_state = self.combo_source_state.currentText().strip()
            dst_state = self.combo_destination_state.currentText().strip()
            if not src_state or not dst_state:
                QtWidgets.QMessageBox.warning(self, "警告", "源状态和目标状态不能为空。")
                return

            model = self._model_from_manager(self.state_manager)
            index = self.state_managers.index(self.state_manager) if self.state_manager in self.state_managers else 0
            self.model_data.append(
                (
                    self._display_name(self.state_manager, index),
                    self._source_name(self.state_manager),
                    model,
                    src_state,
                    dst_state,
                )
            )
            self._update_table()
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "错误", f"添加待检查路径失败：\n{str(e)}")

    def _on_remove_model(self):
        selected_rows = set(item.row() for item in self.table_models.selectedItems())
        if not selected_rows:
            QtWidgets.QMessageBox.warning(self, "警告", "请先选择要移除的路径。")
            return
        for row in sorted(selected_rows, reverse=True):
            if 0 <= row < len(self.model_data):
                del self.model_data[row]
        self._update_table()

    def _on_clear_models(self):
        if not self.model_data:
            return
        reply = QtWidgets.QMessageBox.question(
            self,
            "确认清空",
            "确定要清空所有待检查路径吗？",
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
        )
        if reply == QtWidgets.QMessageBox.Yes:
            self.model_data.clear()
            self._update_table()

    def _update_table(self):
        self.table_models.setRowCount(len(self.model_data))
        for row, (model_name, source, _, src_state, dst_state) in enumerate(self.model_data):
            for col, value in enumerate((model_name, src_state, dst_state, source or "")):
                item = QtWidgets.QTableWidgetItem(value)
                item.setFlags(item.flags() & ~Qt.ItemIsEditable)
                item.setToolTip(value)
                self.table_models.setItem(row, col, item)
        refresh_text_overflow(self)

    def _validate_variable_consistency(self, models: List[Tuple[str, StateMachine]]) -> Tuple[bool, str]:
        if len(models) < 2:
            return True, ""

        reference_name, reference_model = models[0]
        reference_vars = reference_model.defines
        for model_name, model in models[1:]:
            ref_names = set(reference_vars.keys())
            cur_names = set(model.defines.keys())
            if ref_names != cur_names:
                return False, f"变量定义不一致：{reference_name} 与 {model_name}"
            for var_name in ref_names:
                if reference_vars[var_name].type != model.defines[var_name].type:
                    return False, f"变量 {var_name} 类型不一致：{reference_name} 与 {model_name}"
        return True, ""

    def _path_constraint(
        self,
        model: StateMachine,
        source_state: str,
        destination_state: str,
        max_path_length: int,
        max_cycle_length: int,
    ):
        from app.utils.verification import (
            build_target_constraint,
            collect_target_frames,
            get_state_frame_types,
            resolve_state_path,
            run_validate_search,
        )

        source_obj = resolve_state_path(model, source_state)
        destination_obj = resolve_state_path(model, destination_state)
        ctx = run_validate_search(
            state_machine=model,
            source_state=source_obj,
            constraint=None,
            max_path_length=max_path_length,
            max_cycle_length=max_cycle_length,
        )
        target_frames = collect_target_frames(
            ctx=ctx,
            target_state=destination_obj,
            target_frame_types=get_state_frame_types(destination_obj),
        )
        return build_target_constraint(target_frames)

    def _on_accept(self):
        try:
            import z3
            from pyfcstm.solver import create_z3_vars_from_state_machine, solve as solve_constraints

            if len(self.model_data) < 2:
                QtWidgets.QMessageBox.warning(self, "警告", "至少需要添加两条路径进行互斥性分析。")
                return

            models = [(name, model) for name, _, model, _, _ in self.model_data]
            is_consistent, error_msg = self._validate_variable_consistency(models)
            if not is_consistent:
                QtWidgets.QMessageBox.critical(self, "变量一致性检查失败", error_msg)
                return

            max_path_length = self.spinBox_max_path_length.value()
            max_cycle_length = self.spinBox_max_cycle_length.value()
            constraints = []
            summaries = []
            for model_name, _, model, src_state, dst_state in self.model_data:
                constraint = self._path_constraint(model, src_state, dst_state, max_path_length, max_cycle_length)
                constraints.append(constraint)
                summaries.append(f"{model_name}: {src_state} -> {dst_state}")

            combined_constraint = z3.And(*constraints)
            solve_result = solve_constraints(combined_constraint, max_solutions=1)
            result = self._format_result(solve_result, summaries)

            if self.checkBox_show_variables.isChecked():
                result.extend(["", "Z3 变量:"])
                for model_name, model in models:
                    result.append(f"[{model_name}]")
                    for name, var in sorted(create_z3_vars_from_state_machine(model).items()):
                        result.append(f"{name}: {var}")

            if self.checkBox_show_constraints.isChecked():
                result.extend(["", "联合约束表达式:", str(combined_constraint)])

            self._show_result("\n".join(result))
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "错误", f"互斥性验证失败：\n{str(e)}")

    def _format_result(self, solve_result, summaries: List[str]) -> List[str]:
        if solve_result.status == "sat" and solve_result.solutions:
            result = [
                "结论：这些路径不是互斥的。",
                "存在一组变量/事件赋值，使所有路径可以同时满足。",
                "",
                "路径:",
                *summaries,
                "",
                "一个满足赋值:",
            ]
            result.extend(f"{k} = {v}" for k, v in sorted(solve_result.solutions[0].items()))
            return result

        if solve_result.status == "unsat":
            return [
                "结论：这些路径是互斥的。",
                "不存在共同变量/事件赋值使这些路径同时满足。",
                "",
                "路径:",
                *summaries,
            ]

        return ["无法确定互斥性，Z3 求解器返回 unknown。", "", "路径:", *summaries]

    def _show_result(self, text: str):
        result_dialog = QtWidgets.QDialog(self)
        result_dialog.setWindowTitle("互斥性验证结果")
        result_dialog.resize(720, 520)
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
