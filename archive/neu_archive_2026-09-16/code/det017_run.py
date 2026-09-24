"""DET-017 — transfer of kink certificate to Verhulst CME. Per PREREG (frozen 2026-08-24)."""
import json, os, sys, time
import numpy as np

SEED = 20260850
EPSV = 0.1
KCAP = 5.0
OMEGA = 50
DT = 0.005
NK = 15
N_TR = 64
STEPS = int(120.0 / DT)
REC = 200
BURN3 = None  # set after sampling count known
CKPT = "/home/claude/det017_ckpt.json"

def sim_verhulst(lam, seed, twin=False, ntr=N_TR, T=120.0):
    rng = np.random.default_rng(seed)
    steps = int(T / DT)
    n = np.full(ntr, int(round(EPSV * OMEGA)), dtype=np.int64)
    tot = []
    for s in range(steps):
        birth = (lam * EPSV * OMEGA + 0.0 * n) if twin else (lam * n + EPSV * OMEGA)
        death = n + n.astype(float) ** 2 / (KCAP * OMEGA)
        n = np.maximum(n + rng.poisson(birth * DT) - rng.poisson(death * DT), 0)
        if (s + 1) % REC == 0:
            tot.append(n / OMEGA)
    X = np.array(tot)
    X = X[int(0.3 * len(X)):]
    means = X.mean(0); varis = X.var(0)
    return float(np.median(means)), float(np.median(varis / np.maximum(means, 1e-9) * OMEGA))

def mf_two_start(lam, twin=False):
    def f(x):
        b = lam * EPSV if twin else lam * x + EPSV
        return b - x - x * x / KCAP
    def relax(x0):
        x = x0
        for _ in range(60000):
            x += 0.01 * f(x)
            x = max(x, 0.0)
        return x
    return relax(EPSV), relax(10.0)

def curves(lams, seed, twin=False):
    Ms, Fs = [], []
    for i, l in enumerate(lams):
        m, fq = sim_verhulst(l, seed + i, twin=twin)
        Ms.append(m); Fs.append(fq)
    return np.array(Ms), np.array(Fs)

def kink_fit(ks, Ms):
    best = None
    for bi in range(3, len(ks) - 3):
        s1 = np.polyfit(ks[:bi + 1], Ms[:bi + 1], 1)[0]
        s2 = np.polyfit(ks[bi:], Ms[bi:], 1)[0]
        r = (np.sum((Ms[:bi + 1] - np.polyval(np.polyfit(ks[:bi + 1], Ms[:bi + 1], 1), ks[:bi + 1])) ** 2)
             + np.sum((Ms[bi:] - np.polyval(np.polyfit(ks[bi:], Ms[bi:], 1), ks[bi:])) ** 2))
        if best is None or r < best[0]:
            best = (r, abs(s2 - s1), float(ks[bi]), bi)
    return best[1], best[2], best[3]

def prescan(seed):
    ls = np.linspace(0.3, 3.0, 9)
    Fs = [sim_verhulst(l, seed + i, ntr=16, T=60.0)[1] for i, l in enumerate(ls)]
    i = int(np.argmax(Fs))
    if i == len(ls) - 1:
        ls = np.linspace(0.3, 4.5, 9)
        Fs = [sim_verhulst(l, seed + 100 + i2, ntr=16, T=60.0)[1] for i2, l in enumerate(ls)]
        i = int(np.argmax(Fs))
    return float(ls[i])

def split_ext(lf):
    for l in np.linspace(0.25 * lf, 2.5 * lf, 8):
        lo, hi = mf_two_start(l)
        if abs(hi - lo) > 0.5: return True
    return False

ck = json.load(open(CKPT)) if os.path.exists(CKPT) else {}
t0 = time.time()
arg = sys.argv[1] if len(sys.argv) > 1 else "all"

# ===== Stage A: subcritical floors =====
if "floor" not in ck and arg in ("all", "A"):
    Rcs = []
    ls = np.linspace(0.2, 0.6, NK)
    for r in range(3):
        Md, _ = curves(ls, SEED + 1000 * r, twin=False)
        Mt, _ = curves(ls, SEED + 1000 * r + 500, twin=True)
        kd, _, _ = kink_fit(ls, Md)
        kt, _, _ = kink_fit(ls, Mt)
        Rcs.append(kd / max(kt, 1e-9))
        print(f"SUB r{r}: Rc={Rcs[-1]:.2f} [{time.time()-t0:.0f}s]", flush=True)
    ck["floor"] = dict(floor_c=2.5 * max(Rcs), sub_Rc=Rcs)
    json.dump(ck, open(CKPT, "w"), default=float)
    print(f"FROZEN: пол = {ck['floor']['floor_c']:.2f}", flush=True)

if "floor" in ck and arg not in ("A",):
    FLC = ck["floor"]["floor_c"]
    for r in range(5):
        key = f"rep{r}"
        if key in ck: continue
        if arg != "all" and arg != str(r): continue
        lf = prescan(SEED + 7000 + r * 300)
        ls = np.linspace(0.5 * lf, 1.6 * lf, NK)
        dl = ls[1] - ls[0]
        Md, Fd = curves(ls, SEED + 8000 + r * 300)
        Mt, _ = curves(ls, SEED + 8000 + r * 300 + 150, twin=True)
        kd, kbp, bi = kink_fit(ls, Md)
        kt, _, _ = kink_fit(ls, Mt)
        Rc = kd / max(kt, 1e-9)
        interior = 0 < bi < NK - 1
        sp = split_ext(lf)
        cons = abs(kbp - lf) <= 3 * dl + 1e-9
        fires = bool(Rc >= FLC and not sp and interior and cons)
        ck[key] = dict(lf=lf, Rc=Rc, kbp=kbp, interior=bool(interior), split=bool(sp),
                       cons=bool(cons), fires=fires, ls=list(ls), M=list(Md), Mt=list(Mt))
        json.dump(ck, open(CKPT, "w"), default=float)
        print(f"rep{r}: lf={lf:.2f} Rc={Rc:.2f} kbp={kbp:.2f} split={sp} cons={cons} "
              f"fires={int(fires)} [{time.time()-t0:.0f}s]", flush=True)

# ===== Schlogl cross =====
if "floor" in ck and arg in ("all", "S"):
    def schlogl_MF_split(fr_lo=0.1, fr_hi=0.9, n=8):
        k1s, k4s = 5.75, 8.75
        SN1, Ww = 1.37154, 4.00578 - 1.37154
        for fr in np.linspace(fr_lo, fr_hi, n):
            k3 = SN1 + fr * Ww
            rts = np.roots([-1.0, k1s, -k4s, k3])
            rts = np.sort(rts[np.isreal(rts)].real)
            if len(rts) == 3 and rts[0] > 0:   # bistable: two stable + one unstable
                return True
        return False
    if "schlogl" not in ck:
        sp = schlogl_MF_split()
        ck["schlogl"] = dict(split_ext=bool(sp), disqualified=bool(sp))
        json.dump(ck, open(CKPT, "w"), default=float)
        print(f"SCHLOGL cross: расщеплённость в расширенном окне = {sp} -> дисквалифицирован = {sp}", flush=True)

if all(f"rep{r}" in ck for r in range(5)) and "schlogl" in ck:
    f1 = sum(1 for r in range(5) if ck[f"rep{r}"]["fires"])
    pu1 = f1 >= 4; pu1_kill = f1 <= 2
    pu2 = ck["schlogl"]["disqualified"]
    loc = sum(1 for r in range(5)
              if abs(ck[f"rep{r}"]["kbp"] - 1.0) <= 3 * (ck[f"rep{r}"]["ls"][1] - ck[f"rep{r}"]["ls"][0]))
    pu3 = loc >= 3
    loo = all(sum(1 for j in range(5) if j != i and ck[f"rep{j}"]["fires"]) >= 3 for i in range(5))
    ck["verdicts"] = dict(f1=f1, PU1=bool(pu1), PU1_killed=bool(pu1_kill), PU2=bool(pu2),
                          PU3_n=loc, PU3=bool(pu3), loo_ok=bool(loo))
    json.dump(ck, open(CKPT, "w"), default=float)
    print(f"\nP-U1 (перенос): {f1}/5 -> {'ПОДТВЕРЖДЁН' if pu1 else ('УБИТ' if pu1_kill else 'не установлен')} (LOO={loo})")
    print(f"P-U2 (Шлёгль дисквалифицирован): {'ПОДТВЕРЖДЁН' if pu2 else 'УБИТ'}")
    print(f"P-U3 (излом у λ=1): {loc}/5 -> {'подтверждён' if pu3 else 'не подтверждён'}")
print(f"[{time.time()-t0:.0f}s]")
