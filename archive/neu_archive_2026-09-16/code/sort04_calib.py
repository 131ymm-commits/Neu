"""SORT-04 — пост-хок калибровка нуля (не в зачёт): тот же прогон (те же сиды crc32), но с сохранением массивов суррогатов;
уровень ложных срабатываний правила «e > P95 по 20 суррогатам» — суррогат-против-остальных-19 (обменяемость под нулём);
проверка воспроизводимости e_p95 против sort04_results.json. Числа — sort04_calib.json. Функции скопированы из sort04_run.py
(импорт sort04_run перезапустил бы прогон)."""
import numpy as np, json, time, warnings, sys, zlib, glob, os
warnings.filterwarnings('ignore'); sys.path.insert(0, '/home/claude')
from sort02_lib import indicator, analyze_description
from sort03_lib import iaaft
from zeta01_lib import embed
from mol_levels_lib import microstates
from deeptime.markov import TransitionCountEstimator
from deeptime.markov.msm import MaximumLikelihoodMSM
t0 = time.time(); OUT = '/home/claude/sort04_calib.json'; NS = 20; TAU_TR = 2
def est(lab, tau):
    c = TransitionCountEstimator(lagtime=tau, count_mode='sliding').fit_fetch(lab.astype(int)).submodel_largest()
    msm = MaximumLikelihoodMSM(reversible=False).fit(c).fetch_model(); msr = MaximumLikelihoodMSM(reversible=True).fit(c).fetch_model()
    return np.asarray(msm.transition_matrix), np.asarray(msm.stationary_distribution), np.asarray(msr.pcca(2).assignments)
def pipeline(x):
    lab = microstates(embed(x, 5, 2), 30, seed=0); P, pi, pcca = est(lab, 2); return analyze_description(P, pi, indicator(pi, pcca), nmax_cap=3000)
def TR(x, tau=TAU_TR):
    d = x[tau:] - x[:-tau]; return float(np.mean(d ** 3) / np.mean(d ** 2) ** 1.5)
prev = json.load(open('/home/claude/sort04_results.json'))['segments']
arr = {}; fp_e = []; fp_tr = []; fp_a = []; fp_born_e = []; repro = []
for grp in ('A_Z', 'B_O', 'C_N', 'D_F', 'E_S'):
    files = sorted(glob.glob(f'/home/claude/EEG-Epilepsy-Datasets/bonn/{grp}/*.txt') + glob.glob(f'/home/claude/EEG-Epilepsy-Datasets/bonn/{grp}/*.TXT'))[:20]
    for i, fp in enumerate(files):
        if i % 4 == 0: continue
        name = f'EEG_{grp}_{os.path.basename(fp)[:4]}'; x = np.loadtxt(fp)
        rng = np.random.default_rng(zlib.crc32(name.encode())); surs = [iaaft(x, rng) for _ in range(NS)]; sur = [pipeline(y) for y in surs]
        e_s = np.array([s['C1'] - s['rho'] for s in sur]); a_s = np.array([s['a_plus'] for s in sur]); b_s = np.array([s['born_rho'] for s in sur]); tr_s = np.array([TR(y) for y in surs])
        repro.append(abs(float(np.percentile(e_s, 95)) - prev[name]['e_p95']))
        # ложные срабатывания под нулём: каждый суррогат против P95 остальных 19
        for j in range(NS):
            oth = np.delete(np.arange(NS), j)
            fp_e.append(bool(e_s[j] > np.percentile(e_s[oth], 95))); fp_a.append(bool(a_s[j] > np.percentile(a_s[oth], 95)))
            fp_tr.append(bool(abs(tr_s[j]) > np.percentile(np.abs(tr_s[oth]), 95))); fp_born_e.append(bool(b_s[j] and e_s[j] > np.percentile(e_s[oth], 95)))
        arr[name] = dict(group=grp[0], e_sur=e_s.tolist(), a_sur=a_s.tolist(), born_sur=b_s.tolist(), tr_sur=tr_s.tolist(), rho_sur=[s['rho'] for s in sur])
        print(f'{name} [{time.time()-t0:.0f}s] repro Δe_p95={repro[-1]:.2e}', flush=True)
R = dict(fp_rate_e=float(np.mean(fp_e)), fp_rate_a=float(np.mean(fp_a)), fp_rate_tr=float(np.mean(fp_tr)), fp_rate_born_e=float(np.mean(fp_born_e)), n_tests=len(fp_e),
         repro_max_dev=float(max(repro)), note='ложные срабатывания под нулём (суррогат против P95 остальных 19); ожидание ≈ 1/20 = 0.05 при обменяемости')
# по группам: наблюдённые доли против калиброванной ложной
obs = {g: dict(e_above=int(sum(prev[n]['e_above'] for n in prev if prev[n]['group'] == g)), a_above=int(sum(prev[n]['a_above'] for n in prev if prev[n]['group'] == g)),
               born_above=int(sum(prev[n]['born_above'] for n in prev if prev[n]['group'] == g)), TR_sig=int(sum(prev[n]['TR_sig'] for n in prev if prev[n]['group'] == g))) for g in 'ABCDE'}
from scipy.stats import binom
R['groups'] = {g: dict(obs[g], p_e=float(binom.sf(obs[g]['e_above'] - 1, 15, R['fp_rate_e'])), p_a=float(binom.sf(obs[g]['a_above'] - 1, 15, R['fp_rate_a'])),
                       p_born=float(binom.sf(obs[g]['born_above'] - 1, 15, R['fp_rate_born_e'])), p_tr=float(binom.sf(obs[g]['TR_sig'] - 1, 15, R['fp_rate_tr']))) for g in 'ABCDE'}
R['all75'] = dict(e_above=sum(o['e_above'] for o in obs.values()), p_e=float(binom.sf(sum(o['e_above'] for o in obs.values()) - 1, 75, R['fp_rate_e'])),
                  born_above=sum(o['born_above'] for o in obs.values()), p_born=float(binom.sf(sum(o['born_above'] for o in obs.values()) - 1, 75, R['fp_rate_born_e'])))
json.dump(dict(calib=R, surrogates=arr), open(OUT, 'w'), ensure_ascii=False)
print(json.dumps(R, ensure_ascii=False, indent=1)); print('ГОТОВО', f'{time.time()-t0:.0f}s')
