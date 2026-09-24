"""COG-01 — рождение уровня при огрублении: (1) точные случайные цепи (обратимые/необратимые, N = 3, 4, 6 × 2000, все 2-разбиения); (2) оценённые цепи архива
(необратимая ML-MSM) — огрубления PCCA(2), случайные 2- и 5-блочные; (3) описательно — семейство «цикл + сброс». По PREREG 2026-09-09."""
import numpy as np, json, os, sys, time, warnings
warnings.filterwarnings('ignore'); sys.path.insert(0, '/home/claude')
from cog01_lib import *
B = '/home/claude'; OUT = f'{B}/cog01_results.json'; res = json.load(open(OUT)) if os.path.exists(OUT) else {}; t0 = time.time()
stage = sys.argv[1] if len(sys.argv) > 1 else 'all'
if stage in ('all', 'random') and 'random' not in res:
    rng = np.random.default_rng(2026); R = {}
    for fam, gen in (('rev', random_reversible), ('nonrev', random_chain)):
        for n in (3, 4, 6):
            parts = all_bipartitions(n); rows = []
            for i in range(2000):
                r = analyze_chain(gen(n, rng), partitions=parts); rows.append((r['delta'], r['n_birth'], r['bound_violated'], r['u_max'] or 0.0, r['rho'], r['max_l2']))
            rows = np.array(rows, float); d, nb, viol, um, rho, ml = rows.T
            born = nb > 0; auc = None
            if born.any() and (~born).any():
                # AUC ранжирования δ → рождение (Манна–Уитни)
                from scipy.stats import mannwhitneyu
                U = mannwhitneyu(d[born], d[~born]).statistic; auc = float(U / (born.sum() * (~born).sum()))
            # джекнайф по половинам
            halves = [float(np.mean(born[:1000])), float(np.mean(born[1000:]))]
            # рождённая шкала относительно верхней шкалы тонкой цепи (в единицах лага): ln ρ / ln λ₂
            ratio = [np.log(r_) / np.log(m_) for r_, m_, b_ in zip(rho, ml, born) if b_ and 0 < m_ < 1 and 0 < r_ < 1]
            R[f'{fam}_n{n}'] = dict(n_chains=2000, n_parts=len(parts), frac_chains_birth=float(born.mean()), frac_parts_birth=float(nb.sum() / (2000 * len(parts))), bound_violations=int(viol.sum()),
                                    delta_median=float(np.median(d)), delta_born=(float(np.median(d[born])) if born.any() else None), delta_unborn=(float(np.median(d[~born])) if (~born).any() else None),
                                    frac_spectraloid_born=(float(np.mean(born[d < 1e-6])) if (d < 1e-6).any() else None), n_spectraloid=int((d < 1e-6).sum()), auc_delta=auc, halves=halves,
                                    u_max_median=(float(np.median(um[born])) if born.any() else None), t_ratio_median=(float(np.median(ratio)) if ratio else None), t_ratio_p90=(float(np.percentile(ratio, 90)) if ratio else None))
            print(fam, n, json.dumps(R[f'{fam}_n{n}'], default=float)[:400], f'[{time.time()-t0:.0f}s]', flush=True)
    res['random'] = R; json.dump(res, open(OUT, 'w'), default=float)
if stage in ('all', 'cycle') and 'cycle' not in res:
    # описательно (не в PREREG): цикл длины N с вероятностью 1−ε шага вперёд и сбросом в состояние 1 с вероятностью ε (ненормальное возмущение ранга 1)
    C = {}
    for N in (4, 8):
        for eps in (0.02, 0.05, 0.1, 0.2, 0.4):
            P = np.zeros((N, N))
            for i in range(N): P[i, (i + 1) % N] = 1 - eps; P[i, 0] += eps
            parts = all_bipartitions(N) if N <= 8 else None
            r = analyze_chain(P, partitions=parts); C[f'N{N}_eps{eps}'] = dict(rho=r['rho'], w=r['w'], delta=r['delta'], n_birth=r['n_birth'], n_part=r['n_part'], max_l2=r['max_l2'], t_ratio=(float(np.log(r['rho']) / np.log(r['max_l2'])) if r['max_l2'] and 0 < r['max_l2'] < 1 and 0 < r['rho'] < 1 else None))
            print('цикл+сброс', N, eps, json.dumps(C[f'N{N}_eps{eps}'], default=float), flush=True)
    res['cycle'] = C; json.dump(res, open(OUT, 'w'), default=float)
if stage in ('all', 'archive'):
    from archive_loaders import series
    from mol_levels_lib import microstates
    from deeptime.markov import TransitionCountEstimator
    from deeptime.markov.msm import MaximumLikelihoodMSM
    from hor02_lib import telegraph
    from zeta01_lib import embed
    A = res.get('archive', {})
    def est_P(lab, tau):
        c = TransitionCountEstimator(lagtime=tau, count_mode='sliding').fit_fetch(lab.astype(int)).submodel_largest()
        msm = MaximumLikelihoodMSM(reversible=False).fit(c).fetch_model(); msr = MaximumLikelihoodMSM(reversible=True).fit(c).fetch_model()
        return np.asarray(msm.transition_matrix), np.asarray(msm.stationary_distribution), np.asarray(msr.pcca(2).assignments)
    def run(name, F, tau, k, group):
        if name in A: return
        lab = microstates(F, k, seed=0); P, pi, pcca = est_P(lab, tau); rng = np.random.default_rng(1)
        r2 = analyze_chain(P, pi=pi, rng=rng, n_random=300, n_blocks=2); r5 = analyze_chain(P, pi=pi, rng=rng, n_random=300, n_blocks=5); rp = analyze_chain(P, pi=pi, partitions=[pcca])
        # неспектралоидность оценённой цепи и асимметрия: ‖A − Aᵀ‖/‖A‖ как мера необратимости
        Am = sym_form(P, pi); asym = float(np.linalg.norm(Am - Am.T) / np.linalg.norm(Am))
        A[name] = dict(group=group, n_states=int(len(P)), rho=r2['rho'], w=r2['w'], delta=r2['delta'], asym=asym, frac_birth_2=r2['frac_birth'], frac_birth_5=r5['frac_birth'], birth_pcca=bool(rp['n_birth'] > 0), l2_pcca=rp['max_l2'],
                        max_l2_2=r2['max_l2'], t_fine=float(-tau / np.log(r2['rho'])) if 0 < r2['rho'] < 1 else None, t_born_max=(float(-tau / np.log(r2['max_l2'])) if r2['max_l2'] and 0 < r2['max_l2'] < 1 else None), bound_violated=bool(r2['bound_violated'] or r5['bound_violated']))
        res['archive'] = A; json.dump(res, open(OUT, 'w'), default=float)
        print(f"{name:24s} [{group}] k={len(P)} ρ {r2['rho']:.3f} w {r2['w']:.3f} δ {r2['delta']:.3f} асим {asym:.3f} | рождений: 2-блочные {r2['frac_birth']:.3f} 5-блочные {r5['frac_birth']:.3f} PCCA {rp['n_birth']>0} | t_fine {A[name]['t_fine']} t_born_max {A[name]['t_born_max']} [{time.time()-t0:.0f}s]", flush=True)
    for s in range(5):
        rng = np.random.default_rng(1000 * 40 + s); x, _ = telegraph(8000, 40, rng); run(f'tel40_s{s}', embed(x, 4), 1, 30, 'tel')
    for name, F, tau, k, group in series(('real', 'eeg', 'insilico')): run(name, F, tau, k, group)
print('ГОТОВО', f'{time.time()-t0:.0f}s', flush=True)
