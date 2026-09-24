"""EST-02 — множитель обратимости f = t₁(обр)/t₁(необр) против t_w/t_ρ на свежих рядах: 75 сегментов ЭЭГ (i % 4 ≠ 0), 27 телеграфов (L × m × сиды), 5 hier2. По PREREG 2026-09-09."""
import numpy as np, json, os, sys, glob, time, warnings
warnings.filterwarnings('ignore'); sys.path.insert(0, '/home/claude')
from mol_levels_lib import microstates
from deeptime.markov import TransitionCountEstimator
from deeptime.markov.msm import MaximumLikelihoodMSM
from zeta01_lib import embed
from hor02_lib import telegraph, hier_telegraph
from cog01_lib import sym_form, restrict, numerical_radius, spectral_radius
from scipy.stats import spearmanr
B = '/home/claude'; OUT = f'{B}/est02_results.json'; res = json.load(open(OUT)) if os.path.exists(OUT) else {}; t0 = time.time()
def measure(F, tau, k):
    lab = microstates(F, k, seed=0); n = len(lab); out = {}
    for tag, l in (('full', lab), ('half', lab[:n // 2])):
        c = TransitionCountEstimator(lagtime=tau, count_mode='sliding').fit_fetch(l.astype(int)).submodel_largest()
        mr = MaximumLikelihoodMSM(reversible=True).fit(c).fetch_model(); mn = MaximumLikelihoodMSM(reversible=False).fit(c).fetch_model()
        t_r = float(np.sort(np.abs(np.real(mr.timescales(3))))[::-1][0]); t_n = float(np.sort(np.abs(np.real(mn.timescales(3))))[::-1][0])
        P = np.asarray(mn.transition_matrix); pi = np.asarray(mn.stationary_distribution); A0 = restrict(sym_form(P, pi), pi); rho = spectral_radius(A0); w = numerical_radius(A0)
        out[tag] = dict(f=t_r / t_n, twr=(float(np.log(rho) / np.log(w)) if 0 < w < 1 and 0 < rho < 1 else None), rho=rho, w=w, t_rev=t_r, t_nonrev=t_n)
    return out
def run(name, F, tau, k, group):
    if name in res: return
    r = measure(F, tau, k); r['group'] = group; res[name] = r; json.dump(res, open(OUT, 'w'), default=float)
    print(f"{name:24s} [{group}] f {r['full']['f']:.2f}  t_w/t_ρ {r['full']['twr'] if r['full']['twr'] is None else round(r['full']['twr'], 2)}  (половина: f {r['half']['f']:.2f}, {r['half']['twr'] if r['half']['twr'] is None else round(r['half']['twr'], 2)}) [{time.time()-t0:.0f}s]", flush=True)
for grp in ('A_Z', 'B_O', 'C_N', 'D_F', 'E_S'):
    files = sorted(glob.glob(f'{B}/EEG-Epilepsy-Datasets/bonn/{grp}/*.txt') + glob.glob(f'{B}/EEG-Epilepsy-Datasets/bonn/{grp}/*.TXT'))[:20]
    for i, fp in enumerate(files):
        if i % 4 == 0: continue
        run(f'EEG_{grp}_{os.path.basename(fp)[:4]}', embed(np.loadtxt(fp), 5, 2), 2, 30, 'eeg_fresh')
for L in (20, 80, 160):
    for m in (2, 4, 8):
        for s in range(3):
            rng = np.random.default_rng(4000 + 100 * L + 10 * m + s); x, _ = telegraph(8000, L, rng); run(f'tel_L{L}_m{m}_s{s}', embed(x, m), 1, 30, 'tel_fresh')
for s in range(5):
    rng = np.random.default_rng(8000000 + s); x, _ = hier_telegraph(8000, 320, rng, amps=(0.5, 1.0, 2.0)); run(f'hier2_L320_s{s}', embed(x, 4), 1, 30, 'hier2_fresh')
# контроль (a): сырые ряды
from archive_loaders import series
for name, F, tau, k, group in series(('real',)):
    if name.startswith('SLEEP') or name.startswith('NGRIP_2D'): run('raw_' + name, F, tau, k, 'raw_ctrl')
# --- вердикты ---
def pairs(sel):
    return [(v['full']['f'], v['full']['twr']) for k, v in res.items() if k != 'verdicts' and v.get('group') in sel and v['full']['twr']]
allp = pairs(('eeg_fresh', 'tel_fresh', 'hier2_fresh')); f = np.array([p[0] for p in allp]); g = np.array([p[1] for p in allp])
V = dict(n=len(allp), spearman_all=float(spearmanr(f, g)[0]), within15=float(np.mean(np.abs(np.log(f) - np.log(g)) <= np.log(1.5))), median_ratio=float(np.median(f / g)))
for grp_ in ('eeg_fresh', 'tel_fresh', 'hier2_fresh'):
    p = pairs((grp_,)); V[f'spearman_{grp_}'] = (float(spearmanr([a for a, _ in p], [b for _, b in p])[0]) if len(p) >= 4 else None); V[f'n_{grp_}'] = len(p)
hp = [(v['half']['f'], v['half']['twr']) for k, v in res.items() if k != 'verdicts' and v.get('group') in ('eeg_fresh', 'tel_fresh', 'hier2_fresh') and v['half']['twr']]
V['spearman_half'] = float(spearmanr([a for a, _ in hp], [b for _, b in hp])[0]); V['within15_half'] = float(np.mean([abs(np.log(a) - np.log(b)) <= np.log(1.5) for a, b in hp]))
raw = pairs(('raw_ctrl',)); V['raw_ctrl'] = dict(n=len(raw), f_median=float(np.median([a for a, _ in raw])), twr_median=float(np.median([b for _, b in raw])), twr_max=float(max(b for _, b in raw)))
V['PE2a'] = dict(ok=bool(V['spearman_all'] >= 0.7 and (V['spearman_eeg_fresh'] or 0) >= 0.6)); V['PE2b'] = dict(ok=bool(V['within15'] >= 0.7)); V['PE2c'] = dict(ok=bool(0.8 <= V['median_ratio'] <= 1.25))
V['K1'] = dict(hit=bool(V['spearman_all'] <= 0.4)); V['K2'] = dict(hit=bool(V['within15'] < 0.4)); V['K3'] = dict(hit=bool(V['raw_ctrl']['twr_max'] > 1.3))
res['verdicts'] = V; json.dump(res, open(OUT, 'w'), default=float)
print('== ВЕРДИКТЫ EST-02 ==', json.dumps(V, ensure_ascii=False, default=float))
