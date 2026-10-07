"""Короткий текстовый формат команд тренера (решение автора 07.10.2026: голос пока отложен).

Строгий разбор без догадок: каждое слово должно быть из словаря формата, иначе — ошибка с
подсказкой, и ни одна команда строки не уходит агентам. Свободную фразу разбирает parser.py;
сервер превращает её разбор в подсказку в коротком формате (to_short), тренер подтверждает.

    1 фарм лес. 23 ганг мид. 45 вард руна
    все рош            все-1 пуш бот т2         3 ульт марс !
    4 сейв 1           5 купи сентри            потом все назад

Формат целиком — docs/COMMANDS.md, «Короткий формат». Тот же разбор на Lua для чата игры —
game/shared/coach_text.lua (словарь берёт из game/shared/coach_text_data.lua, который пишет
lua_data() отсюда); общие примеры для обоих — coach/data/text_cases.json.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field

from . import lexicon as L
from .parser import Agent, MatchContext
from .protocol import ACTIONS, Command, validate

FORMAT_VERSION = 1

# --- словарь формата -----------------------------------------------------------
ADDR_ALL = {"все", "всем", "0"}
ADDR_ROLE = {
    "керри": [1], "мидер": [2], "оффлейнер": [3], "офлейнер": [3], "хардер": [3],
    "четверка": [4], "пятерка": [5], "саппы": [4, 5], "сапы": [4, 5], "саппорты": [4, 5],
    "коры": [1, 2, 3],
}
ACTION_WORDS = {
    "фарм": "farm", "фарми": "farm", "ф": "farm",
    "пуш": "push", "пушь": "push", "п": "push",
    "деф": "defend", "дефай": "defend", "д": "defend",
    "ганг": "gank", "ганк": "gank", "г": "gank",
    "сбор": "group", "собраться": "group",
    "рош": "roshan", "рошан": "roshan",
    "торм": "tormentor", "торментор": "tormentor",
    "смок": "smoke",
    "назад": "retreat", "отход": "retreat",
    "фокус": "focus", "бей": "focus",
    "драка": "engage", "заход": "engage", "файт": "engage",
    "жди": "hold", "стой": "hold",
    "сплит": "split",
    "вард": "ward",
    "стак": "stack",
    "купи": "buy",
    "юз": "use_item",
    "бб": "buyback", "байбэк": "buyback", "байбек": "buyback", "выкуп": "buyback",
    "ульт": "use_ult",
    "держи": "save_ult",
    "сейв": "save", "спаси": "save",
    "за": "follow",
    "тп": "tp",
    "иди": "move",
    "сам": "free", "сами": "free", "свобода": "free",
    "отмена": "cancel", "отбой": "cancel",
    "доклад": "report", "?": "report",
}
# каноническое слово действия — для подсказок (to_short) и шпаргалки
ACTION_CANON = {
    "farm": "фарм", "push": "пуш", "defend": "деф", "gank": "ганг", "group": "сбор", "roshan": "рош",
    "tormentor": "торм", "smoke": "смок", "retreat": "назад", "focus": "фокус", "engage": "драка",
    "hold": "жди", "split": "сплит", "ward": "вард", "stack": "стак", "buy": "купи", "use_item": "юз",
    "buyback": "бб", "use_ult": "ульт", "save_ult": "держи", "save": "сейв", "follow": "за", "tp": "тп",
    "move": "иди", "free": "сам", "cancel": "отмена", "report": "доклад",
}
# где: фраза → (вид, значение); вид: lane | rel | area | place
WHERE_WORDS = {
    "топ": ("lane", "top"), "мид": ("lane", "mid"), "бот": ("lane", "bot"),
    "сейф": ("rel", "safe"), "хард": ("rel", "off"),
    "лес": ("area", "jungle_own"), "их лес": ("area", "jungle_enemy"), "лес врага": ("area", "jungle_enemy"),
    "вражеский лес": ("area", "jungle_enemy"), "древние": ("area", "ancients"), "линия": ("area", "lane"),
    "база": ("place", "base"), "руна": ("place", "rune"), "рош": ("place", "roshan"),
    "торм": ("place", "tormentor"), "аутпост": ("place", "outpost"), "лотос": ("place", "lotus"),
}
WHERE_CANON = {
    ("lane", "top"): "топ", ("lane", "mid"): "мид", ("lane", "bot"): "бот",
    ("area", "jungle_own"): "лес", ("area", "jungle_enemy"): "их лес", ("area", "ancients"): "древние",
    ("area", "lane"): "линия",
    ("place", "base"): "база", ("place", "rune"): "руна", ("place", "roshan"): "рош",
    ("place", "tormentor"): "торм", ("place", "outpost"): "аутпост", ("place", "lotus"): "лотос",
    ("place", "jungle_own"): "лес", ("place", "jungle_enemy"): "их лес", ("place", "ancients"): "древние",
    ("place", "top"): "топ", ("place", "mid"): "мид", ("place", "bot"): "бот",
}
TIER_WORDS = {"т1": 1, "т2": 2, "т3": 3, "т4": 4}
ENEMY_POS_WORDS = {f"в{i}": i for i in range(1, 6)}
URGENT_WORDS = {"!", "срочно"}
AFTER_WORDS = {"потом"}
NEG_WORD = "не"
SENTRY_WORD = "сентри"
GANK_WORD = "ганг"
FILLER_AFTER = {"save_ult": {"ульт", "ульту"}}       # «держи ульт» — «ульт» здесь не действие

# порядок проверки параметров (сообщение об ошибке одинаково в Python и Lua)
PARAM_ORDER = {"then": 1, "tier": 2, "enemy_pos": 3, "kind": 4, "item": 5, "ally": 6, "enemy": 7,
               "area": 8, "lane": 9, "place": 10, "what": 11}

# какие параметры у действия и куда кладётся «где»
PERSONAL_NEEDS = {"buy": "item", "use_item": "item", "save": "ally", "follow": "ally", "tp": "where",
                  "move": "where", "focus": "target"}
NEEDS_TEXT = {"item": "что купить или применить?", "ally": "кого (номер или имя)?",
              "where": "куда (линия или место)?", "target": "какую цель (герой или в1…в5)?"}


def _items() -> dict[str, str]:
    items = {}
    for word, iid in L.ITEM_PHRASES.items():
        items[word.replace("ё", "е")] = iid
    return items


def _heroes() -> tuple[dict[str, str], dict[str, str]]:
    """Псевдоним → герой; герой → короткое имя для подсказок."""
    alias, canon = {}, {}
    for hid, h in L.load_heroes().items():
        names = [a.lower().replace("ё", "е") for a in h.get("aliases", [])] + [h["ru"].lower().replace("ё", "е")]
        for a in names:
            alias.setdefault(a, hid)
    for hid, h in L.load_heroes().items():
        # для подсказок: русское имя одним словом, иначе самый короткий русский псевдоним от 3 букв;
        # годится только то, что разбирается обратно в этого же героя
        ru_name = h["ru"].lower().replace("ё", "е")
        names = [a.lower().replace("ё", "е") for a in h.get("aliases", [])] + [ru_name]
        ok = [a for a in names if alias.get(a) == hid and re.fullmatch(r"[а-я]+", a)]
        if ru_name in ok and len(ru_name) <= 10:
            canon[hid] = ru_name
        elif ok:
            longer = [a for a in ok if len(a) >= 3] or ok
            canon[hid] = min(longer, key=lambda s: (len(s), s))
        else:
            canon[hid] = next((a for a in names if alias.get(a) == hid), hid.replace("npc_dota_hero_", ""))
    return alias, canon


ITEMS = _items()
HERO_ALIAS, HERO_CANON = _heroes()
ITEM_CANON = {}
for _w, _iid in sorted(ITEMS.items(), key=lambda kv: (len(kv[0]), kv[0])):
    ITEM_CANON.setdefault(_iid, _w)
ITEM_CANON["item_ward_observer"] = "вард"
ITEM_CANON["item_ward_sentry"] = "сентри"
ITEM_CANON["item_tpscroll"] = "тп"

# слова из нескольких слов — для жадного поиска
MULTI = sorted([w for w in list(WHERE_WORDS) + list(ITEMS) + list(HERO_ALIAS) if " " in w],
               key=lambda s: -len(s.split()))


# --- разбор --------------------------------------------------------------------
@dataclass
class ShortResult:
    text: str
    commands: list = field(default_factory=list)
    errors: list = field(default_factory=list)       # непусто — ничего не отправлять

    @property
    def ok(self) -> bool:
        return not self.errors and bool(self.commands)


def normalize_short(text: str) -> list[list[str]]:
    """Строка → команды → слова. Разделители команд: «.», «;», «,» и перевод строки;
    запятая между цифрами («1,2») — список позиций, не разделитель."""
    t = text.lower().replace("ё", "е")
    t = re.sub(r"\b[тt]\s*-?\s*([1-4])\b", r"т\1", t)
    t = t.replace("!", " ! ").replace("?", " ? ")
    t = re.sub(r"(?<=\d)\s*,\s*(?=\d)", "§", t)
    parts = re.split(r"[.;,\n]+", t)
    out = []
    for p in parts:
        p = re.sub(r"[«»\"()\[\]{}:]", " ", p).replace("§", ",")
        words = p.split()
        if words:
            out.append(words)
    return out


class _Ctx:
    def __init__(self, ctx: MatchContext):
        self.ctx = ctx
        self.names = {}
        for a in ctx.agents:
            for n in list(a.aliases) + ([a.name] if a.name else []):
                n = n.lower().replace("ё", "е").strip()
                if n:
                    self.names[n] = a.pos
        self.own_heroes = {a.hero: a.pos for a in ctx.agents if a.hero}
        self.enemies = set(ctx.enemy_heroes or [])

    def agent_by_word(self, w: str):
        if w in self.names:
            return self.names[w]
        for n, pos in self.names.items():          # падеж: «пете», «петю», «петей»
            stem = n[:-1] if n[-1] in "аяоеиыуюь" and len(n) > 3 else n
            if w.startswith(stem) and len(w) - len(stem) <= 2 and len(stem) >= 3:
                return pos
        return None


def _join_multi(words: list[str]) -> list[str]:
    out, i = [], 0
    while i < len(words):
        for m in MULTI:
            k = len(m.split())
            if words[i:i + k] == m.split():
                out.append(m)
                i += k
                break
        else:
            out.append(words[i])
            i += 1
    return out


def _addressee(words, c: _Ctx):
    """Начало команды → (позиции | None, сколько слов съедено, ошибка | None)."""
    if not words:
        return None, 0, None
    w = words[0]
    m = re.fullmatch(r"(все|0)-([1-5,]+)", w)
    if m:
        ex = {int(ch) for ch in m.group(2) if ch.isdigit()}
        return [p for p in range(1, 6) if p not in ex], 1, None
    if w in ADDR_ALL:
        if len(words) >= 3 and words[1] == "кроме":
            ex, n = _positions(words[2:], c)
            if not ex:
                return None, 2, f"кроме кого? после «кроме» — номер или имя"
            return [p for p in range(1, 6) if p not in ex], 2 + n, None
        return [1, 2, 3, 4, 5], 1, None
    pos, n = _positions(words, c)
    if pos:
        return pos, n, None
    return None, 0, None


def _positions(words, c: _Ctx):
    """«12», «1,2», «1 2», «петя», «керри», «петя 3» → (позиции, сколько слов)."""
    out, n = [], 0
    for w in words:
        if re.fullmatch(r"[1-5](?:,?[1-5])*", w):
            out += [int(ch) for ch in w if ch.isdigit()]
        elif w in ADDR_ROLE:
            out += ADDR_ROLE[w]
        elif w not in ACTION_WORDS and w != NEG_WORD and c.agent_by_word(w) is not None:
            out.append(c.agent_by_word(w))
        elif w in HERO_ALIAS and HERO_ALIAS[w] in c.own_heroes and w not in ACTION_WORDS:
            out.append(c.own_heroes[HERO_ALIAS[w]])        # свой герой как обращение: «джагг фарм лес»
        else:
            break
        n += 1
    seen = []
    for p in out:
        if p not in seen:
            seen.append(p)
    return sorted(seen), n


def _rel_to_abs(rel: str, team: str) -> str:
    if team == "dire":
        return "top" if rel == "safe" else "bot"
    return "bot" if rel == "safe" else "top"


def parse_short(text: str, ctx: MatchContext | None = None) -> ShortResult:
    ctx = ctx or MatchContext()
    c = _Ctx(ctx)
    res = ShortResult(text=text)
    parts, pending = [], []
    for words in normalize_short(text):
        agents, n, _ = _addressee(words, c)
        if agents is not None and n == len(words):       # «дима, фарм лес»: обращение отдельно
            pending = words
            continue
        parts.append(pending + words)
        pending = []
    if pending:
        parts.append(pending)
    for words in parts:
        cmd, err = _one(words, c)
        if err:
            res.errors.append(f"«{' '.join(words)}»: {err}")
        elif cmd:
            res.commands.append(cmd)
    if res.errors:
        res.commands = []
    return res


def _one(words, c: _Ctx):
    words = _join_multi(words)
    urgent = after = False
    if words and words[0] in AFTER_WORDS:
        after, words = True, words[1:]
    while words and words[-1] in URGENT_WORDS:
        urgent, words = True, words[:-1]
    if any(w in URGENT_WORDS for w in words):
        urgent, words = True, [w for w in words if w not in URGENT_WORDS]
    agents, n, err = _addressee(words, c)
    if err:
        return None, err
    rest = words[n:]
    neg = False
    if rest and rest[0] == NEG_WORD:
        neg, rest = True, rest[1:]
    if not rest:
        return None, "нет действия (фарм, пуш, рош, назад, …)"
    action = ACTION_WORDS.get(rest[0])
    if action is None:
        hint = ""
        if rest[0] in WHERE_WORDS and len(rest) > 1 and rest[1] in ACTION_WORDS:
            hint = f" — место пишется после действия: «{rest[1]} {rest[0]}»"
        elif rest[0] in WHERE_WORDS:
            hint = f" — место пишется после действия, например «{ACTION_CANON['move']} {rest[0]}»"
        return None, f"не понял «{rest[0]}» на месте действия{hint}"
    spec = ACTIONS[action]
    params: dict = {}
    where = []
    for w in rest[1:]:
        if w in FILLER_AFTER.get(action, ()):
            continue
        if action == "smoke" and w == GANK_WORD:
            params["then"] = "gank"
        elif w in WHERE_WORDS:
            where.append(WHERE_WORDS[w])
        elif w in TIER_WORDS:
            params["tier"] = TIER_WORDS[w]
        elif w in ENEMY_POS_WORDS:
            params["enemy_pos"] = ENEMY_POS_WORDS[w]
        elif w == SENTRY_WORD and action == "ward":
            params["kind"] = "sentry"
        elif action in ("buy", "use_item") and w in ITEMS:
            params["item"] = ITEMS[w]
        elif action in ("save", "follow") and re.fullmatch(r"[1-5]", w):
            params["ally"] = int(w)
        elif action in ("save", "follow") and c.agent_by_word(w) is not None:
            params["ally"] = c.agent_by_word(w)
        elif w in HERO_ALIAS:
            hero = HERO_ALIAS[w]
            if action in ("save", "follow"):
                if hero not in c.own_heroes:
                    return None, f"«{w}» — не наш герой"
                params["ally"] = c.own_heroes[hero]
            elif hero in c.own_heroes and hero not in c.enemies:
                return None, f"«{w}» — наш герой, а не цель"
            else:
                params["enemy"] = hero
        else:
            return None, f"не понял «{w}»"
    # «где» → параметры по действию
    for kind, val in where:
        if kind == "rel":
            kind, val = "lane", _rel_to_abs(val, c.ctx.team)
        if action == "farm":
            if kind == "lane":
                params["area"], params["lane"] = "lane", val
            elif kind == "area":
                params["area"] = val
            else:
                return None, f"фармить можно линию, лес, их лес или древних"
        elif kind == "lane":
            params["lane"] = val
        elif kind == "area":
            if val == "lane":
                return None, "«линия» — только для фарма"
            if "place" not in spec.params:
                return None, f"«{WHERE_CANON[(kind, val)]}» не подходит к «{ACTION_CANON[action]}»"
            params["place"] = val
        else:
            params["place"] = val
    if action == "farm":
        params.setdefault("area", "auto")
    if action in ("push", "defend", "split") and "lane" not in params and "place" not in params:
        params["lane"] = "auto"
    if action == "stack" and params.get("place") not in (None, "ancients"):
        return None, "стакать — только лагеря или древних"
    # запрет «не X»
    if neg:
        params = {"what": action}
        action, spec = "hold", ACTIONS["hold"]
    # адресат
    if agents is None:
        if spec.scope == "team":
            agents = [1, 2, 3, 4, 5]
        else:
            return None, "кому? начните с номера (1–5), имени или «все»"
    need = PERSONAL_NEEDS.get(action)
    if need == "item" and "item" not in params:
        return None, NEEDS_TEXT[need]
    if need == "ally" and "ally" not in params:
        return None, NEEDS_TEXT[need]
    if need == "where" and not ({"lane", "place"} & set(params)):
        return None, NEEDS_TEXT[need]
    if need == "target" and not ({"enemy", "enemy_pos"} & set(params)):
        return None, NEEDS_TEXT[need]
    for k in sorted(params, key=lambda k: PARAM_ORDER.get(k, 99)):     # тот же порядок, что в Lua
        if k not in spec.params:
            return None, f"«{_param_word(k, params[k])}» не подходит к «{ACTION_CANON.get(action, action)}»"
    cmd = Command(action=action, agents=agents, params=params, urgent=urgent, after_prev=after,
                  text=" ".join(words), confidence=1.0)
    problems = validate(cmd)
    if problems:
        return None, "; ".join(problems)
    return cmd, None


def _param_word(k, v):
    """Параметр → слово формата для сообщения об ошибке (то же делает Lua-версия)."""
    if k == "tier":
        return f"т{v}"
    if k == "enemy":
        return HERO_CANON.get(v, v)
    if k == "item":
        return ITEM_CANON.get(v, v)
    if k in ("lane", "place", "area"):
        return WHERE_CANON.get((k, v), str(v))
    return str(v)


# --- обратно: команда → короткий формат (подсказки) ----------------------------
def to_short(cmd: Command, ctx: MatchContext | None = None) -> str:
    """Команда протокола → строка короткого формата; parse_short(to_short(c)) даёт ту же команду."""
    ag = sorted(cmd.agents)
    if ag == [1, 2, 3, 4, 5]:
        addr = "все"
    elif len(ag) >= 3 and len(ag) < 5:
        rest = [p for p in range(1, 6) if p not in ag]
        addr = "все-" + "".join(map(str, rest)) if len(rest) <= 2 else "".join(map(str, ag))
    else:
        addr = "".join(map(str, ag))
    p = cmd.params
    if cmd.action == "hold" and p.get("what") in ACTION_CANON:
        words = [addr, "не", ACTION_CANON[p["what"]]]
    else:
        words = [addr, ACTION_CANON.get(cmd.action, cmd.action)]
        if cmd.action == "farm":
            if p.get("area") == "lane" and p.get("lane"):
                words.append(WHERE_CANON[("lane", p["lane"])])
            elif p.get("area") and p["area"] != "auto":
                words.append(WHERE_CANON[("area", p["area"])])
        else:
            if p.get("lane") and p["lane"] != "auto":
                words.append(WHERE_CANON[("lane", p["lane"])])
            if p.get("place"):
                words.append(WHERE_CANON[("place", p["place"])])
        if p.get("tier"):
            words.append(f"т{p['tier']}")
        if p.get("then") == "gank":
            words.append(GANK_WORD)
        if p.get("enemy"):
            words.append(HERO_CANON.get(p["enemy"], p["enemy"]))
        if p.get("enemy_pos"):
            words.append(f"в{p['enemy_pos']}")
        if p.get("ally"):
            words.append(str(p["ally"]))
        if p.get("item"):
            words.append(ITEM_CANON.get(p["item"], p["item"]))
        if p.get("kind") == "sentry":
            words.append(SENTRY_WORD)
    s = " ".join(words)
    if cmd.after_prev:
        s = "потом " + s
    if cmd.urgent:
        s += " !"
    return s


def suggest(commands: list[Command], ctx: MatchContext | None = None) -> str:
    """Разбор свободной фразы → подсказка в коротком формате (только команды без переспроса)."""
    good = [c for c in commands if not c.clarify and c.agents]
    return ". ".join(to_short(c, ctx) for c in good)


# --- словарь для Lua --------------------------------------------------------------
def _lua(v, ind="  "):
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (int, float)):
        return repr(v)
    if isinstance(v, str):
        return json.dumps(v, ensure_ascii=False)
    if isinstance(v, (list, tuple)):
        return "{ " + ", ".join(_lua(x, ind) for x in v) + " }"
    if isinstance(v, dict):
        items = [f"{ind}[{_lua(k)}] = {_lua(val, ind + '  ')}," for k, val in sorted(v.items(), key=lambda kv: str(kv[0]))]
        return "{\n" + "\n".join(items) + "\n" + ind[:-2] + "}"
    raise TypeError(type(v))


def lua_data() -> str:
    """Словарь формата для game/shared/coach_text_data.lua (одна правда для Python и Lua)."""
    actions = {name: {"scope": s.scope, "params": list(s.params)} for name, s in ACTIONS.items()}
    data = {
        "version": FORMAT_VERSION, "addr_all": sorted(ADDR_ALL), "addr_role": ADDR_ROLE,
        "action_words": ACTION_WORDS, "action_canon": ACTION_CANON,
        "where_words": {k: list(v) for k, v in WHERE_WORDS.items()},
        "tier_words": TIER_WORDS, "enemy_pos_words": ENEMY_POS_WORDS,
        "urgent_words": sorted(URGENT_WORDS), "after_words": sorted(AFTER_WORDS),
        "items": ITEMS, "heroes": HERO_ALIAS, "actions": actions,
        "personal_needs": PERSONAL_NEEDS, "needs_text": NEEDS_TEXT,
        "multi": MULTI,
        "where_canon": {f"{k}/{v}": w for (k, v), w in WHERE_CANON.items()},
        "hero_canon": HERO_CANON, "item_canon": ITEM_CANON,
    }
    body = ",\n".join(f"  {k} = {_lua(v, '    ')}" for k, v in data.items())
    return ("-- Словарь короткого формата команд. ФАЙЛ СОБРАН АВТОМАТИЧЕСКИ:\n"
            "--   cd coach && python -m voicecoach.textcmd --lua ../game/shared/coach_text_data.lua\n"
            "-- Источник — coach/voicecoach/textcmd.py (и lexicon.py, data/heroes.json). Руками не править.\n"
            "return {\n" + body + "\n}\n")


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description="Короткий формат команд: разбор строки или словарь для Lua")
    ap.add_argument("text", nargs="?")
    ap.add_argument("--lua", help="записать словарь для Lua в этот файл")
    a = ap.parse_args()
    if a.lua:
        with open(a.lua, "w", encoding="utf-8") as f:
            f.write(lua_data())
        print("записано:", a.lua)
    if a.text:
        r = parse_short(a.text)
        print(json.dumps({"commands": [c.to_json() for c in r.commands], "errors": r.errors}, ensure_ascii=False,
                         indent=1))
