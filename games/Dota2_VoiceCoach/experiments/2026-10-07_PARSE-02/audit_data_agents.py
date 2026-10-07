"""Аудит агентов-разметчиков PARSE-01/02: что они читали и запускали (без вывода текстов фраз).

Читает транскрипты подагентов сессии (~/.claude/projects/.../subagents). Для каждого вызова
инструмента печатает: Read/Glob/Grep — путь и шаблон; Write/Edit — путь и все пути, которые
открывает записанный скрипт (open(), Path(), строки с «/»); Bash — команду, где кириллица
заменена на <рус> (фразы набора по-русски), и флаг «читает» (cat/head/tail/less/sed/grep/ls/find,
python3 со скриптом). Отдельно — все пути с любым корнем (/home, /tmp, /root, ~, ../, $VAR).
Имена моделей не печатает: в репозиторий их не пишем.
Первая версия (07.10.2026) искала «читает» неверным выражением r'\\b…' (буквальная обратная
косая черта) и только пути под /home/user/Neu — ловила не всё (рецензия линзы 1).
  python3 audit_data_agents.py
"""
import glob
import json
import os
import re

D = os.path.expanduser("~/.claude/projects/-home-user-Neu/c2746a83-5006-51b9-9f59-346f06e713bc/subagents")
PATH = re.compile(r"(?:~|\.\./|\$\w+|/(?:home|tmp|root|etc|usr|opt|var))[^\s'\"<>|;&)(,]*")
READS = re.compile(r"\b(cat|head|tail|less|more|sed|awk|grep|rg|ls|find|python3?\s+(?!-c)[^\s]+\.py|python3?\s+-c)\b")
RUS = re.compile(r"[А-Яа-яЁё]+")


def mask(s: str) -> str:
    return RUS.sub("<рус>", s)


for meta in sorted(glob.glob(f"{D}/agent-*.meta.json")):
    desc = json.load(open(meta)).get("description", "")
    if "held-out" not in desc and "phrase" not in desc:
        continue
    jl = meta.replace(".meta.json", ".jsonl")
    print("=== агент", os.path.basename(jl), "|", desc)
    if not os.path.exists(jl):
        print("  транскрипта нет")
        continue
    for line in open(jl, errors="replace"):
        try:
            o = json.loads(line)
        except ValueError:
            continue
        msg = o.get("message") or {}
        if o.get("type") != "assistant":
            continue
        for b in msg.get("content") or []:
            if not (isinstance(b, dict) and b.get("type") == "tool_use"):
                continue
            inp = b.get("input") or {}
            name = b["name"]
            if name == "Bash":
                cmd = inp.get("command", "")
                print(f"  Bash: читает={bool(READS.search(cmd))} пути={sorted(set(PATH.findall(cmd)))}")
                print("    $ " + mask(cmd).replace("\n", "\n      "))
            elif name in ("Write", "Edit"):
                body = inp.get("content") or inp.get("new_string") or ""
                opened = sorted(set(re.findall(r"(?:open|Path)\(\s*([^),]+)", body)))
                print(f"  {name}: {inp.get('file_path')}; в тексте открывает: {[mask(x) for x in opened]}; "
                      f"пути в тексте: {sorted(set(PATH.findall(body)))}")
            elif name in ("Read", "Glob", "Grep"):
                print(f"  {name}: {inp.get('file_path') or inp.get('path')} шаблон={inp.get('pattern')!r}")
            else:
                print(f"  {name}: ключи {sorted(inp)}")
