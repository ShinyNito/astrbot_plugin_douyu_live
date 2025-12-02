"""斗鱼直播监控器模块"""

import time
from collections.abc import Callable
from threading import Thread

from astrbot.api import logger

try:
    from pydouyu.client import Client

    PYDOUYU_AVAILABLE = True
except ImportError:
    PYDOUYU_AVAILABLE = False
    Client = None
    logger.warning("pydouyu 库未安装，请运行: pip install pydouyu")


class DouyuMonitor:
    """斗鱼直播监控器

    使用 pydouyu 库监控指定直播间的开播状态和礼物消息，
    当检测到开播或收到礼物时通过回调函数通知上层。
    """

    def __init__(
        self,
        room_id: int,
        live_callback: Callable[[int, dict], None] | None = None,
        gift_callback: Callable[[int, dict], None] | None = None,
        offline_callback: Callable[[int, float], None] | None = None,
    ):
        """初始化监控器

        Args:
            room_id: 斗鱼直播间房间号
            live_callback: 开播回调函数，参数为 (room_id, msg)
            gift_callback: 礼物回调函数，参数为 (room_id, msg)
            offline_callback: 下播回调函数，参数为 (room_id, duration_seconds)
        """
        self.room_id = room_id
        self.live_callback = live_callback
        self.gift_callback = gift_callback
        self.offline_callback = offline_callback
        self.client: Client | None = None
        self.running = False
        self.thread: Thread | None = None
        # 使用 None 表示未知状态，避免首次消息误判
        self.last_live_status: bool | None = None
        self._stop_flag = False  # 停止标志
        self.live_start_time: float | None = None  # 开播时间戳
        self._connect_time: float | None = None  # 连接时间，用于启动稳定期
        self._stable_delay = 10.0  # 启动后 10 秒内忽略状态变化

    def _rss_handler(self, msg: dict) -> None:
        """处理直播状态变化

        Args:
            msg: pydouyu 的 rss 事件消息
        """
        try:
            ss = msg.get("ss", "0")
            ivl = msg.get("ivl", "1")
            # ss='1' 表示正在直播, ivl='0' 表示不是回放
            is_live = ss == "1" and ivl == "0"

            # 检查是否在启动稳定期内
            if self._connect_time is not None:
                elapsed = time.time() - self._connect_time
                if elapsed < self._stable_delay:
                    # 在稳定期内，只更新状态，不触发通知
                    if self.last_live_status is None:
                        logger.info(
                            f"斗鱼直播间 {self.room_id} 初始状态: "
                            f"{'直播中' if is_live else '未开播'} (稳定期内)"
                        )
                    self.last_live_status = is_live
                    if is_live and self.live_start_time is None:
                        self.live_start_time = time.time()
                    return

            # 首次收到稳定期后的状态消息
            if self.last_live_status is None:
                logger.info(
                    f"斗鱼直播间 {self.room_id} 状态: {'直播中' if is_live else '未开播'}"
                )
                self.last_live_status = is_live
                if is_live:
                    self.live_start_time = time.time()
                return

            if is_live and not self.last_live_status:
                # 从未开播变为开播，触发通知
                logger.info(f"斗鱼直播间 {self.room_id} 开播了!")
                self.live_start_time = time.time()  # 记录开播时间
                if self.live_callback:
                    self.live_callback(self.room_id, msg)

            elif not is_live and self.last_live_status:
                # 从开播变为下播，触发下播通知
                logger.info(f"斗鱼直播间 {self.room_id} 下播了!")
                duration = 0.0
                if self.live_start_time:
                    duration = time.time() - self.live_start_time
                    self.live_start_time = None
                if self.offline_callback:
                    self.offline_callback(self.room_id, duration)

            self.last_live_status = is_live
        except Exception as e:
            logger.error(f"处理直播状态时出错: {e}")

    def _dgb_handler(self, msg: dict) -> None:
        """处理礼物消息

        Args:
            msg: pydouyu 的 dgb 礼物消息

        消息字段说明：
            - nn: 用户昵称
            - uid: 用户 ID
            - gfid: 礼物 ID
            - gfcnt / hits: 礼物数量
            - level: 用户等级
        """
        try:
            if self.gift_callback:
                self.gift_callback(self.room_id, msg)
        except Exception as e:
            logger.error(f"处理礼物消息时出错: {e}")

    def _run_client(self) -> None:
        """在线程中运行客户端"""
        try:
            # 创建 Client 实例
            self.client = Client(room_id=self.room_id)
            # 注册直播状态处理器
            self.client.add_handler("rss", self._rss_handler)
            # 注册礼物消息处理器
            self.client.add_handler("dgb", self._dgb_handler)
            self.running = True
            # 记录连接时间，用于启动稳定期
            self._connect_time = time.time()
            logger.info(f"斗鱼监控器 {self.room_id} 连接中...")

            # client.start() 会启动内部线程，立即返回
            # 内部线程 (message_worker, heartbeat_worker) 会处理重连
            self.client.start()
            logger.info(
                f"斗鱼监控器 {self.room_id} 已启动 "
                f"(启动稳定期 {self._stable_delay:.0f} 秒)"
            )

            # 等待内部线程结束或收到停止信号
            # message_worker 是一个 Thread，我们等待它
            if hasattr(self.client, "message_worker") and self.client.message_worker:
                while not self._stop_flag and self.client.message_worker.is_alive():
                    time.sleep(1)

        except Exception as e:
            logger.error(f"斗鱼监控器 {self.room_id} 运行出错: {e}")
        finally:
            self.running = False
            self._cleanup_client()

    def _cleanup_client(self) -> None:
        """清理客户端资源"""
        if self.client:
            try:
                self.client.stop()
            except Exception:
                pass
            self.client = None

    def start(self) -> bool:
        """启动监控

        Returns:
            是否成功启动
        """
        if not PYDOUYU_AVAILABLE:
            logger.error("pydouyu 库未安装，无法启动监控")
            return False

        if self.running:
            return True

        self._stop_flag = False
        self.thread = Thread(target=self._run_client, daemon=True)
        self.thread.start()
        return True

    def stop(self) -> None:
        """停止监控"""
        self._stop_flag = True
        self.running = False
        self._cleanup_client()
        logger.info(f"斗鱼直播间 {self.room_id} 监控已停止")

