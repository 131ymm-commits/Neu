"""Обучение агентов Claude (решение Д20): память героя между матчами — уроки, их проверка числами, учёба по ходу матча.

Слова автора 11.10.2026: «суть была в чем. ты должен быть в игре. отыгрывать агентами. так не правельно. нужно было
тебя научить»; «Стандартный режим обучения. Возьми лучший. можеш совместить несколько. В начале пока они еще не
научились делать базовые действия обучения очень много.»

Веса модели не меняются — учится её препромпт (research/06_agent_learning.md: Reflexion — урок словами после неудачи,
ExpeL и ACE — сведение уроков со счётом, Voyager — учебный план; всё работает, только когда успех задаёт внешний
сигнал). Память героя — coach/memory/<герой>.json на ПК хоста: обновление игры её не трогает.

Слои памяти в промпте: слова тренера (дословно, агент их не правит) → проверенные уроки героя → уроки на испытании,
включённые в этот матч → рабочая память матча (уроки после смертей и учебных пауз — в сообщении агенту).

Урок агента — гипотеза: у него есть мера (добивания, смерти, простой рук, уровень к 10:00) и опора (событие матча).
Проверяет его код, а не агент (без внешней правды самооценка закрепляет ошибки, research/06): каждый матч урок на
испытании включается в промпт случайно, в половине матчей; после MIN_ON матчей с уроком и MIN_OFF без него код
сравнивает меру. Лучше, и смерти с добиваниями не хуже, — «проверен», хуже — уходит; не решилось за MAX_TRIALS матчей —
уходит. Числа считает игра (правда от кода).
"""
from __future__ import annotations

import json
import os
import random
import re
import threading
import time
from pathlib import Path

MAX_TRIAL = 6             # уроков на испытании у героя
MAX_PROVEN = 8            # проверенных уроков у героя
MAX_COACH = 8             # уроков тренера у героя
MAX_TEXT = 160            # знаков в уроке
HISTORY_KEEP = 40         # матчей в истории героя
NEW_PER_MATCH = 2         # новых уроков на испытание за матч у героя (остальные — только в рабочей памяти матча)
P_ON = 0.5                # с этой вероятностью урок на испытании включается в матч
MIN_ON, MIN_OFF = 2, 2    # матчей с уроком и без него, чтобы судить
MAX_TRIALS = 8            # не решилось за столько матчей — урок уходит
EARLY_MATCHES = 5         # первые матчи героя — учебных пауз больше (слова автора: «в начале … обучения очень много»)
TRAIN_EVERY_EARLY = 120   # с игры между плановыми паузами в первые матчи
TRAIN_UNTIL = 600         # учебные паузы — на стадии линий, до 10:00
ALARM_WINDOW = 60         # пауза по порогу: за последние столько секунд…
ALARM_MISSED = 3          # …пропущено добиваний не меньше этого,
ALARM_IDLE = 20           # …или руки стояли без дела не меньше стольких секунд
ALARM_GAP = 60            # пауз по порогу — не чаще раза в столько секунд

COACH, DEATH, TRAIN, REVIEW = "тренер", "смерть", "учёба", "разбор"
SOURCES = (COACH, DEATH, TRAIN, REVIEW)
TRIAL, PROVEN = "испытание", "проверен"
# мера урока: имя в строке матча и направление (больше лучше / меньше лучше); всё — к 10:00 (стадия линий)
METRICS = {"lh": ("добивания к 10:00", +1), "deaths": ("смерти к 10:00", -1), "idle": ("простой рук к 10:00, с", -1),
           "lvl": ("уровень к 10:00", +1)}

_SAFE = re.compile(r"[^a-z0-9_]+")
_WORD = re.compile(r"[a-zа-яё0-9]+", re.I)


def safe_name(hero) -> str:
    """Имя файла памяти героя: «npc_dota_hero_crystal_maiden» → «crystal_maiden»."""
    s = str(hero or "").strip().lower().replace("npc_dota_hero_", "")
    return _SAFE.sub("_", s).strip("_") or "hero"


def clean(text) -> str:
    """Урок одной строкой, без кавычек по краям, не длиннее MAX_TEXT."""
    s = " ".join(str(text or "").split()).strip(" \"'«»")
    return s[:MAX_TEXT].rstrip()


def _words(text: str) -> set:
    return {w.lower() for w in _WORD.findall(text) if len(w) > 2 or w.isdigit()}


def similar(a: str, b: str) -> bool:
    """Тот же урок: совпадает с точностью до регистра и знаков или слова (с числами) совпадают на 80 % и больше.
    «Добивай дальнего крипа первым» и «Денай дальнего крипа первым» — разные уроки, «отходи при 30%» и «при 50%» —
    тоже."""
    x, y = clean(a).lower(), clean(b).lower()
    if not x or not y:
        return False
    if x == y:
        return True
    wa, wb = _words(x), _words(y)
    if not wa or not wb:
        return False
    return len(wa & wb) / len(wa | wb) >= 0.8


def mmss(clock) -> str:
    try:
        c = int(float(clock or 0))
    except (TypeError, ValueError):
        c = 0
    sign = "-" if c < 0 else ""
    c = abs(c)
    return f"{sign}{c // 60}:{c % 60:02d}"


def metric_value(row: dict, metric: str):
    """Значение меры урока в строке матча (к 10:00); матч короче 10 минут — None."""
    key = {"lh": "lh10", "deaths": "d10", "idle": "idle10", "lvl": "lvl10"}.get(metric)
    v = row.get(key) if key else None
    return v if isinstance(v, (int, float)) else None


def _mean(xs):
    return sum(xs) / len(xs) if xs else None


class Memory:
    """Память героев на диске. root=None — выключена (тесты, сухой прогон): уроки живут до конца процесса."""

    def __init__(self, root: str | Path | None, now=time.time, rng=None):
        self.root = Path(root) if root else None
        self.now = now
        self.rng = rng or random.Random()
        self.lock = threading.Lock()
        self.cache: dict[str, dict] = {}

    # --- диск ---

    def path(self, hero) -> Path | None:
        return self.root / f"{safe_name(hero)}.json" if self.root else None

    def _load(self, hero) -> dict:
        key = safe_name(hero)
        if key in self.cache:
            return self.cache[key]
        data = None
        p = self.path(hero)
        if p is not None and p.is_file():
            try:
                data = json.loads(p.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                data = None                       # битый файл — начать заново, а не ронять сервер
        if not isinstance(data, dict):
            data = {}
        data.setdefault("hero", key)
        data["matches"] = int(data.get("matches") or 0)
        data["next_id"] = int(data.get("next_id") or 1)
        data["lessons"] = [x for x in data.get("lessons") or [] if isinstance(x, dict) and clean(x.get("text"))]
        data["history"] = [x for x in data.get("history") or [] if isinstance(x, dict)]
        data["removed"] = [x for x in data.get("removed") or [] if isinstance(x, dict)][-20:]
        self.cache[key] = data
        return data

    def _save(self, hero, data: dict) -> None:
        p = self.path(hero)
        if p is None:
            return
        try:
            p.parent.mkdir(parents=True, exist_ok=True)
            tmp = p.with_name(p.name + ".part")
            tmp.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
            os.replace(tmp, p)
        except OSError:
            pass                                  # память не записалась — игра идёт; в следующий раз запишется

    # --- чтение ---

    def lessons(self, hero) -> list[dict]:
        """Уроки героя: тренера, проверенные, на испытании (каждая группа — от новых к старым)."""
        with self.lock:
            items = [dict(x) for x in self._load(hero)["lessons"]]
        order = {COACH: 0, PROVEN: 1, TRIAL: 2}
        return sorted(items, key=lambda x: (order.get(x.get("status"), 3), -int(x.get("id") or 0)))

    def matches(self, hero) -> int:
        with self.lock:
            return self._load(hero)["matches"]

    def history(self, hero) -> list[dict]:
        with self.lock:
            return [dict(x) for x in self._load(hero)["history"]]

    def train_every(self, hero) -> float | None:
        """Плановые учебные паузы — только в первые матчи героя; дальше — по порогу (research/06: по событию лучше)."""
        return TRAIN_EVERY_EARLY if self.matches(hero) < EARLY_MATCHES else None

    def plan_match(self, hero) -> set:
        """Какие уроки включены в этот матч: тренера и проверенные — всегда, на испытании — случайно (P_ON)."""
        on = set()
        for x in self.lessons(hero):
            if x.get("status") in (COACH, PROVEN) or self.rng.random() < P_ON:
                on.add(int(x["id"]))
        return on

    def prompt_block(self, hero, enabled=None) -> str:
        """Раздел системного промпта: включённые в матч уроки по слоям."""
        rows = [x for x in self.lessons(hero) if enabled is None or int(x["id"]) in enabled]
        if not rows:
            return ("ТВОЯ ПАМЯТЬ\nУроков пока нет: это один из первых твоих матчей. Учись — в поле lesson пиши урок себе, "
                    "когда в сообщении «РАЗБОР СМЕРТИ» или «УЧЕБНАЯ ПАУЗА».")
        lines = ["ТВОЯ ПАМЯТЬ — уроки (следуй им; слова тренера важнее твоих уроков):"]
        names = {COACH: "тренер", PROVEN: "проверен матчами", TRIAL: "на испытании"}
        for x in rows:
            lines.append(f"- [{names.get(x.get('status'), '?')}] {clean(x.get('text'))}")
        return "\n".join(lines)

    # --- запись ---

    def add(self, hero, text, src: str, metric: str = "", ref: str = "", match: int | None = None) -> str | None:
        """Новый урок. Тренера — дословно, всегда; агента — только с мерой и опорой (урок без опоры не принимаем,
        research/06), на испытание. → «новый», «повтор» или None (не принят)."""
        s = clean(text)
        if not s or src not in SOURCES:
            return None
        coach = src == COACH
        if not coach and (metric not in METRICS or not clean(ref)):
            return None
        with self.lock:
            data = self._load(hero)
            items = data["lessons"]
            for x in items:
                if similar(x.get("text", ""), s) and (x.get("status") == COACH) == coach:
                    x["repeats"] = int(x.get("repeats") or 0) + 1     # повтор — не голос «за»: та же ошибка снова
                    x["t"] = self.now()
                    self._save(hero, data)
                    return "повтор"
            item = {"id": data["next_id"], "text": s, "src": src, "status": COACH if coach else TRIAL,
                    "match": data["matches"] + 1 if match is None else match, "t": self.now()}
            if not coach:
                item.update({"metric": metric, "ref": clean(ref)[:80], "trials": []})
            data["next_id"] += 1
            items.append(item)
            self._trim(data)
            self._save(hero, data)
            return "новый"

    def _trim(self, data: dict) -> None:
        groups = {COACH: [], PROVEN: [], TRIAL: []}
        for x in data["lessons"]:
            groups.setdefault(x.get("status"), []).append(x)
        for status, cap in ((COACH, MAX_COACH), (PROVEN, MAX_PROVEN), (TRIAL, MAX_TRIAL)):
            g = sorted(groups.get(status, []), key=lambda x: int(x.get("id") or 0))
            for x in g[:-cap] if len(g) > cap else []:
                data["removed"].append({**x, "why": "вытеснен новыми", "t_removed": self.now()})
            groups[status] = g[-cap:]
        data["lessons"] = groups[COACH] + groups[PROVEN] + groups[TRIAL]
        data["removed"] = data["removed"][-20:]

    def record(self, hero, row: dict, enabled=None) -> tuple[int, list[str]]:
        """Матч сыгран: строка матча — в историю; испытания уроков — по мере урока; суд по числам.
        → (номер матча героя, что решено словами)."""
        verdicts = []
        with self.lock:
            data = self._load(hero)
            data["matches"] += 1
            n = data["matches"]
            on = set(enabled or ())
            data["history"].append({**row, "match": n, "on": sorted(on), "t": self.now()})
            data["history"] = data["history"][-HISTORY_KEEP:]
            keep = []
            for x in data["lessons"]:
                if x.get("status") != TRIAL:
                    keep.append(x)
                    continue
                v = metric_value(row, x.get("metric"))
                if v is not None:
                    x.setdefault("trials", []).append({"match": n, "on": int(x["id"]) in on, "v": v,
                                                       "d": row.get("d10"), "lh": row.get("lh10")})
                verdict = self._judge(x)
                if verdict == PROVEN:
                    x["status"] = PROVEN
                    verdicts.append(f"проверен: «{x['text']}»")
                    keep.append(x)
                elif verdict:
                    data["removed"].append({**x, "why": verdict, "t_removed": self.now()})
                    verdicts.append(f"убран ({verdict}): «{x['text']}»")
                else:
                    keep.append(x)
            data["lessons"] = keep
            self._trim(data)
            self._save(hero, data)
        return n, verdicts

    @staticmethod
    def _judge(x: dict) -> str | None:
        """Суд над уроком на испытании: «проверен», причина ухода или None (ещё рано)."""
        trials = x.get("trials") or []
        on = [t for t in trials if t.get("on")]
        off = [t for t in trials if not t.get("on")]
        if len(on) < MIN_ON or len(off) < MIN_OFF:
            return "не решилось за " + str(MAX_TRIALS) + " матчей" if len(trials) >= MAX_TRIALS else None
        sign = METRICS.get(x.get("metric"), ("", +1))[1]
        better = sign * (_mean([t["v"] for t in on]) - _mean([t["v"] for t in off]))
        d_on, d_off = _mean([t["d"] for t in on if t.get("d") is not None]), _mean([t["d"] for t in off if t.get("d") is not None])
        lh_on, lh_off = (_mean([t["lh"] for t in on if t.get("lh") is not None]),
                         _mean([t["lh"] for t in off if t.get("lh") is not None]))
        no_worse = ((d_on is None or d_off is None or d_on <= d_off + 0.5)
                    and (lh_on is None or lh_off is None or lh_on >= lh_off - 2))
        if better > 0 and no_worse:
            return PROVEN
        if better < 0:
            return "с ним хуже"
        if len(trials) >= MAX_TRIALS:
            return "не решилось за " + str(MAX_TRIALS) + " матчей"
        return None


# --- числа матча героя по наблюдениям игры ---

def _stats(obs: dict) -> dict:
    st = obs.get("stats") or {}
    out = {}
    for k in ("lh", "dn", "k", "d", "a", "seen", "idle"):
        try:
            out[k] = int(st.get(k) or 0)
        except (TypeError, ValueError):
            out[k] = 0
    try:
        out["lvl"] = int(obs.get("lvl") or 0)
    except (TypeError, ValueError):
        out["lvl"] = 0
    return out


def _clock(obs) -> float:
    try:
        return float((obs or {}).get("clock") or 0)
    except (TypeError, ValueError, AttributeError):
        return 0.0


def _hp_pct(obs: dict | None) -> int:
    hp = (obs or {}).get("hp") or [0, 0]
    try:
        return int(round(100.0 * hp[0] / hp[1])) if len(hp) == 2 and hp[1] else 0
    except (TypeError, ValueError, ZeroDivisionError):
        return 0


class Tracker:
    """Числа одного героя за матч — из наблюдений игры (правда от кода): срезы к 5:00 и 10:00, смерти с фактами,
    отрезки для учебных пауз (плановых и по порогу)."""

    def __init__(self):
        self.prev: dict | None = None
        self.last: dict | None = None
        self.at5: dict | None = None
        self.at10: dict | None = None
        self.deaths: list[dict] = []
        self.win_start: dict | None = None       # срез в начале отрезка учёбы
        self.win_clock: float | None = None
        self.minute: list[dict] = []             # срезы за последнюю минуту — для паузы по порогу
        self.alarm_clock = -1e9
        self.max_clock = 0.0

    def update(self, obs: dict) -> None:
        if not isinstance(obs, dict):
            return
        clock = _clock(obs)
        self.max_clock = max(self.max_clock, clock)
        prev = self.prev
        if prev is not None and prev.get("alive", True) and not obs.get("alive", True):
            self.deaths.append(self._death(prev, obs))
        row = {**_stats(obs), "clock": int(clock)}
        if self.at5 is None and clock >= 300:
            self.at5 = row
        if self.at10 is None and clock >= 600:
            self.at10 = row
        if self.win_start is None and clock >= 0:
            self.win_start, self.win_clock = row, clock
        self.minute.append(row)
        while self.minute and clock - self.minute[0]["clock"] > ALARM_WINDOW:
            self.minute.pop(0)
        self.prev = self.last = obs

    @staticmethod
    def _death(before: dict, after: dict) -> dict:
        killer = ""
        for e in reversed(after.get("events") or []):
            m = re.search(r"тебя убил (\S+)", str(e))
            if m:
                killer = m.group(1)
                break
        near = before.get("near") or {}
        enemies = [f"{x.get('hero')} {x.get('d')}" for x in before.get("enemies") or [] if (x.get("d") or 1e9) <= 1500]
        return {"clock": int(_clock(after)), "where": before.get("where") or "?", "hp": _hp_pct(before),
                "killer": killer, "enemies": enemies, "tower": near.get("enemy_tower") or "",
                "doing": before.get("doing") or "", "lvl": int(before.get("lvl") or 0)}

    def death_text(self) -> str:
        """Факты последней смерти для промпта «ты погиб»."""
        if not self.deaths:
            return ""
        x = self.deaths[-1]
        parts = [f"{mmss(x['clock'])}", f"убил {x['killer'] or '?'}", f"где: {x['where']}",
                 f"здоровья за ~1 с до смерти {x['hp']}%"]
        parts.append("враги рядом: " + (", ".join(x["enemies"]) if x["enemies"] else "не видно"))
        if x["tower"]:
            parts.append(f"вражеская вышка рядом: {x['tower']}")
        if x["doing"]:
            parts.append(f"руки делали: {x['doing']}")
        return "; ".join(parts)

    def train_due(self, clock: float, every: float | None) -> bool:
        """Плановая пауза (первые матчи героя): прошло every секунд с начала отрезка, стадия линий."""
        return (every is not None and clock < TRAIN_UNTIL and self.win_clock is not None
                and clock - self.win_clock >= every and self.last is not None)

    def alarm(self, clock: float) -> str:
        """Пауза по порогу на стадии линий: за последнюю минуту пропущено ≥ ALARM_MISSED добиваний или руки стояли
        ≥ ALARM_IDLE с; не чаще ALARM_GAP. → почему или ""."""
        if clock >= TRAIN_UNTIL or clock - self.alarm_clock < ALARM_GAP or len(self.minute) < 2:
            return ""
        a, b = self.minute[0], self.minute[-1]
        if b["clock"] - a["clock"] < ALARM_WINDOW * 0.75:
            return ""
        missed = max(0, (b["seen"] - a["seen"]) - (b["lh"] - a["lh"]))
        idle = b["idle"] - a["idle"]
        why = ""
        if missed >= ALARM_MISSED:
            why = f"за минуту пропущено {missed} добиваний"
        elif idle >= ALARM_IDLE:
            why = f"за минуту руки стояли без дела {idle} с"
        if why:
            self.alarm_clock = clock
        return why

    def window(self) -> dict | None:
        """Отрезок учёбы: что изменилось с его начала; начинает новый. Нет данных — None."""
        if self.last is None or self.win_start is None:
            return None
        now = {**_stats(self.last), "clock": int(_clock(self.last))}
        a = self.win_start
        out = {k: now[k] - a.get(k, 0) for k in ("lh", "dn", "d", "seen", "idle")}
        out.update({"from": a["clock"], "to": now["clock"], "lvl": now["lvl"]})
        self.win_start, self.win_clock = now, float(now["clock"])
        return out

    def match_row(self) -> dict:
        """Числа матча для истории героя и суда над уроками."""
        last = {**_stats(self.last), "clock": int(_clock(self.last))} if self.last else {}
        out = {"end_clock": last.get("clock", 0), "lh": last.get("lh", 0), "dn": last.get("dn", 0),
               "k": last.get("k", 0), "d": last.get("d", 0), "a": last.get("a", 0), "lvl": last.get("lvl", 0),
               "seen": last.get("seen", 0), "idle": last.get("idle", 0)}
        for tag, snap in (("5", self.at5), ("10", self.at10)):
            if snap:
                for k in ("lh", "dn", "d", "lvl", "seen", "idle"):
                    out[k + tag] = snap.get(k, 0)
        out["deaths"] = [f"{mmss(x['clock'])} {x['killer'] or '?'}, {x['where']}" for x in self.deaths][-6:]
        return out


def window_text(w: dict) -> str:
    """Числа учебного отрезка словами (для промпта учёбы)."""
    missed = max(0, w["seen"] - w["lh"])
    return (f"с {mmss(w['from'])} по {mmss(w['to'])}: добил {w['lh']} из {w['seen']} вражеских крипов, умерших рядом "
            f"(пропустил {missed}); денаев {w['dn']}; смертей {w['d']}; руки стояли без дела {w['idle']} с; "
            f"уровень {w['lvl']}")


def row_text(r: dict) -> str:
    """Строка истории героя: к 10:00 и итог."""
    parts = []
    if "lh10" in r:
        parts.append(f"к 10:00: добивания {r['lh10']} (из {r.get('seen10', 0)} умерших рядом), денаи {r.get('dn10', 0)}, "
                     f"смерти {r.get('d10', 0)}, уровень {r.get('lvl10', 0)}, простой {r.get('idle10', 0)} с")
    parts.append(f"итог {mmss(r.get('end_clock', 0))}: {r.get('k', 0)}/{r.get('d', 0)}/{r.get('a', 0)}, добивания "
                 f"{r.get('lh', 0)}, уровень {r.get('lvl', 0)}" + (f", {r['result']}" if r.get("result") else ""))
    return "; ".join(parts)
