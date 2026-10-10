"""ИИ-тренер соперника (решение Д16). Слова автора, 10.10.2026: «ок давай пока без друга. … ок давай сейчас версия
ты играеш за две команды (агентами) и чужого тренера (противник.). я за своего».

Пока друг не открыл пульт Тьмы, Тьмой командует ИИ-тренер: раз в PERIOD секунд он смотрит, что видит его команда
(console.team_view — туман войны как у неё в игре), и отдаёт 0–3 приказа коротким форматом тем же путём, что пульт
друга (Room.remote_order: тот же строгий разбор; приказ доходит до игры ровно раз). Друг открыл пульт — ИИ-тренер
молчит. Мотор — Claude Code по подписке (`claude -p` с JSON-схемой, быстрая модель), без Claude или после сбоя —
простые правила по времени игры и по вышкам. Приказы ИИ-тренера в окно хоста не печатаются (это приказы
противника) — только в журнал coach/logs/ai_coach_*.jsonl.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import tempfile
import threading
import time
from pathlib import Path

from .console import _stamp, team_view

PERIOD = 60.0              # с между решениями тренера (живой тренер отдаёт приказ раз в минуту-две)
FRIEND_FRESH = 15.0        # с: друг на пульте, если его пульт спрашивал обзор не раньше
MAX_ORDERS = 3
LIMIT_PAUSE = 600.0        # с: кончился лимит подписки — до конца паузы правила
KEY_VARS = ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN")      # с ключом в окружении `claude -p` платит ключом
LIMIT_RE = re.compile(r"limit|лимит", re.I)

COACH_SCHEMA = {"type": "object", "additionalProperties": False, "required": ["orders"],
                "properties": {"orders": {"type": "array", "items": {"type": "string"}, "maxItems": MAX_ORDERS},
                               "why": {"type": "string"}}}

SYSTEM = """Ты — тренер команды {team_ru} в Dota 2. Пятью героями твоей команды управляют агенты: каждый сам фармит,
дерётся и отступает, а ты раз в минуту даёшь им 0–3 коротких приказа — как капитан, который видит карту.

Приказы пишутся строго в коротком формате: «[кому] действие [где/что] [!]».
- кому: 1…5 (позиции твоих героев), несколько — «23»; «все», «все-1», «все кроме 4,5».
- действия: фарм, пуш, деф, ганг, сбор, рош, торм, смок, назад, фокус, драка, жди, сплит, вард, стак, купи, юз, бб,
  ульт, держи, сейв, за, тп, иди, сам, отмена. Запрет — «не» перед действием («все не рош»).
- где: линии топ, мид, бот; сейф, хард; лес, их лес, древние, база, руна, рош, торм, аутпост, лотос; вышки т1…т4.
- цель: герой врага по имени (марс, пудж, ам…) или позиция врага в1…в5.
- «!» в конце — срочно.
Примеры: «1 фарм лес» · «23 ганг мид» · «все-1 пуш бот т2» · «3 ульт марс !» · «4 сейв 1» · «все смок ганг мид» ·
«все назад» · «все не рош».

Правила: не дёргай команду без нужды — если всё идёт хорошо, приказов может не быть (пустой список). Позиции: 1 —
керри, 2 — мидер, 3 — оффлейнер, 4 и 5 — саппорты; варды, стаки и сейвы — работа саппортов (4, 5), керри пусть
фармит. Не отправляй героев в драку, если враги заметно сильнее; при перевесе — пуш вышек и Рошан. Ты видишь
только то, что видит твоя команда. Ответ — JSON по схеме: orders — список строк-приказов, why — одна фраза, зачем."""


def no_key_env() -> dict:
    return {k: v for k, v in os.environ.items() if k not in KEY_VARS}


def compact_view(view: dict) -> dict:
    """Обзор команды для промпта — коротко: часы, счёт, свои герои, видимые и пропавшие враги, вышки по линиям."""
    def pct(hp):
        return round(100 * hp[0] / max(1, hp[1])) if isinstance(hp, list) and len(hp) == 2 else None

    towers = {}
    for t in view.get("towers") or []:
        side = "свои" if t.get("team") == view.get("team") else "их"
        if t.get("alive"):
            towers.setdefault(side, {}).setdefault(t.get("lane"), []).append(t.get("tier"))
    clock = view.get("game", {}).get("clock")
    recent = [e for e in view.get("events") or [] if clock is None or _stamp(e) >= clock - 120]   # за 2 минуты
    return {
        "часы": f"{int(clock) // 60}:{int(clock) % 60:02d}" if isinstance(clock, (int, float)) and clock >= 0
        else clock, "счёт": view.get("score"),
        "мои": [{"поз": h.get("pos"), "герой": h.get("hero_ru"), "ур": h.get("lvl"), "жив": h.get("alive"),
                 "здоровье%": pct(h.get("hp")), "где": h.get("where"), "делает": h.get("doing"),
                 "возрождение": h.get("respawn")} for h in view.get("heroes") or []],
        "враги_видны": [{"герой": e.get("hero_ru"), "ур": e.get("lvl"), "здоровье%": pct(e.get("hp")),
                         "где": e.get("where")} for e in view.get("enemies") or []],
        "враги_пропали": [{"герой": m.get("hero_ru"), "где_видели": m.get("seen"), "с_назад": m.get("ago"),
                           "мёртв": m.get("dead")} for m in view.get("missing") or []],
        "живые_вышки": towers, "события_за_2_минуты": recent[-4:],
    }


class RulesCoach:
    """Тренер без Claude: по времени игры и по вышкам. Это НЕ Claude — так и пишется в журнале."""
    label = "правила"

    def orders(self, view: dict) -> tuple[list[str], str]:
        clock = (view.get("game") or {}).get("clock") or 0
        mine = [h for h in view.get("heroes") or [] if h.get("alive")]
        hp = [h["hp"][0] / max(1, h["hp"][1]) for h in mine if isinstance(h.get("hp"), list) and len(h["hp"]) == 2]
        if mine and hp and sum(hp) / len(hp) < 0.35:
            return ["все назад"], "команда сильно ранена"
        if clock < 600:
            return [], "ранняя игра: агенты фармят сами"
        theirs = {}
        for t in view.get("towers") or []:
            if t.get("team") != view.get("team") and t.get("alive"):
                theirs[t["lane"]] = min(theirs.get(t["lane"], 9), int(t.get("tier") or 9))
        if not theirs:
            return ["все пуш мид"], "вышек врага не видно — давим центр"
        order = {"bot": 0, "mid": 1, "top": 2}
        lane = min(theirs, key=lambda k: (theirs[k], order.get(k, 3)))
        if len(mine) >= 4:
            return [f"все-1 пуш {LANE_RU.get(lane, lane)} т{theirs[lane]}"], "давим ближайшую вышку"
        return [], "мало живых — ждём"


LANE_RU = {"top": "топ", "mid": "мид", "bot": "бот"}


class ClaudeCoach:
    """Тренер на Claude Code по подписке: `claude -p` быстрой моделью, ответ — JSON по COACH_SCHEMA."""

    def __init__(self, claude: str, model: str = "haiku", team_ru: str = "Тьма", runner=None, timeout: float = 90.0):
        self.claude, self.model, self.timeout = claude, model, timeout
        self.runner = runner or subprocess.run
        self.cwd = tempfile.mkdtemp(prefix="vc_coach_")
        self.system_file = str(Path(self.cwd) / "coach_system.txt")
        Path(self.system_file).write_text(SYSTEM.format(team_ru=team_ru), encoding="utf-8")
        self.label = f"Claude Code ({model})"

    def orders(self, view: dict) -> tuple[list[str], str]:
        argv = [self.claude, "-p", "--model", self.model, "--output-format", "json", "--safe-mode",
                "--system-prompt-file", self.system_file, "--tools", "", "--disallowedTools", "mcp__*",
                "--no-session-persistence", "--json-schema", json.dumps(COACH_SCHEMA, separators=(",", ":")),
                "Дай приказы своей команде сейчас. Обзор — во входных данных."]
        p = self.runner(argv, input=json.dumps(compact_view(view), ensure_ascii=False), capture_output=True,
                        text=True, encoding="utf-8", errors="replace", timeout=self.timeout, cwd=self.cwd,
                        env=no_key_env())
        try:
            data = json.loads(p.stdout)
        except (TypeError, ValueError):
            raise RuntimeError(f"claude -p: не JSON (код {p.returncode}): {(p.stdout or p.stderr or '')[:200]}") from None
        if data.get("is_error"):
            raise RuntimeError(f"claude -p: {str(data.get('result'))[:200]}")
        out = data.get("structured_output")
        if not isinstance(out, dict):
            try:
                out = json.loads(data.get("result") or "")
            except (TypeError, ValueError):
                out = None
        if not isinstance(out, dict):                    # ни схемы, ни JSON — сбой мотора, а не «приказов нет»
            raise RuntimeError(f"claude -p: ответ без JSON: {str(data.get('result'))[:200]}")
        orders = [str(o).strip() for o in out.get("orders") or [] if str(o).strip()][:MAX_ORDERS]
        return orders, str(out.get("why") or "")

    def close(self) -> None:
        shutil.rmtree(self.cwd, ignore_errors=True)


class AICoach:
    """Командует стороной `team`, пока на её пульте нет человека. step() — одно решение (для тестов)."""

    def __init__(self, room, team: str, backend, period: float = PERIOD, log_path: Path | None = None,
                 fallback=None, clock=time.monotonic, max_calls: int | None = None):
        self.room, self.team, self.backend, self.period = room, team, backend, period
        self.fallback = fallback or RulesCoach()
        self.log_path, self.clock = log_path, clock
        self.max_calls = max_calls                   # вызовов Claude за запуск: дальше правила (лимит подписки)
        self.claude_calls = 0
        self.pause_until = 0.0
        self.stop = threading.Event()
        self.sent = 0

    def friend_on(self) -> bool:
        return time.time() - self.room.console_seen.get(self.team, 0) < FRIEND_FRESH

    def step(self) -> list[dict]:
        if not self.room.game_linked() or self.friend_on():
            return []
        view = team_view(self.room, self.team)
        if (view.get("game") or {}).get("clock") is None:
            return []
        backend, err = self.backend, None
        out_of_calls = self.max_calls is not None and self.claude_calls >= self.max_calls
        if self.clock() < self.pause_until or (out_of_calls and backend is not self.fallback):
            backend = self.fallback
        if backend is not self.fallback:
            self.claude_calls += 1
        try:
            orders, why = backend.orders(view)
        except Exception as e:                       # noqa: BLE001 — сбой мотора: в этот раз правила
            err = f"{type(e).__name__}: {e}"
            if LIMIT_RE.search(err):
                self.pause_until = self.clock() + LIMIT_PAUSE
            backend = self.fallback
            orders, why = backend.orders(view)
        if self.stop.is_set() or self.friend_on():   # пока думал (до полутора минут), друг открыл пульт или выход
            return []
        results = []
        for text in orders[:MAX_ORDERS]:
            entry = self.room.remote_order(self.team, text, source="ai_coach")
            results.append({"text": text, "queued": entry.get("queued"), "errors": entry.get("errors")})
            if entry.get("queued"):
                self.sent += 1
        self._log({"t": round(time.time(), 3), "clock": view["game"].get("clock"), "team": self.team,
                   "backend": getattr(backend, "label", str(backend)), "why": why, "orders": results, "error": err})
        return results

    def _log(self, rec: dict) -> None:
        if self.log_path is None:
            return
        try:
            self.log_path.parent.mkdir(parents=True, exist_ok=True)
            with self.log_path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        except OSError:
            pass

    def _loop(self) -> None:
        while not self.stop.wait(self.period):
            try:
                self.step()
            except Exception as e:                   # noqa: BLE001 — тренер не должен ронять лаунчер
                self._log({"t": round(time.time(), 3), "error": f"{type(e).__name__}: {e}"})

    def start(self) -> None:
        threading.Thread(target=self._loop, daemon=True, name="ai-coach").start()

    def close(self) -> None:
        self.stop.set()
        for b in (self.backend, self.fallback):
            if hasattr(b, "close"):
                b.close()
