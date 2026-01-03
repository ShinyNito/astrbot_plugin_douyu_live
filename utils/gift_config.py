"""斗鱼礼物配置加载与缓存"""

from __future__ import annotations

import json
import time

import httpx

from .constants import DEFAULT_GIFT_NAME, GIFT_NAMES

GIFT_CONFIG_URL = (
    "https://webconf.douyucdn.cn/resource/common/prop_gift_list/prop_gift_config.json"
)
JSONP_PREFIX = "DYConfigCallback("

_GIFT_NAME_CACHE: dict[str, str] = {}
_LAST_UPDATE_TS: float | None = None


def _strip_jsonp(payload: str) -> str:
    payload = payload.strip()
    if payload.startswith(JSONP_PREFIX) and payload.endswith(")"):
        return payload[len(JSONP_PREFIX) : -1]
    return payload


def _parse_gift_mapping(data: dict) -> dict[str, str]:
    mapping: dict[str, str] = {}
    for gift_id, info in data.get("data", {}).items():
        if not isinstance(info, dict):
            continue
        name = info.get("name")
        if name:
            mapping[str(gift_id)] = str(name)
    return mapping


def update_gift_config() -> int:
    """拉取斗鱼礼物配置并刷新缓存.

    Returns:
        加载到的礼物数量（如果拉取失败则抛异常）
    """
    response = httpx.get(GIFT_CONFIG_URL, timeout=10.0)
    response.raise_for_status()

    raw_json = _strip_jsonp(response.text)
    data = json.loads(raw_json)

    mapping = _parse_gift_mapping(data)
    if mapping:
        _GIFT_NAME_CACHE.clear()
        _GIFT_NAME_CACHE.update(mapping)
        global _LAST_UPDATE_TS
        _LAST_UPDATE_TS = time.time()

    return len(_GIFT_NAME_CACHE)


def get_gift_name(gift_id: str | int) -> str:
    """获取礼物名称（优先使用在线配置）"""
    gift_key = str(gift_id)
    return _GIFT_NAME_CACHE.get(
        gift_key, GIFT_NAMES.get(gift_key, f"{DEFAULT_GIFT_NAME}({gift_id})")
    )


def get_cached_gift_count() -> int:
    """获取当前缓存的礼物数量"""
    return len(_GIFT_NAME_CACHE)


def get_last_update_time() -> float | None:
    """获取最近一次刷新时间戳"""
    return _LAST_UPDATE_TS
