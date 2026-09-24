"""ORD-002 — AND vs OR input composition at identical pairwise structure. Per PREREG (frozen 2026-08-26).
v2: vectorized (batched over kappa grid and starts); protocol numbers unchanged."""
import json, os, time
import numpy as np

exec(open("/home/claude/det002r_run.py").read().split("import sys, os")[0])

M = 10
GRAPHS = [5201, 5202, 5203, 5204, 5205]
KGRID = [2, 4, 8, 12, 16, 20, 25, 30, 40, 50, 60, 80, 100, 120, 160, 200, 300, 500, 1000]
CARRIERS = [5201, 5203, 5205]
NEG = 5204
DEGEN = 5202
CKPT = "/home/claude/ord002_ckpt.json"

def h1(n): return n / (4.0 + n)

def relax_batch(A, mode, kaps, n0, steps=60000):
    """n0: (M, B); kaps: (B,). Returns final n, max last-step delta."""
    Af = A.astype(float)                      # Af[i,j]=1 if i->j
    indeg = Af.sum(0)                          # (M,)
    has = indeg > 0
    n = n0.copy()
    for _ in range(steps):
        h = h1(n)                              # (M,B)
        if mode == "AND":
            term = np.exp(Af.T @ np.log(np.maximum(h, 1e-300)))   # (M,B) prod over ins
        else:
            term = (Af.T @ h) / np.maximum(indeg, 1.0)[:, None]
        b = EPS + kaps[None, :] * term * has[:, None]
        d = b - n
        n += 0.01 * d
    return n, float(np.max(np.abs(d)))

def run_graph(A):
    K = np.array(KGRID, float)
    B = K.size
    res = {}
    for mode in ("AND", "OR"):
        n0 = np.empty((M, 2 * B))
        n0[:, :B] = EPS; n0[:, B:] = 12.0
        kk = np.concatenate([K, K])
        n, dmax = relax_batch(A, mode, kk, n0)
        if dmax >= 1e-6:
            n, dmax = relax_batch(A, mode, kk, n, steps=60000)   # continue to double total
        lo = n[:, :B].sum(0); hi = n[:, B:].sum(0)
        rows = [dict(k=float(K[i]), lo=float(lo[i]), hi=float(hi[i]), d=float(hi[i] - lo[i])) for i in range(B)]
        split_ks = [float(K[i]) for i in range(B) if hi[i] - lo[i] > 0.5]
        res[mode] = dict(rows=rows, split=bool(split_ks),
                         split_lo=(min(split_ks) if split_ks else None),
                         split_hi=(max(split_ks) if split_ks else None),
                         conv=dmax)
    ident = max(max(abs(a["lo"] - o["lo"]), abs(a["hi"] - o["hi"]))
                for a, o in zip(res["AND"]["rows"], res["OR"]["rows"]))
    res["ident"] = float(ident)
    return res

t0 = time.time()
out = json.load(open(CKPT)) if os.path.exists(CKPT) else {"grid": KGRID}
for sg in GRAPHS:
    if str(sg) in out: continue
    edges = edges_seq(M, sg)
    Kc = k_cycle(edges, M)
    A = adj_at(edges, M, Kc)
    e = run_graph(A)
    e["Kc"] = Kc
    out[str(sg)] = e
    json.dump(out, open(CKPT, "w"), default=float)
    print(f"g{sg} Kc={Kc}: AND split={e['AND']['split']} window=[{e['AND']['split_lo']},{e['AND']['split_hi']}] "
          f"| OR split={e['OR']['split']} | ident={e['ident']:.2e} | conv A/O={e['AND']['conv']:.1e}/{e['OR']['conv']:.1e} "
          f"[{time.time()-t0:.0f}s]", flush=True)

# ===== verdicts (frozen thresholds) =====
g = lambda s: out[str(s)]
and_carr = [x for x in CARRIERS if g(x)["AND"]["split"]]
or_split = [x for x in GRAPHS if g(x)["OR"]["split"]]
neg_split = g(NEG)["AND"]["split"]
degen_ok = g(DEGEN)["ident"] < 1e-9
pao1 = (len(and_carr) >= 2) and (not neg_split) and (len(or_split) == 0)
pao1_kill = (len(or_split) >= 2) or (len(and_carr) <= 1)
loo_ok = True
for drop in GRAPHS:
    c = [x for x in CARRIERS if x != drop and g(x)["AND"]["split"]]
    o = [x for x in GRAPHS if x != drop and g(x)["OR"]["split"]]
    denom = len([x for x in CARRIERS if x != drop])
    loo_ok &= (len(c) >= denom - 1) and (len(o) == 0)
pao3_parts = {}
for x in and_carr:
    klo = g(x)["AND"]["split_lo"]
    orrow = next(r for r in g(x)["OR"]["rows"] if r["k"] == klo)
    dark_or = g(x)["OR"]["rows"][0]["lo"]
    pao3_parts[x] = dict(and_lo=klo, or_mass_at_edge=orrow["lo"], or_dark_ref=dark_or,
                         lit=bool(orrow["lo"] > 2 * dark_or))
edge_5201 = g(5201)["AND"]["split_lo"]
edges_other = [g(x)["AND"]["split_lo"] for x in (5203, 5205) if g(x)["AND"]["split"]]
pao3_order = (edge_5201 is None) or all(e is not None and edge_5201 > e for e in edges_other)
out["verdicts"] = dict(and_carriers=and_carr, or_split=or_split, neg_split=bool(neg_split),
                       degen_ident=g(DEGEN)["ident"], PAO1=bool(pao1), PAO1_killed=bool(pao1_kill),
                       PAO2=bool(degen_ok), loo_ok=bool(loo_ok),
                       PAO3=dict(parts=pao3_parts, edge_order_5201_highest=bool(pao3_order)))
json.dump(out, open("/home/claude/ord002_results.json", "w"), default=float)
print(f"\nP-AO1: AND-носители {and_carr} (нужно >=2 из {CARRIERS}), g5204 split={neg_split} (нужно False), "
      f"OR {or_split} (нужно []) -> {'ПОДТВЕРЖДЁН' if pao1 else ('УБИТ' if pao1_kill else 'не установлен')} (LOO={loo_ok})")
print(f"P-AO2 (g5202 тождество): max|dM|={g(DEGEN)['ident']:.2e} -> {'ПОДТВЕРЖДЁН' if degen_ok else 'УБИТ (артефакт кода)'}")
print(f"P-AO3: {pao3_parts} | кромка g5201 выше прочих: {pao3_order}")
print(f"[{time.time()-t0:.0f}s] -> ord002_results.json")
