"""Тесты coach_intents.lua под LuaJIT (как в Доте), через lupa.
Запуск из папки game/:  pip install lupa  &&  python -m unittest -v
"""
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
GAME = HERE.parent
sys.path.insert(0, str(GAME.parent / "coach"))

try:
    from lupa import luajit21 as lupa_rt
except ImportError:                      # pragma: no cover
    from lupa import lua51 as lupa_rt

from voicecoach.protocol import ACTIONS  # noqa: E402


def load():
    L = lupa_rt.LuaRuntime(unpack_returned_tuples=True)
    src = (GAME / "shared" / "coach_intents.lua").read_text(encoding="utf-8")
    M = L.execute(src)
    return L, M


class Intents(unittest.TestCase):
    def setUp(self):
        self.L, self.M = load()
        self.tbl = self.L.table_from

    def cmd(self, action, agents, params=None, seq=None, after_prev=False, urgent=False):
        d = {"action": action, "agents": self.tbl(agents), "params": self.tbl(params or {}),
             "after_prev": after_prev, "urgent": urgent}
        if seq is not None:
            d["seq"] = seq
        return self.tbl(d)

    def st(self, persona=None):
        if persona is None:
            return self.M.new()
        lua_p = self.L.table()
        for pos, p in persona.items():
            lua_p[pos] = self.tbl({"obedience": p.get("obedience", 1),
                                   "desire_bonus": self.tbl(p.get("desire_bonus", {}))})
        return self.M.new(lua_p)

    def test_running_on_luajit(self):
        self.assertTrue(self.L.eval("jit ~= nil"), "тесты должны идти под LuaJIT, как в Доте")

    def test_ttl_matches_protocol(self):
        ttl = dict(self.M.TTL.items())
        self.assertEqual(ttl, {k: a.ttl_s for k, a in ACTIONS.items()})

    def test_farm_jungle(self):
        st = self.st()
        self.M.apply(st, self.cmd("farm", [1], {"area": "jungle_own"}, seq=1), 0)
        self.assertGreaterEqual(self.M.desire(st, 1, "farm", 0.2, 1), 0.75)
        self.assertLessEqual(self.M.desire(st, 1, "laning", 0.5, 1), 0.1 + 1e-9)
        # другим позициям ничего не меняется
        self.assertAlmostEqual(self.M.desire(st, 2, "farm", 0.2, 1), 0.2)

    def test_push_lane(self):
        st = self.st()
        self.M.apply(st, self.cmd("push", [1, 2, 3, 4, 5], {"lane": "top"}, seq=1), 0)
        self.assertGreaterEqual(self.M.desire(st, 3, "push_tower_top", 0.1, 1), 0.85)
        self.assertLessEqual(self.M.desire(st, 3, "push_tower_bot", 0.6, 1), 0.2 + 1e-9)

    def test_ttl_expiry(self):
        st = self.st()
        self.M.apply(st, self.cmd("farm", [1], {"area": "jungle_own"}, seq=1), 0)
        self.assertAlmostEqual(self.M.desire(st, 1, "farm", 0.2, 121), 0.2)
        self.assertIsNone(self.M.current(st, 1, 121))

    def test_after_prev_queue(self):
        st = self.st()
        self.M.apply(st, self.cmd("farm", [1], {"area": "jungle_own"}, seq=1), 0)
        self.M.apply(st, self.cmd("push", [1], {"lane": "top"}, seq=2, after_prev=True), 5)
        self.assertEqual(self.M.current(st, 1, 10).action, "farm")
        it = self.M.current(st, 1, 121)
        self.assertEqual(it.action, "push")
        self.assertEqual(it.t0, 121)            # отсчёт пошёл с момента, когда очередь дошла
        self.assertIsNotNone(self.M.current(st, 1, 121 + 59))

    def test_new_order_replaces(self):
        st = self.st()
        self.M.apply(st, self.cmd("farm", [1], seq=1), 0)
        self.M.apply(st, self.cmd("roshan", [1], seq=2), 3)
        self.assertEqual(self.M.current(st, 1, 4).action, "roshan")

    def test_cancel(self):
        st = self.st()
        self.M.apply(st, self.cmd("roshan", [1, 2], seq=1), 0)
        self.M.apply(st, self.cmd("cancel", [1, 2, 3, 4, 5], seq=2), 1)
        self.assertIsNone(self.M.current(st, 1, 2))

    def test_dedupe_by_seq(self):
        st = self.st()
        self.assertEqual(len(self.M.apply(st, self.cmd("roshan", [1], seq=5), 0)), 1)
        self.assertEqual(len(self.M.apply(st, self.cmd("farm", [1], seq=5), 1)), 0)
        self.assertEqual(self.M.current(st, 1, 2).action, "roshan")

    def test_retreat_caps_fighting(self):
        st = self.st()
        self.M.apply(st, self.cmd("retreat", [1, 2, 3, 4, 5], seq=1), 0)
        self.assertGreaterEqual(self.M.desire(st, 2, "retreat", 0.0, 1), 0.95)
        self.assertLessEqual(self.M.desire(st, 2, "attack", 0.9, 1), 0.1 + 1e-9)

    def test_hold_what_push(self):
        st = self.st()
        self.M.apply(st, self.cmd("hold", [1, 2, 3, 4, 5], {"what": "push"}, seq=1), 0)
        self.assertLessEqual(self.M.desire(st, 1, "push_tower_mid", 0.7, 1), 0.15 + 1e-9)
        self.assertAlmostEqual(self.M.desire(st, 1, "farm", 0.4, 1), 0.4)

    def test_persona_bonus(self):
        st = self.st({1: {"desire_bonus": {"fight": 0.2}}})
        self.assertAlmostEqual(self.M.desire(st, 1, "attack", 0.4, 0), 0.6)
        self.assertAlmostEqual(self.M.desire(st, 1, "farm", 0.4, 0), 0.4)

    def test_obedience_partial(self):
        st = self.st({1: {"obedience": 0.5}})
        self.M.apply(st, self.cmd("roshan", [1], seq=1), 0)
        # пол 0.9, база 0.1, послушание 0.5 → 0.1 + 0.8*0.5 = 0.5
        self.assertAlmostEqual(self.M.desire(st, 1, "roshan", 0.1, 1), 0.5)

    def test_urgent_raises_floor(self):
        st = self.st()
        self.M.apply(st, self.cmd("roshan", [1], seq=1, urgent=True), 0)
        self.assertAlmostEqual(self.M.desire(st, 1, "roshan", 0.0, 1), 0.95)

    def test_instant_buy(self):
        st = self.st()
        self.M.apply(st, self.cmd("buy", [1], {"item": "item_black_king_bar"}, seq=7), 0)
        self.assertIsNone(self.M.current(st, 1, 1))
        pend = self.M.pending_instant(st, 1, 1)
        self.assertEqual(len(pend), 1)
        self.assertEqual(pend[1].params.item, "item_black_king_bar")
        self.M.done_instant(st, 1, 7)
        self.assertEqual(len(self.M.pending_instant(st, 1, 2)), 0)

    def test_save_ult(self):
        st = self.st()
        self.M.apply(st, self.cmd("save_ult", [2], seq=1), 0)
        self.assertTrue(self.M.ult_held(st, 2, 30))
        self.assertFalse(self.M.ult_held(st, 2, 61))

    def test_desire_clamped(self):
        st = self.st({1: {"desire_bonus": {"fight": 0.2}}})
        self.assertLessEqual(self.M.desire(st, 1, "attack", 0.95, 0), 1.0)


if __name__ == "__main__":
    unittest.main()
