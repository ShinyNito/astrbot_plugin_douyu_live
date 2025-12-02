"""通知发送模块"""

import time
from typing import TYPE_CHECKING

from astrbot.api import logger
from astrbot.api.event import MessageEventResult
from astrbot.api.message_components import AtAll, Plain

if TYPE_CHECKING:
    from astrbot.api import star


class Notifier:
    """通知发送器
    
    负责构建和发送开播通知消息。
    """

    def __init__(self, context: "star.Context"):
        """初始化通知器
        
        Args:
            context: AstrBot 上下文
        """
        self.context = context

    def build_notification(
        self,
        room_id: int,
        room_name: str,
        timestamp: float | None = None,
    ) -> str:
        """构建开播通知消息文本
        
        Args:
            room_id: 房间号
            room_name: 房间/主播名称
            timestamp: 时间戳，默认当前时间
            
        Returns:
            格式化的通知消息
        """
        if timestamp is None:
            timestamp = time.time()
        
        time_str = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(timestamp))
        live_url = f"https://www.douyu.com/{room_id}"

        return (
            f"🎉 斗鱼直播开播通知\n"
            f"━━━━━━━━━━━━━━\n"
            f"👤 主播: {room_name}\n"
            f"🔢 房间号: {room_id}\n"
            f"⏰ 时间: {time_str}\n"
            f"🔗 链接: {live_url}\n"
            f"━━━━━━━━━━━━━━\n"
            f"快去观看吧！"
        )

    async def send_to_subscribers(
        self,
        subscribers: set[str],
        message: str,
        at_all: bool = False,
    ) -> None:
        """发送通知给所有订阅者
        
        Args:
            subscribers: 订阅者的 unified_msg_origin 集合
            message: 通知消息内容
            at_all: 是否 @全体成员
        """
        for umo in subscribers:
            try:
                result = MessageEventResult()
                if at_all:
                    result.chain.append(AtAll())
                    result.chain.append(Plain("\n"))
                result.chain.append(Plain(message))
                await self.context.send_message(umo, result)
                logger.info(f"已发送开播通知到: {umo}")
            except Exception as e:
                logger.error(f"发送通知失败 ({umo}): {e}")
