"""SORT-03 — прогон по PREREG (2026-09-15): 25 сегментов Бонна (конвейер COG-01) × 20 iAAFT-суррогатов. Числа — sort03_results.json."""
import numpy as np, json, time, warnings, sys
warnings.filterwarnings('ignore'); sys.path.insert(0, '/home/claude')
from sort02_lib import indicator, analyze_description
from sort03_lib import iaaft
from archive_loaders import series
from zeta01_lib import embed
from mol_levels_lib import microstates
from deeptime.markov import TransitionCountEstimator
from deeptime.markov.msm import MaximumLikelihoodMSM
import glob, os
t0 = time.time(); OUT = '/home/claude/sort03_results.json'; NS = 20
def est(lab, tau):
    c = TransitionCountEstimator(lagtime=tau, count_mode='sliding').fit_fetch(lab.astype(int)).submodel_largest()
    msm = MaximumLikelihoodMSM(reversible=False).fit(c).fetch_model(); msr = MaximumLikelihoodMSM(reversible=True).fit(c).fetch_model()
    return np.asarray(msm.transition_matrix), np.asarray(msm.stationary_distribution), np.asarray(msr.pcca(2).assignments)
def pipeline(x):
    lab = microstates(embed(x, 5, 2), 30, seed=0); P, pi, pcca = est(lab, 2); return analyze_description(P, pi, indicator(pi, pcca), nmax_cap=3000)
# те же 25 сегментов, что в archive_loaders.series('eeg'): каждый 4-й из первых 20 файлов группы
res = {}
for grp in ('A_Z', 'B_O', 'C_N', 'D_F', 'E_S'):
    files = sorted(glob.glob(f'/home/claude/EEG-Epilepsy-Datasets/bonn/{grp}/*.txt') + glob.glob(f'/home/claude/EEG-Epilepsy-Datasets/bonn/{grp}/*.TXT'))[:20]
    for i, fp in enumerate(files):
        if i % 4: continue
        name = f'EEG_{grp}_{os.path.basename(fp)[:4]}'; x = np.loadtxt(fp); r = pipeline(x); rng = np.random.default_rng(abs(hash(name)) % (2 ** 32))
        sur = [pipeline(iaaft(x, rng)) for _ in range(NS)]
        e_eeg = r['C1'] - r['rho']; e_s = np.array([s['C1'] - s['rho'] for s in sur]); a_s = np.array([s['a_plus'] for s in sur]); rho_s = np.array([s['rho'] for s in sur])
        res[name] = dict(rho=r['rho'], C1=r['C1'], e=float(e_eeg), born=r['born_rho'], a_plus=r['a_plus'], sur_frac=float(np.mean([s['born_rho'] for s in sur])),
                         e_p95=float(np.percentile(e_s, 95)), e_above=bool(e_eeg > np.percentile(e_s, 95)), a_p95=float(np.percentile(a_s, 95)), a_max=float(a_s.max()), a_above=bool(r['a_plus'] > np.percentile(a_s, 95)),
                         rho_sur_mean=float(rho_s.mean()), rho_dev=float(abs(rho_s.mean() - r['rho'])))
        d = res[name]; print(f"{name}: ρ={d['rho']:.3f} C1={d['C1']:.3f} e={d['e']:+.3f} рожд={d['born']} a₊={d['a_plus']:.3f} | сурр: доля рожд {d['sur_frac']:.2f}, e P95 {d['e_p95']:+.3f} (выше {d['e_above']}), a₊ P95 {d['a_p95']:.3f} max {d['a_max']:.3f} (выше {d['a_above']}), ρ̄ {d['rho_sur_mean']:.3f} (Δ {d['rho_dev']:.3f}) [{time.time()-t0:.0f}s]", flush=True)
names = list(res); born = [n for n in names if res[n]['born']]
V = dict(n_born=len(born), sur_frac_mean=float(np.mean([res[n]['sur_frac'] for n in names])), e_above_born=int(sum(res[n]['e_above'] for n in born)), a_above=int(sum(res[n]['a_above'] for n in names)),
         rho_ok=int(sum(res[n]['rho_dev'] <= 0.03 for n in names)), born_names=born, e_above_names=[n for n in born if res[n]['e_above']], a_above_names=[n for n in names if res[n]['a_above']])
V['PN1'] = bool(0.10 <= V['sur_frac_mean'] <= 0.40); V['PN2'] = bool(V['e_above_born'] <= 4); V['PN3'] = bool(V['a_above'] <= 8); V['PN4'] = bool(V['rho_ok'] >= 20)
V['K1'] = bool(V['sur_frac_mean'] < 0.03); V['K2'] = bool(V['e_above_born'] >= 6); V['K3'] = bool(V['a_above'] >= 13); V['K4'] = bool(25 - V['rho_ok'] >= 10)
json.dump(dict(segments=res, verdict=V), open(OUT, 'w'), default=float); print('ВЕРДИКТ', json.dumps(V, ensure_ascii=False)); print('ГОТОВО', f'{time.time()-t0:.0f}s')
