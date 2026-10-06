"""Сервер тренера: принимает речь (текст) от голосовых клиентов, разбирает её в команды
и отдаёт их игре; от игры принимает состояние матча и ответы агентов.

Только стандартная библиотека. Запуск:  python -m voicecoach.server --port 8787
Все пути — JSON. Комната (room) объединяет двух тренеров и одну игру; команда тренера
(team) — radiant или dire. Игра опрашивает /commands; голосовые клиенты — /events.

  POST /api/{room}/say      {"team","text","source"?}      → разбор + команды в очередь
  GET  /api/{room}/commands?team=radiant&after=N             ← игра забирает команды (seq > N)
  POST /api/{room}/state    {"team","agents":[...],"enemy_heroes":[...]}  ← состав матча от игры
  POST /api/{room}/events   {"team","events":[{"pos","kind","text"}]}       ← ответы агентов
  GET  /api/{room}/events?team=radiant&after=N&wait=20       → клиенты ждут ответы (long-poll)
  GET  /api/health
"""
from __future__ import annotations

import argparse
import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from .parser import Agent, MatchContext, parse

TEAMS = ("radiant", "dire")
MAX_QUEUE = 500
STATIC = Path(__file__).resolve().parent.parent / "web"


class Room:
    def __init__(self, name: str):
        self.name = name
        self.lock = threading.Condition()
        self.seq = 0
        self.commands = {t: [] for t in TEAMS}
        self.events = {t: [] for t in TEAMS}
        self.ctx = {t: MatchContext(team=t) for t in TEAMS}
        self.log: list[dict] = []

    def _next(self) -> int:
        self.seq += 1
        return self.seq

    def say(self, team: str, text: str, source: str = "voice") -> dict:
        with self.lock:
            ctx = self.ctx[team]
            res = parse(text, ctx)
            ctx.remember(res)
            out = []
            for c in res.commands:
                item = {"seq": self._next(), "t": time.time(), **c.to_json()}
                if not c.clarify:
                    self.commands[team].append(item)
                out.append(item)
            # переспрос — сразу как событие тренеру
            for item in out:
                if item["clarify"]:
                    self._event(team, {"pos": 0, "kind": "clarify", "text": item["clarify"]})
            del self.commands[team][:-MAX_QUEUE]
            entry = {"t": time.time(), "team": team, "text": text, "source": source,
                     "confidence": res.confidence, "unknown": res.unknown, "commands": out}
            self.log.append(entry)
            self.lock.notify_all()
            return entry

    def commands_after(self, team: str, after: int) -> list[dict]:
        with self.lock:
            return [c for c in self.commands[team] if c["seq"] > after]

    def set_state(self, team: str, state: dict) -> None:
        with self.lock:
            agents = []
            for a in state.get("agents", []):
                aliases = tuple(x.lower() for x in a.get("aliases", []) if x)
                agents.append(Agent(pos=int(a["pos"]), name=a.get("name", ""), aliases=aliases,
                                    hero=a.get("hero")))
            if agents:
                self.ctx[team].agents = agents
            if "enemy_heroes" in state:
                self.ctx[team].enemy_heroes = list(state["enemy_heroes"])

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


class Hub:
    def __init__(self):
        self.rooms: dict[str, Room] = {}
        self.lock = threading.Lock()

    def room(self, name: str) -> Room:
        with self.lock:
            if name not in self.rooms:
                self.rooms[name] = Room(name)
            return self.rooms[name]


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
                if parts == ["api", "health"]:
                    return self._send(200, {"ok": True, "rooms": len(hub.rooms)})
                if len(parts) == 3 and parts[0] == "api":
                    room = hub.room(parts[1])
                    team = self._team(q)
                    after = int(q.get("after", 0))
                    if parts[2] == "commands":
                        return self._send(200, {"commands": room.commands_after(team, after), "seq": room.seq})
                    if parts[2] == "events":
                        wait = min(float(q.get("wait", 0)), 30.0)
                        return self._send(200, {"events": room.events_after(team, after, wait)})
                    if parts[2] == "log":
                        return self._send(200, {"log": room.log[-100:]})
                return self._send(404, {"error": "нет такого пути"})
            except ValueError as e:
                return self._send(400, {"error": str(e)})

        def do_POST(self):
            try:
                parts, q = self._route()
                body = self._body()
                if len(parts) == 3 and parts[0] == "api":
                    room = hub.room(parts[1])
                    team = self._team(q, body)
                    if parts[2] == "say":
                        text = (body.get("text") or "").strip()
                        if not text:
                            return self._send(400, {"error": "пустой text"})
                        return self._send(200, room.say(team, text, body.get("source", "voice")))
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


def serve(host="127.0.0.1", port=8787) -> ThreadingHTTPServer:
    hub = Hub()
    srv = ThreadingHTTPServer((host, port), make_handler(hub))
    srv.hub = hub
    return srv


def main(argv=None):
    ap = argparse.ArgumentParser(description="Сервер голосового тренера Dota 2")
    ap.add_argument("--host", default="127.0.0.1",
                    help="0.0.0.0 — чтобы подключался второй компьютер или телефон в той же сети")
    ap.add_argument("--port", type=int, default=8787)
    a = ap.parse_args(argv)
    srv = serve(a.host, a.port)
    print(f"Тренер слушает http://{a.host}:{a.port}/  (Ctrl+C — выход)")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
