"""校验器 - 五类齐全校验（第二阶段）"""

from typing import Tuple
from collections import Counter
from core.models import Order, 可靠标识


class Validator:
    """校验器 - 五类齐全校验（无状态，保留 class 仅为统一注入接口）"""

    def 校验(self, order: Order) -> Tuple[bool, str]:
        """
        校验订单是否集齐三类（验车、回单、轨迹 各恰好 1 张）
        返回: (是否齐全, 异常原因)
        """
        label_counts = Counter(p.label for p in order.photos if p.label is not None)

        # 只检查可靠标识（验车、回单、轨迹）
        缺失 = [l.value for l in 可靠标识 if label_counts.get(l, 0) == 0]
        重复 = [f"{l.value}×{label_counts[l]}" for l in 可靠标识 if label_counts.get(l, 0) > 1]

        问题 = []
        if 缺失:
            问题.append("缺少: " + "、".join(缺失))
        if 重复:
            问题.append("重复: " + "、".join(重复))
        if 问题:
            return False, "；".join(问题)
        return True, ""

