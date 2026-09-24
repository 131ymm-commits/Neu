"""ICT-01 — ζ по всем 100 сегментам пяти наборов ЭЭГ Бонна (протокол ZETA-01, точная форма), сдвиг медиан с бутстрепом, суррогаты, сиды, сходимость."""
import numpy as np, json, glob, os, sys, time, warnings
warnings.filterwarnings('ignore'); sys.path.insert(0, '/home/claude')
from zeta01_lib import embed
from mol_levels_lib import microstates
from deeptime.markov import TransitionCountEstimator
from deeptime.markov.msm import BayesianMSM, MaximumLikelihoodMSM
OUT = '/home/claude/ict01_results.json'; res = json.load(open(OUT)) if os.path.exists(OUT) else {}; t0 = time.time(); K = 30; TAU = 2; NS = 200; KTS = 14
def p_rank1(z): m = len(z); g = z[0] / z.sum(); return float((1 - g) ** (m - 1))
def stats(ts, tau):
    r = ts[ts > tau]
    if len(r) < 4: return None
    s = np.log(r[:-1] / r[1:]); k = np.arange(1, len(s) + 1); z = np.maximum(k * s, 1e-12); return dict(m=len(z), zeta=float(z[0] / z[1:].mean()), p=p_rank1(z))
def zeta(x, seed=0):
    F = embed(x, 5, 2); lab = microstates(F, K, seed=seed).astype(int)
    c = TransitionCountEstimator(lagtime=TAU, count_mode='effective').fit_fetch(lab).submodel_largest(); msm = MaximumLikelihoodMSM(reversible=True).fit(c).fetch_model()
    post = BayesianMSM(n_samples=NS, reversible=True).fit(msm).fetch_model()
    S = [stats(np.sort(mm.timescales(KTS))[::-1], TAU) for mm in post.samples]; ms = [s['m'] if s else 0 for s in S]; S = [s for s in S if s]
    unresolved = np.mean(np.array(ms) < 3) > 0.5; PL = float(np.mean([s['p'] <= 0.05 for s in S])) if S else 0.0
    dec = 'отказ:не разрешён' if unresolved else ('уровень' if PL >= 0.95 else ('нет' if PL <= 0.05 else 'отказ'))
    its = np.sort(msm.timescales(KTS))[::-1]
    return dict(zeta=(float(np.median([s['zeta'] for s in S])) if S else None), PL=PL, dec=dec, t1=float(its[0]), t2=float(its[1]), m=float(np.median(ms)))
def surrogate(x, rng):
    X = np.fft.rfft(x); ph = np.exp(1j * rng.uniform(0, 2 * np.pi, len(X))); ph[0] = 1; return np.fft.irfft(np.abs(X) * ph, n=len(x))
for grp in ('A_Z', 'B_O', 'C_N', 'D_F', 'E_S'):
    if grp in res: continue
    files = sorted(glob.glob(f'/home/claude/EEG-Epilepsy-Datasets/bonn/{grp}/*.txt') + glob.glob(f'/home/claude/EEG-Epilepsy-Datasets/bonn/{grp}/*.TXT'))
    out = []
    for i, fp in enumerate(files):
        x = np.loadtxt(fp); r = zeta(x); r['file'] = os.path.basename(fp); out.append(r)
        if i % 25 == 24: print(f'{grp}: {i+1} сегментов, медиана ζ {np.median([o["zeta"] for o in out if o["zeta"] is not None]):.2f} [{time.time()-t0:.0f}s]', flush=True)
    res[grp] = dict(segments=out); json.dump(res, open(OUT, 'w'), indent=1, default=float)
# суррогаты и сиды (E и A, 20 сегментов)
rng = np.random.default_rng(0)
for grp in ('E_S', 'A_Z'):
    if 'surr' in res[grp]: continue
    files = sorted(glob.glob(f'/home/claude/EEG-Epilepsy-Datasets/bonn/{grp}/*.txt') + glob.glob(f'/home/claude/EEG-Epilepsy-Datasets/bonn/{grp}/*.TXT'))[:20]
    res[grp]['surr'] = [zeta(surrogate(np.loadtxt(fp), rng))['zeta'] for fp in files]
    res[grp]['seeds'] = {s: [zeta(np.loadtxt(fp), seed=s)['zeta'] for fp in files] for s in (1, 2)}
    print(f'{grp}: суррогаты медиана ζ {np.nanmedian([v for v in res[grp]["surr"] if v is not None]):.2f}; сиды 1/2 медианы {[round(float(np.nanmedian([v for v in res[grp]["seeds"][s] if v is not None])), 2) for s in (1, 2)]} [{time.time()-t0:.0f}s]', flush=True)
    json.dump(res, open(OUT, 'w'), indent=1, default=float)
# вердикты
def med(grp, key='zeta'): return float(np.median([o[key] for o in res[grp]['segments'] if o[key] is not None]))
Z = {g: np.array([o['zeta'] for o in res[g]['segments'] if o['zeta'] is not None]) for g in res}
AB = np.concatenate([Z['A_Z'], Z['B_O']]); E = Z['E_S']; D = float(np.median(E) - np.median(AB))
boot = [np.median(rng.choice(E, len(E))) - np.median(rng.choice(AB, len(AB))) for _ in range(1000)]; ci = [float(np.quantile(boot, 0.025)), float(np.quantile(boot, 0.975))]
lvl = {g: float(np.mean([o['dec'] == 'уровень' for o in res[g]['segments']])) for g in Z}; meds = {g: float(np.median(Z[g])) for g in Z}; t1 = {g: med(g, 't1') for g in Z}
order = [g for g, _ in sorted(meds.items(), key=lambda kv: kv[1])]; target = ['B_O', 'A_Z', 'C_N', 'D_F', 'E_S']
inv = sum(1 for i in range(5) for j in range(i + 1, 5) if target.index(order[i]) > target.index(order[j]))
surrE = [v for v in res['E_S']['surr'] if v is not None]; dsurr = float(np.median(E[:20]) - np.median(surrE))
half = {g: float(np.median(Z[g][:50])) for g in Z}
V = dict(PI1=dict(ok=bool(D >= 0.3 and ci[0] > 0), delta=D, ci=ci), PI2=dict(ok=bool(all(v <= 0.05 for v in lvl.values())), level_frac=lvl), PI3=dict(ok=bool(inv <= 1), order=order, inversions=inv),
         PI4=dict(ok=bool(t1['E_S'] >= 1.5 * float(np.median([o['t1'] for g in ('A_Z', 'B_O') for o in res[g]['segments']]))), t1=t1),
         K1=dict(hit=bool(abs(D) < 0.15 or ci[0] <= 0)), K2=dict(hit=bool(lvl['E_S'] >= 0.05)), K3=dict(hit=bool(abs(dsurr) < 0.1 and D >= 0.3 and ci[0] > 0), dsurr=dsurr),
         medians=meds, first50=half, seeds_E=[float(np.nanmedian([v for v in res['E_S']['seeds'][s] if v is not None])) for s in ('1', '2')] if '1' in res['E_S']['seeds'] else [float(np.nanmedian([v for v in res['E_S']['seeds'][s] if v is not None])) for s in (1, 2)])
res['verdicts'] = V; json.dump(res, open(OUT, 'w'), indent=1, default=float)
print('\nмедианы ζ:', {g: round(v, 2) for g, v in meds.items()}, '| доля «уровень»:', lvl, '| t1 медианы:', {g: round(v, 1) for g, v in t1.items()})
print('== ВЕРДИКТЫ ==')
for k, v in V.items(): print(k, v)
