"""主窗口 - PySide6 薄壳界面（一键一条龙：识别→改名→拼图→文件夹改名）"""

import os
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QProgressBar, QListWidget,
    QFileDialog, QMessageBox
)
from gui.worker import Worker


class MainWindow(QMainWindow):
    """主窗口 - 薄壳界面，一个按钮走完整链路"""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("OCR 照片识别、拼图与归档工具")
        self.setMinimumSize(900, 700)

        self.父文件夹路径 = ""
        self.worker = None
        self.已完成订单 = []

        self._初始化界面()

    def _初始化界面(self):
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)

        # 顶部控制区
        top = QHBoxLayout()
        self.选择文件夹按钮 = QPushButton("选择父文件夹")
        self.选择文件夹按钮.clicked.connect(self._选择文件夹)
        self.路径标签 = QLabel("未选择文件夹（请选择包含各车牌子文件夹的父文件夹）")
        self.开始处理按钮 = QPushButton("开始处理")
        self.开始处理按钮.clicked.connect(self._开始处理)
        self.开始处理按钮.setEnabled(False)
        top.addWidget(self.选择文件夹按钮)
        top.addWidget(self.路径标签)
        top.addWidget(self.开始处理按钮)
        top.addStretch()
        layout.addLayout(top)

        # 进度区
        self.进度条 = QProgressBar()
        self.进度条.setValue(0)
        layout.addWidget(self.进度条)
        self.当前文件标签 = QLabel("")
        layout.addWidget(self.当前文件标签)

        # 结果区：已完成 / 待人工 / 已跳过
        result = QHBoxLayout()

        done = QVBoxLayout()
        done.addWidget(QLabel("已完成（已拼图+已改名）"))
        self.已完成列表 = QListWidget()
        done.addWidget(self.已完成列表)
        result.addLayout(done)

        manual = QVBoxLayout()
        manual.addWidget(QLabel("待人工（不齐全/识别失败）"))
        self.待人工列表 = QListWidget()
        manual.addWidget(self.待人工列表)
        result.addLayout(manual)

        skip = QVBoxLayout()
        skip.addWidget(QLabel("已跳过（已处理过）"))
        self.已跳过列表 = QListWidget()
        skip.addWidget(self.已跳过列表)
        result.addLayout(skip)

        layout.addLayout(result)

        # 底部 RPA 预留
        bottom = QHBoxLayout()
        self.上传按钮 = QPushButton("启动 RPA 上传（预留）")
        self.上传按钮.clicked.connect(self._启动上传占位)
        self.上传按钮.setEnabled(False)
        bottom.addStretch()
        bottom.addWidget(self.上传按钮)
        layout.addLayout(bottom)

    def _选择文件夹(self):
        folder = QFileDialog.getExistingDirectory(self, "选择包含各车牌子文件夹的父文件夹")
        if folder:
            self.父文件夹路径 = folder
            self.路径标签.setText(folder)
            self.开始处理按钮.setEnabled(True)
            self._清空列表()

    def _清空列表(self):
        self.已完成列表.clear()
        self.待人工列表.clear()
        self.已跳过列表.clear()
        self.已完成订单 = []

    def _开始处理(self):
        if not self.父文件夹路径:
            QMessageBox.warning(self, "提示", "请先选择父文件夹")
            return

        self._清空列表()
        self.进度条.setValue(0)
        self.开始处理按钮.setEnabled(False)
        self.上传按钮.setEnabled(False)

        self.worker = Worker(self.父文件夹路径)
        self.worker.进度信号.connect(self._更新进度)
        self.worker.完成信号.connect(self._处理完成)
        self.worker.错误信号.connect(self._处理错误)
        self.worker.start()

    def _更新进度(self, i: int, 总数: int, 车牌: str):
        self.进度条.setMaximum(总数 if 总数 > 0 else 1)
        self.进度条.setValue(i)
        self.当前文件标签.setText(f"处理中: {车牌}")

    def _处理完成(self, 结果):
        self.当前文件标签.setText("处理完成")
        self.开始处理按钮.setEnabled(True)

        for order in 结果.已完成:
            self.已完成列表.addItem(
                f"{order.车牌} - {order.交货单号 or ''}（{os.path.basename(order.文件夹路径 or '')}）"
            )
            self.已完成订单.append(order)

        for order in 结果.待人工:
            self.待人工列表.addItem(f"{order.车牌}: {order.异常原因 or ''}")

        for 名 in 结果.已跳过:
            self.已跳过列表.addItem(名)

        if self.已完成订单:
            self.上传按钮.setEnabled(True)

        QMessageBox.information(
            self, "完成",
            f"处理完成！\n已完成: {len(结果.已完成)} 单\n待人工: {len(结果.待人工)} 单\n已跳过: {len(结果.已跳过)} 个"
        )

    def _处理错误(self, 错误信息: str):
        self.当前文件标签.setText("处理出错")
        self.开始处理按钮.setEnabled(True)
        QMessageBox.critical(self, "错误", 错误信息)

    def _启动上传占位(self):
        QMessageBox.information(
            self, "提示",
            "RPA 上传功能预留中\n将来将调用上传器把已完成订单交给 RPA"
        )
