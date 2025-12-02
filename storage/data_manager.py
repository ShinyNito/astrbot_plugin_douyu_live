"""数据持久化管理模块"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, TYPE_CHECKING

from astrbot.api import logger
from astrbot.api.star import StarTools

if TYPE_CHECKING:
    from ..models.room import RoomInfo


class DataManager:
    """数据管理器
    
    负责插件数据的加载、保存和管理。
    数据存储在 JSON 文件中。
    """

    def __init__(self, plugin_name: str = "astrbot_plugin_douyu_live"):
        """初始化数据管理器
        
        Args:
            plugin_name: 插件名称，用于确定数据目录
        """
        self.data_dir: Path = StarTools.get_data_dir(plugin_name)
        self.data_file: Path = self.data_dir / "douyu_live_data.json"
        
        # 数据结构 - 使用 dict 存储，运行时转换为 RoomInfo
        self.subscriptions: dict[int, set[str]] = {}  # room_id -> set of umo
        self.room_info: dict[int, RoomInfo] = {}  # room_id -> RoomInfo
        
        # 加载数据
        self.load()

    def load(self) -> None:
        """从文件加载数据"""
        from ..models.room import RoomInfo as RoomInfoClass
        
        if not os.path.exists(self.data_file):
            self.subscriptions = {}
            self.room_info = {}
            return

        try:
            with open(self.data_file, encoding="utf-8") as f:
                data = json.load(f)
                # 将字符串键转为整数
                self.subscriptions = {
                    int(k): set(v) for k, v in data.get("subscriptions", {}).items()
                }
                self.room_info = {
                    int(k): RoomInfoClass(**v) for k, v in data.get("room_info", {}).items()
                }
        except Exception as e:
            logger.error(f"加载斗鱼直播数据失败: {e}")
            self.subscriptions = {}
            self.room_info = {}

    def save(self) -> None:
        """保存数据到文件"""
        try:
            data = {
                "subscriptions": {
                    str(k): list(v) for k, v in self.subscriptions.items()
                },
                "room_info": {
                    str(k): v.to_dict() for k, v in self.room_info.items()
                },
            }
            with open(self.data_file, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"保存斗鱼直播数据失败: {e}")

    # ==================== 房间管理 ====================

    def add_room(self, room_id: int, info: RoomInfo) -> None:
        """添加房间
        
        Args:
            room_id: 房间号
            info: 房间信息
        """
        self.room_info[room_id] = info
        if room_id not in self.subscriptions:
            self.subscriptions[room_id] = set()
        self.save()

    def remove_room(self, room_id: int) -> bool:
        """删除房间
        
        Args:
            room_id: 房间号
            
        Returns:
            是否成功删除
        """
        if room_id not in self.room_info:
            return False
        del self.room_info[room_id]
        if room_id in self.subscriptions:
            del self.subscriptions[room_id]
        self.save()
        return True

    def get_room(self, room_id: int) -> RoomInfo | None:
        """获取房间信息
        
        Args:
            room_id: 房间号
            
        Returns:
            房间信息，不存在返回 None
        """
        return self.room_info.get(room_id)

    def has_room(self, room_id: int) -> bool:
        """检查房间是否存在"""
        return room_id in self.room_info

    def get_all_rooms(self) -> dict[int, RoomInfo]:
        """获取所有房间"""
        return self.room_info.copy()

    def update_room(self, room_id: int, **kwargs: Any) -> bool:
        """更新房间信息
        
        Args:
            room_id: 房间号
            **kwargs: 要更新的字段
            
        Returns:
            是否成功更新
        """
        if room_id not in self.room_info:
            return False
        for key, value in kwargs.items():
            if hasattr(self.room_info[room_id], key):
                setattr(self.room_info[room_id], key, value)
        self.save()
        return True

    # ==================== 订阅管理 ====================

    def subscribe(self, room_id: int, umo: str) -> bool:
        """添加订阅
        
        Args:
            room_id: 房间号
            umo: unified_msg_origin
            
        Returns:
            是否成功（False 表示已订阅）
        """
        if room_id not in self.subscriptions:
            self.subscriptions[room_id] = set()
        if umo in self.subscriptions[room_id]:
            return False
        self.subscriptions[room_id].add(umo)
        self.save()
        return True

    def unsubscribe(self, room_id: int, umo: str) -> bool:
        """取消订阅
        
        Args:
            room_id: 房间号
            umo: unified_msg_origin
            
        Returns:
            是否成功（False 表示未订阅）
        """
        if room_id not in self.subscriptions:
            return False
        if umo not in self.subscriptions[room_id]:
            return False
        self.subscriptions[room_id].discard(umo)
        self.save()
        return True

    def get_subscribers(self, room_id: int) -> set[str]:
        """获取房间的订阅者"""
        return self.subscriptions.get(room_id, set()).copy()

    def get_user_subscriptions(self, umo: str) -> list[int]:
        """获取用户订阅的房间列表"""
        return [
            room_id
            for room_id, subscribers in self.subscriptions.items()
            if umo in subscribers
        ]

    def get_total_subscriptions(self) -> int:
        """获取总订阅数"""
        return sum(len(s) for s in self.subscriptions.values())
