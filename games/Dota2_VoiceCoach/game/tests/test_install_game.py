"""Установщик каркаса кастомки: аддон и общие модули попадают в синтетическую папку Dota 2;
переустановка, удаление, чужая папка не трогается."""
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "custom_game"))

import install_game as IG  # noqa: E402


class InstallGame(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.dota = self.tmp / "dota 2 beta"
        (self.dota / "game" / "dota").mkdir(parents=True)
        self.log = []

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_install_reinstall_uninstall(self):
        g, c = IG.install(self.dota, log=self.log.append)
        vs = g / "scripts" / "vscripts"
        for rel in ("addon_game_mode.lua", "coach_game.lua", "coach_agents.lua", "coach_world.lua",
                    "vc_intents.lua", "vc_voice.lua", "vc_text.lua", "vc_text_data.lua",
                    "modifiers/modifier_voicecoach_commander.lua"):
            self.assertTrue((vs / rel).exists(), rel)
        self.assertTrue((g / "addoninfo.txt").exists())
        for rel in ("layout/custom_game/custom_ui_manifest.xml", "layout/custom_game/coach_hud.xml",
                    "scripts/custom_game/coach_hud.js", "styles/custom_game/coach_hud.css"):
            self.assertTrue((c / "panorama" / rel).exists(), rel)
        self.assertFalse((g / "install_game.py").exists())
        IG.install(self.dota, log=self.log.append)
        IG.uninstall(self.dota, log=self.log.append)
        self.assertFalse(g.exists())
        self.assertFalse(c.exists())

    def test_foreign_folder_untouched(self):
        g, _ = IG.targets(self.dota)
        g.mkdir(parents=True)
        (g / "чужое.txt").write_text("x", encoding="utf-8")
        with self.assertRaises(SystemExit):
            IG.install(self.dota, log=self.log.append)
        self.assertTrue((g / "чужое.txt").exists())


if __name__ == "__main__":
    unittest.main()
