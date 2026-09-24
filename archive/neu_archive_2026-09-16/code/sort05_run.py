"""SORT-05 — прогон по PREREG (2026-09-16): D файлы 21–60 (40), C файлы 21–60 (40), A файлы 21–40 (20) × конвейер COG-01 × 50 iAAFT-суррогатов.
Сид суррогатов — crc32 имени. Числа — sort05_results.json."""
import numpy as np, json, time, warnings, sys, zlib, glob, os
warnings.filterwarnings('ignore'); sys.path.insert(0, '/home/claude')
from sort02_lib import indicator, analyze_description
from sort03_lib import iaaft
from zeta01_lib import embed
from mol_levels_lib import microstates
from deeptime.markov import TransitionCountEstimator
from deeptime.markov.msm import MaximumLikelihoodMSM
t0 = time.time(); OUT = '/home/claude/sort05_results.json'; NS = 50
def est(lab, tau):
    c = TransitionCountEstimator(lagtime=tau, count_mode='sliding').fit_fetch(lab.astype(int)).submodel_largest()
    msm = MaximumLikelihoodMSM(reversible=False).fit(c).fetch_model(); msr = MaximumLikelihoodMSM(reversible=True).fit(c).fetch_model()
    return np.asarray(msm.transition_matrix), np.asarray(msm.stationary_distribution), np.asarray(msr.pcca(2).assignments)
def pipeline(x):
    lab = microstates(embed(x, 5, 2), 30, seed=0); P, pi, pcca = est(lab, 2); r = analyze_description(P, pi, indicator(pi, pcca), nmax_cap=3000)
    perm = bool(r['born_rho'] and r.get('n_life_rho') is not None and r['n_life_rho'] >= r['n_max'])
    return dict(rho=r['rho'], rho_plus=r['rho_plus'], real_plus=r['real_plus'], C1=r['C1'], e=float(r['C1'] - r['rho']), born=bool(r['born_rho']), a=r['a_plus'],
                n_life=r.get('n_life_rho'), n_max=r['n_max'], perm=perm, late=r.get('late_plus'))
SEL = {'D_F': range(20, 60), 'C_N': range(20, 60), 'A_Z': range(20, 40)}   # 0-based: файлы 21–60 и 21–40
res = {}
for grp, idx in SEL.items():
    files = sorted(glob.glob(f'/home/claude/EEG-Epilepsy-Datasets/bonn/{grp}/*.txt') + glob.glob(f'/home/claude/EEG-Epilepsy-Datasets/bonn/{grp}/*.TXT'))
    for i in idx:
        fp_ = files[i]; name = f'EEG_{grp}_{os.path.basename(fp_)[:4]}'; x = np.loadtxt(fp_); r = pipeline(x)
        rng = np.random.default_rng(zlib.crc32(name.encode())); sur = [pipeline(iaaft(x, rng)) for _ in range(NS)]
        a_s = np.array([s['a'] for s in sur], float); e_s = np.array([s['e'] for s in sur]); b_s = np.array([s['born'] for s in sur]); p_s = np.array([s['perm'] for s in sur])
        a_p95 = float(np.percentile(a_s, 95)); e_p95 = float(np.percentile(e_s, 95))
        perm1 = bool(r['perm'] and r['a'] is not None and r['a'] > 1)
        res[name] = dict(group=grp[0], **r, a_p95=a_p95, e_p95=e_p95, a_above=bool(r['a'] is not None and r['a'] > a_p95), e_above=bool(r['e'] > e_p95), born_above=bool(r['born'] and r['e'] > e_p95),
                         perm1=perm1, perm1_above=bool(perm1 and r['a'] > a_p95), sur_born_frac=float(b_s.mean()), sur_perm1_frac=float(np.mean(p_s & (a_s > 1))), sur_a_max=float(a_s.max()),
                         rho_sur_mean=float(np.mean([s['rho'] for s in sur])), rho_plus_eq=bool(abs(r['rho_plus'] - r['rho']) < 1e-9))
        d = res[name]; print(f"{name}: ρ={d['rho']:.3f} e={d['e']:+.3f} рожд={d['born']} пост={d['perm']} a₊={d['a']:.2f} (P95 {d['a_p95']:.2f}; сверх {d['a_above']}) пост∧a>1={d['perm1']} сверх={d['perm1_above']} | нуль: рожд {d['sur_born_frac']:.2f} пост∧a>1 {d['sur_perm1_frac']:.2f} ρ₊=ρ {d['rho_plus_eq']} [{time.time()-t0:.0f}s]", flush=True)
names = list(res)
def cnt(g, key): return int(sum(bool(res[n][key]) for n in names if res[n]['group'] == g))
G = {g: dict(n=int(sum(res[n]['group'] == g for n in names)), born=cnt(g, 'born'), perm1=cnt(g, 'perm1'), perm1_above=cnt(g, 'perm1_above'), a_above=cnt(g, 'a_above'), e_above=cnt(g, 'e_above'),
             born_above=cnt(g, 'born_above'), rho_plus_eq=cnt(g, 'rho_plus_eq'), sur_born_mean=float(np.mean([res[n]['sur_born_frac'] for n in names if res[n]['group'] == g])),
             sur_perm1_mean=float(np.mean([res[n]['sur_perm1_frac'] for n in names if res[n]['group'] == g]))) for g in 'ACD'}
Dperm = [n for n in names if res[n]['group'] == 'D' and res[n]['perm1']]
frac_low = float(np.mean([res[n]['sur_born_frac'] < 0.5 for n in Dperm])) if Dperm else float('nan')
frac_high = float(np.mean([res[n]['sur_born_frac'] >= 0.5 for n in Dperm])) if Dperm else float('nan')
V = dict(groups=G, D_perm1_names=Dperm, D_perm1_above_names=[n for n in names if res[n]['group'] == 'D' and res[n]['perm1_above']], C_perm1_names=[n for n in names if res[n]['group'] == 'C' and res[n]['perm1']],
         A_perm1_names=[n for n in names if res[n]['group'] == 'A' and res[n]['perm1']], D_perm_sur_low_frac=frac_low, D_perm_sur_high_frac=frac_high)
V['PV1'] = bool(G['D']['perm1'] >= 5 and G['D']['perm1'] - G['C']['perm1'] >= 3 and G['A']['perm1'] <= 2)
V['PV2'] = bool(G['D']['a_above'] >= 10 and G['C']['a_above'] <= 6 and G['A']['a_above'] <= 4)
V['PV3'] = bool(G['D']['perm1_above'] >= 3 and G['C']['perm1_above'] <= 2 and G['D']['perm1_above'] > G['C']['perm1_above'])
V['PV4'] = bool(Dperm and frac_low >= 0.5)
V['K1'] = bool(G['D']['perm1'] <= G['C']['perm1']); V['K2'] = bool(G['D']['perm1_above'] <= 1); V['K3'] = bool(G['D']['a_above'] <= 5); V['K4'] = bool(Dperm and frac_high >= 0.75)
V['margins'] = dict(PV1_D=G['D']['perm1'] - 5, PV1_DC=G['D']['perm1'] - G['C']['perm1'] - 3, PV2_D=G['D']['a_above'] - 10, PV3_D=G['D']['perm1_above'] - 3)
json.dump(dict(segments=res, verdict=V, params=dict(NS=NS, k=30, m=5, step=2, tau=2, seed_kmeans=0, seed_sur='crc32(name)', test='D 21-60, C 21-60, A 21-40')), open(OUT, 'w'), ensure_ascii=False, indent=0, default=float)
print('ГРУППЫ', json.dumps(G, ensure_ascii=False)); print('ВЕРДИКТ', json.dumps({k: v for k, v in V.items() if k != 'groups'}, ensure_ascii=False)); print('ГОТОВО', f'{time.time()-t0:.0f}s')
