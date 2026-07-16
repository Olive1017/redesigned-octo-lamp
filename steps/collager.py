"""拼图器 - Pillow 二合一/三合一拼图（第二阶段）

Collager 只持配置，实际图像拼接为模块级纯函数。
二合一 = 验车 | 回单（左右，按高对齐）
三合一 = 顶部信息条（销售订单号+车牌号，白底黑字）+ 轨迹（横跨满宽）+ 提货车头 | 送达车头（下，左右）
等比缩放对齐、白底。
"""

import os
from typing import List, Optional
from core.models import Order, PhotoLabel
from core import naming
import config
from PIL import Image, ImageDraw, ImageFont, ImageOps
import logging


class Collager:
    """拼图器 - 持配置 + 调用纯函数完成拼接"""

    def __init__(self):
        self.背景色 = config.COLLAGE_BACKGROUND_COLOR
        self.质量 = config.COLLAGE_QUALITY
        self.字体 = _加载字体(config.LABEL_BANNER_FONT_SIZE)

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
        """三合一 = 顶部信息条 + 轨迹（上） + 提货车头 | 送达车头（下），输出 {车牌}_三合一.jpg"""
        轨迹 = order.取(PhotoLabel.轨迹)
        车头 = order.车头对()  # 剩下两张，不分提货/送达、左右无所谓
        if not 轨迹 or len(车头) != 2 or not order.文件夹路径:
            return None
        下排 = _横向拼接([_打开(车头[0].path), _打开(车头[1].path)], self.背景色)
        上图 = _按宽缩放(_打开(轨迹[0].path), 下排.width)
        # 下面信息条 + 纵向拼接保持不变
        # 顶部信息条：销售订单号 + 车牌号（白底黑字）
        文本 = f"销售订单号：{order.销售订单号 or '无'}    车牌号：{order.车牌}"
        信息条 = _文字条(文本, 下排.width, self.字体, config.LABEL_BANNER_FG, config.LABEL_BANNER_BG)
        画布 = _纵向拼接([信息条, 上图, 下排], self.背景色)
        out = os.path.join(order.文件夹路径, naming.拼图名(order.车牌, "三合一"))
        _保存(画布, out, self.质量)
        order.三合一路径 = out
        return out


# ---- 图像处理纯函数 ----

def _加载字体(字号: int):
    """按候选列表找第一个可用的中文字体，找不到退回默认字体"""
    for p in config.LABEL_FONT_CANDIDATES:
        if os.path.exists(p):
            try:
                return ImageFont.truetype(p, 字号)
            except Exception:
                continue
    logging.getLogger(__name__).warning(
        "[拼图器] 警告：未找到可用中文字体，信息条可能显示为方框。请在 config.LABEL_FONT_CANDIDATES 补充字体路径。"
    )
    return ImageFont.load_default()


def _文字条(文本: str, 宽度: int, 字体, 前景色=(0, 0, 0), 背景色=(255, 255, 255)) -> Image.Image:
    """生成一条白底黑字、文字水平居中的信息条，宽度与拼图对齐"""
    padding = config.LABEL_BANNER_PADDING
    量尺 = ImageDraw.Draw(Image.new("RGB", (宽度, 10), 背景色))
    bbox = 量尺.textbbox((0, 0), 文本, font=字体)
    文本宽, 文本高 = bbox[2] - bbox[0], bbox[3] - bbox[1]
    条高 = 文本高 + padding * 2
    条 = Image.new("RGB", (宽度, 条高), 背景色)
    d = ImageDraw.Draw(条)
    x = (宽度 - 文本宽) // 2 - bbox[0]
    y = padding - bbox[1]
    d.text((x, y), 文本, fill=前景色, font=字体)
    return 条


def _打开(path: str) -> Image.Image:
    img = Image.open(path)
    img = ImageOps.exif_transpose(img)
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
