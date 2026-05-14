import os
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Optional, Sequence, Union

from PyQt5.QtCore import QProcess, Qt
from PyQt5.QtGui import QPainter, QPixmap
from PyQt5.QtWidgets import (
    QDialog,
    QFileDialog,
    QGraphicsPixmapItem,
    QGraphicsScene,
    QGraphicsView,
    QHBoxLayout,
    QLabel,
    QMenu,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)
from pyfcstm.model.plantuml import PlantUMLOptions

from app.ui import UIDialogShowGraph
from app.utils.text_overflow import apply_text_overflow_handling, refresh_text_overflow
from app.utils.show_state_graph import ShowStateGraph
from ..model import StateManager


class CustomGraphicsView(QGraphicsView):
    def wheelEvent(self, event):
        zoom_in_factor = 1.25
        zoom_out_factor = 1 / zoom_in_factor
        old_pos = self.mapToScene(event.pos())
        factor = zoom_in_factor if event.angleDelta().y() > 0 else zoom_out_factor
        self.scale(factor, factor)
        new_pos = self.mapToScene(event.pos())
        delta = new_pos - old_pos
        self.translate(delta.x(), delta.y())


class PlantumlTaskDialog(QDialog):
    def __init__(self, parent, message: str):
        super().__init__(parent)
        self.setWindowTitle("请等待")
        self.setWindowModality(Qt.ApplicationModal)
        self.setFixedSize(360, 130)
        self.process = QProcess(self)
        self.canceled = False
        self.exit_requested = False
        self.stderr_text = ""

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(message))
        button_layout = QHBoxLayout()
        self.button_cancel = QPushButton("中止")
        self.button_exit = QPushButton("中止并退出")
        button_layout.addStretch(1)
        button_layout.addWidget(self.button_cancel)
        button_layout.addWidget(self.button_exit)
        layout.addLayout(button_layout)

        self.button_cancel.clicked.connect(self.cancel)
        self.button_exit.clicked.connect(self.cancel_and_exit)
        self.process.finished.connect(self._on_finished)
        self.process.errorOccurred.connect(self._on_error)
        apply_text_overflow_handling(self)

    def start(self, program: str, arguments: Sequence[str]):
        self.process.start(program, list(arguments))

    def cancel(self):
        self.canceled = True
        if self.process.state() != QProcess.NotRunning:
            self.process.kill()
        else:
            self.reject()

    def cancel_and_exit(self):
        self.exit_requested = True
        self.cancel()

    def closeEvent(self, event):
        if self.process.state() != QProcess.NotRunning:
            self.cancel()
        event.accept()

    def _on_error(self, _error):
        self.stderr_text = self.process.errorString()
        if not self.canceled:
            self.reject()

    def _on_finished(self, exit_code, exit_status):
        stderr = bytes(self.process.readAllStandardError()).decode("utf-8", errors="replace").strip()
        if stderr:
            self.stderr_text = stderr
        if self.canceled:
            self.reject()
        elif exit_status == QProcess.NormalExit and exit_code == 0:
            self.accept()
        else:
            self.reject()


class DialogShowGraph(QDialog, UIDialogShowGraph):
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
        self.state_manager = current_state_manager if current_state_manager in self.state_managers else (
            self.state_managers[0] if self.state_managers else None
        )
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)
        self.temp_png_path = os.path.join(tempfile.gettempdir(), "temp_state_graph.png")
        self._last_plantuml_code = ""
        self._last_preview_options_key = None
        self._syncing_graph_options = False

        self.graphics_view_show_graph = CustomGraphicsView()
        layout = QVBoxLayout(self.widget_graph_container)
        layout.setContentsMargins(0, 0, 0, 0)
        self.label_graph_hint = QLabel("滚轮缩放，按住左键拖动画布；右键可保存当前 PNG 图片。")
        self.label_graph_hint.setStyleSheet("color: #64748b; padding: 2px 0;")
        layout.addWidget(self.label_graph_hint)
        layout.addWidget(self.graphics_view_show_graph)

        self.button_export_graph.clicked.connect(self.export_graph)
        self.button_generate_graph.clicked.connect(self.show_state_graph)
        self.button_reset_graph_options.clicked.connect(self._reset_graph_options)
        self.combo_detail_level.currentIndexChanged.connect(self._on_detail_level_changed)
        self._populate_model_list()
        self.combo_state_machine.currentIndexChanged.connect(self._on_model_changed)

        self.graphics_view_show_graph.setDragMode(QGraphicsView.ScrollHandDrag)
        self.graphics_view_show_graph.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.graphics_view_show_graph.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.graphics_view_show_graph.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self.graphics_view_show_graph.setResizeAnchor(QGraphicsView.AnchorUnderMouse)
        self.graphics_view_show_graph.setViewportUpdateMode(QGraphicsView.FullViewportUpdate)
        self._install_graph_context_menu()
        self.splitter_graph.setSizes([820, 280])

        self.show_state_graph()

    def _install_graph_context_menu(self):
        hint = self.label_graph_hint.text()
        self.graphics_view_show_graph.setToolTip(hint)
        self.graphics_view_show_graph.viewport().setToolTip(hint)
        self.graphics_view_show_graph.viewport().setContextMenuPolicy(Qt.CustomContextMenu)
        self.graphics_view_show_graph.viewport().customContextMenuRequested.connect(
            self._show_graph_context_menu
        )

    def _has_preview_png(self) -> bool:
        scene = self.graphics_view_show_graph.scene()
        return (
            self.state_manager is not None
            and self._last_preview_options_key is not None
            and scene is not None
            and bool(scene.items())
            and os.path.exists(self.temp_png_path)
            and os.path.getsize(self.temp_png_path) > 0
        )

    def _show_graph_context_menu(self, pos):
        menu = QMenu(self)
        save_action = menu.addAction("保存当前图片为 PNG...")
        save_action.setEnabled(self._has_preview_png())
        menu.addAction("导出其他格式...").triggered.connect(self.export_graph)
        if not save_action.isEnabled():
            empty_action = menu.addAction("暂无可保存的预览图")
            empty_action.setEnabled(False)
        selected = menu.exec_(self.graphics_view_show_graph.viewport().mapToGlobal(pos))
        if selected == save_action:
            self._save_preview_png()

    def _save_preview_png(self):
        if not self._has_preview_png():
            QMessageBox.information(self, "没有预览图", "请先生成状态图。")
            return
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "保存当前状态图 PNG",
            "./state_graph.png",
            "PNG Files (*.png);;All Files (*)",
        )
        if not file_path:
            return
        if not file_path.lower().endswith(".png"):
            file_path += ".png"
        shutil.copy2(self.temp_png_path, file_path)

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

    def _on_model_changed(self, index):
        state_manager = self.combo_state_machine.itemData(index)
        if state_manager is None or state_manager is self.state_manager:
            return
        self.state_manager = state_manager
        self._last_preview_options_key = None
        self.show_state_graph()

    def _csv_tuple(self, text: str):
        return tuple(item.strip() for item in text.split(",") if item.strip())

    def _custom_colors(self):
        colors = {}
        for line in self.text_custom_colors.toPlainText().splitlines():
            line = line.strip()
            if not line or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip()
            if key and value:
                colors[key] = value
        return colors or None

    def _build_options(self) -> PlantUMLOptions:
        max_action_lines = self.spin_max_action_lines.value()
        max_depth = self.spin_max_depth.value()
        return PlantUMLOptions(
            detail_level=self.combo_detail_level.currentText(),
            show_variable_definitions=self.check_show_variable_definitions.isChecked(),
            variable_display_mode=self.combo_variable_display_mode.currentText(),
            variable_legend_position=self.combo_variable_legend_position.currentText(),
            state_name_format=self._csv_tuple(self.edit_state_name_format.text()) or ("extra_name",),
            show_pseudo_state_style=self.check_show_pseudo_state_style.isChecked(),
            collapse_empty_states=self.check_collapse_empty_states.isChecked(),
            show_lifecycle_actions=self.check_show_lifecycle_actions.isChecked(),
            show_enter_actions=self.check_show_enter_actions.isChecked(),
            show_during_actions=self.check_show_during_actions.isChecked(),
            show_exit_actions=self.check_show_exit_actions.isChecked(),
            show_aspect_actions=self.check_show_aspect_actions.isChecked(),
            show_abstract_actions=self.check_show_abstract_actions.isChecked(),
            show_concrete_actions=self.check_show_concrete_actions.isChecked(),
            abstract_action_marker=self.combo_abstract_action_marker.currentText(),
            max_action_lines=max_action_lines if max_action_lines > 0 else None,
            show_transition_guards=self.check_show_transition_guards.isChecked(),
            show_transition_effects=self.check_show_transition_effects.isChecked(),
            transition_effect_mode=self.combo_transition_effect_mode.currentText(),
            show_events=self.check_show_events.isChecked(),
            event_name_format=self._csv_tuple(self.edit_event_name_format.text()) or ("extra_name", "relpath"),
            event_visualization_mode=self.combo_event_visualization_mode.currentText(),
            event_legend_position=self.combo_event_legend_position.currentText(),
            max_depth=max_depth if max_depth >= 0 else None,
            collapsed_state_marker=self.edit_collapsed_state_marker.text() or "...",
            use_skinparam=self.check_use_skinparam.isChecked(),
            use_stereotypes=self.check_use_stereotypes.isChecked(),
            custom_colors=self._custom_colors(),
        )

    def _set_checked(self, checkbox, value):
        checkbox.setChecked(bool(value))

    def _on_detail_level_changed(self, _index):
        if self._syncing_graph_options:
            return
        self._apply_detail_level_preset(self.combo_detail_level.currentText())

    def _apply_detail_level_preset(self, detail_level: str):
        config = PlantUMLOptions(detail_level=detail_level).to_config()
        self._syncing_graph_options = True
        try:
            self._set_checked(self.check_show_variable_definitions, config.show_variable_definitions)
            self.combo_variable_display_mode.setCurrentText(config.variable_display_mode)
            self.combo_variable_legend_position.setCurrentText(config.variable_legend_position)
            self.edit_state_name_format.setText(",".join(config.state_name_format))
            self._set_checked(self.check_show_pseudo_state_style, config.show_pseudo_state_style)
            self._set_checked(self.check_collapse_empty_states, config.collapse_empty_states)
            self._set_checked(self.check_show_lifecycle_actions, config.show_lifecycle_actions)
            self._set_checked(self.check_show_enter_actions, config.show_enter_actions)
            self._set_checked(self.check_show_during_actions, config.show_during_actions)
            self._set_checked(self.check_show_exit_actions, config.show_exit_actions)
            self._set_checked(self.check_show_aspect_actions, config.show_aspect_actions)
            self._set_checked(self.check_show_abstract_actions, config.show_abstract_actions)
            self._set_checked(self.check_show_concrete_actions, config.show_concrete_actions)
            self.combo_abstract_action_marker.setCurrentText(config.abstract_action_marker)
            self.spin_max_action_lines.setValue(config.max_action_lines or 0)
            self._set_checked(self.check_show_transition_guards, config.show_transition_guards)
            self._set_checked(self.check_show_transition_effects, config.show_transition_effects)
            self.combo_transition_effect_mode.setCurrentText(config.transition_effect_mode)
            self._set_checked(self.check_show_events, config.show_events)
            self.edit_event_name_format.setText(",".join(config.event_name_format))
            self.combo_event_visualization_mode.setCurrentText(config.event_visualization_mode)
            self.combo_event_legend_position.setCurrentText(config.event_legend_position)
            self.spin_max_depth.setValue(config.max_depth if config.max_depth is not None else -1)
            self.edit_collapsed_state_marker.setText(config.collapsed_state_marker)
            self._set_checked(self.check_use_skinparam, config.use_skinparam)
            self._set_checked(self.check_use_stereotypes, config.use_stereotypes)
        finally:
            self._syncing_graph_options = False

    def _options_key(self, options: PlantUMLOptions):
        return repr(options)

    def _write_temp_puml(self, plantuml_code: str) -> str:
        fd, path = tempfile.mkstemp(prefix="fcstm_graph_", suffix=".puml")
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(plantuml_code)
        return path

    def _run_render_task(self, plantuml_code: str, output_file: str, output_format: str, message: str):
        puml_path = self._write_temp_puml(plantuml_code)
        progress = PlantumlTaskDialog(self, message)
        # The PyInstaller bootloader does not implement ``-m foo.bar``, so
        # ``sys.executable -m app.utils.plantuml_render_cli`` would re-launch
        # the whole GUI inside the subprocess.  When frozen, dispatch via a
        # dedicated flag handled in ``main.py`` instead.
        if getattr(sys, "frozen", False):
            args = [
                "--plantuml-render-cli",
                "--input",
                puml_path,
                "--output",
                output_file,
                "--format",
                output_format,
            ]
        else:
            args = [
                "-m",
                "app.utils.plantuml_render_cli",
                "--input",
                puml_path,
                "--output",
                output_file,
                "--format",
                output_format,
            ]
        progress.start(sys.executable, args)
        result = progress.exec_()
        try:
            os.remove(puml_path)
        except OSError:
            pass
        if progress.exit_requested:
            self.close()
            return False
        if result != QDialog.Accepted:
            if not progress.canceled:
                QMessageBox.critical(
                    self,
                    "状态图生成失败",
                    progress.stderr_text or "PlantUML 后端未能生成目标文件。",
                )
            return False
        return True

    def _load_preview_image(self):
        pixmap = QPixmap(self.temp_png_path)
        if pixmap.isNull():
            QMessageBox.critical(self, "状态图生成失败", "未能读取生成的 PNG 图像。")
            return
        scene = QGraphicsScene()
        scaled_pixmap = pixmap.scaled(
            pixmap.width() * 2,
            pixmap.height() * 2,
            Qt.KeepAspectRatio,
            Qt.SmoothTransformation,
        )
        item = QGraphicsPixmapItem(scaled_pixmap)
        scene.addItem(item)
        self.graphics_view_show_graph.setScene(scene)
        self.graphics_view_show_graph.setRenderHint(QPainter.Antialiasing)
        self.graphics_view_show_graph.setRenderHint(QPainter.SmoothPixmapTransform)
        self.graphics_view_show_graph.setRenderHint(QPainter.TextAntialiasing)
        self.graphics_view_show_graph.fitInView(scene.sceneRect(), Qt.KeepAspectRatio)

    def _reset_graph_options(self):
        self._syncing_graph_options = True
        self.combo_detail_level.setCurrentText("normal")
        self._syncing_graph_options = False
        self._apply_detail_level_preset("normal")
        self.text_custom_colors.clear()
        self.show_state_graph()

    def show_state_graph(self):
        if self.state_manager is None:
            return
        options = self._build_options()
        options_key = self._options_key(options)
        if (
            self._last_preview_options_key == options_key
            and os.path.exists(self.temp_png_path)
            and os.path.getsize(self.temp_png_path) > 0
        ):
            self._load_preview_image()
            return

        try:
            plantuml_code = ShowStateGraph.build_plantuml_code(self.state_manager, options)
        except Exception as err:
            QMessageBox.critical(self, "状态图生成失败", str(err))
            return

        if self._run_render_task(
            plantuml_code,
            self.temp_png_path,
            "png",
            "正在生成状态图，请等待...",
        ):
            self._last_plantuml_code = plantuml_code
            self._last_preview_options_key = options_key
            self._load_preview_image()

    def export_graph(self):
        if self.state_manager is None:
            return
        selected_format = self.combo_export_format.currentText().lower()
        suffix = "puml" if selected_format == "puml" else selected_format
        filters = {
            "png": "PNG Files (*.png)",
            "svg": "SVG Files (*.svg)",
            "pdf": "PDF Files (*.pdf)",
            "puml": "PlantUML Files (*.puml)",
        }
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "导出状态机图",
            "./",
            f"{filters.get(selected_format, 'All Files (*)')};;All Files (*)",
        )
        if not file_path:
            return
        if not file_path.lower().endswith(f".{suffix}"):
            file_path += f".{suffix}"

        options = self._build_options()
        try:
            plantuml_code = ShowStateGraph.build_plantuml_code(self.state_manager, options)
        except Exception as err:
            QMessageBox.critical(self, "状态图导出失败", str(err))
            return

        if selected_format == "puml":
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(plantuml_code)
            return

        if (
            selected_format == "png"
            and self._last_plantuml_code == plantuml_code
            and os.path.exists(self.temp_png_path)
            and os.path.getsize(self.temp_png_path) > 0
        ):
            shutil.copy2(self.temp_png_path, file_path)
            return

        self._run_render_task(
            plantuml_code,
            file_path,
            selected_format,
            "正在保存状态图，请等待...",
        )

    def closeEvent(self, event):
        if os.path.exists(self.temp_png_path):
            try:
                os.remove(self.temp_png_path)
            except OSError:
                pass
        super().closeEvent(event)
