"""SORT-05 — пилот для калибровки (2026-09-16): сегменты, НЕ входящие в тест (D и C — файлы 61–70, A — файлы 41–45; тест — D/C 21–60, A 21–40),
50 iAAFT-суррогатов на сегмент через конвейер COG-01. Считает: (1) ложные уровни правил «> P95 по 50» (LOO суррогат-против-остальных-49):
a₊, e, рождено ∧ e > P95, постоянное ∧ a₊ > P95; (2) нуль-долю «постоянное рождение с a₊ > 1» среди суррогатов (без порога);
(3) устойчивость P95: первые 20 против всех 50. Числа — sort05_pilot.json."""
import numpy as np, json, time, warnings, sys, zlib, glob, os
warnings.filterwarnings('ignore'); sys.path.insert(0, '/home/claude')
from sort02_lib import indicator, analyze_description
from sort03_lib import iaaft
from zeta01_lib import embed
from mol_levels_lib import microstates
from deeptime.markov import TransitionCountEstimator
from deeptime.markov.msm import MaximumLikelihoodMSM
t0 = time.time(); OUT = '/home/claude/sort05_pilot.json'; NS = 50
def est(lab, tau):
    c = TransitionCountEstimator(lagtime=tau, count_mode='sliding').fit_fetch(lab.astype(int)).submodel_largest()
    msm = MaximumLikelihoodMSM(reversible=False).fit(c).fetch_model(); msr = MaximumLikelihoodMSM(reversible=True).fit(c).fetch_model()
    return np.asarray(msm.transition_matrix), np.asarray(msm.stationary_distribution), np.asarray(msr.pcca(2).assignments)
def pipeline(x):
    lab = microstates(embed(x, 5, 2), 30, seed=0); P, pi, pcca = est(lab, 2); r = analyze_description(P, pi, indicator(pi, pcca), nmax_cap=3000)
    perm = bool(r['born_rho'] and r.get('n_life_rho') is not None and r['n_life_rho'] >= r['n_max'])
    return dict(rho=r['rho'], rho_plus=r['rho_plus'], C1=r['C1'], e=float(r['C1'] - r['rho']), born=bool(r['born_rho']), a=r['a_plus'], n_life=r.get('n_life_rho'), n_max=r['n_max'], perm=perm)
SEL = {'D_F': range(60, 70), 'C_N': range(60, 70), 'A_Z': range(40, 45)}   # индексы 0-based: файлы 61–70 и 41–45
res = {}; fp = dict(a=[], e=[], born_e=[], perm_a=[]); null_perm1 = []; null_born = []; p95_shift = dict(a=[], e=[])
for grp, idx in SEL.items():
    files = sorted(glob.glob(f'/home/claude/EEG-Epilepsy-Datasets/bonn/{grp}/*.txt') + glob.glob(f'/home/claude/EEG-Epilepsy-Datasets/bonn/{grp}/*.TXT'))
    for i in idx:
        fp_ = files[i]; name = f'EEG_{grp}_{os.path.basename(fp_)[:4]}'; x = np.loadtxt(fp_); r = pipeline(x)
        rng = np.random.default_rng(zlib.crc32(name.encode())); sur = [pipeline(iaaft(x, rng)) for _ in range(NS)]
        a_s = np.array([s['a'] for s in sur], float); e_s = np.array([s['e'] for s in sur]); b_s = np.array([s['born'] for s in sur]); p_s = np.array([s['perm'] for s in sur])
        for j in range(NS):
            oth = np.delete(np.arange(NS), j)
            fp['a'].append(bool(a_s[j] > np.percentile(a_s[oth], 95))); fp['e'].append(bool(e_s[j] > np.percentile(e_s[oth], 95)))
            fp['born_e'].append(bool(b_s[j] and e_s[j] > np.percentile(e_s[oth], 95))); fp['perm_a'].append(bool(p_s[j] and a_s[j] > np.percentile(a_s[oth], 95)))
        null_perm1.extend(list(p_s & (a_s > 1))); null_born.extend(list(b_s))
        p95_shift['a'].append(float(np.percentile(a_s[:20], 95) - np.percentile(a_s, 95))); p95_shift['e'].append(float(np.percentile(e_s[:20], 95) - np.percentile(e_s, 95)))
        res[name] = dict(group=grp[0], **r, a_p95=float(np.percentile(a_s, 95)), e_p95=float(np.percentile(e_s, 95)), a_above=bool(r['a'] > np.percentile(a_s, 95)), e_above=bool(r['e'] > np.percentile(e_s, 95)),
                         sur_born_frac=float(b_s.mean()), sur_perm_frac=float(p_s.mean()), sur_perm1_frac=float(np.mean(p_s & (a_s > 1))), sur_a_max=float(a_s.max()), rho_sur_mean=float(np.mean([s['rho'] for s in sur])))
        d = res[name]; print(f"{name}: ρ={d['rho']:.3f} e={d['e']:+.3f} рожд={d['born']} пост={d['perm']} a₊={d['a']:.2f} (P95 сурр {d['a_p95']:.2f}, сверх {d['a_above']}) | сурр: рожд {d['sur_born_frac']:.2f} пост {d['sur_perm_frac']:.2f} пост∧a>1 {d['sur_perm1_frac']:.2f} [{time.time()-t0:.0f}s]", flush=True)
C = dict(NS=NS, n_tests=len(fp['a']), fp_a=float(np.mean(fp['a'])), fp_e=float(np.mean(fp['e'])), fp_born_e=float(np.mean(fp['born_e'])), fp_perm_a=float(np.mean(fp['perm_a'])),
         null_perm1=float(np.mean(null_perm1)), null_born=float(np.mean(null_born)), p95_shift_a_absmax=float(np.max(np.abs(p95_shift['a']))), p95_shift_a_absmed=float(np.median(np.abs(p95_shift['a']))),
         p95_shift_e_absmax=float(np.max(np.abs(p95_shift['e']))), by_group={g: dict(n=sum(1 for n in res if res[n]['group'] == g), perm1=sum(1 for n in res if res[n]['group'] == g and res[n]['perm'] and res[n]['a'] > 1),
                                                                                        a_above=sum(1 for n in res if res[n]['group'] == g and res[n]['a_above']), born=sum(1 for n in res if res[n]['group'] == g and res[n]['born'])) for g in 'ACD'})
json.dump(dict(segments=res, calib=C), open(OUT, 'w'), ensure_ascii=False, indent=0, default=float)
print('КАЛИБРОВКА', json.dumps(C, ensure_ascii=False)); print('ГОТОВО', f'{time.time()-t0:.0f}s')
