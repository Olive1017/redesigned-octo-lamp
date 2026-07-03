"""校验器 - 五类齐全校验（第二阶段）"""

from typing import Tuple
from collections import Counter
from models import Order, REQUIRED_LABELS


class Validator:
    """校验器 - 五类齐全校验（无状态，保留 class 仅为统一注入接口）"""

    def 校验(self, order: Order) -> Tuple[bool, str]:
        """
        校验订单是否集齐五类（各类恰好 1 张）
        返回: (是否齐全, 异常原因)
        """
        label_counts = Counter(p.label for p in order.photos if p.label is not None)
        缺失 = [l.value for l in REQUIRED_LABELS if label_counts.get(l, 0) == 0]
        重复 = [f"{l.value}×{label_counts[l]}" for l in REQUIRED_LABELS if label_counts.get(l, 0) > 1]
        问题 = []
        if 缺失:
            问题.append("缺少: " + "、".join(缺失))
        if 重复:
            问题.append("重复: " + "、".join(重复))
        if 问题:
            return False, "；".join(问题)
        return True, ""
