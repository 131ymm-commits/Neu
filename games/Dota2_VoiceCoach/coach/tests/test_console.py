"""Пульт второго тренера через интернет (решение Д13): ключи, туман войны, приказы с пульта в игру, пределы, туннель.

Сервер тренера и пульт поднимаются по-настоящему (порты 0); игра подменена запросами /tick с наблюдениями обеих
команд. Туннель Cloudflare здесь не запускается: проверяется разбор адреса из журнала cloudflared."""
import io
import json
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.request
from pathlib import Path

from voicecoach import agents as A
from voicecoach import console as C
from voicecoach.server import main, serve


def hero(team, pos, name, xy, enemies=(), missing=(), gold=600, alive=True, **kw):
    o = {"team": team, "pos": pos, "hero": name, "clock": 300, "alive": alive, "lvl": 5, "gold": gold,
         "abilities": [], "items": [{"name": "item_tango", "slot": 0}, {"name": "item_ward_observer", "slot": 6,
                                                                       "backpack": True}],
         "enemy_team": ["sniper", "viper", "axe", "lion", "crystal_maiden"] if team == "dire"
         else ["luna", "lina", "bristleback", "witch_doctor", "jakiro"],
         "enemies": [dict(e) for e in enemies], "missing": [dict(m) for m in missing], "coach": [],
         "events": ["4:50 у них погиб axe"], "stats": {"k": 1, "d": 0, "a": 2}, "doing": "фарм бот"}
    if alive:
        o.update({"hp": [400, 600], "mp": [200, 300], "xy": list(xy), "where": "бот"})
    else:
        o["respawn"] = 12
    o.update(kw)
    return o


MAP = {"towers": [{"team": "radiant", "lane": "mid", "tier": 1, "x": -1500, "y": -1400, "alive": True},
                  {"team": "dire", "lane": "mid", "tier": 1, "x": 500, "y": 650, "alive": False}],
       "fountains": {"radiant": [-7000, -6500], "dire": [7000, 6400]}, "bounds": [-8288, -8288, 8288, 8288],
       "score": {"radiant": 3, "dire": 5}}


def payload(**kw):
    """Обмен игры: Свет видит Луну; Тьма видит Снайпера (виден) и не видит Вайпера; секрет Света — его золото."""
    p = {"clock": 300.0, "map": MAP, "heroes": [
        hero("radiant", 1, "sniper", (100, -6000), gold=7777, enemies=[{"hero": "luna", "lvl": 6, "hp": [300, 900],
                                                                        "xy": [200, -5900], "d": 300}]),
        hero("radiant", 2, "viper", (-300, -300), gold=8888),
        hero("dire", 1, "luna", (200, -5900), enemies=[{"hero": "sniper", "lvl": 5, "hp": [400, 600],
                                                         "xy": [100, -6000], "d": 300, "where": "бот"}],
             missing=[{"hero": "viper", "seen": "мид", "ago": 40}, {"hero": "sniper", "seen": "бот", "ago": 1}]),
        hero("dire", 2, "lina", (0, 0), alive=False),
    ]}
    p.update(kw)
    return p


class Servers(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.srv = serve("127.0.0.1", 0, lambda name: A.AgentHub(
            {"radiant": A.RulesBackend(), "dire": A.RulesBackend()}, sync=True))
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()
        self.keys = C.load_keys(("dire", "radiant"), path=Path(self.tmp.name) / "keys.json")
        self.con = C.serve_console(self.srv.hub, "127.0.0.1", 0, "local", {"dire": self.keys["dire"]})
        threading.Thread(target=self.con.serve_forever, daemon=True).start()
        self.port, self.cport = self.srv.server_address[1], self.con.server_address[1]
        self.room = self.srv.hub.room("local")

    def tearDown(self):
        for s in (self.con, self.srv):
            s.shutdown()
            s.server_close()
        self.tmp.cleanup()

    def tick(self, p):
        req = urllib.request.Request(f"http://127.0.0.1:{self.port}/api/local/tick", method="POST",
                                     data=json.dumps(p).encode("utf-8"))
        return json.loads(urllib.request.urlopen(req, timeout=5).read())

    def get(self, path, key=None):
        key = self.keys["dire"] if key is None else key
        r = urllib.request.urlopen(f"http://127.0.0.1:{self.cport}/c/{key}/{path}", timeout=5)
        return r, r.read()

    def say(self, text, key=None):
        key = self.keys["dire"] if key is None else key
        req = urllib.request.Request(f"http://127.0.0.1:{self.cport}/c/{key}/api/say", method="POST",
                                     data=json.dumps({"text": text}).encode("utf-8"),
                                     headers={"Content-Type": "application/json"})
        return json.loads(urllib.request.urlopen(req, timeout=5).read())

    def status(self, url, data=None, method="GET"):
        req = urllib.request.Request(url, data=data, method=method)
        try:
            return urllib.request.urlopen(req, timeout=5).status
        except urllib.error.HTTPError as e:
            return e.code


class Keys(unittest.TestCase):
    def test_keys_kept_between_runs_and_renewed(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "k.json"
            a = C.load_keys(("dire",), path=path)
            self.assertGreaterEqual(len(a["dire"]), 20)
            self.assertEqual(C.load_keys(("dire",), path=path), a)              # ссылка жива после перезапуска
            b = C.load_keys(("dire", "radiant"), path=path)
            self.assertEqual(b["dire"], a["dire"])
            self.assertNotEqual(b["radiant"], b["dire"])
            self.assertNotEqual(C.load_keys(("dire",), path=path, new=True)["dire"], a["dire"])
        self.assertIn("logs", str(C.KEYS_FILE))                                   # logs/ — в .gitignore


class Names(unittest.TestCase):
    def test_russian_names_in_game_strings(self):
        self.assertEqual(C.ru_names("бой → sniper", ["sniper", "lina"]), "бой → Снайпер")
        self.assertEqual(C.ru_names("21:40 снесли их вышку npc_dota_goodguys_tower1_bot", []),
                         "21:40 снесли их вышку Т1 бот Света")
        self.assertEqual(C.ru_names("за 2 (crystal_maiden)", ["crystal_maiden", "maiden"]), "за 2 (Кристальная Дева)")
        self.assertEqual(C.ru_names("фарм бот", ["axe"]), "фарм бот")


class Access(Servers):
    def test_wrong_key_and_other_paths(self):
        base = f"http://127.0.0.1:{self.cport}"
        for path in ("/", "/c/", "/c/nope/", f"/c/{self.keys['radiant']}/", f"/c/{self.keys['radiant']}/api/view",
                     "/api/local/tick", "/api/local/agents", "/voice.html", f"/c/{self.keys['dire']}/../../etc"):
            self.assertEqual(self.status(base + path), 404, path)               # ключ Света тут не выдан
        self.assertEqual(self.status(base + "/api/local/tick", b"{}", "POST"), 404)
        r = urllib.request.urlopen(base + "/robots.txt", timeout=5)
        self.assertIn(b"Disallow: /", r.read())

    def test_page_and_headers(self):
        r, body = self.get("")
        self.assertIn("Пульт тренера".encode(), body)
        h = r.headers
        self.assertIsNone(h.get("Access-Control-Allow-Origin"))                 # чужие сайты пульт не читают
        self.assertEqual(h["Referrer-Policy"], "no-referrer")
        self.assertIn("noindex", h["X-Robots-Tag"])
        self.assertIn("frame-ancestors 'none'", h["Content-Security-Policy"])
        self.assertEqual(h["Cache-Control"], "no-store")
        r, js = self.get("voices.js")
        self.assertIn(b"speechSynthesis", js)
        req = urllib.request.Request(f"http://127.0.0.1:{self.cport}/c/{self.keys['dire']}", method="GET")
        opener = urllib.request.build_opener(type("NoRedirect", (urllib.request.HTTPRedirectHandler,), {
            "redirect_request": lambda *a, **k: None}))
        try:
            opener.open(req, timeout=5)
            code, loc = 200, None
        except urllib.error.HTTPError as e:
            code, loc = e.code, e.headers.get("Location")
        self.assertEqual((code, loc), (301, f"/c/{self.keys['dire']}/"))


class View(Servers):
    def test_fog_of_war_and_map(self):
        v = json.loads(self.get("api/view")[1])
        self.assertFalse(v["game"]["linked"])                                     # игра ещё не прислала обмен
        self.assertEqual(v["heroes"], [])
        self.tick(payload())
        v = json.loads(self.get("api/view")[1])
        self.assertTrue(v["game"]["linked"])
        self.assertEqual((v["team"], v["team_ru"], v["game"]["clock"]), ("dire", "Тьма", 300.0))
        self.assertEqual([(h["pos"], h["hero"], h["alive"]) for h in v["heroes"]], [(1, "luna", True), (2, "lina", False)])
        self.assertEqual(v["heroes"][0]["xy"], [200, -5900])
        self.assertEqual(v["heroes"][0]["items"], ["item_tango"])                 # рюкзак не показываем
        self.assertEqual(v["heroes"][1]["respawn"], 12)
        self.assertNotIn("xy", v["heroes"][1])
        self.assertEqual([e["hero"] for e in v["enemies"]], ["sniper"])
        self.assertEqual(v["enemies"][0]["hero_ru"], "Снайпер")
        self.assertEqual([m["hero"] for m in v["missing"]], ["viper"])            # видимый не числится пропавшим
        self.assertEqual((v["score"], v["bounds"], len(v["towers"])), (MAP["score"], MAP["bounds"], 2))
        self.assertEqual(v["heroes"][0]["agent"][:5], "решил")                    # состояние агента героя
        self.assertEqual(v["events"], ["4:50 у них погиб Акс"])                   # имена — по-русски
        text = json.dumps(v, ensure_ascii=False)
        for secret in ("7777", "8888", "-300"):                                   # золото и место героев Света
            self.assertNotIn(secret, text)


class Orders(Servers):
    def test_order_reaches_game_exactly_once(self):
        r0 = self.tick(payload())
        self.assertEqual(r0["commands"], [])
        res = self.say("все назад")
        self.assertEqual(res["errors"], [])
        self.assertTrue(res["game_linked"])
        self.assertTrue(res["commands"][0]["human"])
        seq = res["queued"]
        r1 = self.tick(payload(cmd_ack=0, cmd_run=r0["run"]))
        self.assertEqual(r1["commands"], [{"seq": seq, "team": "dire", "text": "все назад"}])
        r2 = self.tick(payload(cmd_ack=0, cmd_run=r0["run"]))                    # ответ потерялся — шлём снова
        self.assertEqual(len(r2["commands"]), 1)
        r3 = self.tick(payload(cmd_ack=seq, cmd_run=r0["run"]))                  # игра применила — больше не шлём
        self.assertEqual(r3["commands"], [])
        r4 = self.tick(payload(cmd_ack=seq, cmd_run="старый запуск"))             # подтверждение прошлого запуска
        self.assertEqual(len(r4["commands"]), 1)
        self.room.remote[-1]["t"] -= 31                                          # пролежал без игры — в новый матч не идёт
        self.assertEqual(self.tick(payload(cmd_ack=0, cmd_run=r0["run"]))["commands"], [])

    def test_bad_order_not_queued(self):
        self.tick(payload())
        res = self.say("фывапро")
        self.assertTrue(res["errors"])
        self.assertNotIn("queued", res)
        self.assertEqual(self.room.remote, [])
        res = self.say("1 ульт снайпер !")                                        # цель — герой из вражеской пятёрки
        self.assertEqual(res["errors"], [])

    def test_limits(self):
        base = f"http://127.0.0.1:{self.cport}/c/{self.keys['dire']}/api/say"
        self.assertEqual(self.status(base, json.dumps({"text": "x" * 3000}).encode(), "POST"), 413)
        self.assertEqual(self.status(base, b"not json", "POST"), 400)
        self.assertEqual(self.status(base, json.dumps({"text": "  \n "}).encode(), "POST"), 400)
        codes = [self.status(base, json.dumps({"text": "все назад"}).encode(), "POST") for _ in range(8)]
        self.assertEqual(codes[:5], [200] * 5)
        self.assertIn(429, codes[5:])                                            # не больше приказа в секунду
        res = self.room.remote_order("dire", "все назад")
        self.assertIn("queued", res)

    def test_replies_go_to_own_console_only(self):
        self.tick(payload(replies=[{"team": "dire", "pos": 0, "hero": "", "kind": "order", "text": "→ 12: все назад"},
                                   {"team": "dire", "pos": 2, "hero": "lina", "kind": "refuse",
                                    "text": "Без агента не умею: смок", "to": "1"},
                                   {"team": "radiant", "pos": 0, "kind": "order", "text": "секрет Света"}]))
        evs = json.loads(self.get("api/events?after=0")[1])["events"]
        self.assertEqual([(e["kind"], e["text"]) for e in evs],
                         [("order", "→ 12: все назад"), ("refuse", "Без агента не умею: смок")])
        self.assertEqual((evs[1]["hero_ru"], evs[1]["to"]), ("Лина", [1]))
        t0 = time.time()
        self.assertEqual(json.loads(self.get(f"api/events?after={evs[-1]['seq']}&wait=0.3")[1])["events"], [])
        self.assertGreaterEqual(time.time() - t0, 0.25)                          # long-poll ждёт

    def test_bad_payload_does_not_break_tick(self):
        r = self.tick({"heroes": [{"team": "dire", "pos": "x"}, "мусор"], "replies": ["x", {"team": "dire"}],
                       "cmd_ack": "x"})
        self.assertIn("decisions", r)


class Tunnel(unittest.TestCase):
    def test_url_from_cloudflared_log(self):
        lines = ["2026-10-08T10:00:00Z INF Requesting new quick Tunnel on trycloudflare.com...\n",
                 'ERR failed to request: Post "https://api.trycloudflare.com/tunnel": EOF\n',
                 "INF +--------------------------------------------------------------------------------------------+\n",
                 "INF |  Your quick Tunnel has been created! Visit it at (it may take some time to be reachable):  |\n",
                 "INF |  https://seasonal-deck-organisms-sf.trycloudflare.com                                     |\n",
                 "INF |  https://other-words-here.trycloudflare.com                                               |\n"]
        seen, got = {}, []

        class P:
            stdout = io.StringIO("".join(lines))

        def popen(argv, **kw):
            seen["argv"] = argv
            return P()

        proc = C.start_tunnel(8788, got.append, "cloudflared", popen=popen, which=lambda n: "/usr/bin/cloudflared")
        deadline = time.time() + 2
        while not got and time.time() < deadline:
            time.sleep(0.01)
        time.sleep(0.05)
        self.assertIsNotNone(proc)
        self.assertEqual(seen["argv"], ["/usr/bin/cloudflared", "tunnel", "--url", "http://127.0.0.1:8788"])
        self.assertEqual(got, ["https://seasonal-deck-organisms-sf.trycloudflare.com"])   # один раз, не api.
        self.assertEqual(C.console_url(got[0], "KEY"), "https://seasonal-deck-organisms-sf.trycloudflare.com/c/KEY/")

        def missing(argv, **kw):
            raise FileNotFoundError

        self.assertIsNone(C.start_tunnel(8788, got.append, popen=missing, which=lambda n: None))

    def test_tunnel_needs_remote(self):
        with self.assertRaises(SystemExit):
            main(["--tunnel"])


if __name__ == "__main__":
    unittest.main()
