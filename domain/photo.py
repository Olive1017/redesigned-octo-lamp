"""照片数据模型"""

from dataclasses import dataclass
from typing import Optional
from domain.enums import PhotoLabel


@dataclass
class Photo:
    """照片对象 - 纯数据，不碰 IO"""
    path: str
    label: Optional[PhotoLabel] = None
    plate: Optional[str] = None
    交货单号: Optional[str] = None
    销售订单号: Optional[str] = None
