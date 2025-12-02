"""房间信息数据模型"""

from dataclasses import dataclass, field, asdict
from typing import Any


@dataclass
class RoomInfo:
    """直播间信息
    
    Attributes:
        name: 主播/房间名称
        added_by: 添加者 ID
        added_time: 添加时间
        at_all: 是否开启 @全体成员
    """
    name: str
    added_by: str = ""
    added_time: str = ""
    at_all: bool = False

    def to_dict(self) -> dict[str, Any]:
        """转换为字典"""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "RoomInfo":
        """从字典创建实例"""
        return cls(
            name=data.get("name", ""),
            added_by=data.get("added_by", ""),
            added_time=data.get("added_time", ""),
            at_all=data.get("at_all", False),
        )
