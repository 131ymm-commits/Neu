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
from unittest import mock

from voicecoach import play as P
from voicecoach import rendezvous as RV
from voicecoach import update as U

GAME = Path(__file__).resolve().parents[2]


class FakeNtfy:
    """Тот же API, что у ntfy.sh, — для тестов (и для браузерного теста файла друга). Отдаёт CORS «*», как ntfy."""

    def __init__(self):
        self.topics: dict[str, list] = {}
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
                m = re.match(r"^/([\w-]+)/json\?(.*)$", self.path)
                if not m or "poll=1" not in m.group(2):
                    return self._send(404)
                lines = [json.dumps({"event": "open", "topic": m.group(1)})]
                lines += [json.dumps(x) for x in fake.topics.get(m.group(1), [])]
                self._send(200, ("\n".join(lines) + "\n").encode(), "application/x-ndjson")

        self.srv = ThreadingHTTPServer(("127.0.0.1", 0), H)
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()
        self.base = f"http://127.0.0.1:{self.srv.server_address[1]}"

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
        self.assertIsNone(RV.unseal(s, "vc1.мусор"))
        self.assertIsNone(RV.unseal(s, "привет"))
        name = RV.topic(s)
        self.assertTrue(re.fullmatch(r"dcoach-[A-Za-z0-9_-]{32}", name) and len(name) <= 64, name)
        self.assertEqual(RV.topic(s), name)                                    # из секрета — всегда то же имя

    def test_latest_takes_fresh_authentic_newest(self):
        s, now = RV.new_secret(), 1_000_000.0
        msgs = [RV.seal(s, {"url": "https://old-a.trycloudflare.com/c/K/", "t": now - 100}),
                RV.seal(s, {"url": "https://new-a.trycloudflare.com/c/K/", "t": now - 10}),
                RV.seal(RV.new_secret(), {"url": "https://evil-a.trycloudflare.com/c/K/", "t": now}),   # подделка
                RV.seal(s, {"url": "https://stale-a.trycloudflare.com/c/K/", "t": now - RV.MAX_AGE - 1}),
                "не наше"]
        self.assertEqual(RV.latest(s, msgs, now)["url"], "https://new-a.trycloudflare.com/c/K/")
        self.assertIsNone(RV.latest(s, msgs[3:], now))
        self.assertTrue(RV.latest(s, msgs + [RV.seal(s, {"closed": True, "t": now - 1})], now)["closed"])

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
            self.assertGreaterEqual(len(box.topics[RV.topic(s)]), 2)
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


class Launcher(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.cfg_path = Path(self.tmp.name) / "play.json"
        for name, value in (("CONFIG", self.cfg_path), ("say", lambda text="": None)):
            patcher = mock.patch.object(P, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)
        self.addCleanup(self.tmp.cleanup)
        env = mock.patch.dict(os.environ, {}, clear=False)
        env.start()
        self.addCleanup(env.stop)
        os.environ.pop("ANTHROPIC_API_KEY", None)

    MODELS = json.dumps({"data": [
        {"id": "fast-old", "line": P.FAST_LINE, "created_at": "2025-10-01T00:00:00Z"},
        {"id": "fast-new", "line": P.FAST_LINE, "created_at": "2026-10-07T00:00:00Z"},
        {"id": "big", "line": "other", "created_at": "2026-10-08T00:00:00Z"}]}).encode()

    def test_pick_model_newest_fast(self):
        model, why = P.pick_model("k", opener_for({P.MODELS_API: self.MODELS}))
        self.assertEqual((model, why), ("fast-new", ""))
        bad = urllib.error.HTTPError(P.MODELS_API, 401, "x", {}, io.BytesIO(b"{}"))
        self.assertEqual(P.pick_model("k", opener_for({P.MODELS_API: bad})), (None, "ключ не подошёл"))
        self.assertIn("нет связи", P.pick_model("k", opener_for({}))[1])

    def test_key_asked_once_and_remembered(self):
        args = P.parse([])
        answers = iter(["", ""])
        cfg = {}
        self.assertEqual(P.setup_claude(cfg, args, ask=lambda p: next(answers)), (None, None))
        self.assertEqual(P.load_config(self.cfg_path)["api_key"], "")             # «без Claude» запомнено
        self.assertEqual(P.setup_claude(P.load_config(self.cfg_path), args, ask=lambda p: 1 / 0), (None, None))
        cfg = {}
        key, model = P.setup_claude(cfg, P.parse(["--ask-key"]), ask=lambda p: "sk-test",
                                    opener=opener_for({P.MODELS_API: self.MODELS}))
        self.assertEqual((key, model), ("sk-test", "fast-new"))
        saved = P.load_config(self.cfg_path)
        self.assertEqual((saved["api_key"], saved["model"]), ("sk-test", "fast-new"))
        # без сети берём прошлую модель; с --rules ключ не нужен
        self.assertEqual(P.setup_claude(saved, P.parse([]), opener=opener_for({})), ("sk-test", "fast-new"))
        self.assertEqual(P.setup_claude(saved, P.parse(["--rules"])), (None, None))
        with mock.patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-env"}):
            self.assertEqual(P.setup_claude({}, P.parse([]), opener=opener_for({P.MODELS_API: self.MODELS}))[0],
                             "sk-env")
        self.assertEqual(P._ask(lambda p: (_ for _ in ()).throw(EOFError()), "?"), "")   # окно без ввода

    def test_friend_file(self):
        path = Path(self.tmp.name) / "ДЛЯ_ДРУГА.html"
        P.make_friend_file(path, "SECRET123", "https://ntfy.example")
        html = path.read_text(encoding="utf-8")
        self.assertNotIn("__SECRET__", html)
        self.assertNotIn("__RV_BASE__", html)
        self.assertNotIn("/*__RV_JS__*/", html)
        self.assertIn("'SECRET123'", html)
        self.assertIn("root.Rendezvous", html)                                   # код ящика встроен

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
        self.assertEqual(started[0][0], argv)
        self.assertEqual(started[0][1]["cwd"], str(win64))
        self.assertIn("Workshop Tools", msg)                                     # подсказка: инструментов не видно
        started.clear()
        msg = P.launch_dota(dota, popen=lambda a, **kw: started.append(a), running=lambda name: name == "dota2.exe")
        self.assertEqual(started, [])
        self.assertIn("dota_launch_custom_game voicecoach dota", msg)            # Дота уже открыта — не дублируем

    def test_cloudflared_found_or_downloaded(self):
        self.assertEqual(P.ensure_cloudflared(which=lambda n: "/usr/bin/cloudflared"), "/usr/bin/cloudflared")
        with mock.patch.object(P, "RUNTIME", Path(self.tmp.name) / "rt"):
            exe = P.ensure_cloudflared(opener=opener_for({P.CLOUDFLARED_URL: b"x" * 1_500_000}),
                                       which=lambda n: None, windows=True)
            self.assertTrue(exe.endswith("cloudflared.exe"))
            self.assertEqual(Path(exe).stat().st_size, 1_500_000)
            self.assertEqual(P.ensure_cloudflared(opener=opener_for({}), which=lambda n: None, windows=True), exe)

    def test_watch_reports_changes(self):
        room = SimpleNamespace(console_seen={}, game_linked=lambda: False)
        out, ticks = [], iter(range(3))

        def stop():
            n = next(ticks, None)
            if n == 1:
                room.console_seen["dire"] = time.time()
                room.game_linked = lambda: True
            return n is None

        with mock.patch.object(P, "say", out.append):                       # поверх тихого say из setUp
            P.watch(room, stop=stop, sleep=lambda s: None)
        self.assertEqual(out, ["  ● Друг открыл пульт.", "  ● Игра на связи с сервером тренера."])


class Updater(unittest.TestCase):
    def test_sync_downloads_only_changed_and_checks(self):
        files = {"coach/play.py": b"print(1)\n", "game/a.lua": b"x = 1\n", "coach/tests/t.py": b"skip\n",
                 "docs/x.md": b"skip\n", "ИГРАТЬ.bat": b"@echo off\r\n"}
        tree = {"tree": [{"path": U.PREFIX + k, "type": "blob", "sha": U.blob_sha(v)} for k, v in files.items()]
                + [{"path": "README.md", "type": "blob", "sha": "0"}]}
        routes = {U.API: json.dumps(tree).encode()}
        for k, v in files.items():
            routes[U.RAW + __import__("urllib.parse").parse.quote(U.PREFIX + k)] = v
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp)
            (dest / "game").mkdir()
            (dest / "game" / "a.lua").write_bytes(b"x = 1\n")                  # уже свежий
            op = opener_for(routes)
            n, total = U.sync(dest, opener=op, log=lambda s: None, workers=2)
            self.assertEqual((n, total), (2, 3))                               # play.py и ИГРАТЬ.bat; тесты и docs — мимо
            self.assertEqual((dest / "coach" / "play.py").read_bytes(), b"print(1)\n")
            self.assertTrue((dest / "ИГРАТЬ.bat").exists())
            self.assertFalse((dest / "coach" / "tests").exists())
            self.assertEqual(U.sync(dest, opener=op, log=lambda s: None)[0], 0)  # второй раз — нечего качать
            routes[U.RAW + __import__("urllib.parse").parse.quote(U.PREFIX + "coach/play.py")] = b"print(2)\n"
            (dest / "coach" / "play.py").write_bytes(b"old")
            with self.assertRaises(OSError):                                   # скачалось не то — не пишем
                U.sync(dest, opener=opener_for(routes), log=lambda s: None)
            self.assertEqual((dest / "coach" / "play.py").read_bytes(), b"old")
        self.assertEqual(U.blob_sha(b"hello\n"), "ce013625030ba8dba906f756967f9e9ca394464a")   # как git hash-object

    def test_main_offline(self):
        with tempfile.TemporaryDirectory() as tmp, mock.patch("builtins.print"):
            with mock.patch.object(U, "sync", side_effect=urllib.error.URLError("нет сети")):
                self.assertEqual(U.main([tmp]), 1)                             # файлов нет — ошибка
                (Path(tmp) / "coach" / "voicecoach").mkdir(parents=True)
                (Path(tmp) / "coach" / "voicecoach" / "play.py").write_text("")
                self.assertEqual(U.main([tmp]), 0)                             # есть — играем на них


class BatchFile(unittest.TestCase):
    def test_bat_is_plain_and_complete(self):
        raw = (GAME / "ИГРАТЬ.bat").read_bytes()
        self.assertTrue(all(b < 128 for b in raw))                             # cmd.exe читает в кодировке консоли
        self.assertNotIn(b"\n", raw.replace(b"\r\n", b""))                     # переводы строк Windows
        text = raw.decode("ascii")
        for need in ("python-3.12.10-embed-amd64.zip", r"coach\voicecoach\update.py", r"coach\play.py",
                     "131ymm-commits/Neu/" + U.BRANCH, "pause"):
            self.assertIn(need, text)
        for line in text.splitlines():                                         # скобки в echo ломают блоки cmd
            if line.strip().lower().startswith("echo"):
                self.assertNotRegex(line, r"[()]", line)
        self.assertEqual(hashlib.sha1(b"blob 0\0").hexdigest(), U.blob_sha(b""))


if __name__ == "__main__":
    unittest.main()
