"""后台任务线程 - QThread 运行流水线（第一阶段）"""

from PySide6.QtCore import QThread, Signal
from services.recognizer import Recognizer
from services.writer import Writer
from pipeline import 流水线, 运行结果


class Worker(QThread):
    """后台任务线程 - 运行流水线（第一阶段）"""

    进度信号 = Signal(int, int, str)  # 已处理, 总数, 当前文件名
    完成信号 = Signal(运行结果)  # 运行结果
    错误信号 = Signal(str)  # 错误信息

    def __init__(self, 输入文件夹: str):
        super().__init__()
        self.输入文件夹 = 输入文件夹

    def run(self):
        """运行流水线（第一阶段）"""
        try:
            # 装配依赖
            识别器 = Recognizer()
            输出器 = Writer()

            流水线实例 = 流水线(识别器, 输出器)

            # 进度回调
            def 进度回调(已处理: int, 总数: int, 当前文件: str):
                self.进度信号.emit(已处理, 总数, 当前文件)

            # 运行流水线
            结果 = 流水线实例.运行(self.输入文件夹, 进度回调)

            # 发送完成信号
            self.完成信号.emit(结果)

        except Exception as e:
            self.错误信号.emit(f"处理失败: {str(e)}")
