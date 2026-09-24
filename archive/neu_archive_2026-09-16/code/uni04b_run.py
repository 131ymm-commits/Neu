"""UNI-04b — route switch via delayed death in Schlogl. Per PREREG (frozen 2026-08-27)."""
import json, time
import numpy as np

exec(open("/home/claude/ext001_run.py").read().split("t0 = time.time()")[0])   # feats, classify
TH = json.load(open("/home/claude/ext001_ckpt.json"))["th"]
k1s, k4s = 5.75, 8.75; SN1, W = 1.37154, 4.00578 - 1.37154
DT, REC, T = 0.005, 0.1, 2400.0
V = 200
NS = int(T / REC)
t0 = time.time()

# ---------- MF-DDE sanity ----------
def mf_dde(fr, tau, x0, T_=400.0):
    k3 = SN1 + fr * W
    nlag = max(int(tau / DT), 1)
    buf = [x0] * nlag
    x = x0; tail = []
    n = int(T_ / DT)
    for i in range(n):
        xd = buf[i % nlag]
        x = max(x + DT * (k3 + k1s * x * x - x ** 3 - k4s * xd), 0)
        buf[i % nlag] = x
        if i > n - int(100 / DT): tail.append(x)
    tail = np.array(tail)
    return float(tail.max() - tail.min()), float(tail.mean())

a1, m1 = mf_dde(0.55, 0.05, 0.42)
a2, m2 = mf_dde(0.55, 0.40, 3.7)
san = a1 < 0.05 and a2 > 0.2
print(f"MF-санити: τ=0.05 тёмная амплитуда {a1:.3f} (нужно затухание) | τ=0.40 горячая {a2:.3f} (нужны колебания) -> "
      f"{'OK' if san else 'СТОП'}", flush=True)
if not san:
    raise SystemExit

def sim(tau, drifting, seed, ntraj):
    rng = np.random.default_rng(seed)
    nlag = max(int(tau / DT), 1)
    x0 = 0.42
    n = np.full(ntraj, int(V * x0), dtype=np.int64)
    buf = np.tile(n[:, None], (1, nlag)).astype(np.int64)
    steps = int(T / DT); stride = int(REC / DT)
    rec = np.empty((ntraj, NS))
    for i in range(steps):
        fr = 0.30 + (1.10 - 0.30) * min(i * DT / T, 1.0) if drifting else 0.30
        k3 = SN1 + fr * W
        x = n / V
        xd = buf[:, i % nlag] / V
        bp = V * (k3 + k1s * x * x)
        bm = V * (k4s * xd + x ** 3)
        n = np.maximum(n + rng.poisson(bp * DT) - rng.poisson(np.maximum(bm, 0) * DT), 0)
        buf[:, i % nlag] = n
        if (i + 1) % stride == 0:
            k = (i + 1) // stride - 1
            if k < NS: rec[:, k] = n / V
    return rec

def label(traj):
    blocks = traj[:len(traj) // 240 * 240].reshape(-1, 240).mean(1)   # ~100 blocks
    cr = np.flatnonzero(blocks > 2.2)
    if cr.size and cr[0] >= 20:
        i_on = int(cr[0]); lo = max(i_on - 80, 0)
        w = blocks[lo:min(i_on + 20, len(blocks))]
        return classify(feats(w, i_on - lo), TH)
    w = blocks[-100:]
    return classify(feats(w, 80), TH)

res = {}
for tau, want in ((0.05, "фолд"), (0.40, "осциллятор")):
    labs, ok = [], 0
    dr = sim(tau, True, 990100 + int(tau * 100), 5)
    for r in range(5):
        lb = label(dr[r]); labs.append(lb); ok += (lb == want)
        print(f"τ={tau} реплика {r}: {lb}", flush=True)
    ct = sim(tau, False, 991100 + int(tau * 100), 3)
    cn = sum(1 for r in range(3) if label(ct[r]) == "нет рождения")
    res[str(tau)] = dict(labs=labs, ok=ok, want=want, ctl_none=cn)
    print(f"τ={tau}: {ok}/5 -> {want}; контроли {cn}/3 [{time.time()-t0:.0f}s]", flush=True)

ok_lo, ok_hi = res["0.05"]["ok"], res["0.4"]["ok"]
pum1 = ok_lo >= 4 and ok_hi >= 4
pum1_kill = ok_lo <= 2 or ok_hi <= 2
pum2 = all(res[k]["ctl_none"] >= 2 for k in res)
out = dict(res=res, verdicts=dict(PUM1b=bool(pum1), PUM1b_killed=bool(pum1_kill), PUM2b=bool(pum2)))
json.dump(out, open("/home/claude/uni04b_results.json", "w"), default=float)
print(f"\nP-UM1b (смена маршрута): фолд-арм {ok_lo}/5, осциллятор-арм {ok_hi}/5 -> "
      f"{'ПОДТВЕРЖДЁН' if pum1 else ('УБИТ' if pum1_kill else 'не установлен')}")
print(f"P-UM2b (контроли): {[res[k]['ctl_none'] for k in res]} -> {'✓' if pum2 else '✗'}")
print(f"[{time.time()-t0:.0f}s]")
