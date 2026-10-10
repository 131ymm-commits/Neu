"""Игра вдвоём одним файлом (решение Д14): ящик (шифр, подпись, свежесть), лаунчер хоста, обновлятор, ИГРАТЬ.bat.

Сеть подменена: ntfy — локальный сервер с тем же API (POST /<тема>, GET /<тема>/json?poll=1&since=…), API Anthropic
и GitHub — подставные ответы. Настоящие ntfy.sh, GitHub, cloudflared и Дота здесь не вызываются."""
import hashlib
import io
import json
import os
import re
import tempfile
import threading
import time
import unittest
import urllib.error
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import quote
from unittest import mock

from voicecoach import play as P
from voicecoach import rendezvous as RV
from voicecoach import update as U

GAME = Path(__file__).resolve().parents[2]


class FakeNtfy:
    """Тот же API, что у ntfy.sh, — для тестов (и для браузерного теста файла друга). Отдаёт CORS «*», как ntfy."""

    def __init__(self):
        self.topics: dict[str, list] = {}
        self.queries: list[str] = []
        fake = self

        class H(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def _send(self, code, body=b"", ctype="application/json"):
                self.send_response(code)
                self.send_header("Content-Type", ctype)
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(body)

            def do_POST(self):
                name = self.path.strip("/")
                n = int(self.headers.get("Content-Length") or 0)
                msg = self.rfile.read(n).decode("utf-8")
                fake.topics.setdefault(name, []).append({"id": str(len(fake.topics.get(name, []))),
                                                         "time": int(time.time()), "event": "message",
                                                         "topic": name, "message": msg})
                self._send(200, json.dumps(fake.topics[name][-1]).encode())

            def do_GET(self):
                fake.queries.append(self.path)
                m = re.match(r"^/([\w-]+)/json\?(.*)$", self.path)
                if not m or "poll=1" not in m.group(2):
                    return self._send(404)
                since = re.search(r"since=(\d+)([smh])", m.group(2))         # как ntfy: since=10m — за 10 минут
                cut = time.time() - int(since.group(1)) * {"s": 1, "m": 60, "h": 3600}[since.group(2)] if since else 0
                lines = [json.dumps({"event": "open", "topic": m.group(1)})]
                lines += [json.dumps(x) for x in fake.topics.get(m.group(1), []) if x["time"] >= cut]
                self._send(200, ("\n".join(lines) + "\n").encode(), "application/x-ndjson")

        self.srv = ThreadingHTTPServer(("127.0.0.1", 0), H)
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()
        self.base = f"http://127.0.0.1:{self.srv.server_address[1]}"

    def age(self, name: str, seconds: float) -> None:
        """Состарить сообщения темы: будто их положили seconds секунд назад (по часам ящика)."""
        for x in self.topics.get(name, []):
            x["time"] -= int(seconds)

    def close(self):
        self.srv.shutdown()
        self.srv.server_close()


class Mailbox(unittest.TestCase):
    def test_seal_open_and_forgery(self):
        s = RV.new_secret()
        msg = RV.seal(s, {"url": "https://a-b-c.trycloudflare.com/c/K/", "t": 1000.0})
        self.assertEqual(RV.unseal(s, msg), {"url": "https://a-b-c.trycloudflare.com/c/K/", "t": 1000.0})
        self.assertNotIn("trycloudflare", msg)                                 # ящик ссылку не видит
        self.assertIsNone(RV.unseal(RV.new_secret(), msg))                     # чужой секрет
        ver, n, c, tag = msg.split(".")
        flipped = RV.b64e(bytes([RV.b64d(c)[0] ^ 1]) + RV.b64d(c)[1:])
        self.assertIsNone(RV.unseal(s, ".".join((ver, n, flipped, tag))))      # подменили шифртекст — мимо
        moved = (ver, RV.b64e(RV.b64d(n) + RV.b64d(c)[:1]), RV.b64e(RV.b64d(c)[1:]), tag)
        self.assertIsNone(RV.unseal(s, ".".join(moved)))                       # байт из шифртекста в nonce — мимо
        self.assertIsNone(RV.unseal(s, "vc1.мусор"))
        self.assertIsNone(RV.unseal(s, "привет"))
        name = RV.topic(s)
        self.assertTrue(re.fullmatch(r"dcoach-[A-Za-z0-9_-]{32}", name) and len(name) <= 64, name)
        self.assertEqual(RV.topic(s), name)                                    # из секрета — всегда то же имя

    def test_latest_takes_authentic_newest_without_local_clock(self):
        s, now = RV.new_secret(), 1_000_000.0
        msgs = [RV.seal(s, {"url": "https://old-a.trycloudflare.com/c/K/", "t": now - 100}),
                RV.seal(s, {"url": "https://new-a.trycloudflare.com/c/K/", "t": now + 3600}),   # часы хоста спешат
                RV.seal(RV.new_secret(), {"url": "https://evil-a.trycloudflare.com/c/K/", "t": now + 9999}),
                "не наше"]
        self.assertEqual(RV.latest(s, msgs)["url"], "https://new-a.trycloudflare.com/c/K/")
        self.assertIsNone(RV.latest(s, msgs[2:]))                              # только подделка и мусор
        self.assertTrue(RV.latest(s, msgs + [RV.seal(s, {"closed": True, "t": now + 3601})])["closed"])

    def test_stale_message_is_not_found(self):
        box = FakeNtfy()
        try:
            s = RV.new_secret()
            RV.publish(box.base, RV.topic(s), RV.seal(s, {"url": "https://a-b.trycloudflare.com/c/K/", "t": 1.0}))
            self.assertEqual(RV.latest(s, RV.fetch(box.base, RV.topic(s)))["url"], "https://a-b.trycloudflare.com/c/K/")
            box.age(RV.topic(s), 11 * 60)                                      # хост не повторял ссылку 11 минут
            self.assertIsNone(RV.latest(s, RV.fetch(box.base, RV.topic(s))))  # значит, он не в игре
        finally:
            box.close()

    def test_publisher_through_fake_ntfy(self):
        box = FakeNtfy()
        try:
            s = RV.new_secret()
            seen = []
            pub = RV.Publisher(s, box.base, refresh=0.2, on_result=lambda ok, what: seen.append((ok, what)))
            self.assertTrue(pub.set_url("https://x-y-z.trycloudflare.com/c/K/"))
            time.sleep(0.5)                                                    # повтор, пока игра идёт
            got = RV.latest(s, RV.fetch(box.base, RV.topic(s)))
            self.assertEqual(got["url"], "https://x-y-z.trycloudflare.com/c/K/")
            self.assertEqual(got["fv"], RV.FRIEND_VERSION)                     # файл друга узнает, что устарел
            self.assertGreaterEqual(len(box.topics[RV.topic(s)]), 2)
            self.assertIn("since=10m", box.queries[-1])                        # свежесть считает ящик, не ПК
            self.assertTrue(pub.close())
            self.assertTrue(RV.latest(s, RV.fetch(box.base, RV.topic(s)))["closed"])
            self.assertTrue(all(ok for ok, _ in seen))
            dead = RV.Publisher(s, "http://127.0.0.1:9", on_result=lambda ok, what: seen.append((ok, what)))
            self.assertFalse(dead.set_url("https://q-w-e.trycloudflare.com/c/K/"))   # нет ящика — False, не падение
            dead.close()
        finally:
            box.close()


class FakeResponse(io.BytesIO):
    def __init__(self, data: bytes, headers=None):
        super().__init__(data)
        self.headers = headers or {}
        self.status = 200


def opener_for(routes):
    """urlopen-подмена: адрес (или его начало) → bytes | Exception."""
    calls = []

    def op(req, timeout=None):
        url = req if isinstance(req, str) else req.full_url
        calls.append(req)
        for prefix, out in routes.items():
            if url.startswith(prefix):
                if isinstance(out, Exception):
                    raise out
                return FakeResponse(out, {"Content-Length": str(len(out))})
        raise urllib.error.URLError("нет маршрута " + url)
    op.calls = calls
    return op


class FakeProc:
    def __init__(self, code=None):
        self.code, self.killed = code, False

    def poll(self):
        return self.code

    def terminate(self):
        self.killed = True
        self.code = -15


class Launcher(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.cfg_path = Path(self.tmp.name) / "play.json"
        self.out = []
        self.pages = []
        for name, value in (("CONFIG", self.cfg_path), ("say", self.out.append), ("open_page", self.pages.append)):
            patcher = mock.patch.object(P, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)
        self.addCleanup(self.tmp.cleanup)
        env = mock.patch.dict(os.environ, {}, clear=False)
        env.start()
        self.addCleanup(env.stop)
        os.environ.pop("ANTHROPIC_API_KEY", None)
        for target in ("builtins.input", "getpass.getpass"):                 # забытый ask в тесте — не зависание
            patcher = mock.patch(target, side_effect=EOFError)
            patcher.start()
            self.addCleanup(patcher.stop)

    MODELS = json.dumps({"data": [                                         # поля как у API: id, created_at, …
        {"id": f"x-{P.FAST_LINE}-old", "created_at": "2025-10-01T00:00:00Z"},
        {"id": f"x-{P.FAST_LINE}-new", "created_at": "2026-10-07T00:00:00Z"},
        {"id": "x-big", "created_at": "2026-10-08T00:00:00Z"}]}).encode()
    NEW = f"x-{P.FAST_LINE}-new"

    @staticmethod
    def http_error(code, message=""):
        body = json.dumps({"type": "error", "error": {"type": "x", "message": message}}).encode()
        return urllib.error.HTTPError(P.MODELS_API, code, "x", {}, io.BytesIO(body))

    def test_pick_model_newest_fast(self):
        K = "sk-ant-test-key-0123456789"
        self.assertEqual(P.pick_model(K, opener_for({P.MODELS_API: self.MODELS})), (self.NEW, "", ""))
        model, why, kind = P.pick_model(K, opener_for({P.MODELS_API: self.http_error(401, "invalid x-api-key")}))
        self.assertEqual((model, kind), (None, "key"))
        self.assertIn("invalid x-api-key", why)                                # текст ответа API — хосту
        model, why, kind = P.pick_model(K, opener_for({P.MODELS_API: self.http_error(403, "Request not allowed")}))
        self.assertEqual(kind, "key")
        self.assertIn("HTTP 403: Request not allowed", why)
        self.assertEqual(P.pick_model(K, opener_for({P.MODELS_API: self.http_error(529)}))[2], "net")
        self.assertEqual(P.pick_model(K, opener_for({}))[2], "net")
        self.assertEqual(P.pick_model(K, opener_for({P.MODELS_API: b'{"data": [{"id": "x-big"}]}'}))[2], "none")
        self.assertEqual(P.mask("sk-ant-api03-abcdefghijklmnop"), "sk-ant-…mnop")
        self.assertEqual(P.mask("short"), "…")

    def test_key_choices_are_remembered_only_when_made(self):
        ok = opener_for({P.MODELS_API: self.MODELS})
        never = lambda p: 1 / 0                                               # noqa: E731 — спрашивать нельзя
        no_offer = lambda text: False                                         # noqa: E731
        # пустой Enter — «не сейчас»: ничего не запомнено, в следующий раз спросит снова
        self.assertEqual(P.setup_claude({}, P.parse([]), ask=lambda p: "", opener=ok), (None, None))
        self.assertNotIn("api_key", P.load_config(self.cfg_path))
        # «0» — без Claude, запомнено; при следующем запуске не спрашивает
        self.assertEqual(P.setup_claude({}, P.parse([]), ask=lambda p: "0", opener=ok), (None, None))
        self.assertEqual(P.load_config(self.cfg_path)["api_key"], "")
        self.assertEqual(P.setup_claude(P.load_config(self.cfg_path), P.parse([]), ask=never),
                         (None, None))
        # нажал клавишу при запуске — вводит ключ
        cfg = P.load_config(self.cfg_path)
        self.assertEqual(P.setup_claude(cfg, P.parse(["--ask-key"]), ask=lambda p: " sk-test-key-0123456789 ",
                                        opener=ok), ("sk-test-key-0123456789", self.NEW))
        saved = P.load_config(self.cfg_path)
        self.assertEqual((saved["api_key"], saved["model"]), ("sk-test-key-0123456789", self.NEW))
        self.assertFalse(any("sk-test-key-0123456789" in line for line in self.out))         # ключ на экран не выводится
        # без сети берём прошлую модель; с --rules ключ не нужен
        self.assertEqual(P.setup_claude(saved, P.parse([]), opener=opener_for({})),
                         ("sk-test-key-0123456789", self.NEW))
        self.assertEqual(P.setup_claude(saved, P.parse(["--rules"])), (None, None))
        # сохранённый ключ отозвали — спрашивает новый; Enter — не сейчас
        revoked = opener_for({P.MODELS_API: self.http_error(401, "invalid x-api-key")})
        answers = iter(["sk-new-key-0123456789", ""])
        self.assertEqual(P.setup_claude(dict(saved), P.parse([]), ask=lambda p: next(answers), opener=revoked), (None, None))
        with mock.patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-env-key-0123456789"}):
            self.assertEqual(P.setup_claude({}, P.parse([]), opener=ok)[0], "sk-env-key-0123456789")

    def test_key_without_credit_is_explained(self):
        """Рецензия 3: ключ из организации без кредита принимался, и весь матч стоял на паузе."""
        ok = opener_for({P.MODELS_API: self.MODELS})
        nocredit = lambda key, model, opener: (False, "nocredit")             # noqa: E731
        answers = iter(["sk-no-credit-0123456789", ""])                      # ключ без кредита, потом «не сейчас»
        self.assertEqual(P.setup_claude({}, P.parse([]), ask=lambda p: next(answers), opener=ok, probe=nocredit), (None, None))
        self.assertEqual(P.load_config(self.cfg_path)["api_key"], "sk-no-credit-0123456789")   # ключ сохранён
        self.assertTrue(any("нет кредита" in line for line in self.out))
        self.assertTrue(any("переключите организацию" in line for line in self.out))   # совет и при чужой привязке
        # при следующем запуске — сказать и сразу дать вставить ключ из организации с кредитом
        self.out.clear()
        credit = lambda key, model, opener: (key != "sk-no-credit-0123456789", "" if key != "sk-no-credit-0123456789" else "nocredit")   # noqa: E731
        self.assertEqual(P.setup_claude(P.load_config(self.cfg_path), P.parse([]), ask=lambda p: "sk-with-credit-0123456",
                                        opener=ok, probe=credit),
                         ("sk-with-credit-0123456", self.NEW))
        self.assertTrue(any("нет кредита" in line for line in self.out))
        # проба кредита по-настоящему: 400 «credit balance» → nocredit; 429 — ключ рабочий
        body = b'{"type":"error","error":{"message":"Your credit balance is too low to access the Anthropic API."}}'
        low = urllib.error.HTTPError("u", 400, "x", {}, io.BytesIO(body))
        self.assertEqual(P.probe_key("k", "m", opener_for({"https://api.anthropic.com/v1/messages": low})),
                         (False, "nocredit"))
        busy = urllib.error.HTTPError("u", 429, "x", {}, io.BytesIO(b"{}"))
        self.assertTrue(P.probe_key("k", "m", opener_for({"https://api.anthropic.com/v1/messages": busy}))[0])
        self.assertTrue(P.probe_key("k", "m", opener_for({"https://api.anthropic.com/v1/messages": b"{}"}))[0])

    def test_changing_key_keeps_it_on_empty_enter(self):
        """Рецензия 2: случайная клавиша за 3 с и Enter на вопросе стирали сохранённый ключ."""
        ok = opener_for({P.MODELS_API: self.MODELS})
        P.save_config({"api_key": "sk-saved-key-0123456789", "model": self.NEW})
        cfg = P.load_config(self.cfg_path)
        self.assertEqual(P.setup_claude(cfg, P.parse(["--ask-key"]), ask=lambda p: "", opener=ok),
                         ("sk-saved-key-0123456789", self.NEW))                 # пустой Enter — как было
        self.assertEqual(P.load_config(self.cfg_path)["api_key"], "sk-saved-key-0123456789")
        self.assertEqual(P.setup_claude(cfg, P.parse(["--ask-key"]), ask=lambda p: (_ for _ in ()).throw(KeyboardInterrupt()),
                                        opener=ok)[0], "sk-saved-key-0123456789")   # Ctrl+C
        self.assertEqual(P.setup_claude(cfg, P.parse(["--ask-key"]), ask=lambda p: "0", opener=ok),
                         (None, None))                                          # «0» — выключить Claude
        self.assertEqual(P.load_config(self.cfg_path)["api_key"], "")
        # «без Claude» сохранено; сменить и пустой Enter — так и остаётся без Claude
        self.assertEqual(P.setup_claude(P.load_config(self.cfg_path), P.parse(["--ask-key"]), ask=lambda p: "",
                                        opener=ok), (None, None))

    def test_always_subscription_no_menu(self):
        """Слова автора 10.10.2026: «Не нужно меню с выбиранием системы использования, всегда будет 2»."""
        sub = mock.Mock(return_value="C:/Users/u/.local/bin/claude.exe")
        self.assertEqual(P.setup_agents({}, P.parse([]), subscription=sub), ("sub", "C:/Users/u/.local/bin/claude.exe"))
        sub.assert_called_once()
        self.assertEqual(self.pages, [])                                        # никаких страниц и вопросов
        self.assertEqual(P.setup_agents({"mode": "key", "api_key": "sk-old-key-0123456789"}, P.parse([]),
                                        subscription=sub)[0], "sub")            # прежний выбор ключа — тоже подписка
        self.assertEqual(P.setup_agents({}, P.parse([]), subscription=lambda: None), ("off", None))   # не готов
        self.assertEqual(P.setup_agents({}, P.parse(["--rules"]), subscription=sub), ("off", None))
        # --api — ключ API (на будущее); прежнее «без Claude» ключ не блокирует
        ok = opener_for({P.MODELS_API: self.MODELS})
        self.assertEqual(P.setup_agents({"api_key": ""}, P.parse(["--api"]),
                                        ask_secret=lambda p: "sk-api-key-0123456789", opener=ok, subscription=sub),
                         ("key", ("sk-api-key-0123456789", self.NEW)))

    def test_subscription_setup_installs_and_logs_in(self):
        found = iter([None, "/x/claude"])
        install, login = mock.Mock(return_value=True), mock.Mock(return_value=True)
        states = iter([{"loggedIn": False}, {"loggedIn": True, "authMethod": "claude.ai"}])
        exe = P.setup_subscription(find=lambda: next(found), install=install, auth=lambda e: next(states),
                                   login=login, check=lambda e: (True, ""))
        self.assertEqual(exe, "/x/claude")
        install.assert_called_once()
        login.assert_called_once_with("/x/claude")                           # вход — один раз, браузером
        # уже вошёл — без входа
        login.reset_mock()
        self.assertEqual(P.setup_subscription(find=lambda: "/x/claude", auth=lambda e: {"loggedIn": True},
                                              login=login, check=lambda e: (True, "")), "/x/claude")
        login.assert_not_called()
        # не поставился, не вошёл, не ответил — правила, с причиной на экране
        self.assertIsNone(P.setup_subscription(find=lambda: None, install=lambda: False))
        self.assertIsNone(P.setup_subscription(find=lambda: "/x/claude", auth=lambda e: {"loggedIn": False},
                                               login=lambda e: False))
        self.assertIsNone(P.setup_subscription(find=lambda: "/x/claude", auth=lambda e: {"loggedIn": True},
                                               check=lambda e: (False, "You've hit your session limit")))
        self.assertTrue(any("session limit" in line for line in self.out))
        # Ctrl+C во время установки или входа — пропустить, без трассировки
        def interrupt(*a):
            raise KeyboardInterrupt
        self.assertIsNone(P.setup_subscription(find=lambda: None, install=interrupt))
        self.assertIsNone(P.setup_subscription(find=lambda: "/x/claude", auth=lambda e: {"loggedIn": False},
                                               login=interrupt))
        # старая версия без `auth status` ({}): вход не навязываем, судит пробный вызов
        login.reset_mock()
        self.assertEqual(P.setup_subscription(find=lambda: "/x/claude", auth=lambda e: {}, login=login,
                                              check=lambda e: (True, "")), "/x/claude")
        login.assert_not_called()

    def test_claude_calls_without_api_keys_in_env(self):
        """Документация Claude Code: в режиме -p ключ из окружения берётся раньше подписки — его убираем."""
        seen = []

        def run(argv, **kw):
            seen.append((argv, kw))
            return SimpleNamespace(stdout='{"is_error": false, "result": "готов", "loggedIn": true}', stderr="",
                                   returncode=0)
        with mock.patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-should-not-leak", "ANTHROPIC_AUTH_TOKEN": "t"}):
            self.assertEqual(P.claude_check("c", run=run), (True, ""))
            P.claude_auth("c", run=run)
            P.claude_login("c", run=run)
            from voicecoach.agents import CliBackend
            b = CliBackend(model=P.CLAUDE_FAST, claude="c", runner=run, subscription=True, which=lambda n: None)
        for argv, kw in seen:
            self.assertNotIn("ANTHROPIC_API_KEY", kw["env"])
            self.assertNotIn("ANTHROPIC_AUTH_TOKEN", kw["env"])
        self.assertNotIn("ANTHROPIC_API_KEY", b.env)
        self.assertEqual(seen[0][0][seen[0][0].index("--model") + 1], P.CLAUDE_FAST)   # пробный вызов — быстрой моделью
        self.assertEqual(seen[2][0][1:], ["auth", "login", "--claudeai"])
        ok, why = P.claude_check("c", run=lambda a, **kw: SimpleNamespace(
            stdout='{"is_error": true, "result": "Invalid API key · Please run /login"}', stderr="", returncode=1))
        self.assertEqual((ok, "/login" in why), (False, True))
        self.assertFalse(P.claude_check("c", run=lambda a, **kw: SimpleNamespace(stdout="", stderr="нет", returncode=1))[0])

    def test_find_claude(self):
        home = Path(self.tmp.name)
        (home / ".local" / "bin").mkdir(parents=True)
        (home / ".local" / "bin" / "claude.exe").write_bytes(b"")
        self.assertEqual(P.find_claude(which=lambda n: None, home=home), str(home / ".local" / "bin" / "claude.exe"))
        self.assertEqual(P.find_claude(which=lambda n: "/usr/bin/claude", home=home),
                         str(home / ".local" / "bin" / "claude.exe"))             # родной — раньше PATH
        empty = home / "empty"
        empty.mkdir()
        self.assertEqual(P.find_claude(which=lambda n: "/usr/bin/claude", home=empty), "/usr/bin/claude")
        self.assertIsNone(P.find_claude(which=lambda n: r"C:\npm\claude.CMD", home=empty))   # обёртка npm — нет

    def test_cyrillic_is_not_saved_as_key(self):
        """Рецензия 4: «нет» на вопросе о ключе сохранялось как ключ и давало «нет связи» на каждом запуске."""
        ok = opener_for({P.MODELS_API: self.MODELS})
        answers = iter(["нет", "sk ant api 03 с пробелами 0123", ""])
        self.assertEqual(P.setup_claude({}, P.parse([]), ask=lambda p: next(answers), opener=ok), (None, None))
        self.assertNotIn("api_key", P.load_config(self.cfg_path))
        self.assertTrue(any("не похоже на ключ" in line for line in self.out))
        # и сохранённая раньше кириллица — «ключ не подошёл», а не «нет связи»: лаунчер спросит новый
        self.assertEqual(P.pick_model("ключ", opener_for({}))[2], "key")

    def test_friend_version_same_in_python_and_js(self):
        """Разные версии в rendezvous.py и rv.js — свежий файл друга вечно просил бы новый."""
        js = (P.WEB / "rv.js").read_text(encoding="utf-8")
        self.assertEqual(int(re.search(r"FRIEND_VERSION:\s*(\d+)", js).group(1)), RV.FRIEND_VERSION)

    def test_key_failures_do_not_turn_claude_off(self):
        # Ctrl+C на вопросе — ничего не запоминаем
        def ctrl_c(prompt):
            raise KeyboardInterrupt
        cfg = {}
        self.assertEqual(P.setup_claude(cfg, P.parse([]), ask=ctrl_c, opener=opener_for({})), (None, None))
        self.assertNotIn("api_key", P.load_config(self.cfg_path))
        # нет сети при вводе — ключ сохранён, в этот раз правила, в следующий — Claude
        self.assertEqual(P.setup_claude({}, P.parse([]), ask=lambda p: "sk-later-key-01234567", opener=opener_for({})), (None, None))
        saved = P.load_config(self.cfg_path)
        self.assertEqual(saved["api_key"], "sk-later-key-01234567")
        self.assertEqual(P.setup_claude(saved, P.parse([]), opener=opener_for({P.MODELS_API: self.MODELS})), ("sk-later-key-01234567", self.NEW))
        # три неверных ключа — правила, но «без Claude» не запоминается
        bad = opener_for({P.MODELS_API: self.http_error(401)})
        self.cfg_path.unlink()
        self.assertEqual(P.setup_claude({}, P.parse([]), ask=lambda p: "sk-bad-key-0123456789", opener=bad), (None, None))
        self.assertNotIn("api_key", P.load_config(self.cfg_path))
        self.assertIsNone(P._ask(lambda p: (_ for _ in ()).throw(EOFError()), "?"))   # окно без ввода

    def test_friend_file(self):
        path = Path(self.tmp.name) / "ДЛЯ_ДРУГА.html"
        P.make_friend_file(path, "SECRET123", "https://ntfy.example")
        html = path.read_text(encoding="utf-8")
        self.assertNotIn("__SECRET__", html)
        self.assertNotIn("__RV_BASE__", html)
        self.assertNotIn("/*__RV_JS__*/", html)
        self.assertIn("'SECRET123'", html)
        self.assertIn("root.Rendezvous", html)                                   # код ящика встроен
        self.assertIn("<noscript>", html)                                        # без скриптов — объяснение

    def test_running_reads_console_bytes(self):
        """Блокер рецензии Д14: русская tasklist пишет в cp866 — разбор текстом в UTF-8 падал."""
        def run_with(out):
            def run(argv, **kw):                     # как subprocess.run: с text=True или encoding — строгое декодирование
                if kw.get("text") or kw.get("encoding"):
                    return SimpleNamespace(stdout=out.decode(kw.get("encoding") or "utf-8"), returncode=0)
                return SimpleNamespace(stdout=out, returncode=0)
            return run
        found = '"dota2.exe","1234","Console","1","1 234 567 КБ"\r\n'.encode("cp866")
        none = "ИНФОРМАЦИЯ: Задачи, отвечающие заданным критериям, отсутствуют.\r\n".encode("cp866")
        self.assertTrue(P._running("dota2.exe", run=run_with(found)))
        self.assertFalse(P._running("dota2.exe", run=run_with(none)))
        self.assertFalse(P._running("steam.exe", run=run_with(found)))
        self.assertFalse(P._running("dota2.exe", run=lambda argv, **kw: (_ for _ in ()).throw(ValueError("x"))))
        with self.assertRaises(UnicodeDecodeError):                            # так падал прежний код
            found.decode("utf-8")

    def test_install_skipped_while_dota_open(self):
        dota = Path(self.tmp.name) / "dota 2 beta"
        mod = SimpleNamespace(install=mock.Mock(side_effect=PermissionError("занят")))
        with mock.patch.object(P, "_install_module", return_value=mod):
            self.assertIn("не обновляю", P.install_custom_game(dota, running=lambda n: n == "dota2.exe"))
            mod.install.assert_not_called()
            self.assertIn("Не установил: занят", P.install_custom_game(dota, running=lambda n: False))

    def test_dota_launch(self):
        dota = Path(self.tmp.name) / "dota 2 beta"
        win64 = dota / "game" / "bin" / "win64"
        win64.mkdir(parents=True)
        (win64 / "dota2.exe").write_bytes(b"")
        argv = P.dota_argv(dota)
        self.assertEqual(argv[1:], ["-novid", "-tools", "-addon", "voicecoach", "-condebug",
                                    "+dota_launch_custom_game", "voicecoach", "dota"])
        started = []
        msg = P.launch_dota(dota, popen=lambda a, **kw: started.append((a, kw)), running=lambda name: False,
                            wait=lambda s: None)
        self.assertEqual(started, [])                  # первый живой запуск: без Workshop Tools Steam даёт ошибку —
        self.assertIn("Dota 2 Workshop Tools DLC", msg)  # Доту не запускаем, а говорим, что поставить
        (win64 / "resourcecompiler.exe").write_bytes(b"")
        msg = P.launch_dota(dota, popen=lambda a, **kw: started.append((a, kw)), running=lambda name: False,
                            wait=lambda s: None)
        self.assertEqual(started[0][0], argv)
        self.assertEqual(started[0][1]["cwd"], str(win64))
        self.assertIn("вы тренер Света", msg)
        started.clear()
        msg = P.launch_dota(dota, popen=lambda a, **kw: started.append(a), running=lambda name: name == "dota2.exe")
        self.assertEqual(started, [])
        self.assertIn("dota_launch_custom_game voicecoach dota", msg)            # Дота уже открыта — не дублируем
        msg = P.launch_dota(dota, popen=mock.Mock(side_effect=OSError("нет доступа")), running=lambda n: False,
                            wait=lambda s: None)
        self.assertIn("Не запустил Доту: нет доступа", msg)

    def test_dota_starts_by_itself_when_tools_arrive(self):
        """Рецензия 5: без Workshop Tools лаунчер говорил «запустите снова», а второе окно — «уже запущена».
        Теперь окно ждёт, пока Steam докачает дополнение, и запускает Доту само."""
        dota = Path(self.tmp.name) / "dota 2 beta"
        checks, launched = iter([False, False, True]), []
        stop = threading.Event()
        P.launch_when_tools(dota, stop, lambda: launched.append(1) or "пуск", has=lambda d: next(checks),
                            period=0.0, settle=0.0)
        self.assertEqual(launched, [1])
        self.assertTrue(any("Workshop Tools на месте" in x for x in self.out))
        stop.set()                                                               # закрыли окно — не запускать
        P.launch_when_tools(dota, stop, lambda: 1 / 0, has=lambda d: True, period=0.0)
        # игра уже на связи (хост запустил Доту сам) — ждать нечего, напоминаний нет
        self.out.clear()
        P.launch_when_tools(dota, threading.Event(), lambda: 1 / 0, has=lambda d: False, linked=lambda: True,
                            period=0.0, remind=0.0)
        self.assertEqual(self.out, [])
        # напоминание, что окно не зависло
        n = iter(range(30))
        stop2 = threading.Event()
        P.launch_when_tools(dota, stop2, lambda: "пуск", has=lambda d: next(n) >= 25, period=0.001, settle=0.0,
                            remind=0.002)
        self.assertTrue(any("Окно не зависло" in x for x in self.out))

    def test_starter_no_double_launch_and_retry_after_failure(self):
        """Рецензия 6: «д» во время закачки гасил ожидание; два пути могли запустить Доту дважды."""
        dota = Path(self.tmp.name) / "dota 2 beta"
        results = iter(["Нет бесплатного дополнения…", "Дота запускается с кастомкой", "Дота запускается снова"])
        launched, running = [], [False]

        def launch(d, force=False):
            launched.append(force)
            return next(results)
        st = P.DotaStarter(dota, launch=launch, running=lambda name: running[0])
        self.assertTrue(st.start(force=True).startswith("Нет"))                  # «д» раньше времени — не вышло
        self.assertFalse(st.started)
        self.assertTrue(st.start().startswith("Дота запускается"))               # дополнение пришло — запуск
        running[0] = True
        self.assertIn("уже запущена", st.start(force=True))                      # «д» после запуска — ответ
        self.assertEqual(launched, [True, False])
        # под замком: два потока сразу — один запуск
        calls = []
        st2 = P.DotaStarter(dota, launch=lambda d, force=False: (calls.append(1), time.sleep(0.05),
                                                                 "Дота запускается")[-1], running=lambda n: True)
        ts = [threading.Thread(target=st2.start) for _ in range(2)]
        for x in ts:
            x.start()
        for x in ts:
            x.join()
        self.assertEqual(len(calls), 1)

    def test_wait_enter_d_launches_without_ending_game(self):
        got, stop = [], threading.Event()
        answers = iter(["д", "", "l", "", ""])
        P.wait_enter(stop, ask=lambda p: next(answers), on_word=lambda: got.append(1), clock=lambda: 0.0)
        self.assertEqual(got, [1, 1])                                            # «д» и «l» (английская раскладка)
        self.assertTrue(stop.is_set())                                           # два Enter подряд — конец

    def test_main_waits_for_tools_instead_of_failing(self):
        tmp = Path(self.tmp.name)
        dota = tmp / "dota 2 beta"
        (dota / "game" / "bin" / "win64").mkdir(parents=True)
        (dota / "game" / "bin" / "win64" / "dota2.exe").write_bytes(b"")
        box = FakeNtfy()
        patches = [mock.patch.object(P, "GAME_PORT", 0), mock.patch.object(P, "CONSOLE_PORT", 0),
                   mock.patch.object(P, "PROJECT", tmp), mock.patch.object(P, "already_running", lambda: False),
                   mock.patch.object(P, "load_keys", lambda teams, new=False: {"dire": "k" * 22}),
                   mock.patch.object(P, "reveal", lambda path: None), mock.patch.object(P, "LOGS", tmp / "logs"),
                   mock.patch.object(P, "find_dota", lambda *a, **k: dota),
                   mock.patch.object(P, "install_custom_game", lambda d: "Установлена"),
                   mock.patch.object(P, "launch_dota", mock.Mock(side_effect=AssertionError("рано")))]
        for x in patches:
            x.start()
            self.addCleanup(x.stop)
        try:
            self.assertEqual(P.main(["--rules", "--no-tunnel", "--rv", box.base], enter=lambda p: ""), 0)
        finally:
            box.close()
        text = "\n".join(self.out)
        self.assertIn("Внимание: нет дополнения Dota 2 Workshop Tools", text)      # совет — уже на шаге [2/6]
        self.assertIn("Жду дополнение Workshop Tools", text)
        self.assertNotIn("запустите ИГРАТЬ.bat снова", text)

    def test_cloudflared_found_downloaded_and_checked(self):
        self.assertEqual(P.ensure_cloudflared(which=lambda n: "/usr/bin/cloudflared"), "/usr/bin/cloudflared")
        rt = Path(self.tmp.name) / "rt"
        with mock.patch.object(P, "RUNTIME", rt):
            exe = P.ensure_cloudflared(opener=opener_for({P.CLOUDFLARED_URL: b"x" * 1_500_000}),
                                       which=lambda n: None, windows=True, check=lambda e: True)
            self.assertTrue(exe.endswith("cloudflared.exe"))
            self.assertEqual(Path(exe).stat().st_size, 1_500_000)
            self.assertEqual(P.ensure_cloudflared(opener=opener_for({}), which=lambda n: None, windows=True,
                                                  check=lambda e: True), exe)
            # свой файл не запускается — удалить и скачать заново
            fresh = P.ensure_cloudflared(opener=opener_for({P.CLOUDFLARED_URL: b"y" * 10}), which=lambda n: None,
                                         windows=True, check=lambda e: Path(e).read_bytes() == b"y" * 10)
            self.assertEqual(Path(fresh).read_bytes(), b"y" * 10)
            # скачанный не запускается — ошибка, файла нет
            Path(fresh).unlink()
            with self.assertRaises(OSError):
                P.ensure_cloudflared(opener=opener_for({P.CLOUDFLARED_URL: b"z"}), which=lambda n: None,
                                     windows=True, check=lambda e: False)
            self.assertFalse(Path(fresh).exists())

    def test_download_rejects_truncated(self):
        """Сервер обещал 3 МБ, отдал 1,5 МБ: прежний код принимал файл навсегда."""
        def short(url, timeout=None):
            return FakeResponse(b"x" * 1_500_000, {"Content-Length": "3000000"})
        dest = Path(self.tmp.name) / "cf.exe"
        with self.assertRaises(OSError):
            P.download("u", dest, opener=short)
        self.assertFalse(dest.exists())
        self.assertFalse(dest.with_name("cf.exe.part").exists())

    def test_already_running(self):
        class H(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def do_GET(self):
                body = b'{"ok": true, "rooms": 1}'
                self.send_response(200)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
        srv = ThreadingHTTPServer(("127.0.0.1", 0), H)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        try:
            with mock.patch.object(P, "HEALTH", f"http://127.0.0.1:{srv.server_address[1]}/api/health"):
                self.assertTrue(P.already_running())
        finally:
            srv.shutdown()
            srv.server_close()
        with mock.patch.object(P, "HEALTH", "http://127.0.0.1:9/api/health"):
            self.assertFalse(P.already_running())

    def test_exclusive_port(self):
        """На Windows второй сервер не должен встать на тот же порт (SO_REUSEADDR это позволяет)."""
        import socket
        from voicecoach.console import ExclusiveServer
        a = ExclusiveServer(("127.0.0.1", 0), BaseHTTPRequestHandler)
        try:
            with self.assertRaises(OSError):
                ExclusiveServer(("127.0.0.1", a.server_address[1]), BaseHTTPRequestHandler)
        finally:
            a.server_close()
        # путь Windows: без SO_REUSEADDR (он отдаёт порт второму процессу) и без SO_EXCLUSIVEADDRUSE (с ним порт
        # не отпускают, пока живы соединения прежнего окна); здесь Linux — опции сокета записываем
        win = type("Win", (ExclusiveServer,), {"exclusive": True})
        srv = win(("127.0.0.1", 0), BaseHTTPRequestHandler, bind_and_activate=False)
        real, opts = srv.socket, []
        srv.socket = mock.Mock(wraps=real)
        srv.socket.setsockopt.side_effect = lambda *a: opts.append(a)
        try:
            srv.server_bind()
            self.assertFalse(any(o[1] == socket.SO_REUSEADDR for o in opts), opts)
            self.assertEqual(opts, [])
        finally:
            real.close()

    def test_tunnel_keeper_restarts(self):
        procs, urls = [], []

        def start(port, on_url, cf, on_error=None, on_exit=None):
            proc = FakeProc()
            procs.append(proc)
            on_url(f"https://n{len(procs)}-a.trycloudflare.com")
            return proc
        keeper = P.TunnelKeeper(8788, urls.append, "cf", start=start, period=0.01, backoff=0.01)
        self.assertTrue(keeper.start())
        procs[0].code = 1                                                      # cloudflared упал
        deadline = time.time() + 10
        while len(procs) < 2 and time.time() < deadline:
            time.sleep(0.01)
        keeper.stop.set()
        self.assertGreaterEqual(len(procs), 2)
        self.assertEqual(urls[:2], ["https://n1-a.trycloudflare.com", "https://n2-a.trycloudflare.com"])
        keeper.close()
        self.assertTrue(procs[-1].killed)
        self.assertFalse(P.TunnelKeeper(1, urls.append, "cf", start=lambda *a, **k: None).start())

    def test_wait_enter_needs_two_enters(self):
        """Рецензия 2: Enter, нажатый заранее (во время закачки), сразу заканчивал игру."""
        def answers(*times):
            seq = iter(times)
            clock = SimpleNamespace(t=0.0)

            def ask(prompt):
                t = next(seq, None)
                if t is None:
                    raise EOFError
                clock.t = t
                return ""
            return ask, (lambda: clock.t)
        stop = threading.Event()
        ask, clock = answers(0.0)                                              # один Enter — игра идёт
        P.wait_enter(stop, ask=ask, clock=clock)
        self.assertFalse(stop.is_set())
        ask, clock = answers(0.0, 9.0)                                         # второй — слишком поздно
        P.wait_enter(stop, ask=ask, clock=clock)
        self.assertFalse(stop.is_set())
        ask, clock = answers(0.0, 9.0, 11.0)                                   # два подряд — конец
        P.wait_enter(stop, ask=ask, clock=clock)
        self.assertTrue(stop.is_set())
        self.assertIn("Enter ещё раз", self.out[0])

    def test_bind_waits_for_port_or_reports(self):
        tries = iter([OSError("busy"), OSError("busy"), "server"])

        def make():
            x = next(tries)
            if isinstance(x, Exception):
                raise x
            return x
        self.assertEqual(P.bind(make, 8787, "серверу", wait=lambda s: None, ours=lambda: False), "server")
        self.assertIsNone(P.bind(lambda: (_ for _ in ()).throw(OSError("busy")), 8787, "серверу",
                                 wait=lambda s: None, ours=lambda: True))
        self.assertTrue(any("уже запущена" in x for x in self.out[-2:]))         # второе окно — не «чужая программа»
        self.assertIsNone(P.bind(lambda: (_ for _ in ()).throw(OSError("busy")), 8788, "пульту",
                                 tries=3, wait=lambda s: None))
        self.assertIn("занят другой программой", self.out[-1])

    def test_tunnel_keeper_close_during_restart(self):
        """Рецензия 2: закрыли во время перезапуска — новый cloudflared оставался жить."""
        procs = []
        keeper = None

        def start(port, on_url, cf, on_error=None, on_exit=None):
            proc = FakeProc()
            procs.append(proc)
            if len(procs) == 2:
                keeper.stop.set()                                              # хост закрыл окно, пока запускали
            return proc
        keeper = P.TunnelKeeper(8788, lambda u: None, "cf", start=start, period=0.01, backoff=0.0)
        self.assertTrue(keeper.start())
        procs[0].code = 1
        deadline = time.time() + 10
        while not (len(procs) == 2 and procs[1].killed) and time.time() < deadline:
            time.sleep(0.01)
        self.assertTrue(procs[1].killed)

    def test_watch_reports_changes(self):
        room = SimpleNamespace(console_seen={}, game_linked=lambda: False)
        ticks = iter(range(3))

        def stop():
            n = next(ticks, None)
            if n == 1:
                room.console_seen["dire"] = time.time()
                room.game_linked = lambda: True
            return n is None

        P.watch(room, stop=stop, sleep=lambda s: None)
        self.assertEqual(self.out, ["  ● Друг открыл пульт.", "  ● Игра на связи с сервером тренера."])

    def test_main_runs_and_ends_on_enter(self):
        """Весь лаунчер без Доты и туннеля: сервер, пульт, файл друга; Enter — конец, ящик получает «закрыто»."""
        box = FakeNtfy()
        tmp = Path(self.tmp.name)
        keys = {"dire": "k" * 22}
        patches = [mock.patch.object(P, "GAME_PORT", 0), mock.patch.object(P, "CONSOLE_PORT", 0),
                   mock.patch.object(P, "PROJECT", tmp), mock.patch.object(P, "already_running", lambda: False),
                   mock.patch.object(P, "load_keys", lambda teams, new=False: keys),
                   mock.patch.object(P, "reveal", lambda path: None), mock.patch.object(P, "LOGS", tmp / "logs"),
                   mock.patch.object(P, "find_dota", lambda *a, **k: None)]
        for x in patches:
            x.start()
            self.addCleanup(x.stop)
        try:
            gate = threading.Event()
            code = P.main(["--rules", "--no-dota", "--no-tunnel", "--rv", box.base],
                          enter=lambda p: gate.wait(0.5) or "")
            self.assertEqual(code, 0)
            text = "\n".join(self.out)
            for need in ("[1/6]", "[3/6]", "[5/6]", "Без туннеля", "ОДИН раз", "Заканчиваю"):
                self.assertIn(need, text)
            self.assertTrue((tmp / P.FRIEND_FILE).exists())
            cfg = P.load_config(self.cfg_path)
            self.assertEqual(cfg["friend_version"], RV.FRIEND_VERSION)
            last = RV.latest(cfg["secret"], RV.fetch(box.base, RV.topic(cfg["secret"])))
            self.assertTrue(last["closed"])                                    # друг узнает, что игра закрыта
            # второй запуск того же хоста: файл другу заново не нужен
            self.out.clear()
            self.assertEqual(P.main(["--rules", "--no-dota", "--no-tunnel", "--rv", box.base],
                                    enter=lambda p: ""), 0)
            self.assertIn("уже получал", "\n".join(self.out))
        finally:
            box.close()
        with mock.patch.object(P, "already_running", lambda: True):
            self.out.clear()
            self.assertEqual(P.main(["--rules"]), 1)
            self.assertTrue(any("уже запущена" in x for x in self.out[-2:]))


class Updater(unittest.TestCase):
    REL = "a" * 40
    TREE_SHA = "b" * 40

    def routes(self, files, release=None, branch=U.BRANCH):
        """Подставной GitHub: RELEASE на ветке, список папки games/, дерево папки игры, файлы выпуска."""
        tree = {"tree": [{"path": k, "type": "blob", "sha": U.blob_sha(v)} for k, v in files.items()]
                + [{"path": "coach", "type": "tree", "sha": "c" * 40}], "truncated": False}
        listing = [{"name": "Dota2_VoiceCoach", "type": "dir", "sha": self.TREE_SHA},
                   {"name": "Other", "type": "dir", "sha": "d" * 40}]
        r = {U.RAW + branch + "/" + quote(U.PREFIX + U.RELEASE): ((release or self.REL) + "\n").encode(),
             f"{U.API}/contents/games?ref={self.REL}": json.dumps(listing).encode(),
             f"{U.API}/git/trees/{self.TREE_SHA}?recursive=1": json.dumps(tree).encode()}
        for k, v in files.items():
            r[U.RAW + self.REL + "/" + quote(U.PREFIX + k)] = v
        return r

    FILES = {"coach/play.py": b"print(1)\n", "game/a.lua": b"x = 1\n", "coach/tests/t.py": b"skip\n",
             "docs/x.md": b"skip\n", "ИГРАТЬ.bat": b"@echo off\r\n"}

    def test_sync_release_only_changed_and_checks(self):
        routes = self.routes(self.FILES)
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp)
            (dest / "game").mkdir()
            (dest / "game" / "a.lua").write_bytes(b"x = 1\n")                 # уже свежий
            op = opener_for(routes)
            n, total, sha = U.sync(dest, opener=op, log=lambda s: None, workers=2)
            self.assertEqual((n, total, sha), (2, 3, self.REL))               # play.py и ИГРАТЬ.bat; тесты и docs — мимо
            self.assertEqual((dest / "coach" / "play.py").read_bytes(), b"print(1)\n")
            self.assertTrue((dest / "ИГРАТЬ.bat").exists())
            self.assertFalse((dest / "coach" / "tests").exists())
            self.assertEqual(U.sync(dest, opener=op, log=lambda s: None)[0], 0)  # второй раз — нечего качать
            urls = [c if isinstance(c, str) else c.full_url for c in op.calls]
            self.assertFalse(any("/git/trees/" + U.BRANCH in u for u in urls))   # не всё дерево ветки
        self.assertEqual(U.blob_sha(b"hello\n"), "ce013625030ba8dba906f756967f9e9ca394464a")   # как git hash-object

    def test_sync_is_all_or_nothing(self):
        """Один файл скачался не тем — не заменён ни один (прежний код менял часть файлов и говорил «обновлено»)."""
        routes = self.routes(self.FILES)
        routes[U.RAW + self.REL + "/" + quote(U.PREFIX + "game/a.lua")] = b"x = 2\n"     # не тот хеш
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp)
            (dest / "coach").mkdir()
            (dest / "coach" / "play.py").write_bytes(b"old")
            with self.assertRaises(OSError):
                U.sync(dest, opener=opener_for(routes), log=lambda s: None)
            self.assertEqual((dest / "coach" / "play.py").read_bytes(), b"old")
            self.assertFalse((dest / "ИГРАТЬ.bat").exists())
            self.assertEqual(list(dest.rglob("*.part")), [])

    def test_failed_replace_leaves_no_part_files(self):
        """Файл заняли насовсем: обновление падает, недописанные .part не остаются (рецензия 3: не было теста)."""
        routes = self.routes(self.FILES)
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(U, "replace",
                                                                     side_effect=PermissionError("занят")):
            dest = Path(tmp)
            with self.assertRaises(PermissionError):
                U.sync(dest, opener=opener_for(routes), log=lambda s: None)
            self.assertEqual(list(dest.rglob("*.part")), [])

    def test_release_falls_back_to_main_and_checks_format(self):
        routes = self.routes(self.FILES, branch="main")
        routes[U.RAW + U.BRANCH + "/" + quote(U.PREFIX + U.RELEASE)] = urllib.error.HTTPError(
            "u", 404, "Not Found", {}, io.BytesIO(b""))                        # ветку слили или удалили
        self.assertEqual(U.release(opener_for(routes)), self.REL)
        routes = self.routes(self.FILES, release="не хеш")
        with self.assertRaises(ValueError):
            U.release(opener_for(routes))

    def test_truncated_response_is_an_error(self):
        def short(req, timeout=None):
            return FakeResponse(b"abc", {"Content-Length": "10"})
        with self.assertRaises(OSError):
            U._get("https://example.invalid/x", short, wait=lambda s: None)

    def test_get_retries_dropped_connections_not_404(self):
        """Живая проверка 09.10: из 65 файлов один оборвался (SSL EOF) — и без повтора отменилась вся установка."""
        calls = []

        def flaky(req, timeout=None):
            calls.append(req)
            if len(calls) < 3:
                raise urllib.error.URLError("EOF occurred in violation of protocol")
            return FakeResponse(b"data", {"Content-Length": "4"})
        self.assertEqual(U._get("https://example.invalid/x", flaky, wait=lambda s: None), b"data")
        self.assertEqual(len(calls), 3)
        calls.clear()

        def missing(req, timeout=None):
            calls.append(req)
            raise urllib.error.HTTPError("u", 404, "Not Found", {}, io.BytesIO(b""))
        with self.assertRaises(urllib.error.HTTPError):
            U._get("https://example.invalid/x", missing, wait=lambda s: None)
        self.assertEqual(len(calls), 1)                                        # 404 не повторяем

    def test_no_release_is_not_blamed_on_internet(self):
        with tempfile.TemporaryDirectory() as tmp, mock.patch("builtins.print") as out:
            with mock.patch.object(U, "sync", side_effect=U.NoRelease("нет RELEASE")):
                self.assertEqual(U.main([tmp]), 1)
            text = " ".join(str(c.args[0]) for c in out.call_args_list)
            self.assertIn("выпуск ещё не готов", text)
            self.assertNotIn("интернет", text)

    def test_replace_retries_locked_file(self):
        """Антивирус или OneDrive держат файл: замена повторяется, а не бросает обновление на полпути."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path, dest = Path(tmp) / "a.part", Path(tmp) / "a"
            tmp_path.write_bytes(b"new")
            real, calls = Path.replace, []

            def flaky(self_, target):
                calls.append(1)
                if len(calls) < 3:
                    raise PermissionError("занят")
                return real(self_, target)
            with mock.patch.object(Path, "replace", flaky):
                U.replace(tmp_path, dest, wait=lambda s: None)
            self.assertEqual(dest.read_bytes(), b"new")
            self.assertEqual(len(calls), 3)

    def test_main_plays_on_old_files_after_any_failure(self):
        import http.client
        with tempfile.TemporaryDirectory() as tmp, mock.patch("builtins.print"):
            for err in (urllib.error.URLError("нет сети"), http.client.IncompleteRead(b"x", 5)):
                with mock.patch.object(U, "sync", side_effect=err):
                    self.assertEqual(U.main([tmp]), 1)                         # файлов нет — ошибка
            (Path(tmp) / "coach" / "voicecoach").mkdir(parents=True)
            (Path(tmp) / "coach" / "voicecoach" / "play.py").write_text("")
            for err in (urllib.error.URLError("нет сети"), http.client.IncompleteRead(b"x", 5)):
                with mock.patch.object(U, "sync", side_effect=err):
                    self.assertEqual(U.main([tmp]), 0)                         # есть — играем на них


class BatchFile(unittest.TestCase):
    def test_bat_is_plain_and_complete(self):
        raw = (GAME / "ИГРАТЬ.bat").read_bytes()
        self.assertTrue(all(b < 128 for b in raw))                             # cmd.exe читает в кодировке консоли
        self.assertNotIn(b"\n", raw.replace(b"\r\n", b""))                     # переводы строк Windows
        text = raw.decode("ascii")
        for need in ("python-3.12.10-embed-amd64.zip", r"coach\voicecoach\update.py", r"coach\play.py",
                     "131ymm-commits/Neu/" + U.BRANCH, "131ymm-commits/Neu/main/", "import ssl", "pause"):
            self.assertIn(need, text)
        lines = text.splitlines()
        for line in lines:
            if line.strip().lower().startswith("echo"):                       # скобки в echo ломают блоки cmd
                self.assertNotRegex(line, r"[()]", line)
            if line.startswith("%PS%"):                                        # пути — через $env: «&», «^», «'» в пути
                self.assertRegex(line, r'^%PS% "[^"]*"$', line)                # не ломают ни cmd, ни PowerShell
                self.assertNotRegex(line, r"%(HERE|PROJ|RT)%", line)
        # обновление и запуск — одной строкой, которая кончается выходом: обновлённый .bat cmd уже не дочитывает
        runs = [x for x in lines if r'"%PROJ%coach\play.py"' in x]
        self.assertEqual(len(runs), 2, runs)                                   # копия с GitHub и копия git
        for x in runs:
            self.assertTrue(x.endswith("& pause & exit /b"), x)
        self.assertIn(r'update.py" "%PROJ%." && ', runs[0])
        self.assertIn("pull --ff-only", runs[1])
        self.assertEqual(lines[lines.index(":run_update") + 1], runs[0])
        for bad in ("Invoke-WebRequest", "Expand-Archive", "Move-Item", "-OutFile"):   # пути-шаблоны: «[» в пути
            self.assertNotIn(bad, text)
        boot = next(x for x in lines if "update.py" in x and x.startswith("%PS%"))
        self.assertIn("/RELEASE", boot)                                        # первая загрузка — из выпуска
        self.assertNotIn("call ", text)              # трамплин на копию bat из папки игры убран (рецензия 3: call и ^, %)
        self.assertEqual(hashlib.sha1(b"blob 0\0").hexdigest(), U.blob_sha(b""))


if __name__ == "__main__":
    unittest.main()
