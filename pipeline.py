"""流水线编排 - 第一阶段：识别 + 归档"""

import os
from dataclasses import dataclass
from typing import Dict, List, Optional, Callable
from domain.order import Order, OrderStatus
from domain.photo import Photo
from services.recognizer import Recognizer
from services.writer import Writer
import config


@dataclass
class 运行结果:
    """运行结果 - 第一阶段"""
    订单表: Dict[str, Order]
    已归档: List[Order]
    待定: List[Photo]


class 流水线:
    """流水线编排 - 第一阶段：识别 + 归档"""

    def __init__(
        self,
        识别器: Recognizer,
        输出器: Writer,
    ):
        self.识别器 = 识别器
        self.输出器 = 输出器

    def 运行(
        self,
        输入文件夹: str,
        进度回调: Optional[Callable[[int, int, str], None]] = None,
    ) -> 运行结果:
        """
        运行流水线（第一阶段：边识别边归档）
        输入文件夹: 包含照片的文件夹
        进度回调: 回调函数(已处理数, 总数, 当前文件名)
        返回: 运行结果（订单表、已归档、待定）
        """
        # 1. 遍历文件夹取图片
        图片列表 = self._取图片列表(输入文件夹)
        总数 = len(图片列表)
        if 总数 == 0:
            return 运行结果(订单表={}, 已归档=[], 待定=[])

        订单表: Dict[str, Order] = {}
        待定列表: List[Photo] = []
        已处理 = 0

        # 2. 遍历图片：识别 → 归档
        for path in 图片列表:
            try:
                # 识别
                photo = self.识别器.识别(path)
                photo.状态 = OrderStatus.归档中

                # 归档
                self.输出器.归档(photo)
                photo.状态 = OrderStatus.已归档

                # 按车牌分组
                if photo.plate is None:
                    # 无车牌，计入待定
                    待定列表.append(photo)
                else:
                    # 有车牌，加入订单表
                    if photo.plate not in 订单表:
                        订单表[photo.plate] = Order(车牌=photo.plate, 状态=OrderStatus.归档中)
                    订单表[photo.plate].加照片(photo)

            except Exception as e:
                # 识别失败，创建待定照片
                filename = os.path.basename(path)
                photo = Photo(path=path)
                待定列表.append(photo)
                print(f"[流水线] 识别失败 {filename}: {e}")

            finally:
                已处理 += 1
                if 进度回调:
                    进度回调(已处理, 总数, os.path.basename(path))

        # 3. 收尾：重命名文件夹
        self.输出器.收尾定名(订单表)

        # 更新订单状态
        for order in 订单表.values():
            order.状态 = OrderStatus.已归档

        已归档列表 = list(订单表.values())

        return 运行结果(
            订单表=订单表,
            已归档=已归档列表,
            待定=待定列表,
        )

    @staticmethod
    def _取图片列表(文件夹: str) -> List[str]:
        """获取文件夹内所有图片文件（jpg, jpeg, png, bmp, pdf）"""
        支持的扩展名 = {'.jpg', '.jpeg', '.png', '.bmp', '.pdf'}
        图片列表 = []
        if not os.path.exists(文件夹):
            return 图片列表

        for filename in os.listdir(文件夹):
            if os.path.splitext(filename.lower())[1] in 支持的扩展名:
                图片列表.append(os.path.join(文件夹, filename))

        return 图片列表
