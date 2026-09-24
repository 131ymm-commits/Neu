"""DET-002R — replication of closure step across 20 quenched graphs + real-topology miniature."""
import json, numpy as np, time

EPS, KAP, NS_, NCAP, DT = 0.10, 10.0, 4.0, 60, 0.01
T_TRAJ = 400.0
STEPS = int(T_TRAJ / DT)
REC_EVERY = 6
NSAMP = STEPS // REC_EVERY
BURN = int(0.05 * NSAMP)
NTRAJ = 80
LAGS = [32, 64, 128, 256, 512]
LAG_MAIN = 256
PLATEAU = [128, 256, 512]
NBMAX, MINVIS = 81, 50
RSTAR, RLO = 4.0, 3.0
BASE_SEED = 20260828

def edges_seq(M, seed):
    r = np.random.default_rng(seed)
    pairs = [(i, j) for i in range(M) for j in range(M) if i != j]
    r.shuffle(pairs)
    return pairs

def creates_cycle(A, s, d):
    seen = {d}; stack = [d]
    while stack:
        u = stack.pop()
        for v in np.where(A[u] == 1)[0]:
            if v == s: return True
            if v not in seen: seen.add(v); stack.append(v)
    return False

def adj_at(edges, M, K, dag=False):
    A = np.zeros((M, M), dtype=int)
    for t in range(K):
        s, d = edges[t]
        if dag and creates_cycle(A, s, d):
            s, d = d, s
            if creates_cycle(A, s, d): continue
        A[s, d] = 1
    return A

def has_cycle(A, M):
    indeg = A.sum(0).copy()
    q = [i for i in range(M) if indeg[i] == 0]; cnt = 0
    while q:
        u = q.pop(); cnt += 1
        for v in np.where(A[u] == 1)[0]:
            indeg[v] -= 1
            if indeg[v] == 0: q.append(v)
    return cnt < M

def k_cycle(edges, M):
    for K in range(1, len(edges) + 1):
        if has_cycle(adj_at(edges, M, K), M): return K
    return None

def hill(n): return n * n / (NS_ * NS_ + n * n)

def mf_bistable(A, M):
    def run(n0):
        n = n0.copy()
        for _ in range(60000):
            n += 0.01 * (EPS + KAP * (A.T @ hill(n)) - n)
        return n.sum()
    return (run(np.full(M, 12.0)) - run(np.full(M, EPS))) > 4.0

def simulate(A, M, ntraj, seed):
    rng = np.random.default_rng(seed)
    n = rng.poisson(np.full((ntraj, M), EPS)).astype(float)
    rec = np.empty((ntraj, NSAMP), dtype=np.int16)
    pdeath = 1 - np.exp(-DT)
    Af = A.astype(float)
    for s in range(STEPS):
        b = EPS + KAP * (hill(n) @ Af)
        n = np.clip(n + rng.poisson(b * DT) - rng.binomial(n.astype(np.int64), pdeath), 0, NCAP)
        if (s + 1) % REC_EVERY == 0:
            rec[:, (s + 1) // REC_EVERY - 1] = np.clip(n.sum(1), 0, 200)
    return rec[:, BURN:]

def spectral(data, per_traj=False):
    b = np.clip(data.astype(np.int32), 0, NBMAX - 1)
    res, Cper = {}, None
    for lag in LAGS:
        a0 = b[:, :-lag].ravel(); a1 = b[:, lag:].ravel()
        C = np.bincount(a0 * NBMAX + a1, minlength=NBMAX * NBMAX).reshape(NBMAX, NBMAX).astype(np.float64)
        C = C + C.T
        keep = C.sum(1) >= MINVIS
        if keep.sum() < 3: res[lag] = (np.nan, np.nan); continue
        Ck = C[np.ix_(keep, keep)]
        s = Ck.sum(1)
        A2 = Ck / np.sqrt(np.outer(s, s))
        evv = np.sort(np.linalg.eigvalsh((A2 + A2.T) / 2))[::-1]
        tau = lag * REC_EVERY * DT
        t2 = -tau / np.log(evv[1]) if 0 < evv[1] < 1 else np.nan
        t3 = -tau / np.log(evv[2]) if len(evv) > 2 and 0 < evv[2] < 1 else np.nan
        res[lag] = (t2, t3)
        if lag == LAG_MAIN and per_traj:
            Cper = np.zeros((data.shape[0], NBMAX, NBMAX), dtype=np.int32)
            for j in range(data.shape[0]):
                Cper[j] = np.bincount(b[j, :-lag] * NBMAX + b[j, lag:],
                                      minlength=NBMAX * NBMAX).reshape(NBMAX, NBMAX)
    return res, Cper

def R_counts(C):
    C = C + C.T
    keep = C.sum(1) >= MINVIS
    if keep.sum() < 3: return np.nan
    Ck = C[np.ix_(keep, keep)].astype(np.float64)
    s = Ck.sum(1)
    A2 = Ck / np.sqrt(np.outer(s, s))
    evv = np.sort(np.linalg.eigvalsh((A2 + A2.T) / 2))[::-1]
    if len(evv) < 3 or not (0 < evv[1] < 1) or not (0 < evv[2] < 1): return np.nan
    return np.log(evv[2]) / np.log(evv[1])

def crit(data):
    res, Cper = spectral(data, per_traj=True)
    if Cper is None:
        return None, False
    t2, t3 = res[LAG_MAIN]
    R = t2 / t3 if (t2 == t2 and t3 == t3) else np.nan
    t2s = [res[l][0] for l in PLATEAU]
    pl = (not np.any(np.isnan(t2s))) and (max(t2s) - min(t2s)) / np.mean(t2s) < 0.20
    Ct = Cper.sum(0)
    js = [R_counts(Ct - Cper[j]) for j in range(data.shape[0])]
    j16 = np.nanpercentile(js, 16)
    ok = (R == R and R >= RSTAR and pl and j16 == j16 and j16 >= RLO)
    return (float(R) if R == R else None), bool(ok)

def run_graph(edges, M, tag):
    Kc = k_cycle(edges, M)
    if Kc is None or Kc > len(edges) - 4: return None
    A = adj_at(edges, M, Kc)
    if not mf_bistable(A, M): return dict(Kc=Kc, excluded="not bistable")
    Ks = list(range(max(0, Kc - 2), Kc + 5))
    Rr, okr, Rd, okd = {}, {}, {}, {}
    for K in Ks:
        for dag in (False, True):
            Aa = adj_at(edges, M, K, dag=dag)
            rec = simulate(Aa, M, NTRAJ, seed=BASE_SEED + tag * 100 + K * 2 + int(dag))
            R, ok = crit(rec)
            if dag: Rd[K], okd[K] = R, ok
            else: Rr[K], okr[K] = R, ok
    # sustained detection
    Kstar = None
    for i in range(len(Ks) - 1):
        if okr.get(Ks[i]) and okr.get(Ks[i + 1]): Kstar = Ks[i]; break
    dag_fired = any(okd.values())
    # step position: max dR at K?
    dRs = {K: (Rr.get(K) or 0) - (Rr.get(K - 1) or 0) for K in Ks[1:] if Rr.get(K) is not None}
    step_at = max(dRs, key=dRs.get) if dRs else None
    return dict(Kc=Kc, Ks=Ks, Rr=Rr, Rd=Rd, Kstar=Kstar, dag_fired=bool(dag_fired),
                step_at=step_at, step_ok=bool(step_at == Kc))

import sys, os
t0 = time.time()
CKPT = "/home/claude/det002r_ckpt.json"
out = json.load(open(CKPT)) if os.path.exists(CKPT) else {"seeds": {}, "real": None}
M = 10
SG_FROM = int(sys.argv[1]); SG_TO = int(sys.argv[2]); DO_REAL = len(sys.argv) > 3
good = sum(1 for r in out["seeds"].values() if "excluded" not in r)
sg = SG_FROM
while good < 20 and sg < SG_TO:
    edges = edges_seq(M, sg)
    r = run_graph(edges, M, sg - 5000)
    if r is None:
        sg += 1; continue
    out["seeds"][str(sg)] = r
    json.dump(out, open(CKPT, "w"), default=float)
    if "excluded" in r:
        print(f"seed {sg}: K_cycle={r['Kc']} ИСКЛЮЧЁН ({r['excluded']})", flush=True)
    else:
        good += 1
        print(f"seed {sg}: Kc={r['Kc']} K*={r['Kstar']} dag_fired={r['dag_fired']} "
              f"step@{r['step_at']}({'✓' if r['step_ok'] else '✗'}) "
              f"[{good}/20, {time.time()-t0:.0f}s]", flush=True)
    sg += 1

res = [r for r in out["seeds"].values() if "excluded" not in r]
hit = sum(1 for r in res if r["Kstar"] is not None and r["Kstar"] in (r["Kc"], r["Kc"] + 1))
dagf = sum(1 for r in res if r["dag_fired"])
stp = sum(1 for r in res if r["step_ok"])
print(f"\nP-R1: K* в {{Kc,Kc+1}} у {hit}/20; DAG сработал у {dagf}/20 "
      f"-> {'ПОДТВЕРЖДЁН' if (hit>=16 and dagf==0) else ('УБИТ' if (dagf>=2 or hit<=12) else 'не установлен')}")
print(f"P-R2: ступень на закрытии у {stp}/20 -> {'ПОДТВЕРЖДЁН' if stp>=14 else 'не установлен/убит'}")

json.dump(out, open(CKPT, "w"), default=float)
# real-topology miniature
try:
    if not DO_REAL: raise SystemExit(print(f"[chunk done {time.time()-t0:.0f}s]"))
    lines = open("/home/claude/uaf/crossdomain/metabolic.edgelist.txt").read().split("\n")
    E = [tuple(l.split()[:2]) for l in lines if len(l.split()) >= 2]
    adj = {}
    for a, b in E:
        adj.setdefault(a, set()).add(b); adj.setdefault(b, set()).add(a)
    rng = np.random.default_rng(6001)
    start = list(adj)[rng.integers(len(adj))]
    seen = [start]
    frontier = [start]
    while len(seen) < 15 and frontier:
        u = frontier.pop(0)
        for v in sorted(adj[u]):
            if v not in seen and len(seen) < 15:
                seen.append(v); frontier.append(v)
    idx = {v: i for i, v in enumerate(seen)}
    sub = [(idx[a], idx[b]) for a, b in E if a in idx and b in idx]
    r2 = np.random.default_rng(6002)
    sub = [(a, b) if r2.random() < 0.5 else (b, a) for a, b in sub]
    order = r2.permutation(len(sub))
    edges = [sub[i] for i in order]
    rr = run_graph(edges, 15, 99)
    out["real"] = rr
    if rr and "excluded" not in rr:
        print(f"REAL(metabolic,15): Kc={rr['Kc']} K*={rr['Kstar']} dag={rr['dag_fired']} step@{rr['step_at']}")
    else:
        print("REAL: excluded/degenerate:", rr)
except Exception as ex:
    print("REAL failed:", ex)
    out["real"] = {"error": str(ex)}

json.dump(out, open("/home/claude/det002r_results.json", "w"), default=float)
print(f"[{time.time()-t0:.0f}s] -> det002r_results.json")
