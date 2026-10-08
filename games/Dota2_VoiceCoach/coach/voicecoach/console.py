"""Пульт второго тренера через интернет (решение Д13; слова автора 08.10.2026: «А зделай программу чтобы в неё мог
подключатся второй игрок со стороны через интернет»).

Второй тренер не входит в матч Доты: к игре, запущенной из Tools, никто не подключится (research/00_SUMMARY.md).
Он открывает в браузере ссылку с ключом и командует своей пятёркой с пульта: схема карты, свои герои, видимые враги,
приказы коротким форматом, голосовой чат своих агентов. Пульт — отдельный порт сервера тренера (по умолчанию 8788),
на нём только страница пульта и пути API, все — под ключом команды:

  GET  /c/<ключ>/                        страница пульта (web/console.html)
  GET  /c/<ключ>/voices.js               голоса агентов (как у voice.html)
  GET  /c/<ключ>/api/view                что видит команда: часы, счёт, свои герои, видимые враги, вышки
  GET  /c/<ключ>/api/events?after=N&wait=20   реплики агентов и ответы игры своей команде (long-poll)
  POST /c/<ключ>/api/say   {"text": …}   приказ коротким форматом → игре в ответе на её /tick

Ключ определяет команду: с ключом Тьмы виден только обзор Тьмы (наблюдения её героев), и приказы идут только её
агентам. Порт игры (8787) наружу не выставляется. В интернет пульт выводит туннель Cloudflare (`--tunnel`:
`cloudflared tunnel --url http://127.0.0.1:8788`, адрес https://….trycloudflare.com) или проброс порта.
"""
from __future__ import annotations

import hmac
import json
import os
import re
import secrets
import shutil
import socket
import subprocess
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from .agents import hero_ru

TEAMS = ("radiant", "dire")
TEAM_RU = {"radiant": "Свет", "dire": "Тьма"}
WEB = Path(__file__).resolve().parent.parent / "web"
KEYS_FILE = Path(__file__).resolve().parent.parent / "logs" / "console_keys.json"   # logs/ — вне git
FILES = {"voices.js": "application/javascript; charset=utf-8", "console.js": "application/javascript; charset=utf-8"}
MAX_BODY = 2048           # байт в запросе приказа
MAX_TEXT = 200            # знаков в приказе
WAIT_MAX = 25.0           # с: long-poll событий (у туннеля Cloudflare свой предел ожидания — держимся ниже)
RATE = (4.0, 0.5)         # приказов: запас 4, дальше один в 2 с — поток приказов не множит вызовы агентов
SOCKET_TIMEOUT = 10.0     # с: недосланный запрос не держит поток вечно
MAX_CONN = 32             # одновременных соединений с пультом (у тренера — 2–3 на вкладку)
TUNNEL_WAIT = 40.0        # с: не дождались адреса туннеля — сказать хосту
# адрес быстрого туннеля: несколько слов через дефис (служебный api.trycloudflare.com — не он)
TUNNEL_RE = re.compile(r"https://[a-z0-9]+(?:-[a-z0-9]+)+\.trycloudflare\.com", re.I)
CSP = ("default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; "
       "connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'")


def _int(v, default: int = 0) -> int:
    try:
        return int(v)
    except (TypeError, ValueError):
        return default


def load_keys(teams, path: Path = KEYS_FILE, new: bool = False) -> dict:
    """Ключи пультов: {команда: ключ}. Хранятся в logs/console_keys.json, чтобы ссылка жила после перезапуска
    сервера; new=True — выдать новые (старые ссылки перестанут работать)."""
    data = {}
    if not new and path.exists():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            data = {}
    keys = {}
    for t in teams:
        k = data.get(t)
        keys[t] = k if isinstance(k, str) and len(k) >= 20 else secrets.token_urlsafe(16)
    data = {t: k for t, k in data.items() if t in TEAMS and isinstance(k, str)}
    data.update(keys)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf-8")
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass
    return keys


TOWER_RE = re.compile(r"npc_dota_(goodguys|badguys)_tower(\d)_(top|mid|bot)")
STAMP_RE = re.compile(r"^(-?)(\d+):(\d\d)\s")
PERSONAL_RE = re.compile(r"\b(тебя|ты)\b")


def _stamp(event: str) -> float:
    m = STAMP_RE.match(event)
    if not m:
        return -1e9
    t = int(m.group(2)) * 60 + int(m.group(3))
    return -t if m.group(1) else t
LANE_RU = {"top": "топ", "mid": "мид", "bot": "бот"}


def ru_names(text: str, heroes) -> str:
    """Имена в строках игры — по-русски: «бой → sniper» → «бой → Снайпер», вышка npc_dota_…_tower1_bot → «Т1 бот Света»."""
    text = TOWER_RE.sub(lambda m: f"Т{m.group(2)} {LANE_RU[m.group(3)]} "
                                  f"{'Света' if m.group(1) == 'goodguys' else 'Тьмы'}", str(text))
    for name in sorted({h for h in heroes if h}, key=len, reverse=True):
        text = re.sub(rf"(?<![a-z_]){re.escape(name)}(?![a-z_])", hero_ru(name), text)
    return text


def team_view(room, team: str) -> dict:
    """Что видит команда: только наблюдения её героев (туман войны — как у неё в игре) и общее для всех —
    вышки, фонтаны, счёт. Наблюдения другой команды сюда не попадают."""
    with room.lock:
        payload, t = room.last_tick or {}, room.last_tick_t
    mine = sorted((o for o in payload.get("heroes") or [] if isinstance(o, dict) and o.get("team") == team),
                  key=lambda o: _int(o.get("pos")))
    states, backend = {}, ""
    hub = room.agents
    if hub is not None:
        with hub.lock:
            states = {pos: ag.state for (tm, pos), ag in hub.agents.items() if tm == team}
        b = hub.backends.get(team)
        backend = getattr(b, "label", str(b)) if b is not None else ""
    heroes, enemies, missing, events = [], {}, {}, []
    names = {str(o.get("hero") or "") for o in mine}
    for o in mine:
        names |= {str(h) for h in o.get("enemy_team") or [] if isinstance(h, str)}
    for o in mine:
        pos, name = _int(o.get("pos")), str(o.get("hero") or "")
        row = {"pos": pos, "hero": name, "hero_ru": hero_ru(name), "lvl": o.get("lvl"), "alive": bool(o.get("alive")),
               "gold": o.get("gold"), "doing": ru_names(o.get("doing") or "", names), "agent": states.get(pos, ""),
               "items": [i.get("name") for i in o.get("items") or [] if isinstance(i, dict) and not i.get("backpack")],
               "stats": o.get("stats") or {}}
        if row["alive"]:
            row.update({"hp": o.get("hp"), "mp": o.get("mp"), "xy": o.get("xy"), "where": o.get("where")})
        else:
            row["respawn"] = o.get("respawn")
        heroes.append(row)
        for e in o.get("enemies") or []:
            if isinstance(e, dict) and e.get("hero") and e["hero"] not in enemies:
                enemies[e["hero"]] = {"hero": e["hero"], "hero_ru": hero_ru(e["hero"]), "lvl": e.get("lvl"),
                                      "hp": e.get("hp"), "xy": e.get("xy"), "where": e.get("where")}
        for m in o.get("missing") or []:
            if isinstance(m, dict) and m.get("hero") and m["hero"] not in missing:
                missing[m["hero"]] = {"hero": m["hero"], "hero_ru": hero_ru(m["hero"]), "seen": m.get("seen"),
                                      "ago": m.get("ago"), "dead": bool(m.get("dead"))}
        for ev in o.get("events") or []:
            if not isinstance(ev, str):
                continue
            ev = ru_names(ev, names)
            if PERSONAL_RE.search(ev):                   # «тебя убил …» — у каждого героя своё: подписать героем
                m = STAMP_RE.match(ev)
                cut = m.end() if m else 0
                ev = f"{ev[:cut]}{row['hero_ru']}: {ev[cut:]}"
            if ev not in events:
                events.append(ev)
    m = payload.get("map") if isinstance(payload.get("map"), dict) else {}
    return {"team": team, "team_ru": TEAM_RU.get(team, team), "backend": backend,
            "game": {"linked": room.game_linked(), "clock": payload.get("clock"),
                     "ago_s": round(time.time() - t, 1) if t else None},
            "heroes": heroes, "enemies": list(enemies.values()),
            "missing": [x for n, x in missing.items() if n not in enemies],
            "towers": m.get("towers") or [], "fountains": m.get("fountains") or {}, "bounds": m.get("bounds"),
            "score": m.get("score"), "events": sorted(events, key=_stamp)[-8:]}


def make_console_handler(hub, room_name: str, keys: dict, rate=RATE, socket_timeout: float = SOCKET_TIMEOUT):
    by_key = [(k.encode("utf-8"), t) for t, k in keys.items()]
    buckets: dict[str, tuple[float, float]] = {}
    guard = threading.Lock()

    def team_for(key: str) -> str | None:
        found = None
        for k, t in by_key:                                   # сравнение без утечки по времени
            if hmac.compare_digest(k, key.encode("utf-8")):
                found = t
        return found

    def allow(key: str) -> bool:
        cap, refill = rate
        now = time.monotonic()
        with guard:
            tokens, last = buckets.get(key, (cap, now))
            tokens = min(cap, tokens + (now - last) * refill)
            ok = tokens >= 1
            buckets[key] = (tokens - 1 if ok else tokens, now)
        return ok

    class Handler(BaseHTTPRequestHandler):
        server_version = "VoiceCoach"
        sys_version = ""
        timeout = socket_timeout                        # недосланный запрос не держит поток (long-poll ждёт не сокет)

        def log_message(self, fmt, *args):
            pass

        def _send(self, code: int, obj=None, ctype="application/json; charset=utf-8", raw: bytes | None = None,
                  extra: dict | None = None):
            body = raw if raw is not None else json.dumps(obj, ensure_ascii=False).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Referrer-Policy", "no-referrer")          # ключ из адреса никуда не уходит
            self.send_header("X-Robots-Tag", "noindex, nofollow")       # страницы туннелей попадают в поиск
            self.send_header("X-Frame-Options", "DENY")
            if ctype.startswith("text/html"):
                self.send_header("Content-Security-Policy", CSP)
            for k, v in (extra or {}).items():
                self.send_header(k, v)
            self.end_headers()
            try:
                self.wfile.write(body)
            except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
                pass                                    # браузер ушёл, не дождавшись (long-poll, закрыли вкладку)

        def _parse(self):
            u = urlparse(self.path)
            parts = [p for p in u.path.split("/") if p]
            q = {k: v[0] for k, v in parse_qs(u.query).items()}
            if len(parts) < 2 or parts[0] != "c":
                return None, "", [], q, u.path
            return team_for(parts[1]), parts[1], parts[2:], q, u.path

        def do_GET(self):
            team, key, rest, q, path = self._parse()
            if path == "/robots.txt":                   # страницу поисковик видит и читает «noindex»; API — нет
                return self._send(200, raw=b"User-agent: *\nDisallow: /c/*/api/\n", ctype="text/plain; charset=utf-8")
            if path == "/favicon.ico":
                return self._send(204, raw=b"", ctype="image/x-icon")
            if team is None:
                return self._send(404, {"error": "нет такой страницы"})
            room = hub.room(room_name)
            if not rest:
                if not path.endswith("/"):                  # относительные пути страницы — от «/c/<ключ>/»
                    return self._send(301, raw=b"", ctype="text/plain", extra={"Location": f"/c/{key}/"})
                return self._send(200, raw=(WEB / "console.html").read_bytes(), ctype="text/html; charset=utf-8")
            if len(rest) == 1 and rest[0] in FILES:
                return self._send(200, raw=(WEB / rest[0]).read_bytes(), ctype=FILES[rest[0]])
            if rest == ["api", "view"]:
                return self._send(200, team_view(room, team))
            if rest == ["api", "events"]:
                try:
                    wait = min(max(float(q.get("wait", 0)), 0.0), WAIT_MAX)
                except ValueError:
                    wait = 0.0
                return self._send(200, {"events": room.events_after(team, _int(q.get("after")), wait), "run": room.run})
            return self._send(404, {"error": "нет такой страницы"})

        def do_POST(self):
            team, key, rest, q, path = self._parse()
            if team is None or rest != ["api", "say"]:
                return self._send(404, {"error": "нет такой страницы"})
            n = _int(self.headers.get("Content-Length"), -1)
            if n <= 0 or n > MAX_BODY:
                return self._send(413 if n > MAX_BODY else 400, {"error": "пустой или слишком длинный запрос"})
            try:
                body = json.loads(self.rfile.read(n).decode("utf-8"))
            except (ValueError, UnicodeDecodeError):
                return self._send(400, {"error": "нужен JSON {\"text\": …}"})
            text = "".join(ch for ch in str((body or {}).get("text") or "") if ch.isprintable()).strip()[:MAX_TEXT]
            if not text:
                return self._send(400, {"error": "пустой приказ"})
            if not allow(key):
                return self._send(429, {"error": "слишком часто: не больше приказа в секунду"})
            return self._send(200, hub.room(room_name).remote_order(team, text))

    return Handler


class ConsoleServer(ThreadingHTTPServer):
    """Сервер пульта: не больше max_conn соединений сразу — лишние закрываются, не заводя поток."""
    max_conn = MAX_CONN

    def server_activate(self):
        self.slots = threading.BoundedSemaphore(self.max_conn)
        super().server_activate()

    def process_request(self, request, client_address):
        if not self.slots.acquire(blocking=False):
            self.shutdown_request(request)
            return
        try:
            super().process_request(request, client_address)
        except Exception:
            self.slots.release()
            raise

    def process_request_thread(self, request, client_address):
        try:
            super().process_request_thread(request, client_address)
        finally:
            self.slots.release()


def serve_console(hub, host: str = "127.0.0.1", port: int = 8788, room: str = "local", keys: dict | None = None,
                  max_conn: int = MAX_CONN, socket_timeout: float = SOCKET_TIMEOUT):
    attrs = {"max_conn": max_conn}
    if ":" in host:                                       # адрес IPv6
        attrs["address_family"] = socket.AF_INET6
    cls = type("ConsoleServerOn", (ConsoleServer,), attrs)
    srv = cls((host, port), make_console_handler(hub, room, keys or {}, socket_timeout=socket_timeout))
    srv.keys = dict(keys or {})
    return srv


def console_url(base: str, key: str) -> str:
    return f"{base.rstrip('/')}/c/{key}/"


def start_tunnel(port: int, on_url, cloudflared: str = "cloudflared", popen=subprocess.Popen, which=shutil.which,
                 on_error=None, wait: float = TUNNEL_WAIT):
    """Быстрый туннель Cloudflare (без учётной записи): `cloudflared tunnel --url http://127.0.0.1:<порт>`.
    Адрес https://….trycloudflare.com cloudflared пишет в журнал при запуске — on_url(адрес) зовётся один раз.
    Адрес случайный и меняется при каждом запуске; гарантий работы Cloudflare не даёт (тестовый режим).
    Ошибки cloudflared (строки ERR), его выход и «адреса нет за wait секунд» — в on_error. Нет cloudflared — None."""
    on_error = on_error or (lambda msg: print(msg, flush=True))
    exe = which(cloudflared) or cloudflared
    try:
        proc = popen([exe, "tunnel", "--url", f"http://127.0.0.1:{port}"], stdout=subprocess.PIPE,
                     stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL, text=True, encoding="utf-8",
                     errors="replace")
    except (FileNotFoundError, PermissionError, OSError):
        return None
    got = threading.Event()

    def reader():
        errors = 0
        for line in proc.stdout:                       # читаем до конца, иначе cloudflared упрётся в полную трубу
            m = TUNNEL_RE.search(line)
            if m and not got.is_set():
                got.set()
                on_url(m.group(0))
            elif " ERR " in line and errors < 5:
                errors += 1
                on_error("cloudflared: " + line.strip()[:300])
        code = proc.wait() if hasattr(proc, "wait") else None
        on_error(f"Туннель закрыт: cloudflared завершился (код {code}). Ссылка через интернет больше не работает."
                 if got.is_set() else f"Туннель не поднялся: cloudflared завершился (код {code}) — строки выше.")

    def watchdog():
        if not got.wait(wait):
            on_error(f"Туннель: за {wait:.0f} с cloudflared не дал адреса — проверьте интернет и строки cloudflared.")

    threading.Thread(target=reader, daemon=True, name="tunnel").start()
    threading.Thread(target=watchdog, daemon=True, name="tunnel-wait").start()
    return proc
