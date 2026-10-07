"""Команда протокола → короткая русская строка для тренера: «Вася: фармить свой лес»."""
from __future__ import annotations

from . import lexicon as L
from .protocol import ACTIONS, Command

PLACE_RU = {
    "top": "топ", "mid": "мид", "bot": "бот", "auto": "где лучше",
    "jungle_own": "свой лес", "jungle_enemy": "их лес", "ancients": "древние", "lane": "линия",
    "base": "база", "roshan": "Рошан", "tormentor": "Торментор", "rune": "руна",
    "outpost": "аутпост", "lotus": "лотосы",
}
POS_RU = {1: "керри", 2: "мидер", 3: "оффлейнер", 4: "четвёрка", 5: "пятёрка"}

_hero_ru = None
_item_ru = None


def hero_ru(hero: str) -> str:
    global _hero_ru
    if _hero_ru is None:
        _hero_ru = {k: v["ru"] for k, v in L.load_heroes().items()}
    return _hero_ru.get(hero, hero.replace("npc_dota_hero_", ""))


def item_ru(item: str) -> str:
    """Самое короткое сленговое имя предмета из словаря («бкб», «блинк»)."""
    global _item_ru
    if _item_ru is None:
        _item_ru = {}
        for word, iid in L.ITEM_PHRASES.items():
            if iid not in _item_ru or len(word) < len(_item_ru[iid]):
                _item_ru[iid] = word
    w = _item_ru.get(item)
    return w.upper() if w and len(w) <= 4 else (w or item.replace("item_", ""))


def describe(cmd: Command, names: dict[int, str] | None = None) -> str:
    names = names or {}
    who = ", ".join(names.get(p) or str(p) for p in cmd.agents) if cmd.agents else "?"
    if len(cmd.agents) == 5:
        who = "все"
    spec = ACTIONS.get(cmd.action)
    what = spec.title_ru if spec else cmd.action
    p = cmd.params
    extra = []
    if p.get("area") and p["area"] not in ("lane", "auto"):
        extra.append(PLACE_RU.get(p["area"], p["area"]))
    if p.get("lane") and p["lane"] != "auto":
        extra.append(PLACE_RU.get(p["lane"], p["lane"]))
    if p.get("place"):
        extra.append(PLACE_RU.get(p["place"], p["place"]))
    if p.get("tier"):
        extra.append(f"т{p['tier']}")
    if p.get("enemy"):
        extra.append(hero_ru(p["enemy"]))
    if p.get("enemy_pos"):
        extra.append(f"их {POS_RU.get(p['enemy_pos'], p['enemy_pos'])}")
    if p.get("ally"):
        extra.append(names.get(p["ally"]) or POS_RU.get(p["ally"], str(p["ally"])))
    if p.get("item"):
        extra.append(item_ru(p["item"]))
    if p.get("what"):
        w = ACTIONS.get(p["what"])
        what = "не " + (w.title_ru if w else p["what"])
    if p.get("then") == "gank":
        extra.append("потом ганг")
    if p.get("kind") == "sentry":
        extra.append("сентри")
    text = f"{who}: {what}"
    if extra:
        text += " — " + ", ".join(extra)
    if cmd.after_prev:
        text = "потом " + text
    if cmd.urgent:
        text += " (срочно)"
    if cmd.clarify:
        text += f" — {cmd.clarify}"
    return text
