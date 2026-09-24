"""ORD-002b — cycle-level form of the composition switch. Per PREREG (frozen 2026-08-26)."""
import json, time
import numpy as np

EPS = 0.10
KGRID = np.array([2, 4, 8, 12, 16, 20, 25, 30, 40, 50, 60, 80, 100, 120, 160, 200, 300, 500, 1000], float)

def h1(n): return n / (4.0 + n)

def relax_batch(A, mode, kaps, n0, steps=60000):
    Af = A.astype(float); indeg = Af.sum(0); has = indeg > 0
    n = n0.copy()
    for _ in range(steps):
        h = h1(n)
        term = np.exp(Af.T @ np.log(np.maximum(h, 1e-300))) if mode == "AND" else (Af.T @ h) / np.maximum(indeg, 1.0)[:, None]
        b = EPS + kaps[None, :] * term * has[:, None]
        d = b - n
        n += 0.01 * d
    return n, float(np.max(np.abs(d)))

def scan(A, mode):
    M = A.shape[0]; B = KGRID.size
    n0 = np.empty((M, 2 * B)); n0[:, :B] = EPS; n0[:, B:] = 12.0
    n, dmax = relax_batch(A, mode, np.concatenate([KGRID, KGRID]), n0)
    if dmax >= 1e-6:
        n, dmax = relax_batch(A, mode, np.concatenate([KGRID, KGRID]), n, steps=60000)
    d = n[:, B:].sum(0) - n[:, :B].sum(0)
    ks = [float(KGRID[i]) for i in range(B) if d[i] > 0.5]
    return dict(split=bool(ks), n_nodes=len(ks), window=[min(ks), max(ks)] if ks else None, conv=dmax)

def ring2(M):
    A = np.zeros((M, M), dtype=int)
    for j in range(M):
        A[(j - 1) % M, j] = 1; A[(j - 2) % M, j] = 1
    return A

def weaken(A, nodes):
    """Reduce in-set of each node in `nodes` to its single predecessor (j-1)."""
    A = A.copy(); M = A.shape[0]
    for j in nodes:
        A[:, j] = 0; A[(j - 1) % M, j] = 1
    return A

def cut(A, node):
    A = A.copy(); A[:, node] = 0
    return A

t0 = time.time()
out = {}
# Family A
for M in (6, 8, 10, 12):
    out[f"A_M{M}"] = {m: scan(ring2(M), m) for m in ("AND", "OR")}
    a, o = out[f"A_M{M}"]["AND"], out[f"A_M{M}"]["OR"]
    print(f"A кольцо²({M}): AND split={a['split']} window={a['window']} ({a['n_nodes']} узлов) | OR split={o['split']} [{time.time()-t0:.0f}s]", flush=True)
# Family B
for tag, nodes in (("B_weak1", [0]), ("B_weak2", [0, 5])):
    out[tag] = {"AND": scan(weaken(ring2(10), nodes), "AND")}
    a = out[tag]["AND"]
    print(f"{tag}: AND split={a['split']} window={a['window']} ({a['n_nodes']} узлов) [{time.time()-t0:.0f}s]", flush=True)
# Family C
out["C_dag"] = {m: scan(cut(ring2(10), 0), m) for m in ("AND", "OR")}
c = out["C_dag"]
print(f"C DAG: AND split={c['AND']['split']} | OR split={c['OR']['split']} [{time.time()-t0:.0f}s]", flush=True)

# ===== verdicts (frozen) =====
nA_and = sum(1 for M in (6, 8, 10, 12) if out[f"A_M{M}"]["AND"]["split"])
nA_or = sum(1 for M in (6, 8, 10, 12) if out[f"A_M{M}"]["OR"]["split"])
pba1 = nA_and == 4 and nA_or == 0
pba1_kill = nA_and <= 2 or nA_or >= 1
w1, w2 = out["B_weak1"]["AND"]["n_nodes"], out["B_weak2"]["AND"]["n_nodes"]
pbb1 = w1 <= 2 and w2 == 0
pbb1_kill = w1 >= 4
pbc1 = not (c["AND"]["split"] or c["OR"]["split"])
loo_ok = all(sum(1 for M in (6, 8, 10, 12) if M != drop and out[f"A_M{M}"]["AND"]["split"]) >= 3 and
             sum(1 for M in (6, 8, 10, 12) if M != drop and out[f"A_M{M}"]["OR"]["split"]) == 0
             for drop in (6, 8, 10, 12))
out["verdicts"] = dict(nA_and=nA_and, nA_or=nA_or, w1_nodes=w1, w2_nodes=w2,
                       PBA1=bool(pba1), PBA1_killed=bool(pba1_kill),
                       PBB1=bool(pbb1), PBB1_killed=bool(pbb1_kill), PBC1=bool(pbc1), loo_ok=bool(loo_ok))
json.dump(out, open("/home/claude/ord002b_results.json", "w"), default=float)
print(f"\nP-BA1: AND {nA_and}/4, OR {nA_or}/4 -> {'ПОДТВЕРЖДЁН' if pba1 else ('УБИТ' if pba1_kill else 'не установлен')} (LOO={loo_ok})")
print(f"P-BB1: окно 1 слабого звена = {w1} узлов (нужно <=2), 2 слабых = {w2} (нужно 0) -> "
      f"{'ПОДТВЕРЖДЁН' if pbb1 else ('УБИТ' if pbb1_kill else 'не установлен')}")
print(f"P-BC1 (DAG молчит): {'ПОДТВЕРЖДЁН' if pbc1 else 'УБИТ'}")
print(f"[{time.time()-t0:.0f}s] -> ord002b_results.json")
