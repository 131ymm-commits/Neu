"""Сервер тренера: настоящий HTTP на свободном порту, запросы как у игры и клиента."""
import json
import threading
import time
import unittest
import urllib.request

from voicecoach.server import serve


def call(base, method, path, body=None):
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(base + path, data=data, method=method,
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.status, json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode("utf-8"))


class ServerFlow(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.srv = serve("127.0.0.1", 0)
        cls.base = f"http://127.0.0.1:{cls.srv.server_address[1]}"
        cls.th = threading.Thread(target=cls.srv.serve_forever, daemon=True)
        cls.th.start()

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()

    def test_health(self):
        code, res = call(self.base, "GET", "/api/health")
        self.assertEqual(code, 200)
        self.assertTrue(res["ok"])

    def test_say_then_game_polls(self):
        room = "/api/t1"
        # игра сообщает состав: имена и герои → разбор понимает «Миракл»
        code, _ = call(self.base, "POST", room + "/state", {
            "team": "radiant",
            "agents": [{"pos": 1, "name": "Miracle-", "aliases": ["миракл"], "hero": "npc_dota_hero_antimage"},
                       {"pos": 2, "name": "Topson", "aliases": ["топсон"]},
                       {"pos": 3}, {"pos": 4}, {"pos": 5}],
            "enemy_heroes": ["npc_dota_hero_pudge"]})
        self.assertEqual(code, 200)
        code, res = call(self.base, "POST", room + "/say",
                         {"team": "radiant", "text": "Миракл, фарми лес, остальные на Рошана"})
        self.assertEqual(code, 200)
        self.assertEqual([c["action"] for c in res["commands"]], ["farm", "roshan"])
        code, res = call(self.base, "GET", room + "/commands?team=radiant&after=0")
        cmds = res["commands"]
        self.assertEqual([(c["action"], c["agents"]) for c in cmds],
                         [("farm", [1]), ("roshan", [2, 3, 4, 5])])
        self.assertTrue(all(c["v"] == 1 for c in cmds))
        last = cmds[-1]["seq"]
        code, res = call(self.base, "GET", room + f"/commands?team=radiant&after={last}")
        self.assertEqual(res["commands"], [])
        # у второй команды своя очередь
        code, res = call(self.base, "GET", room + "/commands?team=dire&after=0")
        self.assertEqual(res["commands"], [])

    def test_clarify_goes_to_events_not_to_game(self):
        room = "/api/t2"
        code, res = call(self.base, "POST", room + "/say", {"team": "dire", "text": "купи бкб"})
        self.assertEqual(res["commands"][0]["clarify"], "кому?")
        code, res = call(self.base, "GET", room + "/commands?team=dire&after=0")
        self.assertEqual(res["commands"], [])
        code, res = call(self.base, "GET", room + "/events?team=dire&after=0")
        self.assertEqual(res["events"][0]["kind"], "clarify")

    def test_events_long_poll_wakes_up(self):
        room = "/api/t3"
        got = {}

        def waiter():
            got["res"] = call(self.base, "GET", room + "/events?team=radiant&after=0&wait=10")

        th = threading.Thread(target=waiter)
        t0 = time.time()
        th.start()
        time.sleep(0.3)
        call(self.base, "POST", room + "/events",
             {"team": "radiant", "events": [{"pos": 1, "kind": "ack", "text": "Иду в лес"}]})
        th.join(5)
        self.assertLess(time.time() - t0, 5)
        self.assertEqual(got["res"][1]["events"][0]["text"], "Иду в лес")

    def test_bad_team(self):
        code, res = call(self.base, "POST", "/api/t4/say", {"team": "blue", "text": "отходим"})
        self.assertEqual(code, 400)

    def test_page_served(self):
        with urllib.request.urlopen(self.base + "/", timeout=5) as r:
            self.assertIn("Голосовой тренер", r.read().decode("utf-8"))


if __name__ == "__main__":
    unittest.main()
