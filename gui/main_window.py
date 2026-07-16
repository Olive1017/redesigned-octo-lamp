"""主窗口 - 重新布局（左右分栏 + 底部日志）"""

import os
import logging
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
    QGroupBox, QLineEdit, QPushButton, QLabel, QProgressBar,
    QListWidget, QFileDialog, QMessageBox, QPlainTextEdit
)
from PySide6.QtCore import Qt, Slot
from PySide6.QtGui import QTextCursor

from gui.worker import Worker, 上传Worker


class MainWindow(QMainWindow):
    """主窗口：左侧识别/拼图，右侧上传，底部日志（共享工作目录）"""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("中石油化销拼图上传助手")
        self.setMinimumSize(900, 700)

        self.工作目录 = ""
        self.worker = None
        self.上传worker = None

        self._init_ui()
        self._bind_logger()

    def _init_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)

        # 顶部：工作目录行
        top_row = QHBoxLayout()
        self.dir_edit = QLineEdit()
        self.dir_edit.setReadOnly(True)
        self.select_btn = QPushButton("选择")
        self.select_btn.clicked.connect(self._select_dir)
        top_row.addWidget(QLabel("工作目录:"))
        top_row.addWidget(self.dir_edit)
        top_row.addWidget(self.select_btn)
        main_layout.addLayout(top_row)

        # 上半区：左右分栏
        vertical_split = QSplitter(Qt.Vertical)

        horizontal_split = QSplitter(Qt.Horizontal)

        # 左：识别/拼图
        left_box = QGroupBox("第一步：识别+拼图")
        left_layout = QVBoxLayout(left_box)
        hl = QHBoxLayout()
        self.start_recog_btn = QPushButton("开始识别")
        self.start_recog_btn.clicked.connect(self._start_recog)
        self.start_recog_btn.setEnabled(False)
        self.stop_recog_btn = QPushButton("停止")
        self.stop_recog_btn.clicked.connect(self._stop_recog)
        self.stop_recog_btn.setEnabled(False)
        hl.addWidget(self.start_recog_btn)
        hl.addWidget(self.stop_recog_btn)
        left_layout.addLayout(hl)
        self.recog_progress = QProgressBar()
        left_layout.addWidget(self.recog_progress)
        self.recog_label = QLabel("")
        left_layout.addWidget(self.recog_label)
        self.recog_list = QListWidget()
        left_layout.addWidget(self.recog_list)

        # 右：上传 LMS
        right_box = QGroupBox("第二步：上传系统")
        right_layout = QVBoxLayout(right_box)
        hl2 = QHBoxLayout()
        self.start_upload_btn = QPushButton("开始上传")
        self.start_upload_btn.clicked.connect(self._start_upload)
        self.start_upload_btn.setEnabled(False)
        self.stop_upload_btn = QPushButton("停止")
        self.stop_upload_btn.clicked.connect(self._stop_upload)
        self.stop_upload_btn.setEnabled(False)
        hl2.addWidget(self.start_upload_btn)
        hl2.addWidget(self.stop_upload_btn)
        right_layout.addLayout(hl2)
        self.upload_progress = QProgressBar()
        right_layout.addWidget(self.upload_progress)
        self.upload_label = QLabel("")
        right_layout.addWidget(self.upload_label)
        self.upload_list = QListWidget()
        right_layout.addWidget(self.upload_list)

        horizontal_split.addWidget(left_box)
        horizontal_split.addWidget(right_box)
        horizontal_split.setStretchFactor(0, 1)
        horizontal_split.setStretchFactor(1, 1)

        # 底部：日志
        log_box = QGroupBox("日志")
        log_layout = QVBoxLayout(log_box)
        self.log_view = QPlainTextEdit()
        self.log_view.setReadOnly(True)
        log_layout.addWidget(self.log_view)
        btn_row = QHBoxLayout()
        self.clear_log_btn = QPushButton("清空")
        self.clear_log_btn.clicked.connect(self.log_view.clear)
        self.export_log_btn = QPushButton("导出")
        self.export_log_btn.clicked.connect(self._export_log)
        btn_row.addStretch()
        btn_row.addWidget(self.clear_log_btn)
        btn_row.addWidget(self.export_log_btn)
        log_layout.addLayout(btn_row)

        vertical_split.addWidget(horizontal_split)
        vertical_split.addWidget(log_box)
        vertical_split.setStretchFactor(0, 3)
        vertical_split.setStretchFactor(1, 1)

        main_layout.addWidget(vertical_split)

    def _bind_logger(self):
        # Find any QtLogHandler attached to root logger and connect its signal
        import logging as _logging
        from gui.log_handler import QtLogHandler
        for h in _logging.getLogger().handlers:
            if isinstance(h, QtLogHandler):
                h.signals.日志信号.connect(self._append_log)
                break

    @Slot(str)
    def _append_log(self, text: str):
        self.log_view.appendPlainText(text)
        cursor = self.log_view.textCursor()
        cursor.movePosition(QTextCursor.End)
        self.log_view.setTextCursor(cursor)

    def _select_dir(self):
        folder = QFileDialog.getExistingDirectory(self, "选择工作目录")
        if folder:
            self.工作目录 = folder
            self.dir_edit.setText(folder)
            # enable start buttons
            self.start_recog_btn.setEnabled(True)
            self.start_upload_btn.setEnabled(True)

    # ----------------- 识别相关 -----------------
    def _start_recog(self):
        if not self.工作目录:
            QMessageBox.warning(self, "提示", "请先选择工作目录")
            return
        self.recog_list.clear()
        self.recog_progress.setValue(0)
        self.start_recog_btn.setEnabled(False)
        self.stop_recog_btn.setEnabled(True)

        self.worker = Worker(self.工作目录)
        self.worker.进度信号.connect(self._on_recog_progress)
        self.worker.完成信号.connect(self._on_recog_done)
        self.worker.错误信号.connect(self._on_recog_error)
        self.worker.start()

    def _stop_recog(self):
        if self.worker and self.worker.isRunning():
            try:
                self.worker.terminate()
            except Exception:
                pass
        self.start_recog_btn.setEnabled(True)
        self.stop_recog_btn.setEnabled(False)

    def _on_recog_progress(self, i: int, 总数: int, 车牌: str):
        self.recog_progress.setMaximum(总数 if 总数 > 0 else 1)
        self.recog_progress.setValue(i)
        self.recog_label.setText(f"{i}/{总数}  {车牌}")

    def _on_recog_done(self, 结果):
        self.recog_label.setText("识别完成")
        self.start_recog_btn.setEnabled(True)
        self.stop_recog_btn.setEnabled(False)
        try:
            for order in 结果.已完成:
                self.recog_list.addItem(f"【{order.车牌}】 交货单号: {order.交货单号 or ''}")
            for order in 结果.待人工:
                self.recog_list.addItem(f"待人工: 【{order.车牌}】 {order.异常原因 or ''}")
        except Exception as e:
            logging.exception("解析识别结果时出错: %s", e)

    def _on_recog_error(self, msg: str):
        self.recog_label.setText("识别出错")
        self.start_recog_btn.setEnabled(True)
        self.stop_recog_btn.setEnabled(False)
        QMessageBox.critical(self, "错误", msg)

    # ----------------- 上传相关 -----------------
    def _start_upload(self):
        if not self.工作目录:
            QMessageBox.warning(self, "提示", "请先选择工作目录")
            return
        self.upload_list.clear()
        # set progress to busy
        self.upload_progress.setRange(0, 0)
        self.start_upload_btn.setEnabled(False)
        self.stop_upload_btn.setEnabled(True)

        self.上传worker = 上传Worker(self.工作目录)
        self.上传worker.需要人工登录.connect(self._on_upload_need_manual)
        self.上传worker.完成信号.connect(self._on_upload_done)
        self.上传worker.错误信号.connect(self._on_upload_error)
        self.上传worker.start()

    def _stop_upload(self):
        if self.上传worker and self.上传worker.isRunning():
            try:
                self.上传worker.terminate()
            except Exception:
                pass
        self.start_upload_btn.setEnabled(True)
        self.stop_upload_btn.setEnabled(False)
        self.upload_progress.setRange(0, 1)
        self.upload_progress.setValue(0)

    def _on_upload_need_manual(self):
        QMessageBox.information(self, "需要登录", "请在浏览器输入验证码后点确定继续")
        try:
            if self.上传worker:
                self.上传worker.继续登录()
        except Exception:
            logging.exception("调用继续登录失败")

    def _on_upload_done(self, msg: str):
        logging.info(msg)
        self.upload_list.addItem(msg)
        self.start_upload_btn.setEnabled(True)
        self.stop_upload_btn.setEnabled(False)
        self.upload_progress.setRange(0, 1)
        self.upload_progress.setValue(1)

    def _on_upload_error(self, msg: str):
        logging.error(msg)
        self.upload_list.addItem(msg)
        self.start_upload_btn.setEnabled(True)
        self.stop_upload_btn.setEnabled(False)
        self.upload_progress.setRange(0, 1)
        self.upload_progress.setValue(0)

    # ----------------- 日志导出 -----------------
    def _export_log(self):
        path, _ = QFileDialog.getSaveFileName(self, "导出日志", filter="Text Files (*.txt);;All Files (*)")
        if path:
            try:
                with open(path, "w", encoding="utf-8") as f:
                    f.write(self.log_view.toPlainText())
            except Exception as e:
                QMessageBox.critical(self, "导出失败", str(e))



