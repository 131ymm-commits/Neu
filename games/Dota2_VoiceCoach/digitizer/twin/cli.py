"""Командная строка оцифровки.

  python -m twin.cli check                                  проверить доступ к OpenDota
  python -m twin.cli pros --grep miracle                    найти account_id про-игрока
  python -m twin.cli profile --account 105248644 --limit 50 --name "Miracle-" \
         --alias миракл --out profiles/miracle.json [--request-parse]
  python -m twin.cli files --account 120269134 match1.json match2.json --out profiles/x.json
  python -m twin.cli agent --profile profiles/miracle.json [--hero npc_dota_hero_invoker] \
         --out agents/miracle.json
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .agent_params import agent_params
from .opendota import OpenDota, collect_matches
from .profile import build_profile


def _write(obj, path):
    if path:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(obj, f, ensure_ascii=False, indent=1)
        print(f"записано: {path}")
    else:
        json.dump(obj, sys.stdout, ensure_ascii=False, indent=1)
        print()


def main(argv=None):
    ap = argparse.ArgumentParser(prog="twin", description="Оцифровка игроков Dota 2")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("check")
    pr = sub.add_parser("pros")
    pr.add_argument("--grep", default="")
    p = sub.add_parser("profile")
    p.add_argument("--account", type=int, required=True)
    p.add_argument("--limit", type=int, default=50)
    p.add_argument("--name")
    p.add_argument("--alias", action="append", default=[])
    p.add_argument("--out")
    p.add_argument("--request-parse", action="store_true")
    fl = sub.add_parser("files")
    fl.add_argument("--account", type=int, required=True)
    fl.add_argument("--name")
    fl.add_argument("--alias", action="append", default=[])
    fl.add_argument("--out")
    fl.add_argument("paths", nargs="+")
    ag = sub.add_parser("agent")
    ag.add_argument("--profile", required=True)
    ag.add_argument("--hero")
    ag.add_argument("--obedience", type=float, default=0.85)
    ag.add_argument("--out")
    a = ap.parse_args(argv)

    if a.cmd == "check":
        api = OpenDota(cache_dir=None)
        pros = api._fetch("GET", api._url("/proPlayers"))
        print(f"OpenDota доступен: про-игроков в списке {len(pros)}")
    elif a.cmd == "pros":
        rows = OpenDota().pro_players()
        g = a.grep.lower()
        for r in rows:
            line = f"{r.get('account_id')}\t{r.get('name')}\t{r.get('team_name') or ''}"
            if g in line.lower():
                print(line)
    elif a.cmd == "profile":
        api = OpenDota()
        ms = collect_matches(api, a.account, limit=a.limit, request_missing=a.request_parse)
        _write(build_profile(ms, a.account, name=a.name, aliases=a.alias), a.out)
    elif a.cmd == "files":
        ms = []
        for path in a.paths:
            with open(path, encoding="utf-8") as f:
                ms.append(json.load(f))
        _write(build_profile(ms, a.account, name=a.name, aliases=a.alias), a.out)
    elif a.cmd == "agent":
        with open(a.profile, encoding="utf-8") as f:
            prof = json.load(f)
        _write(agent_params(prof, hero=a.hero, obedience=a.obedience), a.out)


if __name__ == "__main__":
    main()
