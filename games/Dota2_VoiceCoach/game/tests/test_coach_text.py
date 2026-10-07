"""Короткий формат на Lua (game/shared/coach_text.lua) — тот же разбор, что на странице тренера.

Сверка: общие примеры coach/data/text_cases.json и разбор Lua против Python (textcmd.py) на сотнях
строк — сырых фраз наборов PARSE-01/02 (почти все — ошибки формата) и подсказок по ним (верный формат).
"""
import json
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
GAME = HERE.parent
COACH = GAME.parent / "coach"
sys.path.insert(0, str(COACH))

try:
    from lupa import luajit21 as lupa_rt
except ImportError:                      # pragma: no cover
    from lupa import lua51 as lupa_rt


from voicecoach import Agent, MatchContext, parse  # noqa: E402
from voicecoach.server import to_lua  # noqa: E402
from voicecoach.textcmd import parse_short, suggest  # noqa: E402

CASES = json.loads((COACH / "data" / "text_cases.json").read_text(encoding="utf-8"))


def py_ctx(name):
    d = CASES["contexts"][name]
    return MatchContext(team=d["team"], agents=[Agent(a["pos"], a["name"], tuple(a["aliases"]), a["hero"])
                                                for a in d["agents"]], enemy_heroes=list(d["enemy_heroes"]))


def to_py(v):
    if lupa_rt.lua_type(v) != "table":
        return v
    keys = list(v.keys())
    if keys and all(isinstance(k, int) for k in keys) and sorted(keys) == list(range(1, len(keys) + 1)):
        return [to_py(v[k]) for k in range(1, len(keys) + 1)]
    if not keys:
        return {}
    return {k: to_py(v[k]) for k in keys}


class LuaText(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.L = lupa_rt.LuaRuntime(unpack_returned_tuples=True)
        data = cls.L.execute(f'return dofile("{(GAME / "shared" / "coach_text_data.lua").as_posix()}")')
        cls.T = cls.L.execute(f'return dofile("{(GAME / "shared" / "coach_text.lua").as_posix()}")')
        cls.T.init(data)
        cls.ctx = {name: cls.L.execute("return " + to_lua(d)) for name, d in CASES["contexts"].items()}

    def lua_parse(self, text, ctx_name):
        r = to_py(self.T.parse(text, self.ctx[ctx_name]))
        cmds = r.get("commands") or []
        if isinstance(cmds, dict):
            cmds = []
        return [{"action": c["action"], "agents": c["agents"], "params": c.get("params") or {},
                 "urgent": bool(c["urgent"]), "after_prev": bool(c["after_prev"])} for c in cmds], \
            (r.get("errors") or []) if not isinstance(r.get("errors"), dict) else []

    def py_parse(self, text, ctx_name):
        r = parse_short(text, py_ctx(ctx_name))
        return [{"action": c.action, "agents": c.agents, "params": c.params, "urgent": c.urgent,
                 "after_prev": c.after_prev} for c in r.commands], r.errors

    def test_shared_cases(self):
        for case in CASES["cases"]:
            with self.subTest(text=case["text"]):
                cmds, errs = self.lua_parse(case["text"], case["ctx"])
                self.assertEqual(errs, [])
                self.assertEqual(cmds, case["expect"])

    def test_shared_errors(self):
        for case in CASES["errors"]:
            with self.subTest(text=case["text"]):
                cmds, errs = self.lua_parse(case["text"], case["ctx"])
                self.assertEqual(cmds, [])
                self.assertTrue(any(case["error_contains"] in e for e in errs), errs)

    def test_same_as_python(self):
        texts = []
        for name in ("heldout_phrases.jsonl", "heldout_phrases_02.jsonl"):
            p = COACH / "tests" / name
            if p.exists():
                texts += [json.loads(l)["text"] for l in p.read_text(encoding="utf-8").splitlines() if l.strip()]
        n_ok = 0
        for ctx_name in ("dire", "radiant"):
            ctx = py_ctx(ctx_name)
            batch = list(texts)
            for t in texts:
                s = suggest(parse(t, MatchContext(team=ctx.team, agents=ctx.agents,
                                                  enemy_heroes=ctx.enemy_heroes)).commands, ctx)
                if s:
                    batch.append(s)
            batch += [c["text"] for c in CASES["cases"] + CASES["errors"]]
            for t in batch:
                with self.subTest(ctx=ctx_name, text=t):
                    py = self.py_parse(t, ctx_name)
                    lu = self.lua_parse(t, ctx_name)
                    self.assertEqual(lu, py)
                    n_ok += bool(py[0])
        self.assertGreater(n_ok, 200)          # сотни строк, где формат верен и команды совпали

    def test_looks_like_command(self):
        yes = ["1 фарм лес", "все рош", "рош", "дима, стак древние", "потом все назад", "все не рош", "1 летай"]
        no = ["gg", "привет", "ну что народ", "лол", ""]
        for t in yes:
            self.assertTrue(self.T.looks_like_command(t, self.ctx["dire"]), t)
        for t in no:
            self.assertFalse(self.T.looks_like_command(t, self.ctx["dire"]), t)

    def test_uppercase_and_yo(self):
        cmds, errs = self.lua_parse("ВСЕ РОШ!", "radiant")
        self.assertEqual((cmds[0]["action"], cmds[0]["urgent"]), ("roshan", True))
        cmds, errs = self.lua_parse("Лёха фарм лес", "dire")
        self.assertEqual(cmds[0]["agents"], [3])


if __name__ == "__main__":
    unittest.main()
