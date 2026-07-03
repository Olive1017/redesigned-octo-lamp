"""命名规则 - 集中管理，writer 与 collager 复用（纯函数）"""

from typing import Optional
from core.models import PhotoLabel


def 图片名(plate: str, label: PhotoLabel, ext: str) -> str:
    """原始图片重命名：{车牌}_{类别}{ext}，如 粤A12345_回单.jpg"""
    return f"{plate}_{label.value}{ext}"


def 拼图名(plate: str, 类型: str, ext: str = ".jpg") -> str:
    """拼图命名：{车牌}_{二合一/三合一}{ext}"""
    return f"{plate}_{类型}{ext}"


def 文件夹名(plate: str, 交货单号: Optional[str]) -> str:
    """订单文件夹名：有交货单号 → {车牌}_{交货单号}，否则 {车牌}"""
    if 交货单号:
        return f"{plate}_{交货单号}"
    return plate
