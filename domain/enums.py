"""枚举定义"""

from enum import Enum


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
