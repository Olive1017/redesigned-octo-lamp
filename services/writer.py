"""输出器 - 第一阶段：归档 + 收尾定名"""

import os
import shutil
from pathlib import Path
from typing import Dict
from domain.photo import Photo
from domain.order import Order
import config


class Writer:
    """输出器 - 归档 + 收尾定名

    归档采用「移动」而非「复制」：照片被移出初始文件夹、放进对应子文件夹，
    这样初始文件夹里的散落图片会逐步减少。配合流水线的分批循环，可作为循环
    终止判据（初始文件夹里只剩子文件夹、无散落图片时结束）。
    """

    待定文件夹名 = "_待定"
    失败文件夹名 = "_识别失败"

    def __init__(self, output_dir: str = None):
        self.output_dir = output_dir or config.OUTPUT_DIR

    def 归档(self, photo: Photo) -> str:
        子文件夹 = self.待定文件夹名 if photo.plate is None else photo.plate
        target = self._移动到(photo.path, 子文件夹)
        photo.path = target
        return target

    def 移入失败(self, photo: Photo) -> str:
        target = self._移动到(photo.path, self.失败文件夹名)
        photo.path = target
        return target

    def _移动到(self, src: str, 子文件夹: str) -> str:
        folder = os.path.join(self.output_dir, 子文件夹)
        Path(folder).mkdir(parents=True, exist_ok=True)
        filename = os.path.basename(src)
        target = os.path.join(folder, filename)

        if os.path.abspath(src) == os.path.abspath(target):
            return target

        if os.path.exists(target):
            name, ext = os.path.splitext(filename)
            counter = 1
            while True:
                target = os.path.join(folder, f"{name}_{counter}{ext}")
                if not os.path.exists(target):
                    break
                counter += 1

        shutil.move(src, target)
        return target

    def 收尾定名(self, 订单表: Dict[str, Order]):
        for plate, order in 订单表.items():
            交货单号 = order.交货单号
            if not 交货单号:
                order.文件夹路径 = os.path.join(self.output_dir, plate)
                continue

            old_folder = os.path.join(self.output_dir, plate)
            new_folder = os.path.join(self.output_dir, f"{plate}_{交货单号}")

            if old_folder != new_folder:
                if os.path.exists(new_folder):
                    self._合并文件夹(old_folder, new_folder)
                    shutil.rmtree(old_folder)
                else:
                    os.rename(old_folder, new_folder)

            order.文件夹路径 = new_folder

    @staticmethod
    def _合并文件夹(src: str, dst: str):
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
