"""Установщик пробника кастомки: копирует аддон в синтетическую папку Dota 2, кладёт JSON,
переустанавливается, удаляется и не трогает чужую папку с тем же именем."""
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "probe_addon"))

import install_probe as IP  # noqa: E402


class InstallProbe(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.dota = self.tmp / "dota 2 beta"
        (self.dota / "game" / "dota").mkdir(parents=True)
        self.log = []

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_install_reinstall_uninstall(self):
        g, c = IP.install(self.dota, log=self.log.append)
        vs = g / "scripts" / "vscripts"
        for rel in ("addon_game_mode.lua", "probe.lua", "vc_json.lua", "bots/mode_rune_generic.lua",
                    "modifiers/modifier_voicecoach_probe.lua"):
            self.assertTrue((vs / rel).exists(), rel)
        self.assertTrue((g / "addoninfo.txt").exists())
        self.assertTrue((c / "panorama" / "scripts" / "custom_game" / "probe.js").exists())
        self.assertTrue((c / "panorama" / "layout" / "custom_game" / "custom_ui_manifest.xml").exists())
        self.assertFalse((g / "install_probe.py").exists())
        IP.install(self.dota, log=self.log.append)                       # повторная установка
        IP.uninstall(self.dota, log=self.log.append)
        self.assertFalse(g.exists())
        self.assertFalse(c.exists())

    def test_foreign_folder_untouched(self):
        g, _ = IP.targets(self.dota)
        g.mkdir(parents=True)
        (g / "чужое.txt").write_text("x", encoding="utf-8")
        with self.assertRaises(SystemExit):
            IP.install(self.dota, log=self.log.append)
        self.assertTrue((g / "чужое.txt").exists())

    def test_not_dota(self):
        with self.assertRaises(SystemExit):
            IP.install(self.tmp / "пусто", log=self.log.append)


if __name__ == "__main__":
    unittest.main()
