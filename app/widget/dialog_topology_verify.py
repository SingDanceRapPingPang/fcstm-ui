import json
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple, Union

from PyQt5 import QtGui, QtWidgets
from PyQt5.Qt import QDialog
from PyQt5.QtCore import QByteArray, QEvent, QSize, Qt
from PyQt5.QtSvg import QSvgWidget
from pyfcstm.dsl import parse_with_grammar_entry
from pyfcstm.model import StateMachine, parse_dsl_node_to_state_machine
from pyfcstm.topology import (
    build_render_payload,
    build_topology_graph,
    check_finiteness,
    check_inevitability,
    check_reachability,
    format_node,
    render_topology_png,
    render_topology_svg,
    resolve_to_leaves,
)

from app.utils.text_overflow import apply_text_overflow_handling, refresh_text_overflow
from app.utils.ui_to_dsl import state_manager_to_dsl
from ..model import State, StateManager


class DialogTopologyVerify(QDialog):
    """Pure-topology reachability, finiteness and inevitability checks."""

    CHECKS = [
        ("reachability", "3.4 可达性", "目标状态是否存在至少一条可达路径"),
        ("finiteness", "3.5 有穷性", "所有路径是否最终到达 [*] 终止"),
        ("inevitability", "3.6 必达性", "目标状态是否出现在所有最大路径上"),
    ]

    def __init__(
        self,
        parent,
        state_managers: Union[StateManager, Sequence[StateManager]],
        current_state_manager: Optional[StateManager] = None,
        current_state: Optional[State] = None,
    ):
        super().__init__(parent)
        if isinstance(state_managers, StateManager):
            self.state_managers = [state_managers]
        else:
            self.state_managers = list(state_managers or [])
        self.state_manager = current_state_manager if current_state_manager in self.state_managers else (
            self.state_managers[0] if self.state_managers else None
        )
        self.current_state_path = current_state.get_full_path() if current_state is not None else ""
        self._last_model: Optional[StateMachine] = None
        self._last_graph = None
        self._last_result = None
        self._last_payload = None
        self._last_svg_text = ""
        self._diagram_base_size = QSize()
        self._init_ui()
        apply_text_overflow_handling(self)
        self._populate_model_list()
        self._connect()

    def _init_ui(self):
        self.setWindowTitle("拓扑验证")
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)
        self.resize(980, 720)

        main_layout = QtWidgets.QVBoxLayout(self)

        query_group = QtWidgets.QGroupBox("验证设置")
        query_layout = QtWidgets.QGridLayout(query_group)
        self.combo_state_machine = QtWidgets.QComboBox()
        self.combo_check = QtWidgets.QComboBox()
        for key, title, hint in self.CHECKS:
            self.combo_check.addItem(title, key)
            self.combo_check.setItemData(self.combo_check.count() - 1, hint, Qt.ToolTipRole)
        self.combo_source_state = QtWidgets.QComboBox()
        self.combo_source_state.setEditable(True)
        self.combo_target_state = QtWidgets.QComboBox()
        self.combo_target_state.setEditable(True)
        self.check_default_source = QtWidgets.QCheckBox("使用默认初态")
        self.check_default_source.setChecked(not bool(self.current_state_path))
        self.label_target = QtWidgets.QLabel("目标状态：")

        query_layout.addWidget(QtWidgets.QLabel("状态机："), 0, 0)
        query_layout.addWidget(self.combo_state_machine, 0, 1, 1, 3)
        query_layout.addWidget(QtWidgets.QLabel("检查项："), 1, 0)
        query_layout.addWidget(self.combo_check, 1, 1)
        query_layout.addWidget(QtWidgets.QLabel("源状态："), 1, 2)
        query_layout.addWidget(self.combo_source_state, 1, 3)
        query_layout.addWidget(self.check_default_source, 2, 1)
        query_layout.addWidget(self.label_target, 2, 2)
        query_layout.addWidget(self.combo_target_state, 2, 3)
        main_layout.addWidget(query_group)

        result_group = QtWidgets.QGroupBox("结果")
        result_layout = QtWidgets.QVBoxLayout(result_group)
        self.tabs_result = QtWidgets.QTabWidget()

        summary_page = QtWidgets.QWidget()
        summary_layout = QtWidgets.QVBoxLayout(summary_page)
        self.label_status = QtWidgets.QLabel("尚未运行验证")
        self.label_status.setMinimumHeight(34)
        self.label_status.setAlignment(Qt.AlignVCenter | Qt.AlignLeft)
        self.label_status.setStyleSheet(
            """
            QLabel {
                background: #f1f5f9;
                color: #334155;
                border: 1px solid #cbd5e1;
                border-radius: 4px;
                padding: 7px 10px;
                font-weight: 600;
            }
            """
        )
        self.text_summary = QtWidgets.QPlainTextEdit()
        self.text_summary.setReadOnly(True)
        self.text_summary.setFont(QtGui.QFontDatabase.systemFont(QtGui.QFontDatabase.FixedFont))
        summary_layout.addWidget(self.label_status)
        summary_layout.addWidget(self.text_summary, 1)
        self.tabs_result.addTab(summary_page, "报告")

        table_page = QtWidgets.QWidget()
        table_layout = QtWidgets.QVBoxLayout(table_page)
        self.table_result = QtWidgets.QTableWidget(0, 0)
        self.table_result.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.table_result.setSelectionMode(QtWidgets.QAbstractItemView.NoSelection)
        self.table_result.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self.table_result.setAlternatingRowColors(True)
        self.table_result.setWordWrap(False)
        self.table_result.verticalHeader().setVisible(False)
        self.table_result.horizontalHeader().setStretchLastSection(True)
        self.table_result.setStyleSheet(
            """
            QTableWidget {
                gridline-color: #cbd5e1;
                alternate-background-color: #f8fafc;
                selection-background-color: transparent;
                selection-color: #0f172a;
            }
            QHeaderView::section {
                background-color: #1e293b;
                color: #ffffff;
                font-weight: 600;
                padding: 5px 8px;
                border: 0;
                border-right: 1px solid #475569;
            }
            """
        )
        table_layout.addWidget(self.table_result)
        self.tabs_result.addTab(table_page, "路径 / 节点")

        diagram_page = QtWidgets.QWidget()
        diagram_layout = QtWidgets.QVBoxLayout(diagram_page)
        self.svg_diagram = QSvgWidget()
        self.svg_diagram.setMinimumSize(0, 0)
        self.diagram_scroll = QtWidgets.QScrollArea()
        self.diagram_scroll.setWidgetResizable(False)
        self.diagram_scroll.setAlignment(Qt.AlignHCenter | Qt.AlignTop)
        self.diagram_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.diagram_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.diagram_scroll.viewport().installEventFilter(self)
        self.diagram_scroll.setWidget(self.svg_diagram)
        diagram_layout.addWidget(self.diagram_scroll)
        self.tabs_result.addTab(diagram_page, "拓扑图")

        result_layout.addWidget(self.tabs_result)
        main_layout.addWidget(result_group, 1)

        button_layout = QtWidgets.QHBoxLayout()
        self.button_run = QtWidgets.QPushButton("开始验证")
        self.button_save_json = QtWidgets.QPushButton("保存 JSON")
        self.button_export_svg = QtWidgets.QPushButton("导出 SVG")
        self.button_export_png = QtWidgets.QPushButton("导出 PNG")
        self.button_close = QtWidgets.QPushButton("关闭")
        button_layout.addStretch(1)
        button_layout.addWidget(self.button_run)
        button_layout.addWidget(self.button_save_json)
        button_layout.addWidget(self.button_export_svg)
        button_layout.addWidget(self.button_export_png)
        button_layout.addWidget(self.button_close)
        main_layout.addLayout(button_layout)

    def _connect(self):
        self.combo_state_machine.currentIndexChanged.connect(self._on_model_changed)
        self.combo_check.currentIndexChanged.connect(self._on_check_changed)
        self.combo_source_state.currentTextChanged.connect(lambda _text: self._refresh_combo_tooltip(self.combo_source_state))
        self.combo_target_state.currentTextChanged.connect(lambda _text: self._refresh_combo_tooltip(self.combo_target_state))
        self.check_default_source.toggled.connect(self._sync_source_enabled)
        self.button_run.clicked.connect(self._run_check)
        self.button_save_json.clicked.connect(self._save_json)
        self.button_export_svg.clicked.connect(self._export_svg)
        self.button_export_png.clicked.connect(self._export_png)
        self.button_close.clicked.connect(self.reject)
        self._on_check_changed(self.combo_check.currentIndex())

    def eventFilter(self, watched, event):
        if watched is self.diagram_scroll.viewport() and event.type() == QEvent.Resize:
            self._resize_svg_preview_to_viewport()
        return super().eventFilter(watched, event)

    def _display_name(self, state_manager: StateManager, index: int) -> str:
        display_name = getattr(state_manager, "display_name", None)
        if display_name:
            return Path(display_name).stem
        source_file = getattr(state_manager, "source_file_path", None)
        if source_file:
            return Path(source_file).stem
        root_state = state_manager.get_root_state()
        return root_state.name if root_state else "状态机 {}".format(index + 1)

    def _populate_model_list(self):
        self.combo_state_machine.clear()
        for index, state_manager in enumerate(self.state_managers):
            self.combo_state_machine.addItem(self._display_name(state_manager, index), state_manager)
        if self.state_manager in self.state_managers:
            self.combo_state_machine.setCurrentIndex(self.state_managers.index(self.state_manager))
        self._populate_state_lists()
        refresh_text_overflow(self)

    def _on_model_changed(self, index: int):
        self.state_manager = self.combo_state_machine.itemData(index)
        self._populate_state_lists()

    def _collect_state_paths(self) -> List[Tuple[str, str]]:
        paths: List[Tuple[str, str]] = []
        if self.state_manager is None or self.state_manager.root_state is None:
            return paths

        def _walk(state: State):
            path = state.get_full_path()
            display = path
            if getattr(state, "extra_name", None):
                display = "{} ({})".format(path, state.extra_name)
            paths.append((display, path))
            for child in state.children:
                _walk(child)

        _walk(self.state_manager.root_state)
        return paths

    def _populate_state_lists(self):
        source_previous = self.current_state_path or self._combo_path(self.combo_source_state)
        target_previous = self._combo_path(self.combo_target_state)
        self.combo_source_state.clear()
        self.combo_target_state.clear()
        for display, path in self._collect_state_paths():
            self.combo_source_state.addItem(display, path)
            self.combo_target_state.addItem(display, path)

        self._select_combo_path(self.combo_source_state, source_previous)
        if target_previous:
            self._select_combo_path(self.combo_target_state, target_previous)
        elif self.combo_target_state.count() > 1:
            self.combo_target_state.setCurrentIndex(1)
        self.current_state_path = ""
        refresh_text_overflow(self)

    def _combo_path(self, combo: QtWidgets.QComboBox) -> str:
        text = combo.currentText().strip()
        for index in range(combo.count()):
            if text == combo.itemText(index):
                return str(combo.itemData(index) or text).strip()
        data = combo.currentData()
        return str(data or text).strip() if not combo.isEditable() else text

    def _refresh_combo_tooltip(self, combo: QtWidgets.QComboBox, reset_cursor: bool = False):
        text = combo.currentText().strip()
        combo.setToolTip(text)
        if combo.isEditable() and combo.lineEdit() is not None:
            combo.lineEdit().setToolTip(text)
            if reset_cursor:
                combo.lineEdit().setCursorPosition(0)

    def _select_combo_path(self, combo: QtWidgets.QComboBox, path: str):
        path = (path or "").strip()
        if not path:
            return
        for index in range(combo.count()):
            if combo.itemData(index) == path:
                combo.setCurrentIndex(index)
                self._refresh_combo_tooltip(combo, reset_cursor=True)
                return
        combo.setEditText(path)
        self._refresh_combo_tooltip(combo, reset_cursor=True)

    def _on_check_changed(self, _index: int):
        check_key = self._current_check_key()
        needs_target = check_key in {"reachability", "inevitability"}
        self.label_target.setEnabled(needs_target)
        self.combo_target_state.setEnabled(needs_target)
        self._sync_source_enabled()
        self._refresh_combo_tooltip(self.combo_source_state)
        self._refresh_combo_tooltip(self.combo_target_state)

    def _sync_source_enabled(self, *_args):
        use_default = self.check_default_source.isChecked()
        self.combo_source_state.setEnabled(not use_default)

    def _current_check_key(self) -> str:
        return str(self.combo_check.currentData() or "reachability")

    def _build_model(self) -> StateMachine:
        if self.state_manager is None:
            raise ValueError("当前没有可验证的状态机。")
        dsl_code = state_manager_to_dsl(self.state_manager)
        ast_node = parse_with_grammar_entry(dsl_code, entry_name="state_machine_dsl")
        return parse_dsl_node_to_state_machine(ast_node)

    def _state_path_or_none(self, combo: QtWidgets.QComboBox) -> Optional[str]:
        text = self._combo_path(combo)
        return text or None

    def _resolved_leaves_text(self, model: StateMachine, raw_path: Optional[str]) -> str:
        state = model.root_state if not raw_path else model.resolve_state(raw_path)
        if state is None:
            return "默认初态"
        leaves = resolve_to_leaves(state)
        return ", ".join(self._format_node(item) for item in leaves)

    def _format_node(self, node) -> str:
        return format_node(node)

    def _run_check(self):
        self._clear_result()
        check_key = self._current_check_key()
        source_path = None if self.check_default_source.isChecked() else self._state_path_or_none(self.combo_source_state)
        target_path = self._state_path_or_none(self.combo_target_state)
        if check_key == "finiteness":
            target_path = None
        if check_key in {"reachability", "inevitability"} and not target_path:
            QtWidgets.QMessageBox.warning(self, "缺少目标状态", "可达性和必达性验证需要选择目标状态。")
            return

        QtWidgets.QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            model = self._build_model()
            graph = build_topology_graph(model)
            if check_key == "reachability":
                result = check_reachability(model, target=target_path, source=source_path, graph=graph)
                title = "Reachability: {} -> {}".format(source_path or "default", target_path)
            elif check_key == "finiteness":
                result = check_finiteness(model, source=source_path, graph=graph)
                title = "Finiteness: {}".format(source_path or "default")
            elif check_key == "inevitability":
                result = check_inevitability(model, target=target_path, source=source_path, graph=graph)
                title = "Inevitability: {} -> {}".format(source_path or "default", target_path)
            else:
                raise ValueError("未知检查项: {}".format(check_key))

            svg_text = render_topology_svg(model, result, title=title, graph=graph)
            payload = build_render_payload(model, result, title=title, graph=graph)
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "拓扑验证失败", str(e), QtWidgets.QMessageBox.Ok)
            return
        finally:
            QtWidgets.QApplication.restoreOverrideCursor()

        self._last_model = model
        self._last_graph = graph
        self._last_result = result
        self._last_payload = payload
        self._last_svg_text = svg_text
        self.text_summary.setPlainText(self._format_summary(check_key, model, source_path, target_path, result, graph))
        self._set_status(check_key, result)
        self._populate_result_table(check_key, result, graph)
        self._load_svg_preview()
        self.tabs_result.setCurrentIndex(0)

    def _clear_result(self):
        self._last_model = None
        self._last_graph = None
        self._last_result = None
        self._last_payload = None
        self._last_svg_text = ""
        self._diagram_base_size = QSize()
        self.text_summary.clear()
        self.table_result.setRowCount(0)
        self.table_result.setColumnCount(0)
        self.svg_diagram.load(QByteArray())
        self.label_status.setText("运行中...")
        self.label_status.setStyleSheet(
            """
            QLabel {
                background: #eff6ff;
                color: #1d4ed8;
                border: 1px solid #93c5fd;
                border-radius: 4px;
                padding: 7px 10px;
                font-weight: 600;
            }
            """
        )

    def _set_status(self, check_key: str, result):
        if check_key == "reachability":
            ok = bool(result.reachable)
            text = "可达" if ok else "不可达"
        elif check_key == "finiteness":
            ok = bool(result.finite)
            text = "有穷" if ok else "存在无限运行反例"
        else:
            ok = bool(result.inevitable)
            text = "必达" if ok else "可规避"
        if ok:
            bg, fg, border = "#ecfdf5", "#065f46", "#6ee7b7"
        else:
            bg, fg, border = "#fef2f2", "#991b1b", "#fecaca"
        self.label_status.setText("验证结果：{}".format(text))
        self.label_status.setStyleSheet(
            """
            QLabel {{
                background: {bg};
                color: {fg};
                border: 1px solid {border};
                border-radius: 4px;
                padding: 7px 10px;
                font-weight: 700;
            }}
            """.format(bg=bg, fg=fg, border=border)
        )

    def _format_summary(self, check_key: str, model: StateMachine, source_path: Optional[str], target_path: Optional[str], result, graph) -> str:
        lines = [
            "拓扑验证完成",
            "检查项: {}".format(self.combo_check.currentText()),
            "语义: 纯拓扑宏图；忽略 guard / event / variable，每条声明转移都视为可能发生。",
            "输入源状态: {}".format(source_path or "默认初态"),
            "实际源展开: {}".format(self._resolved_leaves_text(model, source_path)),
            "实际源叶子: {}".format(self._format_node(result.source)),
        ]
        if target_path:
            lines.extend(
                [
                    "输入目标状态: {}".format(target_path),
                    "目标展开叶子: {}".format(self._resolved_leaves_text(model, target_path)),
                    "实际目标叶子: {}".format(self._format_node(result.target)),
                ]
            )
        lines.extend(
            [
                "图规模: leaves={} edges={} warnings={}".format(
                    len(graph.leaves), len(graph.edges), len(graph.warnings)
                ),
                "",
            ]
        )
        if check_key == "reachability":
            lines.append("结论: {}".format("目标可达" if result.reachable else "目标不可达"))
            if result.reachable:
                lines.append("见证路径: {}".format(result.format_witness()))
            else:
                lines.append("不可达叶子数: {}".format(len(result.unreach_leaves)))
        elif check_key == "finiteness":
            lines.append("结论: {}".format("所有宏路径均有限终止" if result.finite else "存在不会到达 [*] 的宏路径"))
            lines.append("违规叶子数: {}".format(result.violating_node_count))
            if result.counterexample is not None:
                lines.append("反例类型: {}".format(result.counterexample.kind))
                lines.append("反例路径: {}".format(result.counterexample.format()))
        else:
            lines.append("结论: {}".format("目标在所有最大路径上必达" if result.inevitable else "存在绕过目标的最大路径"))
            if result.counterexample is not None:
                lines.append("反例类型: {}".format(result.counterexample.kind))
                lines.append("反例路径: {}".format(result.counterexample.format()))
        if graph.warnings:
            lines.extend(["", "图构建警告:"])
            lines.extend("  - {}".format(item) for item in graph.warnings)
        return "\n".join(lines)

    def _populate_result_table(self, check_key: str, result, graph):
        if check_key == "reachability":
            if result.reachable and result.witness_path:
                rows = [
                    [str(index), self._format_node(node), "witness"]
                    for index, node in enumerate(result.witness_path, start=1)
                ]
                self._set_table(["#", "节点", "角色"], rows, "ok")
            else:
                rows = [
                    [str(index), self._format_node(node), "unreachable"]
                    for index, node in enumerate(result.unreach_leaves, start=1)
                ]
                self._set_table(["#", "节点", "角色"], rows, "bad")
        elif check_key == "finiteness":
            cex = result.counterexample
            if cex is None:
                rows = [
                    [str(index), self._format_node(node), "reachable leaf"]
                    for index, node in enumerate(graph.leaves, start=1)
                ]
                self._set_table(["#", "节点", "角色"], rows, "ok")
            elif cex.kind == "trap_cycle":
                prefix_rows = [[str(index), self._format_node(node), "prefix"] for index, node in enumerate(cex.prefix, start=1)]
                cycle_rows = [
                    [str(len(prefix_rows) + index), self._format_node(node), "cycle"]
                    for index, node in enumerate(cex.cycle, start=1)
                ]
                self._set_table(["#", "节点", "角色"], prefix_rows + cycle_rows, "bad")
            else:
                rows = [[str(index), self._format_node(node), "prefix"] for index, node in enumerate(cex.prefix, start=1)]
                if cex.deadlock_leaf is not None:
                    rows.append([str(len(rows) + 1), self._format_node(cex.deadlock_leaf), "deadlock"])
                self._set_table(["#", "节点", "角色"], rows, "bad")
        else:
            cex = result.counterexample
            if cex is None:
                rows = [
                    [str(index), self._format_node(node), "target inevitable"]
                    for index, node in enumerate(graph.leaves, start=1)
                ]
                self._set_table(["#", "节点", "角色"], rows, "ok")
            else:
                rows = [[str(index), self._format_node(node), "counterexample"] for index, node in enumerate(cex.prefix, start=1)]
                if cex.kind == "cycle":
                    rows.extend(
                        [str(len(rows) + index), self._format_node(node), "cycle"]
                        for index, node in enumerate(cex.cycle, start=1)
                    )
                elif cex.terminal is not None:
                    rows.append([str(len(rows) + 1), self._format_node(cex.terminal), cex.kind])
                self._set_table(["#", "节点", "角色"], rows, "bad")

    def _set_table(self, headers: List[str], rows: List[List[str]], theme: str):
        self.table_result.clear()
        self.table_result.setColumnCount(len(headers))
        self.table_result.setHorizontalHeaderLabels(headers)
        self.table_result.setRowCount(len(rows))
        for row_index, row_values in enumerate(rows):
            for col_index, value in enumerate(row_values):
                item = QtWidgets.QTableWidgetItem(str(value))
                item.setToolTip(str(value))
                if col_index == 0:
                    item.setTextAlignment(Qt.AlignCenter)
                self._style_result_item(item, theme, str(row_values[-1]).lower())
                self.table_result.setItem(row_index, col_index, item)
        self.table_result.resizeColumnsToContents()
        self.table_result.horizontalHeader().setStretchLastSection(True)

    def _style_result_item(self, item, theme: str, role: str):
        if theme == "ok":
            bg = QtGui.QColor("#ecfdf5" if "witness" in role or "target" in role else "#f8fafc")
            fg = QtGui.QColor("#065f46" if "witness" in role or "target" in role else "#334155")
        else:
            if "cycle" in role or "deadlock" in role:
                bg = QtGui.QColor("#fef2f2")
                fg = QtGui.QColor("#991b1b")
            elif "unreachable" in role:
                bg = QtGui.QColor("#f1f5f9")
                fg = QtGui.QColor("#64748b")
            else:
                bg = QtGui.QColor("#fff7ed")
                fg = QtGui.QColor("#9a3412")
        item.setBackground(bg)
        item.setForeground(fg)

    def _load_svg_preview(self):
        if not self._last_svg_text:
            return
        payload = QByteArray(self._last_svg_text.encode("utf-8"))
        self.svg_diagram.load(payload)
        size = self.svg_diagram.renderer().defaultSize()
        if not size.isValid():
            view_box = self.svg_diagram.renderer().viewBoxF()
            if view_box.isValid():
                size = QSize(max(1, int(view_box.width())), max(1, int(view_box.height())))
        self._diagram_base_size = size if size.isValid() else QSize(640, 360)
        self._resize_svg_preview_to_viewport()

    def _resize_svg_preview_to_viewport(self):
        if not self._diagram_base_size.isValid() or self._diagram_base_size.isEmpty():
            return
        viewport_size = self.diagram_scroll.viewport().size()
        if viewport_size.width() <= 0:
            self.svg_diagram.resize(self._diagram_base_size)
            return
        frame_margin = 2 * self.diagram_scroll.frameWidth()
        available_width = max(1, viewport_size.width() - frame_margin)
        if self._diagram_base_size.width() > available_width:
            scale = float(available_width) / float(max(1, self._diagram_base_size.width()))
        else:
            scale = 1.0
        target_width = max(1, int(round(self._diagram_base_size.width() * scale)))
        target_height = max(1, int(round(self._diagram_base_size.height() * scale)))
        self.svg_diagram.resize(target_width, target_height)

    def _save_json(self):
        if self._last_payload is None:
            QtWidgets.QMessageBox.information(self, "无结果", "请先运行一次拓扑验证。")
            return
        file_path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self,
            "保存拓扑验证 JSON",
            "topology_verification.json",
            "JSON Files (*.json);;All Files (*)",
        )
        if not file_path:
            return
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(self._last_payload, f, ensure_ascii=False, indent=2, default=str)

    def _export_svg(self):
        if not self._last_svg_text:
            QtWidgets.QMessageBox.information(self, "无结果", "请先运行一次拓扑验证。")
            return
        file_path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self,
            "导出拓扑图 SVG",
            "topology_verification.svg",
            "SVG Files (*.svg);;All Files (*)",
        )
        if not file_path:
            return
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(self._last_svg_text)

    def _export_png(self):
        if self._last_model is None or self._last_result is None:
            QtWidgets.QMessageBox.information(self, "无结果", "请先运行一次拓扑验证。")
            return
        file_path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self,
            "导出拓扑图 PNG",
            "topology_verification.png",
            "PNG Files (*.png);;All Files (*)",
        )
        if not file_path:
            return
        QtWidgets.QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            png = render_topology_png(self._last_model, self._last_result, graph=self._last_graph)
            with open(file_path, "wb") as f:
                f.write(png)
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "导出失败", str(e), QtWidgets.QMessageBox.Ok)
        finally:
            QtWidgets.QApplication.restoreOverrideCursor()
