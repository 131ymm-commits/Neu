"""Живой вызов мотора cli (CliBackend) с настоящими промптами агента — README рядом.

Запуск (нужен установленный Claude Code со входом):  python live.py <модель> [<модель> …]
<модель> — алиас или имя модели Claude Code; default — модель Claude Code по умолчанию.
Сырые результаты — live_results.json в текущей папке (в репозиторий кладётся очищенный results.json)."""
import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[2] / "coach"))
from voicecoach import agents as A  # noqa: E402

PILOT = HERE.parent / "2026-10-07_agent_prompt"

out = []
for scen in ("s3", "s1"):
    obs = json.loads((PILOT / f"{scen}_obs.json").read_text(encoding="utf-8"))
    roster = {"allies": [(a.get("pos"), a.get("hero")) for a in obs.get("allies") or []],
              "enemies": list(obs.get("enemy_team") or [])}
    system = A.system_prompt(obs["team"], obs["pos"], obs["hero"], None, 0.85, roster)
    new_coach = [c for c in obs.get("coach") or [] if c.get("ago", 99) <= 2]
    user = A.user_prompt(obs, [], new_coach, "очередное решение")
    for model in sys.argv[1:]:
        b = A.CliBackend(model=None if model == "default" else model, effort="low")
        t0 = time.monotonic()
        try:
            r, err = b.decide(system, user, obs), None
        except A.BackendError as e:
            r, err = {}, str(e)
        dt = time.monotonic() - t0
        d, notes = (None, [])
        if not err:
            d, notes = A.parse_decision(r.get("data") if r.get("data") is not None else r.get("text", ""), obs)
        rec = {"scen": scen, "model_arg": model, "latency_s": round(dt, 2), "error": err, "model": r.get("model"),
               "usage": r.get("usage"), "cost_usd": r.get("cost_usd"), "decision": d, "notes": notes,
               "system_chars": len(system), "user_chars": len(user)}
        out.append(rec)
        print(json.dumps(rec, ensure_ascii=False))
Path("live_results.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
