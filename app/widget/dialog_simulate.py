from PyQt5.Qt import QDialog
from PyQt5 import QtWidgets
from PyQt5.QtCore import Qt, QTimer
import json
import re
import csv
from pathlib import Path

from ..ui import UIDialogSimulate
from typing import Optional, List, Sequence, Union
from ..model import State, StateManager
from app.utils.ui_to_dsl import state_manager_to_dsl
from app.utils.text_overflow import apply_text_overflow_handling, refresh_text_overflow
from pyfcstm.dsl import parse_with_grammar_entry
from pyfcstm.model import parse_dsl_node_to_state_machine
from pyfcstm.simulate import SimulationRuntime
from pyfcstm.entry.simulate.commands import CommandProcessor


class DialogSimulate(QDialog, UIDialogSimulate):
    """模型仿真对话框"""

    def __init__(
        self,
        parent,
        state_managers: Union[StateManager, Sequence[StateManager]],
        current_state_manager: Optional[StateManager] = None,
    ):
        QDialog.__init__(self, parent)
        self.setupUi(self)
        apply_text_overflow_handling(self)

        if isinstance(state_managers, StateManager):
            self.state_managers = [state_managers]
        else:
            self.state_managers = list(state_managers or [])
        self.state_manager = current_state_manager if current_state_manager in self.state_managers else (
            self.state_managers[0] if self.state_managers else None
        )
        self.simulation_runtime: Optional[SimulationRuntime] = None
        self.model = None
        self.cycle_count = 0
        self.is_running = False

        # 定时器用于连续执行
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._execute_single_cycle)
        self.timer_interval = 1000  # 默认1秒

        self._init()

    def _init(self):
        """初始化对话框"""
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)
        self._init_ui()
        self._init_model()
        self._init_connections()

    def _init_ui(self):
        """初始化UI"""
        self.setWindowTitle("模型仿真")
        if hasattr(self, "label_events"):
            self.label_events.setText("命令序列：")
        if hasattr(self, "edit_events"):
            self.edit_events.setPlaceholderText(
                '多个 pyfcstm REPL 命令用 ; 分隔，例如 current; cycle; cycle Start; cycle Stop'
            )
        if hasattr(self, "button_single_cycle"):
            self.button_single_cycle.setText("执行输入")
            self.button_single_cycle.setToolTip("执行 REPL 命令序列；命令为空时执行一次 cycle。")
        if hasattr(self, "button_run_continuous"):
            self.button_run_continuous.setToolTip("命令为空时按定时器连续执行 cycle；命令有内容时执行一次完整序列。")
        if hasattr(self, "button_import_events"):
            self.button_import_events.setText("导入命令...")
        self._populate_model_list()
        self._update_speed_label()

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
        self._populate_initial_state_list()
        refresh_text_overflow(self)

    def _populate_initial_state_list(self):
        if not hasattr(self, "combo_initial_state"):
            return
        current_text = self.combo_initial_state.currentText().strip()
        was_blocked = self.combo_initial_state.blockSignals(True)
        self.combo_initial_state.clear()
        self.combo_initial_state.addItem("")
        if self.state_manager and self.state_manager.root_state:
            self.combo_initial_state.addItems(self._state_paths_from_ui_state(self.state_manager.root_state))
        if current_text:
            index = self.combo_initial_state.findText(current_text)
            if index >= 0:
                self.combo_initial_state.setCurrentIndex(index)
            else:
                self.combo_initial_state.setEditText(current_text)
        self.combo_initial_state.blockSignals(was_blocked)
        refresh_text_overflow(self)

    def _state_paths_from_ui_state(self, state: State) -> List[str]:
        states = [state.get_full_path()]
        for child in state.children:
            states.extend(self._state_paths_from_ui_state(child))
        return states

    def _parse_initial_vars(self):
        text = self.edit_initial_vars.text().strip()
        if not text:
            return None
        try:
            if text.startswith("{"):
                values = json.loads(text)
            else:
                values = {}
                for item in re.split(r"[,;]\s*", text):
                    item = item.strip()
                    if not item:
                        continue
                    if "=" not in item:
                        raise ValueError(f"初始变量项缺少等号: {item}")
                    key, raw_value = item.split("=", 1)
                    values[key.strip()] = json.loads(raw_value.strip())
        except Exception as e:
            raise ValueError(f"初始变量格式错误: {e}")

        if not isinstance(values, dict):
            raise ValueError("初始变量必须是对象或 key=value 列表。")
        for key, value in values.items():
            if not isinstance(key, str) or not key:
                raise ValueError("初始变量名不能为空。")
            if not isinstance(value, (int, float)):
                raise ValueError(f"初始变量 {key} 的值必须是数字。")
        return values

    def _init_model(self):
        """初始化模型和仿真运行时"""
        try:
            if self.state_manager is None:
                raise ValueError("未选择可仿真的子状态机")
            dsl_code = state_manager_to_dsl(self.state_manager)

            # 解析DSL代码为状态机模型
            ast_node = parse_with_grammar_entry(dsl_code, entry_name='state_machine_dsl')
            self.model = parse_dsl_node_to_state_machine(ast_node)

            # 创建仿真运行时
            initial_state = self.combo_initial_state.currentText().strip() or None
            initial_vars = self._parse_initial_vars()
            history_size = self.spin_history_size.value() or None
            abstract_error_mode = self.combo_abstract_error_mode.currentText() or "raise"
            self.simulation_runtime = SimulationRuntime(
                self.model,
                abstract_error_mode=abstract_error_mode,
                history_size=history_size,
                initial_state=initial_state,
                initial_vars=initial_vars,
            )

            # 显示模型信息
            self._display_model_info()

            # 输出初始化信息
            self._append_output("=" * 60)
            self._append_output("模型仿真初始化成功")
            self._append_output("=" * 60)
            self._append_output(f"模型名称: {self.model.name if hasattr(self.model, 'name') else '未命名'}")
            self._append_output(f"初始状态: {self.simulation_runtime.current_state if hasattr(self.simulation_runtime, 'current_state') else '未知'}")
            if initial_state:
                self._append_output(f"热启动状态: {initial_state}")
            if initial_vars:
                self._append_output(f"初始变量: {initial_vars}")
            self._append_output("=" * 60)
            self._append_output("")

        except Exception as e:
            error_msg = f"模型初始化失败: {str(e)}"
            self._append_output(error_msg)
            QtWidgets.QMessageBox.critical(self, "错误", error_msg)

    def _init_connections(self):
        """初始化信号连接"""
        self.button_single_cycle.clicked.connect(self._on_single_cycle)
        self.button_run_continuous.clicked.connect(self._on_run_continuous)
        self.button_pause.clicked.connect(self._on_pause)
        self.button_reset.clicked.connect(self._on_reset)
        self.button_close.clicked.connect(self.close)
        self.button_import_initial_vars.clicked.connect(self._on_import_initial_vars)
        self.button_import_events.clicked.connect(self._on_import_events)
        self.slider_speed.valueChanged.connect(self._on_speed_changed)
        self.combo_state_machine.currentIndexChanged.connect(self._on_model_changed)
        self.combo_initial_state.currentIndexChanged.connect(lambda _index: self._restart_model_from_options())
        self.edit_initial_vars.editingFinished.connect(self._restart_model_from_options)
        self.spin_history_size.valueChanged.connect(lambda _value: self._restart_model_from_options())
        self.combo_abstract_error_mode.currentIndexChanged.connect(lambda _index: self._restart_model_from_options())

    def _on_model_changed(self, index):
        state_manager = self.combo_state_machine.itemData(index)
        if state_manager is None or state_manager is self.state_manager:
            return
        if self.is_running:
            self._on_pause()
        self.state_manager = state_manager
        self.cycle_count = 0
        self.text_simulation_output.clear()
        self._update_cycle_count()
        self._populate_initial_state_list()
        self._init_model()

    def _parse_imported_value(self, raw_value: str):
        raw_value = raw_value.strip()
        try:
            return json.loads(raw_value)
        except Exception:
            pass
        try:
            return int(raw_value, 0)
        except ValueError:
            pass
        return float(raw_value)

    def _load_initial_vars_file(self, file_path: str) -> dict:
        suffix = Path(file_path).suffix.lower()
        if suffix == ".json":
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict) and "variables" in data:
                data = data["variables"]
            if not isinstance(data, dict):
                raise ValueError("JSON 变量文件必须是对象，或包含 variables 对象。")
            return data

        if suffix == ".csv":
            with open(file_path, "r", encoding="utf-8-sig", newline="") as f:
                rows = list(csv.reader(f))
            rows = [row for row in rows if any(cell.strip() for cell in row)]
            if not rows:
                return {}
            first = [cell.strip().lower() for cell in rows[0]]
            if len(first) >= 2 and first[0] in {"name", "var", "variable", "变量"}:
                return {
                    row[0].strip(): self._parse_imported_value(row[1])
                    for row in rows[1:]
                    if len(row) >= 2 and row[0].strip()
                }
            if len(rows) >= 2:
                names = [cell.strip() for cell in rows[0]]
                values = rows[1]
                return {
                    name: self._parse_imported_value(values[index])
                    for index, name in enumerate(names)
                    if name and index < len(values)
                }
            raise ValueError("CSV 变量文件需要 name,value 两列，或第一行变量名、第二行变量值。")

        values = {}
        with open(file_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" not in line:
                    raise ValueError(f"变量行缺少等号: {line}")
                key, raw_value = line.split("=", 1)
                values[key.strip()] = self._parse_imported_value(raw_value)
        return values

    def _load_events_file(self, file_path: str) -> List[str]:
        suffix = Path(file_path).suffix.lower()
        if suffix == ".json":
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                data = data.get("events", [])
            if not isinstance(data, list):
                raise ValueError("JSON 事件文件必须是数组，或包含 events 数组。")
            return [str(item).strip() for item in data if str(item).strip()]

        if suffix == ".csv":
            events = []
            with open(file_path, "r", encoding="utf-8-sig", newline="") as f:
                for row in csv.reader(f):
                    events.extend(cell.strip() for cell in row if cell.strip())
            if events and events[0].lower() in {"event", "events", "事件"}:
                events = events[1:]
            return events

        with open(file_path, "r", encoding="utf-8") as f:
            text = f.read()
        return [item.strip() for item in re.split(r"[;\r\n]+", text) if item.strip()]

    def _load_simulation_input_file(self, file_path: str) -> str:
        suffix = Path(file_path).suffix.lower()
        if suffix in {".txt", ".cmd", ".commands"}:
            with open(file_path, "r", encoding="utf-8") as f:
                text = f.read().strip()
            return text
        events = self._load_events_file(file_path)
        return "; ".join(f"cycle {event}" for event in events)

    def _on_import_initial_vars(self):
        file_path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self,
            "导入初始变量",
            "./",
            "Data Files (*.json *.csv *.txt);;All Files (*)",
        )
        if not file_path:
            return
        try:
            values = self._load_initial_vars_file(file_path)
            self.edit_initial_vars.setText(json.dumps(values, ensure_ascii=False))
            self._restart_model_from_options()
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "导入变量失败", str(e))

    def _on_import_events(self):
        file_path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self,
            "导入命令序列",
            "./",
            "Command Files (*.txt *.cmd *.commands *.json *.csv);;All Files (*)",
        )
        if not file_path:
            return
        try:
            self._set_input_text(self._load_simulation_input_file(file_path))
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "导入命令失败", str(e))

    def _restart_model_from_options(self):
        if self.is_running:
            return
        self.cycle_count = 0
        self._update_cycle_count()
        self.text_simulation_output.clear()
        self._init_model()

    def _display_model_info(self):
        """显示模型信息"""
        if self.model:
            try:
                model_str = str(self.model.to_ast_node())
                self.text_model_display.setPlainText(model_str)
            except Exception as e:
                self.text_model_display.setPlainText(f"模型信息显示失败: {str(e)}")

    def _append_output(self, text: str):
        """追加输出信息"""
        self.text_simulation_output.append(text)
        # 自动滚动到底部
        scrollbar = self.text_simulation_output.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def _update_cycle_count(self):
        """更新周期计数显示"""
        self.label_cycle_count.setText(f"当前周期：{self.cycle_count}")

    def _update_speed_label(self):
        """更新速度标签"""
        speed_value = self.slider_speed.value()
        # 速度值1-10，对应2.0秒到0.2秒
        # 速度1 = 2.0秒，速度10 = 0.2秒
        interval = 2.2 - (speed_value * 0.2)
        self.label_speed_value.setText(f"{interval:.1f} 秒/周期")
        self.timer_interval = int(interval * 1000)

    def _input_text(self) -> str:
        if hasattr(self.edit_events, "toPlainText"):
            return self.edit_events.toPlainText().strip()
        return self.edit_events.text().strip()

    def _set_input_text(self, text: str):
        if hasattr(self.edit_events, "setPlainText"):
            self.edit_events.setPlainText(text)
        else:
            self.edit_events.setText(text)

    def _split_batch_commands(self, text: str) -> List[str]:
        return [command.strip() for command in re.split(r"[;\r\n]+", text) if command.strip()]

    def _sync_cycle_count_from_runtime(self):
        if self.simulation_runtime and hasattr(self.simulation_runtime, "cycle_count"):
            self.cycle_count = self.simulation_runtime.cycle_count
        self._update_cycle_count()

    def _execute_repl_commands(self, command_string: str):
        if not self.simulation_runtime:
            self._append_output("错误: 仿真运行时未初始化")
            return

        processor = CommandProcessor(self.simulation_runtime, state_machine=self.model, use_color=False)
        commands = self._split_batch_commands(command_string)
        for index, command in enumerate(commands):
            separator = "-" * 60
            self._append_output(f"{separator}\n>>> {command}\n{separator}")
            result = processor.process(command)
            if result.output:
                self._append_output(result.output.rstrip())
            if index < len(commands) - 1:
                self._append_output("")
            if result.should_exit:
                break

        self.simulation_runtime = processor.runtime
        self._sync_cycle_count_from_runtime()

    def _execute_input_once(self):
        self._execute_repl_commands(self._input_text() or "cycle")

    def _execute_single_cycle(self):
        """执行单个周期"""
        try:
            self._execute_input_once()
        except Exception as e:
            self._append_output(f"执行输入时发生错误: {str(e)}")
            if self.is_running:
                self._on_pause()

    def _on_single_cycle(self):
        """单步执行按钮点击"""
        self._execute_single_cycle()

    def _on_run_continuous(self):
        """连续执行按钮点击"""
        if not self.simulation_runtime:
            QtWidgets.QMessageBox.warning(self, "警告", "仿真运行时未初始化")
            return

        if self._input_text():
            self._append_output(">>> 执行 REPL 命令序列...")
            self._append_output("")
            self._execute_single_cycle()
            return

        self.is_running = True
        self._append_output(">>> 开始连续执行...")
        self._append_output("")

        # 更新按钮状态
        self.button_single_cycle.setEnabled(False)
        self.button_run_continuous.setEnabled(False)
        self.button_pause.setEnabled(True)
        self.button_reset.setEnabled(False)

        # 启动定时器
        self.timer.start(self.timer_interval)

    def _on_pause(self):
        """暂停按钮点击"""
        self.is_running = False
        self.timer.stop()

        self._append_output(">>> 已暂停执行")
        self._append_output("")

        # 更新按钮状态
        self.button_single_cycle.setEnabled(True)
        self.button_run_continuous.setEnabled(True)
        self.button_pause.setEnabled(False)
        self.button_reset.setEnabled(True)

    def _on_reset(self):
        """重置按钮点击"""
        # 停止定时器
        if self.is_running:
            self._on_pause()

        # 重置周期计数
        self.cycle_count = 0
        self._update_cycle_count()

        # 清空输出
        self.text_simulation_output.clear()

        # 重新初始化模型
        self._init_model()

        self._append_output(">>> 仿真已重置")
        self._append_output("")

    def _on_speed_changed(self, value):
        """速度滑块值变化"""
        self._update_speed_label()

        # 如果正在运行，更新定时器间隔
        if self.is_running:
            self.timer.setInterval(self.timer_interval)

    def closeEvent(self, event):
        """关闭事件"""
        # 停止定时器
        if self.is_running:
            self.timer.stop()

        event.accept()
