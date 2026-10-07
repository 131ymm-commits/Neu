"""Оценка разборщика на независимом наборе фраз (tests/heldout_phrases.jsonl).

Набор пишет агент, который не видел код разборщика и его тесты. Первый прогон на новом
наборе — честная мера; после правок по его ошибкам набор перестаёт быть отложенным,
и это надо писать рядом с числом.

  python -m tests.eval_heldout [--out results.json]

Совпадение команды: то же действие, тот же список позиций, и каждый ожидаемый параметр равен.
Переспрос (команда с непустым clarify) в игру не уходит (docs/COMMANDS.md) и приказ с адресатом
не выполняет — с такой ожидаемой командой он не совпадает (правка до прогона PARSE-02, по рецензии).
Фраза верна, если совпали все ожидаемые команды и лишних нет. Для фраз с clarify=true верно и
точное совпадение, и переспрос, если при этом все ожидаемые команды с адресатом найдены среди
команд без переспроса и лишних команд без переспроса нет (правка до прогона PARSE-02, по рецензии;
на PARSE-01 исходный счёт не меняется: 57/80).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from collections import defaultdict
from pathlib import Path

from voicecoach import Agent, MatchContext, parse

HERE = Path(__file__).resolve().parent


def heldout_ctx():
    return MatchContext(
        team="radiant",
        agents=[
            Agent(1, "Miracle-", ("миракл",), "npc_dota_hero_antimage"),
            Agent(2, "Topson", ("топсон",), "npc_dota_hero_invoker"),
            Agent(3, "Collapse", ("коллапс",), "npc_dota_hero_mars"),
            Agent(4, "Mira", ("мира",), "npc_dota_hero_hoodwink"),
            Agent(5, "Вася", ("вася",), "npc_dota_hero_crystal_maiden"),
        ],
        enemy_heroes=["npc_dota_hero_pudge", "npc_dota_hero_phantom_assassin",
                      "npc_dota_hero_storm_spirit", "npc_dota_hero_tidehunter", "npc_dota_hero_lion"],
    )


def parse02_ctx():
    """Состав для набора PARSE-02 (задан до получения набора): сторона Dire, обычные имена."""
    return MatchContext(
        team="dire",
        agents=[
            Agent(1, "Петя", ("петя",), "npc_dota_hero_juggernaut"),
            Agent(2, "Серёга", ("серега",), "npc_dota_hero_storm_spirit"),
            Agent(3, "Лёха", ("леха",), "npc_dota_hero_axe"),
            Agent(4, "Дима", ("дима",), "npc_dota_hero_rubick"),
            Agent(5, "Вова", ("вова",), "npc_dota_hero_witch_doctor"),
        ],
        enemy_heroes=["npc_dota_hero_antimage", "npc_dota_hero_invoker", "npc_dota_hero_mars",
                      "npc_dota_hero_earthshaker", "npc_dota_hero_crystal_maiden"],
    )


CONTEXTS = {"parse01": heldout_ctx, "parse02": parse02_ctx}


def cmd_match(got: dict, exp: dict) -> bool:
    if got.get("clarify") and exp.get("agents"):
        return False                      # переспрос не выполняет приказ с адресатом
    if got["action"] != exp["action"]:
        return False
    if sorted(got["agents"]) != sorted(exp.get("agents", [])):
        return False
    return all(got["params"].get(k) == v for k, v in (exp.get("params") or {}).items())


def wilson(k: int, n: int, z: float = 1.96):
    """95% интервал Уилсона для доли k/n."""
    if n == 0:
        return (None, None)
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (round(c - h, 3), round(c + h, 3))


def count_hits(exp: list, got: list) -> int:
    """Жадное сопоставление один к одному: сколько ожидаемых команд нашлось."""
    used = set()
    hits = 0
    for e in exp:
        for i, g in enumerate(got):
            if i not in used and cmd_match(g, e):
                used.add(i)
                hits += 1
                break
    return hits


def evaluate(path: Path, ctx_name: str = "parse01"):
    make_ctx = CONTEXTS[ctx_name]
    rows = [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]
    results = []
    n_exp = n_got = n_hit = 0
    for r in rows:
        res = parse(r["text"], make_ctx())
        got = [{"action": c.action, "agents": c.agents, "params": c.params, "clarify": c.clarify}
               for c in res.commands]
        exp = r.get("expected") or []
        hits = count_hits(exp, got)
        exact = hits == len(exp) and len(got) == len(exp)
        asked = any(g["clarify"] for g in got)
        ok = exact
        if r.get("clarify") and asked and not exact:
            need = [e for e in exp if e.get("agents")]
            plain = [g for g in got if not g["clarify"]]
            ok = count_hits(need, plain) == len(need) and len(plain) == len(need)
        n_exp += len(exp)
        n_got += len(got)
        n_hit += hits
        results.append({"id": r["id"], "category": r.get("category", "?"), "text": r["text"],
                        "ok": bool(ok), "exact": exact, "hits": hits,
                        "clarify_expected": bool(r.get("clarify")), "asked": asked,
                        "expected": exp, "got": got, "unknown": res.unknown,
                        "confidence": res.confidence, "note": r.get("note", "")})
    n = len(results)
    k = sum(r["ok"] for r in results)
    by_cat = defaultdict(lambda: [0, 0])
    for r in results:
        by_cat[r["category"]][0] += int(r["ok"])
        by_cat[r["category"]][1] += 1
    summary = {
        "data_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "ctx": ctx_name,
        "n_exp": n_exp, "n_got": n_got, "n_hit": n_hit,
        "phrase_ok_ci95": wilson(k, n),
        "by_category": {c: {"ok": a, "n": b, "share": round(a / b, 3), "ci95": wilson(a, b)}
                        for c, (a, b) in sorted(by_cat.items())},
        "phrases": n,
        "phrase_ok": sum(r["ok"] for r in results),
        "phrase_ok_share": round(sum(r["ok"] for r in results) / n, 3) if n else None,
        "command_recall": round(n_hit / n_exp, 3) if n_exp else None,
        "command_precision": round(n_hit / n_got, 3) if n_got else None,
        "clarify_expected": sum(r["clarify_expected"] for r in results),
        "clarify_asked_when_expected": sum(r["asked"] for r in results if r["clarify_expected"]),
        "asked_when_not_expected": sum(r["asked"] for r in results if not r["clarify_expected"]),
    }
    return summary, results


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default=str(HERE / "heldout_phrases.jsonl"))
    ap.add_argument("--ctx", default="parse01", choices=sorted(CONTEXTS))
    ap.add_argument("--out")
    a = ap.parse_args(argv)
    summary, results = evaluate(Path(a.data), a.ctx)
    print(json.dumps(summary, ensure_ascii=False, indent=1))
    for r in results:
        if not r["ok"]:
            print(f"\n#{r['id']} «{r['text']}»  {r['note']}")
            print("  ждали:", [(e['action'], e.get('agents'), e.get('params')) for e in r["expected"]],
                  "clarify" if r["clarify_expected"] else "")
            print("  вышло:", [(g['action'], g['agents'], g['params'], g['clarify']) for g in r["got"]],
                  "не понял:", r["unknown"])
    if a.out:
        Path(a.out).write_text(json.dumps({"summary": summary, "results": results}, ensure_ascii=False,
                                          indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
