"""Offscreen GUI capture driver for the demo guide.

Run from the repo root with::

    FCSTM_DEMO_XML_DIR=/path/to/dir/with/sysdesim/xmls \
    QT_QPA_PLATFORM=offscreen \
    venv37/bin/python docs/show_assets/scripts/capture_gui.py

``FCSTM_DEMO_XML_DIR`` must point at a directory containing
``单个用例_v2.xml`` and ``单个用例_v2_z1200_experiment.xml``.  Defaults
to the current working directory, so dropping the XMLs next to the
repo root before invocation also works.

Produces PNG screenshots under ``docs/show_assets/gui/``.
"""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path
from typing import Optional

from PyQt5 import QtCore, QtGui, QtWidgets

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from app.utils.dsl_to_ui import (  # noqa: E402
    convert_state_machine_to_state_manager,
    dsl_to_state_manager,
)
from app.utils.show_state_graph import ShowStateGraph  # noqa: E402
from app.utils.xml_converter import convert_xml_to_fcstm  # noqa: E402
from app.widget.dialog_show_graph import DialogShowGraph  # noqa: E402
from app.widget.dialog_sysdesim_validate import DialogSysdesimValidate  # noqa: E402
from app.widget.dialog_topology_verify import DialogTopologyVerify  # noqa: E402
from app.widget.main_window import AppMainWindow  # noqa: E402
from pyfcstm.dsl import parse_with_grammar_entry  # noqa: E402

TOPOLOGY_DSL = REPO_ROOT / "docs" / "topology_controller_all_in_one.fcstm"
XML_DIR = Path(os.environ.get("FCSTM_DEMO_XML_DIR", ".")).expanduser().resolve()
XML_V2 = XML_DIR / "单个用例_v2.xml"
XML_Z1200 = XML_DIR / "单个用例_v2_z1200_experiment.xml"

OUT_DIR = REPO_ROOT / "docs" / "show_assets" / "gui"
OUT_DIR.mkdir(parents=True, exist_ok=True)


def pump(app: QtWidgets.QApplication, ms: int = 250) -> None:
    end = QtCore.QElapsedTimer()
    end.start()
    while end.elapsed() < ms:
        app.processEvents(QtCore.QEventLoop.AllEvents, 25)


def grab(widget: QtWidgets.QWidget, path: Path) -> None:
    pixmap = widget.grab()
    path.parent.mkdir(parents=True, exist_ok=True)
    pixmap.save(str(path), "PNG")
    print(f"  saved {path.relative_to(REPO_ROOT)}  {pixmap.width()}x{pixmap.height()}")


def load_topology_manager():
    return dsl_to_state_manager(str(TOPOLOGY_DSL))


def topology_run(dialog: DialogTopologyVerify, check_key: str, target: Optional[str], source: Optional[str], use_default_source: bool) -> None:
    idx = dialog.combo_check.findData(check_key)
    dialog.combo_check.setCurrentIndex(idx)
    dialog.check_default_source.setChecked(use_default_source)
    if not use_default_source and source is not None:
        dialog._select_combo_path(dialog.combo_source_state, source)
    if target is not None:
        dialog._select_combo_path(dialog.combo_target_state, target)
    dialog._run_check()


def capture_topology(app: QtWidgets.QApplication) -> None:
    print("[topology] capturing dialog scenarios")
    state_manager = load_topology_manager()
    state_manager.display_name = "controller_all_in_one"

    scenarios = [
        dict(name="03-topology-reach-ok",      check="reachability",  target="Controller.Shutdown.PowerOff", source=None, default=True),
        dict(name="04-topology-reach-fail",    check="reachability",  target="Controller.Startup.PowerOn",   source="Controller.Shutdown.PowerOff", default=False),
        dict(name="05-topology-finite-ok",     check="finiteness",    target=None, source="Controller.Shutdown.Save", default=False),
        dict(name="06-topology-finite-fail",   check="finiteness",    target=None, source=None, default=True),
        dict(name="07-topology-inevitable-ok", check="inevitability", target="Controller.Shutdown.PowerOff", source="Controller.Shutdown.Save", default=False),
        dict(name="08-topology-inevitable-fail", check="inevitability", target="Controller.Shutdown.Save", source=None, default=True),
    ]
    for sc in scenarios:
        dialog = DialogTopologyVerify(None, [state_manager], state_manager)
        dialog.resize(1100, 760)
        dialog.show()
        pump(app)
        topology_run(dialog, sc["check"], sc["target"], sc["source"], sc["default"])
        pump(app, 600)
        grab(dialog, OUT_DIR / (sc["name"] + "-report.png"))
        dialog.tabs_result.setCurrentIndex(1)
        pump(app, 300)
        grab(dialog, OUT_DIR / (sc["name"] + "-table.png"))
        dialog.tabs_result.setCurrentIndex(2)
        pump(app, 400)
        grab(dialog, OUT_DIR / (sc["name"] + "-diagram.png"))
        dialog.close()
        pump(app, 100)


def convert_xml(xml_path: Path) -> list:
    output_dir = tempfile.mkdtemp(prefix="fcstm_demo_")
    files, error, _ = convert_xml_to_fcstm(str(xml_path), output_dir)
    if error:
        print(f"  conversion warning ({xml_path.name}): {error}")
    managers = []
    for fp in files:
        mgr = dsl_to_state_manager(fp)
        mgr.origin_file_path = str(xml_path)
        mgr.display_name = Path(fp).stem
        managers.append(mgr)
    return managers


def capture_sysdesim(app: QtWidgets.QApplication, xml_path: Path, slug: str, set_query: bool) -> None:
    print(f"[sysdesim] {slug} ({xml_path.name})")
    managers = convert_xml(xml_path)
    if not managers:
        print(f"  ! no managers produced from {xml_path}")
        return
    dialog = DialogSysdesimValidate(None, managers)
    dialog.resize(1100, 820)
    dialog.show()
    pump(app)

    interaction_index = dialog.combo_interaction_name.findText("测试用例1")
    if interaction_index < 0:
        interaction_index = 0
    dialog.combo_interaction_name.setCurrentIndex(interaction_index)

    if set_query:
        left_idx = dialog.combo_left_machine.findText("StateMachine__Control_region2")
        if left_idx >= 0:
            dialog.combo_left_machine.setCurrentIndex(left_idx)
        right_idx = dialog.combo_right_machine.findText("StateMachine__Control_region3")
        if right_idx >= 0:
            dialog.combo_right_machine.setCurrentIndex(right_idx)
        pump(app, 200)
        dialog.combo_left_state.setEditText("StateMachine.Control.H.M")
        dialog.combo_right_state.setEditText("StateMachine.Control.X")
        dialog.check_enable_query.setChecked(True)
    else:
        dialog.check_enable_query.setChecked(False)

    dialog._run_validate()
    pump(app, 800)

    grab(dialog, OUT_DIR / f"{slug}-report.png")
    dialog.tabs_result.setCurrentIndex(1)
    pump(app, 250)
    grab(dialog, OUT_DIR / f"{slug}-witness.png")
    # Scroll to "start" row when present so the climactic coexistence point lands on screen.
    table = dialog.table_witness
    start_row = -1
    last_col = table.columnCount() - 1
    if last_col >= 0:
        for row in range(table.rowCount()):
            item = table.item(row, last_col)
            if item is not None and item.text() == "start":
                start_row = row
                break
    if start_row >= 0:
        target_item = table.item(max(start_row - 2, 0), 0)
        if target_item is not None:
            table.scrollToItem(target_item, QtWidgets.QAbstractItemView.PositionAtTop)
        pump(app, 250)
        grab(dialog, OUT_DIR / f"{slug}-witness-start.png")
    dialog.tabs_result.setCurrentIndex(2)
    pump(app, 250)
    grab(dialog, OUT_DIR / f"{slug}-diagnostics.png")
    dialog.tabs_result.setCurrentIndex(3)
    pump(app, 350)
    grab(dialog, OUT_DIR / f"{slug}-diagram.png")
    dialog.close()
    pump(app, 100)


def capture_state_graph(app: QtWidgets.QApplication) -> None:
    print("[state-graph] rendering all-in-one state graph PNG via PlantUML")
    state_manager = load_topology_manager()
    target_png = OUT_DIR / "02-state-graph.png"
    ShowStateGraph.dump_state_graph(state_manager, str(target_png), output_format="png")
    print(f"  saved {target_png.relative_to(REPO_ROOT)}  bytes={target_png.stat().st_size}")


def capture_main_window(app: QtWidgets.QApplication) -> None:
    print("[main-window] capturing main window with sample model")
    window = AppMainWindow()
    window.resize(1280, 800)
    window.show()
    pump(app)
    try:
        window._import_fcstm_file(str(TOPOLOGY_DSL), show_message=False)
    except Exception as exc:  # pragma: no cover - tolerant
        print(f"  ! _import_fcstm_file failed: {exc!r}")
    pump(app, 800)
    grab(window, OUT_DIR / "01-main-window.png")
    window.close()
    pump(app, 200)


def main() -> int:
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication(sys.argv)
    capture_main_window(app)
    capture_state_graph(app)
    capture_topology(app)
    capture_sysdesim(app, XML_V2, "09-sysdesim-v2-hm-vs-x", set_query=True)
    capture_sysdesim(app, XML_Z1200, "10-sysdesim-z1200-blocked", set_query=True)
    print("done")
    return 0


if __name__ == "__main__":
    sys.exit(main())
