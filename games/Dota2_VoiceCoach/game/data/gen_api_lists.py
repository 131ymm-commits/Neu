"""Списки имён API для game/tests/test_api_names.py — из опубликованных описаний, не по памяти.

  python3 gen_api_lists.py vscripts  <папка package из @moddota/dota-data 0.47.2>     > vscripts_api.txt
  python3 gen_api_lists.py panorama  <папка package из @moddota/panorama-types 1.39.2> > panorama_api.txt
  python3 gen_api_lists.py botapi    <клон forest0xia/dota2bot-OpenHyperAI>            > botapi_names.txt

Пакеты npm: `npm pack @moddota/dota-data@0.47.2` (лицензия Apache-2.0), `npm pack @moddota/panorama-types@1.39.2`
(MIT) — лицензии сверены по их package.json. В списки идут только имена API.
Open Hyper AI (MIT): https://github.com/forest0xia/dota2bot-OpenHyperAI.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path


def vscripts(pkg: Path) -> list[str]:
    api = json.loads((pkg / "files/vscripts/api.json").read_text(encoding="utf-8"))
    enums = json.loads((pkg / "files/vscripts/enums.json").read_text(encoding="utf-8"))
    names, inst, ext = set(), set(), set()
    for t in api:
        if t["kind"] == "function":
            names.add(t["name"])
        elif t["kind"] == "class":
            for m in t.get("members", []):
                names.add(f'{t["name"]}.{m["name"]}')
            ext.add(f'extends:{t["name"]}={t.get("extend") or ""}')
            if t.get("instance"):
                inst.add(f'instance:{t["instance"]}={t["name"]}')
    for e in enums:
        if e["kind"] == "constant":
            names.add(e["name"])
        else:  # имя самого перечисления не пишем: в коде встречаются только его члены
            for m in e.get("members", []):
                names.add(m["name"])
    head = ["# Имена API vscripts Dota 2: @moddota/dota-data 0.47.2 (npm, 2026-04-26, Apache-2.0). Строки: Класс.метод, функция, константа,",
            "# instance:глобальная_переменная=Класс, extends:Класс=Родитель. Нужны тесту game/tests/test_api_names.py."]
    return head + sorted(names) + sorted(inst) + sorted(ext)


MEMBER = re.compile(r"^\s*(?:readonly\s+)?([A-Za-z_$][\w$]*)\??\s*[:(<]", re.M)
TYPE = re.compile(r"\b(?:interface|type|class|enum)\s+([A-Za-z_]\w*)")


def panorama(pkg: Path) -> list[str]:
    """Грубый, но полный список: имена членов и типов из всех .d.ts пакета (методы, свойства,
    события, типы панелей). Принадлежность имени классу не проверяется."""
    names = set()
    for f in sorted((pkg / "types").glob("*.d.ts")):
        text = f.read_text(encoding="utf-8")
        text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
        text = re.sub(r"//[^\n]*", "", text)
        names |= set(MEMBER.findall(text)) | set(TYPE.findall(text))
        names |= set(re.findall(r"^\s+([A-Z][A-Z0-9_]+)\s*=", text, re.M))      # члены перечислений
        names |= set(re.findall(r"\|\s*'([a-z][A-Za-z0-9_]*)'", text))           # события панелей: 'oninputsubmit'…
    names = {n for n in names if len(n) > 1}
    head = ["# Имена API Panorama: @moddota/panorama-types 1.39.2 (npm, 2026-04-26, MIT): методы, свойства, события, типы панелей."]
    return head + sorted(names)


def strip_lua(src: str) -> str:
    """Убрать комментарии и строки Lua (для поиска имён в коде)."""
    out, i, n = [], 0, len(src)
    while i < n:
        if src.startswith("--", i):
            m = re.match(r"--\[(=*)\[", src[i:])
            if m:
                end = src.find("]" + m.group(1) + "]", i + len(m.group(0)))
                i = n if end < 0 else end + len(m.group(1)) + 2
            else:
                end = src.find("\n", i)
                i = n if end < 0 else end
            continue
        m = re.match(r"\[(=*)\[", src[i:])
        if m:
            end = src.find("]" + m.group(1) + "]", i + len(m.group(0)))
            out.append('""')
            i = n if end < 0 else end + len(m.group(1)) + 2
            continue
        c = src[i]
        if c in "\"'":
            j = i + 1
            while j < n and src[j] != c and src[j] != "\n":
                j += 2 if src[j] == "\\" else 1
            out.append('""')
            i = j + 1
            continue
        out.append(c)
        i += 1
    return "".join(out)


def botapi(repo: Path) -> list[str]:
    """API скриптов ботов: объявления TypeScript в OHA + имена, которые код ботов OHA (он работает
    в игре) вызывает, но сам не определяет."""
    dts = repo / "typescript/bots/ts_libs/dota"
    g = (dts / "globals.d.ts").read_text(encoding="utf-8")
    fns = set(re.findall(r"^\s*function\s+(\w+)\s*\(", g, re.M))
    methods = set(re.findall(r"^\s+([A-Z]\w*)\s*\(", g, re.M))
    methods |= set(re.findall(r"^\s+([A-Z]\w*)\s*\(", (dts / "interfaces.ts").read_text(encoding="utf-8"), re.M))
    consts = set(re.findall(r"^\s+([A-Z][A-Z0-9_]+)\s*(?:=[^,\n]*)?,?\s*$", (dts / "enums.ts").read_text(encoding="utf-8"), re.M))
    defined, used_fn, used_m, used_c = set(), set(), set(), set()
    for f in sorted((repo / "bots").rglob("*.lua")):
        s = strip_lua(f.read_text(encoding="utf-8", errors="replace"))
        defined |= set(re.findall(r"function\s+(?:[\w.]+[.:])?(\w+)\s*\(", s))
        defined |= set(re.findall(r"(?<![\w.:])(\w+)\s*=\s*function\b", s))
        defined |= set(re.findall(r"\blocal\s+(\w+)", s))
        used_m |= set(re.findall(r":\s*([A-Z]\w*)\s*\(", s))
        used_fn |= set(re.findall(r"(?<![\w.:])([A-Z]\w*)\s*\(", s))
        used_c |= set(re.findall(r"(?<![\w.:])([A-Z][A-Z0-9]*_[A-Z0-9_]+)\b", s))
    fns |= used_fn - defined
    methods |= used_m - defined
    consts |= used_c - defined
    head = ["# API скриптов ботов Dota 2 по Open Hyper AI (MIT, github.com/forest0xia/dota2bot-OpenHyperAI, коммит cb814c6):",
            "# объявления typescript/bots/ts_libs/dota/*.ts и имена, которые его Lua-код в bots/ вызывает, но не определяет.",
            "# Строки: fn:функция, method:метод, const:константа. Нужны тесту game/tests/test_api_names.py."]
    return head + [f"fn:{x}" for x in sorted(fns)] + [f"method:{x}" for x in sorted(methods)] + [f"const:{x}" for x in sorted(consts)]


def main():
    kind, path = sys.argv[1], Path(sys.argv[2])
    out = {"vscripts": vscripts, "panorama": panorama, "botapi": botapi}[kind](path)
    sys.stdout.write("\n".join(out) + "\n")


if __name__ == "__main__":
    main()
