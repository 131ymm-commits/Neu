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


class ServerGetWrites(unittest.TestCase):
    """Запись через GET и выдача в <title>: так пишут боты OHA и читает веб-панель кастомки."""

    @classmethod
    def setUpClass(cls):
        cls.srv = serve("127.0.0.1", 0)
        cls.base = f"http://127.0.0.1:{cls.srv.server_address[1]}"
        threading.Thread(target=cls.srv.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()

    def get(self, path):
        with urllib.request.urlopen(self.base + path, timeout=5) as r:
            return r.read().decode("utf-8")

    def test_state_merge_and_events_via_get(self):
        from urllib.parse import quote
        room = "/api/g1"
        # сначала имена (как из файла состава), потом герои от игры — имена не теряются
        call(self.base, "POST", room + "/state", {"team": "radiant", "agents": [
            {"pos": 1, "name": "Вася", "aliases": ["вася"]}]})
        d = quote(json.dumps({"agents": [{"pos": 1, "hero": "npc_dota_hero_pudge"}]}))
        json.loads(self.get(f"{room}/w/state?team=radiant&d={d}"))
        res = json.loads(self.get(f"{room}/log?team=radiant"))
        code, said = call(self.base, "POST", room + "/say", {"team": "radiant", "text": "вася фарми лес"})
        self.assertEqual(said["commands"][0]["agents"], [1])
        code, said = call(self.base, "POST", room + "/say", {"team": "radiant", "text": "пудж фарми лес"})
        self.assertEqual(said["commands"][0]["agents"], [1])     # герой тоже узнаётся
        d = quote(json.dumps({"events": [{"pos": 1, "kind": "ack", "text": "Фармлю"}]}, ensure_ascii=False))
        self.get(f"{room}/w/events?team=radiant&d={d}")
        evs = json.loads(self.get(f"{room}/events?team=radiant&after=0"))["events"]
        self.assertEqual(evs[-1]["text"], "Фармлю")

    def test_commands_in_title(self):
        import html as htmllib
        room = "/api/g2"
        call(self.base, "POST", room + "/say", {"team": "dire", "text": "все на роша"})
        page = self.get(f"{room}/commands?team=dire&after=0&fmt=title")
        title = page.split("<title>", 1)[1].split("</title>", 1)[0]
        data = json.loads(htmllib.unescape(title))
        self.assertEqual(data["commands"][0]["action"], "roshan")
        page = self.get(f"{room}/commands?team=dire&after=0&fmt=title&rid=17")
        title = htmllib.unescape(page.split("<title>", 1)[1].split("</title>", 1)[0])
        rid, body = title.split("|", 1)
        self.assertEqual(rid, "17")
        self.assertEqual(json.loads(body)["commands"][0]["action"], "roshan")


class PushToTalk(unittest.TestCase):
    """Глобальная клавиша: смена состояния → событие ptt странице."""

    @classmethod
    def setUpClass(cls):
        cls.srv = serve("127.0.0.1", 0)
        cls.base = f"http://127.0.0.1:{cls.srv.server_address[1]}"
        threading.Thread(target=cls.srv.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()

    def test_hotkey_sends_only_transitions(self):
        import ptt_hotkey
        states = [False, True, True, True, False, False, True, False]
        sent = []
        it = iter(states)
        ptt_hotkey.run(0x05, sent.append, lambda vk: next(it), sleep=lambda s: None, ticks=len(states))
        self.assertEqual(sent, ["down", "up", "down", "up"])

    def test_ptt_event_reaches_page(self):
        with urllib.request.urlopen(self.base + "/api/p1/ptt?team=dire&state=down", timeout=5) as r:
            self.assertEqual(json.loads(r.read().decode("utf-8")), {"ok": True})
        code, res = call(self.base, "GET", "/api/p1/events?team=dire&after=0")
        self.assertEqual([(e["kind"], e["text"]) for e in res["events"]], [("ptt", "down")])
        code, res = call(self.base, "GET", "/api/p1/ptt?team=dire&state=sideways")
        self.assertEqual(code, 400)
