"""SPEC-01 часть B — байесовский тест выброса верхнего лог-зазора на данных: LJ13 (1M шагов, k=100, τ=2), дипептид (k=100, τ=2),
сон (k=30, τ=1); плюс второй нуль — случайные обратимые цепи. По PREREG (2026-09-04)."""
import numpy as np, scipy.io as sio, glob, os, json, sys, time, warnings
warnings.filterwarnings('ignore')
sys.path.insert(0, '/home/claude')
from mol_levels_lib import microstates
from deeptime.markov import TransitionCountEstimator
from deeptime.markov.msm import BayesianMSM, MaximumLikelihoodMSM
t0 = time.time(); OUT = '/home/claude/spec01_data.json'; res = json.load(open(OUT)) if os.path.exists(OUT) else {}
NS = 200; KTS = 14

def spacing_stats(ts, tau):
    r = ts[ts > tau]
    if len(r) < 4: return None   # < 3 зазоров
    s = np.log(r[:-1] / r[1:]); k = np.arange(1, len(s) + 1); z = k * s
    return dict(z=z, p1=float(np.exp(-z[0] / z[1:].mean())), m=len(s), z1_rest=float(z[0] / z[1:].mean()))

def bayes_test(lab, tau, k, name):
    c = TransitionCountEstimator(lagtime=tau, count_mode='effective').fit_fetch(lab.astype(int)).submodel_largest()
    msm = MaximumLikelihoodMSM(reversible=True).fit(c).fetch_model()
    post = BayesianMSM(n_samples=NS, reversible=True).fit(msm).fetch_model()
    ml = spacing_stats(np.sort(msm.timescales(KTS))[::-1], tau)
    ps = []; zr = []; ms = []
    for mm in post.samples:
        st = spacing_stats(np.sort(mm.timescales(KTS))[::-1], tau)
        if st is None: ms.append(0); continue
        ps.append(st['p1']); zr.append(st['z1_rest']); ms.append(st['m'])
    unresolved = np.mean(np.array(ms) < 3) > 0.5
    PL = float(np.mean(np.array(ps) <= 0.05)) if ps else 0.0
    dec = 'отказ:не разрешён' if unresolved else ('уровень' if PL >= 0.95 else ('нет' if PL <= 0.05 else 'отказ'))
    its_ml = [float(x) for x in np.sort(msm.timescales(KTS))[::-1][:8]]
    r = dict(n_states=int(c.n_states), tau=tau, its_ml=its_ml, m_ml=(ml['m'] if ml else 0), z_ml=([float(x) for x in ml['z'][:6]] if ml else None),
             p1_ml=(ml['p1'] if ml else None), PL=PL, z1_rest_median=(float(np.median(zr)) if zr else None), m_median=float(np.median(ms)), dec=dec)
    res[name] = r; json.dump(res, open(OUT, 'w'), indent=1, default=float)
    print(f"{name:16s} сост {r['n_states']:3d} ITS {np.round(its_ml[:6], 1)} | зазоров(ML) {r['m_ml']} z(ML) {None if not r['z_ml'] else np.round(r['z_ml'][:5], 2)} p1(ML) {None if r['p1_ml'] is None else round(r['p1_ml'], 3)} "
          f"| P_L {PL:.2f} z1/rest мед {r['z1_rest_median']} → {dec} [{time.time()-t0:.0f}s]", flush=True)

# ---- второй нуль: случайные обратимые цепи (гамма-счётчики) ----
if 'random_null' not in res:
    rng = np.random.default_rng(7); pvals = []; zr = []; cvs = []
    for i in range(200):
        C = rng.gamma(1.0, 1.0, (30, 30)); C = C + C.T; P = C / C.sum(1, keepdims=True)
        w = np.sort(np.real(np.linalg.eigvals(P)))[::-1]; w = np.clip(w[1:KTS + 1], 1e-9, 0.999999); ts = -1.0 / np.log(w)
        st = spacing_stats(ts, 0.0)
        if st: pvals.append(st['p1']); zr.append(st['z1_rest']); cvs.append(st['z'].std() / st['z'].mean())
    res['random_null'] = dict(rate_top=float(np.mean(np.array(pvals) <= 0.05)), z1_rest_median=float(np.median(zr)), cv_median=float(np.median(cvs)))
    print('случайные обратимые цепи:', res['random_null'], flush=True); json.dump(res, open(OUT, 'w'), indent=1, default=float)

# ---- сон ----
for psg_p in sorted(glob.glob('/home/claude/combsleepnet/example_data/psg/*.mat')):
    nm = 'SLEEP_' + os.path.basename(psg_p).split('-')[0]
    if nm in res: continue
    psg = sio.loadmat(psg_p)['psg']; F = np.log10(np.mean(psg.astype(np.float64) ** 2, axis=2) + 1e-20)
    bayes_test(microstates(F, 30, seed=0), 1, 30, nm)
# ---- дипептид ----
for f in sorted(glob.glob('/home/claude/mol_ala2_m5_T*_s*.npz')):
    nm = f'DIP_{os.path.basename(f)[13:-4]}'
    if nm in res: continue
    d = np.load(f); sc = d['scal']; phi, psi = sc[:, 0], sc[:, 1]; F = np.column_stack([np.cos(phi), np.sin(phi), np.cos(psi), np.sin(psi)])
    bayes_test(microstates(F, 100, seed=0), 2, 100, nm)
# ---- LJ13 (1M шагов) ----
from lj13 import simulate
for T in (0.18, 0.22, 0.25, 0.28, 0.36):
    for s in (301, 302, 303):
        nm = f'LJ_{T}_{s}'
        if nm in res: continue
        r = simulate(T, s, 1000000, rec_every=50); F = np.sort(r['D'][400:], axis=1)
        np.save(f'/home/claude/lj_labels_{T}_{s}_k100.npy', microstates(F, 100, seed=0))
        bayes_test(np.load(f'/home/claude/lj_labels_{T}_{s}_k100.npy'), 2, 100, nm)

# ---- вердикты части B ----
D = lambda n: res[n]['dec']
dip_hi = [n for n in res if n.startswith('DIP') and not n.startswith('DIP_T300')]; dip_lo = [n for n in res if n.startswith('DIP_T300')]
s4 = sum(1 for n in dip_hi if D(n) == 'уровень') == len(dip_hi) and all(D(n) != 'уровень' for n in dip_lo)
k2a = sum(1 for n in dip_hi if D(n) != 'уровень') >= 2
lj = lambda T: [f'LJ_{T}_{s}' for s in (301, 302, 303)]; edge = lj(0.25) + lj(0.28)
zr = [res[n]['z1_rest_median'] for n in edge if res[n]['z1_rest_median'] is not None]
s5 = (sum(1 for n in edge if D(n) == 'уровень') <= 2 and (0.6 <= float(np.median(zr)) <= 1.6 if zr else False)
      and all(D(n) in ('уровень', 'отказ', 'отказ:не разрешён') for n in lj(0.22)) and all(D(n) in ('нет', 'отказ', 'отказ:не разрешён') for n in lj(0.36))
      and all(D(n) == 'отказ:не разрешён' for n in lj(0.18)))
k4 = sum(1 for n in edge if D(n) == 'уровень') >= 5
sl = [n for n in res if n.startswith('SLEEP')]; s6 = sum(1 for n in sl if D(n) != 'уровень') >= 5; k2b = sum(1 for n in sl if D(n) == 'уровень') >= 3
res['verdicts'] = dict(PS4=dict(ok=s4, dec={n: D(n) for n in dip_hi + dip_lo}), PS5=dict(ok=s5, K4=k4, dec={n: (D(n), res[n]['z1_rest_median']) for n in lj(0.18) + lj(0.22) + edge + lj(0.36)}),
                       PS6=dict(ok=s6, dec={n: D(n) for n in sl}), K2=(k2a or k2b))
json.dump(res, open(OUT, 'w'), indent=1, default=float)
print('\n== ВЕРДИКТЫ B ==')
for k, v in res['verdicts'].items(): print(k, v)
