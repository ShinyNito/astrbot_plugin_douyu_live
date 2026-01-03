"""订阅配置数据模型"""

from dataclasses import asdict, dataclass
from typing import Any

from ..utils.constants import DEFAULT_HIGH_VALUE_THRESHOLD

@dataclass
class SubscriptionConfig:
    """订阅配置

    每个群对每个房间的独立配置。

    Attributes:
        at_all: 是否开启 @全体成员（开播通知）
        gift_notify: 是否开启礼物播报
        high_value_only: 是否只播报高价值礼物（兼容旧字段）
        high_value_threshold: 高价值过滤阈值（基于礼物价值）
    """

    at_all: bool = False
    gift_notify: bool = False
    high_value_only: bool = True  # 默认只播报高价值礼物（兼容旧字段）
    high_value_threshold: int | None = DEFAULT_HIGH_VALUE_THRESHOLD

    def to_dict(self) -> dict[str, Any]:
        """转换为字典"""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SubscriptionConfig":
        """从字典创建实例"""
        raw_threshold = data.get("high_value_threshold")
        if raw_threshold is not None:
            try:
                parsed_threshold = int(raw_threshold)
            except (TypeError, ValueError):
                parsed_threshold = DEFAULT_HIGH_VALUE_THRESHOLD
        else:
            parsed_threshold = None
            if data.get("high_value_only", True):
                parsed_threshold = DEFAULT_HIGH_VALUE_THRESHOLD

        if raw_threshold is not None:
            high_value_only = parsed_threshold is not None
        else:
            high_value_only = data.get("high_value_only", True)

        return cls(
            at_all=data.get("at_all", False),
            gift_notify=data.get("gift_notify", False),
            high_value_only=high_value_only,
            high_value_threshold=parsed_threshold,
        )
