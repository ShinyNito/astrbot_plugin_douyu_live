"""订阅配置数据模型"""

from dataclasses import asdict, dataclass
from typing import Any


@dataclass
class SubscriptionConfig:
    """订阅配置

    每个群对每个房间的独立配置。

    Attributes:
        at_all: 是否开启 @全体成员（开播通知）
        gift_notify: 是否开启礼物播报
        high_value_only: 是否只播报高价值礼物（飞机及以上）
    """

    at_all: bool = False
    gift_notify: bool = False
    high_value_only: bool = True  # 默认只播报高价值礼物

    def to_dict(self) -> dict[str, Any]:
        """转换为字典"""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SubscriptionConfig":
        """从字典创建实例"""
        return cls(
            at_all=data.get("at_all", False),
            gift_notify=data.get("gift_notify", False),
            high_value_only=data.get("high_value_only", True),
        )
