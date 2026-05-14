"""Capture SysDeSim dialog with 三个用例.xml: shows the 交互名 dropdown open
so the demo guide can illustrate that one XML may carry multiple sequence
diagrams selectable from a single dropdown.

Run from the repo root::

    FCSTM_DEMO_THREE_XML=/path/to/三个用例.xml \
    QT_QPA_PLATFORM=offscreen \
    venv37/bin/python docs/show_assets/scripts/capture_three_cases.py

Produces two PNGs under ``docs/show_assets/gui/``:

  - ``11-sysdesim-three-cases.png``           dialog with the 3-interaction XML loaded
  - ``11-sysdesim-three-cases-dropdown.png``  same dialog with the 交互名 dropdown popped open
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
from app.widget.dialog_sysdesim_validate import DialogSysdesimValidate  # noqa: E402

XML_THREE = Path(
    os.environ.get(
        "FCSTM_DEMO_THREE_XML",
        str(REPO_ROOT / "三个用例.xml"),
    )
).expanduser().resolve()
OUT_DIR = REPO_ROOT / "docs" / "show_assets" / "gui"
OUT_DIR.mkdir(parents=True, exist_ok=True)


def pump(app: QtWidgets.QApplication, ms: int = 300) -> None:
    end = QtCore.QElapsedTimer()
    end.start()
    while end.elapsed() < ms:
        app.processEvents(QtCore.QEventLoop.AllEvents, 25)


def convert_xml(xml_path: Path) -> list:
    output_dir = tempfile.mkdtemp(prefix="fcstm_demo_three_")
    files, error, _ = convert_xml_to_fcstm(str(xml_path), output_dir)
    if error:
        print(f"  conversion warning: {error}")
    managers = []
    for fp in files:
        mgr = dsl_to_state_manager(fp)
        mgr.origin_file_path = str(xml_path)
        mgr.display_name = Path(fp).stem
        managers.append(mgr)
    return managers


def grab_path(widget: QtWidgets.QWidget, path: Path) -> QtGui.QPixmap:
    pixmap = widget.grab()
    path.parent.mkdir(parents=True, exist_ok=True)
    pixmap.save(str(path), "PNG")
    print(f"  saved {path.relative_to(REPO_ROOT)}  {pixmap.width()}x{pixmap.height()}")
    return pixmap


def composite_dropdown(dialog: QtWidgets.QWidget, combo: QtWidgets.QComboBox, app: QtWidgets.QApplication) -> QtGui.QPixmap:
    """Render the dialog with its 交互名 dropdown popped open.

    Strategy: pop the real popup, grab dialog + popup separately, then composite
    the popup onto the dialog at the visual location of the combo.  Falls back to
    drawing a faux dropdown if the offscreen popup grab is degenerate.
    """
    combo.showPopup()
    pump(app, 400)

    base = dialog.grab()
    view = combo.view()
    popup_window = view.window()
    popup_pix = popup_window.grab() if popup_window is not None else QtGui.QPixmap()
    combo.hidePopup()

    composite = QtGui.QPixmap(base.size())
    composite.fill(QtCore.Qt.white)
    painter = QtGui.QPainter(composite)
    painter.drawPixmap(0, 0, base)

    combo_top_left_in_dialog = combo.mapTo(dialog, QtCore.QPoint(0, combo.height()))

    if not popup_pix.isNull() and popup_pix.width() > 4 and popup_pix.height() > 4:
        painter.drawPixmap(combo_top_left_in_dialog, popup_pix)
    else:
        # Fallback: draw a faux dropdown with the same items.
        item_h = max(combo.height() - 2, 22)
        row_count = combo.count()
        list_w = max(combo.width(), 220)
        list_h = item_h * row_count + 4
        rect = QtCore.QRect(combo_top_left_in_dialog.x(), combo_top_left_in_dialog.y(),
                            list_w, list_h)
        painter.fillRect(rect, QtGui.QColor("#ffffff"))
        pen = QtGui.QPen(QtGui.QColor("#3d7eff"))
        pen.setWidth(2)
        painter.setPen(pen)
        painter.drawRect(rect)
        font = combo.font()
        painter.setFont(font)
        for i in range(row_count):
            row_rect = QtCore.QRect(rect.x() + 2, rect.y() + 2 + i * item_h, rect.width() - 4, item_h)
            if i == combo.currentIndex():
                painter.fillRect(row_rect, QtGui.QColor("#e7f0ff"))
            painter.setPen(QtGui.QColor("#000000"))
            painter.drawText(row_rect.adjusted(8, 0, -4, 0), QtCore.Qt.AlignVCenter, combo.itemText(i))

    painter.end()
    return composite


def main() -> int:
    if not XML_THREE.exists():
        print(f"missing XML: {XML_THREE}")
        return 2

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication(sys.argv)

    print(f"[three-cases] converting {XML_THREE.name}")
    managers = convert_xml(XML_THREE)
    if not managers:
        print("  ! no managers produced")
        return 1

    dialog = DialogSysdesimValidate(None, managers)
    dialog.resize(1100, 820)
    dialog.show()
    pump(app, 500)

    # Pre-pick 测试用例1 so the closed combo shows it.
    combo = dialog.combo_interaction_name
    idx = combo.findText("测试用例1")
    if idx >= 0:
        combo.setCurrentIndex(idx)
    pump(app, 200)

    closed_path = OUT_DIR / "11-sysdesim-three-cases.png"
    grab_path(dialog, closed_path)

    print(f"[three-cases] interaction items: {[combo.itemText(i) for i in range(combo.count())]}")

    pix = composite_dropdown(dialog, combo, app)
    open_path = OUT_DIR / "11-sysdesim-three-cases-dropdown.png"
    open_path.parent.mkdir(parents=True, exist_ok=True)
    pix.save(str(open_path), "PNG")
    print(f"  saved {open_path.relative_to(REPO_ROOT)}  {pix.width()}x{pix.height()}")

    dialog.close()
    pump(app, 100)
    return 0


if __name__ == "__main__":
    sys.exit(main())
