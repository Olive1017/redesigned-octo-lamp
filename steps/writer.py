"""输出器 - 就地重命名图片 + 订单文件夹改名 + 幂等判断

人工已按车牌分好子文件夹，因此不再跨文件夹移动/分组：
- 重命名图片：在原子文件夹内把图片改为 {车牌}_{类别}{ext}
- 文件夹改名：{车牌}/ → {车牌}_{交货单号}/
- 是否已处理：幂等判断（文件夹名带交货单号后缀 或 已存在拼图文件）
"""

import os
from typing import Optional
from core.models import Order, Photo
from core import naming


class Writer:
    """输出器 - 就地重命名图片、文件夹改名（不跨文件夹移动）"""

    def 重命名图片(self, photo: Photo) -> str:
        """把图片就地重命名为 {车牌}_{类别}{ext}（同目录）。
        无 label 或无车牌时保持原名。同名自动加序号防覆盖。返回新路径。"""
        if photo.label is None or photo.plate is None:
            return photo.path
        文件夹 = os.path.dirname(photo.path)
        _, ext = os.path.splitext(os.path.basename(photo.path))
        目标名 = naming.图片名(photo.plate, photo.label, ext)
        target = os.path.join(文件夹, 目标名)
        if os.path.abspath(target) == os.path.abspath(photo.path):
            return photo.path
        target = self._防重名(target)
        os.rename(photo.path, target)
        photo.path = target
        return target

    def 文件夹改名(self, order: Order) -> Optional[str]:
        """订单文件夹 {车牌}/ → {车牌}_{交货单号}/。
        无交货单号则不改。同时同步 photos 与拼图路径。返回新路径。"""
        if not order.文件夹路径 or not os.path.isdir(order.文件夹路径):
            return order.文件夹路径
        交货单号 = order.交货单号
        if not 交货单号:
            return order.文件夹路径
        父目录 = os.path.dirname(order.文件夹路径)
        新路径 = os.path.join(父目录, naming.文件夹名(order.车牌, 交货单号))
        if os.path.abspath(新路径) == os.path.abspath(order.文件夹路径):
            return order.文件夹路径
        新路径 = self._防重名目录(新路径)
        os.rename(order.文件夹路径, 新路径)
        # 同步路径前缀
        for p in order.photos:
            p.path = os.path.join(新路径, os.path.basename(p.path))
        if order.二合一路径:
            order.二合一路径 = os.path.join(新路径, os.path.basename(order.二合一路径))
        if order.三合一路径:
            order.三合一路径 = os.path.join(新路径, os.path.basename(order.三合一路径))
        order.文件夹路径 = 新路径
        return 新路径

    @staticmethod
    def 是否已处理(文件夹路径: str) -> bool:
        """幂等判断：文件夹名已带交货单号后缀（含下划线）或已存在拼图文件 → 视为已处理。
        未处理的文件夹名就是纯车牌（无下划线）。"""
        名字 = os.path.basename(文件夹路径.rstrip("/\\"))
        if "_" in 名字:
            return True
        try:
            for f in os.listdir(文件夹路径):
                if "_二合一" in f or "_三合一" in f:
                    return True
        except OSError:
            pass
        return False

    @staticmethod
    def _防重名(target: str) -> str:
        if not os.path.exists(target):
            return target
        folder = os.path.dirname(target)
        name, ext = os.path.splitext(os.path.basename(target))
        counter = 1
        while True:
            候选 = os.path.join(folder, f"{name}_{counter}{ext}")
            if not os.path.exists(候选):
                return 候选
            counter += 1

    @staticmethod
    def _防重名目录(target: str) -> str:
        if not os.path.exists(target):
            return target
        parent = os.path.dirname(target)
        name = os.path.basename(target)
        counter = 1
        while True:
            候选 = os.path.join(parent, f"{name}_{counter}")
            if not os.path.exists(候选):
                return 候选
            counter += 1
