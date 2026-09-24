"""EXT-002 — thermoacoustic: positive external validation of the winding leg. Per PREREG (frozen 2026-08-27)."""
import json, time
import numpy as np
import pandas as pd

LAG = 2
NSUR = 200
RNG = np.random.default_rng(424243)

def wind_z(seg):
    seg = np.asarray(seg, float)
    t = np.arange(len(seg))
    res = seg - np.polyval(np.polyfit(t, seg, 1), t)
    if res.std() == 0: return None, None
    u = res[LAG:]; v = res[:-LAG]
    phi = np.arctan2(v, u)
    dphi = np.angle(np.exp(1j * np.diff(phi)))
    sd = dphi.std() + 1e-12
    z = float(abs(dphi.sum()) / (sd * np.sqrt(dphi.size)))
    # sign-flip surrogate threshold
    zs = []
    for _ in range(NSUR):
        eps = RNG.choice([-1.0, 1.0], size=dphi.size)
        zs.append(abs((eps * dphi).sum()) / (sd * np.sqrt(dphi.size)))
    th = 2.5 * float(np.percentile(zs, 99))
    return z, th

t0 = time.time()
df = pd.read_csv("deep-early-warnings-pnas/test_empirical/thermoacoustic/data/processed_data/df_transitions.csv")
rows = []
for tsid in sorted(df.tsid.unique()):
    d = df[df.tsid == tsid].reset_index(drop=True)
    p = d["Pressure (kPa)"].to_numpy()
    zp, thp = wind_z(p[500:2500])
    zq, thq = wind_z(p[3500:4500])
    pre_fire = bool(zp is not None and zp >= thp)
    post_fire = bool(zq is not None and zq >= thq)
    rows.append(dict(tsid=int(tsid), z_pre=zp, th_pre=thp, z_post=zq, th_post=thq,
                     pre=pre_fire, post=post_fire,
                     dur=float(d["Time (s)"].max() - d["Time (s)"].min()),
                     t0=float(d["Time (s)"].min())))
    print(f"tsid={tsid}: PRE z={zp:.1f}/θ{thp:.1f} {'ОГОНЬ' if pre_fire else '—'} | "
          f"POST z={zq:.1f}/θ{thq:.1f} {'ОГОНЬ' if post_fire else '—'} [{time.time()-t0:.0f}s]", flush=True)

n_pre = sum(r["pre"] for r in rows)
n_post = sum(r["post"] for r in rows)
diff = n_post - n_pre
pg1 = diff >= 6; pg1_kill = diff <= 0
pg2 = n_post >= 15; pg2_kill = n_post <= 10
# ramp-speed halves by absolute start time (log: slower ramps recorded at larger t)
byt0 = sorted(rows, key=lambda r: r["t0"])
fast = byt0[:len(rows) // 2]; slow = byt0[len(rows) // 2:]
fr_fast = sum(r["post"] for r in fast) / len(fast)
fr_slow = sum(r["post"] for r in slow) / len(slow)
pg3 = fr_fast >= 0.7 and fr_slow >= 0.7
loo = all((sum(r["post"] for r in rows if r is not x) - sum(r["pre"] for r in rows if r is not x)) >= 5
          for x in rows)
out = dict(rows=rows, n_pre=n_pre, n_post=n_post,
           verdicts=dict(diff=diff, PG1=bool(pg1), PG1_killed=bool(pg1_kill),
                         PG2=bool(pg2), PG2_killed=bool(pg2_kill),
                         fr_fast=fr_fast, fr_slow=fr_slow, PG3=bool(pg3), loo_ok=bool(loo)))
json.dump(out, open("/home/claude/ext002_results.json", "w"), default=float)
print(f"\nP-G1 (post−pre = {n_post}−{n_pre} = {diff}, нужно >=6): "
      f"{'ПОДТВЕРЖДЁН' if pg1 else ('УБИТ' if pg1_kill else 'не установлен')} (LOO={loo})")
print(f"P-G2 (post-огни {n_post}/19, нужно >=15): {'ПОДТВЕРЖДЁН' if pg2 else ('УБИТ' if pg2_kill else 'не установлен')}")
print(f"P-G3 (скоростная независимость: {fr_fast:.2f}/{fr_slow:.2f}): {pg3}")
print(f"[{time.time()-t0:.0f}s]")
