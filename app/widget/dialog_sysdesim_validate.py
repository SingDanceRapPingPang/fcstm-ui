import json
from pathlib import Path
from typing import Dict, List, Optional, Sequence

from PyQt5 import QtGui, QtWidgets
from PyQt5.Qt import QDialog
from PyQt5.QtCore import QByteArray, QEvent, QSize, Qt
from PyQt5.QtSvg import QSvgWidget
from pyfcstm.convert.sysdesim import (
    build_overlay_from_diagnostics,
    build_sysdesim_phase10_report,
    build_sysdesim_timeline_import_report,
    extract_sysdesim_interactions,
    render_sysdesim_timeline_png,
    render_sysdesim_timeline_svg,
    run_sysdesim_static_pre_checks,
)

from app.utils.text_overflow import apply_text_overflow_handling, refresh_text_overflow
from ..model import State, StateManager


class DialogSysdesimValidate(QDialog):
    """SysDeSim XML timeline import report and state coexistence query."""

    def __init__(self, parent, state_managers: Sequence[StateManager]):
        super().__init__(parent)
        self.state_managers = list(state_managers or [])
        self._xml_sources: Dict[str, List[StateManager]] = self._collect_xml_sources()
        self._last_report = None
        self._last_phase10_report = None
        self._last_static_diagnostics = []
        self._last_overlay = None
        self._last_svg_text = ""
        self._diagram_base_size = QSize()
        self._last_run_kwargs: Dict[str, object] = {}
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
        self.combo_interaction_name = QtWidgets.QComboBox()
        self.combo_interaction_name.setEditable(True)
        self.spin_tick_duration = QtWidgets.QDoubleSpinBox()
        self.spin_tick_duration.setDecimals(3)
        self.spin_tick_duration.setRange(0, 1_000_000)
        self.spin_tick_duration.setSpecialValueText("自动")
        source_layout.addWidget(QtWidgets.QLabel("XML 文件："), 0, 0)
        source_layout.addWidget(self.combo_xml_source, 0, 1, 1, 3)
        source_layout.addWidget(QtWidgets.QLabel("状态机名："), 1, 0)
        source_layout.addWidget(self.edit_machine_name, 1, 1)
        source_layout.addWidget(QtWidgets.QLabel("交互名："), 1, 2)
        source_layout.addWidget(self.combo_interaction_name, 1, 3)
        source_layout.addWidget(QtWidgets.QLabel("tick(ms)："), 2, 0)
        source_layout.addWidget(self.spin_tick_duration, 2, 1)
        main_layout.addWidget(source_group)

        query_group = QtWidgets.QGroupBox("Phase11 状态共存查询")
        query_layout = QtWidgets.QGridLayout(query_group)
        self.check_enable_query = QtWidgets.QCheckBox("启用 Phase11 state query")
        self.check_enable_query.setChecked(True)
        self.check_block_static_errors = QtWidgets.QCheckBox("静态预检 error 时跳过 SMT")
        self.check_block_static_errors.setChecked(True)
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
        query_layout.addWidget(self.check_enable_query, 0, 0, 1, 2)
        query_layout.addWidget(self.check_block_static_errors, 0, 2, 1, 2)
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
        self.tabs_result = QtWidgets.QTabWidget()
        self.text_result = QtWidgets.QPlainTextEdit()
        self.text_result.setReadOnly(True)
        self.text_result.setFont(QtGui.QFontDatabase.systemFont(QtGui.QFontDatabase.FixedFont))
        self.tabs_result.addTab(self.text_result, "报告")

        witness_page = QtWidgets.QWidget()
        witness_layout = QtWidgets.QVBoxLayout(witness_page)
        self.label_witness_summary = QtWidgets.QLabel("未运行 SAT 查询")
        self.table_witness = QtWidgets.QTableWidget(0, 0)
        self.table_witness.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.table_witness.setSelectionMode(QtWidgets.QAbstractItemView.NoSelection)
        self.table_witness.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self.table_witness.setAlternatingRowColors(True)
        self.table_witness.setWordWrap(False)
        self.table_witness.verticalHeader().setVisible(False)
        self.table_witness.horizontalHeader().setStretchLastSection(False)
        self.table_witness.setStyleSheet(
            """
            QTableWidget {
                gridline-color: #cbd5e1;
                alternate-background-color: #f8fafc;
                selection-background-color: #1d4ed8;
                selection-color: #ffffff;
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
        witness_layout.addWidget(self.label_witness_summary)
        witness_layout.addWidget(self.table_witness, 1)
        self.tabs_result.addTab(witness_page, "SAT 轨迹")

        diagnostics_page = QtWidgets.QWidget()
        diagnostics_layout = QtWidgets.QVBoxLayout(diagnostics_page)
        self.table_diagnostics = QtWidgets.QTableWidget(0, 4)
        self.table_diagnostics.setHorizontalHeaderLabels(["级别", "代码", "来源", "消息"])
        self.table_diagnostics.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.table_diagnostics.setSelectionMode(QtWidgets.QAbstractItemView.NoSelection)
        self.table_diagnostics.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self.table_diagnostics.setAlternatingRowColors(False)
        self.table_diagnostics.setWordWrap(False)
        self.table_diagnostics.verticalHeader().setVisible(False)
        self.table_diagnostics.horizontalHeader().setStretchLastSection(True)
        self.table_diagnostics.horizontalHeader().setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeToContents)
        self.table_diagnostics.horizontalHeader().setSectionResizeMode(1, QtWidgets.QHeaderView.ResizeToContents)
        self.table_diagnostics.horizontalHeader().setSectionResizeMode(2, QtWidgets.QHeaderView.ResizeToContents)
        self.table_diagnostics.setStyleSheet(
            """
            QTableWidget {
                gridline-color: #cbd5e1;
                selection-background-color: transparent;
                selection-color: #0f172a;
            }
            QHeaderView::section {
                background-color: #334155;
                color: #ffffff;
                font-weight: 600;
                padding: 5px 8px;
                border: 0;
                border-right: 1px solid #64748b;
            }
            """
        )
        self.text_diagnostic_detail = QtWidgets.QPlainTextEdit()
        self.text_diagnostic_detail.setReadOnly(True)
        self.text_diagnostic_detail.setFont(QtGui.QFontDatabase.systemFont(QtGui.QFontDatabase.FixedFont))
        diagnostics_layout.addWidget(self.table_diagnostics, 2)
        diagnostics_layout.addWidget(self.text_diagnostic_detail, 1)
        self.tabs_result.addTab(diagnostics_page, "静态诊断")

        diagram_page = QtWidgets.QWidget()
        diagram_layout = QtWidgets.QVBoxLayout(diagram_page)
        self.svg_diagram = QSvgWidget()
        self.svg_diagram.setMinimumSize(0, 0)
        self.diagram_scroll = QtWidgets.QScrollArea()
        self.diagram_scroll.setWidgetResizable(False)
        self.diagram_scroll.setAlignment(Qt.AlignHCenter | Qt.AlignTop)
        self.diagram_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.diagram_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.diagram_scroll.viewport().installEventFilter(self)
        self.diagram_scroll.setWidget(self.svg_diagram)
        diagram_layout.addWidget(self.diagram_scroll)
        self.tabs_result.addTab(diagram_page, "顺序图")

        result_layout.addWidget(self.tabs_result)
        main_layout.addWidget(result_group, 1)

        button_layout = QtWidgets.QHBoxLayout()
        self.button_run = QtWidgets.QPushButton("开始验证")
        self.button_save_report = QtWidgets.QPushButton("保存 JSON 报告")
        self.button_export_svg = QtWidgets.QPushButton("导出 SVG")
        self.button_export_png = QtWidgets.QPushButton("导出 PNG")
        self.button_close = QtWidgets.QPushButton("关闭")
        button_layout.addStretch(1)
        button_layout.addWidget(self.button_run)
        button_layout.addWidget(self.button_save_report)
        button_layout.addWidget(self.button_export_svg)
        button_layout.addWidget(self.button_export_png)
        button_layout.addWidget(self.button_close)
        main_layout.addLayout(button_layout)

    def _connect(self):
        self.combo_xml_source.currentIndexChanged.connect(self._on_xml_changed)
        self.combo_left_machine.currentIndexChanged.connect(lambda _index: self._populate_state_combo("left"))
        self.combo_right_machine.currentIndexChanged.connect(lambda _index: self._populate_state_combo("right"))
        self.table_diagnostics.itemSelectionChanged.connect(self._show_selected_diagnostic)
        self.table_diagnostics.itemClicked.connect(self._show_clicked_diagnostic)
        self.button_run.clicked.connect(self._run_validate)
        self.button_save_report.clicked.connect(self._save_report)
        self.button_export_svg.clicked.connect(self._export_svg)
        self.button_export_png.clicked.connect(self._export_png)
        self.button_close.clicked.connect(self.reject)

    def eventFilter(self, watched, event):
        if watched is self.diagram_scroll.viewport() and event.type() == QEvent.Resize:
            self._resize_svg_preview_to_viewport()
        return super().eventFilter(watched, event)

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
        xml_path = self._current_xml_path()
        current_interaction = self.combo_interaction_name.currentText().strip()
        self.combo_interaction_name.clear()
        if xml_path:
            try:
                for item in extract_sysdesim_interactions(xml_path):
                    name = getattr(item, "interaction_name", None) or getattr(item, "interaction_id", "")
                    self.combo_interaction_name.addItem(name)
            except Exception:
                pass
        if current_interaction:
            self.combo_interaction_name.setCurrentText(current_interaction)

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

    def _build_validate_kwargs(self) -> Optional[Dict[str, object]]:
        kwargs: Dict[str, object] = {
            "machine_name": self.edit_machine_name.text().strip() or None,
            "interaction_name": self.combo_interaction_name.currentText().strip() or None,
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
                return None
            kwargs.update(
                {
                    "left_machine_alias": self.combo_left_machine.currentText().strip(),
                    "left_state_ref": self.combo_left_state.currentText().strip(),
                    "right_machine_alias": self.combo_right_machine.currentText().strip(),
                    "right_state_ref": self.combo_right_state.currentText().strip(),
                    "observation_scope": self.combo_scope.currentText(),
                }
            )
        return kwargs

    @staticmethod
    def _serialize_diagnostic(diag) -> Dict[str, object]:
        payload = {
            "level": getattr(diag, "level", ""),
            "code": getattr(diag, "code", ""),
            "message": getattr(diag, "message", ""),
        }
        source_id = getattr(diag, "source_id", None)
        if source_id is not None:
            payload["source_id"] = source_id
        state_path = getattr(diag, "state_path", None)
        if state_path is not None:
            payload["state_path"] = list(state_path)
        details = getattr(diag, "details", None)
        if details is not None:
            payload["details"] = details
        hints = getattr(diag, "hints", None)
        if hints:
            payload["hints"] = list(hints)
        return payload

    @staticmethod
    def _json_default(obj):
        return str(obj)

    def _diagnostic_count(self, level: str) -> int:
        level = level.lower()
        return sum(
            1 for item in self._last_static_diagnostics
            if (getattr(item, "level", "") or "").lower() == level
        )

    def _refresh_overlay_and_svg(self):
        if self._last_phase10_report is None:
            return
        phase11 = self._last_report.get("phase11") if isinstance(self._last_report, dict) else None
        timeline_report = phase11.get("timeline_report") if isinstance(phase11, dict) else None
        summary_lines = []
        if isinstance(timeline_report, dict):
            symbol = timeline_report.get("first_coexistence_symbol")
            time_text = timeline_report.get("first_coexistence_time_text")
            note = timeline_report.get("first_coexistence_note") or timeline_report.get("reason")
            if symbol is not None:
                summary_lines.append("First coexistence: {} = {}".format(symbol, time_text))
            elif note:
                summary_lines.append("Phase11: {}".format(note))
        elif isinstance(self._last_report, dict) and (self._last_report.get("static_check") or {}).get("skipped_smt"):
            summary_lines.append("Validation skipped: static pre-check has blocking errors.")

        self._last_overlay = build_overlay_from_diagnostics(
            phase10_report=self._last_phase10_report,
            diagnostics=self._last_static_diagnostics,
            summary_lines=summary_lines,
            coexistence_timeline=timeline_report if isinstance(timeline_report, dict) else None,
            include_state_cells=True,
        )
        self._last_svg_text = render_sysdesim_timeline_svg(
            phase10_report=self._last_phase10_report,
            overlay=self._last_overlay,
        )

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
        viewport_width = self.diagram_scroll.viewport().width()
        if viewport_width <= 0:
            self.svg_diagram.resize(self._diagram_base_size)
            return
        frame_margin = 2 * self.diagram_scroll.frameWidth()
        available_width = max(1, viewport_width - frame_margin)
        scale = float(available_width) / float(max(1, self._diagram_base_size.width()))
        target_width = max(1, int(round(self._diagram_base_size.width() * scale)))
        target_height = max(1, int(round(self._diagram_base_size.height() * scale)))
        self.svg_diagram.resize(target_width, target_height)

    def _populate_diagnostics(self, diagnostics: Sequence[object]):
        self.table_diagnostics.setRowCount(0)
        self.text_diagnostic_detail.clear()
        for row, diag in enumerate(diagnostics):
            self.table_diagnostics.insertRow(row)
            values = [
                getattr(diag, "level", ""),
                getattr(diag, "code", ""),
                getattr(diag, "source_id", "") or "",
                getattr(diag, "message", "") or "",
            ]
            for col, value in enumerate(values):
                item = QtWidgets.QTableWidgetItem(str(value))
                item.setData(Qt.UserRole, diag)
                self._style_diagnostic_item(item, diag, col)
                self.table_diagnostics.setItem(row, col, item)
        if diagnostics:
            self._show_diagnostic_detail(diagnostics[0])

    def _style_diagnostic_item(self, item, diag, col: int):
        level = (getattr(diag, "level", "") or "").lower()
        font = item.font()
        if level == "error":
            row_bg = QtGui.QColor("#fef2f2")
            level_bg = QtGui.QColor("#dc2626")
            level_fg = QtGui.QColor("#ffffff")
            text_fg = QtGui.QColor("#7f1d1d")
        elif level == "warning":
            row_bg = QtGui.QColor("#fffbeb")
            level_bg = QtGui.QColor("#f59e0b")
            level_fg = QtGui.QColor("#111827")
            text_fg = QtGui.QColor("#78350f")
        else:
            row_bg = QtGui.QColor("#f8fafc")
            level_bg = QtGui.QColor("#64748b")
            level_fg = QtGui.QColor("#ffffff")
            text_fg = QtGui.QColor("#334155")

        item.setBackground(level_bg if col == 0 else row_bg)
        item.setForeground(level_fg if col == 0 else text_fg)
        if col == 0:
            font.setBold(True)
            item.setText(str(item.text()).upper())
            item.setTextAlignment(Qt.AlignCenter)
        item.setFont(font)

    def _show_clicked_diagnostic(self, item):
        diag = item.data(Qt.UserRole) if item is not None else None
        self._show_diagnostic_detail(diag)

    def _show_selected_diagnostic(self):
        rows = self.table_diagnostics.selectionModel().selectedRows()
        if not rows:
            return
        item = self.table_diagnostics.item(rows[0].row(), 0)
        diag = item.data(Qt.UserRole) if item is not None else None
        self._show_diagnostic_detail(diag)

    def _show_diagnostic_detail(self, diag):
        if diag is None:
            self.text_diagnostic_detail.clear()
            return
        lines = [
            "{} {}".format(str(getattr(diag, "level", "")).upper(), getattr(diag, "code", "")),
            "",
            getattr(diag, "message", "") or "",
        ]
        source_id = getattr(diag, "source_id", None)
        if source_id:
            lines.extend(["", "source: {}".format(source_id)])
        details = getattr(diag, "details", None)
        if details:
            lines.extend(
                [
                    "",
                    "details:",
                    json.dumps(details, ensure_ascii=False, indent=2, default=self._json_default),
                ]
            )
        hints = getattr(diag, "hints", None) or []
        if hints:
            lines.extend(["", "hints:"])
            lines.extend("  - {}".format(item) for item in hints)
        self.text_diagnostic_detail.setPlainText("\n".join(lines))

    def _run_validate(self):
        xml_path = self._current_xml_path()
        if not xml_path:
            QtWidgets.QMessageBox.warning(self, "缺少 XML", "当前没有可验证的 XML 导入来源。")
            return

        kwargs = self._build_validate_kwargs()
        if kwargs is None:
            return
        self._last_report = None
        self._last_phase10_report = None
        self._last_static_diagnostics = []
        self._last_overlay = None
        self._last_svg_text = ""
        self._last_run_kwargs = dict(kwargs)
        self.text_result.clear()
        self._populate_diagnostics([])
        self._populate_witness_table(None)
        self._diagram_base_size = QSize()
        self.svg_diagram.load(QByteArray())

        QtWidgets.QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            self._last_phase10_report = build_sysdesim_phase10_report(
                xml_path,
                machine_name=kwargs.get("machine_name"),
                interaction_name=kwargs.get("interaction_name"),
                tick_duration_ms=kwargs.get("tick_duration_ms"),
            )
            self._last_static_diagnostics = run_sysdesim_static_pre_checks(
                phase10_report=self._last_phase10_report,
                left_machine_alias=kwargs.get("left_machine_alias"),
                left_state_ref=kwargs.get("left_state_ref"),
                right_machine_alias=kwargs.get("right_machine_alias"),
                right_state_ref=kwargs.get("right_state_ref"),
            )

            blocking_errors = [
                item for item in self._last_static_diagnostics
                if (getattr(item, "level", "") or "").lower() == "error"
            ]
            if blocking_errors and self.check_block_static_errors.isChecked():
                self._last_report = {
                    "source_xml_path": xml_path,
                    "selected_machine_name": self._last_phase10_report.phase9_report.selected_machine_name,
                    "selected_interaction_name": self._last_phase10_report.phase9_report.selected_interaction_name,
                    "tick_duration_ms": kwargs.get("tick_duration_ms"),
                    "static_check": {
                        "skipped_smt": True,
                        "blocking_errors": len(blocking_errors),
                        "warnings": self._diagnostic_count("warning"),
                        "diagnostics": [
                            self._serialize_diagnostic(item)
                            for item in self._last_static_diagnostics
                        ],
                    },
                }
            else:
                self._last_report = build_sysdesim_timeline_import_report(xml_path, **kwargs)
                self._last_report["static_check"] = {
                    "skipped_smt": False,
                    "blocking_errors": len(blocking_errors),
                    "warnings": self._diagnostic_count("warning"),
                    "diagnostics": [
                        self._serialize_diagnostic(item)
                        for item in self._last_static_diagnostics
                    ],
                }

            self._refresh_overlay_and_svg()
        except Exception as e:
            self._last_report = None
            QtWidgets.QMessageBox.critical(self, "SysDeSim 验证失败", str(e))
            return
        finally:
            QtWidgets.QApplication.restoreOverrideCursor()

        self.text_result.setPlainText(self._format_report(self._last_report))
        self._populate_diagnostics(self._last_static_diagnostics)
        self._populate_witness_table(self._last_report)
        self._load_svg_preview()

    def _format_report(self, report: Dict[str, object]) -> str:
        phase78 = report.get("phase78") or {}
        phase9 = report.get("phase9") or {}
        phase10 = report.get("phase10") or {}
        static_check = report.get("static_check") or {}
        outputs = phase9.get("outputs") or []
        traces = phase10.get("traces") or []
        scenario = phase10.get("scenario") or {}
        has_state_query = isinstance(report.get("phase11"), dict)
        has_import_sections = bool(phase78 or phase9 or phase10)

        lines = [
            "SysDeSim State Query Complete" if has_state_query else "SysDeSim Timeline Validation Complete",
            "Mode: {}".format(
                "static pre-check only"
                if static_check.get("skipped_smt")
                else ("import report + state query" if has_state_query else "import report only")
            ),
            f"Machine: {report.get('selected_machine_name', '')}",
            f"Interaction: {report.get('selected_interaction_name', '')}",
            f"Source: {report.get('source_xml_path', '')}",
            f"Tick: {self._format_tick_duration_text(report.get('tick_duration_ms'))}",
            "Static Check: errors={errors} warnings={warnings} diagnostics={diagnostics}{suffix}".format(
                errors=static_check.get("blocking_errors", self._diagnostic_count("error")),
                warnings=static_check.get("warnings", self._diagnostic_count("warning")),
                diagnostics=len(static_check.get("diagnostics") or self._last_static_diagnostics),
                suffix=" (SMT skipped)" if static_check.get("skipped_smt") else "",
            ),
        ]
        if not has_import_sections:
            lines.extend(["", "SMT validation was skipped because static pre-check reported blocking errors."])
            return "\n".join(lines)

        lines.extend(
            [
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
        )

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
                "  witness timeline points: {}".format(
                    len(timeline_report.get("timeline_points") or [])
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

    @staticmethod
    def _unique_headers(headers: Sequence[str]) -> List[str]:
        seen: Dict[str, int] = {}
        result = []
        for header in headers:
            base = header or "machine"
            count = seen.get(base, 0)
            seen[base] = count + 1
            result.append(base if count == 0 else "{}#{}".format(base, count + 1))
        return result

    def _phase11_machine_aliases(self, report: Dict[str, object], timeline_points: Sequence[object]) -> List[str]:
        aliases = []

        def add(alias):
            alias = str(alias or "")
            if alias and alias not in aliases:
                aliases.append(alias)

        phase9 = report.get("phase9") or {}
        for item in phase9.get("outputs") or []:
            if isinstance(item, dict):
                add(item.get("output_name"))

        phase10 = report.get("phase10") or {}
        for item in phase10.get("traces") or []:
            if isinstance(item, dict):
                add(item.get("machine_alias"))

        for point in timeline_points:
            if not isinstance(point, dict):
                continue
            for alias, _state in point.get("machine_states") or []:
                add(alias)
        return aliases

    @staticmethod
    def _coexistence_cell_text(point: Dict[str, object], timeline_report: Dict[str, object]) -> str:
        if point.get("is_coexistent"):
            if point.get("symbol") == timeline_report.get("first_coexistence_symbol"):
                return "start"
            return "yes"
        if point.get("point_kind") == "initial":
            return "initial"
        return ""

    def _populate_witness_table(self, report: Optional[Dict[str, object]]):
        self.table_witness.clear()
        self.table_witness.setRowCount(0)
        self.table_witness.setColumnCount(0)
        self.label_witness_summary.setText("未运行 SAT 查询")
        if not isinstance(report, dict):
            return

        phase11 = report.get("phase11")
        if not isinstance(phase11, dict):
            self.label_witness_summary.setText("Phase11 未启用或未返回 SAT 查询。")
            return

        solve_result = phase11.get("solve_result") or {}
        timeline_report = phase11.get("timeline_report") or {}
        timeline_points = [
            item for item in (timeline_report.get("timeline_points") or [])
            if isinstance(item, dict)
        ]
        status = str(solve_result.get("status") or timeline_report.get("status") or "").upper()
        if not timeline_points:
            reason = solve_result.get("reason") or timeline_report.get("reason") or "没有 witness timeline。"
            self.label_witness_summary.setText("SAT 轨迹：status={}，{}".format(status or "-", reason))
            return

        output_aliases = self._phase11_machine_aliases(report, timeline_points)
        main_alias = output_aliases[0] if output_aliases else None
        machine_headers = self._unique_headers([
            self._short_machine_alias(alias, main_alias)
            for alias in output_aliases
        ])
        headers = ["t", "act"] + machine_headers + ["co"]
        self.table_witness.setColumnCount(len(headers))
        self.table_witness.setHorizontalHeaderLabels(headers)
        self.table_witness.setRowCount(len(timeline_points))
        header = self.table_witness.horizontalHeader()
        header.setStretchLastSection(False)
        header.setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QtWidgets.QHeaderView.Stretch)
        for col in range(2, len(headers) - 1):
            header.setSectionResizeMode(col, QtWidgets.QHeaderView.Stretch)
        header.setSectionResizeMode(len(headers) - 1, QtWidgets.QHeaderView.ResizeToContents)

        first_symbol = timeline_report.get("first_coexistence_symbol")
        first_time = timeline_report.get("first_coexistence_time_text")
        if first_symbol is not None:
            self.label_witness_summary.setText(
                "SAT 轨迹：status={}，first coexistence {} = {}，points={}".format(
                    status or "-",
                    first_symbol,
                    first_time,
                    len(timeline_points),
                )
            )
        else:
            self.label_witness_summary.setText(
                "SAT 轨迹：status={}，points={}".format(status or "-", len(timeline_points))
            )

        for row, point in enumerate(timeline_points):
            state_map = {
                str(alias): str(state)
                for alias, state in point.get("machine_states") or []
            }
            action_text = self._format_phase11_actions(point.get("actions") or [], main_alias)
            co_text = self._coexistence_cell_text(point, timeline_report)
            values = [
                str(point.get("time_value_text", "")),
                action_text,
            ] + [
                self._short_state_text(state_map.get(alias, "-"))
                for alias in output_aliases
            ] + [
                co_text,
            ]
            tooltip = "symbol={symbol}\nkind={kind}\nlabel={label}".format(
                symbol=point.get("symbol", ""),
                kind=point.get("point_kind", ""),
                label=point.get("point_label", ""),
            )
            for col, value in enumerate(values):
                item = QtWidgets.QTableWidgetItem(value)
                item.setToolTip(tooltip)
                item.setData(Qt.UserRole, point)
                self._style_witness_item(item, point, co_text, headers[col], value)
                self.table_witness.setItem(row, col, item)

        self.table_witness.resizeColumnsToContents()
        header.setSectionResizeMode(1, QtWidgets.QHeaderView.Stretch)
        for col in range(2, len(headers) - 1):
            header.setSectionResizeMode(col, QtWidgets.QHeaderView.Stretch)

    def _style_witness_item(self, item, point: Dict[str, object], co_text: str, header: str, value: str):
        font = item.font()
        kind = point.get("point_kind")
        if co_text == "start":
            item.setBackground(QtGui.QColor("#dcfce7"))
            font.setBold(True)
        elif co_text == "yes":
            item.setBackground(QtGui.QColor("#f0fdf4"))
        elif kind == "initial":
            item.setBackground(QtGui.QColor("#eff6ff"))

        if header == "co":
            font.setBold(bool(co_text))
            if co_text == "start":
                item.setBackground(QtGui.QColor("#16a34a"))
                item.setForeground(QtGui.QColor("#ffffff"))
            elif co_text == "yes":
                item.setForeground(QtGui.QColor("#15803d"))
            elif co_text == "initial":
                item.setForeground(QtGui.QColor("#1d4ed8"))
        elif header == "act":
            if "tau:" in value:
                item.setForeground(QtGui.QColor("#b45309"))
                font.setBold(True)
            elif value and value != "-":
                item.setForeground(QtGui.QColor("#0369a1"))
        elif header not in {"t", "co"} and value != "-":
            item.setForeground(QtGui.QColor("#334155"))

        if value == "-":
            item.setForeground(QtGui.QColor("#94a3b8"))
        item.setFont(font)

    def _format_phase11_timeline_table(self, timeline_report: Dict[str, object], output_aliases: Sequence[str]) -> str:
        timeline_points = timeline_report.get("timeline_points") or []
        if not timeline_points:
            return ""

        main_alias = output_aliases[0] if output_aliases else None
        machine_headers = [self._short_machine_alias(alias, main_alias) for alias in output_aliases]
        headers = ["t", "act"] + machine_headers + ["co"]
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
                    self._format_phase11_actions(item.get("actions") or [], main_alias),
                ]
                + [state_map.get(header, "-") for header in machine_headers]
                + [co_text]
            )

        max_widths = {"t": 8, "act": 28, "co": 8}
        for header in machine_headers:
            max_widths[header] = 14

        return "\n".join(
            [
                "  witness timeline:",
                "    - t: solved continuous-time value.",
                "    - act: actions observed at that point; tau:* means hidden auto-transition.",
                "    - co: `initial` marks the initial state; `start` marks first coexistence; `yes` means coexistence still holds.",
                self._format_table(headers, rows, max_widths),
            ]
        )

    def _export_svg(self):
        if not self._last_svg_text:
            QtWidgets.QMessageBox.warning(self, "没有顺序图", "请先运行验证。")
            return
        file_path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self,
            "导出 SysDeSim 顺序图 SVG",
            "./sysdesim_sequence.svg",
            "SVG Files (*.svg);;All Files (*)",
        )
        if not file_path:
            return
        if not file_path.lower().endswith(".svg"):
            file_path += ".svg"
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(self._last_svg_text)

    def _export_png(self):
        if self._last_phase10_report is None:
            QtWidgets.QMessageBox.warning(self, "没有顺序图", "请先运行验证。")
            return
        file_path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self,
            "导出 SysDeSim 顺序图 PNG",
            "./sysdesim_sequence.png",
            "PNG Files (*.png);;All Files (*)",
        )
        if not file_path:
            return
        if not file_path.lower().endswith(".png"):
            file_path += ".png"
        QtWidgets.QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            payload = render_sysdesim_timeline_png(
                phase10_report=self._last_phase10_report,
                overlay=self._last_overlay,
                font_files=self._resolve_cjk_font_files(),
            )
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "导出 PNG 失败", str(e))
            return
        finally:
            QtWidgets.QApplication.restoreOverrideCursor()
        with open(file_path, "wb") as f:
            f.write(payload)

    @staticmethod
    def _resolve_cjk_font_files() -> Optional[List[str]]:
        try:
            from pyfcstm.entry.sysdesim import _resolve_render_font_files
            return _resolve_render_font_files([])
        except Exception:
            return None

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
            json.dump(self._last_report, f, ensure_ascii=False, indent=2, default=self._json_default)
