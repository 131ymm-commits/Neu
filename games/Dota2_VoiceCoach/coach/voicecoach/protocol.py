"""Протокол команд «голос → игра», версия 1.

Одна фраза тренера превращается в список Command. Команда адресована агентам
своей команды по позициям 1–5 (позиция — постоянный номер агента в матче;
имена игроков и героев переводятся в позиции через MatchContext).

Этот же JSON читает мост в игре (Lua). Меняя поля, поднимать PROTOCOL_VERSION
и править docs/COMMANDS.md.
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any

PROTOCOL_VERSION = 1

# Параметры команд и их допустимые значения.
LANES = ("top", "mid", "bot", "auto")
AREAS = ("lane", "jungle_own", "jungle_enemy", "ancients", "auto")
PLACES = (
    "top", "mid", "bot",            # линии
    "jungle_own", "jungle_enemy", "ancients",
    "base", "roshan", "tormentor", "rune", "outpost", "lotus",
)


@dataclass(frozen=True)
class ActionSpec:
    name: str
    title_ru: str
    scope: str            # "team" — без адресата идёт всем; "personal" — нужен адресат
    params: tuple = ()    # имена допустимых параметров
    needs: tuple = ()     # без этих параметров команда требует уточнения
    ttl_s: int = 60       # сколько секунд намерение живёт у агента


ACTIONS: dict[str, ActionSpec] = {a.name: a for a in (
    ActionSpec("farm", "фармить", "personal", ("area", "lane"), ttl_s=120),
    ActionSpec("push", "пушить линию", "team", ("lane", "group", "tier")),
    ActionSpec("defend", "защищать", "team", ("lane", "place", "tier")),
    ActionSpec("gank", "ганг", "personal", ("lane", "enemy", "enemy_pos")),
    ActionSpec("group", "собраться", "team", ("place", "lane")),
    ActionSpec("roshan", "Рошан", "team", ("check",), ttl_s=90),
    ActionSpec("tormentor", "Торментор", "team", ()),
    ActionSpec("smoke", "смок", "team", ("lane", "enemy", "then")),
    ActionSpec("retreat", "отступить", "team", ("place",), ttl_s=20),
    ActionSpec("focus", "фокус цели", "team", ("enemy", "enemy_pos"), needs=("target",), ttl_s=20),
    ActionSpec("engage", "начать драку", "team", ("enemy", "enemy_pos"), ttl_s=20),
    ActionSpec("hold", "ждать, не начинать", "team", ("what",), ttl_s=30),
    ActionSpec("split", "сплит-пуш", "personal", ("lane",), ttl_s=120),
    ActionSpec("ward", "поставить вард", "personal", ("place", "lane", "kind")),
    ActionSpec("stack", "стакнуть лагерь", "personal", ("place",)),
    ActionSpec("buy", "купить", "personal", ("item",), needs=("item",), ttl_s=300),
    ActionSpec("use_item", "применить предмет", "personal", ("item", "enemy"), needs=("item",), ttl_s=10),
    ActionSpec("buyback", "выкупиться", "personal", (), ttl_s=15),
    ActionSpec("use_ult", "ультануть", "personal", ("enemy", "enemy_pos"), ttl_s=10),
    ActionSpec("save_ult", "держать ульту", "personal", (), ttl_s=60),
    ActionSpec("save", "спасти союзника", "personal", ("ally",), needs=("ally",), ttl_s=10),
    ActionSpec("follow", "идти с союзником", "personal", ("ally",), needs=("ally",), ttl_s=60),
    ActionSpec("tp", "телепорт", "personal", ("place", "lane"), needs=("where",), ttl_s=15),
    ActionSpec("move", "идти", "personal", ("place", "lane"), needs=("where",), ttl_s=45),
    ActionSpec("free", "играть самим", "team", (), ttl_s=0),
    ActionSpec("cancel", "отменить приказ", "team", (), ttl_s=0),
    ActionSpec("report", "доложить", "team", ("about",), ttl_s=0),
)}


@dataclass
class Command:
    action: str
    agents: list[int]                       # позиции 1..5 своей команды
    params: dict[str, Any] = field(default_factory=dict)
    urgent: bool = False
    after_prev: bool = False                # «потом …»: выполнить после предыдущей
    text: str = ""                          # кусок фразы, из которого собрана команда
    confidence: float = 1.0
    clarify: str = ""                       # непусто — нужна переспросить тренера

    def to_json(self) -> dict:
        d = asdict(self)
        d["v"] = PROTOCOL_VERSION
        return d


def validate(cmd: Command) -> list[str]:
    """Проверка команды по протоколу; возвращает список нарушений."""
    errs = []
    spec = ACTIONS.get(cmd.action)
    if spec is None:
        return [f"неизвестное действие {cmd.action!r}"]
    if not cmd.agents and not cmd.clarify:
        errs.append("нет адресата")
    if any(p not in range(1, 6) for p in cmd.agents):
        errs.append(f"позиции вне 1..5: {cmd.agents}")
    if len(set(cmd.agents)) != len(cmd.agents):
        errs.append("повтор позиции")
    for k in cmd.params:
        if k not in spec.params:
            errs.append(f"параметр {k!r} не положен действию {cmd.action}")
    if "lane" in cmd.params and cmd.params["lane"] not in LANES:
        errs.append(f"линия {cmd.params['lane']!r}")
    if "area" in cmd.params and cmd.params["area"] not in AREAS:
        errs.append(f"зона {cmd.params['area']!r}")
    if "place" in cmd.params and cmd.params["place"] not in PLACES:
        errs.append(f"место {cmd.params['place']!r}")
    if not 0.0 <= cmd.confidence <= 1.0:
        errs.append("уверенность вне [0,1]")
    return errs
