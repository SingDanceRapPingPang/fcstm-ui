from pyfcstm.model import (
    State,
    CompositeState,
    Event,
    Transition,
    Statechart
)
from PyQt5.QtWidgets import QMainWindow, QVBoxLayout, QWidget
from PyQt5.QtCore import Qt
from graphviz import Digraph
import tempfile
from PyQt5.QtGui import QPixmap
from PyQt5.QtWidgets import QLabel, QScrollArea


class StateMachineGraphWindow(QMainWindow):
    def __init__(self, state_chart, parent=None):
        super().__init__(parent)
        self.setWindowTitle("状态机图")
        self.resize(800, 600)

        # 创建主窗口部件
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)

        # 创建滚动区域
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        layout.addWidget(scroll_area)

        # 创建标签用于显示图像
        self.image_label = QLabel()
        self.image_label.setAlignment(Qt.AlignCenter)
        scroll_area.setWidget(self.image_label)

        # 生成并显示状态机图
        self.generate_state_machine_graph(state_chart)

    def generate_state_machine_graph(self, state_chart):
        # 创建有向图
        dot = Digraph(comment='State Machine')
        dot.attr(rankdir='TB')

        # 设置节点样式
        dot.attr('node', shape='box', style='rounded')

        def add_state_to_graph(state, parent=None):
            # 添加状态节点
            state_label = f"{state.name}"
            if isinstance(state, CompositeState):
                state_label += " (Composite)"
                dot.node(state.id, state_label, shape='box', style='rounded')

                # 添加子状态
                for child in state.states:
                    add_state_to_graph(child, state)
                    # 添加从父状态到子状态的边
                    dot.edge(state.id, child.id, style='dashed')

                # 如果有初始状态，添加特殊标记
                if state.initial_state_id:
                    initial_state = state.initial_state
                    if initial_state:
                        dot.node(f"{state.id}_initial", "", shape="point")
                        dot.edge(f"{state.id}_initial", initial_state.id)
            else:
                dot.node(state.id, state_label)

        # 添加所有状态
        add_state_to_graph(state_chart.root_state)

        # 添加所有迁移
        for transition in state_chart.transitions:
            dot.edge(transition.src_state_id, transition.dst_state_id,
                     label=f"{transition.event.name}")

        # 生成图像
        with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp:
            dot.render(tmp.name, format='png', cleanup=True)
            pixmap = QPixmap(f"{tmp.name}.png")
            self.image_label.setPixmap(pixmap)