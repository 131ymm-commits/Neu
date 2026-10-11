"""Отчёт игры для Claude вместо снимков экрана (просьба автора 11.10.2026: «зделай общюю систему»)."""
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from voicecoach import play as P
from voicecoach import report as R


class ReportTest(unittest.TestCase):
    def test_scrub_hides_personal(self):
        text = ("Журнал: C:\\Users\\M4800\\Desktop\\Дима\\DotaCoach\\coach\\logs\\a.jsonl; пульт "
                "http://127.0.0.1:8788/c/ISY4azvlopco8TvlAORA9w/ и https://abc-def.trycloudflare.com/c/x; "
                "ключ sk-ant-api03-SECRETSECRET; D:\\Users\\Other\\x")
        s = R.scrub(text, home="C:\\Users\\M4800")
        self.assertNotIn("M4800", s)
        self.assertNotIn("ISY4azvlopco8TvlAORA9w", s)
        self.assertNotIn("SECRETSECRET", s)
        self.assertNotIn("abc-def", s)
        self.assertNotIn("Other", s)
        self.assertIn("%USERPROFILE%\\Desktop", s)

    def test_drive_folder_detection(self):
        seen = []

        def exists(p):
            seen.append(p)
            return p.endswith("Мой диск")
        got = R.drive_folder(home="/home/u", exists=exists)
        self.assertEqual(got.name, "DotaCoach")
        self.assertEqual(got.parent.name, "Мой диск")
        self.assertIsNone(R.drive_folder(home="/home/u", exists=lambda p: False))

    def test_build_and_write_both_places(self):
        with tempfile.TemporaryDirectory() as tmp:
            logs, drive = Path(tmp) / "logs", Path(tmp) / "drive" / "DotaCoach"
            text = R.build({"Окно": "строка 1\nC:\\Users\\M4800\\x", "Пусто": "", "Агенты": {"radiant": {"calls": 3}}})
            self.assertIn("===== Окно =====", text)
            self.assertNotIn("Пусто", text)
            self.assertIn('"calls": 3', text)
            done = R.write(text, logs, R.LIVE_NAME, drive)
            self.assertEqual([p.parent for p in done], [logs, drive])
            self.assertEqual((drive / R.LIVE_NAME).read_text(encoding="utf-8"), text)
            self.assertTrue(R.final_name().startswith(R.FINAL_PREFIX))
            self.assertIn("…(начало обрезано)…", R.tail("x" * 100, 10))

    def test_agent_samples_and_dota_lines(self):
        with tempfile.TemporaryDirectory() as tmp:
            log = Path(tmp) / "agents.jsonl"
            recs = [{"clock": c, "team": "radiant", "pos": 1, "hero": "sniper", "decision": {"plan": "farm"},
                     "model": "m"} for c in range(40)]
            recs.append({"clock": 41, "error": "таймаут", "team": "dire", "pos": 2})
            recs.append({"clock": 42, "lesson": {"text": "урок"}, "decision": {"plan": "farm"}})
            log.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in recs) + "\nне json\n", encoding="utf-8")
            text, counts = R.agent_samples(log)
            self.assertEqual((counts["записей"], counts["ошибок"], counts["решений"], counts["уроков"]), (42, 1, 41, 1))
            self.assertIn("таймаут", text)
            self.assertIn('"clock": 0', text)                                  # начало матча
            self.assertNotIn('"clock": 20,', text)                             # середина — не вся
            self.assertEqual(R.agent_samples(Path(tmp) / "нет.jsonl")[1]["записей"], 0)
        dota = "шум движка\n[VScript] [ТРЕНЕР] пульс: связь есть\nScript Error: coach_exec.lua:12: x\nещё шум"
        self.assertEqual(R.dota_lines(dota).splitlines(), ["[VScript] [ТРЕНЕР] пульс: связь есть",
                                                           "Script Error: coach_exec.lua:12: x"])


class LauncherReport(unittest.TestCase):
    def test_final_report_drive_or_reveal(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            wlog = tmp / "launcher.log"
            wlog.write_text("[1/6] Агенты героев\n  Героев ведёт Claude\n", encoding="utf-8")
            hub = SimpleNamespace(progress=lambda: {"radiant": {"claude": True}}, summary=lambda: {"paid_calls": 5})
            reports = {"wlog": wlog, "dlog": None, "room": SimpleNamespace(agents=hub), "log": None,
                       "drive": tmp / "drive" / "DotaCoach"}
            out, shown = [], []
            with mock.patch.object(P, "LOGS", tmp / "logs"), mock.patch.object(P, "say", out.append):
                done = P.final_report(reports, learned=[{"team": "radiant", "pos": 1, "hero": "sniper", "match": 1,
                                                         "row": {}, "verdicts": [], "added": ["урок"], "say": ""}])
                self.assertEqual(len(done), 2)
                self.assertTrue(any("Google Диске" in x for x in out))
                text = (tmp / "drive" / "DotaCoach" / R.LIVE_NAME).read_text(encoding="utf-8")
                for need in ("Героев ведёт Claude", '"paid_calls": 5', "Обучение (Д20)", "урок"):
                    self.assertIn(need, text)
                reports["drive"] = None
                out.clear()
                done = P.final_report(reports, reveal_file=shown.append)
                self.assertEqual(shown, done[:1])                              # без Google Диска — открыть папку
                self.assertTrue(any("перетащите этот файл в чат" in x for x in out))


if __name__ == "__main__":
    unittest.main()
