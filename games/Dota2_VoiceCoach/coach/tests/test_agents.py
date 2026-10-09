"""Агенты героев (решение Д11): разбор ответа модели, промпты, расписание решений, моторы, путь /tick.

Модель здесь не вызывается: моторы api и cli проверяются на подменённых HTTP и процессе — что уходит
в API и в `claude -p` и как разбирается ответ. Настоящий вызов — на ПК автора (журнал агентов)."""
import io
import json
import os
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.request
from pathlib import Path
from unittest import mock

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

    def test_failures_free_the_agent(self):
        class Weird(FakeBackend):
            def decide(self, system, user, obs, extra=None):
                self.calls.append(1)
                raise RuntimeError("неожиданное")

        h = self.hub(Weird())
        h.tick({"heroes": [obs(clock=0)]})
        ag = h.agents[("radiant", 1)]
        self.assertEqual((ag.busy, h.inflight, ag.calls), (False, 0, 1))
        self.assertIn("RuntimeError", ag.state)
        h = self.hub()
        with mock.patch.object(A, "user_prompt", side_effect=KeyError("поле")):    # сломалось до вызова модели
            h.tick({"heroes": [obs(clock=0)]})
        ag = h.agents[("radiant", 1)]
        self.assertEqual((ag.busy, h.inflight, len(self.backend.calls)), (False, 0, 0))
        h.tick({"heroes": [obs(clock=1)]})                                    # после ошибки — пауза 3 с, не каждый тик
        self.assertEqual(len(self.backend.calls), 0)
        h.tick({"heroes": [obs(clock=4)]})
        self.assertEqual(len(self.backend.calls), 1)
        with mock.patch.object(A, "memory_line", side_effect=ValueError("учёт")):  # сломался учёт после ответа
            h.tick({"heroes": [obs(clock=9)]})
        self.assertEqual((ag.busy, h.inflight), (False, 0))
        self.assertIn("сбой сервера", ag.state)

    def test_bad_observation_does_not_stop_others(self):
        h = self.hub()
        r = h.tick({"heroes": [{"team": "radiant", "pos": None}, {"team": "radiant", "pos": 9, "clock": 0},
                               "мусор", obs(clock=0, pos=2)]})
        self.assertEqual([(d["team"], d["pos"]) for d in r["decisions"]], [("radiant", 2)])

    def test_free_backends_not_counted_and_pause_per_side(self):
        paid = FakeBackend()
        h = A.AgentHub({"radiant": A.RulesBackend(), "dire": paid}, sync=True, max_calls=1)
        heroes = [obs(clock=0, pos=p) for p in (1, 2, 3)] + [obs(clock=0, pos=p, team="dire") for p in (1, 2)]
        r = h.tick({"heroes": heroes})
        self.assertEqual(sum(d["team"] == "radiant" for d in r["decisions"]), 3)   # правила предел не тратят
        self.assertEqual(len(paid.calls), 1)
        self.assertEqual(h.agents[("dire", 2)].state, "лимит вызовов исчерпан")
        s = h.summary()
        self.assertEqual((s["calls"], s["paid_calls"]), (4, 1))
        self.assertEqual(s["teams"]["radiant"]["backend"], "правила (не Claude)")
        self.assertEqual(s["teams"]["dire"]["calls"], 1)
        slow = FakeBackend(error=A.BackendError("HTTP 429", retry_after=30))
        h = A.AgentHub({"radiant": slow, "dire": A.RulesBackend()}, sync=True)
        h.tick({"heroes": [obs(clock=0), obs(clock=0, team="dire")]})
        r = h.tick({"heroes": [obs(clock=10), obs(clock=10, team="dire")]})
        self.assertIn("пауза", h.agents[("radiant", 1)].state)
        self.assertEqual(next(d["seq"] for d in r["decisions"] if d["team"] == "dire"), 2)  # Тьма не ждёт чужой 429

    def test_coach_orders_wake_at_most_every_coach_gap(self):
        """Поток приказов не множит вызовы: приказ будит агента не чаще раза в coach_gap с (остальное — в очереди)."""
        h = self.hub()
        h.tick({"heroes": [obs(clock=0)]})
        orders = []
        for i in range(8):                                                     # приказ каждые 0.5 с игры
            orders.append({"seq": i + 1, "ago": 0, "text": f"1 пуш бот {i}", "urgent": False})
            h.tick({"heroes": [obs(clock=1 + i * 0.5, coach=list(orders))]})
        triggers = [c["extra"]["trigger"] for c in self.backend.calls[1:]]
        self.assertEqual(triggers, ["приказ тренера", "приказ тренера"])        # в 1 с и в 4 с, а не 8 раз
        h.tick({"heroes": [obs(clock=8, coach=list(orders))]})                 # следующее решение видит все приказы
        self.assertIn("1 пуш бот 7", self.backend.calls[-1]["user"])

    def test_narrow_pool_serves_both_sides(self):
        """Рецензия 3: при узком пуле (по подписке) места доставались в порядке героев в обмене — сначала одной
        стороне; герои второй стороны почти не получали решений. Теперь — тем, кто дольше без решения."""
        light, dark = FakeBackend(), FakeBackend()
        h = A.AgentHub({"radiant": light, "dire": dark}, sync=True, max_inflight=4, period=2.0, min_gap=0.5)
        heroes = [obs(team=t, pos=p) for t in ("radiant", "dire") for p in range(1, 6)]
        for clock in (0.0, 1.0, 2.0):
            h.tick({"clock": clock, "heroes": [dict(o, clock=clock) for o in heroes]})
        got = {(c["obs"]["team"], c["obs"]["pos"]) for b in (light, dark) for c in b.calls}
        self.assertEqual(len(got), 10, sorted(got))                              # все десять уже решали
        self.assertEqual(h.tick({"clock": 3.0, "heroes": []})["stale"], 20.0)     # игра держит решение 20 с

    def test_paid_call_limit_is_per_side(self):
        """Предел платных вызовов — у каждой стороны свой: соперник не исчерпает предел хоста."""
        light, dark = FakeBackend(), FakeBackend()
        h = A.AgentHub({"radiant": light, "dire": dark}, sync=True, max_calls=2)
        for clock in (0, 5, 10, 15):
            h.tick({"heroes": [obs(clock=clock, team="dire", pos=p) for p in (1, 2, 3)]})
        self.assertEqual(len(dark.calls), 2)
        h.tick({"heroes": [obs(clock=20, pos=1), obs(clock=20, pos=2)]})
        self.assertEqual(len(light.calls), 2)                                   # у Света свой предел
        self.assertEqual(h.summary()["paid_calls"], 4)

    def test_applied_measures_decision_age(self):
        with tempfile.TemporaryDirectory() as tmp:
            log = Path(tmp) / "a.jsonl"
            h = self.hub(log_path=log)
            h.tick({"heroes": [obs(clock=10)]})
            h.tick({"heroes": [obs(clock=11)], "clock": 11,
                    "applied": [{"team": "radiant", "pos": 1, "seq": 1, "clock": 11.5},
                                {"team": "radiant", "pos": 1, "seq": 7, "clock": 11.5}, {"pos": "x"}]})
            s = h.summary()
            self.assertEqual(s["teams"]["radiant"]["decision_age_p50_s"], 1.5)
            self.assertEqual(s["decision_age_p95_s"], 1.5)
            recs = [json.loads(x) for x in log.read_text(encoding="utf-8").splitlines()]
            applied = [r for r in recs if r.get("event") == "applied"]
            self.assertEqual([(r["pos"], r["seq"], r["decision_age_s"]) for r in applied], [(1, 1, 1.5)])
            self.assertEqual(recs[0]["seq"], 1)
            self.assertNotIn("raw", recs[0])                                  # чистый ответ — без сырого текста

    def test_coordinates_not_in_prompt(self):
        o = obs(clock=0, xy=[100, -200], allies=[{"pos": 2, "hero": "viper", "xy": [1, 2]}],
                enemies=[{"hero": "luna", "d": 900, "xy": [3, 4]}])
        u = A.user_prompt(o, [], [], "x")
        self.assertNotIn('"xy"', u)
        self.assertIn('"luna"', u)
        self.assertEqual(o["xy"], [100, -200])                                 # наблюдение не тронуто — оно для карты

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
              "usage": {"input_tokens": 900, "output_tokens": 60, "cache_read_input_tokens": 2100},
              "stop_reason": "end_turn", "model": "model-x"}
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
        self.assertEqual(body["output_config"], {"format": {"type": "json_schema", "schema": A.DECISION_SCHEMA},
                                                 "effort": "low"})
        self.assertEqual(body["max_tokens"], 4000)                             # запас на думание (входит в max_tokens)
        self.assertNotIn("thinking", body)                                     # по умолчанию — как решила модель
        self.assertEqual(body["messages"][0]["role"], "user")
        self.assertEqual(h.summary()["cache_read"], 2100)
        self.assertEqual(b.label, "Claude API (model-x)")
        thinking = A.ApiBackend("m", api_key="k", thinking="between_tools", effort=None, max_tokens=900)
        body = thinking.body("s", "u")
        self.assertEqual((body["thinking"], body["max_tokens"]), ({"type": "between_tools"}, 900))
        self.assertNotIn("effort", body["output_config"])

    def test_unsupported_params_are_dropped(self):
        ok = {"content": [{"type": "text", "text": '{"plan":"hold"}'}], "usage": {}}
        http = FakeHTTP([http_error(400, '{"error":{"message":"effort: not supported by this model"}}'),
                         http_error(400, '{"error":{"message":"output_config.format: unsupported"}}'), ok])
        b = A.ApiBackend("m", api_key="k", opener=http)
        self.assertEqual(A.parse_decision(b.decide("s", "u", obs())["text"])[0]["plan"], "hold")
        self.assertEqual(b.dropped, ["effort", "structured"])
        self.assertEqual(json.loads(http.requests[1].data)["output_config"], {"format": {
            "type": "json_schema", "schema": A.DECISION_SCHEMA}})
        self.assertNotIn("output_config", json.loads(http.requests[2].data))  # дальше без схемы: JSON по промпту
        other = A.ApiBackend("m", api_key="k", opener=FakeHTTP([http_error(400, "messages: too long")]))
        with self.assertRaises(A.BackendError):                                # чужая 400 — не повторять вслепую
            other.decide("s", "u", obs())
        self.assertEqual(other.dropped, [])

    def test_errors(self):
        b2 = A.ApiBackend("m", api_key="k", opener=FakeHTTP([http_error(429, "slow down", {"retry-after": "7"})]))
        with self.assertRaises(A.BackendError) as cm:
            b2.decide("s", "u", obs())
        self.assertEqual(cm.exception.retry_after, 7.0)
        b3 = A.ApiBackend("m", api_key="k", opener=FakeHTTP([
            http_error(529, "overloaded", {"retry-after": "Wed, 07 Oct 2026 10:00:00 GMT"})]))
        with self.assertRaises(A.BackendError) as cm:
            b3.decide("s", "u", obs())
        self.assertEqual(cm.exception.retry_after, 30.0)                       # дата вместо секунд
        with self.assertRaises(ValueError):
            A.ApiBackend("", api_key="k")

    def test_truncated_reply_is_error_but_tokens_counted(self):
        cut = {"content": [{"type": "text", "text": '{"plan":"fa'}], "stop_reason": "max_tokens", "model": "m",
               "usage": {"input_tokens": 3000, "output_tokens": 4000}}
        b = A.ApiBackend("m", api_key="k", opener=FakeHTTP([cut]))
        with tempfile.TemporaryDirectory() as tmp:
            log = Path(tmp) / "a.jsonl"
            h = A.AgentHub({"radiant": b, "dire": A.RulesBackend()}, sync=True, log_path=log)
            r = h.tick({"heroes": [obs(clock=0)]})
            self.assertEqual(r["decisions"], [])
            self.assertIn("max_tokens", h.agents[("radiant", 1)].state)
            s = h.summary()
            self.assertEqual((s["errors"], s["in"], s["out"]), (1, 3000, 4000))   # обрезанный ответ оплачен
            rec = json.loads(log.read_text(encoding="utf-8").splitlines()[0])
            self.assertEqual((rec["stop_reason"], rec["model"], rec["raw"]), ("max_tokens", "m", '{"plan":"fa'))


class Cli(unittest.TestCase):
    REPLY = {"type": "result", "subtype": "success", "is_error": False, "result": '{"plan":"push"}',
             "structured_output": {"plan": "push", "where": "mid", "target": "", "ally": 0, "cast": [], "buy": [],
                                   "level": [], "retreat_hp": 30, "buyback": False, "say": "Пушу", "to": []},
             "usage": {"input_tokens": 10, "output_tokens": 5}, "total_cost_usd": 0.01,
             "modelUsage": {"small-model": {"costUSD": 0.0001}, "big-model": {"costUSD": 0.0099}}}

    def runner(self, reply=None, code=0):
        seen = {}

        def run(argv, **kw):
            seen["argv"], seen["kw"] = argv, kw
            seen["system"] = Path(argv[argv.index("--system-prompt-file") + 1]).read_text(encoding="utf-8")

            class P:
                returncode = code
                stdout = json.dumps(reply or self.REPLY)
                stderr = ""
            return P()
        return run, seen

    def test_argv_and_reply(self):
        run, seen = self.runner()
        b = A.CliBackend(model="m", runner=run, effort="low", which=lambda name: "/opt/bin/claude")
        out = b.decide("СИСТЕМА\nв две строки", "НАБЛЮДЕНИЕ", obs())
        self.assertEqual(out["data"]["say"], "Пушу")
        self.assertEqual((out["model"], out["stop_reason"], out["cost_usd"]), ("big-model,small-model", "success", 0.01))
        argv = seen["argv"]
        self.assertEqual(argv[:6], ["/opt/bin/claude", "--model", "m", "--effort", "low", "-p"])
        self.assertEqual(seen["system"], "СИСТЕМА\nв две строки")              # промпт — файлом, не строкой
        self.assertNotIn("--system-prompt", argv)
        self.assertIn("--safe-mode", argv)                                     # без CLAUDE.md, хуков, MCP, навыков
        self.assertNotIn("--bare", argv)                                       # --bare не берёт подписку
        self.assertEqual(argv[argv.index("--tools") + 1], "")
        self.assertEqual(argv[argv.index("--disallowedTools") + 1], "mcp__*")
        self.assertIn("--no-session-persistence", argv)
        self.assertEqual(json.loads(argv[argv.index("--json-schema") + 1]), A.DECISION_SCHEMA)
        self.assertEqual(seen["kw"]["input"], "НАБЛЮДЕНИЕ")
        self.assertEqual((seen["kw"]["encoding"], seen["kw"]["errors"]), ("utf-8", "replace"))
        self.assertEqual(seen["kw"]["cwd"], b.cwd)                             # пустая папка: чужой CLAUDE.md не найдётся
        b.decide("СИСТЕМА\nв две строки", "ещё", obs())
        self.assertEqual(seen["argv"][seen["argv"].index("--system-prompt-file") + 1],
                         argv[argv.index("--system-prompt-file") + 1])           # тот же файл, не новый на вызов
        plain = A.CliBackend(runner=run, which=lambda name: None)
        self.assertEqual(plain.argv("s")[:2], ["claude", "-p"])                # не нашёл в PATH — как есть

    def test_failures(self):
        def missing(argv, **kw):
            raise FileNotFoundError

        with self.assertRaises(A.BackendError):
            A.CliBackend(runner=missing).decide("s", "u", obs())
        run, _ = self.runner({"is_error": True, "result": "Not logged in"}, code=1)
        with self.assertRaises(A.BackendError) as cm:
            A.CliBackend(runner=run).decide("s", "u", obs())
        self.assertIn("Not logged in", str(cm.exception))
        self.assertIsNone(cm.exception.retry_after)                           # не вошёл — это не лимит
        run, _ = self.runner({"is_error": True, "result": "Claude AI usage limit reached|1760000000"}, code=1)
        with self.assertRaises(A.BackendError) as cm:
            A.CliBackend(runner=run).decide("s", "u", obs())
        self.assertEqual(cm.exception.retry_after, 600.0)                     # лимит подписки — сторона ждёт
        # кредит API кончился (текст ответа API из документации) — пауза на час, а не стук каждые 3 с
        body = b'{"type":"error","error":{"type":"invalid_request_error","message":"Your credit balance is too low to access the Anthropic API. Please go to Plans & Billing to upgrade or purchase credits."}}'
        err = urllib.error.HTTPError(A.ApiBackend.URL, 400, "Bad Request", {}, io.BytesIO(body))

        def broke(req, timeout=None):
            raise err
        with self.assertRaises(A.BackendError) as cm:
            A.ApiBackend("m", api_key="k", opener=broke).decide("s", "u", obs())
        self.assertEqual(cm.exception.retry_after, 3600.0)
        self.assertIn("кредит API кончился", str(cm.exception))

        def garbage(argv, **kw):
            class P:
                returncode = 2
                stdout = ""
                stderr = "error: unknown option '--safe-mode'"
            return P()

        with self.assertRaises(A.BackendError) as cm:
            A.CliBackend(runner=garbage).decide("s", "u", obs())
        self.assertIn("unknown option", str(cm.exception))                    # старая версия Claude Code — видно, почему

    def test_cli_cost_not_counted_twice(self):
        run, _ = self.runner()
        cli = A.CliBackend(runner=run, which=lambda name: None)
        h = A.AgentHub({"radiant": cli, "dire": FakeBackend()}, sync=True, prices={"in": 1.0, "out": 5.0})
        h.tick({"heroes": [obs(clock=0), obs(clock=0, team="dire")]})
        s = h.summary()
        self.assertEqual(s["cost_cli"], 0.01)
        self.assertAlmostEqual(s["cost_usd_est"], (1000 * 1 + 50 * 5) / 1e6)  # только сторона без своей цены
        self.assertEqual(s["teams"]["radiant"]["in"], 10)

    def test_make_backend(self):
        self.assertIsInstance(A.make_backend("rules"), A.RulesBackend)
        with mock.patch.dict(os.environ, {"ANTHROPIC_API_KEY": "k"}):
            b = A.make_backend("api", "m", effort="medium", thinking="between_tools", max_tokens=1234)
        self.assertEqual((b.effort, b.thinking, b.max_tokens), ("medium", "between_tools", 1234))
        c = A.make_backend("cli", "m", "claude", effort=None)
        self.assertNotIn("--effort", c.argv("s"))
        with self.assertRaises(ValueError):
            A.make_backend("telepathy")


class Args(unittest.TestCase):
    def test_backends_and_personas_from_args(self):
        from voicecoach.server import agent_factory_from_args, main  # noqa: F401
        import argparse
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "vasya.json"
            p.write_text(json.dumps({"name": "Вася", "style": {"aggression": 0.9}}, ensure_ascii=False), encoding="utf-8")
            a = argparse.Namespace(agents="rules", radiant=None, dire=None, model=None, claude="claude", period=4.0,
                                   max_calls=None, personas=None, persona=[f"radiant:1={p}"], price_in=None,
                                   price_out=None, price_cache_read=None, price_cache_write=None, effort="off",
                                   thinking=None, max_tokens=4000)
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
            a.agents, a.dire, a.model, a.effort, a.max_tokens = "api", "rules", "m", "medium", 2000
            with mock.patch.dict(os.environ, {"ANTHROPIC_API_KEY": "k"}):
                _, backends = agent_factory_from_args(a)
            self.assertEqual((backends["radiant"].effort, backends["radiant"].max_tokens), ("medium", 2000))
            self.assertIsInstance(backends["dire"], A.RulesBackend)
            a.effort = "off"
            with mock.patch.dict(os.environ, {"ANTHROPIC_API_KEY": "k"}):
                _, backends = agent_factory_from_args(a)
            self.assertIsNone(backends["radiant"].effort)


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
