"""后台任务线程 - QThread 运行流水线（第一阶段：分批循环识别 + 归档）"""

from PySide6.QtCore import QThread, Signal
from services.recognizer import Recognizer
from services.writer import Writer
from pipeline import 流水线, 运行结果


class Worker(QThread):
    进度信号 = Signal(int, int, str)
    完成信号 = Signal(运行结果)
    错误信号 = Signal(str)

    def __init__(self, 输入文件夹: str):
        super().__init__()
        self.输入文件夹 = 输入文件夹

    def run(self):
        try:
            识别器 = Recognizer()
            输出器 = Writer(self.输入文件夹)
            流水线实例 = 流水线(识别器, 输出器)

            def 进度回调(已处理: int, 总数: int, 当前文件: str):
                self.进度信号.emit(已处理, 总数, 当前文件)

            结果 = 流水线实例.运行(self.输入文件夹, 进度回调)
            self.完成信号.emit(结果)
        except Exception as e:
            self.错误信号.emit(f"处理失败: {str(e)}")
