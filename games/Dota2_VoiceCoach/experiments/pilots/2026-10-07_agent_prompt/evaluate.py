"""Оценка пилота промпта: ответы голов → parse_decision по наблюдению сценария → проверка ожиданий,
записанных до ответов (EXPECT.md)."""
import json, sys
from pathlib import Path
SP = Path(__file__).resolve().parent
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / 'coach'))
from voicecoach.agents import parse_decision

def expect(n, d):
    if n == 1:
        return d["plan"] == "farm" and d["where"] == "bot" and 20 <= d["retreat_hp"] <= 40
    if n == 2:
        return d["plan"] == "push" and d["where"] == "bot" and bool(d["say"])
    if n == 3:
        hits = {(c["ability"], c["target"]) for c in d["cast"]}
        return d["plan"] == "fight" and d["target"] == "luna" and bool(
            hits & {("sniper_assassinate", "luna"), ("sniper_shrapnel", "luna")})
    if n == 4:
        return d["buyback"] is True and bool(d["buy"])
    if n == 5:
        return d["plan"] in ("follow", "farm", "hold") and bool(d["say"]) and bool(d["level"])

rows = [json.loads(l) for l in (SP / 'answers.jsonl').read_text(encoding='utf-8').splitlines()]
out = []
for r in rows:
    n = r["scenario"]
    obs = json.loads((SP / f's{n}_obs.json').read_text(encoding='utf-8'))
    raw = r["raw"]
    pure = raw.strip().startswith("{") and raw.strip().endswith("}")
    d, notes = parse_decision(raw, obs)
    ok = d is not None
    out.append({"model": r["model"], "round": r.get("round", 1), "scenario": n, "json_only": pure, "parsed": ok,
                "notes": notes, "retreat_hp": d and d["retreat_hp"], "expected": bool(ok and expect(n, d)),
                "decision": d})
for o in sorted(out, key=lambda o: (o["round"], o["model"], o["scenario"])):
    print(o["round"], o["model"], o["scenario"], "json_only" if o["json_only"] else "TEXT", "ok" if o["parsed"] else "FAIL",
          "notes=%d" % len(o["notes"]), "exp" if o["expected"] else "MISS", o["notes"])
(SP / 'eval.json').write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding='utf-8')
