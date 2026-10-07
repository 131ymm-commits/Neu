"""Установка пробника кастомки «голосовой тренер» в Dota 2 Workshop Tools (Windows).

  python install_probe.py                       # папка Dota 2 ищется сама (реестр Steam, библиотеки)
  python install_probe.py --dota "D:\\SteamLibrary\\steamapps\\common\\dota 2 beta"
  python install_probe.py --uninstall

Копирует:
  probe_addon/game     → <dota>/game/dota_addons/voicecoach_probe
  probe_addon/content  → <dota>/content/dota_addons/voicecoach_probe
  game/shared/json.lua → …/game/dota_addons/voicecoach_probe/scripts/vscripts/vc_json.lua
  game/shared/coach_text.lua, coach_text_data.lua → …/scripts/vscripts/vc_text.lua, vc_text_data.lua
Чужие папки с тем же именем не трогает (своя папка помечена файлом-меткой).
Как запускать и что прислать — README.md рядом.
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

ADDON = "voicecoach_probe"
MARKER = "voicecoach_probe.marker"


def targets(dota: Path) -> tuple[Path, Path]:
    return dota / "game" / "dota_addons" / ADDON, dota / "content" / "dota_addons" / ADDON


def _clear(dst: Path) -> None:
    if dst.exists():
        if not (dst / MARKER).exists():
            raise SystemExit(f"{dst} уже есть и это не наш пробник (нет {MARKER}) — не трогаю")
        shutil.rmtree(dst)


def install(dota: Path, log=print) -> tuple[Path, Path]:
    if not (dota / "game" / "dota").exists():
        raise SystemExit(f"{dota} — не папка Dota 2 (нет game/dota)")
    g, c = targets(dota)
    for src, dst in ((HERE / "game", g), (HERE / "content", c)):
        _clear(dst)
        shutil.copytree(src, dst)
        (dst / MARKER).write_text("пробник голосового тренера: games/Dota2_VoiceCoach/game/probe_addon\n",
                                  encoding="utf-8")
    shutil.copy(GAME / "shared" / "json.lua", g / "scripts" / "vscripts" / "vc_json.lua")
    shutil.copy(GAME / "shared" / "coach_text.lua", g / "scripts" / "vscripts" / "vc_text.lua")
    shutil.copy(GAME / "shared" / "coach_text_data.lua", g / "scripts" / "vscripts" / "vc_text_data.lua")
    log(f"Пробник установлен:\n  {g}\n  {c}")
    log("Дальше — README.md пробника: сервер тренера с комнатой probe, затем Dota 2 Tools и\n"
        f"  dota_launch_custom_game {ADDON} dota")
    return g, c


def uninstall(dota: Path, log=print) -> None:
    for dst in targets(dota):
        if dst.exists():
            _clear(dst)
            log(f"Удалено: {dst}")


def main(argv=None):
    ap = argparse.ArgumentParser(description="Установка пробника кастомки голосового тренера")
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
