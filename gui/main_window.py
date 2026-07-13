"""主窗口 - PySide6 薄壳界面（一键一条龙：识别→改名→拼图→文件夹改名）"""

import os
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QProgressBar, QListWidget,
    QFileDialog, QMessageBox
)

from core.models import Order
from gui.worker import Worker, 上传Worker


class MainWindow(QMainWindow):
    """主窗口 - 薄壳界面，一个按钮走完整链路"""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("OCR 照片识别、拼图与归档工具")
        self.setMinimumSize(900, 700)

        self.父文件夹路径 = ""
        self.worker = None
        self.上传worker = None
        self.可上传订单 = []

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

        layout.addLayout(result)

        # 底部 RPA 上传
        bottom = QHBoxLayout()
        self.上传按钮 = QPushButton("启动 RPA 上传")
        self.上传按钮.clicked.connect(self._启动上传)
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
        self.可上传订单 = []

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
            self._添加订单到列表(order, self.已完成列表)
            self.可上传订单.append(order)

        # 处理已跳过订单中有交货单号的
        for order in 结果.已跳过:
            if order.交货单号:
                self.可上传订单.append(order)

        for order in 结果.待人工:
            self._添加订单到列表(order, self.待人工列表)

        if self.可上传订单:
            self.上传按钮.setEnabled(True)

        QMessageBox.information(
            self, "完成",
            f"处理完成！\n可上传: {len(self.可上传订单)} 单\n待人工: {len(结果.待人工)} 单\n已跳过: {len(结果.已跳过)} 个"
        )

    def _添加订单到列表(self, order: Order, 列表控件: QListWidget):
        """将订单的详细识别信息添加到列表中"""
        识别信息 = []

        # 基本信息
        文本 = f"【{order.车牌}】"
        if order.交货单号:
            文本 += f" 交货单:{order.交货单号}"
        if order.销售订单号:
            文本 += f" 销售单:{order.销售订单号}"
        识别信息.append(文本)

        # 照片识别结果
        成功识别 = [p for p in order.photos if p.label is not None]
        失败识别 = [p for p in order.photos if p.label is None]

        if 成功识别:
            识别摘要 = {}
            for p in 成功识别:
                标识 = p.label.value if p.label else "未知"
                识别摘要[标识] = 识别摘要.get(标识, 0) + 1
            识别信息.append(f"  ✅ 识别: {', '.join(f'{k}×{v}' for k, v in 识别摘要.items())}")

        if 失败识别:
            失败文件名 = [os.path.basename(p.path) for p in 失败识别]
            识别信息.append(f"  ❌ 失败: {', '.join(失败文件名[:3])}" +
                             ("..." if len(失败文件名) > 3 else ""))

        # 异常原因
        if order.异常原因:
            识别信息.append(f"  ⚠️ {order.异常原因}")

        列表控件.addItem("\n".join(识别信息))

    def _处理错误(self, 错误信息: str):
        self.当前文件标签.setText("处理出错")
        self.开始处理按钮.setEnabled(True)
        QMessageBox.critical(self, "错误", 错误信息)

    def _启动上传(self):
        if not self.父文件夹路径:
            QMessageBox.warning(self, "提示", "请先选择父文件夹并完成处理")
            return
        self.上传按钮.setEnabled(False)
        self.上传worker = 上传Worker(self.父文件夹路径)
        self.上传worker.需要人工登录.connect(self._提示人工登录)
        self.上传worker.完成信号.connect(self._上传完成)
        self.上传worker.错误信号.connect(self._上传错误)
        self.上传worker.start()

    def _提示人工登录(self):
        QMessageBox.information(self, "需要登录",
                                "验证码自动识别失败，请在弹出的浏览器里手动完成登录/验证码，然后点“确定”继续")
        self.上传worker.继续登录()

    def _上传完成(self, msg: str):
        self.上传按钮.setEnabled(True)
        QMessageBox.information(self, "完成", msg)

    def _上传错误(self, msg: str):
        self.上传按钮.setEnabled(True)
        QMessageBox.critical(self, "上传出错", msg)


