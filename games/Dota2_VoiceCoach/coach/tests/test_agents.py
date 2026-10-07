"""Агенты героев (решение Д11): разбор ответа модели, промпты, расписание решений, моторы, путь /tick.

Модель здесь не вызывается: моторы api и cli проверяются на подменённых HTTP и процессе — что уходит
в API и в `claude -p` и как разбирается ответ. Настоящий вызов — на ПК автора (журнал агентов)."""
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
from voicecoach.server import serve


def obs(clock=0.0, pos=1, team="radiant", alive=True, hp=(500, 500), coach=(), enemies=(), **kw):
    o = {"team": team, "pos": pos, "hero": "sniper", "clock": clock, "alive": alive, "lvl": 3, "gold": 600,
         "abilities": [{"name": "sniper_shrapnel", "lvl": 1, "use": "point", "ready": True},
                       {"name": "sniper_assassinate", "lvl": 1, "use": "target", "ready": True, "ult": True}],
         "items": [{"name": "item_tango", "slot": 0, "use": "target", "ready": True}],
         "enemy_team": ["luna", "lina", "bristleback", "witch_doctor", "jakiro"],
         "coach": [dict(c) for c in coach], "enemies": [dict(e) for e in enemies]}
    if alive:
        o["hp"] = list(hp)
    o.update(kw)
    return o


class FakeBackend:
    label = "подставной"

    def __init__(self, reply=None, error=None, delay=0.0):
        self.calls = []
        self.reply, self.error, self.delay = reply, error, delay

    def decide(self, system, user, obs, extra=None):
        self.calls.append({"system": system, "user": user, "obs": obs, "extra": extra})
        if self.delay:
            time.sleep(self.delay)
        if self.error:
            raise self.error
        return {"data": self.reply or {"plan": "farm", "where": "bot", "target": "", "ally": 0, "cast": [],
                                       "buy": [], "level": [], "retreat_hp": 30, "buyback": False, "say": ""},
                "usage": {"input_tokens": 1000, "output_tokens": 50, "cache_read_input_tokens": 2000}}


class ParseDecision(unittest.TestCase):
    def test_valid_and_text_with_fence(self):
        d, notes = A.parse_decision('Вот: ```json\n{"plan":"push","where":"top","say":"Иду"}\n``` всё', obs())
        self.assertEqual(d["plan"], "push")
        self.assertEqual(d["where"], "top")
        self.assertEqual(d["say"], "Иду")
        self.assertEqual(d["retreat_hp"], 25)
        self.assertEqual(notes, [])

    def test_bad_plan_is_rejected(self):
        d, notes = A.parse_decision({"plan": "dance"}, obs())
        self.assertIsNone(d)
        self.assertTrue(notes)
        self.assertEqual(A.parse_decision("нет тут json", obs())[0], None)

    def test_names_checked_against_observation(self):
        d, notes = A.parse_decision({"plan": "fight", "target": "npc_dota_hero_Luna",
                                     "cast": [{"ability": "sniper_assassinate", "target": "lina"},
                                              {"ability": "lina_laguna_blade", "target": "luna"},
                                              {"ability": "sniper_shrapnel", "target": "pudge"},
                                              {"ability": "item_tpscroll", "target": "base"}],
                                     "buy": ["item_power_treads", "Сапоги"], "level": ["sniper_take_aim"],
                                     "retreat_hp": 150, "say": "x" * 300}, obs())
        self.assertEqual(d["target"], "luna")
        self.assertEqual(d["cast"], [{"ability": "sniper_assassinate", "target": "lina"},
                                     {"ability": "sniper_shrapnel", "target": ""}])
        self.assertEqual(d["buy"], ["item_power_treads"])
        self.assertEqual(d["level"], [])
        self.assertEqual(d["retreat_hp"], 90)
        self.assertEqual(len(d["say"]), A.MAX_SAY)
        self.assertEqual(len(notes), 5)          # чужая способность, цель pudge, тп нет, «Сапоги», take_aim

    def test_special_targets_and_ult_alias(self):
        d, _ = A.parse_decision({"plan": "hold", "cast": [{"ability": "#ult", "target": "self"},
                                                          {"ability": "sniper_shrapnel", "target": "creeps"},
                                                          {"ability": "item_tango", "target": "2"}]}, obs())
        self.assertEqual([c["target"] for c in d["cast"]], ["self", "creeps", "2"])

    def test_schema_fits_structured_outputs(self):
        s = A.DECISION_SCHEMA
        self.assertEqual(set(s["required"]), set(s["properties"]))
        self.assertIs(s["additionalProperties"], False)
        item = s["properties"]["cast"]["items"]
        self.assertIs(item["additionalProperties"], False)
        text = json.dumps(s)
        for bad in ("minimum", "maximum", "minLength", "maxLength", "multipleOf"):
            self.assertNotIn(bad, text)          # в structured outputs не поддерживаются (документация API)
        self.assertEqual(s["properties"]["plan"]["enum"], list(A.PLANS))


class VoiceChatParse(unittest.TestCase):
    def test_to_field(self):
        d, notes = A.parse_decision({"plan": "hold", "say": "Вайпер, ко мне", "to": [2, 1, 2, 9, "x"]}, obs(pos=1))
        self.assertEqual(d["to"], [2])                          # себя, повтор и чужие номера — прочь
        self.assertEqual(len(notes), 1)                          # «x» — не номер
        d, _ = A.parse_decision({"plan": "hold", "say": "", "to": [2]}, obs())
        self.assertEqual(d["to"], [])                            # без реплики адресат не нужен
        self.assertIn("to", A.DECISION_SCHEMA["required"])
        self.assertEqual(A.DECISION_SCHEMA["properties"]["to"], {"type": "array", "items": {"type": "integer"}})


class Prompts(unittest.TestCase):
    def test_system_prompt(self):
        p = A.system_prompt("dire", 2, "npc_dota_hero_lina", {"name": "Тест", "style": {"aggression": 0.8}})
        self.assertIn("lina", p)
        self.assertIn("Тьму", p)
        self.assertIn("мидер", p)
        self.assertIn("Тест", p)
        self.assertIn("агрессия 0.8", p)
        self.assertIn("«пуш» — пушить линию", p)
        example = p.rsplit("Пример: ", 1)[1]
        d, notes = A.parse_decision(example, None)
        self.assertEqual((d["plan"], d["where"]), ("farm", "mid"))
        self.assertEqual(notes, [])

    def test_system_prompt_voice_chat_and_names(self):
        p = A.system_prompt("radiant", 1, "sniper", None, 0.85,
                            {"allies": [(2, "viper"), (3, "axe")], "enemies": ["luna", "lina"]})
        self.assertIn("ГОЛОСОВОЙ ЧАТ КОМАНДЫ", p)
        self.assertIn("2 — viper (Вайпер)", p)
        self.assertIn("luna (Луна)", p)
        self.assertIn('"to":[]', p)
        self.assertEqual(A.hero_ru("npc_dota_hero_crystal_maiden"), "Кристальная Дева")   # coach/data/heroes.json

    def test_user_prompt(self):
        o = obs(clock=754, coach=[{"seq": 3, "ago": 1, "text": "1 пуш бот т2", "urgent": True}])
        u = A.user_prompt(o, ["12:30 farm bot"], o["coach"], "приказ тренера")
        self.assertIn("12:34", u)
        self.assertIn("НОВЫЙ ПРИКАЗ ТРЕНЕРА: «1 пуш бот т2» (срочно)", u)
        self.assertIn("12:30 farm bot", u)
        view = json.loads(u.split("Наблюдение: ", 1)[1].split("\n", 1)[0])
        self.assertNotIn("team", view)
        self.assertEqual(view["clock"], 754)
        self.assertEqual(list(view)[:3], ["clock", "alive", "lvl"])                # сначала сам герой
        self.assertNotIn("заказать покупки", u)
        dead = A.user_prompt(obs(clock=900, alive=False, gold=4200), [], [], "ты погиб")
        self.assertIn("Ты мёртв, золота 4200, очередь покупок пуста", dead)
        busy = A.user_prompt(obs(clock=900, alive=False, gold=4200, queue={"buy": ["item_bfury"]}), [], [], "x")
        self.assertNotIn("заказать покупки", busy)


class Hub(unittest.TestCase):
    def hub(self, backend=None, **kw):
        self.backend = backend or FakeBackend()
        return A.AgentHub({"radiant": self.backend, "dire": A.RulesBackend()}, sync=True, **kw)

    def test_schedule_and_triggers(self):
        h = self.hub()
        r = h.tick({"heroes": [obs(clock=0)]})
        self.assertEqual(len(self.backend.calls), 1)
        self.assertIn("начало", self.backend.calls[0]["extra"]["trigger"])
        self.assertEqual(r["decisions"][0]["seq"], 1)
        self.assertEqual(r["decisions"][0]["decision"]["plan"], "farm")
        self.assertEqual(r["run"], h.run)
        h.tick({"heroes": [obs(clock=0.5)]})                                   # рано
        h.tick({"heroes": [obs(clock=2.0)]})                                   # без повода
        self.assertEqual(len(self.backend.calls), 1)
        order = {"seq": 1, "ago": 0, "text": "1 пуш бот т2", "urgent": False}
        h.tick({"heroes": [obs(clock=2.5, coach=[order])]})
        self.assertEqual(self.backend.calls[-1]["extra"]["trigger"], "приказ тренера")
        self.assertIn("НОВЫЙ ПРИКАЗ", self.backend.calls[-1]["user"])
        h.tick({"heroes": [obs(clock=4.0, coach=[order])]})                    # приказ уже учтён
        self.assertEqual(len(self.backend.calls), 2)
        h.tick({"heroes": [obs(clock=4.0, coach=[order], enemies=[{"hero": "luna", "d": 900}])]})
        self.assertEqual(self.backend.calls[-1]["extra"]["trigger"], "враг рядом")
        h.tick({"heroes": [obs(clock=5.5, coach=[order], hp=(200, 500), enemies=[{"hero": "luna", "d": 900}])]})
        self.assertEqual(self.backend.calls[-1]["extra"]["trigger"], "быстро теряешь здоровье")
        h.tick({"heroes": [obs(clock=7.0, coach=[order], alive=False)]})
        self.assertEqual(self.backend.calls[-1]["extra"]["trigger"], "ты погиб")
        h.tick({"heroes": [obs(clock=12.0, coach=[order], alive=False)]})      # мёртвым — реже
        self.assertEqual(len(self.backend.calls), 5)
        h.tick({"heroes": [obs(clock=13.0, coach=[order])]})
        self.assertEqual(self.backend.calls[-1]["extra"]["trigger"], "ты возродился")
        h.tick({"heroes": [obs(clock=17.5, coach=[order])]})
        self.assertEqual(self.backend.calls[-1]["extra"]["trigger"], "очередное решение")
        ag = h.agents[("radiant", 1)]
        self.assertEqual(ag.seen_coach, 1)
        self.assertTrue(any("пуш бот" in m for m in ag.memory))

    def test_errors_limits_and_new_match(self):
        bad = FakeBackend(error=A.BackendError("HTTP 500: сломалось"))
        h = self.hub(bad, max_calls=3)
        r = h.tick({"heroes": [obs(clock=0)]})
        self.assertEqual(r["decisions"], [])
        self.assertIn("ошибка", r["agents"][0]["state"])
        h.tick({"heroes": [obs(clock=2)]})                                     # после ошибки ждём 3 с
        self.assertEqual(len(bad.calls), 1)
        for clock in (4, 8, 12):
            h.tick({"heroes": [obs(clock=clock)]})
        self.assertEqual(len(bad.calls), 3)                                    # предел вызовов
        self.assertIn("лимит", h.agents[("radiant", 1)].state)
        h2 = self.hub(FakeBackend(error=A.BackendError("HTTP 429", retry_after=30)))
        h2.tick({"heroes": [obs(clock=0)]})
        h2.tick({"heroes": [obs(clock=10)]})
        self.assertEqual(len(self.backend.calls), 1)                           # пауза по retry-after
        self.assertIn("пауза", h2.agents[("radiant", 1)].state)
        h3 = self.hub()
        h3.tick({"heroes": [obs(clock=600)]})
        first = h3.agents[("radiant", 1)]
        h3.tick({"heroes": [obs(clock=-80)]})                                  # новый матч
        self.assertIsNot(h3.agents[("radiant", 1)], first)

    def test_log_summary_prices(self):
        with tempfile.TemporaryDirectory() as tmp:
            log = Path(tmp) / "a.jsonl"
            h = self.hub(log_path=log, prices={"in": 1.0, "out": 5.0, "cache_read": 0.1})
            h.tick({"heroes": [obs(clock=0), obs(clock=0, pos=2)]})
            recs = [json.loads(x) for x in log.read_text(encoding="utf-8").splitlines()]
            self.assertEqual(len(recs), 2)
            self.assertEqual(recs[0]["decision"]["plan"], "farm")
            self.assertIn("latency_s", recs[0])
            s = h.summary()
            self.assertEqual((s["calls"], s["in"], s["out"], s["cache_read"]), (2, 2000, 100, 4000))
            self.assertAlmostEqual(s["cost_usd_est"], (2000 * 1 + 100 * 5 + 4000 * 0.1) / 1e6)

    def test_background_calls(self):
        slow = FakeBackend(delay=0.2)
        h = A.AgentHub({"radiant": slow, "dire": slow})
        try:
            r = h.tick({"heroes": [obs(clock=0)]})
            self.assertEqual(r["decisions"], [])                               # ответ сразу, модель думает в фоне
            self.assertEqual(r["agents"][0]["state"], "думает")
            deadline = time.time() + 3
            while time.time() < deadline and not h.tick({"heroes": [obs(clock=0.2)]})["decisions"]:
                time.sleep(0.05)
            self.assertEqual(h.tick({"heroes": [obs(clock=0.3)]})["decisions"][0]["seq"], 1)
            self.assertEqual(len(slow.calls), 1)
        finally:
            h.close()


class SayingBackend(FakeBackend):
    """Агент, который говорит заданное (и только раз)."""

    def __init__(self, lines):
        super().__init__()
        self.lines = list(lines)

    def decide(self, system, user, obs, extra=None):
        self.calls.append({"system": system, "user": user, "obs": obs, "extra": extra})
        say, to = self.lines.pop(0) if self.lines else ("", [])
        return {"data": {"plan": "farm", "where": "bot", "target": "", "ally": 0, "cast": [], "buy": [], "level": [],
                         "retreat_hp": 30, "buyback": False, "say": say, "to": to}, "usage": {}}


class VoiceChatHub(unittest.TestCase):
    def test_conversation(self):
        talk = SayingBackend([("Вайпер, иди ко мне на бот", [2])])
        h = A.AgentHub({"radiant": talk, "dire": A.RulesBackend()}, sync=True)
        heard = []
        h.on_say = lambda team, e: heard.append((team, e))
        p1, p2 = obs(clock=0, pos=1), obs(clock=0, pos=2)
        p2["hero"] = "viper"
        enemy = obs(clock=0, pos=1, team="dire")
        enemy["hero"] = "luna"
        h.tick({"heroes": [p1, p2, enemy]})                        # первые решения всех; первый агент зовёт второго
        self.assertEqual(heard[0][0], "radiant")
        self.assertEqual((heard[0][1]["from"], heard[0][1]["to"], heard[0][1]["reply"]), (1, [2], False))
        n = len(talk.calls)
        p1, p2 = obs(clock=1.5, pos=1), obs(clock=1.5, pos=2)
        p2["hero"] = "viper"
        h.tick({"heroes": [p1, p2]})
        last = talk.calls[-1]
        self.assertEqual(len(talk.calls), n + 1)                   # проснулся только второй
        self.assertEqual(last["obs"]["pos"], 2)
        self.assertEqual(last["extra"]["trigger"], A.ASKED)
        self.assertIn("НОВОЕ", last["user"])
        self.assertIn("→ тебе: «Вайпер, иди ко мне на бот»", last["user"])
        self.assertEqual(last["extra"]["chat_to_me"][0]["from"], 1)
        enemy_prompt = A.user_prompt(enemy, [], [], "x", h._chat_for(h.agents[("dire", 1)], 1.5), 1)
        self.assertNotIn("Вайпер, иди", enemy_prompt)              # чужая команда чат не слышит

    def test_reply_does_not_ping_pong(self):
        talk = SayingBackend([("Вайпер, иди ко мне", [2]), ("", []), ("Иду", [1])])
        h = A.AgentHub({"radiant": talk, "dire": talk}, sync=True)
        p = lambda c, pos: dict(obs(clock=c, pos=pos), hero="viper" if pos == 2 else "sniper")
        h.tick({"heroes": [p(0, 1), p(0, 2)]})
        h.tick({"heroes": [p(1.5, 1), p(1.5, 2)]})                 # второй отвечает первому
        chat = list(h.chat["radiant"])
        self.assertEqual([(e["from"], e["to"], e["reply"]) for e in chat], [(1, [2], False), (2, [1], True)])
        n = len(talk.calls)
        h.tick({"heroes": [p(3.0, 1), p(3.0, 2)]})                 # ответ первого не будит
        self.assertEqual(len(talk.calls), n)

    def test_rules_answer_and_callout(self):
        d = A.rules_decision(obs(), None, {"chat_to_me": [{"from": 3, "hero": "axe", "text": "помоги"}]})
        self.assertEqual((d["say"], d["to"], d["plan"], d["ally"]), ("Акс, понял, иду", [3], "save", 3))
        d = A.rules_decision(obs(enemies=[{"hero": "luna", "d": 900}]), None, {"trigger": "враг рядом"})
        self.assertEqual(d["say"], "Вижу Луна")


class Rules(unittest.TestCase):
    def test_rules(self):
        d = A.rules_decision(obs(clock=-60, items=[]))
        self.assertEqual((d["plan"], d["where"]), ("farm", "bot"))
        self.assertIn("item_tango", d["buy"])
        d = A.rules_decision(obs(clock=300, pos=3, team="dire",
                                 coach=[{"seq": 1, "ago": 2, "text": "3 пуш топ"}]), new_coach=[{"seq": 1}])
        self.assertEqual((d["plan"], d["where"]), ("push", "top"))
        self.assertTrue(d["say"].startswith("Понял"))
        d = A.rules_decision(obs(clock=300, coach=[{"seq": 1, "ago": 2, "text": "1 ульт луна"}]))
        self.assertEqual(d["cast"], [{"ability": "sniper_assassinate", "target": "luna"}])
        d = A.rules_decision(obs(clock=300, hp=(100, 500)))
        self.assertEqual(d["plan"], "retreat")
        self.assertEqual(A.parse_decision(d, obs())[1], [])
        self.assertEqual([A.default_lane(t, p) for t in ("radiant", "dire") for p in range(1, 6)],
                         ["bot", "mid", "top", "top", "bot", "top", "mid", "bot", "bot", "top"])


class FakeHTTP:
    def __init__(self, responses):
        self.responses = list(responses)
        self.requests = []

    def __call__(self, req, timeout=None):
        self.requests.append(req)
        r = self.responses.pop(0)
        if isinstance(r, Exception):
            raise r
        return io.BytesIO(json.dumps(r).encode("utf-8"))


def http_error(code, body, headers=None):
    return urllib.error.HTTPError(A.ApiBackend.URL, code, "err", headers or {}, io.BytesIO(body.encode("utf-8")))


class Api(unittest.TestCase):
    def test_request_and_reply(self):
        ok = {"content": [{"type": "text", "text": '{"plan":"retreat","where":"base","target":"","ally":0,"cast":[],'
                                                  '"buy":[],"level":[],"retreat_hp":40,"buyback":false,"say":"Ухожу"}'}],
              "usage": {"input_tokens": 900, "output_tokens": 60, "cache_read_input_tokens": 2100}}
        http = FakeHTTP([ok])
        b = A.ApiBackend("model-x", api_key="k", opener=http)
        h = A.AgentHub({"radiant": b, "dire": b}, sync=True)
        r = h.tick({"heroes": [obs(clock=0)]})
        self.assertEqual(r["decisions"][0]["decision"]["say"], "Ухожу")
        req = http.requests[0]
        self.assertEqual(req.full_url, "https://api.anthropic.com/v1/messages")
        self.assertEqual(req.get_header("X-api-key"), "k")
        self.assertEqual(req.get_header("Anthropic-version"), "2023-06-01")
        body = json.loads(req.data)
        self.assertEqual(body["model"], "model-x")
        self.assertEqual(body["system"][0]["cache_control"], {"type": "ephemeral"})
        self.assertEqual(body["output_config"]["format"], {"type": "json_schema", "schema": A.DECISION_SCHEMA})
        self.assertEqual(body["messages"][0]["role"], "user")
        self.assertEqual(h.summary()["cache_read"], 2100)
        self.assertEqual(b.label, "Claude API (model-x)")

    def test_errors(self):
        ok = {"content": [{"type": "text", "text": '{"plan":"hold"}'}], "usage": {}}
        http = FakeHTTP([http_error(400, '{"error":{"message":"output_config: unsupported"}}'), ok])
        b = A.ApiBackend("m", api_key="k", opener=http)
        self.assertEqual(A.parse_decision(b.decide("s", "u", obs())["text"])[0]["plan"], "hold")
        self.assertFalse(b.structured)                                         # дальше без схемы
        self.assertNotIn("output_config", json.loads(http.requests[1].data))
        b2 = A.ApiBackend("m", api_key="k", opener=FakeHTTP([http_error(429, "slow down", {"retry-after": "7"})]))
        with self.assertRaises(A.BackendError) as cm:
            b2.decide("s", "u", obs())
        self.assertEqual(cm.exception.retry_after, 7.0)
        with self.assertRaises(ValueError):
            A.ApiBackend("", api_key="k")


class Cli(unittest.TestCase):
    def test_argv_and_reply(self):
        seen = {}

        def runner(argv, **kw):
            seen["argv"], seen["kw"] = argv, kw

            class P:
                returncode = 0
                stdout = json.dumps({"type": "result", "is_error": False, "result": "",
                                     "structured_output": {"plan": "push", "where": "mid", "target": "", "ally": 0,
                                                           "cast": [], "buy": [], "level": [], "retreat_hp": 30,
                                                           "buyback": False, "say": "Пушу"},
                                     "usage": {"input_tokens": 10, "output_tokens": 5}, "total_cost_usd": 0.01})
                stderr = ""
            return P()

        b = A.CliBackend(model="m", runner=runner)
        out = b.decide("СИСТЕМА", "НАБЛЮДЕНИЕ", obs())
        self.assertEqual(out["data"]["say"], "Пушу")
        argv = seen["argv"]
        self.assertEqual(argv[:4], ["claude", "--model", "m", "-p"])
        self.assertEqual(argv[argv.index("--system-prompt") + 1], "СИСТЕМА")
        self.assertEqual(argv[argv.index("--tools") + 1], "")
        self.assertEqual(json.loads(argv[argv.index("--json-schema") + 1]), A.DECISION_SCHEMA)
        self.assertNotIn("--bare", argv)                                       # --bare не берёт подписку
        self.assertEqual(seen["kw"]["input"], "НАБЛЮДЕНИЕ")

        def missing(argv, **kw):
            raise FileNotFoundError

        with self.assertRaises(A.BackendError):
            A.CliBackend(runner=missing).decide("s", "u", obs())

        def failing(argv, **kw):
            class P:
                returncode = 1
                stdout = json.dumps({"is_error": True, "result": "Not logged in"})
                stderr = ""
            return P()

        with self.assertRaises(A.BackendError):
            A.CliBackend(runner=failing).decide("s", "u", obs())


class Args(unittest.TestCase):
    def test_backends_and_personas_from_args(self):
        from voicecoach.server import agent_factory_from_args, main  # noqa: F401
        import argparse
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "vasya.json"
            p.write_text(json.dumps({"name": "Вася", "style": {"aggression": 0.9}}, ensure_ascii=False), encoding="utf-8")
            a = argparse.Namespace(agents="rules", radiant=None, dire=None, model=None, claude="claude", period=4.0,
                                   max_calls=None, personas=None, persona=[f"radiant:1={p}"], price_in=None,
                                   price_out=None, price_cache_read=None, price_cache_write=None)
            factory, backends = agent_factory_from_args(a)
            hub = factory("t")
            hub.log_path = None
            self.assertEqual(backends["radiant"].label, "правила (не Claude)")
            hub.sync = True
            hub.tick({"heroes": [obs(clock=0)]})
            self.assertIn("Ты — Вася", hub.agents[("radiant", 1)].system)
            self.assertIn("агрессия 0.9", hub.agents[("radiant", 1)].system)
            hub.close()
            a.persona = ["radiant=1"]
            with self.assertRaises(ValueError):
                agent_factory_from_args(a)
            a.persona, a.agents = [], "api"
            with self.assertRaises(ValueError):                                # api без модели и ключа — отказ
                agent_factory_from_args(a)


class Route(unittest.TestCase):
    def test_tick_and_agents_routes(self):
        srv = serve("127.0.0.1", 0, lambda name: A.AgentHub(
            {"radiant": A.RulesBackend(), "dire": A.RulesBackend()}, sync=True))
        t = threading.Thread(target=srv.serve_forever, daemon=True)
        t.start()
        try:
            port = srv.server_address[1]
            body = json.dumps({"clock": -80, "heroes": [obs(clock=-80, items=[]),
                                                        obs(clock=-80, pos=3, team="dire", items=[])]}).encode()
            req = urllib.request.Request(f"http://127.0.0.1:{port}/api/local/tick", data=body, method="POST",
                                         headers={"Content-Type": "application/json"})
            r = json.loads(urllib.request.urlopen(req, timeout=5).read())
            self.assertEqual(len(r["decisions"]), 2)
            self.assertEqual(r["backend"]["radiant"], "правила (не Claude)")
            st = json.loads(urllib.request.urlopen(f"http://127.0.0.1:{port}/api/local/agents", timeout=5).read())
            self.assertEqual([a["pos"] for a in st["agents"]], [3, 1])
            self.assertEqual(st["summary"]["calls"], 2)
            # голосовой чат: реплика агента — событие kind=voice своей команде
            order = obs(clock=-70, items=[], coach=[{"seq": 1, "ago": 0, "text": "1 пуш бот"}])
            body = json.dumps({"heroes": [order]}).encode()
            req = urllib.request.Request(f"http://127.0.0.1:{port}/api/local/tick", data=body, method="POST")
            urllib.request.urlopen(req, timeout=5).read()
            evs = json.loads(urllib.request.urlopen(
                f"http://127.0.0.1:{port}/api/local/events?team=radiant&after=0", timeout=5).read())["events"]
            voice = [e for e in evs if e["kind"] == "voice"]
            self.assertEqual((voice[-1]["pos"], voice[-1]["text"], voice[-1]["hero_ru"], voice[-1]["to"]),
                             (1, "Понял: 1 пуш бот", "Снайпер", []))
            dire = json.loads(urllib.request.urlopen(
                f"http://127.0.0.1:{port}/api/local/events?team=dire&after=0", timeout=5).read())["events"]
            self.assertFalse([e for e in dire if e["kind"] == "voice"])
            for name, ctype in (("voice.html", "text/html"), ("voices.js", "application/javascript")):
                r = urllib.request.urlopen(f"http://127.0.0.1:{port}/{name}", timeout=5)
                self.assertTrue(r.headers["Content-Type"].startswith(ctype))
                self.assertIn(b"speechSynthesis" if name == "voices.js" else b"VoiceChat", r.read())
        finally:
            srv.shutdown()
            srv.server_close()


if __name__ == "__main__":
    unittest.main()
