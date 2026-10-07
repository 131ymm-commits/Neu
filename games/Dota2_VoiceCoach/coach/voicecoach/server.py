"""Сервер тренера: принимает речь (текст) от голосовых клиентов, разбирает её в команды
и отдаёт их игре; от игры принимает состояние матча и ответы агентов.

Только стандартная библиотека. Запуск:  python -m voicecoach.server --port 8787
Все пути — JSON. Комната (room) объединяет двух тренеров и одну игру; команда тренера
(team) — radiant или dire. Игра опрашивает /commands; голосовые клиенты — /events.

  POST /api/{room}/say      {"team","text","source"?,"mode"?} → разбор + команды в очередь
       mode="short" — короткий формат (textcmd.py, решение автора 07.10.2026: голос отложен):
       строгий разбор; при ошибке ничего не уходит, в ответе — ошибки и подсказка в коротком
       формате из свободного разбора. Без mode — свободная фраза (parser.py), как раньше.
  GET  /api/{room}/commands?team=radiant&after=N             ← игра забирает команды (seq > N)
  POST /api/{room}/state    {"team","agents":[...],"enemy_heroes":[...]}  ← состав матча от игры
  POST /api/{room}/events   {"team","events":[{"pos","kind","text"}]}       ← ответы агентов
  GET  /api/{room}/events?team=radiant&after=N&wait=20       → клиенты ждут ответы (long-poll)
  GET  /api/{room}/w/{state|events}?team=..&d=<JSON в url-кодировке>  ← запись через GET
       (у ботов и у скрытой веб-панели кастомки нет удобного POST)
  GET  /api/{room}/commands?...&fmt=title                    → тот же JSON внутри <title> страницы
       (так ответ читает DOTAHTMLPanel в аркаде — research/00_SUMMARY.md)
  GET  /api/{room}/ptt?team=..&state=down|up               ← глобальная клавиша «нажми и говори»
       (coach/ptt_hotkey.py): событие kind=ptt уходит странице, она включает распознавание
  POST /api/{room}/tick     {"clock","heroes":[наблюдения],"coached"}   ← кастомка раз в секунду (Д11):
       наблюдения героев → агенты Claude (agents.py) → в ответе последние решения агентов
  GET  /api/{room}/agents                                  → состояние агентов, память, задержка, токены
  GET  /api/health

Запасной канал к ботам (если HTTP из ботов не работает): --inbox <папка bots/coach в Доте> —
сервер дублирует команды в файлы inbox_radiant.lua / inbox_dire.lua, боты читают их через loadfile
(так делает проект bota, 2025).

Состав (имена и как их зовут голосом) можно задать заранее: --roster roster.json
  {"radiant": [{"pos": 1, "name": "Miracle-", "aliases": ["миракл"]}, ...], "dire": [...]}

Агенты героев (кастомка, решение Д11): --agents rules|api|cli (по умолчанию rules — правила, НЕ Claude);
--radiant / --dire — свой мотор для одной стороны (например, соперник на бесплатных правилах);
api — ключ в ANTHROPIC_API_KEY и --model; cli — Claude Code (`claude -p`, путь — --claude).
"""
from __future__ import annotations

import argparse
import html
import json
import os
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

from .agents import AgentHub, make_backend
from .describe import describe
from .parser import Agent, MatchContext, parse
from .textcmd import parse_short, suggest

TEAMS = ("radiant", "dire")
MAX_QUEUE = 500
STATIC = Path(__file__).resolve().parent.parent / "web"


def to_lua(v) -> str:
    """Python → литерал Lua (для файла-ящика ботов)."""
    if v is None:
        return "nil"
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (int, float)):
        return repr(v)
    if isinstance(v, str):
        return '"' + v.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n") + '"'
    if isinstance(v, (list, tuple)):
        return "{" + ", ".join(to_lua(x) for x in v) + "}"
    if isinstance(v, dict):
        parts = []
        for k, x in v.items():
            key = k if isinstance(k, str) and k.isidentifier() else "[" + to_lua(k) + "]"
            parts.append(f"{key} = {to_lua(x)}")
        return "{" + ", ".join(parts) + "}"
    raise TypeError(type(v))


class Room:
    def __init__(self, name: str):
        self.name = name
        self.inbox_dir: str | None = None
        self.lock = threading.Condition()
        self.seq = 0
        self.commands = {t: [] for t in TEAMS}
        self.events = {t: [] for t in TEAMS}
        self.ctx = {t: MatchContext(team=t) for t in TEAMS}
        self.log: list[dict] = []
        self.roster_source = "нет"
        self.agents: AgentHub | None = None       # агенты героев кастомки — при первом /tick

    def _next(self) -> int:
        self.seq += 1
        return self.seq

    def say(self, team: str, text: str, source: str = "voice", mode: str = "free") -> dict:
        if mode == "short":
            return self.say_short(team, text, source)
        with self.lock:
            ctx = self.ctx[team]
            res = parse(text, ctx)
            ctx.remember(res)
            out = []
            names = {a.pos: a.name for a in ctx.agents if a.name}
            for c in res.commands:
                item = {"seq": self._next(), "t": time.time(), **c.to_json(), "human": describe(c, names)}
                if not c.clarify:
                    self.commands[team].append(item)
                out.append(item)
            # переспрос — сразу как событие тренеру
            for item in out:
                if item["clarify"]:
                    self._event(team, {"pos": 0, "kind": "clarify", "text": item["clarify"]})
            del self.commands[team][:-MAX_QUEUE]
            self._write_inbox(team)
            entry = {"t": time.time(), "team": team, "text": text, "source": source,
                     "confidence": res.confidence, "unknown": res.unknown, "commands": out}
            self.log.append(entry)
            self.lock.notify_all()
            return entry

    def say_short(self, team: str, text: str, source: str = "text") -> dict:
        """Короткий формат: всё или ничего. Ошибка → подсказка из свободного разбора, в очередь не идёт."""
        with self.lock:
            ctx = self.ctx[team]
            names = {a.pos: a.name for a in ctx.agents if a.name}
            res = parse_short(text, ctx)
            out = []
            suggestion, suggestion_human = "", []
            if res.ok:
                for c in res.commands:
                    item = {"seq": self._next(), "t": time.time(), **c.to_json(), "human": describe(c, names)}
                    self.commands[team].append(item)
                    out.append(item)
                del self.commands[team][:-MAX_QUEUE]
                self._write_inbox(team)
            else:
                free = parse(text, MatchContext(team=ctx.team, agents=ctx.agents, enemy_heroes=ctx.enemy_heroes))
                suggestion = suggest(free.commands, ctx)
                if suggestion:
                    check = parse_short(suggestion, ctx)
                    suggestion_human = [describe(c, names) for c in check.commands] if check.ok else []
                    if not check.ok:
                        suggestion = ""
            entry = {"t": time.time(), "team": team, "text": text, "source": source, "format": "short",
                     "confidence": 1.0 if res.ok else 0.0, "unknown": [], "commands": out,
                     "errors": res.errors or ([] if res.commands else ["пустая строка"]),
                     "suggestion": suggestion, "suggestion_human": suggestion_human}
            if res.ok:
                entry["errors"] = []
            self.log.append(entry)
            self.lock.notify_all()
            return entry

    def _write_inbox(self, team: str) -> None:
        """Файл-ящик для ботов: последние команды команды; запись через временный файл."""
        if not self.inbox_dir:
            return
        keep = [{k: c[k] for k in ("seq", "action", "agents", "params", "urgent", "after_prev")}
                for c in self.commands[team][-30:]]
        text = "return " + to_lua({"seq": self.seq, "commands": keep}) + "\n"
        path = os.path.join(self.inbox_dir, f"inbox_{team}.lua")
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            f.write(text)
        os.replace(tmp, path)

    def commands_after(self, team: str, after: int) -> list[dict]:
        with self.lock:
            return [c for c in self.commands[team] if c["seq"] > after]

    def set_state(self, team: str, state: dict) -> None:
        """Состав матча. Сливается с уже известным по позиции: игра сообщает героев,
        файл состава — имена и прозвища; пустое поле не затирает известное."""
        with self.lock:
            known = {a.pos: a for a in self.ctx[team].agents}
            for a in state.get("agents", []):
                pos = int(a["pos"])
                old = known.get(pos, Agent(pos=pos))
                aliases = tuple(x.lower().replace("ё", "е") for x in a.get("aliases", []) if x)
                known[pos] = Agent(pos=pos, name=a.get("name") or old.name,
                                   aliases=aliases or old.aliases, hero=a.get("hero") or old.hero)
            self.ctx[team].agents = [known[p] for p in sorted(known)]
            if state.get("enemy_heroes"):
                self.ctx[team].enemy_heroes = list(state["enemy_heroes"])

    def state(self, team: str) -> dict:
        with self.lock:
            c = self.ctx[team]
            return {"agents": [{"pos": a.pos, "name": a.name, "aliases": list(a.aliases), "hero": a.hero}
                               for a in c.agents],
                    "enemy_heroes": list(c.enemy_heroes), "source": self.roster_source}

    def _event(self, team: str, ev: dict) -> None:
        ev = {"seq": self._next(), "t": time.time(), **ev}
        self.events[team].append(ev)
        del self.events[team][:-MAX_QUEUE]

    def add_events(self, team: str, events: list[dict]) -> None:
        with self.lock:
            for ev in events:
                self._event(team, {"pos": ev.get("pos", 0), "kind": ev.get("kind", "say"),
                                   "text": ev.get("text", "")})
            self.lock.notify_all()

    def events_after(self, team: str, after: int, wait: float) -> list[dict]:
        deadline = time.time() + wait
        with self.lock:
            while True:
                evs = [e for e in self.events[team] if e["seq"] > after]
                left = deadline - time.time()
                if evs or left <= 0:
                    return evs
                self.lock.wait(timeout=left)


def rules_agents(room_name: str) -> AgentHub:
    """Агенты по умолчанию: правила без модели с обеих сторон (не Claude)."""
    return AgentHub({"radiant": make_backend("rules"), "dire": make_backend("rules")})


class Hub:
    def __init__(self, agent_factory=None):
        self.rooms: dict[str, Room] = {}
        self.lock = threading.Lock()
        self.agent_factory = agent_factory or rules_agents

    def room(self, name: str) -> Room:
        with self.lock:
            if name not in self.rooms:
                self.rooms[name] = Room(name)
            return self.rooms[name]

    def agents(self, room: Room) -> AgentHub:
        with self.lock:
            if room.agents is None:
                room.agents = self.agent_factory(room.name)
            return room.agents


def make_handler(hub: Hub):
    class Handler(BaseHTTPRequestHandler):
        server_version = "VoiceCoach/0.1"

        def log_message(self, fmt, *args):      # тише в консоли
            pass

        def _send(self, code: int, obj=None, ctype="application/json; charset=utf-8", raw: bytes = None):
            body = raw if raw is not None else json.dumps(obj, ensure_ascii=False).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Headers", "Content-Type")
            self.end_headers()
            self.wfile.write(body)

        def do_OPTIONS(self):
            self._send(204, raw=b"")

        def _body(self) -> dict:
            n = int(self.headers.get("Content-Length") or 0)
            if n <= 0:
                return {}
            return json.loads(self.rfile.read(n).decode("utf-8"))

        def _route(self):
            u = urlparse(self.path)
            parts = [p for p in u.path.split("/") if p]
            q = {k: v[0] for k, v in parse_qs(u.query).items()}
            return parts, q

        def _team(self, q, body=None):
            team = (body or {}).get("team") or q.get("team") or "radiant"
            if team not in TEAMS:
                raise ValueError(f"team должен быть radiant или dire, а не {team!r}")
            return team

        def do_GET(self):
            try:
                parts, q = self._route()
                if not parts or parts == ["index.html"]:
                    page = STATIC / "index.html"
                    if page.exists():
                        return self._send(200, raw=page.read_bytes(), ctype="text/html; charset=utf-8")
                    return self._send(404, {"error": "нет web/index.html"})
                if parts == ["favicon.ico"]:
                    return self._send(204, raw=b"")
                if parts == ["api", "health"]:
                    return self._send(200, {"ok": True, "rooms": len(hub.rooms)})
                if len(parts) == 3 and parts[0] == "api":
                    room = hub.room(parts[1])
                    team = self._team(q)
                    after = int(q.get("after", 0))
                    if parts[2] == "commands":
                        data = {"commands": room.commands_after(team, after), "seq": room.seq}
                        if q.get("fmt") == "title":
                            # «номер|JSON»: клиент узнаёт свой ответ (страница может прийти из кеша)
                            body = json.dumps(data, ensure_ascii=False)
                            rid = q.get("rid")
                            if rid:
                                body = f"{rid}|{body}"
                            page = f"<!doctype html><html><head><title>{html.escape(body)}</title></head><body></body></html>"
                            return self._send(200, raw=page.encode("utf-8"), ctype="text/html; charset=utf-8")
                        return self._send(200, data)
                    if parts[2] == "events":
                        wait = min(float(q.get("wait", 0)), 30.0)
                        return self._send(200, {"events": room.events_after(team, after, wait)})
                    if parts[2] == "state":
                        return self._send(200, room.state(team))
                    if parts[2] == "ptt":
                        st = q.get("state")
                        if st not in ("down", "up"):
                            raise ValueError("state должен быть down или up")
                        room.add_events(team, [{"pos": 0, "kind": "ptt", "text": st}])
                        return self._send(200, {"ok": True})
                    if parts[2] == "log":
                        return self._send(200, {"log": room.log[-100:]})
                    if parts[2] == "agents":
                        if room.agents is None:
                            return self._send(200, {"agents": [], "summary": {}, "backend": {}})
                        return self._send(200, room.agents.status())
                if len(parts) == 4 and parts[0] == "api" and parts[2] == "w":
                    room = hub.room(parts[1])
                    team = self._team(q)
                    body = json.loads(unquote(q.get("d", "{}"))) if "d" in q else {}
                    if parts[3] == "state":
                        room.set_state(team, body)
                        return self._send(200, {"ok": True})
                    if parts[3] == "events":
                        room.add_events(team, body.get("events", []))
                        return self._send(200, {"ok": True})
                return self._send(404, {"error": "нет такого пути"})
            except ValueError as e:
                return self._send(400, {"error": str(e)})

        def do_POST(self):
            try:
                parts, q = self._route()
                body = self._body()
                if len(parts) == 3 and parts[0] == "api" and parts[2] == "tick":
                    room = hub.room(parts[1])
                    return self._send(200, hub.agents(room).tick(body))
                if len(parts) == 3 and parts[0] == "api":
                    room = hub.room(parts[1])
                    team = self._team(q, body)
                    if parts[2] == "say":
                        text = (body.get("text") or "").strip()
                        if not text:
                            return self._send(400, {"error": "пустой text"})
                        return self._send(200, room.say(team, text, body.get("source", "voice"),
                                                        body.get("mode", "free")))
                    if parts[2] == "state":
                        room.set_state(team, body)
                        return self._send(200, {"ok": True})
                    if parts[2] == "events":
                        room.add_events(team, body.get("events", []))
                        return self._send(200, {"ok": True})
                return self._send(404, {"error": "нет такого пути"})
            except (ValueError, KeyError, json.JSONDecodeError) as e:
                return self._send(400, {"error": str(e)})

    return Handler


DEMO_ROSTER = Path(__file__).resolve().parent.parent / "data" / "demo_roster.json"


def load_roster(hub: "Hub", path: str, room: str = "local", source: str | None = None) -> None:
    with open(path, encoding="utf-8") as f:
        roster = json.load(f)
    r = hub.room(room)
    for team in TEAMS:
        if roster.get(team):
            r.set_state(team, {"agents": roster[team]})
    r.roster_source = source or str(path)


def serve(host="127.0.0.1", port=8787, agent_factory=None) -> ThreadingHTTPServer:
    hub = Hub(agent_factory)
    srv = ThreadingHTTPServer((host, port), make_handler(hub))
    srv.hub = hub
    return srv


LOGS = Path(__file__).resolve().parent.parent / "logs"


def agent_factory_from_args(a):
    """Моторы сторон и журнал вызовов из аргументов командной строки."""
    kinds = {"radiant": a.radiant or a.agents, "dire": a.dire or a.agents}
    backends = {t: make_backend(k, a.model, a.claude) for t, k in kinds.items()}
    personas = json.loads(Path(a.personas).read_text(encoding="utf-8")) if a.personas else {}
    for spec in a.persona or []:                     # radiant:1=digitizer/agents/vasya.json
        try:
            who, path = spec.split("=", 1)
            team, pos = who.split(":", 1)
            int(pos)
        except ValueError:
            raise ValueError(f"--persona {spec!r}: нужно сторона:позиция=файл, например radiant:1=agents/vasya.json")
        if team not in TEAMS:
            raise ValueError(f"--persona {spec!r}: сторона radiant или dire")
        personas.setdefault(team, {})[pos] = json.loads(Path(path).read_text(encoding="utf-8"))
    prices = {k: v for k, v in (("in", a.price_in), ("out", a.price_out), ("cache_read", a.price_cache_read),
                                ("cache_write", a.price_cache_write)) if v is not None}

    def factory(room_name: str) -> AgentHub:
        log = LOGS / f"agents_{room_name}_{time.strftime('%Y%m%d_%H%M%S')}.jsonl"
        return AgentHub(backends, period=a.period, max_calls=a.max_calls, log_path=log, personas=personas or None,
                        prices=prices or None)
    return factory, backends


def main(argv=None):
    ap = argparse.ArgumentParser(description="Сервер голосового тренера Dota 2")
    ap.add_argument("--host", default="127.0.0.1",
                    help="0.0.0.0 — чтобы подключался второй компьютер или телефон в той же сети")
    ap.add_argument("--port", type=int, default=8787)
    ap.add_argument("--roster", help="JSON с именами агентов по командам (см. начало файла)")
    ap.add_argument("--room", default="local")
    ap.add_argument("--inbox", help="папка bots/coach в Доте: дублировать команды в файлы для ботов")
    ag = ap.add_argument_group("агенты героев кастомки (решение Д11)")
    ag.add_argument("--agents", choices=("rules", "api", "cli"), default="rules",
                    help="мотор агентов: rules — правила, не Claude; api — Claude по ключу; cli — Claude Code")
    ag.add_argument("--radiant", choices=("rules", "api", "cli"), help="свой мотор для Света")
    ag.add_argument("--dire", choices=("rules", "api", "cli"), help="свой мотор для Тьмы")
    ag.add_argument("--model", help="модель Claude (имя из документации Anthropic); для api обязательна")
    ag.add_argument("--claude", default="claude", help="путь к Claude Code для --agents cli")
    ag.add_argument("--period", type=float, default=4.0, help="решение агента не реже раза в столько секунд игры")
    ag.add_argument("--max-calls", type=int, help="предел вызовов модели за запуск сервера (защита кошелька)")
    ag.add_argument("--personas", help="JSON характеров: {\"radiant\": {\"1\": {…agent_params…}}, …}")
    ag.add_argument("--persona", action="append", metavar="СТОРОНА:ПОЗ=ФАЙЛ",
                    help="характер одного агента из оцифровки: radiant:1=../digitizer/agents/vasya.json (можно несколько)")
    for k in ("in", "out", "cache-read", "cache-write"):
        ag.add_argument(f"--price-{k}", type=float, help="цена за 1 млн токенов, $ — для оценки цены в журнале")
    a = ap.parse_args(argv)
    try:
        factory, backends = agent_factory_from_args(a)
    except ValueError as e:
        raise SystemExit(f"Агенты: {e}")
    srv = serve(a.host, a.port, factory)
    for t, b in backends.items():
        print(f"Агенты {'Света' if t == 'radiant' else 'Тьмы'}: {b.label}")
    print(f"Журнал вызовов агентов: {LOGS}")
    if a.inbox:
        srv.hub.room(a.room).inbox_dir = a.inbox
        for team in TEAMS:
            srv.hub.room(a.room)._write_inbox(team)
        print(f"Команды дублируются в файлы: {a.inbox}")
    if a.roster:
        load_roster(srv.hub, a.roster, a.room)
        print(f"Состав загружен из {a.roster}")
    else:
        load_roster(srv.hub, str(DEMO_ROSTER), a.room, source="демо")
        print("Состав — демо (Вася, Петя, Коля, Дима, Саша); свой — через --roster")
    print(f"Тренер слушает http://{a.host}:{a.port}/  (Ctrl+C — выход)")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    for name, room in srv.hub.rooms.items():
        if room.agents is not None:
            print(f"Агенты комнаты {name}: {json.dumps(room.agents.summary(), ensure_ascii=False)}")
            room.agents.close()


if __name__ == "__main__":
    main()
