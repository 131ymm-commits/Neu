"""PERS-01 — персистентность рождённого уровня: (i) инверсии верхней шкалы вдоль цепи огрублений (рекурсивная бисекция, точный лумпинг) при фиксированном τ;
(ii) ход отношения r(n) = ITS_грубой(nτ)/ITS_тонкой(nτ) по лагам n = 1, 2, 4, 8 для PCCA(2)-огрубления. По PREREG 2026-09-09."""
import numpy as np, json, os, sys, time, warnings
warnings.filterwarnings('ignore'); sys.path.insert(0, '/home/claude')
from archive_loaders import series
from mol_levels_lib import microstates
from deeptime.markov import TransitionCountEstimator
from deeptime.markov.msm import MaximumLikelihoodMSM
from hor02_lib import telegraph
from zeta01_lib import embed
from cog01_lib import sym_form, restrict, numerical_radius, spectral_radius, lump, lambda2
B = '/home/claude'; OUT = f'{B}/pers01_results.json'; res = json.load(open(OUT)) if os.path.exists(OUT) else {}; t0 = time.time()
def fit(lab, tau, rev=False):
    c = TransitionCountEstimator(lagtime=tau, count_mode='sliding').fit_fetch(lab.astype(int)).submodel_largest()
    return MaximumLikelihoodMSM(reversible=rev).fit(c).fetch_model(), c
def top_its(msm, tau):
    ts = np.sort(np.abs(np.real(msm.timescales(3))))[::-1]; return float(ts[0])
def bisect_hierarchy(P, pi, depth=4):
    """вложенные разбиения: рекурсивная бисекция по знаку верхнего собственного вектора симметризованной (обратимой) части внутри блока"""
    n = len(P); levels = []; blocks = np.zeros(n, int)
    for d in range(depth):
        new = np.zeros(n, int); nb = 0
        for b in np.unique(blocks):
            idx = np.where(blocks == b)[0]
            if len(idx) < 2: new[idx] = nb; nb += 1; continue
            Pb = P[np.ix_(idx, idx)]; pib = pi[idx] / pi[idx].sum(); S = (sym_form(Pb + 1e-12, pib) + sym_form(Pb + 1e-12, pib).T) / 2
            ev, U = np.linalg.eigh(S); v = U[:, -2] if len(idx) > 1 else np.zeros(len(idx))
            sgn = v >= 0
            if sgn.all() or (~sgn).all(): sgn[np.argmax(np.abs(v))] = ~sgn[np.argmax(np.abs(v))]
            new[idx[sgn]] = nb; new[idx[~sgn]] = nb + 1; nb += 2
        blocks = new; levels.append(blocks.copy())
    return levels  # от 2 блоков к 2^depth
def run(name, F, tau, k, group):
    if name in res: return
    lab = microstates(F, k, seed=0); n = len(lab)
    mn, c = fit(lab, tau); P = np.asarray(mn.transition_matrix); pi = np.asarray(mn.stationary_distribution); syms = np.asarray(c.state_symbols)
    A0 = restrict(sym_form(P, pi), pi); rho = spectral_radius(A0); w = numerical_radius(A0)
    # (i) цепь огрублений
    levels = bisect_hierarchy(P, pi, depth=min(4, int(np.floor(np.log2(len(P))))))
    l2 = [lambda2(lump(P, pi, b)[0]) for b in levels]  # от грубого к тонкому
    l2_fine = rho
    seq = l2 + [l2_fine]  # 2, 4, 8, 16, k
    # допуск оценки: |λ₂| тонкой цепи по половинам
    tol = 0.0
    try:
        h = [spectral_radius(restrict(sym_form(np.asarray(m.transition_matrix), np.asarray(m.stationary_distribution)), np.asarray(m.stationary_distribution))) for m in (fit(lab[:n // 2], tau)[0], fit(lab[n // 2:], tau)[0])]
        tol = abs(h[0] - h[1]) / 2
    except Exception: pass
    inversions = int(sum(seq[i] > seq[i + 1] + max(tol, 1e-6) for i in range(len(seq) - 1)))
    # (ii) вдоль лага для PCCA(2)
    mr, _ = fit(lab, tau, rev=True); pc = np.asarray(mr.pcca(2).assignments); coarse = np.zeros(lab.max() + 1, int) - 1; coarse[syms] = pc
    lab_c = coarse[lab]; ok = lab_c >= 0
    rr = {}
    for nlag in (1, 2, 4, 8):
        try:
            mf, _ = fit(lab, tau * nlag); mc, _ = fit(lab_c[ok], tau * nlag); rr[str(nlag)] = dict(fine=top_its(mf, tau * nlag), coarse=top_its(mc, tau * nlag))
            rr[str(nlag)]['r'] = rr[str(nlag)]['coarse'] / rr[str(nlag)]['fine']
        except Exception as e:
            rr[str(nlag)] = dict(error=str(e))
    res[name] = dict(group=group, k=int(len(P)), rho=rho, w=w, delta=w - rho, l2_levels=seq, n_levels=[int(len(np.unique(b))) for b in levels] + [int(len(P))], tol=tol, inversions=inversions, lag=rr)
    json.dump(res, open(OUT, 'w'), default=float)
    rs = [rr[s].get('r') for s in ('1', '2', '4', '8')]
    print(f"{name:24s} [{group}] δ {w-rho:.3f} | |λ₂| по уровням {[round(x, 3) for x in seq]} инверсий {inversions} (допуск {tol:.4f}) | r(n) {[None if x is None else round(x, 2) for x in rs]} [{time.time()-t0:.0f}s]", flush=True)
for s in range(5):
    rng = np.random.default_rng(1000 * 40 + s); x, _ = telegraph(8000, 40, rng); run(f'tel40_s{s}', embed(x, 4), 1, 30, 'tel')
for name, F, tau, k, group in series(('real', 'eeg', 'insilico')): run(name, F, tau, k, group)
print('ГОТОВО', f'{time.time()-t0:.0f}s', flush=True)
