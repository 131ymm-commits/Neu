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

