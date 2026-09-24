"""UNI-04c — raw-grid winding label. Per PREREG (frozen 2026-08-27). Same seeds as UNI-04b."""
import json, time
import numpy as np
exec(open("/home/claude/uni04b_run.py").read().split("res = {}")[0])
RNGW = np.random.default_rng(424246)

def wind_raw(seg, lag=1, nsur=200):
    seg = np.asarray(seg, float)
    t = np.arange(len(seg))
    res = seg - np.polyval(np.polyfit(t, seg, 1), t)
    if res.std() == 0: return None, None, False
    u = res[lag:]; v = res[:-lag]
    phi = np.arctan2(v, u)
    d = np.angle(np.exp(1j * np.diff(phi)))
    sd = d.std() + 1e-12
    z = float(abs(d.sum()) / (sd * np.sqrt(d.size)))
    eps = RNGW.choice([-1.0, 1.0], size=(nsur, d.size))
    zs = np.abs(eps @ d) / (sd * np.sqrt(d.size))
    th = 2.5 * float(np.percentile(zs, 99))
    return z, th, bool(z >= th)

def label2(traj):
    z, th, fire = wind_raw(traj[-4000:])
    if fire: return "осциллятор", z, th
    blocks = traj[:len(traj) // 240 * 240].reshape(-1, 240).mean(1)
    cr = np.flatnonzero(blocks > 2.2)
    if cr.size and cr[0] >= 20:
        i_on = int(cr[0]); lo = max(i_on - 80, 0)
        w = blocks[lo:min(i_on + 20, len(blocks))]
        return classify(feats(w, i_on - lo), TH), z, th
    w = blocks[-100:]
    return classify(feats(w, 80), TH), z, th

res = {}
t0 = time.time()
for tau, want in ((0.05, "фолд"), (0.40, "осциллятор")):
    dr = sim(tau, True, 990100 + int(tau * 100), 5)
    labs, ok = [], 0
    for r in range(5):
        lb, z, th = label2(dr[r]); labs.append(lb); ok += (lb == want)
        print(f"τ={tau} реплика {r}: {lb} (z={z:.1f}/θ{th:.1f})", flush=True)
    ct = sim(tau, False, 991100 + int(tau * 100), 3)
    cn = sum(1 for r in range(3) if label2(ct[r])[0] == "нет рождения")
    res[str(tau)] = dict(labs=labs, ok=ok, ctl_none=cn)
    print(f"τ={tau}: {ok}/5 -> {want}; контроли {cn}/3 [{time.time()-t0:.0f}s]", flush=True)
ok_lo, ok_hi = res["0.05"]["ok"], res["0.4"]["ok"]
pum1 = ok_lo >= 4 and ok_hi >= 4
pum1_kill = ok_lo <= 2 or ok_hi <= 2
json.dump(dict(res=res, PUM1c=bool(pum1), PUM1c_killed=bool(pum1_kill)),
          open("/home/claude/uni04c_results.json", "w"), default=float)
print(f"\nP-UM1c: фолд-арм {ok_lo}/5, осциллятор-арм {ok_hi}/5 -> "
      f"{'ПОДТВЕРЖДЁН' if pum1 else ('УБИТ' if pum1_kill else 'не установлен')}")
