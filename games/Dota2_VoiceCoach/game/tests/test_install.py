"""Установщик прототипа поверх OHA (game/prototype_oha/install.py).

Всегда: на маленькой синтетической копии OHA (файлы режимов трёх видов, как у OHA:
обычный конец, конец `return X`, без GetDesire). Если рядом есть настоящий клон OHA
(переменная OHA_PATH), дополнительно ставится на него и все изменённые Lua-файлы
компилируются под LuaJIT — так ловится сломанный синтаксис до игры.
"""
import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
GAME = HERE.parent
sys.path.insert(0, str(GAME / "prototype_oha"))
sys.path.insert(0, str(GAME.parent / "digitizer"))

try:
    from lupa import luajit21 as lupa_rt
except ImportError:                      # pragma: no cover
    from lupa import lua51 as lupa_rt

import install as inst  # noqa: E402

PLAIN = """local bot = GetBot()
function GetDesire()
\treturn 0.25
end
function Think() end
"""
MODULE = """local X = {}
function GetDesire()
\treturn 0.4
end
X.GetDesire = GetDesire
return X
"""
NO_DESIRE = """local bot = GetBot()
if bot == nil then return end
function Think() end
"""
GENERAL = """local Customize = { }
Customize.Enable = true
Customize.Localization = "en"
Customize.Radiant_Heros = {
    'Random',
    'Random',
}
Customize.Dire_Heros = {
    'Random',
}
Customize.Radiant_Names = {
    'Random',
}
Customize.Dire_Names = {
    'Random',
}
return Customize
"""


def fake_oha(root: Path) -> Path:
    bots = root / "oha" / "bots"
    (bots / "Customize").mkdir(parents=True)
    (bots / "bot_generic.lua").write_text("-- bot\n", encoding="utf-8")
    (bots / "mode_farm_generic.lua").write_text(PLAIN, encoding="utf-8")
    (bots / "mode_team_roam_generic.lua").write_text(MODULE, encoding="utf-8")
    (bots / "mode_attack_generic.lua").write_text(NO_DESIRE, encoding="utf-8")
    (bots / "mode_retreat_generic_wip.lua").write_text(PLAIN, encoding="utf-8")
    (bots / "Customize" / "general.lua").write_text(GENERAL, encoding="utf-8")
    return root / "oha"


def fake_dota(root: Path) -> Path:
    dota = root / "dota 2 beta"
    old = dota / "game" / "dota" / "scripts" / "vscripts" / "bots"
    old.mkdir(parents=True)
    (old / "valve_default.lua").write_text("-- старые боты\n", encoding="utf-8")
    return dota


def lua_compiles(L, src: str) -> str | None:
    """None — компилируется; иначе текст ошибки компилятора LuaJIT."""
    check = L.eval("function(s) local f, e = load(s); if f then return true, '' end; return false, e end")
    ok, err = check(src)
    return None if ok else str(err)


def lua_load(L, src: str):
    loader = L.eval("function(s) local f, e = load(s); if f then return f, '' end; return false, e end")
    fn, err = loader(src)
    return (fn if fn else None), str(err)


class Install(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.L = lupa_rt.LuaRuntime(unpack_returned_tuples=True)
        self.agent = {"name": "Вася", "aliases": ["вася", "васька"], "hero": "npc_dota_hero_pudge",
                      "behavior": {"obedience": 0.7, "desire_bonus": {"fight": 0.1, "farm": -0.05}}}

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def lineup(self):
        return {"radiant": [self.agent, None, None, None, None], "dire": [None] * 5}

    def test_install_backup_patch_customize(self):
        dota, oha = fake_dota(self.tmp), fake_oha(self.tmp)
        logs = []
        bots = inst.install(dota, oha, self.lineup(), "http://127.0.0.1:8787", "local", log=logs.append,
                            roster_path=self.tmp / "roster.json")
        vs = bots.parent
        self.assertTrue(any(p.name.startswith("bots_backup_") for p in vs.iterdir()))
        for f in ("coach_bot.lua", "coach_intents.lua", "json.lua", "coach_config.lua"):
            self.assertTrue((bots / "coach" / f).exists(), f)
        farm = (bots / "mode_farm_generic.lua").read_text(encoding="utf-8")
        self.assertEqual(farm.count(inst.WRAP_BEGIN), 1)
        roam = (bots / "mode_team_roam_generic.lua").read_text(encoding="utf-8")
        self.assertTrue(roam.rstrip().endswith("return X"), "обёртка должна стоять до return X")
        self.assertIn(inst.WRAP_BEGIN, roam)
        wip = (bots / "mode_retreat_generic_wip.lua").read_text(encoding="utf-8")
        self.assertNotIn(inst.WRAP_BEGIN, wip)                  # не режим — не трогаем
        cust = (vs / "game" / "Customize" / "general.lua").read_text(encoding="utf-8")
        self.assertIn('Customize.Localization = "ru"', cust)
        self.assertIn("'npc_dota_hero_pudge'", cust)
        self.assertIn("'Вася'", cust)
        roster = json.loads((self.tmp / "roster.json").read_text(encoding="utf-8"))
        self.assertEqual(roster["radiant"][0]["aliases"], ["вася", "васька"])
        for p in [bots / "mode_farm_generic.lua", bots / "mode_team_roam_generic.lua",
                  bots / "mode_attack_generic.lua", bots / "coach" / "coach_config.lua",
                  vs / "game" / "Customize" / "general.lua"]:
            self.assertIsNone(lua_compiles(self.L, p.read_text(encoding="utf-8")), p.name)

    def test_reinstall_is_idempotent_and_uninstall_restores(self):
        dota, oha = fake_dota(self.tmp), fake_oha(self.tmp)
        rp = self.tmp / "roster.json"
        inst.install(dota, oha, self.lineup(), "http://x", "r", log=lambda *_: None, roster_path=rp)
        bots = inst.install(dota, oha, self.lineup(), "http://x", "r", log=lambda *_: None, roster_path=rp)
        self.assertEqual((bots / "mode_farm_generic.lua").read_text(encoding="utf-8").count(inst.WRAP_BEGIN), 1)
        backups = [p for p in bots.parent.iterdir() if p.name.startswith("bots_backup_")]
        self.assertEqual(len(backups), 1)                       # вторая установка своих не бэкапит
        inst.uninstall(dota, log=lambda *_: None)
        self.assertTrue((bots / "valve_default.lua").exists())

    def test_wrapper_calls_coach_with_base_desire(self):
        calls = []
        self.L.execute('function GetScriptDirectory() return "bots" end; function GetBot() return {} end')
        self.L.globals().py_record = lambda mode, base: calls.append((mode, base)) or 0.9
        self.L.execute('package.preload["bots/coach/coach_bot"] = function() '
                       'return { desire = function(mode, base) return py_record(mode, base) end } end')
        for text, mode, base in ((PLAIN, "farm", 0.25), (MODULE, "team_roam", 0.4)):
            src = inst.patch_mode_file(text, mode)
            fn, err = lua_load(self.L, src)
            self.assertIsNotNone(fn, err)
            X = fn()
            self.assertAlmostEqual(self.L.eval("GetDesire()"), 0.9)
            if X is not None:
                self.assertAlmostEqual(X.GetDesire(), 0.9)     # и в таблице модуля
            self.assertEqual(calls[-1], (mode, base))

    def test_config_has_personas_by_team_id(self):
        txt = inst.config_text("http://h", "room1", self.lineup())
        cfg = self.L.execute(txt)
        self.assertEqual(cfg.base_url, "http://h")
        self.assertAlmostEqual(cfg.personas[2][1].obedience, 0.7)
        self.assertAlmostEqual(cfg.personas[2][1].desire_bonus.fight, 0.1)

    @unittest.skipUnless(os.environ.get("OHA_PATH"), "нет клона OHA (OHA_PATH)")
    def test_real_oha_all_patched_files_compile(self):
        dota = fake_dota(self.tmp)
        bots = inst.install(dota, Path(os.environ["OHA_PATH"]), self.lineup(), "http://x", "r",
                            log=lambda *_: None, roster_path=self.tmp / "roster.json")
        bad = []
        for f in sorted(bots.glob("mode_*_generic.lua")):
            err = lua_compiles(self.L, f.read_text(encoding="utf-8"))
            if err:
                bad.append((f.name, err))
        cust = bots.parent / "game" / "Customize" / "general.lua"
        err = lua_compiles(self.L, cust.read_text(encoding="utf-8"))
        if err:
            bad.append(("Customize/general.lua", err))
        self.assertEqual(bad, [])
        patched = [f.name for f in bots.glob("mode_*_generic.lua")
                   if inst.WRAP_BEGIN in f.read_text(encoding="utf-8")]
        self.assertGreaterEqual(len(patched), 15, patched)


if __name__ == "__main__":
    unittest.main()
