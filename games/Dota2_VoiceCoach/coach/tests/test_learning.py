"""Обучение агентов (Д20): память героя между матчами и числа матча от игры."""
import json
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
        self.m = L.Memory(self.root, now=lambda: self.t[0])

    def tearDown(self):
        self.dir.cleanup()

    def tick(self):
        self.t[0] += 1

    def test_lessons_persist_and_coach_first(self):
        self.assertEqual(self.m.add("npc_dota_hero_sniper", "Стой у своей волны, а не у вышки", L.DEATH), "новый")
        self.tick()
        self.assertEqual(self.m.add("sniper", "  «Не ходи под вражескую вышку»  ", L.COACH), "новый")
        again = L.Memory(self.root)                                   # другой процесс — с диска
        rows = again.lessons("sniper")
        self.assertEqual([r["src"] for r in rows], [L.COACH, L.DEATH])
        self.assertEqual(rows[0]["text"], "Не ходи под вражескую вышку")
        block = again.prompt_block("sniper")
        self.assertIn("1. [тренер] Не ходи под вражескую вышку", block)
        self.assertIn("2. [смерть] Стой у своей волны", block)
        data = json.loads((self.root / "sniper.json").read_text(encoding="utf-8"))
        self.assertEqual(len(data["lessons"]), 2)

    def test_repeat_raises_weight_but_not_for_coach(self):
        self.m.add("lion", "Не стой впереди керри под ударами двух героев", L.TRAIN)
        self.assertEqual(self.m.add("lion", "не стой впереди керри под ударами двух героев!", L.DEATH), "повтор")
        self.assertEqual(self.m.lessons("lion")[0]["w"], 1)
        self.m.add("lion", "Денай своих крипов", L.COACH)
        self.assertEqual(self.m.add("lion", "денай своих крипов", L.COACH), "повтор")
        coach = [r for r in self.m.lessons("lion") if r["src"] == L.COACH]
        self.assertEqual((len(coach), coach[0]["w"]), (1, 0))
        self.assertIsNone(self.m.add("lion", "   ", L.DEATH))
        self.assertIsNone(self.m.add("lion", "что-то", "выдумка"))

    def test_vote_removes_harmful_and_keeps_coach(self):
        self.m.add("axe", "Прыгай в драку первым без союзников", L.DEATH)
        self.tick()
        self.m.add("axe", "Стой у своей волны на линии", L.TRAIN)
        self.tick()
        self.m.add("axe", "Не отходи далеко от линии до 10:00", L.COACH)
        shown = self.m.lessons("axe")                                 # 1 тренер, 2 и 3 — свои
        self.assertEqual(shown[0]["src"], L.COACH)
        harmful = next(i for i, r in enumerate(shown, 1) if "Прыгай" in r["text"])
        good = next(i for i, r in enumerate(shown, 1) if "волны" in r["text"])
        self.assertEqual(self.m.vote("axe", shown, up=[good, 1], down=[harmful, 1, 99, "x"]), (1, 1))
        rows = self.m.lessons("axe")
        self.assertEqual([r["text"] for r in rows], ["Не отходи далеко от линии до 10:00", "Стой у своей волны на линии"])
        self.assertEqual(rows[1]["w"], 1)

    def test_caps_drop_weakest_oldest(self):
        for i in range(L.MAX_LEARNED + 3):
            self.tick()
            self.m.add("cm", f"урок {i}: держись в {i * 100 + 300} от вышки", L.TRAIN)
        rows = self.m.lessons("cm")
        self.assertEqual(len(rows), L.MAX_LEARNED)
        self.assertNotIn("урок 0: держись в 300 от вышки", [r["text"] for r in rows])     # самый старый — вон
        for i in range(L.MAX_COACH + 2):
            self.m.add("cm", f"приказ {i}: отходи при {i * 5 + 20}% здоровья", L.COACH)
        self.assertEqual(len([r for r in self.m.lessons("cm") if r["src"] == L.COACH]), L.MAX_COACH)

    def test_similar(self):
        self.assertTrue(L.similar("Не стой под вышкой", "не стой под вышкой!"))
        self.assertFalse(L.similar("Добивай дальнего крипа первым", "Денай дальнего крипа первым"))
        self.assertFalse(L.similar("отходи при 30% здоровья", "отходи при 50% здоровья"))

    def test_matches_history_and_training_rate(self):
        self.assertEqual(self.m.train_every("viper"), L.TRAIN_EVERY_EARLY)
        for i in range(L.EARLY_MATCHES):
            self.assertEqual(self.m.record("viper", {"lh10": i}), i + 1)
        self.assertEqual(self.m.matches("viper"), L.EARLY_MATCHES)
        self.assertEqual(self.m.train_every("viper"), L.TRAIN_EVERY)
        self.assertEqual([r["lh10"] for r in self.m.history("viper")], list(range(L.EARLY_MATCHES)))

    def test_broken_file_and_disabled_memory(self):
        self.root.mkdir(parents=True)
        (self.root / "luna.json").write_text("{не json", encoding="utf-8")
        self.assertEqual(self.m.lessons("luna"), [])
        self.assertEqual(self.m.add("luna", "Добивай дальнего крипа первым", L.DEATH), "новый")
        off = L.Memory(None)
        off.add("luna", "урок без диска", L.DEATH)
        self.assertEqual(len(off.lessons("luna")), 1)
        self.assertIn("Уроков пока нет", off.prompt_block("lina"))


class TrackerTest(unittest.TestCase):
    def test_death_facts_snapshots_and_windows(self):
        tr = L.Tracker()
        tr.update(obs(0))
        tr.update(obs(150, lh=3, seen=8, idle=20, lvl=2))
        self.assertTrue(tr.train_due(150, 120))
        w = tr.window()
        self.assertEqual((w["lh"], w["seen"], w["idle"], w["from"], w["to"]), (3, 8, 20, 0, 150))
        self.assertIn("добил 3 из 8", L.window_text(w))
        self.assertIn("пропустил 5", L.window_text(w))
        self.assertFalse(tr.train_due(200, 120))                       # новый отрезок начался в 2:30
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
        self.assertNotIn("lina", text)                                # дальше 1500 — не «рядом»
        tr.update(obs(320, lh=6, seen=15, d=1, lvl=3, alive=False, events=["5:11 тебя убил luna"]))
        self.assertEqual(len(tr.deaths), 1)                           # мёртв дальше — та же смерть
        tr.update(obs(620, lh=20, dn=4, seen=30, d=1, lvl=6, idle=90))
        tr.update(obs(700, lh=25, dn=5, seen=36, d=2, lvl=7, idle=100))
        row = tr.match_row()
        self.assertEqual((row["lh10"], row["seen10"], row["dn10"], row["d10"], row["lvl10"]), (20, 30, 4, 1, 6))
        self.assertEqual((row["lh"], row["end_clock"]), (25, 700))
        self.assertEqual(row["deaths"], ["5:11 luna, бот, их Т1, 650"])
        self.assertIn("к 10:00: добивания 20 (из 30 умерших рядом)", L.row_text(row))
        self.assertFalse(tr.train_due(700, 120))                      # после 10:00 — без учебных пауз


if __name__ == "__main__":
    unittest.main()
