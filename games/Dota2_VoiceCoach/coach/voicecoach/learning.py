"""Обучение агентов Claude (решение Д20): память героя между матчами — уроки, числа матчей, учёба по ходу матча.

Слова автора 11.10.2026: «суть была в чем. ты должен быть в игре. отыгрывать агентами. так не правельно. нужно было
тебя научить»; «Стандартный режим обучения. Возьми лучший. можеш совместить несколько. В начале пока они еще не
научились делать базовые действия обучения очень много.»

Веса модели не меняются — учится её препромпт: уроки героя в coach/memory/<герой>.json на ПК хоста (обновление игры
пишет только файлы выпуска и эту папку не трогает). Откуда урок:
  тренер — «запомни …» в чате, на пульте или в поле приказа: дословно; агент его не оценивает и не убирает;
  смерть — после «ты погиб» агент пишет урок (поле lesson решения) по фактам смерти от игры;
  учёба  — учебная пауза на стадии линий: агент видит числа своих базовых действий за отрезок и пишет урок;
  разбор — после матча агент по числам матча отмечает уроки, которые помогли (+1) и не помогли (−1), и добавляет
           новые; урок с весом ниже нуля уходит, при переполнении уходят самые слабые и старые.
Правда — от кода (правило репозитория): числа (добивания, вражеские крипы, умершие рядом, денаи, смерти, уровень,
простой рук) считает игра; агент по ним пишет уроки, но сам себя не оценивает.
"""
from __future__ import annotations

import json
import os
import re
import threading
import time
from pathlib import Path

MAX_LEARNED = 12          # уроков агента у героя (смерть, учёба, разбор)
MAX_COACH = 8             # уроков тренера у героя
MAX_TEXT = 160            # знаков в уроке
HISTORY_KEEP = 40         # матчей в истории героя
EARLY_MATCHES = 5         # первые матчи героя — учёба чаще (слова автора: «в начале … обучения очень много»)
TRAIN_EVERY_EARLY = 120   # с игры между учебными паузами в первые матчи
TRAIN_EVERY = 240         # и потом
TRAIN_UNTIL = 600         # учебные паузы — на стадии линий, до 10:00
SEEN_R = 900              # крип, умерший ближе к герою, — «умер рядом» (считает игра)

COACH, DEATH, TRAIN, REVIEW = "тренер", "смерть", "учёба", "разбор"
SOURCES = (COACH, DEATH, TRAIN, REVIEW)

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


class Memory:
    """Память героев на диске. root=None — выключена (тесты, сухой прогон): уроки живут до конца процесса."""

    def __init__(self, root: str | Path | None, now=time.time):
        self.root = Path(root) if root else None
        self.now = now
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
        data["lessons"] = [x for x in data.get("lessons") or [] if isinstance(x, dict) and clean(x.get("text"))]
        data["history"] = [x for x in data.get("history") or [] if isinstance(x, dict)]
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
        """Уроки героя по порядку показа: сначала тренера, потом по весу и свежести."""
        with self.lock:
            items = [dict(x) for x in self._load(hero)["lessons"]]
        coach = [x for x in items if x.get("src") == COACH]
        own = sorted((x for x in items if x.get("src") != COACH),
                     key=lambda x: (-int(x.get("w") or 0), -int(x.get("match") or 0), -float(x.get("t") or 0)))
        return coach + own

    def matches(self, hero) -> int:
        with self.lock:
            return self._load(hero)["matches"]

    def history(self, hero) -> list[dict]:
        with self.lock:
            return [dict(x) for x in self._load(hero)["history"]]

    def train_every(self, hero) -> float:
        return TRAIN_EVERY_EARLY if self.matches(hero) < EARLY_MATCHES else TRAIN_EVERY

    def prompt_block(self, hero) -> str:
        """Раздел системного промпта: уроки из прошлых матчей и от тренера (номера — для разбора)."""
        rows = self.lessons(hero)
        if not rows:
            return ("ТВОЯ ПАМЯТЬ\nУроков пока нет: это один из первых твоих матчей. Учись — в поле lesson пиши урок "
                    "себе, когда погиб, на учебной паузе и когда тренер говорит «запомни».")
        lines = ["ТВОЯ ПАМЯТЬ — уроки из прошлых матчей и от тренера (следуй им; урок тренера важнее твоих):"]
        for i, x in enumerate(rows, 1):
            tag = x.get("src") or "?"
            w = int(x.get("w") or 0)
            if x.get("src") != COACH and w:
                tag += f", вес {w:+d}"
            lines.append(f"{i}. [{tag}] {clean(x.get('text'))}")
        return "\n".join(lines)

    # --- запись ---

    def add(self, hero, text, src: str, match: int | None = None, clock=None) -> str | None:
        """Новый урок. → «новый», «повтор» (такой уже есть — у агента вес +1) или None (пусто, не тот источник)."""
        s = clean(text)
        if not s or src not in SOURCES:
            return None
        with self.lock:
            data = self._load(hero)
            items = data["lessons"]
            for x in items:
                if similar(x.get("text", ""), s) and (x.get("src") == COACH) == (src == COACH):
                    if src != COACH:
                        x["w"] = min(5, int(x.get("w") or 0) + 1)
                    x["t"] = self.now()
                    self._save(hero, data)
                    return "повтор"
            items.append({"text": s, "src": src, "w": 0, "match": data["matches"] + 1 if match is None else match,
                          "clock": None if clock is None else int(float(clock)), "t": self.now()})
            self._trim(data)
            self._save(hero, data)
            return "новый"

    def _trim(self, data: dict) -> None:
        coach = [x for x in data["lessons"] if x.get("src") == COACH]
        own = [x for x in data["lessons"] if x.get("src") != COACH]
        coach = coach[-MAX_COACH:]                                  # у тренера — последние
        own = [x for x in own if int(x.get("w") or 0) >= 0]         # не помогавшие — вон
        if len(own) > MAX_LEARNED:                                  # слабые и старые — вон
            own.sort(key=lambda x: (int(x.get("w") or 0), float(x.get("t") or 0)))
            own = own[len(own) - MAX_LEARNED:]
        data["lessons"] = coach + own

    def vote(self, hero, shown: list[dict], up=(), down=()) -> tuple[int, int]:
        """Итог разбора: номера (1…) в списке shown, который видел агент. Уроки тренера не трогаются.
        → (сколько отмечено «за», сколько «против»)."""
        def pick(nums):
            out = []
            for n in nums or ():
                try:
                    i = int(n) - 1
                except (TypeError, ValueError):
                    continue
                if 0 <= i < len(shown) and shown[i].get("src") != COACH and shown[i] not in out:
                    out.append(shown[i])
            return out
        ups, downs = pick(up), pick(down)
        downs = [x for x in downs if x not in ups]                  # и «за», и «против» — не считать
        with self.lock:
            data = self._load(hero)
            for x in data["lessons"]:
                for want, delta in ((ups, 1), (downs, -1)):
                    if any(x.get("text") == y.get("text") and x.get("src") == y.get("src") for y in want):
                        x["w"] = max(-5, min(5, int(x.get("w") or 0) + delta))
            self._trim(data)
            self._save(hero, data)
        return len(ups), len(downs)

    def record(self, hero, row: dict) -> int:
        """Матч сыгран: числа матча — в историю героя. → номер матча героя."""
        with self.lock:
            data = self._load(hero)
            data["matches"] += 1
            data["history"].append({**row, "match": data["matches"], "t": self.now()})
            data["history"] = data["history"][-HISTORY_KEEP:]
            self._save(hero, data)
            return data["matches"]


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
    отрезки для учебных пауз."""

    def __init__(self):
        self.prev: dict | None = None
        self.last: dict | None = None
        self.at5: dict | None = None
        self.at10: dict | None = None
        self.deaths: list[dict] = []
        self.win_start: dict | None = None       # срез в начале отрезка учёбы
        self.win_clock: float | None = None
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

    def train_due(self, clock: float, every: float) -> bool:
        return (clock < TRAIN_UNTIL and self.win_clock is not None and clock - self.win_clock >= every
                and self.last is not None)

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
        """Числа матча для истории героя и разбора."""
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
