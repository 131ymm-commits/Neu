"""Разбор фразы тренера (текст после распознавания речи) в команды протокола.

Быстрый путь без ИИ: словарь + правила порядка слов. Что не разобрано
уверенно — помечается (confidence, clarify, unknown), и тогда фразу можно
отдать запасному разборщику на языковой модели (llm_fallback.py, позже).

Пример:
    ctx = MatchContext(team="radiant", agents=[Agent(1, "Miracle", ("миракл",)), ...])
    parse("Миракл, фарми лес, остальные на Рошана", ctx).commands
    → [farm(agents=[1], area=jungle_own), roshan(agents=[2,3,4,5])]
"""
from __future__ import annotations

import difflib
import re
from dataclasses import dataclass, field

from . import lexicon as L
from .protocol import ACTIONS, Command

ALL = [1, 2, 3, 4, 5]


@dataclass
class Agent:
    pos: int
    name: str = ""
    aliases: tuple = ()          # как тренер зовёт агента: («миракл», «мирак»)
    hero: str | None = None      # npc_dota_hero_*


@dataclass
class MatchContext:
    team: str = "radiant"        # radiant | dire — нужно для «лёгкой/сложной линии»
    agents: list = field(default_factory=lambda: [Agent(i) for i in ALL])
    enemy_heroes: list = field(default_factory=list)
    last_agents: list = field(default_factory=list)   # кому был прошлый приказ

    def remember(self, result: "ParseResult") -> None:
        for c in reversed(result.commands):
            if c.agents:
                self.last_agents = list(c.agents)
                return


@dataclass
class ParseResult:
    text: str
    commands: list
    unknown: list
    confidence: float


# --- нормализация ------------------------------------------------------------

def normalize(text: str) -> list[str]:
    t = text.lower().replace("ё", "е")
    t = re.sub(r"\b[тt]\s*-?\s*([1-4])\b", r"т\1", t)          # «Т-2», «t 2» → т2
    t = re.sub(r"[,.;!?:…]+", " | ", t)
    t = re.sub(r"[«»\"()\[\]{}]", " ", t)
    t = re.sub(r"(?<=\w)-(?=\w)", " ", t)                      # «рыцарь-дракон» → два слова
    toks = [w for w in t.split() if w]
    # склеить подряд идущие разделители
    out = []
    for w in toks:
        if w == "|" and (not out or out[-1] == "|"):
            continue
        out.append(w)
    while out and out[-1] == "|":
        out.pop()
    return out


def _verb_number(word: str) -> str:
    """Грубо: множественное («фармите», «пушим») или единственное («фарми»)."""
    if word.endswith(("те", "тесь", "емся", "имся", "ем", "им", "ем", "аем", "уем", "ем")):
        return "plural"
    if word.endswith(("и", "й", "ь", "ись", "йся", "ься")):
        return "single"
    return ""


# --- словарь, собранный под конкретный матч ----------------------------------

class _Index:
    def __init__(self, ctx: MatchContext):
        self.ctx = ctx
        self.phrases: dict[str, list] = {}

        def add(phrase, interp):
            lst = self.phrases.setdefault(phrase, [])
            if interp not in lst:
                lst.append(interp)

        for w in L.SEQ_WORDS: add(w, ("seq", None))
        for w in L.NEG_WORDS: add(w, ("neg", None))
        for w in L.URGENT_WORDS: add(w, ("urgent", None))
        for w in L.FILLERS: add(w, ("filler", None))
        for w in L.PREPS: add(w, ("prep", w))
        for w in L.ENEMY_MARK: add(w, ("enemy_mark", None))
        for w in L.OWN_MARK: add(w, ("own_mark", None))
        for w in L.PRONOUNS: add(w, ("pronoun", None))
        for w in L.ADDRESS_ALL: add(w, ("addr_all", None))
        for w in L.ADDRESS_REST: add(w, ("addr_rest", None))
        for w, pos in L.ADDRESS_ROLE.items(): add(w, ("addr", list(pos)))
        for w, pos in L.LANE_OR_ROLE.items(): add(w, ("lane_or_role", pos))
        for w in L.POSITION_WORDS: add(w, ("posword", None))
        for w, n in L.NUMBER_WORDS.items(): add(w, ("number", n))
        for w, a in L.ACTION_WORDS.items(): add(w, ("action", a))
        for w, pl in L.PLACE_PHRASES.items(): add(w, ("place", pl))
        for w in L.TOWER_WORDS: add(w, ("tower", None))
        for w, n in L.TIER_TOKENS.items(): add(w, ("tier", n))
        for w, item in L.ITEM_PHRASES.items(): add(w, ("item", item))

        # имена агентов и герои — с падежами
        self.name_forms: list[tuple[str, str, tuple]] = []   # (стем/слово, полное, interp)
        own_heroes = {a.hero: a.pos for a in ctx.agents if a.hero}
        enemy = set(ctx.enemy_heroes)
        for a in ctx.agents:
            for al in a.aliases:
                self._add_name(al, ("agent", a.pos))
        for hero, info in L.load_heroes().items():
            for al in info["aliases"]:
                if len(al.replace(" ", "")) <= 2 and hero not in own_heroes and hero not in enemy:
                    continue      # «та», «па», «ам» — только если герой есть в матче
                if hero in own_heroes:
                    interp = ("agent", own_heroes[hero])
                else:
                    interp = ("hero", hero)
                self._add_name(al, interp)
        self.max_len = max(len(p.split()) for p in self.phrases)
        self.fuzzy_keys = [f for f, full, it in self.name_forms if len(full) >= 5]
        self.fuzzy_map = {f: it for f, full, it in self.name_forms if len(full) >= 5}

    def _add_name(self, alias: str, interp):
        alias = alias.lower().replace("ё", "е").strip()
        if not alias:
            return
        lst = self.phrases.setdefault(alias, [])
        if interp not in lst:
            lst.append(interp)
        self.name_forms.append((alias, alias, interp))

    def lookup_name_case(self, words: list[str]):
        """Имя/герой в косвенном падеже: «мираклу», «инвокера», «пуджем»."""
        n = len(words)
        hits = []
        for _, full, interp in self.name_forms:
            parts = full.split()
            if len(parts) != n:
                continue
            # падеж меняет только первое слово («короля обезьян»)
            if words[1:] != parts[1:]:
                continue
            w, base = words[0], parts[0]
            stem = base[:-1] if base[-1] in "аяоеиыуьй" else base
            if len(stem) < 3:
                continue
            if w.startswith(stem) and w[len(stem):] in L.CASE_ENDINGS and w != base:
                hits.append(interp)
        return hits

    def fuzzy(self, word: str):
        if len(word) < 5:
            return None
        m = difflib.get_close_matches(word, self.fuzzy_keys, n=1, cutoff=0.82)
        if m:
            return self.fuzzy_map[m[0]]
        return None


@dataclass
class _Span:
    words: list
    interps: list
    fuzzy: bool = False
    oblique: bool = False     # имя в косвенном падеже: не обращение, а дополнение


def _tokenize(words: list[str], idx: _Index) -> list[_Span]:
    spans = []
    i = 0
    while i < len(words):
        if words[i] == "|":
            spans.append(_Span(["|"], [("sep", None)]))
            i += 1
            continue
        found = None
        for n in range(min(idx.max_len, len(words) - i), 0, -1):
            chunk = words[i:i + n]
            if "|" in chunk:
                continue
            phrase = " ".join(chunk)
            if phrase in idx.phrases:
                found = _Span(chunk, list(idx.phrases[phrase]))
                break
            case_hits = idx.lookup_name_case(chunk)
            if case_hits:
                found = _Span(chunk, case_hits, oblique=True)
                break
        if found is None:
            w = words[i]
            interps = []
            for stem, action in L.ACTION_STEMS:
                if w.startswith(stem):
                    interps.append(("action", action))
                    break
            if interps:
                found = _Span([w], interps)
            else:
                fz = idx.fuzzy(w)
                if fz:
                    found = _Span([w], [fz], fuzzy=True)
                else:
                    found = _Span([w], [("unknown", w)])
        else:
            # точная фраза могла быть и действием по основе: «смоки», «варды», «тп»
            if len(found.words) == 1 and not any(k == "action" for k, _ in found.interps):
                w = found.words[0]
                for stem, action in L.ACTION_STEMS:
                    if w.startswith(stem):
                        found.interps.append(("action", action))
                        break
        spans.append(found)
        i += len(found.words)
    return spans


# --- сборка команд -----------------------------------------------------------

WEAK_ACTIONS = {"move", "report", "press", "save_ult_hint", "buy_or_group"}
GROUPABLE = {"push", "roshan", "defend", "smoke", "tormentor", "retreat", "engage", "focus", "gank"}
ALLY_PREPS = {"с", "со", "к", "ко", "за"}


class _Clause:
    def __init__(self):
        self.agents: list[int] = []
        self.rest = False
        self.pronoun = False
        self.action: str | None = None
        self.verb = ""
        self.hints: set = set()
        self.lanes: list[str] = []
        self.rel_lanes: list[str] = []
        self.areas: list[str] = []
        self.places: list[str] = []
        self.enemies: list[str] = []
        self.enemy_pos: list[int] = []
        self.allies: list[int] = []
        self.items: list[str] = []
        self.tier: int | None = None
        self.tower = False
        self.lane_or_role: list[int] = []
        self.negated = False
        self.urgent = False
        self.after_prev = False
        self.enemy_next = False
        self.own_next = False
        self.last_prep = ""
        self.pending_number: int | None = None
        self.pending_posword = False
        self.words: list[str] = []
        self.content = 0
        self.known = 0
        self.fuzzy = 0

    def has_action(self):
        return self.action is not None

    def empty(self):
        return not (self.action or self.agents or self.rest or self.lanes or self.rel_lanes
                    or self.areas or self.places or self.enemies or self.enemy_pos or self.items
                    or self.allies or self.tower or self.lane_or_role or self.negated or self.hints)


def parse(text: str, ctx: MatchContext | None = None) -> ParseResult:
    ctx = ctx or MatchContext()
    idx = _Index(ctx)
    words = normalize(text)
    spans = _tokenize(words, idx)

    clauses: list[_Clause] = []
    cur = _Clause()
    unknown: list[str] = []

    def close(new_after_prev=False):
        nonlocal cur
        if not cur.empty():
            clauses.append(cur)
        cur = _Clause()
        cur.after_prev = new_after_prev

    for sp in spans:
        kinds = [k for k, _ in sp.interps]
        val = dict(sp.interps)
        word = " ".join(sp.words)

        if "sep" in kinds:
            if cur.has_action():
                close()
            continue
        if "seq" in kinds:
            if cur.has_action():
                close(new_after_prev=True)
            else:
                cur.after_prev = True
            continue
        if "filler" in kinds:
            continue

        cur.words.append(word)
        cur.content += 1
        if "unknown" in kinds:
            unknown.append(word)
            continue
        cur.known += 1
        if sp.fuzzy:
            cur.fuzzy += 1

        if "neg" in kinds:
            cur.negated = True
            continue
        if "urgent" in kinds:
            cur.urgent = True
            continue
        if "prep" in kinds:
            cur.last_prep = val["prep"]
            continue
        if "enemy_mark" in kinds:
            cur.enemy_next = True
            continue
        if "own_mark" in kinds:
            cur.own_next = True
            continue
        if "pronoun" in kinds:
            if cur.has_action():
                close()
            cur.pronoun = True
            continue
        if "posword" in kinds:
            if cur.pending_number:
                _add_agents(cur, [cur.pending_number])
                cur.pending_number = None
            else:
                cur.pending_posword = True
            continue
        if "number" in kinds:
            n = val["number"]
            if cur.pending_posword:
                cur.pending_posword = False
                _add_agents(cur, [n])
            else:
                cur.pending_number = n       # «вторую башню», «вторая позиция»
            continue
        if "tier" in kinds:
            cur.tier = val["tier"]
            cur.tower = True
            continue
        if "tower" in kinds:
            cur.tower = True
            if cur.pending_number:
                cur.tier = cur.pending_number
                cur.pending_number = None
            continue

        # адресат или союзник-цель
        is_agent_like = any(k in ("addr_all", "addr_rest", "addr", "agent") for k in kinds)
        if is_agent_like:
            positions = []
            if "agent" in kinds:
                positions = [val["agent"]]
            elif "addr" in kinds:
                positions = list(val["addr"])
            elif "addr_all" in kinds:
                positions = list(ALL)
            if cur.enemy_next and "addr" in kinds:
                cur.enemy_pos += positions          # «их керри»
                cur.enemy_next = False
                continue
            # обращение — в именительном падеже («Миракл, …»); «Мираклу», «с Мираклом» — союзник
            as_ally = (cur.last_prep in ALLY_PREPS or cur.action in ("follow", "save")
                       or (sp.oblique and "agent" in kinds))
            if as_ally and positions and "addr_all" not in kinds:
                cur.allies += positions
                cur.last_prep = ""
                continue
            if cur.has_action():
                close()
            if "addr_rest" in kinds:
                cur.rest = True
            else:
                _add_agents(cur, positions)
            continue

        if "lane_or_role" in kinds:
            pos = val["lane_or_role"]
            lane_val = val.get("place")
            if cur.action in ("follow", "save") or cur.last_prep in ALLY_PREPS:
                cur.allies.append(pos)
                continue
            if cur.has_action() or cur.agents or cur.rest:
                if lane_val is None:
                    lane_val = ("lane", "mid") if pos == 2 else ("rel_lane", "off")
                _add_place(cur, lane_val)
            else:
                cur.lane_or_role.append(pos)
            continue

        if "hero" in kinds:
            hero = val["hero"]
            cur.enemies.append(hero)
            cur.enemy_next = False
            continue

        # предметы и действия: одно слово может быть и тем и другим («смоки», «тп»)
        has_item = "item" in kinds
        has_action = "action" in kinds
        if has_item and cur.action == "press":
            cur.action = "use_item"
            cur.items.append(val["item"])
            continue
        if has_item and (cur.action in ("buy", "buy_or_group") or (cur.action and not has_action)):
            cur.items.append(val["item"])
            continue
        if has_item and not has_action:
            cur.items.append(val["item"])
            continue

        if "place" in kinds:
            _add_place(cur, val["place"])
            continue

        if has_action:
            if not _set_action(cur, val["action"], sp.words[-1]):
                # новый приказ тем же адресатам: «Миракл, фарми и пушь»
                agents, rest, pronoun = list(cur.agents), cur.rest, cur.pronoun
                close()
                cur.agents, cur.rest, cur.pronoun = agents, rest, pronoun
                _set_action(cur, val["action"], sp.words[-1])
            continue

    close()

    # --- превращение предложений в команды ---
    commands: list[Command] = []
    used_agents: list[int] = []
    prev_agents: list[int] = []
    for cl in clauses:
        cmd = _finalize(cl, ctx, prev_agents, used_agents)
        if cmd is None:
            continue
        if commands and _same(commands[-1], cmd):
            continue
        commands.append(cmd)
        if cmd.agents:
            prev_agents = list(cmd.agents)
            used_agents += [a for a in cmd.agents if a not in used_agents]

    content = sum(c.content for c in clauses) + 0
    known = sum(c.known for c in clauses)
    fuzz = sum(c.fuzzy for c in clauses)
    if content == 0:
        conf = 0.0
    else:
        conf = max(0.0, min(1.0, known / max(content, 1) - 0.15 * fuzz))
    for c in commands:
        c.confidence = round(min(c.confidence, conf), 3)
    return ParseResult(text=text, commands=commands, unknown=unknown, confidence=round(conf, 3))


def _add_agents(cl: _Clause, positions):
    for p in positions:
        if p not in cl.agents:
            cl.agents.append(p)


def _add_place(cl: _Clause, place):
    kind, v = place
    if kind == "lane":
        cl.lanes.append(v)
    elif kind == "rel_lane":
        cl.rel_lanes.append(v)
    elif kind == "area":
        if v == "jungle":
            if cl.enemy_next:
                v = "jungle_enemy"
            else:
                v = "jungle_own"
        cl.areas.append(v)
    elif kind == "place":
        cl.places.append(v)
    cl.enemy_next = False
    cl.own_next = False


def _set_action(cl: _Clause, action: str, verb_word: str) -> bool:
    """Записать действие в предложение. False — действие несовместимо с уже
    названным, и вызывающий должен начать новое предложение."""
    if cl.action is None:
        cl.action = action
        cl.verb = verb_word
        return True
    if action == cl.action:
        return True
    a, b = cl.action, action
    # сочетания внутри одного приказа
    if {a, b} == {"smoke", "gank"}:
        cl.action = "smoke"
        cl.hints.add("then_gank")
        return True
    if a in ("press", "save_ult_hint") and b == "use_ult":
        cl.action = "save_ult" if a == "save_ult_hint" else "use_ult"
        cl.verb = verb_word
        return True
    if b in ("press", "save_ult_hint"):
        return True
    if a in WEAK_ACTIONS and a != "buy_or_group":
        cl.action, cl.verb = b, verb_word
        return True
    if b == "move":
        return True
    if a == "group" and b in GROUPABLE:
        cl.action, cl.verb = b, verb_word
        cl.hints.add("group")
        return True
    if b == "group" and a in GROUPABLE:
        cl.hints.add("group")
        return True
    if a in ("focus", "buy", "buy_or_group", "engage") and b in ("roshan", "tormentor"):
        cl.action, cl.verb = b, verb_word
        return True
    if {a, b} == {"engage", "focus"}:
        cl.action = "engage"
        return True
    return False


def _rel_to_abs(rel: str, team: str) -> str:
    if team == "dire":
        return "top" if rel == "safe" else "bot"
    return "bot" if rel == "safe" else "top"


def _same(a: Command, b: Command) -> bool:
    return a.action == b.action and a.agents == b.agents and a.params == b.params


def _finalize(cl: _Clause, ctx: MatchContext, prev_agents, used_agents) -> Command | None:
    lanes = cl.lanes + [_rel_to_abs(r, ctx.team) for r in cl.rel_lanes]
    action = cl.action

    # роль-или-линия («мид»): адресат при глаголе в ед. числе, иначе линия
    if cl.lane_or_role:
        number = _verb_number(cl.verb) if cl.verb else ""
        other_place = bool(lanes or cl.areas or cl.places)
        if (number == "single" or other_place) and not cl.agents:
            for p in cl.lane_or_role:
                if p not in cl.agents:
                    cl.agents.append(p)
        else:
            for p in cl.lane_or_role:
                lanes.append("mid" if p == 2 else _rel_to_abs("off", ctx.team))

    if action == "buy_or_group":
        action = "buy" if cl.items else "group"
    if action == "press":
        action = None
    if action == "save_ult_hint":
        action = "hold"

    # действие не названо — выводим из того, что сказано
    if action is None:
        if cl.items:
            action = "buy"
        elif "roshan" in cl.places:
            action = "roshan"
        elif "base" in cl.places:
            action = "retreat"
        elif cl.areas:
            action = "farm"
        elif cl.allies:
            action = "follow"
        elif cl.enemies or cl.enemy_pos:
            action = "focus"
        elif cl.tower:
            action = "push"
        elif lanes:
            action = "push"
        elif cl.places:
            action = "move"
        elif cl.negated:
            action = "hold"
        else:
            if cl.agents or cl.rest:
                return Command(action="report", agents=_agents_or_all(cl, prev_agents, used_agents),
                               text=" ".join(cl.words), confidence=0.3,
                               clarify="что им делать?")
            return None

    if action == "buy" and not cl.items and (cl.places or lanes or cl.areas):
        action = "move"
    if action == "move":
        if "roshan" in cl.places:
            action = "roshan"
        elif "base" in cl.places:
            action = "retreat"
        elif cl.areas:
            action = "farm"
    if action == "buy" and not cl.items and cl.tower:
        action = "push"

    params: dict = {}
    negated_what = None
    if cl.negated:
        if action == "use_ult":
            action = "save_ult"
        elif action in ("hold", "cancel", "save_ult", "free"):
            pass
        else:
            negated_what = action
            action = "hold"

    # адресаты
    single = _verb_number(cl.verb) == "single" if cl.verb else False
    plural = _verb_number(cl.verb) == "plural" if cl.verb else False
    clarify = ""
    if cl.agents:
        agents = list(cl.agents)
    elif cl.rest:
        agents = [p for p in ALL if p not in used_agents] or list(ALL)
    elif cl.pronoun and ctx.last_agents:
        agents = list(prev_agents or ctx.last_agents)
    elif prev_agents:
        agents = list(prev_agents)
    else:
        spec = ACTIONS[action]
        if plural or spec.scope == "team":
            agents = list(ALL)
        elif ctx.last_agents:
            agents = list(ctx.last_agents)
        elif single:
            agents = []
            clarify = "кому?"
        else:
            agents = list(ALL)
    if cl.allies:
        agents = [a for a in agents if a not in cl.allies] or agents

    # параметры по действию
    enemy = cl.enemies[0] if cl.enemies else None
    if action == "farm":
        if cl.areas:
            params["area"] = cl.areas[0]
        elif lanes:
            params["area"] = "lane"
            params["lane"] = lanes[0]
        else:
            params["area"] = "auto"
    elif action in ("push", "split"):
        params["lane"] = lanes[0] if lanes else "auto"
        if action == "push":
            params["group"] = len(agents) >= 2 or "group" in cl.hints
            if cl.tier:
                params["tier"] = cl.tier
    elif action == "defend":
        if "base" in cl.places:
            params["place"] = "base"
        else:
            params["lane"] = lanes[0] if lanes else "auto"
        if cl.tier:
            params["tier"] = cl.tier
    elif action == "gank":
        if enemy:
            params["enemy"] = enemy
        if cl.enemy_pos:
            params["enemy_pos"] = cl.enemy_pos[0]
        params["lane"] = lanes[0] if lanes else "auto"
    elif action == "group":
        if cl.places:
            params["place"] = cl.places[0]
        elif lanes:
            params["lane"] = lanes[0]
    elif action == "smoke":
        if "then_gank" in cl.hints:
            params["then"] = "gank"
        if lanes:
            params["lane"] = lanes[0]
        if enemy:
            params["enemy"] = enemy
    elif action == "retreat":
        if cl.places:
            params["place"] = cl.places[0]
    elif action in ("focus", "engage", "use_ult"):
        if enemy:
            params["enemy"] = enemy
        if cl.enemy_pos:
            params["enemy_pos"] = cl.enemy_pos[0]
        if action == "focus" and not enemy and not cl.enemy_pos:
            action = "engage"          # «бейте!» без цели — начинаем драку
    elif action == "hold":
        if negated_what:
            params["what"] = negated_what
    elif action == "ward":
        if cl.places:
            params["place"] = cl.places[0]
        elif cl.areas:
            params["place"] = cl.areas[0]
        elif lanes:
            params["lane"] = lanes[0]
        if "item_ward_sentry" in cl.items:
            params["kind"] = "sentry"
    elif action == "stack":
        if cl.areas and cl.areas[0] == "ancients":
            params["place"] = "ancients"
    elif action == "use_item":
        params["item"] = cl.items[0]
    elif action == "buy":
        if cl.items:
            params["item"] = cl.items[0]
        else:
            clarify = clarify or "что купить?"
    elif action in ("save", "follow"):
        if cl.allies:
            params["ally"] = cl.allies[0]
        else:
            clarify = clarify or "кому помочь?"
    elif action == "move" and lanes and len(agents) >= 2:
        action = "push"                # «идите на топ» вдвоём и больше — давим линию
        params["lane"] = lanes[0]
        params["group"] = True
    elif action in ("tp", "move"):
        if cl.places:
            params["place"] = cl.places[0]
        elif cl.areas:
            params["place"] = cl.areas[0]
        elif lanes:
            params["lane"] = lanes[0]
        elif cl.allies and action == "move":
            action = "follow"
            params["ally"] = cl.allies[0]
        else:
            clarify = clarify or "куда?"

    return Command(action=action, agents=sorted(agents), params=params, urgent=cl.urgent,
                   after_prev=cl.after_prev, text=" ".join(cl.words), clarify=clarify)


def _agents_or_all(cl, prev_agents, used_agents):
    if cl.agents:
        return list(cl.agents)
    if cl.rest:
        return [p for p in ALL if p not in used_agents] or list(ALL)
    return list(prev_agents or ALL)
