"""Установщик прототипа «голосовой тренер + боты Open Hyper AI» для лобби Local Host.

Что делает (ничего не удаляет без резервной копии):
  1. находит Доту (или берёт --dota);
  2. копирует боты OHA (папка из GitHub-архива или из подписки Workshop) в
     <Дота>/game/dota/scripts/vscripts/bots/; прежнюю папку bots переименовывает в bots_backup_<время>;
  3. кладёт модуль тренера в bots/coach/ и пишет coach_config.lua (адрес сервера, характеры агентов);
  4. дописывает в режимы ботов (mode_*_generic.lua) обёртку желания — перед финальным `return`, если он есть;
  5. пишет настройки OHA в vscripts/game/Customize/general.lua (OHA читает их первыми): русский язык,
     имена и герои двойников по позициям;
  6. пишет roster.json для сервера тренера (имена и как их зовут голосом).

Запуск (Windows, из папки games/Dota2_VoiceCoach/game/prototype_oha):
  python install.py --oha "C:\\путь\\к\\dota2bot-OpenHyperAI" --lineup lineup.json
  python install.py --uninstall          вернуть прежнюю папку bots

lineup.json — кто играет: {"radiant": ["../../digitizer/agents/vasya.json", null, ...], "dire": [...]}
(пути к файлам агентов из `python -m twin.cli agent`; null — бот OHA по умолчанию).
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
GAME = HERE.parent
MARKER = ".voicecoach"
WRAP_BEGIN = "-- [voicecoach] begin"
WRAP_END = "-- [voicecoach] end"
# режимы, которые понимает модуль намерений (game/shared/coach_intents.lua, M.MODES)
KNOWN_MODES = {
    "laning", "attack", "roam", "retreat", "farm", "team_roam", "roshan", "ward", "rune",
    "push_tower_top", "push_tower_mid", "push_tower_bot",
    "defend_tower_top", "defend_tower_mid", "defend_tower_bot",
    "assemble", "outpost", "secret_shop", "side_shop",
}
TEAM_IDS = {"radiant": 2, "dire": 3}      # TEAM_RADIANT / TEAM_DIRE в API ботов


# --- поиск Доты --------------------------------------------------------------

def find_dota() -> Path | None:
    cands = []
    if sys.platform == "win32":
        try:
            import winreg
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam") as k:
                steam = Path(winreg.QueryValueEx(k, "SteamPath")[0])
            cands.append(steam)
            vdf = steam / "steamapps" / "libraryfolders.vdf"
            if vdf.exists():
                for m in re.finditer(r'"path"\s+"([^"]+)"', vdf.read_text(encoding="utf-8", errors="ignore")):
                    cands.append(Path(m.group(1).replace("\\\\", "\\")))
        except OSError:
            pass
        cands += [Path(r"C:\Program Files (x86)\Steam"), Path(r"C:\Program Files\Steam"),
                  Path(r"D:\Steam"), Path(r"D:\SteamLibrary"), Path(r"E:\SteamLibrary")]
    else:
        cands += [Path.home() / ".steam" / "steam", Path.home() / ".local" / "share" / "Steam"]
    for c in cands:
        d = c / "steamapps" / "common" / "dota 2 beta"
        if (d / "game" / "dota").exists():
            return d
    return None


def oha_bots_dir(path: Path) -> Path:
    """Папка с файлами ботов OHA: корень репозитория (есть bots/) или сама папка bots/Workshop."""
    if (path / "bots" / "bot_generic.lua").exists():
        return path / "bots"
    if (path / "bot_generic.lua").exists():
        return path
    raise SystemExit(f"Не нашёл ботов OHA в {path}: нужен bot_generic.lua в папке или в её подпапке bots")


# --- обёртка желания ---------------------------------------------------------

def wrapper(mode: str) -> str:
    return f"""
{WRAP_BEGIN}: обёртка голосового тренера (games/Dota2_VoiceCoach/game/prototype_oha/install.py)
do
  local __coach_ok, __coach = pcall(require, GetScriptDirectory() .. "/coach/coach_bot")
  if __coach_ok and type(__coach) == "table" and type(GetDesire) == "function" then
    local __coach_base = GetDesire
    GetDesire = function()
      return __coach.desire("{mode}", __coach_base())
    end
    if type(X) == "table" and X.GetDesire == __coach_base then X.GetDesire = GetDesire end
  elseif not __coach_ok then
    print("[тренер] модуль не загрузился: " .. tostring(__coach))
  end
end
{WRAP_END}
"""


def patch_mode_file(text: str, mode: str) -> str:
    """Дописать обёртку; если файл кончается `return X` — вставить перед ним. Повторно не дописывает."""
    if WRAP_BEGIN in text:
        return text
    lines = text.rstrip("\n").split("\n")
    # последний значащий оператор: пропускаем пустые строки и комментарии
    i = len(lines) - 1
    while i >= 0 and (not lines[i].strip() or lines[i].strip().startswith("--")):
        i -= 1
    if i >= 0 and re.match(r"^\s*return\b", lines[i]):
        return "\n".join(lines[:i]) + "\n" + wrapper(mode) + "\n".join(lines[i:]) + "\n"
    return text.rstrip("\n") + "\n" + wrapper(mode)


def mode_of(filename: str) -> str | None:
    m = re.match(r"^mode_(.+)_generic\.lua$", filename)
    if not m or m.group(1) not in KNOWN_MODES:
        return None
    return m.group(1)


# --- настройки OHA -----------------------------------------------------------

def lua_str(s: str) -> str:
    return "'" + s.replace("\\", "\\\\").replace("'", "\\'") + "'"


def replace_table(text: str, name: str, values: list[str]) -> str:
    body = ",\n".join("    " + lua_str(v) for v in values)
    pat = re.compile(r"(Customize\." + re.escape(name) + r"\s*=\s*\{)(.*?)(\n\})", re.S)
    if not pat.search(text):
        raise SystemExit(f"В настройках OHA нет таблицы Customize.{name} — формат изменился")
    return pat.sub(lambda m: m.group(1) + "\n" + body + ",\n}", text, count=1)


def customize_text(oha_general: str, lineup_agents: dict) -> str:
    t = re.sub(r'Customize\.Localization\s*=\s*"[a-z]+"', 'Customize.Localization = "ru"', oha_general)
    for team, key in (("radiant", "Radiant"), ("dire", "Dire")):
        agents = lineup_agents.get(team, [None] * 5)
        heroes = [(a or {}).get("hero") or "Random" for a in agents]
        names = [(a or {}).get("name") or "Random" for a in agents]
        t = replace_table(t, f"{key}_Heros", heroes)
        t = replace_table(t, f"{key}_Names", names)
    return "-- Сгенерировано установщиком голосового тренера из настроек OHA по умолчанию.\n" + t


# --- характеры для модуля тренера ------------------------------------------------

def lua_value(v, indent="  "):
    if v is None:
        return "nil"
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (int, float)):
        return repr(v)
    if isinstance(v, str):
        return lua_str(v)
    if isinstance(v, list):
        return "{ " + ", ".join(lua_value(x, indent) for x in v) + " }"
    if isinstance(v, dict):
        items = []
        for k, x in v.items():
            key = f"[{k}]" if isinstance(k, int) else (k if re.match(r"^[A-Za-z_]\w*$", k) else f"[{lua_str(k)}]")
            items.append(f"{key} = {lua_value(x, indent)}")
        return "{ " + ", ".join(items) + " }"
    raise TypeError(type(v))


def config_text(base_url: str, room: str, lineup_agents: dict) -> str:
    personas = {}
    for team, agents in lineup_agents.items():
        tid = TEAM_IDS[team]
        personas[tid] = {}
        for pos, a in enumerate(agents, start=1):
            if a:
                b = a.get("behavior", {})
                personas[tid][pos] = {"name": a.get("name"), "obedience": b.get("obedience", 0.85),
                                      "desire_bonus": b.get("desire_bonus", {}),
                                      "tone": (a.get("voice") or {}).get("tone", "calm")}
    return ("-- Настройки тренера для ботов: пишет install.py, руками править можно.\n"
            f"return {lua_value({'base_url': base_url, 'room': room, 'poll_interval': 0.5, 'debug': False, 'personas': personas})}\n")


def roster_json(lineup_agents: dict) -> dict:
    out = {}
    for team, agents in lineup_agents.items():
        out[team] = []
        for pos, a in enumerate(agents, start=1):
            if a:
                out[team].append({"pos": pos, "name": a.get("name", ""), "aliases": a.get("aliases", []),
                                  "hero": a.get("hero")})
    return out


def load_lineup(path: Path | None) -> dict:
    if path is None:
        return {"radiant": [None] * 5, "dire": [None] * 5}
    raw = json.loads(path.read_text(encoding="utf-8"))
    out = {}
    for team in ("radiant", "dire"):
        lst = list(raw.get(team, [])) + [None] * 5
        out[team] = []
        for p in lst[:5]:
            if p:
                ap = (path.parent / p).resolve()
                out[team].append(json.loads(ap.read_text(encoding="utf-8")))
            else:
                out[team].append(None)
    return out


# --- установка ---------------------------------------------------------------

def install(dota: Path, oha: Path, lineup: dict, base_url: str, room: str, log=print,
            roster_path: Path | None = None) -> Path:
    vscripts = dota / "game" / "dota" / "scripts" / "vscripts"
    bots = vscripts / "bots"
    stamp = time.strftime("%Y%m%d_%H%M%S")
    if bots.exists():
        if (bots / MARKER).exists():
            shutil.rmtree(bots)                      # наша прошлая установка
        else:
            backup = vscripts / f"bots_backup_{stamp}"
            bots.rename(backup)
            log(f"прежняя папка bots сохранена: {backup}")
    shutil.copytree(oha_bots_dir(oha), bots)
    coach = bots / "coach"
    coach.mkdir(exist_ok=True)
    shutil.copy(HERE / "coach" / "coach_bot.lua", coach)
    shutil.copy(GAME / "shared" / "coach_intents.lua", coach)
    shutil.copy(GAME / "shared" / "coach_voice.lua", coach)
    shutil.copy(GAME / "shared" / "json.lua", coach)
    (coach / "coach_config.lua").write_text(config_text(base_url, room, lineup), encoding="utf-8")
    patched = []
    for f in sorted(bots.glob("mode_*_generic.lua")):
        mode = mode_of(f.name)
        if mode:
            f.write_text(patch_mode_file(f.read_text(encoding="utf-8"), mode), encoding="utf-8")
            patched.append(mode)
    log(f"обёртки тренера в режимах: {', '.join(patched)}")
    general = bots / "Customize" / "general.lua"
    if general.exists():
        cust_dir = vscripts / "game" / "Customize"
        target = cust_dir / "general.lua"
        if target.exists() and "голосового тренера" not in target.read_text(encoding="utf-8", errors="ignore"):
            target.rename(cust_dir / f"general_backup_{stamp}.lua")
        cust_dir.mkdir(parents=True, exist_ok=True)
        target.write_text(customize_text(general.read_text(encoding="utf-8"), lineup), encoding="utf-8")
        log(f"настройки OHA (ru, имена и герои): {target}")
    (bots / MARKER).write_text(json.dumps({"installed": stamp, "base_url": base_url, "room": room}), encoding="utf-8")
    roster = roster_path or (HERE / "roster.json")
    roster.write_text(json.dumps(roster_json(lineup), ensure_ascii=False, indent=1), encoding="utf-8")
    log(f"состав для сервера тренера: {roster}")
    return bots


def uninstall(dota: Path, log=print) -> None:
    vscripts = dota / "game" / "dota" / "scripts" / "vscripts"
    bots = vscripts / "bots"
    backups = sorted(vscripts.glob("bots_backup_*"))
    if bots.exists() and (bots / MARKER).exists():
        shutil.rmtree(bots)
    if backups:
        backups[-1].rename(bots)
        log(f"возвращена папка {backups[-1].name}")
    else:
        log("резервной копии нет: папка bots удалена (Дота возьмёт своих ботов)")


def main(argv=None):
    ap = argparse.ArgumentParser(description="Установка прототипа голосового тренера поверх ботов OHA")
    ap.add_argument("--dota", type=Path, help="папка 'dota 2 beta' (по умолчанию ищется сама)")
    ap.add_argument("--oha", type=Path, help="папка с ботами Open Hyper AI (GitHub-архив или Workshop)")
    ap.add_argument("--lineup", type=Path, help="lineup.json: агенты по позициям для обеих команд")
    ap.add_argument("--server", default="http://127.0.0.1:8787")
    ap.add_argument("--room", default="local")
    ap.add_argument("--uninstall", action="store_true")
    a = ap.parse_args(argv)
    dota = a.dota or find_dota()
    if dota is None:
        raise SystemExit("Не нашёл Доту: укажите --dota \"...\\steamapps\\common\\dota 2 beta\"")
    if a.uninstall:
        uninstall(dota)
        return
    if a.oha is None:
        raise SystemExit("Укажите --oha: папку с ботами Open Hyper AI")
    bots = install(dota, a.oha, load_lineup(a.lineup), a.server, a.room)
    print(f"\nГотово: {bots}\nДальше — docs/FIRST_RUN.md, шаг «Матч с ботами».")


if __name__ == "__main__":
    main()
