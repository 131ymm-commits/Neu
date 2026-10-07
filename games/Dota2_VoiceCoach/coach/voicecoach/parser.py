"""Разбор фразы тренера (текст после распознавания речи) в команды протокола.

Быстрый путь без ИИ: словарь + правила порядка слов и падежей. Что не разобрано уверенно —
помечается (confidence, clarify, unknown), и тогда фразу можно отдать запасному разборщику на
языковой модели (позже).

Пример:
    ctx = MatchContext(team="radiant", agents=[Agent(1, "Miracle", ("миракл",)), ...])
    parse("Миракл, фарми лес, остальные на Рошана", ctx).commands
    → [farm(agents=[1], area=jungle_own), roshan(agents=[2,3,4,5])]

Правила (проверены тестами tests/test_parser.py; часть добавлена по ошибкам замера PARSE-01):
- обращение — в именительном падеже («Миракл, …»); в дательном при действии — тоже адресат
  («Васе стакать древних»); после «к/за» и при «помоги/спаси» — союзник;
- «X с Y» при глаголе во мн. числе или без глагола — оба адресаты; «иди с Y» — союзник;
- «Миракл фарми бот, Топсон мид» — пропущенный глагол переносится из прошлой части;
- «вард у Рошана», «тп на Рошана» — Рошан здесь место, а не приказ;
- «не» относится к следующему действию; «ой, нет, бот» заменяет названное раньше место;
- «па пошла на мид» — сведения, а не приказ: переспрос.
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
        """Запомнить, кому был прошлый личный приказ: только если явно назван один агент.
        После «все на Рошана» фраза «купи бкб» должна переспросить «кому?», а не уйти всем."""
        if not result.commands:
            return
        if result.focus_agents:
            self.last_agents = list(result.focus_agents) if len(result.focus_agents) == 1 else []
        elif any(len(c.agents) >= 2 for c in result.commands):
            self.last_agents = []          # был общий приказ — личный без адресата переспросит
        # иначе приказ ушёл прошлому адресату («Вася, фарми лес» → «купи бкб») — помним его же


@dataclass
class ParseResult:
    text: str
    commands: list
    unknown: list
    confidence: float
    focus_agents: list = field(default_factory=list)   # явно названные адресаты последнего приказа


# --- нормализация ------------------------------------------------------------

def normalize(text: str) -> list[str]:
    t = text.lower().replace("ё", "е")
    t = re.sub(r"\b[тt]\s*-?\s*([1-4])\b", r"т\1", t)          # «Т-2», «t 2» → т2
    t = re.sub(r"[,.;!?:…—–]+", " | ", t)
    t = re.sub(r"[«»\"()\[\]{}]", " ", t)
    t = re.sub(r"(?<=\w)-(?=\w)", " ", t)                      # «рыцарь-дракон» → два слова
    out = []
    for w in t.split():
        if w == "|" and (not out or out[-1] == "|"):
            continue
        out.append(w)
    while out and out[-1] == "|":
        out.pop()
    return out


def _verb_number(word: str) -> str:
    """Грубо: множественное («фармите», «пушим») или единственное («фарми»)."""
    if not word:
        return ""
    if word.endswith(("те", "тесь", "емся", "имся", "ем", "им", "аем", "уем")):
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
        for w in L.OBJ_PRONOUNS: add(w, ("obj_pronoun", None))
        for w in L.ANAPHORA: add(w, ("anaphora", None))
        for w in L.CORRECTION_WORDS: add(w, ("correction", None))
        for w in L.INFO_WORDS: add(w, ("info", None))
        for w in L.EXCEPT_WORDS: add(w, ("except", None))
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
        self.name_forms: list[tuple[str, str, tuple]] = []
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
            if len(parts) != n or words[1:] != parts[1:]:
                continue
            w, base = words[0], parts[0]
            stem = base[:-1] if base[-1] in "аяоеиыуьй" else base
            if len(stem) < 3:
                continue
            if w.startswith(stem) and w[len(stem):] in L.CASE_ENDINGS and w != base:
                if interp not in hits:
                    hits.append(interp)
        return hits

    def fuzzy(self, word: str):
        if len(word) < 5:
            return None
        m = difflib.get_close_matches(word, self.fuzzy_keys, n=1, cutoff=0.82)
        return self.fuzzy_map[m[0]] if m else None


@dataclass
class _Span:
    words: list
    interps: list
    fuzzy: bool = False
    oblique: bool = False     # имя в косвенном падеже


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
                found = _Span([w], [fz], fuzzy=True) if fz else _Span([w], [("unknown", w)])
        elif len(found.words) == 1 and not any(k == "action" for k, _ in found.interps):
            # точное слово могло быть и действием по основе: «смоки», «варды»
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
ALLY_PREPS = {"к", "ко", "за"}            # «иди к Мираклу», «за ней»
WITH_PREPS = {"с", "со"}                  # «Мира с Васей ставьте» / «иди с Топсоном»
PLACE_ACTIONS = {"ward", "tp", "move", "stack", "group", "follow"}   # Рошан при них — место
PLACE_PREPS = {"у", "возле", "около", "под"}
# «иди» после законченного приказа — новый приказ («купи тп и иди на бот»), а после
# пуша, фарма и т.п. — просто часть того же приказа («пушим, идём на топ»)
MOVE_ABSORBERS = {"push", "defend", "gank", "group", "roshan", "tormentor", "smoke", "retreat",
                  "focus", "engage", "farm", "split", "follow", "move", "press", "save_ult_hint"}


class _Clause:
    def __init__(self):
        self.agents: list[int] = []
        self.dative: list[int] = []          # имя в косвенном падеже без предлога
        self.with_agents: list[int] = []     # «с Васей»
        self.rest = False
        self.pronoun = False
        self.ambiguous_addr = False
        self.excluded: list[int] = []        # «все кроме Миракла»
        self.except_next = False
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
        self.neg_pending = False
        self.correction = False
        self.info = False
        self.urgent = False
        self.after_prev = False
        self.enemy_next = False
        self.last_prep = ""
        self.last_kind = ""
        self.pending_number: int | None = None
        self.pending_posword = False
        self.words: list[str] = []
        self.content = 0
        self.known = 0
        self.fuzzy = 0

    def has_action(self):
        return self.action is not None

    def has_object(self):
        return bool(self.lanes or self.rel_lanes or self.areas or self.places or self.enemies
                    or self.enemy_pos or self.items or self.tower)

    def addressed(self):
        return bool(self.agents or self.dative or self.rest)

    def empty(self):
        return not (self.action or self.addressed() or self.has_object() or self.allies
                    or self.lane_or_role or self.negated or self.hints or self.info or self.with_agents)


def _add_agents(lst, positions):
    for p in positions:
        if p not in lst:
            lst.append(p)


def _add_place(cl: _Clause, place, utter):
    kind, v = place
    if cl.correction:
        # «пушь топ, ой, нет, бот»: новое место заменяет прежнее
        for lst in (cl.lanes, cl.rel_lanes, cl.areas, cl.places):
            if lst:
                lst.pop()
                break
        cl.correction = False
    if kind == "lane":
        cl.lanes.append(v)
        cl.last_kind = "lane"
    elif kind == "rel_lane":
        cl.rel_lanes.append(v)
        cl.last_kind = "lane"
    elif kind == "area":
        if v == "jungle":
            v = "jungle_enemy" if cl.enemy_next else "jungle_own"
            cl.last_kind = "area_jungle"
        else:
            cl.last_kind = "area"
        cl.areas.append(v)
    elif kind == "place":
        cl.places.append(v)
        cl.last_kind = "place"
    cl.enemy_next = False
    utter["last_place"] = (kind, v) if kind != "area" else ("area", "jungle" if v.startswith("jungle") else v)


def _set_action(cl: _Clause, action: str, verb_word: str) -> bool:
    """Записать действие в предложение. False — несовместимо с уже названным: нужен новый приказ."""
    if cl.action is None:
        cl.action = action
        cl.verb = verb_word
        return True
    if action == cl.action:
        return True
    a, b = cl.action, action
    if {a, b} == {"smoke", "gank"}:
        cl.action = "smoke"
        cl.hints.add("then_gank")
        return True
    if a in ("press", "save_ult_hint") and b == "use_ult":
        cl.action = "save_ult" if a == "save_ult_hint" else "use_ult"
        return True                                   # число глагола — у «дай/держи»
    if b in ("press", "save_ult_hint"):
        return True
    if a == "defend" and b == "give_up":              # «держим мид, не отдаём вышку»
        return True
    if b == "move":
        return a in MOVE_ABSORBERS
    if a in WEAK_ACTIONS and a != "buy_or_group":
        cl.action, cl.verb = b, verb_word
        return True
    if a == "group" and b in GROUPABLE:
        cl.action, cl.verb = b, verb_word
        cl.hints.add("group")
        return True
    if b == "group" and a in GROUPABLE:
        cl.hints.add("group")
        return True
    if a in ("focus", "buy", "buy_or_group") and b in ("roshan", "tormentor"):
        cl.action, cl.verb = b, verb_word
        return True
    return False


def _next_content(spans, i):
    """Есть ли после i в этом предложении что-то кроме незнакомых и служебных слов."""
    for sp in spans[i + 1:]:
        kinds = [k for k, _ in sp.interps]
        if "sep" in kinds or "seq" in kinds:
            return False
        if all(k in ("filler", "unknown") for k in kinds):
            continue
        return True
    return False


def parse(text: str, ctx: MatchContext | None = None) -> ParseResult:
    ctx = ctx or MatchContext()
    idx = _Index(ctx)
    words = normalize(text)
    spans = _tokenize(words, idx)

    clauses: list[_Clause] = []
    cur = _Clause()
    unknown: list[str] = []
    utter = {"last_place": None}
    last_agents_in_utter: list[int] = []

    def close(new_after_prev=False):
        nonlocal cur, last_agents_in_utter
        if not cur.empty():
            clauses.append(cur)
            if cur.agents or cur.dative:
                last_agents_in_utter = list(cur.agents or cur.dative)
        cur = _Clause()
        cur.after_prev = new_after_prev

    for i, sp in enumerate(spans):
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
            cur.neg_pending = True
            continue
        if "urgent" in kinds:
            cur.urgent = True
            continue
        if "correction" in kinds:
            cur.correction = True
            continue
        if "info" in kinds:
            cur.info = True
            continue
        if "except" in kinds:
            cur.except_next = True
            continue
        if "prep" in kinds:
            cur.last_prep = val["prep"]
            continue
        if "enemy_mark" in kinds:
            if cur.last_kind == "area_jungle" and cur.areas and cur.areas[-1] == "jungle_own":
                cur.areas[-1] = "jungle_enemy"           # «лес врага»
            else:
                cur.enemy_next = True
            continue
        if "own_mark" in kinds:
            continue
        if "anaphora" in kinds:
            if utter["last_place"]:
                _add_place(cur, utter["last_place"], utter)
            continue
        if "obj_pronoun" in kinds:
            if cur.last_prep in ALLY_PREPS | WITH_PREPS and last_agents_in_utter:
                _add_agents(cur.allies, last_agents_in_utter)
                cur.last_prep = ""
            continue
        if "pronoun" in kinds:
            if cur.has_action():
                close()
            cur.pronoun = True
            continue
        if "posword" in kinds:
            if cur.pending_number:
                _add_agents(cur.agents, [cur.pending_number])
                cur.pending_number = None
            else:
                cur.pending_posword = True
            continue
        if "number" in kinds:
            n = val["number"]
            if cur.pending_posword:
                cur.pending_posword = False
                _add_agents(cur.agents, [n])
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

        # адресат, союзник или цель
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
            if cur.except_next and positions:
                _add_agents(cur.excluded, positions)   # «все кроме Миракла»
                cur.except_next = False
                continue
            if positions and "addr_all" not in kinds:
                if cur.last_prep in ALLY_PREPS or cur.action in ("follow", "save"):
                    _add_agents(cur.allies, positions)
                    cur.last_prep = ""
                    continue
                if cur.last_prep in WITH_PREPS:
                    _add_agents(cur.with_agents, positions)
                    cur.last_prep = ""
                    continue
            # обращение в конце фразы: «заходи первым, Коллапс»
            if (cur.has_action() and not cur.addressed() and not _next_content(spans, i)
                    and "addr_rest" not in kinds):
                _add_agents(cur.dative if sp.oblique else cur.agents, positions)
                continue
            if cur.has_action() or (cur.addressed() and cur.has_object()):
                close()
            if "addr_rest" in kinds:
                cur.rest = True
            elif sp.oblique and "agent" in kinds:
                _add_agents(cur.dative, positions)
            else:
                _add_agents(cur.agents, positions)
                if word in L.AMBIGUOUS_ROLE:
                    cur.ambiguous_addr = True
            continue

        if "lane_or_role" in kinds:
            pos = val["lane_or_role"]
            lane_val = val.get("place")
            if cur.action in ("follow", "save") or cur.last_prep in ALLY_PREPS:
                _add_agents(cur.allies, [pos])
                continue
            if cur.has_action() or cur.addressed():
                if lane_val is None:
                    lane_val = ("lane", "mid") if pos == 2 else ("rel_lane", "off")
                _add_place(cur, lane_val, utter)
            else:
                cur.lane_or_role.append(pos)
            continue

        if "hero" in kinds:
            cur.enemies.append(val["hero"])
            cur.enemy_next = False
            continue

        has_item = "item" in kinds
        has_action = "action" in kinds
        # Рошан при «вард», «тп», «иди»… или после «у» — место, а не приказ
        if has_action and val["action"] == "roshan" and (cur.action in PLACE_ACTIONS
                                                          or cur.last_prep in PLACE_PREPS):
            _add_place(cur, ("place", "roshan"), utter)
            continue
        if has_item and cur.action == "press":
            item = val["item"]
            # «дай вард на Рошана» — поставить вард; «прожми бкб», «кидай еул» — применить
            cur.action = "ward" if item in ("item_ward_observer", "item_ward_sentry") else "use_item"
            cur.items.append(item)
            continue
        if has_item and (cur.action in ("buy", "buy_or_group") or (cur.action and not has_action)):
            cur.items.append(val["item"])
            continue
        if has_item and not has_action:
            cur.items.append(val["item"])
            continue

        if "place" in kinds:
            _add_place(cur, val["place"], utter)
            continue

        if has_action:
            negated_now = cur.neg_pending
            cur.neg_pending = False
            action = val["action"]
            if action == "buyback_or_hero":
                action = "buyback"
            if cur.action is None:
                cur.negated = cur.negated or negated_now
            elif negated_now and not (cur.action == "defend" and action == "give_up"):
                # «не» относится к новому действию: отдельный приказ тем же адресатам
                agents, dative, rest = list(cur.agents), list(cur.dative), cur.rest
                close()
                cur.agents, cur.dative, cur.rest = agents, dative, rest
                cur.negated = True
            if not _set_action(cur, action, sp.words[-1]):
                # новый приказ тем же адресатам: «Миракл, фарми и пушь»
                agents, dative, rest, pronoun = list(cur.agents), list(cur.dative), cur.rest, cur.pronoun
                close()
                cur.agents, cur.dative, cur.rest, cur.pronoun = agents, dative, rest, pronoun
                _set_action(cur, action, sp.words[-1])
            continue

    close()

    # --- превращение предложений в команды ---
    commands: list[Command] = []
    implicit: list[bool] = []
    used_agents: list[int] = []
    prev_agents: list[int] = []
    prev_action: str | None = None
    focus_agents: list[int] = []
    for cl in clauses:
        explicit = sorted(set(cl.agents) | set(cl.dative)) if (cl.agents or cl.dative) else []
        res = _finalize(cl, ctx, prev_agents, used_agents, prev_action)
        if res is None:
            continue
        cmd, was_implicit = res
        if explicit and not cmd.clarify:
            focus_agents = [a for a in cmd.agents if a in explicit] or explicit
        if commands and _same(commands[-1], cmd):
            continue
        commands.append(cmd)
        implicit.append(was_implicit)
        if cmd.agents:
            prev_agents = list(cmd.agents)
            used_agents += [a for a in cmd.agents if a not in used_agents]
        if not cmd.clarify:
            prev_action = cmd.action

    # «пушим топ, а Миракл сплитит бот»: кто получил личный приказ — не в «всех» этой фразы
    for i, cmd in enumerate(commands):
        if not implicit[i] or len(cmd.agents) < 2:
            continue
        # не исключаем, если личный приказ помогает общему: «дефаем мид, Миракл, тпшнись туда же»
        named = {a for j, other in enumerate(commands) if j != i and not implicit[j]
                 and not _supports(other, cmd) for a in other.agents}
        rest = [a for a in cmd.agents if a not in named]
        if rest and len(rest) < len(cmd.agents):
            cmd.agents = rest
            if cmd.action == "push":
                cmd.params["group"] = len(rest) >= 2

    content = sum(c.content for c in clauses)
    known = sum(c.known for c in clauses)
    fuzz = sum(c.fuzzy for c in clauses)
    conf = 0.0 if content == 0 else max(0.0, min(1.0, known / content - 0.15 * fuzz))
    for c in commands:
        c.confidence = round(min(c.confidence, conf), 3)
    return ParseResult(text=text, commands=commands, unknown=unknown, confidence=round(conf, 3),
                       focus_agents=focus_agents)


def _supports(personal: Command, team_cmd: Command) -> bool:
    """Личный приказ ведёт туда же, куда общий (тп/идти на ту же линию или место)."""
    if personal.action not in ("tp", "move", "follow"):
        return False
    for k in ("lane", "place"):
        v = personal.params.get(k)
        if v is not None and v == team_cmd.params.get(k):
            return True
    return False


def _rel_to_abs(rel: str, team: str) -> str:
    if team == "dire":
        return "top" if rel == "safe" else "bot"
    return "bot" if rel == "safe" else "top"


def _same(a: Command, b: Command) -> bool:
    return a.action == b.action and a.agents == b.agents and a.params == b.params


def _finalize(cl: _Clause, ctx: MatchContext, prev_agents, used_agents, prev_action):
    """Предложение → (команда, адресаты_по_умолчанию) или None."""
    lanes = cl.lanes + [_rel_to_abs(r, ctx.team) for r in cl.rel_lanes]
    action = cl.action

    # роль-или-линия («мид»): адресат при глаголе в ед. числе, иначе линия
    if cl.lane_or_role:
        number = _verb_number(cl.verb)
        other_place = bool(lanes or cl.areas or cl.places)
        if (number == "single" or other_place) and not cl.agents:
            _add_agents(cl.agents, cl.lane_or_role)
        else:
            for p in cl.lane_or_role:
                lanes.append("mid" if p == 2 else _rel_to_abs("off", ctx.team))

    # сведения о враге без приказа: «па пошла на мид»
    if cl.info and action is None:
        return Command(action="report", agents=[], text=" ".join(cl.words), confidence=0.3,
                       clarify="это сведения или приказ?"), False

    if action == "buy_or_group":
        action = "buy" if cl.items else "group"
    if action == "press":
        action = "use_item" if cl.items else None
    if action == "save_ult_hint":
        action = "hold"
    if action == "give_up":
        action = "defend" if cl.negated else "retreat"
        cl.negated = False

    # пропущенный глагол: «Миракл фарми бот, Топсон мид»
    if (action is None and prev_action and (cl.agents or cl.dative)
            and (lanes or cl.areas or cl.places)):
        action = prev_action

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
        elif cl.tower or lanes:
            action = "push"
        elif cl.places:
            action = "move"
        elif cl.negated or cl.neg_pending:
            action = "hold"
        elif cl.addressed():
            return Command(action="report", agents=_agents_or_all(cl, prev_agents, used_agents),
                           text=" ".join(cl.words), confidence=0.3, clarify="что им делать?"), False
        else:
            return None

    if action == "buy" and not cl.items and (cl.places or lanes or cl.areas):
        action = "move"
    if action == "buy" and not cl.items and cl.tower:
        action = "push"
    if action == "move":
        if "roshan" in cl.places:
            action = "roshan"
        elif "base" in cl.places:
            action = "retreat"
        elif cl.areas:
            action = "farm"

    params: dict = {}
    negated_what = None
    if cl.negated:
        if action == "use_ult":
            action = "save_ult"
        elif action not in ("hold", "cancel", "save_ult", "free"):
            negated_what = action
            action = "hold"

    # адресаты
    number = _verb_number(cl.verb)
    single, plural = number == "single", number == "plural"
    clarify = ""
    agents = list(cl.agents)
    if cl.dative:
        if action in ("follow", "save"):
            _add_agents(cl.allies, cl.dative)      # «помоги Мираклу», «Мираклу помоги»
        else:
            _add_agents(agents, cl.dative)         # «Васе стакать древних»: адресат
    if cl.with_agents:
        if action in ("follow", "move", "save"):
            _add_agents(cl.allies, cl.with_agents)
            if action == "move":
                action = "follow"
        elif not single and agents:
            _add_agents(agents, cl.with_agents)    # «Мира с Васей ставьте»
    was_implicit = False
    if agents:
        pass
    elif cl.rest:
        agents = [p for p in ALL if p not in used_agents] or list(ALL)
    elif cl.pronoun and (prev_agents or ctx.last_agents):
        agents = list(prev_agents or ctx.last_agents)
    elif prev_agents:
        agents = list(prev_agents)
    else:
        spec = ACTIONS[action]
        if plural or spec.scope == "team":
            agents = list(ALL)
            was_implicit = True
        elif ctx.last_agents:
            agents = list(ctx.last_agents)
        else:
            agents = []
            clarify = "кому?"
    if cl.excluded:
        agents = [a for a in agents if a not in cl.excluded] or agents
    if cl.ambiguous_addr and single:
        agents, clarify = [], "какой саппорт: четвёрка или пятёрка?"
    if cl.allies:
        agents = [a for a in agents if a not in cl.allies] or agents

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
        if enemy:
            params["enemy"] = enemy
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

    cmd = Command(action=action, agents=sorted(agents), params=params, urgent=cl.urgent,
                  after_prev=cl.after_prev, text=" ".join(cl.words), clarify=clarify)
    return cmd, was_implicit


def _agents_or_all(cl, prev_agents, used_agents):
    if cl.agents or cl.dative:
        return list(cl.agents or cl.dative)
    if cl.rest:
        return [p for p in ALL if p not in used_agents] or list(ALL)
    return list(prev_agents or ALL)
