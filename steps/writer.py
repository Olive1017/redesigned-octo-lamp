"""输出器 - 第一阶段：归档（移动+按车牌_类别改名） + 收尾定名"""

import os
import shutil
from pathlib import Path
from typing import Dict
from core.models import Photo, Order
from core import naming
import config


class Writer:
    """输出器 - 归档 + 收尾定名

    归档采用「移动」而非「复制」：照片被移出初始文件夹、放进对应子文件夹，
    并按 {车牌}_{类别} 重命名。初始文件夹里的散落图片会逐步减少，作为循环终止判据。
    """

    待定文件夹名 = "_待定"
    失败文件夹名 = "_识别失败"

    def __init__(self, output_dir: str = None):
        self.output_dir = output_dir or config.OUTPUT_DIR

    def 归档(self, photo: Photo) -> str:
        """
        归档单张照片（移动，来一张移一张）
        无车牌 → _待定/（保留原名）
        有车牌且有类别 → {车牌}/，重命名为 {车牌}_{类别}{ext}
        有车牌但无类别 → {车牌}/，保留原名
        返回: 目标文件路径
        """
        _, ext = os.path.splitext(os.path.basename(photo.path))
        if photo.plate is None:
            子文件夹 = self.待定文件夹名
            目标文件名 = os.path.basename(photo.path)
        else:
            子文件夹 = photo.plate
            if photo.label is not None:
                目标文件名 = naming.图片名(photo.plate, photo.label, ext)
            else:
                目标文件名 = os.path.basename(photo.path)
        target = self._移动到(photo.path, 子文件夹, 目标文件名)
        photo.path = target
        return target

    def 移入失败(self, photo: Photo) -> str:
        """多轮重试仍识别失败 → 移到 _识别失败/，保留原名，等待人工"""
        target = self._移动到(photo.path, self.失败文件夹名, os.path.basename(photo.path))
        photo.path = target
        return target

    def _移动到(self, src: str, 子文件夹: str, 目标文件名: str) -> str:
        """移动文件到 output_dir/子文件夹/目标文件名，同名自动加序号防覆盖"""
        folder = os.path.join(self.output_dir, 子文件夹)
        Path(folder).mkdir(parents=True, exist_ok=True)
        target = os.path.join(folder, 目标文件名)

        if os.path.abspath(src) == os.path.abspath(target):
            return target

        if os.path.exists(target):
            name, ext = os.path.splitext(目标文件名)
            counter = 1
            while True:
                target = os.path.join(folder, f"{name}_{counter}{ext}")
                if not os.path.exists(target):
                    break
                counter += 1

        shutil.move(src, target)
        return target

    def 收尾定名(self, 订单表: Dict[str, Order]):
        """收尾：{车牌}/ → {车牌}_{交货单号}/，无交货单号保持原名"""
        for plate, order in 订单表.items():
            交货单号 = order.交货单号
            old_folder = os.path.join(self.output_dir, plate)
            if not 交货单号:
                order.文件夹路径 = old_folder
                continue

            new_folder = os.path.join(self.output_dir, naming.文件夹名(plate, 交货单号))

            if old_folder != new_folder:
                if os.path.exists(new_folder):
                    self._合并文件夹(old_folder, new_folder)
                    shutil.rmtree(old_folder)
                else:
                    os.rename(old_folder, new_folder)

            order.文件夹路径 = new_folder

    @staticmethod
    def _合并文件夹(src: str, dst: str):
        """合并两个文件夹（dst 已存在，把 src 的文件移进去）"""
        for filename in os.listdir(src):
            src_file = os.path.join(src, filename)
            dst_file = os.path.join(dst, filename)
            if os.path.exists(dst_file):
                name, ext = os.path.splitext(filename)
                counter = 1
                while True:
                    new_name = f"{name}_{counter}{ext}"
                    new_file = os.path.join(dst, new_name)
                    if not os.path.exists(new_file):
                        shutil.move(src_file, new_file)
                        break
                    counter += 1
            else:
                shutil.move(src_file, dst_file)
