"""VER-001b — fresh-seed replication of DEL-001 test scan. Per PREREG (frozen 2026-08-31).
Frozen TH from del001_ckpt calibration; fresh seeds 955000+k, broken 965010."""
import json, os, time
import numpy as np
from scipy.signal import welch

exec(open("/home/claude/del001_run.py").read().split("t0 = time.time()")[0])   # mf_run, sim, stat_R2, tau_sp
TH = json.load(open("/home/claude/del001_ckpt.json"))["cal"]["th"]
CK = "/home/claude/ver001b_ckpt.json"
ck = json.load(open(CK)) if os.path.exists(CK) else {}
t0 = time.time()
print(f"замороженный порог TH={TH:.3f}", flush=True)

for k in range(4, 12):
    key = f"k{k}"
    if key in ck: continue
    recs = sim(k, 955000 + k)
    zs = [stat_R2(x) for x in recs]
    fires = sum(1 for z in zs if z >= TH)
    taus = [tau_sp(x) for x in recs]
    tv = [t for t in taus if t is not None]
    ck[key] = dict(z=zs, fires=fires, tau_med=(float(np.median(tv)) if tv else None))
    json.dump(ck, open(CK, "w"), default=float)
    print(f"k={k}: z={[round(z,1) for z in zs]} огней {fires}/5 | tau_med={ck[key]['tau_med']} [{time.time()-t0:.0f}s]", flush=True)

if "broken" not in ck:
    zs = [stat_R2(x) for x in sim(10, 965010, broken=True)]
    ck["broken"] = dict(z=zs, fires=sum(1 for z in zs if z >= TH))
    json.dump(ck, open(CK, "w"), default=float)
    print(f"разорванная k=10: огней {ck['broken']['fires']}/5 [{time.time()-t0:.0f}s]", flush=True)

KS = list(range(4, 12))
fires = {k: ck[f"k{k}"]["fires"] for k in KS}
kdet = None
for k in KS:
    if fires[k] >= 4 and all(fires[q] >= 4 for q in KS if q > k):
        kdet = k; break
islands = any(fires[KS[i]] >= 4 and fires[KS[i + 1]] <= 1 for i in range(len(KS) - 1))
mono = kdet is None or all(fires[k] <= 1 for k in KS if k <= kdet - 2)
pv1b1 = kdet is not None and 4 <= kdet <= 6
pv1b1_kill = kdet is None or (kdet is not None and kdet >= 7)
pv1b2 = (not islands) and mono
t4, t5, t6 = ck["k4"]["tau_med"], ck["k5"]["tau_med"], ck["k6"]["tau_med"]
pv1b4 = None not in (t4, t5, t6) and t4 < t5 < t6
pv1b3 = ck["broken"]["fires"] <= 1
degen = all(fires[k] >= 4 for k in KS) or all(fires[k] <= 1 for k in KS)
ck["verdicts"] = dict(kdet=kdet, fires=fires, PV1b1=bool(pv1b1), PV1b1_killed=bool(pv1b1_kill),
                      PV1b2=bool(pv1b2), islands=bool(islands), tau=(t4, t5, t6), PV1b4=bool(pv1b4),
                      PV1b3=bool(pv1b3), broken_fires=ck["broken"]["fires"], degen_flag=bool(degen))
json.dump(ck, open(CK, "w"), default=float)
print(f"\nP-V1b1: k_det={kdet} (исходно 5, нужно [4,6]) -> {'РЕПЛИЦИРОВАН' if pv1b1 else ('ПРОВАЛ' if pv1b1_kill else 'не установлен')}")
print(f"P-V1b2 (монотонность/острова): {'✓' if pv1b2 else '✗'} | P-V1b3 (разорванная {ck['broken']['fires']}/5): {'✓' if pv1b3 else '✗'}")
print(f"P-V1b4 (софтенинг {t4}/{t5}/{t6}): {'✓' if pv1b4 else '✗'} | вырожденность: {degen}")
print(f"[{time.time()-t0:.0f}s]")
