"""HOR-02 — рождение рекуррентности: локальный показатель горизонта β_loc(m) = log₂ t₁(2m)/t₁(m) против числа committed-переключений
верхнего процесса полного ряда в окне N_c(m). Ядра — PCCA+(2) на MSM полного ряда (χ ≥ 0.8), вехи меняются при входе в другое ядро.
По PREREG 2026-09-09 (с поправкой до прогона)."""
import numpy as np, warnings
warnings.filterwarnings('ignore')
from deeptime.markov import TransitionCountEstimator
from deeptime.markov.msm import MaximumLikelihoodMSM
from mol_levels_lib import microstates

def fit_msm(lab, tau, reversible=True):
    c = TransitionCountEstimator(lagtime=tau, count_mode='effective').fit_fetch(lab.astype(int)).submodel_largest()
    return MaximumLikelihoodMSM(reversible=reversible).fit(c).fetch_model(), c

def t1(lab, tau, reversible=False):
    """верхняя шкала; по поправке 2 PREREG первичная — НЕобратимая ML-MSM (обратимая завышает t₁ на вложениях)"""
    try:
        msm, _ = fit_msm(lab, tau, reversible); ts = np.sort(np.real(msm.timescales(3)))[::-1]
        return float(ts[0]) if np.isfinite(ts[0]) and ts[0] > 0 else None
    except Exception:
        return None

def cores_top(lab, tau, chi_min=0.8):
    """ядра двух метастабильных множеств PCCA+(2) MSM полного ряда; возвращает массив core[label] ∈ {+1, −1, 0} и сводку"""
    msm, c = fit_msm(lab, tau); p = msm.pcca(2); chi = p.memberships; syms = np.asarray(c.state_symbols)
    core = np.zeros(int(lab.max()) + 1, int); sizes = []
    for j, sgn in ((0, 1), (1, -1)):
        idx = np.where(chi[:, j] >= chi_min)[0]
        if len(idx) < 2: idx = np.argsort(chi[:, j])[-3:]
        core[syms[idx]] = sgn; sizes.append(int(len(idx)))
    ts = np.sort(msm.timescales(3))[::-1]; t1n = t1(lab, tau)
    return core, dict(t1_full=(t1n if t1n is not None else float(ts[0])), t1_full_rev=float(ts[0]), t2_full=float(ts[1]) if len(ts) > 1 and np.isfinite(ts[1]) else None, core_sizes=sizes, n_states=int(len(syms)))

def milestones(lab, core):
    m = core[lab]; seq = m.copy(); last = 0
    for i in range(len(seq)):
        if seq[i] == 0: seq[i] = last
        else: last = seq[i]
    return seq

def n_switch(seq):
    s = seq[seq != 0]
    return int(np.sum(np.diff(s) != 0)) if len(s) > 1 else 0

def horizons(n):
    return [n // 16, n // 8, n // 4, n // 2, n] if n >= 8000 else [n // 8, n // 4, n // 2, n]

def analyze(F, tau, k, hidden=None):
    """F — признаки (n × d); hidden — скрытое состояние верхнего процесса (для телеграфов) или None.
    Возвращает словарь: горизонты, t₁ по префиксам/суффиксам, N_c по префиксам/суффиксам, N_true, пары (N_c(m), β_loc(m))."""
    n = len(F); lab_full = microstates(F, k, seed=0)
    try:
        core, info = cores_top(lab_full, tau)
    except Exception as e:
        return dict(error=str(e))
    mil = milestones(lab_full, core); hs = horizons(n)
    tp, ts_, ncp, ncs, ntp, nts, tpr, tsr = [], [], [], [], [], [], [], []
    for m in hs:
        lp, ls = microstates(F[:m], k, seed=0), microstates(F[n - m:], k, seed=0)
        tp.append(t1(lp, tau)); ts_.append(t1(ls, tau)); tpr.append(t1(lp, tau, True)); tsr.append(t1(ls, tau, True))
        ncp.append(n_switch(mil[:m])); ncs.append(n_switch(mil[n - m:]))
        if hidden is not None:
            ntp.append(int(np.sum(np.diff(hidden[:m]) != 0))); nts.append(int(np.sum(np.diff(hidden[n - m:]) != 0)))
    pairs = []
    for i in range(len(hs) - 1):
        for side, tv, nc in (('p', tp, ncp), ('s', ts_, ncs)):
            if tv[i] is not None and tv[i + 1] is not None and tv[i] > 0 and tv[i + 1] > 0:
                pairs.append(dict(side=side, m=hs[i], nc_m=nc[i], nc_2m=nc[i + 1], beta=float(np.log2(tv[i + 1] / tv[i]))))
    # средние по префиксу/суффиксу (для сводных карт)
    pairs_avg = []
    for i in range(len(hs) - 1):
        bs = [p['beta'] for p in pairs if p['m'] == hs[i]]
        if bs: pairs_avg.append(dict(m=hs[i], nc_m=float(np.mean([ncp[i], ncs[i]])), nc_2m=float(np.mean([ncp[i + 1], ncs[i + 1]])), beta=float(np.mean(bs))))
    pairs_rev = []
    for i in range(len(hs) - 1):
        for side, tv, nc in (('p', tpr, ncp), ('s', tsr, ncs)):
            if tv[i] is not None and tv[i + 1] is not None and tv[i] > 0 and tv[i + 1] > 0:
                pairs_rev.append(dict(side=side, m=hs[i], nc_m=nc[i], nc_2m=nc[i + 1], beta=float(np.log2(tv[i + 1] / tv[i]))))
    N_full = n_switch(mil)
    return dict(n=n, k=k, tau=tau, hs=hs, t1_prefix=tp, t1_suffix=ts_, t1_prefix_rev=tpr, t1_suffix_rev=tsr, pairs_rev=pairs_rev, nc_prefix=ncp, nc_suffix=ncs, ntrue_prefix=ntp or None, ntrue_suffix=nts or None,
                N_c_full=N_full, N_true_full=(int(np.sum(np.diff(hidden) != 0)) if hidden is not None else None), pairs=pairs, pairs_avg=pairs_avg, **info)

def telegraph(n, L, rng, noise=0.3):
    s = np.zeros(n); state = 1.0; i = 0
    while i < n:
        d = int(rng.exponential(L)) + 1; s[i:i + d] = state; state = -state; i += d
    return s + noise * rng.normal(size=n), s

def hier_telegraph(n, L, rng, noise=0.3, amps=(1.0, 1.0, 1.0)):
    """сумма трёх телеграфов с пребываниями L/25, L/5, L; amps — амплитуды (быстрый, средний, верхний).
    При 1/1/1 наблюдаемая x вырождена по верхнему состоянию (x = +1 — три комбинации), MSM его не видит (диагностика 2026-09-09);
    семейство hier2 с амплитудами 0.5/1/2 разрешает все 8 уровней."""
    x = np.zeros(n); top = None
    for Lk, a in zip((L / 25, L / 5, L), amps):
        xk, sk = telegraph(n, max(Lk, 1.5), rng, noise=0.0); x += a * xk; top = sk
    return x + noise * rng.normal(size=n), top
