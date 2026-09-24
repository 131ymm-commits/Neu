"""DUST-01 — NGRIP δ¹⁸O + Ca²⁺ против δ¹⁸O в одиночку: спектральный класс (MSM на микросостояниях, точная форма p_rank1), шумовой контроль,
фазовые суррогаты, сиды, отложенная половина (блоки по 40). По PREREG 2026-09-09."""
import numpy as np, json, sys, time, warnings
warnings.filterwarnings('ignore'); sys.path.insert(0, '/home/claude')
from mol_levels_lib import microstates
from deeptime.markov import TransitionCountEstimator
from deeptime.markov.msm import BayesianMSM, MaximumLikelihoodMSM
OUT = '/home/claude/dust01_results.json'; res = {}; t0 = time.time(); K = 15; TAU = 1; NS = 200; KTS = 14

def load(fn):
    rows = [l.split() for l in open(fn) if l.strip()]; a = np.array([float(r[0]) for r in rows]); d = np.array([float(r[1]) for r in rows]); ca = np.array([float(r[2]) for r in rows])
    o = np.argsort(a); a, d, ca = a[o], d[o], ca[o]; nan = np.isnan(ca); ca[nan] = np.interp(a[nan], a[~nan], ca[~nan]); return a, d, np.log(ca)
def std(x): return (x - x.mean(0)) / x.std(0)
def embed(x, m): n = len(x) - m + 1; return np.column_stack([x[i: i + n] for i in range(m)])
def p_rank1(z): m = len(z); g = z[0] / z.sum(); return float((1 - g) ** (m - 1))
def stats(ts, tau):
    r = ts[ts > tau]
    if len(r) < 4: return None
    s = np.log(r[:-1] / r[1:]); k = np.arange(1, len(s) + 1); z = np.maximum(k * s, 1e-12); return dict(m=len(z), zeta=float(z[0] / z[1:].mean()), p=p_rank1(z))
def test(F, k=K, tau=TAU, seed=0, ns=NS):
    lab = microstates(F, k, seed=seed).astype(int)
    c = TransitionCountEstimator(lagtime=tau, count_mode='effective').fit_fetch(lab).submodel_largest(); msm = MaximumLikelihoodMSM(reversible=True).fit(c).fetch_model()
    post = BayesianMSM(n_samples=ns, reversible=True).fit(msm).fetch_model()
    S = [stats(np.sort(mm.timescales(KTS))[::-1], tau) for mm in post.samples]; ms = [s['m'] if s else 0 for s in S]; S = [s for s in S if s]
    unresolved = np.mean(np.array(ms) < 3) > 0.5; PL = float(np.mean([s['p'] <= 0.05 for s in S])) if S else 0.0
    dec = 'отказ:не разрешён' if unresolved else ('уровень' if PL >= 0.95 else ('нет' if PL <= 0.05 else 'отказ'))
    its = np.sort(msm.timescales(KTS))[::-1]
    return dict(n=int(len(F)), n_states=int(c.n_states), its=[float(x) for x in its[:6]], t1=float(its[0]), zeta=(float(np.median([s['zeta'] for s in S])) if S else None),
                zeta_q=([float(x) for x in np.quantile([s['zeta'] for s in S], [0.05, 0.95])] if S else None), PL=PL, dec=dec, m_median=float(np.median(ms)), lab=lab, msm=msm, c=c)
def heldout(F, k=K, tau=TAU, block=40):
    """обучение на нечётных блоках, тест на чётных: t1 обучения против t1 теста по автокорреляции собственного вектора"""
    lab = microstates(F, k, seed=0).astype(int); n = len(lab); bid = np.arange(n) // block; tr = bid % 2 == 0; te = ~tr
    # обучающая последовательность — конкатенация блоков (переходы на стыках блоков считаются; их ~n/(2·block))
    c = TransitionCountEstimator(lagtime=tau, count_mode='effective').fit_fetch(lab[tr]).submodel_largest(); msm = MaximumLikelihoodMSM(reversible=True).fit(c).fetch_model()
    ts = np.sort(msm.timescales(KTS))[::-1]; ev = msm.eigenvectors_right(3)[:, 1]; sym = c.state_symbols
    f = np.array([ev[np.searchsorted(sym, s)] if s in set(sym) else np.nan for s in lab[te]]); ok = ~np.isnan(f)
    g = f[ok]; a = np.corrcoef(g[:-tau], g[tau:])[0, 1] if g.std() > 0 else 0.0; t_te = (-tau / np.log(a)) if a > 0 else 0.0
    return dict(t1_train=float(ts[0]), t1_test=float(t_te), ratio=(float(t_te / ts[0]) if ts[0] > 0 else None), n_train=int(tr.sum()), n_test=int(te.sum()))
def surrogate(x, rng):
    X = np.fft.rfft(x); ph = np.exp(1j * rng.uniform(0, 2 * np.pi, len(X))); ph[0] = 1; return np.fft.irfft(np.abs(X) * ph, n=len(x))

for win, fn in (('W50', '/home/claude/ngrip2d/ngrip_ca_50yr.txt'), ('W20', '/home/claude/ngrip2d/ngrip_ca_20yr_11.6-23.0ka.txt')):
    a, d, lc = load(fn); n = len(a); r = dict(n=n, age_min=float(a.min()), age_max=float(a.max()))
    F1 = std(d)[:, None]; F1m2 = std(embed(d, 2)); F2 = std(np.column_stack([d, lc]));
    for name, F in (('1D_m1', F1), ('1D_m2', F1m2), ('2D_d18O_lnCa', F2)):
        t = test(F); r[name] = {k: v for k, v in t.items() if k not in ('lab', 'msm', 'c')}
        print(f"{win} {name:14s} n={t['n']} сост {t['n_states']} | ITS {np.round(t['its'][:5], 2)} | ζ {t['zeta']} {None if not t['zeta_q'] else np.round(t['zeta_q'], 2)} P_L {t['PL']:.2f} → {t['dec']} [{time.time()-t0:.0f}s]", flush=True)
    r['seeds'] = {name: [test(F, seed=s)['zeta'] for s in (1, 2, 3)] for name, F in (('1D_m2', F1m2), ('2D_d18O_lnCa', F2))}
    print(f"{win} сиды: {r['seeds']}", flush=True)
    rng = np.random.default_rng(0); noise = []; surr = []
    for s in range(10):
        Fn = std(np.column_stack([d, rng.normal(size=n)])); tn = test(Fn); noise.append(dict(zeta=tn['zeta'], t1=tn['t1'], dec=tn['dec']))
        ds, cs = surrogate(std(d), rng), surrogate(std(lc), rng); t2 = test(std(np.column_stack([ds, cs]))); t1s = test(std(embed(ds, 2)))
        surr.append(dict(zeta2=t2['zeta'], zeta1=t1s['zeta'], dz=(t2['zeta'] - t1s['zeta']) if (t2['zeta'] is not None and t1s['zeta'] is not None) else None))
    r['noise'] = noise; r['surr'] = surr
    z1 = r['1D_m2']['zeta']; z2 = r['2D_d18O_lnCa']['zeta']
    dz_noise = [x['zeta'] - z1 for x in noise if x['zeta'] is not None and z1 is not None]; dz_surr = [x['dz'] for x in surr if x['dz'] is not None]
    r['dzeta'] = (z2 - z1) if (z1 is not None and z2 is not None) else None; r['t1_ratio'] = r['2D_d18O_lnCa']['t1'] / r['1D_m2']['t1']
    r['dz_noise_q'] = [float(np.quantile(dz_noise, q)) for q in (0.1, 0.5, 0.9)] if dz_noise else None; r['dz_surr_median'] = float(np.median(dz_surr)) if dz_surr else None
    r['heldout_2D'] = heldout(F2); r['heldout_1D'] = heldout(F1m2)
    print(f"{win}: Δζ = {r['dzeta']} | t1 2D/1D = {r['t1_ratio']:.2f} | шум Δζ q10/50/90 {r['dz_noise_q']} | суррогаты Δζ медиана {r['dz_surr_median']} | отложенная 2D {r['heldout_2D']} 1D {r['heldout_1D']}", flush=True)
    res[win] = r; json.dump(res, open(OUT, 'w'), indent=1, default=float)
w = res['W50']
V = dict(PDU1=dict(ok=bool(w['dzeta'] is not None and w['dzeta'] >= 0.5 and w['t1_ratio'] >= 1.5), dzeta=w['dzeta'], t1_ratio=w['t1_ratio']),
         PDU2=dict(ok=bool(w['dzeta'] is not None and w['dz_noise_q'] and w['dzeta'] > w['dz_noise_q'][2]), dz_noise_q=w['dz_noise_q']),
         PDU3=dict(ok=bool(w['heldout_2D']['ratio'] is not None and 0.5 <= w['heldout_2D']['ratio'] <= 2), ratio=w['heldout_2D']['ratio']),
         PDU4=dict(ok=bool(w['dz_surr_median'] is not None and abs(w['dz_surr_median']) <= 0.3), dz_surr=w['dz_surr_median']),
         K1=dict(hit=bool(w['dzeta'] is None or w['dzeta'] <= 0)), K2=dict(hit=bool(w['dzeta'] is not None and w['dz_noise_q'] and w['dz_noise_q'][0] <= w['dzeta'] <= w['dz_noise_q'][2])),
         K3=dict(hit=bool(w['2D_d18O_lnCa']['dec'] == 'уровень' and not (0.5 <= (w['heldout_2D']['ratio'] or 0) <= 2))))
res['verdicts'] = V; json.dump(res, open(OUT, 'w'), indent=1, default=float)
print('\n== ВЕРДИКТЫ ==')
for k, v in V.items(): print(k, v)
