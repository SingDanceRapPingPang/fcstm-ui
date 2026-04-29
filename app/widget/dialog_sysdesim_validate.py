import json
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

from PyQt5 import QtGui, QtWidgets
from PyQt5.Qt import QDialog
from PyQt5.QtCore import Qt
from pyfcstm.convert.sysdesim import build_sysdesim_timeline_import_report

from app.utils.text_overflow import apply_text_overflow_handling, refresh_text_overflow
from ..model import State, StateManager


class DialogSysdesimValidate(QDialog):
    """SysDeSim XML timeline import report and state coexistence query."""

    def __init__(self, parent, state_managers: Sequence[StateManager]):
        super().__init__(parent)
        self.state_managers = list(state_managers or [])
        self._xml_sources: Dict[str, List[StateManager]] = self._collect_xml_sources()
        self._last_report = None
        self._init_ui()
        apply_text_overflow_handling(self)
        self._populate_xml_sources()
        self._connect()

    def _collect_xml_sources(self) -> Dict[str, List[StateManager]]:
        sources: Dict[str, List[StateManager]] = {}
        for manager in self.state_managers:
            origin = getattr(manager, "origin_file_path", None)
            if origin and str(origin).lower().endswith((".xml", ".xmi")):
                sources.setdefault(origin, []).append(manager)
        return sources

    def _init_ui(self):
        self.setWindowTitle("SysDeSim 时间线验证")
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)
        self.resize(820, 620)

        main_layout = QtWidgets.QVBoxLayout(self)

        source_group = QtWidgets.QGroupBox("已导入 SysDeSim 模型")
        source_layout = QtWidgets.QGridLayout(source_group)
        self.combo_xml_source = QtWidgets.QComboBox()
        self.edit_machine_name = QtWidgets.QLineEdit()
        self.edit_interaction_name = QtWidgets.QLineEdit()
        self.spin_tick_duration = QtWidgets.QDoubleSpinBox()
        self.spin_tick_duration.setDecimals(3)
        self.spin_tick_duration.setRange(0, 1_000_000)
        self.spin_tick_duration.setSpecialValueText("自动")
        source_layout.addWidget(QtWidgets.QLabel("XML 文件："), 0, 0)
        source_layout.addWidget(self.combo_xml_source, 0, 1, 1, 3)
        source_layout.addWidget(QtWidgets.QLabel("状态机名："), 1, 0)
        source_layout.addWidget(self.edit_machine_name, 1, 1)
        source_layout.addWidget(QtWidgets.QLabel("交互名："), 1, 2)
        source_layout.addWidget(self.edit_interaction_name, 1, 3)
        source_layout.addWidget(QtWidgets.QLabel("tick(ms)："), 2, 0)
        source_layout.addWidget(self.spin_tick_duration, 2, 1)
        main_layout.addWidget(source_group)

        query_group = QtWidgets.QGroupBox("Phase11 状态共存查询")
        query_layout = QtWidgets.QGridLayout(query_group)
        self.check_enable_query = QtWidgets.QCheckBox("启用 Phase11 state query")
        self.check_enable_query.setChecked(True)
        self.combo_left_machine = QtWidgets.QComboBox()
        self.combo_left_machine.setEditable(True)
        self.combo_left_state = QtWidgets.QComboBox()
        self.combo_left_state.setEditable(True)
        self.combo_right_machine = QtWidgets.QComboBox()
        self.combo_right_machine.setEditable(True)
        self.combo_right_state = QtWidgets.QComboBox()
        self.combo_right_state.setEditable(True)
        self.combo_scope = QtWidgets.QComboBox()
        self.combo_scope.addItems(["both", "post_step", "open_interval"])
        query_layout.addWidget(self.check_enable_query, 0, 0, 1, 4)
        query_layout.addWidget(QtWidgets.QLabel("左模型："), 1, 0)
        query_layout.addWidget(self.combo_left_machine, 1, 1)
        query_layout.addWidget(QtWidgets.QLabel("左状态："), 1, 2)
        query_layout.addWidget(self.combo_left_state, 1, 3)
        query_layout.addWidget(QtWidgets.QLabel("右模型："), 2, 0)
        query_layout.addWidget(self.combo_right_machine, 2, 1)
        query_layout.addWidget(QtWidgets.QLabel("右状态："), 2, 2)
        query_layout.addWidget(self.combo_right_state, 2, 3)
        query_layout.addWidget(QtWidgets.QLabel("观测范围："), 3, 0)
        query_layout.addWidget(self.combo_scope, 3, 1)
        main_layout.addWidget(query_group)

        result_group = QtWidgets.QGroupBox("结果")
        result_layout = QtWidgets.QVBoxLayout(result_group)
        self.text_result = QtWidgets.QPlainTextEdit()
        self.text_result.setReadOnly(True)
        self.text_result.setFont(QtGui.QFontDatabase.systemFont(QtGui.QFontDatabase.FixedFont))
        result_layout.addWidget(self.text_result)
        main_layout.addWidget(result_group, 1)

        button_layout = QtWidgets.QHBoxLayout()
        self.button_run = QtWidgets.QPushButton("开始验证")
        self.button_save_report = QtWidgets.QPushButton("保存 JSON 报告")
        self.button_close = QtWidgets.QPushButton("关闭")
        button_layout.addStretch(1)
        button_layout.addWidget(self.button_run)
        button_layout.addWidget(self.button_save_report)
        button_layout.addWidget(self.button_close)
        main_layout.addLayout(button_layout)

    def _connect(self):
        self.combo_xml_source.currentIndexChanged.connect(self._on_xml_changed)
        self.combo_left_machine.currentIndexChanged.connect(lambda _index: self._populate_state_combo("left"))
        self.combo_right_machine.currentIndexChanged.connect(lambda _index: self._populate_state_combo("right"))
        self.button_run.clicked.connect(self._run_validate)
        self.button_save_report.clicked.connect(self._save_report)
        self.button_close.clicked.connect(self.reject)

    def _populate_xml_sources(self):
        self.combo_xml_source.clear()
        for xml_path in sorted(self._xml_sources):
            self._add_xml_source_item(xml_path)
        self._on_xml_changed(0)
        refresh_text_overflow(self)

    def _add_xml_source_item(self, xml_path: str):
        for index in range(self.combo_xml_source.count()):
            if self.combo_xml_source.itemData(index) == xml_path:
                return
        self.combo_xml_source.addItem(Path(xml_path).stem, xml_path)
        refresh_text_overflow(self)

    def _on_xml_changed(self, _index: int):
        managers = self._current_source_managers()
        for combo in (self.combo_left_machine, self.combo_right_machine):
            combo.clear()
            for manager in managers:
                alias = self._manager_alias(manager)
                combo.addItem(alias, manager)
        if self.combo_right_machine.count() > 1:
            self.combo_right_machine.setCurrentIndex(1)
        self._populate_state_combo("left")
        self._populate_state_combo("right")
        refresh_text_overflow(self)

    def _current_xml_path(self) -> Optional[str]:
        return self.combo_xml_source.currentData()

    def _current_source_managers(self) -> List[StateManager]:
        xml_path = self._current_xml_path()
        if not xml_path:
            return []
        return self._xml_sources.get(xml_path, [])

    def _manager_alias(self, manager: StateManager) -> str:
        display_name = getattr(manager, "display_name", None)
        if display_name:
            return Path(display_name).stem
        source_file = getattr(manager, "source_file_path", None)
        if source_file:
            return Path(source_file).stem
        root_state = manager.get_root_state()
        return root_state.name if root_state else "StateMachine"

    def _populate_state_combo(self, side: str):
        combo_machine = self.combo_left_machine if side == "left" else self.combo_right_machine
        combo_state = self.combo_left_state if side == "left" else self.combo_right_state
        current_text = combo_state.currentText().strip()
        combo_state.clear()
        manager = combo_machine.currentData()
        if manager and manager.root_state:
            combo_state.addItems(self._state_paths(manager.root_state))
        if current_text:
            combo_state.setCurrentText(current_text)
        refresh_text_overflow(self)

    def _state_paths(self, state: State) -> List[str]:
        states = [state.get_full_path()]
        for child in state.children:
            states.extend(self._state_paths(child))
        return states

    def _run_validate(self):
        xml_path = self._current_xml_path()
        if not xml_path:
            QtWidgets.QMessageBox.warning(self, "缺少 XML", "当前没有可验证的 XML 导入来源。")
            return

        kwargs = {
            "machine_name": self.edit_machine_name.text().strip() or None,
            "interaction_name": self.edit_interaction_name.text().strip() or None,
            "tick_duration_ms": self.spin_tick_duration.value() or None,
        }
        if self.check_enable_query.isChecked():
            if not all(
                [
                    self.combo_left_machine.currentText().strip(),
                    self.combo_left_state.currentText().strip(),
                    self.combo_right_machine.currentText().strip(),
                    self.combo_right_state.currentText().strip(),
                ]
            ):
                QtWidgets.QMessageBox.warning(self, "缺少查询参数", "启用状态共存查询时，需要选择左右模型和状态。")
                return
            kwargs.update(
                {
                    "left_machine_alias": self.combo_left_machine.currentText().strip(),
                    "left_state_ref": self.combo_left_state.currentText().strip(),
                    "right_machine_alias": self.combo_right_machine.currentText().strip(),
                    "right_state_ref": self.combo_right_state.currentText().strip(),
                    "observation_scope": self.combo_scope.currentText(),
                }
            )

        QtWidgets.QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            self._last_report = build_sysdesim_timeline_import_report(xml_path, **kwargs)
        except Exception as e:
            self._last_report = None
            QtWidgets.QMessageBox.critical(self, "SysDeSim 验证失败", str(e))
            return
        finally:
            QtWidgets.QApplication.restoreOverrideCursor()

        self.text_result.setPlainText(self._format_report(self._last_report))

    def _format_report(self, report: Dict[str, object]) -> str:
        phase78 = report.get("phase78") or {}
        phase9 = report.get("phase9") or {}
        phase10 = report.get("phase10") or {}
        outputs = phase9.get("outputs") or []
        traces = phase10.get("traces") or []
        scenario = phase10.get("scenario") or {}
        has_state_query = isinstance(report.get("phase11"), dict)

        lines = [
            "SysDeSim State Query Complete" if has_state_query else "SysDeSim Timeline Import Report Complete",
            "Mode: {}".format("import report + state query" if has_state_query else "import report only"),
            f"Machine: {report.get('selected_machine_name', '')}",
            f"Interaction: {report.get('selected_interaction_name', '')}",
            f"Source: {report.get('source_xml_path', '')}",
            f"Tick: {self._format_tick_duration_text(report.get('tick_duration_ms'))}",
            "Model Import: graph_edges={graph} inputs={inputs} events={events} steps={steps} windows={windows} durations={durations} diagnostics={diagnostics}".format(
                graph=len(phase78.get("machine_graph") or []),
                inputs=len(phase78.get("input_candidates") or []),
                events=len(phase78.get("event_candidates") or []),
                steps=len(phase78.get("steps") or []),
                windows=len(phase78.get("time_windows") or []),
                durations=len(phase78.get("duration_constraints") or []),
                diagnostics=len(phase78.get("diagnostics") or []),
            ),
            f"Outputs: {len(outputs)}",
            "",
            self._format_table(
                headers=["output", "defines", "events", "diag"],
                rows=[
                    [
                        str(item.get("output_name", "")),
                        str(len(item.get("define_names") or [])),
                        str(len(item.get("event_runtime_refs") or [])),
                        self._diagnostic_summary(item.get("diagnostic_codes") or [], item.get("semantic_note")),
                    ]
                    for item in outputs
                    if isinstance(item, dict)
                ],
                max_widths={"output": 36, "defines": 7, "events": 6, "diag": 18},
                alignments={"defines": "right", "events": "right"},
            ),
        ]

        if any((item.get("diagnostic_codes") or item.get("semantic_note")) for item in outputs if isinstance(item, dict)):
            lines.extend(["", "Notes: compact diagnostics shown; use 保存 JSON 报告 to export full JSON diagnostics."])

        lines.extend(
            [
                "",
                "Scenario: scenario={name} steps={steps} temporal_constraints={constraints} bindings={bindings} traces={traces} diagnostics={diagnostics}".format(
                    name=scenario.get("name", ""),
                    steps=len(scenario.get("steps") or []),
                    constraints=len(scenario.get("temporal_constraints") or []),
                    bindings=len(phase10.get("bindings") or []),
                    traces=len(traces),
                    diagnostics=len(phase10.get("diagnostics") or []),
                ),
                "  Initial States:",
            ]
        )
        for trace in traces:
            if isinstance(trace, dict):
                lines.append(
                    "    {alias} -> {state}".format(
                        alias=trace.get("machine_alias", ""),
                        state=trace.get("initial_state_path", ""),
                    )
                )

        phase11 = report.get("phase11")
        if not isinstance(phase11, dict):
            lines.extend(["", "State Query: not requested."])
            return "\n".join(lines)

        constraint_preview = phase11.get("constraint_preview") or {}
        solve_result = phase11.get("solve_result") or {}
        timeline_report = phase11.get("timeline_report") or {}
        lines.extend(
            [
                "",
                "State Query: {left_alias}:{left_state} <-> {right_alias}:{right_state}".format(
                    left_alias=solve_result.get("left_machine_alias", ""),
                    left_state=solve_result.get("left_state_path", ""),
                    right_alias=solve_result.get("right_machine_alias", ""),
                    right_state=solve_result.get("right_state_path", ""),
                ),
                "  scope: {scope} | candidates: {count} | status: {status}".format(
                    scope=phase11.get("observation_scope", ""),
                    count=constraint_preview.get("candidate_count", ""),
                    status=str(solve_result.get("status", "")).upper(),
                ),
            ]
        )
        if timeline_report.get("first_coexistence_symbol") is not None:
            lines.append(
                "  first coexistence: {symbol} = {time}".format(
                    symbol=timeline_report.get("first_coexistence_symbol", ""),
                    time=timeline_report.get("first_coexistence_time_text", ""),
                )
            )
        if timeline_report.get("first_coexistence_note"):
            lines.append(f"  note: {timeline_report.get('first_coexistence_note')}")
        if timeline_report.get("first_coexistence_symbol") is not None:
            lines.append(
                self._format_phase11_timeline_table(
                    timeline_report,
                    [item.get("output_name", "") for item in outputs if isinstance(item, dict)],
                )
            )
        elif solve_result.get("reason"):
            lines.append(f"  reason: {solve_result.get('reason')}")
        return "\n".join(lines)

    @staticmethod
    def _format_tick_duration_text(value) -> str:
        return "not required" if value is None else f"{value} ms"

    @staticmethod
    def _fit_text(text: str, width: int, align: str = "left") -> str:
        text = str(text)
        if len(text) > width:
            text = text[: max(width - 3, 0)] + ("..." if width > 3 else "")
        return text.rjust(width) if align == "right" else text.ljust(width)

    def _format_table(
        self,
        headers: Sequence[str],
        rows: Sequence[Sequence[str]],
        max_widths: Dict[str, int],
        alignments: Optional[Dict[str, str]] = None,
    ) -> str:
        alignments = alignments or {}
        widths = []
        for index, header in enumerate(headers):
            max_len = max([len(header)] + [len(str(row[index])) for row in rows])
            widths.append(max(len(header), min(max_len, max_widths[header])))

        border = "+-" + "-+-".join("-" * width for width in widths) + "-+"

        def row(values: Sequence[str]) -> str:
            return (
                "| "
                + " | ".join(
                    self._fit_text(str(value), width, alignments.get(header, "left"))
                    for header, value, width in zip(headers, values, widths)
                )
                + " |"
            )

        return "\n".join([border, row(headers), border] + [row(item) for item in rows] + [border])

    @staticmethod
    def _short_diagnostic_code(code: str) -> str:
        short_code_map = {
            "parallel_main_machine_semantic_downgrade": "parallel-main",
            "parallel_split_semantic_downgrade": "parallel-split",
            "transition_effect_semantic_downgrade": "tx-effect",
        }
        if code in short_code_map:
            return short_code_map[code]
        if code.endswith("_semantic_downgrade"):
            code = code[: -len("_semantic_downgrade")]
        return code.replace("_", "-")

    def _diagnostic_summary(self, diagnostic_codes: Sequence[str], semantic_note: Optional[str]) -> str:
        if diagnostic_codes:
            summary = ",".join(self._short_diagnostic_code(str(code)) for code in diagnostic_codes)
        elif semantic_note:
            summary = "semantic"
        else:
            summary = "-"
        return summary[:15] + "..." if len(summary) > 18 else summary

    @staticmethod
    def _short_machine_alias(machine_alias: str, main_alias: Optional[str]) -> str:
        if main_alias is not None and machine_alias == main_alias:
            return "Main"
        if "_region" in machine_alias:
            return "R{}".format(machine_alias.rsplit("_region", 1)[-1])
        return machine_alias

    @staticmethod
    def _short_state_text(state_path: str) -> str:
        if ".Control." in state_path:
            return state_path.split(".Control.", 1)[1]
        if state_path.endswith(".Control"):
            return "Control"
        return state_path.rsplit(".", 1)[-1]

    def _format_phase11_actions(self, actions: Sequence[str], main_alias: Optional[str]) -> str:
        if not actions:
            return "-"
        rendered = []
        for item in actions:
            item = str(item)
            if item.startswith("hidden_auto(") and ": " in item and " -> " in item:
                prefix = item[len("hidden_auto("):-1]
                machine_alias, arc = prefix.split(": ", 1)
                src, dst = arc.split(" -> ", 1)
                rendered.append(
                    "tau:{alias} {src}->{dst}".format(
                        alias=self._short_machine_alias(machine_alias, main_alias),
                        src=self._short_state_text(src),
                        dst=self._short_state_text(dst),
                    )
                )
            elif item.startswith("SetInput("):
                rendered.append(item[len("SetInput("):-1])
            else:
                rendered.append(item)
        return ",".join(rendered)

    def _format_phase11_timeline_table(self, timeline_report: Dict[str, object], output_aliases: Sequence[str]) -> str:
        timeline_points = timeline_report.get("timeline_points") or []
        if not timeline_points:
            return ""

        main_alias = output_aliases[0] if output_aliases else None
        machine_headers = [self._short_machine_alias(alias, main_alias) for alias in output_aliases]
        headers = ["t", "pt", "act"] + machine_headers + ["co"]
        rows = []
        for item in timeline_points:
            if not isinstance(item, dict):
                continue
            state_map = {
                self._short_machine_alias(alias, main_alias): self._short_state_text(state)
                for alias, state in item.get("machine_states", [])
            }
            point_label = item.get("point_label", "")
            if item.get("point_kind") == "auto":
                point_label = f"tau@{point_label}"
            co_text = ""
            if item.get("is_coexistent"):
                co_text = "start" if item.get("symbol") == timeline_report.get("first_coexistence_symbol") else "yes"
            rows.append(
                [
                    str(item.get("time_value_text", "")),
                    str(point_label),
                    self._format_phase11_actions(item.get("actions") or [], main_alias),
                ]
                + [state_map.get(header, "-") for header in machine_headers]
                + [co_text]
            )

        max_widths = {"t": 8, "pt": 14, "act": 28, "co": 8}
        for header in machine_headers:
            max_widths[header] = 14

        return "\n".join(
            [
                "  witness timeline:",
                "    - t: solved continuous-time value.",
                "    - pt: `sXX` is one imported step, `tau@...` is one hidden auto point.",
                "    - act: actions observed at that point.",
                "    - co: `start` marks the first coexistence point; `yes` means coexistence still holds.",
                self._format_table(headers, rows, max_widths),
            ]
        )

    def _save_report(self):
        if self._last_report is None:
            QtWidgets.QMessageBox.warning(self, "没有报告", "请先运行验证。")
            return
        file_path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self,
            "保存 SysDeSim JSON 报告",
            "./sysdesim_report.json",
            "JSON Files (*.json);;All Files (*)",
        )
        if not file_path:
            return
        if not file_path.lower().endswith(".json"):
            file_path += ".json"
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(self._last_report, f, ensure_ascii=False, indent=2)
