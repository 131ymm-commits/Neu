"""Отчёт игры для Claude — вместо снимков экрана (просьба автора 11.10.2026: «может ли лаунчер каждуй раз отправлять
тебе отчет? чтобы я не клацал принтскрины? зделай общюю систему»).

Лаунчер собирает один текстовый файл: окно лаунчера целиком, итоги агентов (вызовы Claude, ошибки, модель, примеры
решений), обучение героев (Д20), строки кастомки и ошибки из консоли Доты, вывод сборщика интерфейса при сбое. Во время
игры раз в минуту обновляется «DotaCoach_сейчас.txt», в конце — «DotaCoach_отчёт_<дата>.txt».

Куда: всегда — coach\\logs; если на ПК стоит «Google Диск для компьютера» — ещё и в папку DotaCoach на Google Диске:
оттуда Claude читает отчёт сам (Google Drive подключён к сессии Claude), человеку ничего делать не нужно. Без
Google Диска — в конце окно Проводника с файлом: перетащить его в чат.

Что скрыто: имя пользователя Windows в путях (и с удвоенными «\\», и с «/»), ключ пульта друга в ссылках, ключи API,
адрес туннеля. В живом отчёте нет ходов игры из консоли Доты — приказов соперника и реплик его агентов (Д16: хост их не
видит, рецензия 12); в итоговом, после игры, они есть.
"""
from __future__ import annotations

import json
import os
import re
import time
from pathlib import Path

LIVE_NAME = "DotaCoach_сейчас.txt"
FINAL_PREFIX = "DotaCoach_отчёт_"
MAX_SECTION = 60_000          # знаков в одном разделе (окно, консоль Доты): дальше — только конец
MAX_SAMPLES = 24              # решений агентов в примерах

_KEY_IN_URL = re.compile(r"(/c/)[A-Za-z0-9_\-]{12,}")
_KEY_IN_QUERY = re.compile(r"([?&](?:key|k)=)[A-Za-z0-9_\-]{12,}")
_API_KEY = re.compile(r"sk-ant-[A-Za-z0-9_\-]{8,}")
_TUNNEL = re.compile(r"(?:\b(?:https?|wss?)://)?[a-z0-9\-]+\.trycloudflare\.com[^\s\"'<>]*", re.I)
_USERS_SP = re.compile(r"([A-Za-z]:(?:\\\\|\\|/)+Users(?:\\\\|\\|/)+)[^\\/\"'\r\n<>]{1,64}?(?=[\\/])", re.I)
_USERS = re.compile(r"([A-Za-z]:(?:\\\\|\\|/)+Users(?:\\\\|\\|/)+)[^\\/\s\"'<>]+", re.I)
# ходы игры в консоли Доты (как GAME_MOVE лаунчера): реплики агентов и тренеров, приказы с пульта — в том числе
# соперника; окну хоста и живому отчёту не нужны
MOVE = re.compile(r"\[ТРЕНЕР\] (ход |\d \S*: |: |приказ с пульта)")


def _path_variants(path: str) -> list[str]:
    """Путь Windows с разделителями «\», удвоенными «\\» (repr, JSON) и «/» — длинные первыми; другой путь — как есть."""
    if not re.match(r"^[A-Za-z]:[\\/]", path):
        return [path]
    parts = [x for x in re.split(r"[\\/]+", path) if x]
    return sorted({sep.join(parts) for sep in ("\\", "\\\\", "/")}, key=len, reverse=True)


def scrub(text: str, home: str | None = None) -> str:
    """Скрыть личное: путь к папке пользователя, ключ пульта в ссылке, ключи API, адрес туннеля."""
    s = str(text or "")
    home = home if home is not None else os.environ.get("USERPROFILE") or str(Path.home())
    if home and len(home) > 3:
        for v in _path_variants(home):
            s = re.sub(re.escape(v), "%USERPROFILE%", s, flags=re.I)
    s = _USERS_SP.sub(r"\1<пользователь>", s)                 # имя с пробелом — до следующего разделителя
    s = _USERS.sub(r"\1<пользователь>", s)
    s = _TUNNEL.sub("<туннель>.trycloudflare.com", s)          # адрес туннеля — со всем путём (и ключом в нём)
    s = _KEY_IN_URL.sub(r"\1<ключ>", s)
    s = _KEY_IN_QUERY.sub(r"\1<ключ>", s)
    s = _API_KEY.sub("sk-ant-<скрыт>", s)
    return s


def drive_folder(home: str | None = None, exists=os.path.isdir) -> Path | None:
    """Папка «Google Диска для компьютера» на этом ПК (виртуальный диск с «My Drive»/«Мой диск» или зеркало в папке
    пользователя) → <она>/DotaCoach; не стоит — None. В корень «Google Drive» писать нельзя — только в «Мой диск»
    (рецензия 12)."""
    home = home if home is not None else os.environ.get("USERPROFILE") or str(Path.home())
    names = ("My Drive", "Мой диск")
    cands = []
    if os.name == "nt":
        for letter in "GHIJKLMNOPQRSTUVWXYZDEF":
            for n in names:
                cands.append(Path(f"{letter}:\\") / n)
    for root in ("Google Drive", "Google Диск"):
        for n in names:
            cands.append(Path(home) / root / n)
    for n in names:
        cands.append(Path(home) / n)
    for c in cands:
        try:
            if exists(str(c)):
                return c / "DotaCoach"
        except OSError:
            continue
    return None


def tail(text: str, limit: int = MAX_SECTION) -> str:
    return text if len(text) <= limit else "…(начало обрезано)…\n" + text[-limit:]


def read_text(path) -> str:
    try:
        return Path(path).read_text(encoding="utf-8", errors="replace") if path else ""
    except OSError:
        return ""


def dota_lines(text: str, moves: bool = True) -> str:
    """Из консоли Доты — строки кастомки и ошибки скриптов и интерфейса (остальное — шум движка); moves=False — без ходов
    игры (живой отчёт во время игры: ходы соперника хосту не показываем)."""
    keep = [x for x in text.splitlines()
            if ("[ТРЕНЕР]" in x or re.search(r"script error|error|ошибка|traceback|\.lua:\d+|\.js:\d+", x, re.I))
            and (moves or not MOVE.search(x))]
    return "\n".join(keep)


def agent_samples(path, limit: int = MAX_SAMPLES) -> tuple[str, dict]:
    """Из журнала агентов (JSONL): ошибки и примеры решений (начало и конец матча), уроки; сводка по записям."""
    errors, decisions, lessons, counts = [], [], [], {"записей": 0, "ошибок": 0, "решений": 0, "уроков": 0}
    try:
        lines = Path(path).read_text(encoding="utf-8", errors="replace").splitlines() if path else []
    except OSError:
        lines = []
    for line in lines:
        try:
            r = json.loads(line)
        except ValueError:
            continue
        counts["записей"] += 1
        if r.get("error"):
            counts["ошибок"] += 1
            errors.append(r)
        if r.get("decision"):
            counts["решений"] += 1
            decisions.append(r)
        if r.get("lesson") or r.get("event") == "match_learned":
            counts["уроков"] += 1
            lessons.append(r)
    half = limit // 2
    picked = decisions[:half] + (decisions[-half:] if len(decisions) > half else [])
    out = []

    def row(r):
        keep = {k: r.get(k) for k in ("clock", "team", "pos", "hero", "trigger", "model", "latency_s", "decision",
                                      "lesson", "error", "notes") if r.get(k) not in (None, "", [], {})}
        return json.dumps(keep, ensure_ascii=False)
    if errors:
        out.append("Ошибки (первые 10):")
        out += [row(r) for r in errors[:10]]
    if picked:
        out.append("Решения (начало и конец):")
        out += [row(r) for r in picked]
    if lessons:
        out.append("Обучение:")
        out += [json.dumps(r, ensure_ascii=False)[:600] for r in lessons[-20:]]
    return "\n".join(out), counts


TRACK_PATH_EVERY = 10         # с между точками пути героя в итоговом отчёте (в треке — раз в 2 с)
STILL_DIST = 60               # единиц карты за 2 с — «стоит на месте» (скорость героя ~300 в секунду)


def read_track(path) -> list[dict]:
    """Трек героев (Д24): JSONL, точка героя раз в 2 с по часам игры."""
    rows = []
    for line in read_text(path).splitlines():
        try:
            r = json.loads(line)
        except ValueError:
            continue
        if isinstance(r, dict) and r.get("team") and r.get("pos") is not None and r.get("t") is not None:
            rows.append(r)
    return rows


def _clock(t) -> str:
    t = int(round(float(t or 0)))
    return ("-" if t < 0 else "") + f"{abs(t) // 60}:{abs(t) % 60:02d}"


def _share(counter, total: int, top: int) -> str:
    return ", ".join(f"{k} {round(100 * n / max(1, total))}%" for k, n in counter.most_common(top))


def track_summary(rows: list[dict]) -> str:
    """По каждому герою: где был, сколько стоял, что делали руки, какие планы давал агент, цифры поминутно, смерти."""
    from collections import Counter, defaultdict              # noqa: PLC0415
    by = defaultdict(list)
    for r in rows:
        by[(str(r["team"]), int(r["pos"]))].append(r)
    out = [f"Трек: точка героя раз в 2 с по часам игры; «стоит» — сдвинулся меньше чем на {STILL_DIST} за 2 с."]
    for (team, pos), rs in sorted(by.items()):
        rs.sort(key=lambda r: float(r["t"]))
        alive = [r for r in rs if r.get("alive")]
        still = moving = 0
        for a, b in zip(rs, rs[1:]):
            if a.get("alive") and b.get("alive") and None not in (a.get("x"), a.get("y"), b.get("x"), b.get("y")) \
                    and 0 < float(b["t"]) - float(a["t"]) <= 5:
                if ((b["x"] - a["x"]) ** 2 + (b["y"] - a["y"]) ** 2) ** 0.5 < STILL_DIST:
                    still += 1
                else:
                    moving += 1
        zones = Counter(r["where"] for r in alive if r.get("where"))
        doing = Counter(r["doing"] for r in alive if r.get("doing"))
        plans = Counter(f"{r['plan']} {r.get('to') or ''}".strip() for r in rs if r.get("plan"))
        out.append(f"\n{team} {pos} {rs[-1].get('hero') or '?'}: {_clock(rs[0]['t'])}–{_clock(rs[-1]['t'])}, живой "
                   f"{round(100 * len(alive) / max(1, len(rs)))}% точек; стоял на месте "
                   f"{round(100 * still / max(1, still + moving))}% времени живым")
        if zones:
            out.append(f"  где был: {_share(zones, len(alive), 5)}")
        if doing:
            out.append(f"  руки: {_share(doing, len(alive), 8)}")
        if plans:
            out.append(f"  план агента: {_share(plans, len(rs), 6)}")
        marks = []
        for m in range(5, int(float(rs[-1]['t']) // 60) + 1, 5):
            done = [r for r in rs if float(r["t"]) <= m * 60]
            if done:
                r = done[-1]
                marks.append(f"{m}:00 доб {r.get('lh')}/{r.get('dn')} уб {r.get('k')} см {r.get('d')} ур {r.get('lvl')} "
                             f"зол {r.get('gold')}")
        last = rs[-1]
        marks.append(f"конец доб {last.get('lh')}/{last.get('dn')} уб {last.get('k')} см {last.get('d')} "
                     f"ур {last.get('lvl')} зол {last.get('gold')}")
        out.append("  цифры: " + "; ".join(marks))
        deaths = []
        for a, b in zip(rs, rs[1:]):
            if a.get("alive") and not b.get("alive"):
                deaths.append(f"{_clock(b['t'])} ({a.get('where') or '?'}, {a.get('x')},{a.get('y')}, было {a.get('hp')}%, "
                              f"руки: {a.get('doing') or '—'})")
        if deaths:
            out.append("  смерти: " + "; ".join(deaths))
    return "\n".join(out)


def track_path_lines(rows: list[dict], every: float = TRACK_PATH_EVERY) -> str:
    """Путь героев для карты: по строке на героя — точки раз в every с, «x,y» в сотнях единиц карты (центр карты — 0,0;
    углы — около ±75), «м» — мёртв. 40 минут — около 2 КБ на героя."""
    from collections import defaultdict                      # noqa: PLC0415
    by = defaultdict(list)
    for r in rows:
        by[(str(r["team"]), int(r["pos"]))].append(r)
    out = [f"Путь: точка раз в {every:g} с, x,y — в сотнях единиц карты, м — мёртв."]
    for (team, pos), rs in sorted(by.items()):
        rs.sort(key=lambda r: float(r["t"]))
        pts, last = [], None
        for r in rs:
            t = float(r["t"])
            if last is not None and t - last < every:
                continue
            last = t
            if not r.get("alive") or r.get("x") is None or r.get("y") is None:
                pts.append("м")
            else:
                pts.append(f"{round(r['x'] / 100)},{round(r['y'] / 100)}")
        out.append(f"{team} {pos} {rs[-1].get('hero') or '?'} с {_clock(rs[0]['t'])}: {' '.join(pts)}")
    return "\n".join(out)


def build(info: dict) -> str:
    """Текст отчёта из частей: info — {заголовок раздела: текст или словарь}; порядок — как в info."""
    parts = [f"DotaCoach — отчёт для Claude, {time.strftime('%Y-%m-%d %H:%M:%S')}"]
    for title, body in info.items():
        if body in (None, "", {}, []):
            continue
        if not isinstance(body, str):
            body = json.dumps(body, ensure_ascii=False, indent=1)
        parts.append(f"\n===== {title} =====\n{tail(body)}")
    return scrub("\n".join(parts)) + "\n"


def write(text: str, logs: Path, name: str, drive: Path | None = None) -> list[Path]:
    """Записать отчёт: в coach\\logs и (если есть) на Google Диск. → куда записан."""
    done = []
    for folder in (logs, drive):
        if folder is None:
            continue
        for attempt in range(3):                      # файл занят синхронизацией или антивирусом — ещё раз
            try:
                folder.mkdir(parents=True, exist_ok=True)
                p = folder / name
                tmp = p.with_name(p.name + ".part")
                tmp.write_text(text, encoding="utf-8")
                os.replace(tmp, p)
                done.append(p)
                break
            except OSError:
                if attempt < 2:
                    time.sleep(0.3)
    return done


def final_name() -> str:
    return f"{FINAL_PREFIX}{time.strftime('%Y%m%d_%H%M%S')}.txt"

