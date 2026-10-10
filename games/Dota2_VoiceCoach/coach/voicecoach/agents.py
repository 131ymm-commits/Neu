"""Агенты Claude: каждого героя ведёт свой агент (решение автора Д11, 07.10.2026).

Игра раз в секунду присылает наблюдения всех героев (POST /api/{room}/tick, game/custom_game/…/coach_link.lua).
У каждого героя свой агент: свой системный промпт (характер, герой, позиция, команда), своя память и своя
очередь. Агент решает раз в `period` секунд игры и сразу по событию: новый приказ тренера, смерть или
возрождение, враг рядом, резкая потеря здоровья. Вызов модели идёт в фоне; игра забирает готовое решение
на следующем обмене, а выполняет его исполнитель в игре (coach_exec.lua) — рефлексами, пока не придёт новое.

Мотор агента (backend):
  rules — правила без модели: тесты, сухой прогон, бесплатный соперник. Это НЕ Claude, и HUD так и пишет.
  api   — Claude через Messages API: ключ в ANTHROPIC_API_KEY, модель — --model (имя из документации Anthropic).
          Ответ — JSON по схеме DECISION_SCHEMA (structured outputs, параметр output_config.format),
          системный промпт помечен для кэша.
  cli   — Claude через Claude Code: `claude -p` со входом по подписке. Каждый вызов — новый процесс (медленнее);
          лимиты подписки Anthropic не публикует.
Журнал вызовов — JSONL: повод, время ответа, токены, решение, ошибки. По нему меряются задержка и цена.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import tempfile
import threading
import time
import urllib.error
import urllib.request
from collections import deque
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path

from .lexicon import load_heroes
from .parser import Agent, MatchContext
from .protocol import ACTIONS
from .textcmd import ACTION_CANON, parse_short

PLANS = ("farm", "push", "defend", "fight", "retreat", "roshan", "move", "follow", "save", "group", "hold")
WHERE = ("", "top", "mid", "bot", "base", "roshan")
SPECIAL_TARGETS = {"", "self", "creeps", "base", "top", "mid", "bot", "roshan", "1", "2", "3", "4", "5"}
MAX_CASTS, MAX_BUY, MAX_LEVEL, MAX_SAY = 4, 6, 4, 120
ITEM_RE = re.compile(r"^item_[a-z0-9_]+$")

DECISION_SCHEMA = {
    "type": "object",
    "properties": {
        "plan": {"type": "string", "enum": list(PLANS)},
        "where": {"type": "string", "enum": list(WHERE)},
        "target": {"type": "string"},
        "ally": {"type": "integer"},
        "cast": {"type": "array", "items": {
            "type": "object",
            "properties": {"ability": {"type": "string"}, "target": {"type": "string"}},
            "required": ["ability", "target"], "additionalProperties": False}},
        "buy": {"type": "array", "items": {"type": "string"}},
        "level": {"type": "array", "items": {"type": "string"}},
        "retreat_hp": {"type": "integer"},
        "buyback": {"type": "boolean"},
        "say": {"type": "string"},
        "to": {"type": "array", "items": {"type": "integer"}},
    },
    "required": ["plan", "where", "target", "ally", "cast", "buy", "level", "retreat_hp", "buyback", "say", "to"],
    "additionalProperties": False,
}

# Правила ролей по стадиям игры (Д18: «они должны качатся. особенно в начале. почитай гайды в интернете о поведении
# разных ролей в доте»). Опора — research/05_roles_laning.md (источники и статусы там); пороги retreat_hp — наше
# правило, в гайдах их нет. Агент получает общие правила и правила своей позиции — промпт короче.
GAME_PHASES = """СТАДИИ ИГРЫ (по гайдам)
- Опыт получают все союзники в радиусе 1500 от умирающего вражеского крипа, поровну; добивать не нужно, кто ушёл дальше — теряет опыт всей волны. Поэтому первые 10 минут все стоят на своих линиях (plan farm, where — своя линия) и уходят только на ганг, на защиту вышки или отойти. Руки сами идут к своей волне.
- После линий (10–12-я минута): собирайтесь (group) и ломайте вышки (push), первой — Т1 лёгкой линии врага (у Света лёгкая — бот, у Тьмы — топ); после выигранной драки — вышка или Рошан, а не фарм. Не стой без дела: нет цели — фарми линию, где нет врагов. Не гонись далеко и не дерись там, где врагов не видно.
- retreat_hp (правило этой игры): на линии 30 корам (позиции 1–3), 35 саппортам; +10, когда у ближнего врага 6-й уровень или видно двоих врагов; до 10:00 не ставь 0.
- Лечилку (item_flask), кларити (item_clarity) и танго (item_tango — у дерева) руки применяют сами, когда ранен и врага рядом нет; палочку (item_magic_stick, item_magic_wand) и item_faerie_fire — когда здоровья мало и враг рядом. Вернулся на базу — cast item_tpscroll с целью своей линии.
- В первом решении задай buy (стартовые предметы роли) и level — очередь прокачки на первые 10 уровней по сборке своего героя."""

ROLE_PLAYBOOK = {
    1: """КЕРРИ (позиция 1). Линия: добивай вражеских крипов и денаи своих (сначала дальнего); не дерись до первого большого предмета, разве что у своей вышки. У вражеского оффлейнера или поз. 4 6-й уровень или видно двоих врагов — фарми у своей Т1, retreat_hp выше. После линии фарми линии без врагов; к 18–20-й минуте — первый большой предмет. Падают ваши вышки — иди защищать, не фарми. Старт: item_tango, item_branches, item_branches, item_flask, item_quelling_blade (если ближний бой). Прокачка: способность для фарма и урона в первую очередь, побег — одно очко, ульта на 6, 12, 18.""",
    2: """МИДЕР (позиция 2). На линии один и качаешься быстрее всех: добивай, денаи, разменивайся ударами с мидером врага. С 5:00 до 6:30 (ночь и руна силы — время гангов врага) осторожнее: retreat_hp +10, ближе к своей вышке. После 6-го уровня толкни волну (push mid на одно решение) и иди на ганг соседней линии (fight по врагу на ней), потом вернись на мид. Старт: item_tango, item_branches, item_branches, item_faerie_fire; потом item_bottle, item_magic_wand, item_boots.""",
    3: """ОФФЛЕЙНЕР (позиция 3). Сложная линия: главное — выжить и набрать опыт. Денаи крипов, которых добивает вражеский керри, бери свои добивания. Давят двое — стой у своей вышки в радиусе опыта (farm), не уходи с линии и не умирай. После линии ты начинаешь драки: с ключевым предметом (обычно item_blink) — fight по главной цели врага вместе с командой. Старт: item_tango, item_quelling_blade, item_branches, item_flask; потом item_magic_stick, item_boots.""",
    4: """САППОРТ-РОУМЕР (позиция 4). До 6:00 стой на сложной линии с оффлейнером (plan farm там же: руки не заберут у него добивания, будут денаить и бить врага). С 6:00, если оглушение готово, — ганг на мид: fight по мидеру врага (или follow 2), в say «иду мид», потом вернись на линию. Бей керри и поз. 5 врага, спасай оффлейнера (save 3); не стой без дела и не забирай фарм у коров. Старт: item_tango, item_branches, item_ward_observer, item_ward_sentry, item_blood_grenade; потом item_magic_stick, item_boots, item_arcane_boots или item_tranquil_boots. Прокачка: сначала оглушение и урон, в остальное по одному очку.""",
    5: """САППОРТ (позиция 5). Береги керри на лёгкой линии: стой с ним (plan farm там же — руки встанут впереди него, будут денаить и бить врага, когда безопасно), принимай удары вместо него; лучше умрёшь ты, чем керри. С 1:30 — вард у своей Т1 (cast item_ward_observer с целью своей линии). Не жадничай на фарме. После линии — варды, спасай коров (save), помогай в драках. Старт: item_tango, item_ward_observer, item_ward_sentry, item_clarity, item_flask, item_blood_grenade; потом item_magic_stick, item_boots, item_tranquil_boots или item_arcane_boots, item_force_staff или item_glimmer_cape. Прокачка: сначала оглушение и урон, в остальное по одному очку.""",
}

ROLE_RU = {
    1: "керри (позиция 1): лёгкая линия, фарм, сила к поздней игре",
    2: "мидер (позиция 2): центральная линия, темп, ганги после 6 уровня",
    3: "оффлейнер (позиция 3): сложная линия, инициация, место в драке",
    4: "роумер-саппорт (позиция 4): помогает сложной линии, ганги, контроль",
    5: "саппорт (позиция 5): бережёт керри на лёгкой линии, варды, сейвы",
}


def default_lane(team: str, pos: int) -> str:
    """Как X.default_lane в coach_exec.lua: лёгкая у 1 и 5, мид у 2, сложная у 3 и 4."""
    radiant = team == "radiant"
    if pos == 2:
        return "mid"
    if pos in (1, 5):
        return "bot" if radiant else "top"
    return "top" if radiant else "bot"


def mmss(clock) -> str:
    c = int(round(abs(float(clock or 0))))
    return f"{'-' if (clock or 0) < 0 else ''}{c // 60}:{c % 60:02d}"


def short_hero(name) -> str:
    s = str(name or "").strip().lower().replace(" ", "_")
    return s[len("npc_dota_hero_"):] if s.startswith("npc_dota_hero_") else s


# --- разбор ответа ---

def extract_json(text: str) -> dict | None:
    """Первый JSON-объект в тексте (модель может обернуть его в ```json … ``` или добавить слова)."""
    start = text.find("{")
    while start != -1:
        depth, in_str, esc = 0, False, False
        for i in range(start, len(text)):
            ch = text[i]
            if in_str:
                if esc:
                    esc = False
                elif ch == "\\":
                    esc = True
                elif ch == '"':
                    in_str = False
            elif ch == '"':
                in_str = True
            elif ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    try:
                        obj = json.loads(text[start:i + 1])
                    except json.JSONDecodeError:
                        break
                    if isinstance(obj, dict):
                        return obj
                    break
        start = text.find("{", start + 1)
    return None


def parse_decision(raw, obs: dict | None = None) -> tuple[dict | None, list[str]]:
    """Ответ модели → решение для исполнителя и замечания. Без допустимого плана — (None, причины).
    С наблюдением проверяются имена: цель — из вражеской пятёрки, способности — у героя."""
    notes: list[str] = []
    if isinstance(raw, str):
        d = extract_json(raw)
        if d is None:
            return None, ["в ответе нет JSON-объекта"]
    elif isinstance(raw, dict):
        d = raw
    else:
        return None, ["ответ — не объект"]
    plan = str(d.get("plan") or "").strip().lower()
    if plan not in PLANS:
        return None, [f"план {plan!r} не из списка"]
    out = {"plan": plan}
    where = str(d.get("where") or "").strip().lower()
    if where not in WHERE:
        notes.append(f"место {where!r} не из списка")
        where = ""
    out["where"] = where

    enemies = {short_hero(h) for h in (obs or {}).get("enemy_team") or []} if obs else None
    target = short_hero(d.get("target"))
    if target and enemies is not None and target not in enemies:
        notes.append(f"цели {target!r} нет во вражеской пятёрке")
        target = ""
    out["target"] = target

    try:
        ally = int(d.get("ally") or 0)
    except (TypeError, ValueError):
        ally = 0
    out["ally"] = ally if 0 <= ally <= 5 else 0

    names = None
    if obs is not None:
        names = {a.get("name") for a in obs.get("abilities") or []} | {i.get("name") for i in obs.get("items") or []}
    casts = []
    for c in d.get("cast") or []:
        if len(casts) >= MAX_CASTS:
            notes.append("применений больше 4 — лишние отброшены")
            break
        if not isinstance(c, dict):
            continue
        name = str(c.get("ability") or "").strip()
        if not name:
            continue
        if names is not None and name not in names and name != "#ult":
            notes.append(f"способности или предмета {name} у героя нет")
            continue
        t = str(c.get("target") or "").strip().lower()
        if t not in SPECIAL_TARGETS:
            t = short_hero(t)
            if enemies is not None and t not in enemies:
                notes.append(f"цели {t!r} для {name} нет во вражеской пятёрке")
                t = ""
        casts.append({"ability": name, "target": t})
    out["cast"] = casts

    buy = []
    for x in d.get("buy") or []:
        s = str(x).strip().lower()
        if ITEM_RE.match(s):
            buy.append(s)
        else:
            notes.append(f"{s!r} — не имя предмета")
    out["buy"] = buy[:MAX_BUY]

    allowed = None
    if obs is not None:
        allowed = set(obs.get("can_level") or []) | {a.get("name") for a in obs.get("abilities") or []}
    level = []
    for x in d.get("level") or []:
        s = str(x).strip()
        if allowed is not None and s not in allowed and not s.startswith("special_bonus"):
            notes.append(f"качать {s} нельзя")
            continue
        level.append(s)
    out["level"] = level[:MAX_LEVEL]

    try:
        hp = int(d.get("retreat_hp"))
    except (TypeError, ValueError):
        hp = 25
    out["retreat_hp"] = max(0, min(90, hp))
    out["buyback"] = d.get("buyback") is True
    out["say"] = str(d.get("say") or "").strip()[:MAX_SAY]
    me = int((obs or {}).get("pos") or 0)
    to = []
    for x in d.get("to") or []:
        try:
            n = int(x)
        except (TypeError, ValueError):
            notes.append(f"кому {x!r} — не номер союзника")
            continue
        if 1 <= n <= 5 and n != me and n not in to:
            to.append(n)
    out["to"] = to if out["say"] else []
    return out, notes


# --- промпты ---

_HEROES_RU: dict | None = None


def hero_ru(name) -> str:
    """Как называть героя в речи: «luna» → «Луна» (coach/data/heroes.json); неизвестного — как есть."""
    global _HEROES_RU
    if _HEROES_RU is None:
        try:
            _HEROES_RU = {short_hero(k): v.get("ru") or v.get("en") for k, v in load_heroes().items()}
        except OSError:
            _HEROES_RU = {}
    s = short_hero(name)
    return _HEROES_RU.get(s) or s

def _glossary() -> str:
    skip = {"tormentor"}
    return "; ".join(f"«{ACTION_CANON[a]}» — {spec.title_ru}" for a, spec in ACTIONS.items()
                     if a in ACTION_CANON and a not in skip)


def persona_text(persona: dict | None) -> str:
    """Характер из оцифровки (digitizer/twin/agent_params.py) или архетип позиции."""
    if not persona:
        return "Характер: крепкий игрок своей позиции — без лишнего риска, но и без трусости."
    lines = []
    name = persona.get("name")
    src = persona.get("source_profile") or {}
    head = "Твой стиль снят с матчей игрока" + (f" {name}" if name else "")
    if src.get("matches"):
        head += f" ({src['matches']} матчей)"
    lines.append(head + ".")
    style = persona.get("style") or {}
    axes = [("aggression", "агрессия"), ("farm_focus", "фарм"), ("risk", "риск"), ("teamfight", "командные драки"),
            ("vision", "обзор"), ("support_play", "помощь своим"), ("mechanics", "механика")]
    vals = [f"{ru} {float(style[k]):.1f}" for k, ru in axes if style.get(k) is not None]
    if vals:
        lines.append("Оси стиля (0 — мало, 1 — много): " + ", ".join(vals) + ".")
    beh = persona.get("behavior") or {}
    if beh.get("retreat_hp") is not None:
        lines.append(f"Обычно отходишь при {int(round(float(beh['retreat_hp']) * 100))}% здоровья.")
    if persona.get("core_build"):
        lines.append("Любимая сборка: " + ", ".join(map(str, persona["core_build"][:8])) + ".")
    if persona.get("phrases"):
        lines.append("Твои фразы из чата: " + " | ".join(map(str, persona["phrases"][:5])) + ".")
    return "\n".join(lines)


def roster_text(roster: dict | None) -> str:
    if not roster:
        return ""
    allies = ", ".join(f"{p} — {h} ({hero_ru(h)})" for p, h in roster.get("allies") or [])
    enemies = ", ".join(f"{h} ({hero_ru(h)})" for h in roster.get("enemies") or [])
    out = []
    if allies:
        out.append(f"Союзники (позиция — герой): {allies}.")
    if enemies:
        out.append(f"Враги: {enemies}.")
    return "\n".join(out) + "\nВ речи называй героев по-русски (как в скобках), союзников — по герою или номеру."


def system_prompt(team: str, pos: int, hero: str, persona: dict | None = None, obedience: float = 0.85,
                  roster: dict | None = None) -> str:
    who = (persona or {}).get("name") or f"игрок позиции {pos}"
    team_ru = "Свет (Radiant)" if team == "radiant" else "Тьму (Dire)"
    return f"""Ты — {who}: играешь в Dota 2 героем {short_hero(hero)} за {team_ru}, роль — {ROLE_RU.get(pos, f"позиция {pos}")}.
В команде пятеро героев, и каждого ведёт свой ИИ-игрок, как ты. Над вами тренер — человек: героем он не играет, а пишет приказы коротким текстом. У команды голосовой чат: вы переговариваетесь, тренер вас слышит.

{persona_text(persona)}
{roster_text(roster)}

{GAME_PHASES}

{ROLE_PLAYBOOK.get(pos, "")}

КАК ТЫ УПРАВЛЯЕШЬ ГЕРОЕМ
Раз в несколько секунд и сразу при событии (приказ тренера, смерть, враг рядом, резкая потеря здоровья) ты получаешь наблюдение — JSON с тем, что видит твой герой, — и отвечаешь одним решением, тоже JSON. Решение выполняют твои «руки» — исполнитель в игре. Руки сами: добивают крипов при фарме линии; бьют цель; применяют способности из cast, когда цель видна (до далёкой цели сначала подходят); отходят к фонтану, когда здоровья меньше retreat_hp процентов; покупают предметы из buy по очереди, когда герой у фонтана или мёртв и хватает золота; вкладывают очки способностей по level. До следующего решения руки продолжают выполнять это. Ты решаешь, ЧТО делать и ГДЕ; руки — КАК.
Способности по врагам руки применяют и без cast: в планах fight, defend, save и push — по видимому врагу в досягаемости (цель плана — первой; ульту — в fight, defend и save, когда враг ранен или врагов рядом двое); на farm и прочих — только добить слабого врага (меньше 40% здоровья) или отбиться, когда ранен ты, а враг вплотную; при отходе (и в plan retreat) — по догоняющему, только по цели или в точку, без ульты. Только через cast: способности по союзникам, канальные (их сбивает движение), переключатели, ульты-добивания вроде axe_culling_blade, площадные по земле не из известных рукам, телепорт, варды и предметы, кроме расходников (лечилку, кларити, танго, палочку и item_faerie_fire руки применяют сами). Если ты саппорт (позиции 4, 5), на farm рядом со своим кором (позиции 1–3) руки не добивают вражеских крипов — добивания ему, — а добивают своих крипов, бьют врага, когда безопасно, и стоят у кора: опыт идёт и так.

ПОЛЯ РЕШЕНИЯ
- plan: farm (фарм линии where с добиванием), push (давить линию where к вышкам врага), defend (защищать линию where или base), fight (бить героя target; не видно — искать, где видели, или на линии where), retreat (к своему фонтану), roshan (бить Рошана), move (идти к where), follow (идти за союзником ally), save (бежать на помощь союзнику ally), group (собраться в where или к своим), hold (стоять).
- where: "", "top", "mid", "bot", "base", "roshan".
- target: имя героя врага из enemy_team (например "luna") или "".
- ally: номер союзника 1–5 или 0.
- cast: до 4 применений {{"ability": имя из abilities или items, "target": цель}}. Цель: "" — цель плана, а без неё ближайший видимый враг: руки применят, когда он в досягаемости (способность без цели — когда враг рядом); "self" — сразу, на себя или без цели; "creeps" — крипы рядом (для способностей по площади); номер союзника "1"–"5"; место "base"/"top"/"mid"/"bot" — своя внешняя вышка линии (для телепорта item_tpscroll и вардов); имя героя врага. Каждое применение — один раз; ждёт цели и отката до 8 с. Новое решение заменяет невыполненные применения прошлого: нужное повтори (вард, к которому герой уже идёт, он донесёт, только если ты его повторил). Варды (item_ward_observer, item_ward_sentry) руки ставят только у своей внешней вышки линии; точек рун и лагерей руки не знают.
- buy: очередь покупок — внутренние имена предметов Доты ("item_tango", "item_power_treads"). Пустой список — очередь не менять. Есть золото, а ты у фонтана или мёртв — закажи, что нужно по роли и сборке.
- level: очередь прокачки из can_level (есть, когда есть очки). Пустой — руки качают сами: ульту, потом младшую способность.
- retreat_hp: порог отхода, проценты здоровья; обычно 25–40. 0 — не отходить вовсе: только осознанно (например, добить цель).
- buyback: true — выкупиться сейчас (только когда мёртв). После выкупа или возрождения выбери план — куда идти.
- say: твоя реплика в голосовой чат команды (до 100 знаков, по-русски). Сказать нечего — "".
- to: кому реплика — номера союзников, например [2] или [2,3]; [] — всем (и тренеру).

ПРИКАЗЫ ТРЕНЕРА
Они в поле coach: seq, ago (сколько секунд назад), text, urgent (срочно). Новый приказ отмечен в сообщении. Формат: «[кому] действие [где/цель] [!]»; кому — номера позиций («23» — второй и третий) или «все». Слова: {_glossary()}; «не X» — не делать X; «!» — срочно.
Слушайся тренера, если приказ выполним (послушание {obedience:.2f} из 1). Если нет — ты мёртв, нет маны, ульта в откате, это верная смерть — скажи об этом в say коротко и делай лучшее, что можешь. Смок, стаки, лес и варды не у своих вышек руки пока не умеют — скажи тренеру честно, что сделаешь вместо. На новый приказ отвечай в say коротко («Иду пушить бот»).

ГОЛОСОВОЙ ЧАТ КОМАНДЫ
Твою реплику (say) слышат тренер и все четверо союзников; их реплики ты видишь в сообщении в разделе «Голосовой чат» (кто, кому, сколько секунд назад). Говори как живой игрок в голосе Доты: коротко и по делу — где враги и куда пропали, у кого из врагов нет ульты или выкупа, кому нужна помощь, договорённости (Рошан, драка, пуш, отход), ответы тренеру и союзникам. Хочешь, чтобы союзник что-то сделал, — обратись к нему (to) и скажи что. Если обратились к тебе — ответь коротко (to — тот, кто обратился) и, если согласен, сделай. Молчать — нормально: не повторяй то, что уже сказано, и не болтай без нового.

ЧТО В НАБЛЮДЕНИИ
clock — игровые часы, с; hp, mp — [сейчас, максимум]; where — где ты (линия и ближайшая вышка); attack — урон и дальность атаки; abilities — способности (use: target/point/none/passive; ready; cd — откат, с; mana; range); items — предметы (backpack — в рюкзаке: там предмет не действует и не применяется; tp_slot — ячейка телепорта); slots_free и backpack_free — свободные ячейки инвентаря и рюкзака: при полном инвентаре купленное ложится в рюкзак; points и can_level — очки способностей и что можно качать; gold; buyback — цена и можно ли; in_shop — у фонтана; doing — что сейчас делают руки; queue — очереди рук; notes — что руки не смогли сделать; near — крипы и вражеская вышка рядом (weak_enemy_creeps — можно добить сразу); allies — союзники; enemies — видимые враги (d — расстояние до тебя); missing — невидимые враги (seen — где, ago — сколько секунд назад видели); towers — уровень внешней живой вышки на линиях (0 — вышек нет); roshan — жив ли Рошан; events — недавние события.

Отвечай ТОЛЬКО JSON-объектом решения, без пояснений и без markdown.
Пример: {{"plan":"farm","where":"{default_lane(team, pos)}","target":"","ally":0,"cast":[],"buy":["item_tango","item_branches"],"level":[],"retreat_hp":30,"buyback":false,"say":"","to":[]}}"""


SHOP_HINT_GOLD = 600         # с таким золотом у фонтана или мёртвым — напомнить о покупках (пилот: агент забывал)

# порядок полей наблюдения в сообщении: сначала сам герой, потом окружение (JSON из Lua приходит без порядка)
OBS_ORDER = ("clock", "alive", "respawn", "lvl", "hp", "mp", "gold", "buyback", "where", "attack", "abilities",
             "points", "can_level", "items", "slots_free", "in_shop", "doing", "queue", "notes", "near", "enemies",
             "missing", "allies", "towers", "roshan", "coach", "events", "stats", "enemy_team")


PROMPT_SKIP = {"xy"}         # координаты — для карты на пульте тренера; агенту хватает where и d


def _without(keys: set, v):
    """Копия наблюдения без полей keys на любой глубине."""
    if isinstance(v, dict):
        return {k: _without(keys, x) for k, x in v.items() if k not in keys}
    if isinstance(v, list):
        return [_without(keys, x) for x in v]
    return v


def chat_line(e: dict, me: int, clock) -> str:
    who = "ты" if e["from"] == me else f"{hero_ru(e['hero'])} ({e['from']})"
    if not e.get("to"):
        whom = "всем"
    elif me in e["to"]:
        whom = "тебе" if len(e["to"]) == 1 else "тебе и " + ",".join(str(x) for x in e["to"] if x != me)
    else:
        whom = ",".join(str(x) for x in e["to"])
    ago = max(0, int(round(float(clock or 0) - float(e.get("clock") or 0))))
    return f"{ago} с назад {who} → {whom}: «{e['text']}»"


def user_prompt(obs: dict, memory: list[str], new_coach: list[dict], trigger: str,
                chat: list[dict] | None = None, me: int | None = None, seen_chat: int = 0) -> str:
    lines = [f"Часы {mmss(obs.get('clock'))}. Повод: {trigger}."]
    if new_coach:
        lines.append("НОВЫЙ ПРИКАЗ ТРЕНЕРА: " + "; ".join(
            f"«{c.get('text', '')}»" + (" (срочно)" if c.get("urgent") else "") for c in new_coach))
    if chat:
        me = int(me if me is not None else obs.get("pos") or 0)
        rows = [("НОВОЕ " if e["seq"] > seen_chat and e["from"] != me else "") + chat_line(e, me, obs.get("clock"))
                for e in chat]
        lines.append("Голосовой чат команды (старое → новое): " + " | ".join(rows))
    if memory:
        lines.append("Твои прошлые решения: " + " | ".join(memory))
    gold = int(obs.get("gold") or 0)
    queued = ((obs.get("queue") or {}).get("buy") or []) if isinstance(obs.get("queue"), dict) else []
    if (not obs.get("alive", True) or obs.get("in_shop")) and gold >= SHOP_HINT_GOLD and not queued:
        lines.append(f"Ты {'мёртв' if not obs.get('alive', True) else 'у фонтана'}, золота {gold}, "
                     "очередь покупок пуста — самое время заказать покупки (buy).")
    rest = [k for k in obs if k not in OBS_ORDER and k not in ("team", "pos", "hero")]
    view = _without(PROMPT_SKIP, {k: obs[k] for k in (*OBS_ORDER, *rest) if k in obs})
    lines.append("Наблюдение: " + json.dumps(view, ensure_ascii=False, separators=(",", ":")))
    lines.append("Твоё решение (только JSON):")
    return "\n".join(lines)


def memory_line(obs: dict, d: dict, new_coach: list[dict]) -> str:
    s = f"{mmss(obs.get('clock'))} {d['plan']}"
    if d.get("where"):
        s += f" {d['where']}"
    if d.get("target"):
        s += f" → {d['target']}"
    if d.get("cast"):
        s += " cast " + ",".join(c["ability"] for c in d["cast"])
    if new_coach:
        s += " (на приказ «" + "; ".join(c.get("text", "") for c in new_coach) + "»)"
    if d.get("say"):
        s += f"; сказал{(' ' + ','.join(map(str, d['to']))) if d.get('to') else ''} «{d['say']}»"
    return s


# --- моторы ---

LIMIT_RE = re.compile(r"limit|лимит", re.I)          # «usage limit reached» и подобное в ответе claude -p
KEY_VARS = ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN")


class BackendError(Exception):
    def __init__(self, msg: str, retry_after: float | None = None, reply: dict | None = None):
        super().__init__(msg)
        self.retry_after = retry_after
        self.reply = reply or {}                            # что всё же пришло (токены, stop_reason) — в журнал


START_ITEMS = {
    1: ["item_tango", "item_quelling_blade", "item_branches", "item_branches", "item_slippers"],
    2: ["item_tango", "item_faerie_fire", "item_branches", "item_branches", "item_circlet"],
    3: ["item_tango", "item_quelling_blade", "item_gauntlets", "item_branches"],
    4: ["item_tango", "item_branches", "item_branches", "item_circlet"],
    5: ["item_tango", "item_tango", "item_branches", "item_branches"],
}
LATER_ITEMS = {1: ["item_magic_stick", "item_boots"], 2: ["item_bottle", "item_boots"],
               3: ["item_magic_stick", "item_boots"], 4: ["item_boots", "item_magic_stick"],
               5: ["item_boots", "item_magic_stick"]}
INTENT_PLAN = {"retreat": "retreat", "move": "move", "push": "push", "split": "push", "defend": "defend",
               "gank": "fight", "engage": "fight", "focus": "fight", "group": "group", "roshan": "roshan",
               "hold": "hold", "follow": "follow", "save": "save", "farm": "farm"}


def rules_decision(obs: dict, new_coach: list[dict] | None = None, extra: dict | None = None) -> dict:
    """Решение без модели — простые правила (тесты, сухой прогон, бесплатный соперник). Не Claude.
    Говорит в чат: на приказ — «Понял», на обращение союзника — «Иду», на нового врага рядом — «Вижу …»."""
    extra = extra or {}
    team, pos = obs.get("team", "radiant"), int(obs.get("pos", 1))
    d = {"plan": "farm", "where": default_lane(team, pos), "target": "", "ally": 0, "cast": [], "buy": [],
         "level": [], "retreat_hp": 30, "buyback": False, "say": "", "to": []}
    have = {i.get("name") for i in obs.get("items") or []}
    queued = set((obs.get("queue") or {}).get("buy") or [])
    if obs.get("clock", 0) < 60 and not have and not queued:
        d["buy"] = list(START_ITEMS.get(pos, START_ITEMS[5]))
    elif not queued:
        d["buy"] = [x for x in LATER_ITEMS.get(pos, []) if x not in have][:1]
    coach = sorted(obs.get("coach") or [], key=lambda c: c.get("seq", 0))
    if coach and coach[-1].get("ago", 999) <= 60:
        ctx = MatchContext(team=team, agents=[Agent(i) for i in range(1, 6)],
                           enemy_heroes=["npc_dota_hero_" + h for h in obs.get("enemy_team") or []])
        r = parse_short(coach[-1].get("text", ""), ctx)
        if r.ok:
            c = r.commands[-1]
            p = c.params
            plan = INTENT_PLAN.get(c.action)
            if plan:
                d["plan"] = plan
                d["where"] = p.get("lane") if p.get("lane") in ("top", "mid", "bot") else (
                    p.get("place") if p.get("place") in ("base", "roshan") else "")
                if plan == "farm" and not d["where"]:
                    d["where"] = default_lane(team, pos)
                if plan in ("push", "defend") and not d["where"]:
                    d["where"] = "mid"
                d["target"] = short_hero(p.get("enemy") or "")
                d["ally"] = int(p.get("ally") or 0)
            elif c.action == "use_ult":
                ult = next((a["name"] for a in obs.get("abilities") or [] if a.get("ult")), None)
                if ult:
                    d["cast"] = [{"ability": ult, "target": short_hero(p.get("enemy") or "")}]
            elif c.action == "buyback":
                d["buyback"] = True
        if new_coach:
            d["say"] = "Понял: " + coach[-1].get("text", "")
    asked = extra.get("chat_to_me") or []
    if asked and not d["say"]:
        e = asked[-1]
        d["say"], d["to"] = f"{hero_ru(e['hero'])}, понял, иду", [e["from"]]
        if obs.get("alive", True):
            d["plan"], d["where"], d["ally"] = "save", "", e["from"]
    elif extra.get("trigger") == "враг рядом" and not d["say"] and obs.get("enemies"):
        d["say"] = f"Вижу {hero_ru(obs['enemies'][0]['hero'])}"
    if not obs.get("alive", True):
        return d
    hp = obs.get("hp") or [1, 1]
    if hp[1] and hp[0] / hp[1] < 0.3 and d["plan"] not in ("retreat", "fight"):
        d["plan"], d["where"] = "retreat", "base"
    return d


class RulesBackend:
    label = "правила (не Claude)"
    free = True                                             # не тратит предел вызовов и не входит в цену

    def decide(self, system: str, user: str, obs: dict, extra: dict | None = None) -> dict:
        return {"data": rules_decision(obs, (extra or {}).get("new_coach"), extra), "usage": {}}


def _retry_after(value) -> float | None:
    """Заголовок retry-after: секунды или дата (тогда — 30 с)."""
    if not value:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return 30.0


class ApiBackend:
    """Claude через Messages API (ключ — переменная окружения ANTHROPIC_API_KEY).

    Новые модели думают по умолчанию, и думание входит в max_tokens (документация Anthropic, «Troubleshooting
    thinking», 07.10.2026) — поэтому запас max_tokens большой, а effort по умолчанию low. Параметр, который модель
    не принимает (effort, thinking, структурированный ответ), после ответа 400 отключается, и запрос повторяется."""
    URL = "https://api.anthropic.com/v1/messages"
    VERSION = "2023-06-01"

    def __init__(self, model: str, api_key: str | None = None, timeout: float = 30.0, max_tokens: int = 4000,
                 structured: bool = True, effort: str | None = "low", thinking: str | None = None, opener=None):
        if not model:
            raise ValueError("нужна модель (--model): имя из документации Anthropic")
        self.model = model
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY", "")
        if not self.api_key:
            raise ValueError("нет ключа: задайте переменную окружения ANTHROPIC_API_KEY")
        self.timeout, self.max_tokens, self.structured = timeout, max_tokens, structured
        self.effort, self.thinking = effort, thinking
        self.opener = opener or urllib.request.urlopen
        self.label = f"Claude API ({model})"
        self.dropped: list[str] = []                       # что модель не приняла — в журнал и сводку

    def body(self, system: str, user: str) -> dict:
        b = {"model": self.model, "max_tokens": self.max_tokens,
             "system": [{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}],
             "messages": [{"role": "user", "content": user}]}
        cfg = {}
        if self.structured:
            cfg["format"] = {"type": "json_schema", "schema": DECISION_SCHEMA}
        if self.effort:
            cfg["effort"] = self.effort
        if cfg:
            b["output_config"] = cfg
        if self.thinking:
            b["thinking"] = {"type": self.thinking}
        return b

    def _drop(self, text: str) -> bool:
        """400 из-за параметра, которого модель не знает, — отключить его и повторить."""
        low = text.lower()
        if self.effort and "effort" in low:
            self.effort = None
            self.dropped.append("effort")
            return True
        if self.thinking and "thinking" in low:
            self.thinking = None
            self.dropped.append("thinking")
            return True
        if self.structured and ("output_config" in low or "json_schema" in low or "format" in low):
            self.structured = False                         # дальше просим JSON словами
            self.dropped.append("structured")
            return True
        return False

    def decide(self, system: str, user: str, obs: dict, extra: dict | None = None) -> dict:
        for _ in range(4):
            req = urllib.request.Request(
                self.URL, data=json.dumps(self.body(system, user)).encode("utf-8"), method="POST",
                headers={"x-api-key": self.api_key, "anthropic-version": self.VERSION,
                         "content-type": "application/json"})
            try:
                with self.opener(req, timeout=self.timeout) as r:
                    data = json.loads(r.read().decode("utf-8"))
                break
            except urllib.error.HTTPError as e:
                text = e.read().decode("utf-8", "replace")[:400] if hasattr(e, "read") else ""
                if e.code == 400 and self._drop(text):
                    continue
                if "credit balance" in text.lower():          # кредит организации кончился: до пополнения не стучаться
                    raise BackendError("кредит API кончился (запросы стоят до нового месяца или пополнения)",
                                       3600.0) from None
                retry = e.headers.get("retry-after") if getattr(e, "headers", None) else None
                raise BackendError(f"HTTP {e.code}: {text}", _retry_after(retry)) from None
            except (urllib.error.URLError, TimeoutError, OSError) as e:
                raise BackendError(f"нет связи с API: {e}") from None
        else:
            raise BackendError("API отклоняет запрос и после отключения необязательных параметров")
        text = "".join(b.get("text", "") for b in data.get("content") or [] if b.get("type") == "text")
        out = {"text": text, "usage": data.get("usage") or {}, "stop_reason": data.get("stop_reason"),
               "model": data.get("model")}
        if data.get("stop_reason") == "max_tokens":
            raise BackendError(f"ответ обрезан на max_tokens={self.max_tokens} (думание съело лимит?)",
                               reply=out)
        return out


CLI_SYSTEM_PROMPTS: dict[str, str] = {}


class CliBackend:
    """Claude через Claude Code: `claude -p` (вход по подписке или ключом — как настроен Claude Code).

    Без --bare: режим --bare подписку не использует (документация Claude Code, «headless»). Вместо него --safe-mode:
    не грузит CLAUDE.md, навыки, плагины, хуки, MCP и автопамять, а вход и модель работают как обычно.
    Системный промпт — файлом (--system-prompt-file): длинная строка с переводами строк в командной строке
    Windows ломается. На Windows лучше нативный claude.exe: обёртку claude.cmd из npm запускает cmd.exe."""

    def __init__(self, model: str | None = None, claude: str = "claude", timeout: float = 90.0, runner=None,
                 effort: str | None = None, which=shutil.which, subscription: bool = False):
        self.model, self.timeout, self.effort = model, timeout, effort
        # по подписке: ключ из окружения убрать — в режиме -p Claude Code берёт ключ, если он есть (документация,
        # «Authentication»), и вызовы ушли бы в оплату по ключу
        self.env = {k: v for k, v in os.environ.items() if k not in KEY_VARS} if subscription else None
        self.claude = which(claude) or claude
        self.runner = runner or subprocess.run
        self.cwd = tempfile.mkdtemp(prefix="vc_agent_")      # пустая рабочая папка
        self.label = "Claude Code" + (f" ({model})" if model else "")
        self.self_cost = True        # цену считает сам Claude Code (cost_cli); по подписке это оценка, не списание

    def prompt_file(self, system: str) -> str:
        key = hashlib.sha1(system.encode("utf-8")).hexdigest()[:16]
        path = CLI_SYSTEM_PROMPTS.get(key)
        if path is None or not os.path.exists(path):
            path = os.path.join(self.cwd, f"system_{key}.txt")
            with open(path, "w", encoding="utf-8") as f:
                f.write(system)
            CLI_SYSTEM_PROMPTS[key] = path
        return path

    def argv(self, system: str) -> list[str]:
        a = [self.claude, "-p", "--output-format", "json", "--safe-mode", "--system-prompt-file",
             self.prompt_file(system), "--tools", "", "--disallowedTools", "mcp__*", "--no-session-persistence",
             "--json-schema", json.dumps(DECISION_SCHEMA, separators=(",", ":")),
             "Реши, что делать герою сейчас. Наблюдение и приказы — во входных данных."]
        if self.effort:
            a[1:1] = ["--effort", self.effort]
        if self.model:
            a[1:1] = ["--model", self.model]
        return a

    def decide(self, system: str, user: str, obs: dict, extra: dict | None = None) -> dict:
        try:
            p = self.runner(self.argv(system), input=user, capture_output=True, text=True, encoding="utf-8",
                            errors="replace", timeout=self.timeout, cwd=self.cwd, env=self.env)
        except FileNotFoundError:
            raise BackendError(f"не нашёл {self.claude}: установите Claude Code или укажите --claude") from None
        except subprocess.TimeoutExpired:
            raise BackendError(f"claude -p не ответил за {self.timeout:.0f} с") from None
        try:
            data = json.loads(p.stdout)
        except json.JSONDecodeError:
            raise BackendError(f"claude -p: не JSON (код {p.returncode}): {(p.stdout or p.stderr)[:200]}") from None
        if data.get("is_error"):
            text = str(data.get("result"))
            # кончился лимит подписки: сторона ждёт 10 минут, а не стучится каждые несколько секунд
            raise BackendError(f"claude -p: {text[:200]}", 600.0 if LIMIT_RE.search(text) else None)
        # modelUsage: кроме модели агента Claude Code зовёт и малую служебную — главная та, что дороже
        mu = data.get("modelUsage") or {}
        models = sorted(mu, key=lambda m: -float((mu[m] or {}).get("costUSD") or 0))
        return {"data": data.get("structured_output"), "text": data.get("result") or "",
                "usage": data.get("usage") or {}, "cost_usd": data.get("total_cost_usd"),
                "model": ",".join(models) or None, "stop_reason": data.get("subtype")}


def make_backend(kind: str, model: str | None = None, claude: str = "claude", effort: str | None = "low",
                 thinking: str | None = None, max_tokens: int = 4000):
    if kind == "rules":
        return RulesBackend()
    if kind == "api":
        return ApiBackend(model or "", effort=effort, thinking=thinking, max_tokens=max_tokens)
    if kind == "cli":
        return CliBackend(model, claude, effort=effort)
    raise ValueError(f"неизвестный мотор агентов: {kind}")


# --- агенты и их расписание ---

@dataclass
class HeroAgent:
    team: str
    pos: int
    hero: str
    system: str
    memory: deque = field(default_factory=lambda: deque(maxlen=6))
    seen_coach: int = 0
    seen_chat: int = 0                  # последняя реплика чата команды, которую агент уже слышал
    busy: bool = False
    last_clock: float = -1e9
    last_error: bool = False
    called_obs: dict | None = None
    decision: dict | None = None
    seq: int = 0
    state: str = "ждёт"
    calls: int = 0
    errors: int = 0
    decided: dict = field(default_factory=dict)   # seq → (часы наблюдения, время готовности) — для замера задержки
    last_coach_clock: float = -1e9      # когда приказ тренера будил агента в последний раз


ASKED = "к тебе обратился союзник"
COACH = "приказ тренера"
CHAT_WINDOW = 60          # с игры: столько агент «помнит» голосовой чат
CHAT_KEEP = 6             # и не больше стольких реплик
RAW_KEEP = 400            # столько знаков сырого ответа модели — в журнал, когда ответ не разобрался чисто


def _hp_pct(obs: dict | None) -> float:
    hp = (obs or {}).get("hp") or [0, 0]
    return 100.0 * hp[0] / hp[1] if len(hp) == 2 and hp[1] else 0.0


def _near_enemies(obs: dict | None, radius: float = 1500) -> set:
    return {e.get("hero") for e in (obs or {}).get("enemies") or [] if (e.get("d") or 1e9) <= radius}


def _clock(obs) -> float:
    try:
        return float((obs or {}).get("clock") or 0)
    except (TypeError, ValueError, AttributeError):
        return 0.0


def _q(xs: list, p: float):
    xs = sorted(xs)
    return round(xs[min(len(xs) - 1, int(p * len(xs)))], 2) if xs else None


def _new_stats() -> dict:
    return {"calls": 0, "errors": 0, "latency": [], "age": [], "in": 0, "out": 0, "cache_read": 0,
            "cache_write": 0, "cost_cli": 0.0}


class AgentHub:
    """Агенты одной комнаты (одного матча): по агенту на героя, решения в фоне."""

    def __init__(self, backends: dict, period: float = 4.0, dead_period: float = 12.0, min_gap: float = 1.0,
                 error_gap: float = 3.0, max_inflight: int = 10, max_calls: int | None = None,
                 log_path: str | Path | None = None, personas: dict | None = None, obedience: float = 0.85,
                 prices: dict | None = None, sync: bool = False, coach_gap: float = 3.0):
        self.backends = backends                  # {"radiant": мотор, "dire": мотор}
        self.period, self.dead_period, self.min_gap, self.error_gap = period, dead_period, min_gap, error_gap
        # сколько игре держать решение агента, прежде чем героем возьмётся править запасной исполнитель:
        # период плюс запас на думание (по подписке решения реже — игра узнаёт это из ответа на обмен)
        self.stale = max(20.0, period + 15.0)
        self.max_inflight = max_inflight
        self.max_calls = max_calls                # предел платных вызовов у каждой стороны (правила не считаются)
        self.personas = personas or {}
        self.obedience = obedience
        self.prices = prices or {}
        self.sync = sync
        self.pool = None if sync else ThreadPoolExecutor(max_workers=max_inflight, thread_name_prefix="agent")
        self.lock = threading.Lock()
        self.agents: dict[tuple, HeroAgent] = {}
        self.inflight = 0
        self.calls_paid = {t: 0 for t in backends}     # платные вызовы по сторонам: соперник не тратит предел хоста
        self.coach_gap = coach_gap
        self.pause_until = {t: 0.0 for t in backends}         # пауза по retry-after — у стороны, которой ответили 429
        self.pause_why = {t: "лимит API" for t in backends}
        self.log_path = Path(log_path) if log_path else None
        self.run = f"{time.time():.0f}-{id(self) % 10000}"   # новый запуск сервера — номера решений с 1, игра их сбрасывает
        self.chat = {t: deque(maxlen=40) for t in backends}   # голосовой чат каждой команды (слышит только своя)
        self.chat_seq = 0
        self.on_say = None                                    # on_say(team, реплика) — сервер шлёт её тренеру
        self.stats = {t: _new_stats() for t in backends}      # по сторонам: у сторон могут быть разные моторы
        self.model_seen = {t: "" for t in backends}           # какая модель ответила последней (её имя дал мотор)

    def _paid(self, team: str) -> bool:
        return not getattr(self.backends.get(team), "free", False)

    def _persona(self, team: str, pos: int) -> dict | None:
        return (self.personas.get(team) or {}).get(str(pos)) or (self.personas.get(team) or {}).get(pos)

    def _agent(self, obs: dict) -> HeroAgent:
        team, pos, hero = obs.get("team"), int(obs.get("pos")), str(obs.get("hero") or "")
        if not 1 <= pos <= 5:
            raise ValueError(f"позиция {pos} вне 1–5")
        key = (team, pos)
        ag = self.agents.get(key)
        clock = float(obs.get("clock") or 0)
        if ag is None or ag.hero != hero or clock < ag.last_clock - 60:     # новый матч или другой герой
            if ag is not None and clock < ag.last_clock - 60:
                self.chat[team].clear()
            persona = self._persona(team, pos)
            roster = {"allies": [(a.get("pos"), a.get("hero")) for a in obs.get("allies") or []],
                      "enemies": list(obs.get("enemy_team") or [])}
            ag = HeroAgent(team=team, pos=pos, hero=hero,
                           system=system_prompt(team, pos, hero, persona, self.obedience, roster))
            self.agents[key] = ag
        return ag

    def _chat_for(self, ag: HeroAgent, clock: float) -> list[dict]:
        """Последние реплики своей команды за CHAT_WINDOW с игры — что агент «слышит»."""
        recent = [dict(e) for e in self.chat.get(ag.team, ()) if clock - e["clock"] <= CHAT_WINDOW]
        return recent[-CHAT_KEEP:]

    def _asked(self, ag: HeroAgent) -> list[dict]:
        """Новые обращения союзников к этому агенту (ответы на обращения не будят — нет пинг-понга)."""
        return [e for e in self.chat.get(ag.team, ()) if e["seq"] > ag.seen_chat and e["from"] != ag.pos
                and ag.pos in e["to"] and not e["reply"]]

    def _trigger(self, ag: HeroAgent, obs: dict) -> str | None:
        if ag.calls == 0:
            return "начало игры для тебя"
        clock = float(obs.get("clock") or 0)
        gap = clock - ag.last_clock
        if gap < (self.error_gap if ag.last_error else self.min_gap):
            return None
        if (any((c.get("seq") or 0) > ag.seen_coach for c in obs.get("coach") or [])
                and clock - ag.last_coach_clock >= self.coach_gap):
            return COACH          # чаще — приказ подождёт до следующего решения: поток приказов не множит вызовы
        if self._asked(ag):
            return ASKED
        prev = ag.called_obs
        if prev is not None:
            if prev.get("alive") and not obs.get("alive"):
                return "ты погиб"
            if not prev.get("alive") and obs.get("alive"):
                return "ты возродился"
            if obs.get("alive"):
                if _near_enemies(obs) - _near_enemies(prev):
                    return "враг рядом"
                if _hp_pct(prev) - _hp_pct(obs) >= 20:
                    return "быстро теряешь здоровье"
        if gap >= (self.period if obs.get("alive") else self.dead_period):
            return "очередное решение"
        return None

    def _want(self, obs, now: float):
        """Нужно ли агенту этого героя решать сейчас и можно ли (предел вызовов, пауза). → (агент, повод) или None.
        Место в пуле не занимает — это делает _schedule (под замком)."""
        if not isinstance(obs, dict) or obs.get("team") not in self.backends:
            return None
        ag = self._agent(obs)
        if ag.busy:
            return None
        trig = self._trigger(ag, obs)
        if trig is None:
            return None
        if self._paid(ag.team) and self.max_calls is not None and self.calls_paid.get(ag.team, 0) >= self.max_calls:
            ag.state = "лимит вызовов исчерпан"
            return None
        if now < self.pause_until.get(ag.team, 0.0):
            ag.state = "пауза: " + self.pause_why.get(ag.team, "лимит")
            return None
        return ag, trig

    def _schedule(self, obs, now: float, t_obs=None, want=None):
        """Нужно ли агенту этого героя решать сейчас; да — задание для фона (под замком).
        t_obs — точные часы игры, когда собраны наблюдения (в самих наблюдениях часы округлены до секунд)."""
        want = want or self._want(obs, now)
        if want is None or self.inflight >= self.max_inflight:
            return None
        ag, trig = want
        paid = self._paid(ag.team)
        if paid and self.max_calls is not None and self.calls_paid.get(ag.team, 0) >= self.max_calls:
            ag.state = "лимит вызовов исчерпан"                # в этом же обмене предел могли выбрать соседи
            return None
        ag.busy, ag.state = True, "думает"
        self.inflight += 1
        if paid:
            self.calls_paid[ag.team] = self.calls_paid.get(ag.team, 0) + 1
        if trig == COACH:
            ag.last_coach_clock = _clock(obs)
        try:
            t_obs = float(t_obs)
        except (TypeError, ValueError):
            t_obs = _clock(obs)
        return (ag, obs, trig, self._chat_for(ag, _clock(obs)), self._asked(ag), self.chat_seq, t_obs)

    def _applied(self, payload: dict) -> list[dict]:
        """Игра сообщила, какие решения дошли до рук. Возраст решения — секунды игры от наблюдения, по которому
        агент решал, до начала выполнения: обмен с игрой, думание модели и ожидание следующего обмена (под замком)."""
        out = []
        for a in payload.get("applied") or []:
            try:
                team, pos, seq = a.get("team"), int(a.get("pos")), int(a.get("seq"))
                ag = self.agents.get((team, pos))
                got = ag.decided.pop(seq, None) if ag else None
                if got is None:
                    continue
                age = round(float(a.get("clock", payload.get("clock"))) - got[0], 2)
            except (TypeError, ValueError, AttributeError):
                continue
            self.stats[team]["age"].append(age)
            out.append({"t": round(time.time(), 3), "event": "applied", "team": team, "pos": pos, "seq": seq,
                        "decision_age_s": age, "ready_to_report_s": round(time.time() - got[1], 2)})
        return out

    def tick(self, payload: dict) -> dict:
        jobs = []
        now = time.monotonic()
        with self.lock:
            applied = self._applied(payload)
            wants = []
            for obs in payload.get("heroes") or []:
                try:
                    w = self._want(obs, now)
                except (TypeError, ValueError, KeyError, AttributeError):
                    continue                              # битое наблюдение одного героя не мешает остальным
                if w is not None:
                    wants.append((w, obs))
            # места в пуле — сначала приказам тренера и обращениям союзников, дальше тем, кто дольше всех без
            # решения: при узком пуле (по подписке — 4 вызова сразу) ни одна сторона и ни один герой не голодает
            wants.sort(key=lambda x: (x[0][1] not in (COACH, ASKED), x[0][0].last_clock))
            for w, obs in wants:
                if self.inflight >= self.max_inflight:
                    break
                try:
                    job = self._schedule(obs, now, payload.get("clock"), want=w)
                except (TypeError, ValueError, KeyError, AttributeError):
                    continue
                if job is not None:
                    jobs.append(job)
        for rec in applied:
            self._log(rec)
        for job in jobs:
            if self.sync:
                self._run(*job)
            else:
                self.pool.submit(self._run, *job)
        with self.lock:
            return {
                "decisions": [{"team": a.team, "pos": a.pos, "seq": a.seq, "decision": a.decision}
                              for a in self.agents.values() if a.decision is not None],
                "agents": [{"team": a.team, "pos": a.pos, "state": a.state} for a in self.agents.values()],
                "backend": {t: getattr(b, "label", str(b)) for t, b in self.backends.items()},
                "run": self.run,
                "stale": self.stale,
            }

    def _run(self, ag: HeroAgent, obs: dict, trig: str, chat: list | None = None, asked: list | None = None,
             heard: int = 0, t_obs: float | None = None) -> None:
        """Один вызов модели в фоне. Что бы ни случилось, агент освобождается — иначе он замолчит до конца матча."""
        try:
            self._run_once(ag, obs, trig, chat, asked, heard, _clock(obs) if t_obs is None else t_obs)
        except Exception as e:                                     # noqa: BLE001 — сбой учёта, не модели
            with self.lock:
                ag.state = "сбой сервера: " + f"{type(e).__name__}: {e}"[:80]
                ag.last_error, ag.last_clock, ag.called_obs = True, _clock(obs), obs
                ag.calls += 1
        finally:
            with self.lock:
                ag.busy = False
                self.inflight -= 1

    def _run_once(self, ag: HeroAgent, obs: dict, trig: str, chat: list | None, asked: list | None,
                  heard: int, t_obs: float) -> None:
        t0 = time.monotonic()
        backend = self.backends[ag.team]
        reply, decision, notes, err, new_coach = {}, None, [], None, []
        said = None
        try:
            new_coach = [c for c in obs.get("coach") or [] if (c.get("seq") or 0) > ag.seen_coach]
            user = user_prompt(obs, list(ag.memory), new_coach, trig, chat or [], ag.pos, ag.seen_chat)
            reply = backend.decide(ag.system, user, obs, {"new_coach": new_coach, "trigger": trig,
                                                          "chat_to_me": asked or []}) or {}
            raw = reply.get("data") if reply.get("data") is not None else (reply.get("text") or "")
            decision, notes = parse_decision(raw, obs)
            if decision is None:
                err = "; ".join(notes) or "пустой ответ"
        except BackendError as e:
            err = str(e)
            reply = dict(e.reply or {})                            # обрезанный ответ тоже оплачен — токены в учёт
            if e.retry_after:
                with self.lock:
                    until = time.monotonic() + e.retry_after
                    if until > self.pause_until.get(ag.team, 0.0):     # причину пишет самая долгая пауза
                        self.pause_until[ag.team] = until
                        self.pause_why[ag.team] = ("кредит API кончился" if "кредит" in err else "лимит подписки"
                                                   if getattr(backend, "self_cost", False) else "лимит API")
        except Exception as e:                                     # noqa: BLE001 — агент не должен ронять сервер
            err = f"{type(e).__name__}: {e}"
        latency = time.monotonic() - t0
        usage = reply.get("usage") or {}
        clock = _clock(obs)
        with self.lock:
            st = self.stats[ag.team]
            ag.calls += 1
            ag.last_clock = clock
            ag.called_obs = obs
            ag.last_error = decision is None
            st["calls"] += 1
            st["latency"].append(latency)
            st["in"] += int(usage.get("input_tokens") or 0)
            st["out"] += int(usage.get("output_tokens") or 0)
            st["cache_read"] += int(usage.get("cache_read_input_tokens") or 0)
            st["cache_write"] += int(usage.get("cache_creation_input_tokens") or 0)
            if reply.get("cost_usd"):
                st["cost_cli"] += float(reply["cost_usd"])
            if decision is not None:
                if reply.get("model"):
                    self.model_seen[ag.team] = str(reply["model"])
                ag.seq += 1
                ag.decision = decision
                ag.decided[ag.seq] = (t_obs, time.time())
                for old in [k for k in ag.decided if k < ag.seq - 8]:
                    del ag.decided[old]
                ag.state = "решил" + (f": «{decision['say']}»" if decision.get("say") else "")
                ag.seen_coach = max([ag.seen_coach] + [int(c.get("seq") or 0) for c in obs.get("coach") or []])
                ag.seen_chat = max(ag.seen_chat, heard)
                ag.memory.append(memory_line(obs, decision, new_coach))
                if decision.get("say"):
                    self.chat_seq += 1
                    said = {"seq": self.chat_seq, "clock": clock, "from": ag.pos, "hero": ag.hero,
                            "text": decision["say"], "to": list(decision.get("to") or []), "reply": trig == ASKED}
                    self.chat[ag.team].append(said)
            else:
                ag.errors += 1
                st["errors"] += 1
                ag.state = "ошибка: " + (err or "")[:80]
        if said is not None and self.on_say is not None:
            try:
                self.on_say(ag.team, dict(said))
            except Exception:                                      # noqa: BLE001 — тренеру не дошло, игра идёт
                pass
        rec = {"t": round(time.time(), 3), "clock": obs.get("clock"), "team": ag.team, "pos": ag.pos,
               "hero": ag.hero, "trigger": trig, "backend": getattr(backend, "label", ""),
               "model": reply.get("model"), "stop_reason": reply.get("stop_reason"),
               "latency_s": round(latency, 3), "usage": usage, "cost_usd": reply.get("cost_usd"),
               "seq": ag.seq if decision is not None else None, "decision": decision, "notes": notes, "error": err}
        if err or notes:
            rec["raw"] = (reply.get("text") or json.dumps(reply.get("data"), ensure_ascii=False))[:RAW_KEEP]
        self._log(rec)

    def _log(self, rec: dict) -> None:
        if not self.log_path:
            return
        line = json.dumps(rec, ensure_ascii=False)
        with self.lock:
            self.log_path.parent.mkdir(parents=True, exist_ok=True)
            with self.log_path.open("a", encoding="utf-8") as f:
                f.write(line + "\n")

    def summary(self) -> dict:
        """Сводка: всего и по сторонам. Задержка вверху — только платных моторов (правила отвечают мгновенно)."""
        keys = ("calls", "errors", "in", "out", "cache_read", "cache_write", "cost_cli")
        with self.lock:
            per = {t: {**{k: s[k] for k in keys}, "latency": list(s["latency"]), "age": list(s["age"])}
                   for t, s in self.stats.items()}
            labels = {t: getattr(b, "label", str(b)) for t, b in self.backends.items()}
            dropped = {t: list(getattr(b, "dropped", []) or []) for t, b in self.backends.items()}
            paid = {t: self._paid(t) for t in self.backends}
            self_cost = {t: bool(getattr(b, "self_cost", False)) for t, b in self.backends.items()}
            calls_paid = sum(self.calls_paid.values())
        total = {k: 0 for k in keys}
        total["cost_cli"] = 0.0
        priced = {k: 0 for k in ("in", "out", "cache_read", "cache_write")}   # токены моторов без своей цены
        lat_paid, ages = [], []
        teams = {}
        for t, s in per.items():
            row = {"backend": labels[t], **{k: s[k] for k in keys},
                   "latency_p50_s": _q(s["latency"], 0.5), "latency_p95_s": _q(s["latency"], 0.95),
                   "decision_age_p50_s": _q(s["age"], 0.5), "decision_age_p95_s": _q(s["age"], 0.95)}
            if dropped[t]:
                row["dropped"] = dropped[t]                       # что модель не приняла (effort, thinking, схема)
            teams[t] = row
            for k in keys:
                total[k] += s[k]
            if not self_cost[t]:
                for k in priced:
                    priced[k] += s[k]
            if paid[t]:
                lat_paid += s["latency"]
            ages += s["age"]
        out = dict(total)
        out["cost_cli"] = round(out["cost_cli"], 6)
        out["paid_calls"] = calls_paid
        out.update({"latency_p50_s": _q(lat_paid, 0.5), "latency_p95_s": _q(lat_paid, 0.95),
                    "decision_age_p50_s": _q(ages, 0.5), "decision_age_p95_s": _q(ages, 0.95)})
        p = self.prices
        if p:                      # оценка по ценам API — без сторон на Claude Code: их цену уже дал он сам (cost_cli)
            out["cost_usd_est"] = round((priced["in"] * p.get("in", 0) + priced["out"] * p.get("out", 0)
                                         + priced["cache_read"] * p.get("cache_read", 0)
                                         + priced["cache_write"] * p.get("cache_write", 0)) / 1e6, 6)
        out["teams"] = teams
        return out

    def progress(self) -> dict:
        """Для окна хоста (лаунчер): по сторонам — сколько героев у агентов, решений, вызовов и ошибок, первая
        ошибка агента («1 sniper: ошибка: …»), пауза стороны, если она идёт, и выбран ли предел вызовов."""
        now = time.monotonic()
        with self.lock:
            out = {}
            for t in self.backends:
                ags = sorted((a for a in self.agents.values() if a.team == t), key=lambda a: a.pos)
                err = next((f"{a.pos} {short_hero(a.hero)}: {a.state}" for a in ags
                            if a.state.startswith(("ошибка", "сбой"))), "")
                limit = (self._paid(t) and self.max_calls is not None
                         and self.calls_paid.get(t, 0) >= self.max_calls)       # предел вызовов стороны выбран
                out[t] = {"heroes": len(ags), "decisions": sum(a.seq for a in ags), "calls": self.stats[t]["calls"],
                          "errors": self.stats[t]["errors"], "error": err,
                          "pause": self.pause_why.get(t, "") if now < self.pause_until.get(t, 0.0) else "",
                          "limit": bool(limit), "max_calls": self.max_calls,
                          "model": self.model_seen.get(t, "")}
            return out

    def status(self) -> dict:
        summary = self.summary()
        with self.lock:
            agents = [{"team": a.team, "pos": a.pos, "hero": a.hero, "state": a.state, "calls": a.calls,
                       "errors": a.errors, "decision": a.decision, "memory": list(a.memory)}
                      for a in sorted(self.agents.values(), key=lambda a: (a.team, a.pos))]
            chat = {t: list(c) for t, c in self.chat.items()}
        return {"agents": agents, "summary": summary, "chat": chat,
                "backend": {t: getattr(b, "label", str(b)) for t, b in self.backends.items()}}

    def close(self) -> None:
        if self.pool:
            self.pool.shutdown(wait=False, cancel_futures=True)
