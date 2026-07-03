"""流水线编排 - 第一阶段：分批循环识别+归档；第二阶段：校验+拼图"""

import os
from dataclasses import dataclass
from typing import Dict, List, Optional, Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from models import Order, OrderStatus, Photo
from recognizer import Recognizer
from writer import Writer
from validator import Validator
from collager import Collager
import config


@dataclass
class 运行结果:
    """第一阶段运行结果"""
    订单表: Dict[str, Order]
    已归档: List[Order]
    待定: List[Photo]


@dataclass
class 拼图结果:
    """第二阶段运行结果"""
    已拼图: List[Order]
    待人工: List[Order]


class 流水线:
    """第一阶段：分批循环识别 + 归档"""

    def __init__(self, 识别器: Recognizer, 输出器: Writer):
        self.识别器 = 识别器
        self.输出器 = 输出器

    def 运行(
        self,
        输入文件夹: str,
        进度回调: Optional[Callable[[int, int, str], None]] = None,
    ) -> 运行结果:
        图片列表 = self._取图片列表(输入文件夹)
        总数 = len(图片列表)
        if 总数 == 0:
            return 运行结果(订单表={}, 已归档=[], 待定=[])

        订单表: Dict[str, Order] = {}
        待定列表: List[Photo] = []
        失败次数: Dict[str, int] = {}
        已处理 = 0

        while True:
            剩余 = self._取图片列表(输入文件夹)
            可处理 = [p for p in 剩余 if 失败次数.get(p, 0) < config.MAX_ROUNDS_PER_IMAGE]
            if not 可处理:
                break

            批次 = 可处理[:config.BATCH_SIZE]
            结果们 = self._识别一批(批次)

            for path, (photo, err) in zip(批次, 结果们):
                if err is not None:
                    失败次数[path] = 失败次数.get(path, 0) + 1
                    print(f"[流水线] 识别失败(第{失败次数[path]}轮) {os.path.basename(path)}: {err}")
                    if 失败次数[path] >= config.MAX_ROUNDS_PER_IMAGE:
                        失败照片 = Photo(path=path)
                        self.输出器.移入失败(失败照片)
                        待定列表.append(失败照片)
                        已处理 += 1
                        if 进度回调:
                            进度回调(已处理, 总数, os.path.basename(path))
                    continue

                self.输出器.归档(photo)
                if photo.plate is None:
                    待定列表.append(photo)
                else:
                    if photo.plate not in 订单表:
                        订单表[photo.plate] = Order(车牌=photo.plate, 状态=OrderStatus.归档中)
                    订单表[photo.plate].加照片(photo)
                已处理 += 1
                if 进度回调:
                    进度回调(已处理, 总数, os.path.basename(path))

        self.输出器.收尾定名(订单表)
        for order in 订单表.values():
            order.状态 = OrderStatus.已归档

        return 运行结果(
            订单表=订单表,
            已归档=list(订单表.values()),
            待定=待定列表,
        )

    def _识别一批(self, 批次: List[str]):
        结果: List = [None] * len(批次)

        def 识别单张(i: int, path: str):
            try:
                return i, self.识别器.识别(path), None
            except Exception as e:
                return i, None, e

        并发数 = max(1, min(len(批次), config.BATCH_SIZE))
        with ThreadPoolExecutor(max_workers=并发数) as 执行器:
            futures = [执行器.submit(识别单张, i, p) for i, p in enumerate(批次)]
            for f in as_completed(futures):
                i, photo, err = f.result()
                结果[i] = (photo, err)
        return 结果

    @staticmethod
    def _取图片列表(文件夹: str) -> List[str]:
        支持的扩展名 = {'.jpg', '.jpeg', '.png', '.bmp', '.pdf'}
        图片列表 = []
        if not os.path.exists(文件夹):
            return 图片列表
        for filename in os.listdir(文件夹):
            full = os.path.join(文件夹, filename)
            if not os.path.isfile(full):
                continue
            if os.path.splitext(filename.lower())[1] in 支持的扩展名:
                图片列表.append(full)
        return 图片列表


class 拼图流水线:
    """第二阶段：遭历已归档订单 → 校验 → 齐全则拼图，不齐记「待人工」"""

    def __init__(self, 校验器: Validator, 拼图器: Collager):
        self.校验器 = 校验器
        self.拼图器 = 拼图器

    def 运行(
        self,
        订单表: Dict[str, Order],
        进度回调: Optional[Callable[[int, int, str], None]] = None,
    ) -> 拼图结果:
        已拼图: List[Order] = []
        待人工: List[Order] = []
        订单列表 = list(订单表.values())
        总数 = len(订单列表)

        for i, order in enumerate(订单列表, 1):
            齐全, 原因 = self.校验器.校验(order)
            if not 齐全:
                order.状态 = OrderStatus.标黄人工
                order.异常原因 = 原因
                待人工.append(order)
            else:
                self.拼图器.生成二合一(order)
                self.拼图器.生成三合一(order)
                order.状态 = OrderStatus.已拼图
                已拼图.append(order)
            if 进度回调:
                进度回调(i, 总数, order.车牌)

        return 拼图结果(已拼图=已拼图, 待人工=待人工)
