"""Offscreen capture driver for expert_test_procedure.md screenshots.

Adds three captures not produced by capture_gui.py:

  13-state-graph-dialog.png            DialogShowGraph for T-01
  14-sysdesim-convert-options.png      Conversion options modal for T-05
  15-sysdesim-region1-a-vs-e-*.png     Phase11 UNSAT scenario (4 tabs) for T-06

Invoke from repo root:

    FCSTM_DEMO_XML_DIR=/path/to/xml/dir \
    QT_QPA_PLATFORM=offscreen \
    venv37/bin/python docs/show_assets/scripts/capture_expert_extras.py
"""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

from PyQt5 import QtCore, QtWidgets

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from app.utils.dsl_to_ui import dsl_to_state_manager  # noqa: E402
from app.utils.xml_converter import convert_xml_to_fcstm  # noqa: E402
from app.widget.dialog_show_graph import DialogShowGraph  # noqa: E402
from app.widget.dialog_sysdesim_validate import DialogSysdesimValidate  # noqa: E402

TOPOLOGY_DSL = REPO_ROOT / "docs" / "topology_controller_all_in_one.fcstm"
XML_DIR = Path(os.environ.get("FCSTM_DEMO_XML_DIR", ".")).expanduser().resolve()
XML_V2 = XML_DIR / "单个用例_v2.xml"

OUT_DIR = REPO_ROOT / "docs" / "show_assets" / "gui"
OUT_DIR.mkdir(parents=True, exist_ok=True)


def pump(app, ms=300):
    timer = QtCore.QElapsedTimer()
    timer.start()
    while timer.elapsed() < ms:
        app.processEvents(QtCore.QEventLoop.AllEvents, 25)


def grab(widget, path: Path):
    pixmap = widget.grab()
    path.parent.mkdir(parents=True, exist_ok=True)
    pixmap.save(str(path), "PNG")
    print(f"  saved {path.relative_to(REPO_ROOT)}  {pixmap.width()}x{pixmap.height()}")


def capture_state_graph_dialog(app):
    print("[T-01] DialogShowGraph for state graph")
    state_manager = dsl_to_state_manager(str(TOPOLOGY_DSL))
    state_manager.display_name = "topology_controller_all_in_one"
    dialog = DialogShowGraph(None, [state_manager], state_manager)
    dialog.resize(1280, 820)
    dialog.show()
    # Wait for PlantUML subprocess (Java) to finish; the dialog renders async.
    for _ in range(40):
        pump(app, 250)
        if dialog._has_preview_png():
            break
    pump(app, 400)
    grab(dialog, OUT_DIR / "13-state-graph-dialog.png")
    dialog.close()
    pump(app, 100)


def capture_convert_options(app):
    print("[T-05] SysDeSim 转换选项 dialog")
    dialog = QtWidgets.QDialog()
    dialog.setWindowTitle("SysDeSim 转换选项")
    dialog.setMinimumWidth(640)
    dialog.resize(680, 240)
    layout = QtWidgets.QVBoxLayout(dialog)
    form = QtWidgets.QFormLayout()
    edit_machine_name = QtWidgets.QLineEdit()
    edit_machine_id = QtWidgets.QLineEdit()
    spin_tick = QtWidgets.QDoubleSpinBox()
    spin_tick.setDecimals(3)
    spin_tick.setRange(0, 1_000_000)
    spin_tick.setSpecialValueText("自动")
    spin_tick.setValue(0)
    check_report = QtWidgets.QCheckBox("生成 SysDeSim 转换诊断报告")
    form.addRow("状态机名：", edit_machine_name)
    form.addRow("状态机ID：", edit_machine_id)
    form.addRow("tick(ms)：", spin_tick)
    form.addRow("", check_report)
    layout.addLayout(form)
    note = QtWidgets.QLabel(
        "状态机名/ID 留空时使用 pyfcstm 默认选择。\n"
        "tick 为自动时不传 --tick-duration-ms。"
    )
    layout.addWidget(note)
    button_box = QtWidgets.QDialogButtonBox(
        QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel
    )
    layout.addWidget(button_box)
    dialog.show()
    pump(app, 400)
    grab(dialog, OUT_DIR / "14-sysdesim-convert-options.png")
    dialog.close()
    pump(app, 100)


def capture_sysdesim_unsat(app):
    print("[T-06] Phase11 UNSAT (region1.A vs region1.EState)")
    output_dir = tempfile.mkdtemp(prefix="fcstm_expert_")
    files, error, _ = convert_xml_to_fcstm(str(XML_V2), output_dir)
    if error:
        print(f"  conversion warning: {error}")
    managers = []
    for fp in files:
        mgr = dsl_to_state_manager(fp)
        mgr.origin_file_path = str(XML_V2)
        mgr.display_name = Path(fp).stem
        managers.append(mgr)
    dialog = DialogSysdesimValidate(None, managers)
    dialog.resize(1100, 820)
    dialog.show()
    pump(app, 400)

    idx = dialog.combo_interaction_name.findText("测试用例1")
    if idx >= 0:
        dialog.combo_interaction_name.setCurrentIndex(idx)
    pump(app, 200)

    left_idx = dialog.combo_left_machine.findText("StateMachine__Control_region1")
    if left_idx >= 0:
        dialog.combo_left_machine.setCurrentIndex(left_idx)
    right_idx = dialog.combo_right_machine.findText("StateMachine__Control_region1")
    if right_idx >= 0:
        dialog.combo_right_machine.setCurrentIndex(right_idx)
    pump(app, 200)
    dialog.combo_left_state.setEditText("StateMachine.Control.A")
    dialog.combo_right_state.setEditText("StateMachine.Control.EState")
    dialog.check_enable_query.setChecked(True)
    dialog._run_validate()
    pump(app, 1200)

    slug = "15-sysdesim-region1-a-vs-e-unsat"
    grab(dialog, OUT_DIR / f"{slug}-report.png")
    dialog.tabs_result.setCurrentIndex(1)
    pump(app, 300)
    grab(dialog, OUT_DIR / f"{slug}-witness.png")
    dialog.tabs_result.setCurrentIndex(2)
    pump(app, 300)
    grab(dialog, OUT_DIR / f"{slug}-diagnostics.png")
    dialog.tabs_result.setCurrentIndex(3)
    pump(app, 500)
    grab(dialog, OUT_DIR / f"{slug}-diagram.png")
    dialog.close()
    pump(app, 100)


def main() -> int:
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication(sys.argv)
    capture_state_graph_dialog(app)
    capture_convert_options(app)
    capture_sysdesim_unsat(app)
    print("done")
    return 0


if __name__ == "__main__":
    sys.exit(main())
