"""订单数据模型"""

from dataclasses import dataclass, field
from typing import List, Optional
from collections import Counter
from domain.enums import PhotoLabel, OrderStatus, REQUIRED_LABELS
from domain.photo import Photo


@dataclass
class Order:
    """订单对象 - 数据 + 纯查询，不碰 Pillow/文件系统/网络"""
    车牌: str
    photos: List[Photo] = field(default_factory=list)
    状态: OrderStatus = OrderStatus.待处理
    异常原因: Optional[str] = None
    文件夹路径: Optional[str] = None
    二合一路径: Optional[str] = None
    三合一路径: Optional[str] = None

    def 加照片(self, photo: Photo):
        """添加照片"""
        self.photos.append(photo)

    def 取(self, label: PhotoLabel) -> List[Photo]:
        """按标识取照片列表"""
        return [p for p in self.photos if p.label == label]

    def 是否齐全(self) -> bool:
        """校验五类照片是否齐全（各类恰好 1 张）"""
        label_counts = Counter(p.label for p in self.photos if p.label is not None)
        return all(label_counts.get(label, 0) == 1 for label in REQUIRED_LABELS)

    @property
    def 交货单号(self) -> Optional[str]:
        """从「回单」照片取交货单号"""
        回单照片s = self.取(PhotoLabel.回单)
        if 回单照片s:
            return 回单照片s[0].交货单号
        return None

    @property
    def 销售订单号(self) -> Optional[str]:
        """从「回单」照片取销售订单号（留给 RPA）"""
        回单照片s = self.取(PhotoLabel.回单)
        if 回单照片s:
            return 回单照片s[0].销售订单号
        return None
