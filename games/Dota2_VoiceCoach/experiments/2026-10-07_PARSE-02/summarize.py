"""Сводка чисел для отчёта: summary-блоки прогонов без разборов по фразам (для ledger.py audit —
чтобы совпадение числа с данными было информативным). Пишет report_numbers.json.
  python3 summarize.py
"""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def load(p):
    return json.loads(Path(p).read_text(encoding="utf-8"))


def drop(d, keys):
    return {k: v for k, v in d.items() if k not in keys}


out = {
    "result": drop(load(HERE / "result.json")["summary"], {"code_sha256"}),
    "result_prefix": drop(load(HERE / "result_prefix.json")["summary"], {"code_sha256"}),
    "result_B": drop(load(HERE / "result_B.json")["summary"], {"code_sha256"}),
    "agreement": drop(load(HERE / "agreement.json"), {"per_phrase"}),
    "secondary": load(HERE / "secondary_result.json"),
    "parse01_result": load(HERE.parent / "2026-10-06_PARSE-01" / "result.json")["summary"],
    "S4_ids": {
        "new_only": [r["id"] for r, o in zip(load(HERE / "result.json")["results"], load(HERE / "result_prefix.json")["results"]) if r["ok"] and not o["ok"]],
        "old_only": [r["id"] for r, o in zip(load(HERE / "result.json")["results"], load(HERE / "result_prefix.json")["results"]) if o["ok"] and not r["ok"]],
    },
    "failed_ids_new": [r["id"] for r in load(HERE / "result.json")["results"] if not r["ok"]],
}
# вероятности ставок из таблицы калибровки (они же в PREREG) — чтобы отчёт сверялся и по ним
import re
cal = (HERE.parents[3] / "tools" / "self_calibration.py").read_text(encoding="utf-8")
out["prereg_probabilities"] = [float(x) for x in re.findall(r"\('DOTA-PARSE-02', '[^']*', '[^']*', '[^']*', ([0-9.]+),", cal)]
(HERE / "report_numbers.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
print("report_numbers.json:", len(json.dumps(out)), "символов")
