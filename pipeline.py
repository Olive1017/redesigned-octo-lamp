"""流水线编排 - 一键一条龙：逐子文件夹 识别→就地改名→校验→拼图→改文件夹名

人工已按车牌把图片分到各子文件夹（每个子文件夹 = 一个车牌 = 一个订单）。
本流水线遭历父文件夹下的每个子文件夹，逐个走完整链路。
- 车牌以子文件夹名为准，识别返回的车牌仅作交叉校验。
- 已处理过的文件夹（名带交货单号 / 已有拼图）自动跳过（幂等、可断点续跑）。
"""

import os
from dataclasses import dataclass, field
from typing import List, Optional, Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from core.models import Order, OrderStatus, PhotoLabel, Photo
from steps.recognizer import Recognizer
from steps.writer import Writer
from steps.validator import Validator
from steps.collager import Collager
import config


@dataclass
class 处理结果:
    """一键一条龙运行结果"""
    已完成: List[Order] = field(default_factory=list)   # 识别+拼图+改名成功
    待人工: List[Order] = field(default_factory=list)   # 不齐全 / 识别失败
    已跳过: List[Order] = field(default_factory=list)      # 幂等跳过的文件夹名


class 流水线:
    """一键一条龙：遭历父文件夹下的车牌子文件夹，逐个处理"""

    支持的扩展名 = {'.jpg', '.jpeg', '.png', '.bmp', '.pdf'}

    def __init__(self, 识别器: Recognizer, 输出器: Writer, 校验器: Validator, 拼图器: Collager):
        self.识别器 = 识别器
        self.输出器 = 输出器
        self.校验器 = 校验器
        self.拼图器 = 拼图器

    def 运行(
        self,
        父文件夹: str,
        进度回调: Optional[Callable[[int, int, str], None]] = None,
    ) -> 处理结果:
        子文件夹s = self._取子文件夹(父文件夹)
        结果 = 处理结果()
        总数 = len(子文件夹s)
        if 总数 == 0:
            return 结果

        for i, 子路径 in enumerate(子文件夹s, 1):
            车牌 = os.path.basename(子路径)
            if 进度回调:
                进度回调(i, 总数, 车牌)

            # 幂等：跳过已处理的文件夹
            if self.输出器.是否已处理(子路径):
                # 已处理过：不重复识别。只从文件夹名 {车牌}_{交货单号} 还原交货单号，
                # 供 UI 计数与上传门槛判断（上传器会自行重扫物理文件夹）。
                order = Order(车牌=车牌, 文件夹路径=子路径, 状态=OrderStatus.已拼图)
                if "_" in 车牌:
                    原车牌, 交货单号 = 车牌.rsplit("_", 1)
                    order.车牌 = 原车牌
                    # 挂一张最小「回单」占位照片，让 order.交货单号 属性取得到值
                    order.加照片(Photo(path=子路径, label=PhotoLabel.回单,
                                       plate=原车牌, 交货单号=交货单号))
                结果.已跳过.append(order)
                continue

            order = self._处理文件夹(子路径, 车牌)
            if order.状态 == OrderStatus.已拼图:
                结果.已完成.append(order)
            else:
                结果.待人工.append(order)

        return 结果

    def _处理文件夹(self, 子路径: str, 车牌: str) -> Order:
        order = Order(车牌=车牌, 文件夹路径=子路径, 状态=OrderStatus.归档中)
        待识别 = self._取图片列表(子路径)
        if not 待识别:
            order.状态 = OrderStatus.标黄人工
            order.异常原因 = "文件夹内无图片"
            return order

        # 1. 分批识别（大模型一次只能识别几张），失败的图片按轮次重试
        轮次 = 0
        while 待识别 and 轮次 < config.MAX_ROUNDS_PER_IMAGE:
            轮次 += 1
            失败 = []
            for 批次 in self._分批(待识别, config.BATCH_SIZE):
                for path, (photo, err) in zip(批次, self._识别一批(批次)):
                    if err is not None or photo is None:
                        失败.append(path)
                        continue
                    # 2. 车牌以文件夹名为准，识别车牌仅作校验
                    if photo.plate and photo.plate != 车牌:
                        print(f"[流水线] 车牌不一致：文件夹={车牌} 识别={photo.plate}（以文件夹名为准）")
                    photo.plate = 车牌
                    order.加照片(photo)
                    # 3. 就地重命名图片 {车牌}_{类别}
                    self.输出器.重命名图片(photo)
            待识别 = 失败

        if 待识别:
            order.状态 = OrderStatus.标黄人工
            order.异常原因 = "识别失败: " + "、".join(os.path.basename(p) for p in 待识别)
            return order

        # 4. 校验五类齐全
        齐全, 原因 = self.校验器.校验(order)
        if not 齐全:
            order.状态 = OrderStatus.标黄人工
            order.异常原因 = 原因
            return order

        # 5. 拼图（二合一/三合一）写进本文件夹
        self.拼图器.生成二合一(order)
        self.拼图器.生成三合一(order)

        # 6. 拼完改文件夹名：{车牌} → {车牌}_{交货单号}
        self.输出器.文件夹改名(order)
        order.状态 = OrderStatus.已拼图
        return order

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
    def _分批(seq: List[str], size: int):
        for i in range(0, len(seq), size):
            yield seq[i:i + size]

    def _取子文件夹(self, 父文件夹: str) -> List[str]:
        if not os.path.isdir(父文件夹):
            return []
        return sorted(
            os.path.join(父文件夹, d) for d in os.listdir(父文件夹)
            if os.path.isdir(os.path.join(父文件夹, d))
        )

    def _取图片列表(self, 文件夹: str) -> List[str]:
        图片 = []
        for filename in os.listdir(文件夹):
            full = os.path.join(文件夹, filename)
            if os.path.isfile(full) and os.path.splitext(filename.lower())[1] in self.支持的扩展名:
                图片.append(full)
        return sorted(图片)
