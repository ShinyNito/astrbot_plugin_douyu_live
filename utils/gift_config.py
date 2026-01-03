"""斗鱼礼物配置加载与缓存"""

from __future__ import annotations

import json
import time

import httpx

from .constants import DEFAULT_GIFT_NAME, GIFT_NAMES, HIGH_VALUE_GIFT_IDS

GIFT_CONFIG_URL = (
    "https://webconf.douyucdn.cn/resource/common/prop_gift_list/prop_gift_config.json"
)
ROOM_GIFT_CONFIG_URL = "http://open.douyucdn.cn/api/RoomApi/room/{room_id}"
JSONP_PREFIX = "DYConfigCallback("

_GIFT_NAME_CACHE: dict[str, str] = {}
_HIGH_VALUE_GIFT_CACHE: set[str] = set(HIGH_VALUE_GIFT_IDS)
_GIFT_VALUE_CACHE: dict[str, int] = {}
_ROOM_GIFT_NAME_CACHE: dict[int, dict[str, str]] = {}
_ROOM_HIGH_VALUE_CACHE: dict[int, set[str]] = {}
_ROOM_GIFT_VALUE_CACHE: dict[int, dict[str, int]] = {}
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


def _parse_gift_values(data: dict) -> dict[str, int]:
    values: dict[str, int] = {}
    for gift_id, info in data.get("data", {}).items():
        if not isinstance(info, dict):
            continue
        devote = info.get("devote")
        try:
            devote_value = int(float(devote)) if devote is not None else 0
        except (TypeError, ValueError):
            continue
        values[str(gift_id)] = devote_value
    return values


def _parse_room_gift_mapping(data: dict) -> tuple[dict[str, str], set[str]]:
    gift_list = data.get("data", {}).get("gift", [])
    mapping: dict[str, str] = {}
    high_value: set[str] = set()
    if not isinstance(gift_list, list):
        return mapping, high_value

    for gift in gift_list:
        if not isinstance(gift, dict):
            continue
        gift_id = gift.get("id")
        gift_name = gift.get("name")
        if gift_id and gift_name:
            mapping[str(gift_id)] = str(gift_name)
        gift_value = gift.get("gx")
        try:
            gift_value_int = int(float(gift_value)) if gift_value is not None else 0
        except (TypeError, ValueError):
            continue
        if gift_value_int >= HIGH_VALUE_DEVOTE_THRESHOLD and gift_id:
            high_value.add(str(gift_id))
    return mapping, high_value


def _parse_room_gift_values(data: dict) -> dict[str, int]:
    gift_list = data.get("data", {}).get("gift", [])
    values: dict[str, int] = {}
    if not isinstance(gift_list, list):
        return values

    for gift in gift_list:
        if not isinstance(gift, dict):
            continue
        gift_id = gift.get("id")
        gift_value = gift.get("gx")
        if not gift_id:
            continue
        try:
            gift_value_int = int(float(gift_value)) if gift_value is not None else 0
        except (TypeError, ValueError):
            continue
        values[str(gift_id)] = gift_value_int
    return values


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
    values = _parse_gift_values(data)
    if not mapping:
        raise ValueError("礼物配置响应中未包含礼物数据")

    _GIFT_NAME_CACHE.clear()
    _GIFT_NAME_CACHE.update(mapping)
    if values:
        _GIFT_VALUE_CACHE.clear()
        _GIFT_VALUE_CACHE.update(values)
    if high_value:
        _HIGH_VALUE_GIFT_CACHE.clear()
        _HIGH_VALUE_GIFT_CACHE.update(high_value)

    global _LAST_UPDATE_TS
    _LAST_UPDATE_TS = time.time()

    return len(_GIFT_NAME_CACHE)


def update_room_gift_config(room_id: int) -> int:
    """拉取房间/主播礼物配置并刷新缓存.

    Returns:
        加载到的房间礼物数量（如果拉取失败则抛异常）
    """
    response = httpx.get(ROOM_GIFT_CONFIG_URL.format(room_id=room_id), timeout=10.0)
    response.raise_for_status()

    if not response.text.strip():
        raise ValueError("房间礼物配置响应为空")

    try:
        data = response.json()
    except json.JSONDecodeError as exc:
        raise ValueError("房间礼物配置响应无法解析为 JSON") from exc

    if data.get("error") != 0:
        raise ValueError(f"房间礼物配置响应错误: {data.get('error')}")

    mapping, high_value = _parse_room_gift_mapping(data)
    values = _parse_room_gift_values(data)
    if not mapping:
        raise ValueError("房间礼物配置响应中未包含礼物数据")

    _ROOM_GIFT_NAME_CACHE[room_id] = mapping
    if high_value:
        _ROOM_HIGH_VALUE_CACHE[room_id] = high_value
    if values:
        _ROOM_GIFT_VALUE_CACHE[room_id] = values

    _GIFT_NAME_CACHE.update(mapping)
    if high_value:
        _HIGH_VALUE_GIFT_CACHE.update(high_value)
    if values:
        _GIFT_VALUE_CACHE.update(values)

    return len(mapping)


def get_gift_name(gift_id: str | int, room_id: int | None = None) -> str:
    """获取礼物名称（优先使用在线配置）"""
    gift_key = str(gift_id)
    if room_id is not None:
        room_mapping = _ROOM_GIFT_NAME_CACHE.get(room_id)
        if room_mapping and gift_key in room_mapping:
            return room_mapping[gift_key]
    return _GIFT_NAME_CACHE.get(
        gift_key, GIFT_NAMES.get(gift_key, f"{DEFAULT_GIFT_NAME}({gift_id})")
    )


def is_high_value_gift(gift_id: str | int, room_id: int | None = None) -> bool:
    """判断是否为高价值礼物（基于配置的 devote 值）"""
    if room_id is not None:
        room_high_value = _ROOM_HIGH_VALUE_CACHE.get(room_id)
        if room_high_value is not None:
            return str(gift_id) in room_high_value
    return str(gift_id) in _HIGH_VALUE_GIFT_CACHE


def get_gift_value(gift_id: str | int, room_id: int | None = None) -> int | None:
    """获取礼物价值（优先使用房间配置）"""
    gift_key = str(gift_id)
    if room_id is not None:
        room_values = _ROOM_GIFT_VALUE_CACHE.get(room_id)
        if room_values and gift_key in room_values:
            return room_values[gift_key]
    return _GIFT_VALUE_CACHE.get(gift_key)


def get_cached_gift_count() -> int:
    """获取当前缓存的礼物数量"""
    return len(_GIFT_NAME_CACHE)


def get_room_cached_gift_count(room_id: int) -> int:
    """获取房间缓存的礼物数量"""
    return len(_ROOM_GIFT_NAME_CACHE.get(room_id, {}))


def get_last_update_time() -> float | None:
    """获取最近一次刷新时间戳"""
    return _LAST_UPDATE_TS
