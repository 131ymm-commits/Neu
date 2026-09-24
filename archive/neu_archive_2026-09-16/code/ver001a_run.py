"""VER-001a — fresh-seed replication of UNI-04d. Per PREREG (frozen 2026-08-31).
Machinery uni04d verbatim; ONLY seeds changed: drift 990300+, ctrl 991300+."""
import json, time
import numpy as np
exec(open("/home/claude/uni04d_run.py").read().split("\nres = {}")[0])   # sim, label3, TH, V, ...

res = {}
t0 = time.time()
for tau, want in ((0.05, "фолд"), (0.40, "осциллятор")):
    dr = sim(tau, True, 990300 + int(tau * 100), 5)
    labs, ok = [], 0
    for r in range(5):
        lb, z, ar = label3(dr[r]); labs.append(lb); ok += (lb == want)
        print(f"τ={tau} реплика {r}: {lb} (z={z:.1f}, ампл/пуассон={ar:.1f})", flush=True)
    ct = sim(tau, False, 991300 + int(tau * 100), 3)
    clabs = [label3(ct[r])[0] for r in range(3)]
    res[str(tau)] = dict(labs=labs, ok=ok, ctl_labs=clabs)
    print(f"τ={tau}: {ok}/5 -> {want}; контроли {clabs} [{time.time()-t0:.0f}s]", flush=True)

ok_lo, ok_hi = res["0.05"]["ok"], res["0.4"]["ok"]
pv1a = ok_lo >= 4 and ok_hi >= 4
pv1a_kill = ok_lo <= 2 or ok_hi <= 2
c_lo = sum(1 for l in res["0.05"]["ctl_labs"] if l == "нет рождения")
c_hi = sum(1 for l in res["0.4"]["ctl_labs"] if l == "осциллятор")
ctl_ok = c_lo >= 2 and c_hi >= 2
ctl_kill = c_lo <= 1
json.dump(dict(res=res, PV1a=bool(pv1a), PV1a_killed=bool(pv1a_kill),
               ctl_lo_none=c_lo, ctl_hi_osc=c_hi, ctl_ok=bool(ctl_ok), ctl_killed=bool(ctl_kill)),
          open("/home/claude/ver001a_results.json", "w"), default=float)
print(f"\nP-V1a: фолд-арм {ok_lo}/5, осциллятор-арм {ok_hi}/5 -> "
      f"{'РЕПЛИЦИРОВАН' if pv1a else ('ПРОВАЛ' if pv1a_kill else 'не установлен')}")
print(f"Контроли (исправленные ожидания): τ_low none {c_lo}/3, τ_high osc {c_hi}/3 -> {'✓' if ctl_ok else '✗'}")
print(f"[{time.time()-t0:.0f}s]")
