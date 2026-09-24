"""Calibration for DET-006 (exact (V,fr) grid) and DET-008 (ignition times).
Exact quantities + reference counts only; no detector on pilots."""
import json, numpy as np
from scipy.linalg import eigh_tridiagonal

k1, k4 = 5.75, 8.75
SN1, SN2 = 1.37154, 4.00578
W = SN2 - SN1
XMAX = 4.6

def exact_point(V, fr):
    k3 = SN1 + fr * W
    N = int(np.ceil(V * XMAX))
    x = np.arange(N + 1) / V
    Wp = k3 + k1 * x**2; Wm = k4 * x + x**3
    Wp[-1] = 0.0; Wm[0] = 0.0
    lg = np.concatenate([[0.0], np.cumsum(np.log(Wp[:-1]) - np.log(np.where(Wm[1:] > 0, Wm[1:], 1e-300)))])
    lg -= lg.max(); pi = np.exp(lg); pi /= pi.sum()
    d = -(Wp + Wm); off = np.sqrt(Wp[:-1] * Wm[1:])
    ev = np.sort(eigh_tridiagonal(d, off, eigvals_only=True))[::-1]
    t2 = 1.0 / (-ev[1]); t3 = 1.0 / (-ev[2])
    r = np.roots([-1.0, k1, -k4, k3]); r = np.sort(r[np.isreal(r)].real); r = r[r >= -1e-9]
    if len(r) < 3: return None
    nl, nh = int(round(V * r[0])), int(round(V * r[2]))
    cs = np.cumsum(pi); j = np.arange(nl, nh)
    Tlh = float(np.sum(cs[j] / (Wp[j] * pi[j])))
    csr = np.cumsum(pi[::-1])[::-1]; j2 = np.arange(nl + 1, nh + 1)
    Thl = float(np.sum(csr[j2] / (Wm[j2] * pi[j2])))
    tex = 1 / (1 / Thl + 1 / Tlh)
    return dict(V=V, fr=fr, k3=k3, t2=t2, t3=t3, Thl=Thl, Tlh=Tlh, tex=tex,
                regime=("in" if Thl < Tlh / 3 else ("out" if Thl > Tlh else "mid")))

print(f"{'V':>3} {'fr':>5} {'t2ex':>8} {'Thl':>8} {'Tlh':>9} {'tex':>8} regime")
grid = []
for V in (16, 20, 24, 28, 32):
    for fr in (0.30, 0.45, 0.60, 0.75, 0.90, 0.96):
        p = exact_point(V, fr)
        if p is None: continue
        grid.append(p)
        print(f"{V:>3} {fr:>5.2f} {p['t2']:>8.1f} {p['Thl']:>8.1f} {p['Tlh']:>9.1f} "
              f"{p['tex']:>8.1f} {p['regime']}")

# select points: tex <= 200 (measurable at T=400,B2), spanning regimes
sel = [p for p in grid if p["tex"] <= 200 and p["tex"] >= 3]
n_in = sum(1 for p in sel if p["regime"] == "in")
n_mid = sum(1 for p in sel if p["regime"] == "mid")
n_out = sum(1 for p in sel if p["regime"] == "out")
texs = [p["tex"] for p in sel]
print(f"\nselected {len(sel)} points: in={n_in} mid={n_mid} out={n_out}; "
      f"tex range {min(texs):.1f}..{max(texs):.1f} ({max(texs)/min(texs):.0f}x); "
      f"Thl range {min(p['Thl'] for p in sel):.0f}..{max(p['Thl'] for p in sel):.0f}")
json.dump(sel, open("/home/claude/det006_grid.json", "w"))

# ---- DET-008: silent seeds, cycle lengths, ignition reference ----
import sys
sys.path.insert(0, "/home/claude")
exec(open("/home/claude/det002r_run.py").read().split("import sys, os")[0])  # model funcs

ck = json.load(open("/home/claude/det002r_ckpt.json"))
seeds = {int(k): v for k, v in ck["seeds"].items() if "excluded" not in v}
silent = sorted(k for k, v in seeds.items() if v["Kstar"] is None)
detected = sorted(k for k, v in seeds.items() if v["Kstar"] is not None)
print("\nsilent seeds:", silent)

def first_cycle_len(edges, M, Kc):
    A = adj_at(edges, M, Kc)
    # find a cycle: DFS from the last added edge's target
    s, d = edges[Kc - 1]
    # path d ~> s exists; find its length
    from collections import deque
    par = {d: None}
    q = deque([d])
    while q:
        u = q.popleft()
        if u == s: break
        for v in np.where(A[u] == 1)[0]:
            if v not in par: par[v] = u; q.append(v)
    L = 1
    u = s
    while par.get(u) is not None:
        u = par[u]; L += 1
    return L

def ignition_times(edges, M, K, ntraj, Tmax, seed):
    A = adj_at(edges, M, K).astype(float)
    rng = np.random.default_rng(seed)
    n = rng.poisson(np.full((ntraj, M), EPS)).astype(float)
    pdeath = 1 - np.exp(-DT)
    steps = int(Tmax / DT)
    tig = np.full(ntraj, np.nan)
    for s_ in range(steps):
        b = EPS + KAP * (hill(n) @ A)
        n = np.clip(n + rng.poisson(b * DT) - rng.binomial(n.astype(np.int64), pdeath), 0, NCAP)
        if s_ % 50 == 0:
            hi = n.sum(1) > 12.0
            new = hi & np.isnan(tig)
            tig[new] = s_ * DT
            if not np.isnan(tig).any(): break
    return tig

cal = {}
for sg in silent:
    edges = edges_seq(10, sg)
    Kc = seeds[sg]["Kc"]
    L = first_cycle_len(edges, 10, Kc)
    tig = ignition_times(edges, 10, Kc + 1, 16, 6400.0, 999000 + sg)
    med = float(np.nanmedian(tig))
    frac = float(np.mean(~np.isnan(tig)))
    cal[sg] = dict(Kc=Kc, L=L, tig_med=med, ignited_frac=frac)
    print(f"seed {sg}: Kc={Kc} L_cycle={L} T_ig med={med:.0f} ignited {frac:.2f}", flush=True)
for sg in detected:
    edges = edges_seq(10, sg)
    Kc = seeds[sg]["Kc"]
    L = first_cycle_len(edges, 10, Kc)
    tig = ignition_times(edges, 10, Kc + 1, 8, 1600.0, 998000 + sg)
    med = float(np.nanmedian(tig))
    cal[sg] = dict(Kc=Kc, L=L, tig_med=med, ignited_frac=float(np.mean(~np.isnan(tig))))
    print(f"seed {sg} (det): Kc={Kc} L={L} T_ig med={med:.0f}", flush=True)
json.dump(cal, open("/home/claude/det008_cal.json", "w"))
print("-> det006_grid.json, det008_cal.json")
