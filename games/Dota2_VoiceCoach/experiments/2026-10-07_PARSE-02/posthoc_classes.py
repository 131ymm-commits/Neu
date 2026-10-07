"""PARSE-02, пост-хок по оценке совета 26 (вердикты P1–P8 не меняет).

Исход фразы — худший из исходов её команд: запрещённое > неверно > переспрос > верно (правило совета).
- верно — фраза верна по оценщику (result.json, поле ok);
- запрещённое — исполнена команда, которую правда запрещает по двум явным правилам: ожидается
  hold {what: X} для позиций S, а исполнено X для кого-то из S; ожидается save_ult, а исполнено use_ult;
- неверно — исполнена лишняя команда или ожидаемая команда не найдена и переспроса нет;
- переспрос — ожидаемая команда не найдена, но разборщик переспросил, лишних исполненных нет.
Незнание = переспрос; самообман (молча неверное исполнение) = неверно + запрещённое.
Плюс: насколько уверенность разборщика отделяет верные фразы от ошибок (AUROC), и падение старого
разборщика между наборами PARSE-01 → PARSE-02.

  python3 posthoc_classes.py   → posthoc_classes.json
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
COACH = HERE.parents[1] / "coach"
sys.path.insert(0, str(COACH))
spec = importlib.util.spec_from_file_location("ev", COACH / "tests" / "eval_heldout.py")
ev = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ev)
spec2 = importlib.util.spec_from_file_location("sec", HERE / "secondary.py")
sec = importlib.util.module_from_spec(spec2)
spec2.loader.exec_module(sec)


def forbidden(exp, executed):
    for e in exp:
        s = set(e.get("agents") or [])
        what = (e.get("params") or {}).get("what") if e["action"] == "hold" else None
        banned = what or ("use_ult" if e["action"] == "save_ult" else None)
        if banned and any(g["action"] == banned and s & set(g["agents"]) for g in executed):
            return True
    return False


def classify(r):
    if r["ok"]:
        return "верно"
    exp, got = r["expected"], r["got"]
    executed = [g for g in got if not g["clarify"]]
    asked = len(executed) < len(got)
    if forbidden(exp, executed):
        return "запрещённое"
    used, unmatched = set(), 0
    for e in exp:
        hit = next((i for i, g in enumerate(executed) if i not in used and ev.cmd_match(g, e)), None)
        if hit is None:
            unmatched += 1
        else:
            used.add(hit)
    extra = len(executed) - len(used)
    if extra or (unmatched and not asked):
        return "неверно"
    return "переспрос" if asked else "неверно"


def auroc(pos, neg):
    """P(уверенность верной > уверенности ошибочной) + ½ P(равны)."""
    if not pos or not neg:
        return None
    s = sum((p > n) + 0.5 * (p == n) for p in pos for n in neg)
    return round(s / (len(pos) * len(neg)), 3)


def summarize(results):
    cls = {r["id"]: classify(r) for r in results}
    count = {k: sum(1 for v in cls.values() if v == k) for k in ("верно", "переспрос", "неверно", "запрещённое")}
    conf = {r["id"]: r["confidence"] for r in results}
    ok = [conf[i] for i, c in cls.items() if c == "верно"]
    silent = [conf[i] for i, c in cls.items() if c in ("неверно", "запрещённое")]
    errors = [conf[i] for i, c in cls.items() if c != "верно"]
    return {
        "classes": count,
        "self_deception_silent": count["неверно"] + count["запрещённое"],
        "ignorance_clarify": count["переспрос"],
        "forbidden_ids": sorted(i for i, c in cls.items() if c == "запрещённое"),
        "clarify_ids": sorted(i for i, c in cls.items() if c == "переспрос"),
        "silent_with_confidence_1": sum(1 for x in silent if x >= 1.0),
        "auroc_conf_correct_vs_silent": auroc(ok, silent),
        "auroc_conf_correct_vs_all_errors": auroc(ok, errors),
        "per_phrase": cls,
    }


def load(name):
    return json.loads((HERE / name).read_text(encoding="utf-8"))


new, old = load("result.json")["results"], load("result_prefix.json")["results"]
s_new, s_old = summarize(new), summarize(old)
p01 = load("pilot_parse01_original_result_prefix.json")["summary"]
old02 = load("result_prefix.json")["summary"]
out = {
    "new": {k: v for k, v in s_new.items() if k != "per_phrase"},
    "old_75dc796": {k: v for k, v in s_old.items() if k != "per_phrase"},
    "transitions_old_to_new": {
        f"{a}→{b}": sum(1 for i in s_new["per_phrase"] if s_old["per_phrase"][i] == a and s_new["per_phrase"][i] == b)
        for a in ("верно", "переспрос", "неверно", "запрещённое") for b in ("верно", "переспрос", "неверно", "запрещённое")
        if a != b},
    "old_parser_set_drop": {
        "parse01": [p01["phrase_ok"], p01["phrases"]], "parse02": [old02["phrase_ok"], old02["phrases"]],
        "diff": round(old02["phrase_ok"] / old02["phrases"] - p01["phrase_ok"] / p01["phrases"], 3),
        "ci95_newcombe": sec.newcombe(old02["phrase_ok"], old02["phrases"], p01["phrase_ok"], p01["phrases"]),
    },
    "per_phrase_new": s_new["per_phrase"], "per_phrase_old": s_old["per_phrase"],
}
(HERE / "posthoc_classes.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
print(json.dumps({k: out[k] for k in ("new", "old_75dc796", "old_parser_set_drop")}, ensure_ascii=False, indent=1))
print({k: v for k, v in out["transitions_old_to_new"].items() if v})
