"""领域模型 - 枚举 + Photo + Order（合并自原 domain/，B 档扇平）"""

from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional
from collections import Counter


class PhotoLabel(str, Enum):
    """照片标识 - 与 OCR 返回的「打标识」字段对应"""
    回单 = "回单"
    验车 = "验车"
    轨迹 = "轨迹"
    提货车头 = "提货车头"
    送达车头 = "送达车头"


class OrderStatus(str, Enum):
    """订单状态"""
    待处理 = "待处理"
    归档中 = "归档中"
    已归档 = "已归档"
    已拼图 = "已拼图"
    已上传 = "已上传"
    标黄人工 = "标黄人工"


# 每类照片必需标识
REQUIRED_LABELS = [PhotoLabel.回单, PhotoLabel.验车, PhotoLabel.轨迹, PhotoLabel.提货车头, PhotoLabel.送达车头]


@dataclass
class Photo:
    """照片对象 - 纯数据，不碰 IO"""
    path: str
    label: Optional[PhotoLabel] = None
    plate: Optional[str] = None
    交货单号: Optional[str] = None
    销售订单号: Optional[str] = None


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
