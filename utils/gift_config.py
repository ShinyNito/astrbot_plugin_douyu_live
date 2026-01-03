"""斗鱼礼物配置加载与缓存"""

from __future__ import annotations

import json
import time

import httpx

from .constants import DEFAULT_GIFT_NAME, GIFT_NAMES, HIGH_VALUE_GIFT_IDS

GIFT_CONFIG_URL = (
    "https://webconf.douyucdn.cn/resource/common/prop_gift_list/prop_gift_config.json"
)
JSONP_PREFIX = "DYConfigCallback("

_GIFT_NAME_CACHE: dict[str, str] = {}
_HIGH_VALUE_GIFT_CACHE: set[str] = set(HIGH_VALUE_GIFT_IDS)
_LAST_UPDATE_TS: float | None = None
HIGH_VALUE_DEVOTE_THRESHOLD = 10000


def _strip_jsonp(payload: str) -> str:
    payload = payload.strip()
    if not payload:
        return payload
    if payload.startswith(JSONP_PREFIX):
        payload = payload[len(JSONP_PREFIX) :]

    payload = payload.rstrip(";").strip()

    if payload.endswith(")"):
        return payload[:-1].strip()

    start = payload.find("(")
    end = payload.rfind(")")
    if start != -1 and end != -1 and end > start:
        return payload[start + 1 : end].strip()
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


def _parse_high_value_gifts(data: dict) -> set[str]:
    high_value: set[str] = set()
    for gift_id, info in data.get("data", {}).items():
        if not isinstance(info, dict):
            continue
        devote = info.get("devote")
        try:
            devote_value = int(float(devote)) if devote is not None else 0
        except (TypeError, ValueError):
            continue
        if devote_value >= HIGH_VALUE_DEVOTE_THRESHOLD:
            high_value.add(str(gift_id))
    return high_value


def update_gift_config() -> int:
    """拉取斗鱼礼物配置并刷新缓存.

    Returns:
        加载到的礼物数量（如果拉取失败则抛异常）
    """
    response = httpx.get(GIFT_CONFIG_URL, timeout=10.0)
    response.raise_for_status()

    raw_json = _strip_jsonp(response.text)
    if not raw_json:
        raise ValueError("礼物配置响应为空")

    try:
        data = json.loads(raw_json)
    except json.JSONDecodeError as exc:
        raise ValueError("礼物配置响应无法解析为 JSON") from exc

    mapping = _parse_gift_mapping(data)
    high_value = _parse_high_value_gifts(data)
    if not mapping:
        raise ValueError("礼物配置响应中未包含礼物数据")

    _GIFT_NAME_CACHE.clear()
    _GIFT_NAME_CACHE.update(mapping)
    if high_value:
        _HIGH_VALUE_GIFT_CACHE.clear()
        _HIGH_VALUE_GIFT_CACHE.update(high_value)

    global _LAST_UPDATE_TS
    _LAST_UPDATE_TS = time.time()

    return len(_GIFT_NAME_CACHE)


def get_gift_name(gift_id: str | int) -> str:
    """获取礼物名称（优先使用在线配置）"""
    gift_key = str(gift_id)
    return _GIFT_NAME_CACHE.get(
        gift_key, GIFT_NAMES.get(gift_key, f"{DEFAULT_GIFT_NAME}({gift_id})")
    )


def is_high_value_gift(gift_id: str | int) -> bool:
    """判断是否为高价值礼物（基于配置的 devote 值）"""
    return str(gift_id) in _HIGH_VALUE_GIFT_CACHE


def get_cached_gift_count() -> int:
    """获取当前缓存的礼物数量"""
    return len(_GIFT_NAME_CACHE)


def get_last_update_time() -> float | None:
    """获取最近一次刷新时间戳"""
    return _LAST_UPDATE_TS
