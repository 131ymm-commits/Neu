"""Диагностика (НЕ вердикт): расхождение оценок t1 при T=0.22 — наш симметризованный конвейер против deeptime.
Судья — физическая разметка по энергии: двухсостоянийное время обмена из committed-пребываний и время автокорреляции E."""
import numpy as np, sys, json, time
sys.path.insert(0, '/home/claude')
from lj13 import simulate
from mol_levels_lib import microstates, transition_matrix, implied_timescales, committed, dwell_times
from deeptime.markov import TransitionCountEstimator
from deeptime.markov.msm import MaximumLikelihoodMSM
out = {}
for T, s in [(0.22, 301), (0.22, 303), (0.28, 301)]:
    t0 = time.time(); r = simulate(T, s, 500000, rec_every=50); F = np.sort(r['D'][300:], axis=1); E = r['Ep'][300:]
    lab = microstates(F, 30, seed=0); tau = 16
    P, keep = transition_matrix(lab, 30, tau); its_ours, _ = implied_timescales(P, tau, 4)
    def dt_its(mode, rev):
        c = TransitionCountEstimator(lagtime=tau, count_mode=mode).fit_fetch(lab).submodel_largest()
        m = MaximumLikelihoodMSM(reversible=rev).fit(c).fetch_model(); return np.sort(m.timescales(4))[::-1]
    its_eff_rev = dt_its('effective', True); its_sl_rev = dt_its('sliding', True); its_sl_nonrev = dt_its('sliding', False); its_sample = dt_its('sample', True)
    # физическая разметка: порог по энергии между модами гистограммы (два состояния: твёрдое/жидкое)
    h, edges = np.histogram(E, 60); mids = 0.5 * (edges[1:] + edges[:-1])
    # порог — минимум гистограммы между глобальным максимумом и верхним хвостом (простая, замороженная эвристика)
    imax = np.argmax(h); hi = np.flatnonzero(mids > mids[imax] + 0.5)
    thr = None
    if hi.size:
        j = hi[np.argmin(h[hi[:max(1, len(hi) // 2)]])]; thr = float(mids[j])
    if thr is None: thr = float(np.quantile(E, 0.97))
    S = (E > thr).astype(int); Sc = committed(S, 5)
    seg, st = dwell_times(Sc); tA = seg[st == 0].mean() if (st == 0).any() else np.nan; tB = seg[st == 1].mean() if (st == 1).any() else np.nan
    t_exch = 1.0 / (1.0 / tA + 1.0 / tB) if np.isfinite(tA) and np.isfinite(tB) else np.nan
    # автокорреляционное время E (интегральное до первого нуля) и 1/e
    e = E - E.mean(); ac = np.correlate(e, e, 'full')[len(e) - 1:] / (e @ e); ac = ac[:2000]
    t_1e = float(np.argmax(ac < np.exp(-1))) if (ac < np.exp(-1)).any() else np.nan
    first0 = np.argmax(ac <= 0) if (ac <= 0).any() else len(ac); t_int = float(1 + 2 * ac[1:first0].sum())
    # доля времени в редком состоянии и число committed-переключений
    frac = float(Sc.mean()); nsw = int((np.diff(Sc) != 0).sum())
    o = dict(its_ours=its_ours.round(1).tolist(), its_eff_rev=its_eff_rev.round(1).tolist(), its_sliding_rev=its_sl_rev.round(1).tolist(),
             its_sliding_nonrev=its_sl_nonrev.round(1).tolist(), its_sample_rev=its_sample.round(1).tolist(),
             thrE=thr, frac_rare=frac, n_switch=nsw, tA=float(tA), tB=float(tB), t_exch=float(t_exch), tE_1e=t_1e, tE_int=t_int)
    out[f'LJ_{T}_{s}'] = o
    print(f"T={T} s{s}: наш t1 {its_ours[0]:.1f} | deeptime eff/rev {its_eff_rev[0]:.1f} sliding/rev {its_sl_rev[0]:.1f} sliding/nonrev {its_sl_nonrev[0]:.1f} sample/rev {its_sample[0]:.1f} "
          f"| физ.: доля редкого {frac:.3f}, переключений {nsw}, t_A {tA:.0f} t_B {tB:.0f} → t_обмена {t_exch:.1f} | AC(E): 1/e {t_1e:.0f}, интегр. {t_int:.1f} [{time.time()-t0:.0f}s]", flush=True)
    json.dump(out, open('/home/claude/core01p_diag.json', 'w'), indent=1)
