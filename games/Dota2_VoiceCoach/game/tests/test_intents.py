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


class Respond(unittest.TestCase):
    """Ответ агента на приказ: отказ по делу, оговорка, отсрочка у непослушного."""

    def setUp(self):
        self.L, self.M = load()
        self.tbl = self.L.table_from

    def st(self, obedience=1.0):
        p = self.L.table()
        p[1] = self.tbl({"obedience": obedience, "desire_bonus": self.tbl({})})
        return self.M.new(p)

    def cmd(self, action, seq=1, urgent=False, params=None):
        return self.tbl({"action": action, "agents": self.tbl([1]), "seq": seq, "urgent": urgent,
                         "params": self.tbl(params or {})})

    def respond(self, st, action, state, **kw):
        r = self.M.respond(st, 1, self.cmd(action, **kw), 0, self.tbl(state))
        return dict(r.items())

    def test_dead_refuses_except_buyback_and_buy(self):
        st = self.st()
        self.assertEqual(self.respond(st, "roshan", {"alive": False, "respawn_left": 25}),
                         {"kind": "refuse", "reason": "dead_s", "value": 25})
        self.assertEqual(self.respond(st, "buyback", {"alive": False, "has_buyback": True})["kind"], "ack")
        self.assertEqual(self.respond(st, "buyback", {"alive": False, "has_buyback": False})["reason"], "no_buyback")
        self.assertEqual(self.respond(st, "buy", {"alive": False})["kind"], "ack")

    def test_alive_buyback_refused(self):
        self.assertEqual(self.respond(self.st(), "buyback", {"alive": True})["reason"], "alive")

    def test_buy_short_of_gold_is_accepted_with_note(self):
        r = self.respond(self.st(), "buy", {"alive": True, "gold": 1200, "item_cost": 4050})
        self.assertEqual((r["kind"], r["value"]), ("short", 2850))

    def test_ult_on_cooldown(self):
        r = self.respond(self.st(), "use_ult", {"alive": True, "has_ult": True, "ult_cd": 42})
        self.assertEqual((r["kind"], r["reason"], r["value"]), ("refuse", "ult_cd", 42))

    def test_disobedient_busy_agent_delays_but_not_urgent(self):
        st = self.st(obedience=0.35)
        r = self.respond(st, "roshan", {"alive": True, "busy": 0.9})
        self.assertEqual((r["kind"], r["delay"]), ("delay", 20))     # 10 + 20*(0.7-0.35)/0.7
        r = self.respond(st, "roshan", {"alive": True, "busy": 0.9}, urgent=True)
        self.assertEqual(r["kind"], "ack")
        r = self.respond(st, "retreat", {"alive": True, "busy": 0.9})
        self.assertEqual(r["kind"], "ack")                           # отход не откладывают
        r = self.respond(self.st(obedience=0.9), "roshan", {"alive": True, "busy": 0.9})
        self.assertEqual(r["kind"], "ack")

    def test_delay_activates_later(self):
        st = self.st()
        self.M.apply(st, self.cmd("roshan", seq=3), 0)
        self.assertTrue(self.M.delay(st, 1, 3, 20, 0))
        self.assertIsNone(self.M.current(st, 1, 10))
        self.assertAlmostEqual(self.M.desire(st, 1, "roshan", 0.1, 10), 0.1)
        it = self.M.current(st, 1, 20)
        self.assertEqual(it.action, "roshan")
        self.assertGreaterEqual(self.M.desire(st, 1, "roshan", 0.1, 21), 0.9)

    def test_new_order_cancels_delay(self):
        st = self.st()
        self.M.apply(st, self.cmd("roshan", seq=3), 0)
        self.M.delay(st, 1, 3, 20, 0)
        self.M.apply(st, self.cmd("retreat", seq=4), 5)
        self.assertEqual(self.M.current(st, 1, 25).action, "retreat")


class Voice(unittest.TestCase):
    def setUp(self):
        self.L = lupa_rt.LuaRuntime(unpack_returned_tuples=True)
        self.V = self.L.execute((GAME / "shared" / "coach_voice.lua").read_text(encoding="utf-8"))

    def test_tone_and_determinism(self):
        calm = self.L.table_from({"tone": "calm"})
        hype = self.L.table_from({"tone": "hype"})
        self.assertEqual(self.V.ack(calm, "roshan", 1), self.V.ack(calm, "roshan", 1))
        self.assertIn(self.V.ack(hype, "roshan", 0), ("Рошан наш!", "Забираем Рошана"))
        self.assertEqual(self.V.ack(None, "roshan", 0), "Иду на Рошана")
        # нет фразы у тона — берётся спокойная, потом общая
        self.assertEqual(self.V.ack(hype, "stack", 0), "Стакну")
        self.assertEqual(self.V.ack(calm, "unknown_action", 0), "Понял")

    def test_refuse_formats(self):
        self.assertEqual(self.V.refuse("ult_cd", 41.6), "Ульта в откате, 42 с")
        self.assertEqual(self.V.refuse("no_buyback", None), "Нет байбэка")
        self.assertEqual(self.V.refuse("???", None), "Не могу")
