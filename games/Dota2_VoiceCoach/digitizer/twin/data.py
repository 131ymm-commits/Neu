"""Справочные таблицы (из dotaconstants, см. data/SOURCE.md)."""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

DATA = Path(__file__).resolve().parent.parent / "data"


@lru_cache(maxsize=None)
def _load(name: str):
    with open(DATA / name, encoding="utf-8") as f:
        return json.load(f)


def hero_name(hero_id: int) -> str:
    """npc_dota_hero_* по числовому id; неизвестный id → 'hero_<id>'."""
    h = _load("heroes_by_id.json").get(str(hero_id))
    return h["name"] if h else f"hero_{hero_id}"


def hero_title(hero_id: int) -> str:
    h = _load("heroes_by_id.json").get(str(hero_id))
    return h["localized_name"] if h else f"hero_{hero_id}"


def item_cost(key: str) -> int:
    """Цена предмета по ключу без префикса item_ ('black_king_bar'); 0 — нет данных."""
    it = _load("items.json").get(key)
    return int(it["cost"] or 0) if it else 0


def item_components(key: str) -> list[str]:
    """Компоненты предмета по рецепту текущего патча (dotaconstants)."""
    it = _load("items.json").get(key)
    return [c for c in (it.get("components") or []) if c] if it else []


def ability_name(ability_id: int) -> str:
    return _load("ability_ids.json").get(str(ability_id), f"ability_{ability_id}")


def order_name(order_type: int | str) -> str:
    return _load("order_types.json").get(str(order_type), f"ORDER_{order_type}")
