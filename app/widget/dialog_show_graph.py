from PyQt5.QtWidgets import QDialog, QFileDialog, QGraphicsScene, QGraphicsPixmapItem, QGraphicsView, QVBoxLayout
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QPixmap, QPainter
from PyQt5 import uic
import os
from app.utils.show_state_graph import ShowStateGraph
from pyfcstm.model import Statechart
from app.ui import UIDialogShowGraph
from app.utils.fcstm_state_chart import FcstmStateChart

class CustomGraphicsView(QGraphicsView):
    def wheelEvent(self, event):
        """重写滚轮事件，只处理缩放，不处理滚动"""
        # 计算缩放因子
        zoomInFactor = 1.25
        zoomOutFactor = 1 / zoomInFactor

        # 保存当前场景位置
        oldPos = self.mapToScene(event.pos())

        # 缩放
        if event.angleDelta().y() > 0:
            factor = zoomInFactor
        else:
            factor = zoomOutFactor
        self.scale(factor, factor)

        # 调整场景位置
        newPos = self.mapToScene(event.pos())
        delta = newPos - oldPos
        self.translate(delta.x(), delta.y())

class DialogShowGraph(QDialog, UIDialogShowGraph):
    def __init__(self, parent, fcstm_state_chart: FcstmStateChart):
        QDialog.__init__(self, parent)
        self.setupUi(self)
        self.fcstm_state_chart = fcstm_state_chart
        self.temp_png_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'temp_state_graph.png')
        
        # 创建自定义的CustomGraphicsView并添加到widget容器中
        self.graphics_view_show_graph = CustomGraphicsView()
        layout = QVBoxLayout(self.widget_graph_container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.graphics_view_show_graph)
        
        # 连接信号和槽
        self.button_export_graph.clicked.connect(self.export_graph)
        
        # 设置图形视图的属性
        self.graphics_view_show_graph.setDragMode(QGraphicsView.ScrollHandDrag)
        self.graphics_view_show_graph.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.graphics_view_show_graph.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.graphics_view_show_graph.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self.graphics_view_show_graph.setResizeAnchor(QGraphicsView.AnchorUnderMouse)
        self.graphics_view_show_graph.setViewportUpdateMode(QGraphicsView.FullViewportUpdate)
        
        # 显示状态机图
        self.show_state_graph()
        
    def show_state_graph(self):
        """显示状态机图"""
        # 生成状态机图
        ShowStateGraph.show_state_graph(self.fcstm_state_chart, self.temp_png_path)
        
        # 创建场景并显示图像
        scene = QGraphicsScene()
        pixmap = QPixmap(self.temp_png_path)
        
        # 增加图片大小
        scaled_pixmap = pixmap.scaled(pixmap.width() * 2, pixmap.height() * 2, 
                                    Qt.KeepAspectRatio, Qt.SmoothTransformation)
        
        item = QGraphicsPixmapItem(scaled_pixmap)
        scene.addItem(item)
        
        # 设置场景到视图
        self.graphics_view_show_graph.setScene(scene)
        self.graphics_view_show_graph.setRenderHint(QPainter.Antialiasing)
        self.graphics_view_show_graph.setRenderHint(QPainter.SmoothPixmapTransform)
        self.graphics_view_show_graph.setRenderHint(QPainter.TextAntialiasing)
        
        # 调整视图以适应内容
        self.graphics_view_show_graph.fitInView(scene.sceneRect(), Qt.KeepAspectRatio)
        
    def export_graph(self):
        """导出状态机图"""
        # 获取保存路径
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "导出状态机图",
            "./",
            "PNG Files (*.png);;All Files (*)"
        )
        
        if file_path:
            # 复制临时文件到目标位置
            if os.path.exists(self.temp_png_path):
                import shutil
                shutil.copy2(self.temp_png_path, file_path)
    
    def closeEvent(self, event):
        """关闭对话框时清理临时文件"""
        if os.path.exists(self.temp_png_path):
            os.remove(self.temp_png_path)
        super().closeEvent(event)
