"""Установка кастомки «тренер доты» в Dota 2 Workshop Tools (Windows).

  python install_game.py                        # папка Dota 2 ищется сама (реестр Steam, библиотеки)
  python install_game.py --dota "D:\\SteamLibrary\\steamapps\\common\\dota 2 beta"
  python install_game.py --uninstall

Копирует:
  custom_game/game     → <dota>/game/dota_addons/voicecoach
  custom_game/content  → <dota>/content/dota_addons/voicecoach
  общие модули game/shared → …/scripts/vscripts/vc_intents.lua, vc_text.lua, vc_text_data.lua, vc_json.lua
Чужие папки с тем же именем не трогает (своя папка помечена файлом-меткой). Запуск — README.md рядом.
"""
from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
GAME = HERE.parent
sys.path.insert(0, str(GAME / "prototype_oha"))

from install import find_dota  # noqa: E402

ADDON = "voicecoach"
MARKER = "voicecoach_game.marker"
SHARED = {"coach_intents.lua": "vc_intents.lua", "coach_text.lua": "vc_text.lua",
          "coach_text_data.lua": "vc_text_data.lua", "json.lua": "vc_json.lua"}


def targets(dota: Path) -> tuple[Path, Path]:
    return dota / "game" / "dota_addons" / ADDON, dota / "content" / "dota_addons" / ADDON


def _clear(dst: Path) -> None:
    if dst.exists():
        if not (dst / MARKER).exists():
            raise SystemExit(f"{dst} уже есть и это не наша кастомка (нет {MARKER}) — не трогаю")
        shutil.rmtree(dst)


def install(dota: Path, log=print) -> tuple[Path, Path]:
    if not (dota / "game" / "dota").exists():
        raise SystemExit(f"{dota} — не папка Dota 2 (нет game/dota)")
    g, c = targets(dota)
    for src, dst in ((HERE / "game", g), (HERE / "content", c)):
        _clear(dst)
        shutil.copytree(src, dst)
        (dst / MARKER).write_text("кастомка голосового тренера: games/Dota2_VoiceCoach/game/custom_game\n",
                                  encoding="utf-8")
    vs = g / "scripts" / "vscripts"
    for src, name in SHARED.items():
        shutil.copy(GAME / "shared" / src, vs / name)
    log(f"Кастомка установлена:\n  {g}\n  {c}")
    log(f"Запуск — README.md: Dota 2 Tools, затем в консоли  dota_launch_custom_game {ADDON} dota")
    return g, c


def uninstall(dota: Path, log=print) -> None:
    for dst in targets(dota):
        if dst.exists():
            _clear(dst)
            log(f"Удалено: {dst}")


def main(argv=None):
    ap = argparse.ArgumentParser(description="Установка кастомки «тренер доты»")
    ap.add_argument("--dota", type=Path, help="папка 'dota 2 beta' (по умолчанию ищется сама)")
    ap.add_argument("--uninstall", action="store_true")
    a = ap.parse_args(argv)
    dota = a.dota or find_dota()
    if dota is None:
        raise SystemExit("Не нашёл Dota 2. Укажите --dota \"…\\steamapps\\common\\dota 2 beta\"")
    if a.uninstall:
        uninstall(dota)
    else:
        install(dota)


if __name__ == "__main__":
    main()
