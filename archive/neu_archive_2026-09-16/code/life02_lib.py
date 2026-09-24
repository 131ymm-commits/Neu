"""LIFE-02 — семейства с t_ρ ≥ 5 лагов и измерение (Ω, ρ, n*, τ, d₂) для положительно рождающих 2-блочных разбиений."""
import numpy as np, sys; sys.path.insert(0, '/home/claude')
from cog01_lib import stationary, sym_form, restrict, spectral_radius, all_bipartitions, random_chain, random_reversible
src = open('/home/claude/ach01_run.py').read(); exec("def knob_chain" + src.split("def knob_chain")[1].split("def family")[0])
TOL = 1e-9

def lazy(P, a): return (1 - a) * P + a * np.eye(len(P))

def metastable_base(n, eps, rng):
    """обратимая база: два кластера по n/2 состояний, межкластерные веса × eps (симметричный W ⇒ обратимость)"""
    W = rng.exponential(size=(n, n)); W = (W + W.T) / 2; h = n // 2; W[:h, h:] *= eps; W[h:, :h] *= eps
    return W / W.sum(1, keepdims=True)

def life(P, pi, rho, blocks, nmax=4000):
    ind = (np.asarray(blocks) == np.asarray(blocks).min()).astype(float); h = ind - pi @ ind; h /= np.sqrt(np.sum(pi * h * h))
    Om = float(np.sum(pi * (P @ h) * h))
    if not Om > rho + TOL: return None
    t_rho = -1 / np.log(rho); v = P @ (P @ h); n = 2; nstar = None; D2 = None
    while n <= nmax:
        Dn = float(np.sum(pi * v * h)) - Om ** n
        if n == 2: D2 = Dn
        if Dn < -1e-12: nstar = n; break
        v = P @ v; n += 1
    tau = nstar / t_rho if nstar else None
    return dict(Om=Om, rho=rho, t_rho=t_rho, nstar=nstar, tau=tau, d2=D2 / Om ** 2)

def family_records(chains, parts, nmax=4000):
    recs = []
    for c, (P, pi) in enumerate(chains):
        rho = spectral_radius(restrict(sym_form(P, pi), pi))
        for b in parts:
            r = life(P, pi, rho, b, nmax)
            if r: recs.append(dict(r, chain=c))
    return recs

def sorts(recs):
    s = []
    for r in recs:
        tau = r['tau'] if r['tau'] is not None else np.inf
        s.append('II' if (tau >= 1 and r['d2'] > 0) else ('I' if (tau < 1 and r['d2'] < 0) else 'X'))
    return s

def summarize(recs):
    if not recs: return dict(n=0)
    s = sorts(recs); n = len(s); taus = np.array([r['tau'] if r['tau'] is not None else np.inf for r in recs]); d2 = np.array([r['d2'] for r in recs])
    tr = np.array([r['t_rho'] for r in recs]); fin = np.isfinite(taus)
    out = dict(n=n, n_chains=len(set(r['chain'] for r in recs)), fI=s.count('I') / n, fII=s.count('II') / n, fX=s.count('X') / n, frac_d2neg=float(np.mean(d2 < 0)),
               t_rho_median=float(np.median(tr)), t_rho_p10=float(np.percentile(tr, 10)), tau_median=float(np.median(taus[fin])) if fin.any() else None, tau_p10=float(np.percentile(taus[fin], 10)) if fin.any() else None,
               tau_p90=float(np.percentile(taus[fin], 90)) if fin.any() else None, n_inf=int((~fin).sum()),
               tau_med_d2pos=(float(np.median(taus[d2 > 0])) if (d2 > 0).any() else None), tau_med_d2neg=(float(np.median(taus[d2 < 0])) if (d2 < 0).any() else None))
    h = n // 2; out['halves_fII'] = [s[:h].count('II') / max(1, h), s[h:].count('II') / max(1, n - h)]
    return out

def lifted_mixed(L, p, s, rng, boundary='A'):
    """лифтированный путь с ручкой детерминизма s: P± = (1 − s)·сдвиг(±, стена: переворот и стояние) + s·R± (случайные строки Дирихле);
    состояния (x, σ): переворот σ с вероятностью p, затем шаг по P_σ'. s = 0 — LIFT-01 (вариант A); s = 1 — лифтированная случайная динамика."""
    n = 2 * L; idx = lambda x, sg: 2 * (x - 1) + (0 if sg == 1 else 1)
    Rp = rng.dirichlet(np.ones(L), size=L); Rm = rng.dirichlet(np.ones(L), size=L); P = np.zeros((n, n))
    for x in range(1, L + 1):
        for sg in (1, -1):
            i = idx(x, sg)
            for s2, pr in ((sg, 1 - p), (-sg, p)):
                # детерминированная часть
                x2 = x + s2
                if 1 <= x2 <= L: P[i, idx(x2, s2)] += pr * (1 - s)
                else: P[i, idx(x, -s2)] += pr * (1 - s)
                # случайная часть: строка R_{s2}[x], направление сохраняется s2
                R = Rp if s2 == 1 else Rm
                for y in range(1, L + 1): P[i, idx(y, s2)] += pr * s * R[x - 1, y - 1]
    return P

def site_cuts(L):
    xs = np.repeat(np.arange(1, L + 1), 2); return [(xs > k).astype(int) for k in range(1, L)]

def lifted_local(L, p, s, boundary='A'):
    """лифтированный путь с ЛОКАЛЬНОЙ ручкой шума s: с вероятностью s шаг — симметричный (x ± 1 поровну, у стены — стояние), σ сохраняется;
    иначе — детерминированный шаг по σ (стена: переворот и стояние). Переворот σ с вероятностью p перед шагом. s = 1: сайтовый процесс обратим."""
    n = 2 * L; idx = lambda x, sg: 2 * (x - 1) + (0 if sg == 1 else 1); P = np.zeros((n, n))
    for x in range(1, L + 1):
        for sg in (1, -1):
            i = idx(x, sg)
            for s2, pr in ((sg, 1 - p), (-sg, p)):
                x2 = x + s2
                if 1 <= x2 <= L: P[i, idx(x2, s2)] += pr * (1 - s)
                else: P[i, idx(x, -s2)] += pr * (1 - s)
                for dx in (-1, 1):
                    y = x + dx
                    if 1 <= y <= L: P[i, idx(y, s2)] += pr * s / 2
                    else: P[i, idx(x, s2)] += pr * s / 2
    return P
