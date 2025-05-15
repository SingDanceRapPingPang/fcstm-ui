import pytest
from PyQt5 import QtWidgets
import os

from app.widget import AppMainWindow


@pytest.mark.unittest
class TestMainWindow:
    @pytest.fixture
    def main_window(self, qtbot):
        window = AppMainWindow()
        qtbot.addWidget(window)
        return qtbot, window

    @pytest.fixture
    def new_state_chart(self, main_window):
        qtbot, window = main_window

        # 点击“新建状态机”按钮
        qtbot.mouseClick(window.button_initial_new_state_machine, qtbot.QtCore.Qt.LeftButton)

        # 等待对话框弹出
        dialogs = window.findChildren(QtWidgets.QDialog)  # 或使用具体方式定位新建 FSM 的对话框
        assert dialogs, "未弹出新建状态机对话框"

        fsm_dialog = dialogs[0]

        # 输入状态机名称
        name_input = fsm_dialog.findChild(QtWidgets.QLineEdit, "name_edit")
        assert name_input, "找不到名称输入框"

        qtbot.keyClicks(name_input, "TestFSM")
        qtbot.wait(100)

        # 点击 OK
        ok_button = fsm_dialog.findChild(QtWidgets.QPushButton, "ok_button")
        assert ok_button, "找不到 OK 按钮"
        qtbot.mouseClick(ok_button, qtbot.QtCore.Qt.LeftButton)

        # 验证是否已进入主状态机编辑界面
        assert window.stackedWidget_state_machine.currentIndex() == 1

        return qtbot, window

    def test_statechart_name(self, new_state_chart):

    def test_import_statechart(self, monkeypatch, main_window, tmp_path):
        qtbot, window = main_window
        json_file = "../ui/ui/export_data/test_json.json"
        json_file = "../../app/ui/ui/export_data/test_json.json"
        monkeypatch.setattr(
            QtWidgets.QFileDialog,
            "getOpenFileName",
            lambda *args, **kwargs: (str(json_file), "JSON Files (*.json)")
        )

        window._import_statechart()

        assert window.state_chart is not None
        assert window.state_chart.name == "1234"
        assert "".join(window.state_chart.preamble) == ""
        assert window.state_chart.root_state.name == "start2"

