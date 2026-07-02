"""输出器 - 第一阶段：归档 + 收尾定名"""

import os
import shutil
from pathlib import Path
from typing import Dict, List
from domain.photo import Photo
from domain.order import Order
import config


class Writer:
    """输出器 - 归档 + 收尾定名"""

    def __init__(self, output_dir: str = None):
        self.output_dir = output_dir or config.OUTPUT_DIR

    def 归档(self, photo: Photo) -> str:
        """
        归档单张照片（幂等，来一张存一张）
        plate is None → 复制到 _待定/，保留原文件名
        有车牌 → {车牌}/，保留原文件名
        返回: 目标文件路径
        """
        if photo.plate is None:
            # 无车牌，放入 _待定/
            folder = os.path.join(self.output_dir, "_待定")
            Path(folder).mkdir(parents=True, exist_ok=True)
            filename = os.path.basename(photo.path)
            target = os.path.join(folder, filename)
        else:
            # 有车牌，放入 {车牌}/
            folder = os.path.join(self.output_dir, photo.plate)
            Path(folder).mkdir(parents=True, exist_ok=True)
            filename = os.path.basename(photo.path)
            target = os.path.join(folder, filename)

        # 复制文件（如果目标已存在则覆盖）
        shutil.copy2(photo.path, target)
        return target

    def 收尾定名(self, 订单表: Dict[str, Order]):
        """
        收尾：对每个有交货单号的订单，重命名文件夹
        {车牌}/ → {车牌}_{交货单号}/
        无交货单号的保持原名
        """
        for plate, order in 订单表.items():
            交货单号 = order.交货单号
            if not 交货单号:
                # 无交货单号，保持原名
                order.文件夹路径 = os.path.join(self.output_dir, plate)
                continue

            # 有交货单号，重命名
            old_folder = os.path.join(self.output_dir, plate)
            new_folder = os.path.join(self.output_dir, f"{plate}_{交货单号}")

            if old_folder != new_folder:
                if os.path.exists(new_folder):
                    # 目标已存在，合并（保留新名称）
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
                # 目标文件已存在，添加序号
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
