"""主窗口 - PySide6 薄壳界面（第一阶段）"""

import os
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QProgressBar, QListWidget,
    QFileDialog, QMessageBox
)
from PySide6.QtCore import Qt
from gui.worker import Worker


class MainWindow(QMainWindow):
    """主窗口 - 薄壳界面，调用流水线（第一阶段）"""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("OCR 照片识别与归档工具（第一阶段）")
        self.setMinimumSize(900, 700)

        self.输入文件夹路径 = ""
        self.worker = None
        self.已归档订单表 = {}

        self._初始化界面()

    def _初始化界面(self):
        """初始化界面布局"""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)

        # 顶部控制区
        top_layout = QHBoxLayout()
        self.选择文件夹按钮 = QPushButton("选择文件夹")
        self.选择文件夹按钮.clicked.connect(self._选择文件夹)
        self.路径标签 = QLabel("未选择文件夹")
        self.开始处理按钮 = QPushButton("开始归档")
        self.开始处理按钮.clicked.connect(self._开始处理)
        self.开始处理按钮.setEnabled(False)
        top_layout.addWidget(self.选择文件夹按钮)
        top_layout.addWidget(self.路径标签)
        top_layout.addWidget(self.开始处理按钮)
        top_layout.addStretch()
        layout.addLayout(top_layout)

        # 中部进度区
        self.进度条 = QProgressBar()
        self.进度条.setValue(0)
        layout.addWidget(self.进度条)
        self.当前文件标签 = QLabel("")
        layout.addWidget(self.当前文件标签)

        # 下部结果区
        result_layout = QHBoxLayout()

        # 已归档列表
        archived_layout = QVBoxLayout()
        archived_label = QLabel("已归档")
        archived_layout.addWidget(archived_label)
        self.已归档列表 = QListWidget()
        archived_layout.addWidget(self.已归档列表)
        result_layout.addLayout(archived_layout)

        # 待定列表
        pending_layout = QVBoxLayout()
        pending_label = QLabel("待定/无车牌")
        pending_layout.addWidget(pending_label)
        self.待定列表 = QListWidget()
        pending_layout.addWidget(self.待定列表)
        result_layout.addLayout(pending_layout)

        layout.addLayout(result_layout)

        # 底部第二阶段按钮（占位）
        bottom_layout = QHBoxLayout()
        self.校验拼图按钮 = QPushButton("校验并拼图（第二阶段）")
        self.校验拼图按钮.clicked.connect(self._校验拼图占位)
        self.校验拼图按钮.setEnabled(False)
        self.上传按钮 = QPushButton("启动 RPA 上传（第二阶段）")
        self.上传按钮.clicked.connect(self._启动上传占位)
        self.上传按钮.setEnabled(False)
        bottom_layout.addStretch()
        bottom_layout.addWidget(self.校验拼图按钮)
        bottom_layout.addWidget(self.上传按钮)
        layout.addLayout(bottom_layout)

    def _选择文件夹(self):
        """选择输入文件夹"""
        folder = QFileDialog.getExistingDirectory(self, "选择装照片的文件夹")
        if folder:
            self.输入文件夹路径 = folder
            self.路径标签.setText(folder)
            self.开始处理按钮.setEnabled(True)
            self._清空列表()

    def _清空列表(self):
        """清空结果列表"""
        self.已归档列表.clear()
        self.待定列表.clear()
        self.已归档订单表.clear()

    def _开始处理(self):
        """开始处理"""
        if not self.输入文件夹路径:
            QMessageBox.warning(self, "提示", "请先选择文件夹")
            return

        self._清空列表()
        self.进度条.setValue(0)
        self.开始处理按钮.setEnabled(False)
        self.校验拼图按钮.setEnabled(False)
        self.上传按钮.setEnabled(False)

        # 创建并启动 Worker
        self.worker = Worker(self.输入文件夹路径)
        self.worker.进度信号.connect(self._更新进度)
        self.worker.完成信号.connect(self._处理完成)
        self.worker.错误信号.connect(self._处理错误)
        self.worker.start()

    def _更新进度(self, 已处理: int, 总数: int, 当前文件: str):
        """更新进度"""
        self.进度条.setMaximum(总数)
        self.进度条.setValue(已处理)
        self.当前文件标签.setText(f"处理中: {当前文件}")

    def _处理完成(self, 结果):
        """处理完成"""
        self.当前文件标签.setText("归档完成")
        self.开始处理按钮.setEnabled(True)

        # 填充已归档列表
        for order in 结果.已归档:
            item_text = f"{order.车牌} - {order.交货单号 or '未识别'} ({order.文件夹路径})"
            self.已归档列表.addItem(item_text)
            self.已归档订单表[order.车牌] = order

        # 填充待定列表
        for photo in 结果.待定:
            item_text = os.path.basename(photo.path)
            self.待定列表.addItem(item_text)

        # 启用第二阶段按钮（如果有已归档订单）
        if self.已归档订单表:
            self.校验拼图按钮.setEnabled(True)
            self.上传按钮.setEnabled(True)

        QMessageBox.information(
            self, "完成",
            f"归档完成！\n已归档: {len(结果.已归档)} 单\n待定: {len(结果.待定)} 张"
        )

    def _处理错误(self, 错误信息: str):
        """处理错误"""
        self.当前文件标签.setText("处理出错")
        self.开始处理按钮.setEnabled(True)
        QMessageBox.critical(self, "错误", 错误信息)

    def _校验拼图占位(self):
        """校验并拼图（第二阶段占位）"""
        QMessageBox.information(
            self, "提示",
            "校验并拼图功能（第二阶段）待实现\n"
            "将来将调用校验器和拼图器处理已归档订单"
        )

    def _启动上传占位(self):
        """启动 RPA 上传（第二阶段占位）"""
        QMessageBox.information(
            self, "提示",
            "RPA 上传功能（第二阶段）待实现\n"
            "将来将调用上传器上传已处理订单"
        )
