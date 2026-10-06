"""Профиль игрока → параметры агента в игре.

Связь осей стиля с поведением бота — ПРЕДПОЛОЖЕНИЕ (формулы ниже придуманы, не
откалиброваны). Калибровка: сыграть агентом матчи и сравнить его статистику с
профилем игрока (та же features.py) — расхождение по каждой оси и есть ошибка
оцифровки. Это главный измеримый критерий «похож ли двойник».
"""
from __future__ import annotations

import re

SCHEMA = "dota-twin-agent/1"
DEFAULT = 0.5


def _v(style: dict, key: str) -> float:
    v = style.get(key)
    return DEFAULT if v is None else float(v)


_LAT = [("sch", "ш"), ("sh", "ш"), ("ch", "ч"), ("zh", "ж"), ("kh", "х"), ("ph", "ф"), ("th", "т"),
        ("ck", "к"), ("ee", "и"), ("oo", "у"), ("yu", "ю"), ("ya", "я"), ("yo", "ё"), ("ts", "ц"),
        ("a", "а"), ("b", "б"), ("c", "к"), ("d", "д"), ("e", "е"), ("f", "ф"), ("g", "г"), ("h", "х"),
        ("i", "и"), ("j", "дж"), ("k", "к"), ("l", "л"), ("m", "м"), ("n", "н"), ("o", "о"), ("p", "п"),
        ("q", "к"), ("r", "р"), ("s", "с"), ("t", "т"), ("u", "у"), ("v", "в"), ("w", "в"), ("x", "кс"),
        ("y", "и"), ("z", "з")]


def translit(name: str) -> str:
    """Грубая латиница → кириллица для голосовых имён: «Topson» → «топсон»,
    «Miracle-» → «миракл». Английское чтение не угадывает («Notail» → «нотаил»):
    такие имена человек вписывает в aliases сам."""
    s = re.sub(r"[^a-z ]", "", name.lower()).strip()
    if len(s) > 3 and s.endswith("e") and s[-2] not in "aeiouy":
        s = s[:-1]                       # немое e: miracle → miracl
    out, i = "", 0
    while i < len(s):
        for lat, cyr in _LAT:
            if s.startswith(lat, i):
                out += cyr
                i += len(lat)
                break
        else:
            out += s[i]
            i += 1
    return out


def agent_params(profile: dict, hero: str | None = None, obedience: float = 0.85) -> dict:
    st = profile.get("style") or {}
    aggression, farm, risk = _v(st, "aggression"), _v(st, "farm_focus"), _v(st, "risk")
    teamfight, vision, support = _v(st, "teamfight"), _v(st, "vision"), _v(st, "support_play")
    mech = _v(st, "mechanics")

    pool = profile.get("hero_pool") or []
    if hero is None and pool:
        hero = pool[0]["hero"]
    hero_info = (profile.get("heroes") or {}).get(hero or "", {})

    name = profile.get("name") or str(profile.get("account_id"))
    aliases = list(profile.get("aliases") or [])
    tr = translit(name)
    if tr and tr not in aliases:
        aliases.append(tr)

    return {
        "schema": SCHEMA,
        "source_profile": {"account_id": profile.get("account_id"), "matches": profile.get("matches_used"),
                           "schema": profile.get("schema")},
        "name": name,
        "aliases": aliases,
        "position": profile.get("main_position"),
        "hero": hero,
        "hero_pool": [{"hero": h["hero"], "weight": h["share"]} for h in pool[:8]],
        "core_build": hero_info.get("core_build"),
        "core_timings_s": hero_info.get("core_timings_median_s"),
        "start_items": hero_info.get("start_items"),
        "skill_build": hero_info.get("skill_build"),
        "behavior": {
            # отступать, когда здоровья меньше этой доли: рисковые — позже
            "retreat_hp": round(0.45 - 0.25 * risk, 3),
            # добавки к желаниям режимов бота (−0.2..+0.2)
            "desire_bonus": {
                "fight": round((aggression - 0.5) * 0.4, 3),
                "farm": round((farm - 0.5) * 0.4, 3),
                "teamfight_join": round((teamfight - 0.5) * 0.4, 3),
                "ward": round((vision - 0.5) * 0.4, 3),
                "stack": round((support - 0.5) * 0.4, 3),
            },
            "join_fight_radius": round(1200 + 1800 * teamfight),
            # механика: задержка реакции и точность добивания — грубая оценка по APM и линии
            "reaction_ms": round(350 - 200 * mech),
            "last_hit_accuracy": round(0.55 + 0.4 * mech, 3),
            # насколько агент слушается тренера (не из данных: настройка игры)
            "obedience": obedience,
        },
        "ward_spots": profile.get("ward_spots", [])[:10],
        "chat_samples": profile.get("chat_samples", [])[:10],
        "notes": "формулы поведения — предположение, см. twin/agent_params.py",
    }
