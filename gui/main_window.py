"""主窗口 - PySide6 薄壳界面（第一阶段归档 + 第二阶段拼图）"""

import os
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QProgressBar, QListWidget,
    QFileDialog, QMessageBox
)
from PySide6.QtCore import Qt
from gui.worker import Worker, 拼图Worker


class MainWindow(QMainWindow):
    """主窗口 - 薄壳界面，调用流水线"""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("OCR 照片识别、归档与拼图工具")
        self.setMinimumSize(900, 700)

        self.输入文件夹路径 = ""
        self.worker = None
        self.拼图worker = None
        self.已归档订单表 = {}

        self._初始化界面()

    def _初始化界面(self):
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

        archived_layout = QVBoxLayout()
        archived_layout.addWidget(QLabel("已归档"))
        self.已归档列表 = QListWidget()
        archived_layout.addWidget(self.已归档列表)
        result_layout.addLayout(archived_layout)

        pending_layout = QVBoxLayout()
        pending_layout.addWidget(QLabel("待定/无车牌"))
        self.待定列表 = QListWidget()
        pending_layout.addWidget(self.待定列表)
        result_layout.addLayout(pending_layout)

        layout.addLayout(result_layout)

        # 底部第二阶段按钮
        bottom_layout = QHBoxLayout()
        self.校验拼图按钮 = QPushButton("校验并拼图")
        self.校验拼图按钮.clicked.connect(self._开始拼图)
        self.校验拼图按钮.setEnabled(False)
        self.上传按钮 = QPushButton("启动 RPA 上传（预留）")
        self.上传按钮.clicked.connect(self._启动上传占位)
        self.上传按钮.setEnabled(False)
        bottom_layout.addStretch()
        bottom_layout.addWidget(self.校验拼图按钮)
        bottom_layout.addWidget(self.上传按钮)
        layout.addLayout(bottom_layout)

    def _选择文件夹(self):
        folder = QFileDialog.getExistingDirectory(self, "选择装照片的文件夹")
        if folder:
            self.输入文件夹路径 = folder
            self.路径标签.setText(folder)
            self.开始处理按钮.setEnabled(True)
            self._清空列表()

    def _清空列表(self):
        self.已归档列表.clear()
        self.待定列表.clear()
        self.已归档订单表.clear()

    def _开始处理(self):
        if not self.输入文件夹路径:
            QMessageBox.warning(self, "提示", "请先选择文件夹")
            return

        self._清空列表()
        self.进度条.setValue(0)
        self.开始处理按钮.setEnabled(False)
        self.校验拼图按钮.setEnabled(False)
        self.上传按钮.setEnabled(False)

        self.worker = Worker(self.输入文件夹路径)
        self.worker.进度信号.connect(self._更新进度)
        self.worker.完成信号.connect(self._处理完成)
        self.worker.错误信号.connect(self._处理错误)
        self.worker.start()

    def _更新进度(self, 已处理: int, 总数: int, 当前文件: str):
        self.进度条.setMaximum(总数 if 总数 > 0 else 1)
        self.进度条.setValue(已处理)
        self.当前文件标签.setText(f"处理中: {当前文件}")

    def _处理完成(self, 结果):
        self.当前文件标签.setText("归档完成")
        self.开始处理按钮.setEnabled(True)

        for order in 结果.已归档:
            item_text = f"{order.车牌} - {order.交货单号 or '未识别'} ({order.文件夹路径})"
            self.已归档列表.addItem(item_text)
            self.已归档订单表[order.车牌] = order

        for photo in 结果.待定:
            self.待定列表.addItem(os.path.basename(photo.path))

        if self.已归档订单表:
            self.校验拼图按钮.setEnabled(True)

        QMessageBox.information(
            self, "完成",
            f"归档完成！\n已归档: {len(结果.已归档)} 单\n待定: {len(结果.待定)} 张"
        )

    def _开始拼图(self):
        if not self.已归档订单表:
            QMessageBox.warning(self, "提示", "没有已归档订单")
            return

        self.进度条.setValue(0)
        self.校验拼图按钮.setEnabled(False)
        self.上传按钮.setEnabled(False)

        self.拼图worker = 拼图Worker(self.已归档订单表)
        self.拼图worker.进度信号.connect(self._更新进度)
        self.拼图worker.完成信号.connect(self._拼图完成)
        self.拼图worker.错误信号.connect(self._处理错误)
        self.拼图worker.start()

    def _拼图完成(self, 结果):
        self.当前文件标签.setText("拼图完成")
        self.校验拼图按钮.setEnabled(True)

        待人工文本 = ""
        if 结果.待人工:
            待人工文本 = "\n\n待人工:\n" + "\n".join(
                f"{o.车牌}: {o.异常原因}" for o in 结果.待人工
            )

        if 结果.已拼图:
            self.上传按钮.setEnabled(True)

        QMessageBox.information(
            self, "完成",
            f"拼图完成！\n已拼图: {len(结果.已拼图)} 单\n待人工: {len(结果.待人工)} 单" + 待人工文本
        )

    def _处理错误(self, 错误信息: str):
        self.当前文件标签.setText("处理出错")
        self.开始处理按钮.setEnabled(True)
        self.校验拼图按钮.setEnabled(bool(self.已归档订单表))
        QMessageBox.critical(self, "错误", 错误信息)

    def _启动上传占位(self):
        QMessageBox.information(
            self, "提示",
            "RPA 上传功能预留中\n将来将调用上传器将已拼图订单交给 RPA"
        )
