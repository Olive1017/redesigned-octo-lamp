"""拼图器 - Pillow 二合一/三合一拼图（第二阶段）

Collager 只持配置，实际图像拼接为模块级纯函数。
二合一 = 验车 | 回单（左右，按高对齐）
三合一 = 轨迹（上，横跨满宽）+ 提货车头 | 送达车头（下，左右）
等比缩放对齐、白底。
"""

import os
from typing import List, Optional
from PIL import Image
from core.models import Order, PhotoLabel
from core import naming
import config


class Collager:
    """拼图器 - 持配置 + 调用纯函数完成拼接"""

    def __init__(self):
        self.背景色 = config.COLLAGE_BACKGROUND_COLOR
        self.质量 = config.COLLAGE_QUALITY

    def 生成二合一(self, order: Order) -> Optional[str]:
        """二合一 = 验车 | 回单，输出 {车牌}_二合一.jpg 到订单文件夹"""
        验车 = order.取(PhotoLabel.验车)
        回单 = order.取(PhotoLabel.回单)
        if not 验车 or not 回单 or not order.文件夹路径:
            return None
        画布 = _横向拼接([_打开(验车[0].path), _打开(回单[0].path)], self.背景色)
        out = os.path.join(order.文件夹路径, naming.拼图名(order.车牌, "二合一"))
        _保存(画布, out, self.质量)
        order.二合一路径 = out
        return out

    def 生成三合一(self, order: Order) -> Optional[str]:
        """三合一 = 轨迹（上） + 提货车头 | 送达车头（下），输出 {车牌}_三合一.jpg"""
        轨迹 = order.取(PhotoLabel.轨迹)
        提货 = order.取(PhotoLabel.提货车头)
        送达 = order.取(PhotoLabel.送达车头)
        if not 轨迹 or not 提货 or not 送达 or not order.文件夹路径:
            return None
        下排 = _横向拼接([_打开(提货[0].path), _打开(送达[0].path)], self.背景色)
        上图 = _按宽缩放(_打开(轨迹[0].path), 下排.width)
        画布 = _纵向拼接([上图, 下排], self.背景色)
        out = os.path.join(order.文件夹路径, naming.拼图名(order.车牌, "三合一"))
        _保存(画布, out, self.质量)
        order.三合一路径 = out
        return out


# ---- 图像处理纯函数 ----

def _打开(path: str) -> Image.Image:
    img = Image.open(path)
    return img.convert("RGB")


def _按高缩放(img: Image.Image, 目标高: int) -> Image.Image:
    if img.height == 目标高:
        return img
    比例 = 目标高 / img.height
    return img.resize((max(1, round(img.width * 比例)), 目标高), Image.Resampling.LANCZOS)


def _按宽缩放(img: Image.Image, 目标宽: int) -> Image.Image:
    if img.width == 目标宽:
        return img
    比例 = 目标宽 / img.width
    return img.resize((目标宽, max(1, round(img.height * 比例))), Image.Resampling.LANCZOS)


def _横向拼接(imgs: List[Image.Image], 背景色) -> Image.Image:
    """按最大高度等比对齐，左右拼接"""
    目标高 = max(im.height for im in imgs)
    缩放后 = [_按高缩放(im, 目标高) for im in imgs]
    总宽 = sum(im.width for im in 缩放后)
    画布 = Image.new("RGB", (总宽, 目标高), 背景色)
    x = 0
    for im in 缩放后:
        画布.paste(im, (x, 0))
        x += im.width
    return 画布


def _纵向拼接(imgs: List[Image.Image], 背景色) -> Image.Image:
    """按最大宽度对齐，上下拼接，窄图居中"""
    目标宽 = max(im.width for im in imgs)
    缩放后 = [_按宽缩放(im, 目标宽) if im.width != 目标宽 else im for im in imgs]
    总高 = sum(im.height for im in 缩放后)
    画布 = Image.new("RGB", (目标宽, 总高), 背景色)
    y = 0
    for im in 缩放后:
        x = (目标宽 - im.width) // 2
        画布.paste(im, (x, y))
        y += im.height
    return 画布


def _保存(img: Image.Image, path: str, 质量: int):
    img.save(path, format="JPEG", quality=质量)
