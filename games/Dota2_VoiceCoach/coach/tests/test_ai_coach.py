"""ИИ-тренер соперника (решение Д16): командует Тьмой коротким форматом тем же путём, что пульт друга; молчит, пока
друг на пульте; без Claude — правила. Настоящий сервер игры (комната, разбор приказов), мотор Claude подменён."""
import json
import os
import tempfile
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from voicecoach import agents as A
from voicecoach import ai_coach as AI
from voicecoach.server import serve

from tests.test_console import MAP, hero, payload


def towers_map():
    """Вышки обеих сторон: у Света (врага Тьмы) т1 стоят на топе и миде, на боте т1 уже нет — осталась т2.
    Правила берут сначала ближние вышки (т1), при равных — бот, мид, топ: значит, мид т1."""
    towers = [{"team": "radiant", "lane": "top", "tier": 1, "x": -6000, "y": 1800, "alive": True},
              {"team": "radiant", "lane": "mid", "tier": 1, "x": -1500, "y": -1400, "alive": True},
              {"team": "radiant", "lane": "bot", "tier": 1, "x": 4900, "y": -6100, "alive": False},
              {"team": "radiant", "lane": "bot", "tier": 2, "x": 0, "y": -6300, "alive": True},
              {"team": "dire", "lane": "mid", "tier": 1, "x": 500, "y": 650, "alive": True}]
    return {**MAP, "towers": towers}


class Coach(unittest.TestCase):
    def setUp(self):
        self.srv = serve("127.0.0.1", 0, lambda name: A.AgentHub(
            {"radiant": A.RulesBackend(), "dire": A.RulesBackend()}, sync=True))
        self.room = self.srv.hub.room("local")
        self.tmp = tempfile.TemporaryDirectory()
        self.log = Path(self.tmp.name) / "ai_coach.jsonl"

    def tearDown(self):
        self.srv.server_close()
        self.tmp.cleanup()

    def tick(self, clock):
        p = payload(clock=clock, map=towers_map())
        names = ["luna", "lina", "bristleback", "witch_doctor", "jakiro"]
        p["heroes"] = [h for h in p["heroes"] if h["team"] == "radiant"] + [
            hero("dire", pos, names[pos - 1], (100 * pos, 100 * pos)) for pos in range(1, 6)]   # пятеро Тьмы живы
        p["heroes"][2]["missing"] = [{"hero": "viper", "seen": "мид", "ago": 40}]
        for h in p["heroes"]:
            h["clock"] = clock
        self.room.on_tick(p)

    def records(self):
        return [json.loads(x) for x in self.log.read_text(encoding="utf-8").splitlines()]

    def test_rules_coach_pushes_weakest_tower_and_waits_early(self):
        coach = AI.AICoach(self.room, "dire", AI.RulesCoach(), log_path=self.log)
        self.tick(300)
        self.assertEqual(coach.step(), [])                                   # ранняя игра: агенты фармят сами
        self.tick(900)
        got = coach.step()
        self.assertEqual([g["text"] for g in got], ["все-1 пуш мид т1"])
        self.assertTrue(got[0]["queued"])                                     # разобран как у пульта, в очереди
        self.assertEqual(self.room.remote[-1]["team"], "dire")
        self.assertEqual(self.records()[-1]["backend"], "правила")

    def test_silent_while_friend_on_console_or_no_game(self):
        coach = AI.AICoach(self.room, "dire", AI.RulesCoach())
        self.assertEqual(coach.step(), [])                                   # игры нет — молчит
        self.tick(900)
        self.room.console_seen["dire"] = time.time()                          # друг открыл пульт
        self.assertEqual(coach.step(), [])
        self.assertEqual(self.room.remote, [])
        self.room.console_seen["dire"] = time.time() - AI.FRIEND_FRESH - 1    # ушёл — тренер снова командует
        self.assertTrue(coach.step())

    def test_claude_coach_orders_checked_like_console(self):
        seen = []

        def run(argv, **kw):
            seen.append((argv, kw))
            out = {"is_error": False, "result": "",
                   "structured_output": {"orders": ["все-1 пуш бот т2", "чепуха какая-то", "3 ульт марс !", "лишний"],
                                         "why": "у врага слабый бот"}}
            return SimpleNamespace(stdout=json.dumps(out), stderr="", returncode=0)
        with mock.patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-should-not-leak"}):
            coach = AI.AICoach(self.room, "dire", AI.ClaudeCoach("claude", runner=run), log_path=self.log)
            self.tick(900)
            got = coach.step()
        self.assertEqual([g["text"] for g in got], ["все-1 пуш бот т2", "чепуха какая-то", "3 ульт марс !"])   # не больше 3
        self.assertTrue(got[0]["queued"])
        self.assertFalse(got[1]["queued"])                                    # неверный — в игру не ушёл
        argv, kw = seen[0]
        self.assertEqual(argv[argv.index("--model") + 1], "haiku")
        self.assertIn("--json-schema", argv)
        self.assertNotIn("ANTHROPIC_API_KEY", kw["env"])                      # по подписке, не по ключу
        view = json.loads(kw["input"])
        self.assertEqual(view["часы"], "15:00")                                # часы как в игре, не секунды
        self.assertEqual(view["события_за_2_минуты"], [])                     # «4:50 у них погиб axe» — давно
        self.assertNotIn("СЕКРЕТ", kw["input"])                               # туман войны: чужие наблюдения не видны
        self.assertEqual(self.records()[-1]["why"], "у врага слабый бот")

    def test_limit_switches_to_rules_for_a_while(self):
        calls = []

        def run(argv, **kw):
            calls.append(1)
            return SimpleNamespace(stdout=json.dumps({"is_error": True, "result": "You've hit your session limit"}),
                                   stderr="", returncode=1)
        now = [1000.0]
        coach = AI.AICoach(self.room, "dire", AI.ClaudeCoach("claude", runner=run), log_path=self.log,
                           clock=lambda: now[0])
        self.tick(900)
        got = coach.step()
        self.assertEqual([g["text"] for g in got], ["все-1 пуш мид т1"])         # правила вместо Claude
        self.assertIn("session limit", self.records()[-1]["error"])
        coach.step()
        self.assertEqual(len(calls), 1)                                         # пауза: Claude не дёргаем
        now[0] += AI.LIMIT_PAUSE + 1
        coach.step()
        self.assertEqual(len(calls), 2)                                         # пауза кончилась — снова Claude


    def test_claude_calls_capped_then_rules(self):
        """Рецензия 6: ИИ-тренер звал Claude без потолка — теперь свой предел, дальше правила; считает вызовы."""
        calls = []

        def run(argv, **kw):
            calls.append(1)
            out = {"is_error": False, "structured_output": {"orders": ["все-1 пуш бот т2"], "why": "давим"}}
            return SimpleNamespace(stdout=json.dumps(out), stderr="", returncode=0)
        coach = AI.AICoach(self.room, "dire", AI.ClaudeCoach("claude", runner=run), max_calls=2)
        self.tick(900)
        for _ in range(4):
            coach.step()
        self.assertEqual((len(calls), coach.claude_calls), (2, 2))
        coach.close()

    def test_no_json_answer_falls_back_to_rules(self):
        def run(argv, **kw):
            return SimpleNamespace(stdout=json.dumps({"is_error": False, "result": "не знаю"}), stderr="", returncode=0)
        coach = AI.AICoach(self.room, "dire", AI.ClaudeCoach("claude", runner=run), log_path=self.log)
        self.tick(900)
        self.assertEqual([g["text"] for g in coach.step()], ["все-1 пуш мид т1"])
        self.assertIn("без JSON", self.records()[-1]["error"])

    def test_friend_arrives_while_coach_thinks(self):
        coach = None

        def run(argv, **kw):
            self.room.console_seen["dire"] = time.time()                       # пока Claude думал, друг открыл пульт
            out = {"is_error": False, "structured_output": {"orders": ["все назад"]}}
            return SimpleNamespace(stdout=json.dumps(out), stderr="", returncode=0)
        coach = AI.AICoach(self.room, "dire", AI.ClaudeCoach("claude", runner=run))
        self.tick(900)
        self.assertEqual(coach.step(), [])
        self.assertEqual(self.room.remote, [])


if __name__ == "__main__":
    unittest.main()
