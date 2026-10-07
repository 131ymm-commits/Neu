"""Короткий формат команд (voicecoach/textcmd.py).

Примеры — coach/data/text_cases.json; их же гоняет тест Lua-версии (game/tests/test_coach_text.py),
чтобы разбор в чате игры совпадал с разбором на странице тренера.
"""
import json
import unittest
from pathlib import Path

from voicecoach import Agent, MatchContext, parse
from voicecoach.textcmd import (ACTION_CANON, ACTION_WORDS, HERO_ALIAS, HERO_CANON, ITEM_CANON, ITEMS,
                                lua_data, parse_short, suggest, to_short)

HERE = Path(__file__).resolve().parent
DATA = HERE.parent / "data"
CASES = json.loads((DATA / "text_cases.json").read_text(encoding="utf-8"))
GAME = HERE.parent.parent / "game"


def make_ctx(name):
    d = CASES["contexts"][name]
    return MatchContext(team=d["team"], agents=[Agent(a["pos"], a["name"], tuple(a["aliases"]), a["hero"])
                                                for a in d["agents"]],
                        enemy_heroes=list(d["enemy_heroes"]))


def short(c):
    return {"action": c.action, "agents": c.agents, "params": c.params, "urgent": c.urgent,
            "after_prev": c.after_prev}


class SharedCases(unittest.TestCase):
    def test_cases(self):
        for case in CASES["cases"]:
            with self.subTest(text=case["text"]):
                r = parse_short(case["text"], make_ctx(case["ctx"]))
                self.assertEqual(r.errors, [])
                self.assertEqual([short(c) for c in r.commands], case["expect"])

    def test_errors(self):
        for case in CASES["errors"]:
            with self.subTest(text=case["text"]):
                r = parse_short(case["text"], make_ctx(case["ctx"]))
                self.assertEqual(r.commands, [], "при ошибке ничего не уходит агентам")
                self.assertTrue(any(case["error_contains"] in e for e in r.errors), r.errors)


class RoundTrip(unittest.TestCase):
    """Всё, что понимает свободный разборщик, записывается коротким форматом и читается обратно
    той же командой: подсказка тренеру не врёт."""

    INTERNAL = {"group", "check", "about"}       # внутренние параметры разборщика, в формат не входят

    def phrases(self):
        out = []
        for name in ("heldout_phrases.jsonl", "heldout_phrases_02.jsonl"):
            p = HERE / name
            if p.exists():
                out += [json.loads(l)["text"] for l in p.read_text(encoding="utf-8").splitlines() if l.strip()]
        return out

    def test_free_parse_to_short_and_back(self):
        ctx = make_ctx("dire")
        n = 0
        for text in self.phrases():
            free = parse(text, MatchContext(team=ctx.team, agents=ctx.agents, enemy_heroes=ctx.enemy_heroes))
            good = [c for c in free.commands if not c.clarify and c.agents]
            if not good:
                continue
            s = suggest(free.commands, ctx)
            back = parse_short(s, ctx)
            with self.subTest(text=text, short=s):
                self.assertEqual(back.errors, [])
                # «auto» (линия/зона на выбор агента) и отсутствие параметра — одно и то же
                norm = lambda c: dict(short(c), params={k: v for k, v in c.params.items()
                                                        if k not in self.INTERNAL and v != "auto"})
                self.assertEqual([norm(c) for c in back.commands], [norm(c) for c in good])
            n += 1
        self.assertGreater(n, 100)


class Vocabulary(unittest.TestCase):
    def test_canon_words_parse_back(self):
        for action, word in ACTION_CANON.items():
            self.assertEqual(ACTION_WORDS[word], action)
        for hero, word in HERO_CANON.items():
            self.assertEqual(HERO_ALIAS[word], hero)
        for item, word in ITEM_CANON.items():
            self.assertEqual(ITEMS[word], item)

    def test_lua_data_is_fresh(self):
        """game/shared/coach_text_data.lua собран из этого словаря и не устарел."""
        path = GAME / "shared" / "coach_text_data.lua"
        self.assertTrue(path.exists(), "соберите: python -m voicecoach.textcmd --lua ../game/shared/coach_text_data.lua")
        self.assertEqual(path.read_text(encoding="utf-8"), lua_data())


class Misc(unittest.TestCase):
    def test_whole_line_or_nothing(self):
        r = parse_short("1 фарм лес. 2 летай", make_ctx("radiant"))
        self.assertEqual(r.commands, [])
        self.assertEqual(len(r.errors), 1)

    def test_suggestion_skips_clarify(self):
        ctx = make_ctx("radiant")
        free = parse("купи бкб", ctx)                 # адресат неясен — переспрос, в подсказку не идёт
        self.assertEqual(suggest(free.commands, ctx), "")


if __name__ == "__main__":
    unittest.main()
