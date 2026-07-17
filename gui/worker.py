"""后台任务线程 - QThread 运行一键一条龙流水线"""

import threading
from PySide6.QtCore import QThread, Signal
from steps.recognizer import Recognizer
from steps.writer import Writer
from steps.validator import Validator
from steps.collager import Collager
from pipeline import 流水线, 处理结果


class Worker(QThread):
    """一键一条龙 Worker - 识别→改名→校验→拼图→文件夹改名"""

    进度信号 = Signal(int, int, str)
    完成信号 = Signal(处理结果)
    错误信号 = Signal(str)

    def __init__(self, 父文件夹: str):
        super().__init__()
        self.父文件夹 = 父文件夹

    def run(self):
        try:
            流水线实例 = 流水线(Recognizer(), Writer(), Validator(), Collager())

            def 进度回调(i: int, 总数: int, 车牌: str):
                self.进度信号.emit(i, 总数, 车牌)

            结果 = 流水线实例.运行(self.父文件夹, 进度回调)
            self.完成信号.emit(结果)
        except Exception as e:
            self.错误信号.emit(f"处理失败: {str(e)}")


class 上传Worker(QThread):
    """RPA 上传 Worker - LMS 系统自动上传"""

    需要人工登录 = Signal()
    完成信号 = Signal(str)
    错误信号 = Signal(str)

    def __init__(self, 目录: str):
        super().__init__()
        self.目录 = 目录
        self._login_event = threading.Event()

    def 继续登录(self):
        """主线程在用户点确定后调用，解除阻塞"""
        self._login_event.set()

    def run(self):
        try:
            from steps.uploader import main as 上传main

            def 等待人工():
                self._login_event.clear()
                self.需要人工登录.emit()
                self._login_event.wait()

            上传main(self.目录, 等待人工=等待人工)
            self.完成信号.emit("上传流程结束")
        except Exception as e:
            self.错误信号.emit(f"上传失败: {e}")
