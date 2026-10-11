"""Обучение агентов (Д20): память героя между матчами, проверка уроков числами, числа матча от игры."""
import json
import random
import tempfile
import unittest
from pathlib import Path

from voicecoach import learning as L


def obs(clock, lh=0, dn=0, d=0, lvl=1, seen=0, idle=0, alive=True, **kw):
    o = {"clock": clock, "alive": alive, "lvl": lvl,
         "stats": {"lh": lh, "dn": dn, "k": 0, "d": d, "a": 0, "seen": seen, "idle": idle}}
    if alive:
        o["hp"] = kw.pop("hp", [600, 600])
    o.update(kw)
    return o


class MemoryTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.root = Path(self.dir.name) / "memory"
        self.t = [1000.0]
        self.m = L.Memory(self.root, now=lambda: self.t[0], rng=random.Random(1))

    def tearDown(self):
        self.dir.cleanup()

    def test_coach_verbatim_agent_needs_metric_and_ref(self):
        self.assertEqual(self.m.add("npc_dota_hero_sniper", "  «Не ходи под вражескую вышку»  ", L.COACH), "новый")
        self.assertIsNone(self.m.add("sniper", "Стой у своей волны", L.DEATH))                     # без меры
        self.assertIsNone(self.m.add("sniper", "Стой у своей волны", L.DEATH, metric="deaths"))    # без опоры
        self.assertIsNone(self.m.add("sniper", "Стой у своей волны", L.DEATH, metric="мана", ref="5:11"))
        self.assertEqual(self.m.add("sniper", "Стой у своей волны", L.DEATH, metric="deaths", ref="смерть 5:11"),
                         "новый")
        again = L.Memory(self.root)                                          # другой процесс — с диска
        rows = again.lessons("sniper")
        self.assertEqual([(r["status"], r["text"]) for r in rows],
                         [(L.COACH, "Не ходи под вражескую вышку"), (L.TRIAL, "Стой у своей волны")])
        self.assertEqual((rows[1]["metric"], rows[1]["ref"]), ("deaths", "смерть 5:11"))
        data = json.loads((self.root / "sniper.json").read_text(encoding="utf-8"))
        self.assertEqual(len(data["lessons"]), 2)

    def test_repeat_is_not_a_vote(self):
        """research/06: повтор урока после той же ошибки — скорее знак, что урок не работает, а не голос «за»."""
        self.m.add("lion", "Не стой впереди керри под ударами двух героев", L.TRAIN, metric="deaths", ref="3:10")
        self.assertEqual(self.m.add("lion", "не стой впереди керри под ударами двух героев!", L.DEATH, metric="deaths",
                                    ref="4:00"), "повтор")
        row = self.m.lessons("lion")[0]
        self.assertEqual((row["status"], row["repeats"]), (L.TRIAL, 1))

    def test_random_control_and_judgement_by_numbers(self):
        """Урок на испытании включается в половине матчей; после 2 матчей с ним и 2 без код сравнивает меру."""
        self.m.add("axe", "Тренер: стой у своей вышки до 6 уровня", L.COACH)
        self.m.add("axe", "Отходи к своей вышке, когда двое врагов рядом", L.DEATH, metric="deaths", ref="смерть 4:12")
        self.m.add("axe", "Прыгай на керри врага первым", L.TRAIN, metric="deaths", ref="пауза 3:00")
        ids = {r["text"]: r["id"] for r in self.m.lessons("axe")}
        good, bad = ids["Отходи к своей вышке, когда двое врагов рядом"], ids["Прыгай на керри врага первым"]
        coach = ids["Тренер: стой у своей вышки до 6 уровня"]
        on_counts = {good: 0, bad: 0}
        for _ in range(200):
            on = self.m.plan_match("axe")
            self.assertIn(coach, on)                                         # тренер — всегда
            for k in on_counts:
                on_counts[k] += k in on
        for k, c in on_counts.items():
            self.assertTrue(70 <= c <= 130, (k, c))                          # примерно в половине
        # с хорошим уроком смертей меньше, с плохим — больше
        plan = [({good}, 1), (set(), 3), ({good, bad}, 4), ({bad}, 5), (set(), 3), ({good}, 1)]
        verdicts = []
        for on, deaths in plan:
            _, v = self.m.record("axe", {"lh10": 20, "d10": deaths, "idle10": 30, "lvl10": 5}, on | {coach})
            verdicts += v
        rows = {r["text"]: r for r in self.m.lessons("axe")}
        self.assertEqual(rows["Отходи к своей вышке, когда двое врагов рядом"]["status"], L.PROVEN)
        self.assertNotIn("Прыгай на керри врага первым", rows)
        self.assertTrue(any(v.startswith("проверен") for v in verdicts))
        self.assertTrue(any("с ним хуже" in v for v in verdicts))
        self.assertEqual(self.m.matches("axe"), 6)
        self.assertEqual(self.m.history("axe")[0]["on"], sorted({good, coach}))

    def test_undecided_lesson_leaves_after_max_trials(self):
        self.m.add("cm", "Ставь вард у Т1 на 1:30", L.REVIEW, metric="lvl", ref="разбор")
        lid = self.m.lessons("cm")[0]["id"]
        for i in range(L.MAX_TRIALS):                                        # всё время включён — сравнить не с чем
            self.m.record("cm", {"lvl10": 5, "d10": 1, "lh10": 3}, {lid})
        self.assertEqual(self.m.lessons("cm"), [])
        short = L.Memory(None)                                               # матч короче 10 минут — не испытание
        short.add("cm", "Денай дальнего крипа", L.TRAIN, metric="lh", ref="пауза 2:00")
        short.record("cm", {"lh5": 3}, set())
        self.assertEqual(short.lessons("cm")[0]["trials"], [])

    def test_caps(self):
        for i in range(L.MAX_TRIAL + 3):
            self.t[0] += 1
            self.m.add("viper", f"урок {i}: держись в {i * 100 + 300} от вышки", L.TRAIN, metric="deaths", ref=f"{i}:00")
        rows = self.m.lessons("viper")
        self.assertEqual(len(rows), L.MAX_TRIAL)
        self.assertNotIn("урок 0: держись в 300 от вышки", [r["text"] for r in rows])     # самые старые — вон
        for i in range(L.MAX_COACH + 2):
            self.m.add("viper", f"приказ {i}: отходи при {i * 5 + 20}% здоровья", L.COACH)
        self.assertEqual(len([r for r in self.m.lessons("viper") if r["status"] == L.COACH]), L.MAX_COACH)

    def test_prompt_block_and_training_rate(self):
        self.assertIn("Уроков пока нет", self.m.prompt_block("luna"))
        self.m.add("luna", "Не дерись до 6 уровня", L.COACH)
        self.m.add("luna", "Добивай дальнего крипа первым", L.TRAIN, metric="lh", ref="пауза 2:00")
        ids = [r["id"] for r in self.m.lessons("luna")]
        block = self.m.prompt_block("luna", {ids[0]})
        self.assertIn("[тренер] Не дерись до 6 уровня", block)
        self.assertNotIn("Добивай", block)                                   # не включён в этот матч
        self.assertIn("[на испытании] Добивай дальнего крипа первым", self.m.prompt_block("luna", set(ids)))
        self.assertEqual(self.m.train_every("luna"), L.TRAIN_EVERY_EARLY)
        for _ in range(L.EARLY_MATCHES):
            self.m.record("luna", {}, set())
        self.assertIsNone(self.m.train_every("luna"))                        # дальше — только по порогу

    def test_similar_and_broken_file(self):
        self.assertTrue(L.similar("Не стой под вышкой", "не стой под вышкой!"))
        self.assertFalse(L.similar("Добивай дальнего крипа первым", "Денай дальнего крипа первым"))
        self.assertFalse(L.similar("отходи при 30% здоровья", "отходи при 50% здоровья"))
        self.root.mkdir(parents=True)
        (self.root / "lina.json").write_text("{не json", encoding="utf-8")
        self.assertEqual(self.m.lessons("lina"), [])
        self.assertEqual(self.m.add("lina", "Бей Dragon Slave по волне после 10:00", L.REVIEW, metric="lh",
                                    ref="разбор"), "новый")


class TrackerTest(unittest.TestCase):
    def test_death_facts_snapshots_and_windows(self):
        tr = L.Tracker()
        tr.update(obs(0))
        tr.update(obs(150, lh=3, seen=8, idle=20, lvl=2))
        self.assertTrue(tr.train_due(150, 120))
        self.assertFalse(tr.train_due(150, None))                            # плановых пауз нет — только по порогу
        w = tr.window()
        self.assertEqual((w["lh"], w["seen"], w["idle"], w["from"], w["to"]), (3, 8, 20, 0, 150))
        self.assertIn("добил 3 из 8", L.window_text(w))
        self.assertIn("пропустил 5", L.window_text(w))
        self.assertFalse(tr.train_due(200, 120))
        before = obs(310, lh=6, seen=14, lvl=3, hp=[90, 600], where="бот, их Т1, 650", doing="фарм бот: добиваю",
                     enemies=[{"hero": "luna", "d": 400}, {"hero": "lina", "d": 2500}],
                     near={"enemy_tower": "Т1 bot, 650"})
        tr.update(before)
        tr.update(obs(311, lh=6, seen=14, d=1, lvl=3, alive=False, events=["5:11 тебя убил luna"]))
        self.assertEqual(tr.at5["lh"], 6)
        text = tr.death_text()
        for part in ("5:11", "убил luna", "бот, их Т1", "15%", "luna 400", "вражеская вышка рядом: Т1 bot, 650",
                     "руки делали: фарм бот: добиваю"):
            self.assertIn(part, text)
        self.assertNotIn("lina", text)
        tr.update(obs(320, lh=6, seen=15, d=1, lvl=3, alive=False, events=["5:11 тебя убил luna"]))
        self.assertEqual(len(tr.deaths), 1)
        tr.update(obs(620, lh=20, dn=4, seen=30, d=1, lvl=6, idle=90))
        tr.update(obs(700, lh=25, dn=5, seen=36, d=2, lvl=7, idle=100))
        row = tr.match_row()
        self.assertEqual((row["lh10"], row["seen10"], row["dn10"], row["d10"], row["lvl10"]), (20, 30, 4, 1, 6))
        self.assertEqual(L.metric_value(row, "deaths"), 1)
        self.assertEqual(row["deaths"], ["5:11 luna, бот, их Т1, 650"])
        self.assertIn("к 10:00: добивания 20 (из 30 умерших рядом)", L.row_text(row))

    def test_alarm_by_threshold(self):
        """research/06: паузы по событию — пропущено ≥ 3 добиваний или простой ≥ 20 с за минуту; не чаще раза в
        минуту; после 10:00 — нет."""
        tr = L.Tracker()
        for c in range(0, 61, 5):
            tr.update(obs(c, lh=0, seen=c // 15))                            # 4 крипа умерли рядом, добил 0
        self.assertIn("пропущено 4 добиваний", tr.alarm(60))
        self.assertEqual(tr.alarm(70), "")                                   # не чаще раза в минуту
        for c in range(65, 131, 5):
            tr.update(obs(c, lh=4, seen=4 + (c - 60) // 30, idle=(c - 60) // 2))
        self.assertIn("руки стояли без дела", tr.alarm(130))
        late = L.Tracker()
        for c in range(600, 661, 5):
            late.update(obs(c, seen=c // 10))
        self.assertEqual(late.alarm(660), "")


if __name__ == "__main__":
    unittest.main()
