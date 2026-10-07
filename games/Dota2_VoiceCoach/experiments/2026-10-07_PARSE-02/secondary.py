"""PARSE-02, вторичные меры (заданы в PREREG-PARSE-02.md до прогона разборщика). Тексты фраз не печатает.

  python3 secondary.py beval   до прогона: labels_B_eval.jsonl (id, category, text — из A; expected, clarify, note — из B)
  python3 secondary.py s1      до прогона разборщика, после коммита PREREG: agreement.json (согласие A и B)
  python3 secondary.py after   после прогонов run_parse02.py new/old/newB: secondary_result.json (S2, S3, S4, сравнение с PARSE-01)

S1 — фраза согласована, если у A и B обе clarify = true (списки не сравниваются) или обе clarify = false и
     списки команд равны как мультимножества (то же action, тот же отсортированный agents, params равны как словари).
     Знаменатель — 80 id набора A; id без строки в B или с другим текстом — несогласие (их число пишется отдельно).
S2 — доля верных по A (result.json) среди согласованных фраз, интервал Уилсона.
S3 — доля верных, если правда — B (result_B.json по labels_B_eval.jsonl), интервал Уилсона.
S5 — строгая доля по result.json: ответ равен разметке A как мультимножество команд, параметры протокола v1
     сравниваются полностью (лишний параметр протокола — ошибка; внутренние параметры разборщика не учитываются);
     для фраз с clarify — так же либо переспрос и точное совпадение остальных команд с адресатом. Плюс число
     фраз, верных по главному правилу только за счёт переспроса.
S1' — S1 без фраз, где у A пустой список и нет clarify (решение A «сведения → пустой список» попало в промпт B).
S4 — парное сравнение нынешнего разборщика с разборщиком до правок (75dc796) на тех же 80 фразах по A:
     b — верно только у нового, c — верно только у старого; точный двусторонний тест Мак-Немара
     (биномиальный, полный перебор); разница долей с 95% бутстрэп-интервалом (10 000 повторов по фразам, сид 20261007).
Сравнение с PARSE-01 — описательное: разницы долей PARSE-02 − PARSE-01 (первый прогон PARSE-01) — общая, без asr,
     по четырём общим категориям — с 95% интервалом Ньюкомба (гибрид Уилсона, независимые выборки).
"""
from __future__ import annotations

import hashlib
import json
import math
import random
import sys
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
COACH = HERE.parents[1] / "coach"
A_PATH = COACH / "tests" / "heldout_phrases_02.jsonl"
B_PATH = HERE / "labels_B.jsonl"
B_EVAL = HERE / "labels_B_eval.jsonl"
PARSE01 = HERE.parent / "2026-10-06_PARSE-01" / "result.json"
SEED, BOOT = 20261007, 10000
Z = 1.959963984540054


def rows(path: Path) -> list[dict]:
    return [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]


def wilson_raw(k: int, n: int, z: float = Z):
    if n == 0:
        return (float("nan"), float("nan"))
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (c - h, c + h)


def wilson(k, n):
    lo, hi = wilson_raw(k, n)
    return [round(lo, 3), round(hi, 3)]


def newcombe(k1, n1, k2, n2):
    """95% интервал разницы p1 − p2 независимых долей (Newcombe 1998, метод 10)."""
    p1, p2 = k1 / n1, k2 / n2
    l1, u1 = wilson_raw(k1, n1)
    l2, u2 = wilson_raw(k2, n2)
    d = p1 - p2
    return [round(d - math.sqrt((p1 - l1) ** 2 + (u2 - p2) ** 2), 3),
            round(d + math.sqrt((u1 - p1) ** 2 + (p2 - l2) ** 2), 3)]


def mcnemar_exact(b: int, c: int) -> float:
    """Точный двусторонний тест Мак-Немара: P(X ≤ min(b, c)) · 2, X ~ Bin(b + c, 1/2), не больше 1."""
    n = b + c
    if n == 0:
        return 1.0
    tail = sum(math.comb(n, i) for i in range(min(b, c) + 1)) / 2 ** n
    return min(1.0, 2 * tail)


def canon(cmds):
    return Counter((c["action"], tuple(sorted(c.get("agents") or [])),
                    json.dumps(c.get("params") or {}, sort_keys=True, ensure_ascii=False)) for c in cmds)


def agree(a: dict, b: dict | None) -> bool:
    if b is None or b.get("text") != a.get("text"):
        return False
    if bool(a.get("clarify")) != bool(b.get("clarify")):
        return False
    if a.get("clarify"):
        return True
    return canon(a.get("expected") or []) == canon(b.get("expected") or [])


def beval():
    A, B = rows(A_PATH), {r["id"]: r for r in rows(B_PATH)}
    out = []
    for a in A:
        b = B.get(a["id"]) or {}
        out.append({"id": a["id"], "category": a["category"], "text": a["text"],
                    "expected": b.get("expected", []), "clarify": bool(b.get("clarify")), "note": b.get("note", "")})
    B_EVAL.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in out), encoding="utf-8")
    return {"rows": len(out), "missing_in_B": sum(1 for a in A if a["id"] not in B)}


def s1():
    A, B = rows(A_PATH), {r["id"]: r for r in rows(B_PATH)}
    per = [{"id": a["id"], "category": a["category"], "agree": agree(a, B.get(a["id"]))} for a in A]
    k, n = sum(p["agree"] for p in per), len(per)
    bad = sum(1 for a in A if a["id"] not in B or B[a["id"]].get("text") != a["text"])
    cat = defaultdict(lambda: [0, 0])
    for p in per:
        cat[p["category"]][0] += int(p["agree"])
        cat[p["category"]][1] += 1
    assert all(isinstance(r.get("clarify", False), bool) for r in list(B.values()) + A), "clarify не bool"
    empty_a = {a["id"] for a in A if not (a.get("expected") or []) and not a.get("clarify")}
    k1 = sum(p["agree"] for p in per if p["id"] not in empty_a)
    n1 = n - len(empty_a)
    out = {"A_sha256": sha(A_PATH), "B_sha256": sha(B_PATH),
           "agree": k, "n": n, "share": round(k / n, 3), "ci95": wilson(k, n), "missing_or_text_changed": bad,
           "S1prime_without_empty_A": {"agree": k1, "n": n1, "share": round(k1 / n1, 3), "ci95": wilson(k1, n1)},
           "by_category": {c: {"agree": x, "n": m} for c, (x, m) in sorted(cat.items())}, "per_phrase": per}
    (HERE / "agreement.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    return out


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


# Параметры протокола v1 в том виде, как он дан разметчикам (agent_prompt_A.md); прочие параметры разборщика —
# внутренние (например push.group, roshan.check) и в строгом сравнении не участвуют.
V1_PARAMS = {
    "farm": {"area", "lane"}, "push": {"lane", "tier"}, "defend": {"lane", "place", "tier"},
    "gank": {"lane", "enemy", "enemy_pos"}, "group": {"place", "lane"}, "roshan": set(), "tormentor": set(),
    "smoke": {"then", "lane", "enemy"}, "retreat": {"place"}, "focus": {"enemy", "enemy_pos"}, "engage": {"enemy"},
    "hold": {"what"}, "split": {"lane"}, "ward": {"place", "lane", "kind"}, "stack": {"place"}, "buy": {"item"},
    "use_item": {"item"}, "buyback": set(), "use_ult": {"enemy"}, "save_ult": set(), "save": {"ally"},
    "follow": {"ally"}, "tp": {"place", "lane"}, "move": {"place", "lane"}, "free": set(), "cancel": set(),
    "report": set(),
}


def strict_key(c: dict) -> tuple:
    allowed = V1_PARAMS.get(c["action"], set())
    params = {k: v for k, v in (c.get("params") or {}).items() if k in allowed}
    return (c["action"], tuple(sorted(c.get("agents") or [])), json.dumps(params, sort_keys=True, ensure_ascii=False))


def strict_ok(r: dict) -> bool:
    """S5: ответ разборщика равен разметке как мультимножество (параметр протокола сверх разметки — ошибка);
    для фраз с clarify — то же, либо переспрос и точное совпадение остальных команд с адресатом."""
    exp, got = r["expected"], r["got"]
    plain = [g for g in got if not g["clarify"]]
    asked = len(plain) < len(got)
    exp_key = Counter(strict_key(e) for e in exp)
    if not asked and Counter(strict_key(g) for g in plain) == exp_key:
        return True
    if r["clarify_expected"] and asked:
        need = Counter(strict_key(e) for e in exp if e.get("agents"))
        return Counter(strict_key(g) for g in plain) == need
    return False


def load(name):
    return json.loads((HERE / name).read_text(encoding="utf-8"))


def after():
    new, old, resb, ag = load("result.json"), load("result_prefix.json"), load("result_B.json"), load("agreement.json")
    assert [r["id"] for r in new["results"]] == [r["id"] for r in old["results"]] == [r["id"] for r in resb["results"]]
    assert [r["text"] for r in new["results"]] == [r["text"] for r in old["results"]] == [r["text"] for r in resb["results"]]
    ok_new = {r["id"]: r["ok"] for r in new["results"]}
    ok_old = {r["id"]: r["ok"] for r in old["results"]}
    cat_of = {r["id"]: r["category"] for r in new["results"]}
    agreed = [p["id"] for p in ag["per_phrase"] if p["agree"]]
    k2 = sum(ok_new[i] for i in agreed)
    k3, n3 = resb["summary"]["phrase_ok"], resb["summary"]["phrases"]
    ids = [r["id"] for r in new["results"]]
    b = sum(1 for i in ids if ok_new[i] and not ok_old[i])
    c = sum(1 for i in ids if ok_old[i] and not ok_new[i])
    rng = random.Random(SEED)
    diffs = []
    for _ in range(BOOT):
        s = [ids[rng.randrange(len(ids))] for _ in ids]
        diffs.append(sum(ok_new[i] - ok_old[i] for i in s) / len(s))
    diffs.sort()
    p01 = load_parse01()
    cat_new = defaultdict(lambda: [0, 0])
    for i in ids:
        cat_new[cat_of[i]][0] += int(ok_new[i])
        cat_new[cat_of[i]][1] += 1
    k_new, n_new = sum(ok_new.values()), len(ids)
    k_na = sum(v for i, v in ok_new.items() if cat_of[i] != "asr")
    n_na = sum(1 for i in ids if cat_of[i] != "asr")
    comp = {"всего": {"parse02": [k_new, n_new], "parse01": [p01["k"], p01["n"]],
                      "diff": round(k_new / n_new - p01["k"] / p01["n"], 3),
                      "ci95": newcombe(k_new, n_new, p01["k"], p01["n"])},
            "без asr": {"parse02": [k_na, n_na], "parse01": [p01["k"], p01["n"]],
                        "diff": round(k_na / n_na - p01["k"] / p01["n"], 3),
                        "ci95": newcombe(k_na, n_na, p01["k"], p01["n"])}}
    for key in ("simple", "multi", "modal", "hard"):
        k1, n1 = cat_new[key]
        k0, n0 = p01["cat"][key]
        comp[key] = {"parse02": [k1, n1], "parse01": [k0, n0],
                     "diff": round(k1 / n1 - k0 / n0, 3) if n1 and n0 else None,
                     "ci95": newcombe(k1, n1, k0, n0) if n1 and n0 else None}
    k5 = sum(strict_ok(r) for r in new["results"])
    only_clar = sum(1 for r in new["results"] if r["ok"] and not r["exact"] and r["clarify_expected"])
    out = {
        "S5_strict": {"ok": k5, "n": len(new["results"]), "share": round(k5 / len(new["results"]), 3),
                      "ci95": wilson(k5, len(new["results"])),
                      "ok_only_thanks_to_clarify_main_rule": only_clar},
        "S2": {"ok": k2, "n": len(agreed), "share": round(k2 / len(agreed), 3) if agreed else None,
               "ci95": wilson(k2, len(agreed))},
        "S3": {"ok": k3, "n": n3, "share": round(k3 / n3, 3), "ci95": wilson(k3, n3),
               "by_category": resb["summary"]["by_category"], "command_recall": resb["summary"]["command_recall"],
               "command_precision": resb["summary"]["command_precision"],
               "same_parser_output_as_result_json": all(
                   g["got"] == r["got"] for g, r in zip(resb["results"], new["results"]))},
        "S4": {"new_ok": k_new, "old_ok": sum(ok_old.values()), "n": n_new, "b_new_only": b, "c_old_only": c,
               "mcnemar_exact_p": round(mcnemar_exact(b, c), 4),
               "diff": round((k_new - sum(ok_old.values())) / n_new, 3),
               "bootstrap_ci95": [round(diffs[int(0.025 * BOOT)], 3), round(diffs[int(0.975 * BOOT) - 1], 3)],
               "seed": SEED, "resamples": BOOT, "old_crashed": old["summary"].get("crashed_phrases"),
               "old_by_category": old["summary"]["by_category"]},
        "vs_PARSE01": comp,
    }
    (HERE / "secondary_result.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    return out


def load_parse01():
    d = json.loads(PARSE01.read_text(encoding="utf-8"))["summary"]
    return {"k": d["phrase_ok"], "n": d["phrases"],
            "cat": {c: (v["ok"], v["n"]) for c, v in d["by_category"].items()}}


if __name__ == "__main__":
    what = sys.argv[1] if len(sys.argv) > 1 else ""
    if what == "beval":
        print(beval())
    elif what == "s1":
        o = s1()
        print(json.dumps({k: v for k, v in o.items() if k != "per_phrase"}, ensure_ascii=False))
    elif what == "after":
        print(json.dumps(after(), ensure_ascii=False))
    else:
        print(__doc__)
