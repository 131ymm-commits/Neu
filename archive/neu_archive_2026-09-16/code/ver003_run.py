"""VER-003 — integrator step-halving. Per PREREG (frozen 2026-08-31).
(a) UNI-04d at DT=0.0025, seeds 990400/991400; (b) DEL MF at dt=0.0025; (c) ORD-002b A_M8 at Euler 0.005."""
import json, os, time
import numpy as np

CK = "/home/claude/ver003_ckpt.json"
ck = json.load(open(CK)) if os.path.exists(CK) else {}
t0 = time.time()

# ---------- (b) DEL-001 MF halving ----------
if "b" not in ck:
    exec(open("/home/claude/del001_run.py").read().split("def sim")[0])   # mf_run only
    a6 = mf_run(6, dt=0.0025); a7 = mf_run(7, dt=0.0025)
    pv3b = a6 < 0.02 and a7 > 0.05
    ck["b"] = dict(amp6=a6, amp7=a7, PV3b=bool(pv3b))
    json.dump(ck, open(CK, "w"), default=float)
    print(f"P-V3b (MF dt/2): k=6 амплитуда {a6:.4f} (<0.02?), k=7 {a7:.4f} (>0.05?) -> "
          f"{'✓' if pv3b else 'ПРОВАЛ'} [{time.time()-t0:.0f}s]", flush=True)

# ---------- (c) ORD-002b halved Euler step ----------
if "c" not in ck:
    src = open("/home/claude/ord002b_run.py").read()
    exec(src.split("def weaken")[0])   # h1, relax_batch(step 0.01), scan, ring2, KGRID, EPS
    def relax_h(A, mode, kaps, n0, step, steps):
        Af = A.astype(float); indeg = Af.sum(0); has = indeg > 0
        n = n0.copy()
        for _ in range(steps):
            h = h1(n)
            term = np.exp(Af.T @ np.log(np.maximum(h, 1e-300))) if mode == "AND" else (Af.T @ h) / np.maximum(indeg, 1.0)[:, None]
            b = EPS + kaps[None, :] * term * has[:, None]
            d = b - n
            n += step * d
        return n, float(np.max(np.abs(d)))
    def scan_h(A, mode, step, steps):
        M = A.shape[0]; B = KGRID.size
        n0 = np.empty((M, 2 * B)); n0[:, :B] = EPS; n0[:, B:] = 12.0
        n, dmax = relax_h(A, mode, np.concatenate([KGRID, KGRID]), n0, step, steps)
        if dmax >= 1e-6:
            n, dmax = relax_h(A, mode, np.concatenate([KGRID, KGRID]), n, step, steps)
        d = n[:, B:].sum(0) - n[:, :B].sum(0)
    # split criterion identical to ord002b scan()
        ks = [float(KGRID[i]) for i in range(B) if d[i] > 0.5]
        return dict(split=bool(ks), n_nodes=len(ks), window=[min(ks), max(ks)] if ks else None, conv=dmax)
    A8 = ring2(8)
    rA = scan_h(A8, "AND", 0.005, 120000)
    rO = scan_h(A8, "OR", 0.005, 120000)
    grid = list(KGRID)
    ref = [16.0, 40.0]
    def edge_ok(w):
        if w is None: return False
        i0, i1 = grid.index(w[0]), grid.index(w[1])
        j0, j1 = grid.index(ref[0]), grid.index(ref[1])
        return abs(i0 - j0) <= 1 and abs(i1 - j1) <= 1
    pv3c = rA["split"] and edge_ok(rA["window"]) and not rO["split"] and rA["conv"] < 1e-6 and rO["conv"] < 1e-6
    ck["c"] = dict(AND=rA, OR=rO, PV3c=bool(pv3c))
    json.dump(ck, open(CK, "w"), default=float)
    print(f"P-V3c (ORD-002b шаг/2): AND split={rA['split']} окно={rA['window']} (реф [16,40]±1 узел), "
          f"OR split={rO['split']} -> {'✓' if pv3c else 'ПРОВАЛ'} [{time.time()-t0:.0f}s]", flush=True)

# ---------- (a) UNI-04d at DT/2 ----------
if "a" not in ck:
    g = {}
    exec(open("/home/claude/uni04d_run.py").read().split("\nres = {}")[0], g)   # sim, label3 in g
    g["DT"] = 0.0025
    res = {}
    for tau, want in ((0.05, "фолд"), (0.40, "осциллятор")):
        dr = g["sim"](tau, True, 990400 + int(tau * 100), 5)
        labs = [g["label3"](dr[r])[0] for r in range(5)]
        ok = sum(1 for l in labs if l == want)
        ct = g["sim"](tau, False, 991400 + int(tau * 100), 3)
        clabs = [g["label3"](ct[r])[0] for r in range(3)]
        res[str(tau)] = dict(labs=labs, ok=ok, ctl_labs=clabs)
        print(f"dt/2 τ={tau}: {ok}/5 -> {want}; контроли {clabs} [{time.time()-t0:.0f}s]", flush=True)
    ok_lo, ok_hi = res["0.05"]["ok"], res["0.4"]["ok"]
    pv3a = ok_lo >= 4 and ok_hi >= 4
    pv3a_kill = ok_lo <= 2 or ok_hi <= 2
    ck["a"] = dict(res=res, PV3a=bool(pv3a), PV3a_killed=bool(pv3a_kill))
    json.dump(ck, open(CK, "w"), default=float)
    print(f"P-V3a (UNI-04d dt/2): фолд-арм {ok_lo}/5, осц-арм {ok_hi}/5 -> "
          f"{'✓' if pv3a else ('ПРОВАЛ' if pv3a_kill else 'не уст.')}", flush=True)

print(f"[VER-003 done {time.time()-t0:.0f}s]")
