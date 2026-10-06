"""Сквозной тест без Доты: фраза тренера → сервер (настоящий HTTP) → мост на Lua (LuaJIT)
→ намерения агентов → желания режимов. HTTP в Lua подменён вызовом из Python (urllib):
в игре его делает CreateHTTPRequestScriptVM."""
import json
import sys
import threading
import unittest
import urllib.error
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
GAME = HERE.parent
sys.path.insert(0, str(GAME.parent / "coach"))

try:
    from lupa import luajit21 as lupa_rt
except ImportError:                      # pragma: no cover
    from lupa import lua51 as lupa_rt

from voicecoach.server import serve  # noqa: E402


def lua_module(L, name):
    return L.execute((GAME / "shared" / f"{name}.lua").read_text(encoding="utf-8"))


class BridgeEndToEnd(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.srv = serve("127.0.0.1", 0)
        cls.base = f"http://127.0.0.1:{cls.srv.server_address[1]}"
        threading.Thread(target=cls.srv.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()

    def setUp(self):
        self.L = lupa_rt.LuaRuntime(unpack_returned_tuples=True)
        self.json = lua_module(self.L, "json")
        self.Intents = lua_module(self.L, "coach_intents")
        self.Bridge = lua_module(self.L, "coach_bridge")
        self.t = [0.0]
        self.logs = []

    def py_http(self, method, url, body, cb):
        data = body.encode("utf-8") if body is not None else None
        req = urllib.request.Request(url, data=data, method=method,
                                     headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=5) as r:
                cb(r.status, r.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            cb(e.code, e.read().decode("utf-8"))
        except OSError:
            cb(0, None)

    def make_bridge(self, room, base=None, on_command=None):
        opts = self.L.table_from({
            "base_url": base or self.base, "room": room,
            "http": self.py_http, "now": lambda: self.t[0], "json": self.json,
            "log": self.logs.append,
        })
        if on_command:
            opts["on_command"] = on_command
        return self.Bridge.new(opts)

    def say(self, room, team, text):
        req = urllib.request.Request(f"{self.base}/api/{room}/say", method="POST",
                                     data=json.dumps({"team": team, "text": text}).encode("utf-8"),
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=5) as r:
            return json.loads(r.read().decode("utf-8"))

    def test_voice_to_desire(self):
        st = {"radiant": self.Intents.new(), "dire": self.Intents.new()}
        got = []

        def on_command(team, cmd):
            got.append((team, cmd.action))
            self.Intents.apply(st[team], cmd, self.t[0])

        b = self.make_bridge("e2e", on_command=on_command)
        # игра сообщает состав (как будет делать в матче)
        agents = self.L.table_from([
            self.L.table_from({"pos": 1, "name": "Miracle-", "aliases": self.L.table_from(["миракл"]),
                               "hero": "npc_dota_hero_antimage"}),
            self.L.table_from({"pos": 2, "name": "Topson", "aliases": self.L.table_from(["топсон"])}),
        ])
        self.Bridge.push_state(b, "radiant", agents, self.L.table_from(["npc_dota_hero_pudge"]))
        self.say("e2e", "radiant", "Миракл, фарми лес, остальные на Рошана")
        self.say("e2e", "dire", "все назад")
        self.Bridge.tick(b)
        self.assertEqual(got, [("radiant", "farm"), ("radiant", "roshan"), ("dire", "retreat")])
        I = self.Intents
        self.assertGreaterEqual(I.desire(st["radiant"], 1, "farm", 0.1, 1), 0.75)
        self.assertGreaterEqual(I.desire(st["radiant"], 3, "roshan", 0.1, 1), 0.9)
        self.assertGreaterEqual(I.desire(st["dire"], 4, "retreat", 0.0, 1), 0.95)
        # повторный опрос не дублирует
        self.Bridge.tick(b)
        self.assertEqual(len(got), 3)
        self.assertTrue(b.connected)

    def test_agent_reply_reaches_events(self):
        b = self.make_bridge("e2e_events")
        self.Bridge.say(b, "radiant", 1, "ack", "Иду в лес")
        self.Bridge.tick(b)
        with urllib.request.urlopen(f"{self.base}/api/e2e_events/events?team=radiant&after=0", timeout=5) as r:
            evs = json.loads(r.read().decode("utf-8"))["events"]
        self.assertEqual([(e["pos"], e["text"]) for e in evs], [(1, "Иду в лес")])

    def test_server_down_backoff(self):
        b = self.make_bridge("down", base="http://127.0.0.1:9")    # порт 9 — никто не слушает
        self.Bridge.tick(b)
        self.assertFalse(b.connected)
        self.assertEqual(b.fail_count, 1)
        first_next = b.next_try
        self.Bridge.tick(b)                     # раньше срока — не стучимся
        self.assertEqual(b.fail_count, 1)
        self.t[0] = first_next + 0.01
        self.Bridge.tick(b)
        self.assertEqual(b.fail_count, 2)
        self.assertTrue(any("нет связи" in str(l) for l in self.logs))


if __name__ == "__main__":
    unittest.main()
