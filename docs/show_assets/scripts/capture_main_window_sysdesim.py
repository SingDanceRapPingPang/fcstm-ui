"""Capture the main window after importing 单个用例_v2.xml so the demo
guide can illustrate that the left panel groups SysDeSim-converted
models by their source XML, instead of (incorrectly) implying a "source"
column on each row.

Run from the repo root::

    FCSTM_DEMO_V2_XML=/path/to/单个用例_v2.xml \
    QT_QPA_PLATFORM=offscreen \
    venv37/bin/python docs/show_assets/scripts/capture_main_window_sysdesim.py

Produces two PNGs under ``docs/show_assets/gui/``:

  - ``12-main-window-after-sysdesim-import.png``  full main window
  - ``12-left-panel-after-sysdesim-import.png``   the left tree, cropped
"""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

from PyQt5 import QtCore, QtGui, QtWidgets

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from app.utils.dsl_to_ui import dsl_to_state_manager  # noqa: E402
from app.utils.xml_converter import convert_xml_to_fcstm  # noqa: E402
from app.widget.main_window import AppMainWindow  # noqa: E402

XML_V2 = Path(
    os.environ.get(
        "FCSTM_DEMO_V2_XML",
        str(REPO_ROOT / "单个用例_v2.xml"),
    )
).expanduser().resolve()
OUT_DIR = REPO_ROOT / "docs" / "show_assets" / "gui"
OUT_DIR.mkdir(parents=True, exist_ok=True)


def pump(app: QtWidgets.QApplication, ms: int = 300) -> None:
    end = QtCore.QElapsedTimer()
    end.start()
    while end.elapsed() < ms:
        app.processEvents(QtCore.QEventLoop.AllEvents, 25)


def grab(widget: QtWidgets.QWidget, path: Path) -> None:
    pixmap = widget.grab()
    path.parent.mkdir(parents=True, exist_ok=True)
    pixmap.save(str(path), "PNG")
    print(f"  saved {path.relative_to(REPO_ROOT)}  {pixmap.width()}x{pixmap.height()}")


def import_xml_silently(window: AppMainWindow, xml_path: Path) -> None:
    """Replay the body of AppMainWindow._import_xml_file without the dialogs."""
    output_dir = tempfile.mkdtemp(prefix="fcstm_demo_v2_")
    generated_files, error, _report = convert_xml_to_fcstm(
        str(xml_path), output_dir
    )
    if error:
        print(f"  conversion warning: {error}")
    for index, fcstm_file in enumerate(generated_files):
        manager = dsl_to_state_manager(fcstm_file)
        manager.origin_file_path = str(xml_path)
        window._add_state_manager(
            manager,
            display_name=Path(fcstm_file).stem,
            source_path=fcstm_file,
            set_current=index == 0,
        )


def main() -> int:
    if not XML_V2.exists():
        print(f"missing XML: {XML_V2}")
        return 2

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication(sys.argv)
    window = AppMainWindow()
    window.resize(1280, 800)
    window.show()
    pump(app, 400)

    import_xml_silently(window, XML_V2)
    pump(app, 600)

    grab(window, OUT_DIR / "12-main-window-after-sysdesim-import.png")

    tree = window.tree_state_machine_files
    tree.expandAll()
    pump(app, 200)

    # Crop the left panel: take the panel that holds the tree.
    panel = tree.parentWidget()
    while panel is not None and panel.parentWidget() is not None and panel.width() == window.width():
        panel = panel.parentWidget()
    if panel is None:
        panel = tree
    grab(panel, OUT_DIR / "12-left-panel-after-sysdesim-import.png")

    window.close()
    pump(app, 100)
    return 0


if __name__ == "__main__":
    sys.exit(main())
