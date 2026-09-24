"""CORE-01p-b — повтор CORE-01p при параметрах эталона (LJ13: 1 000 000 шагов, запись каждые 50, отброс 400 кадров, как MOL-002)
+ отказ по числу committed-вылазок n_exc < 10 + исправленный контроль невырожденности. По PREREG (2026-09-04)."""
import numpy as np, json, os, sys, time
sys.path.insert(0, '/home/claude')
from mol_levels_lib import microstates, committed
from deeptime.markov import TransitionCountEstimator
from deeptime.markov.msm import BayesianMSM, MaximumLikelihoodMSM
from lj13 import simulate
t0 = time.time(); OUT = '/home/claude/core01pb_results.json'
NS = 200; NS_CONV = 50; GSTAR = 3.0; GSUB = 1.3; NEXC = 10
res = json.load(open(OUT)) if os.path.exists(OUT) else {}

def post_its(lab, tau, n_samples, k_ts=4):
    c = TransitionCountEstimator(lagtime=tau, count_mode='effective').fit_fetch(lab.astype(int)).submodel_largest()
    msm = MaximumLikelihoodMSM(reversible=True).fit(c).fetch_model()
    post = BayesianMSM(n_samples=n_samples, reversible=True).fit(msm).fetch_model()
    ts = np.sort(np.array([m.timescales(k_ts) for m in post.samples]), axis=1)[:, ::-1]
    return post, c, ts

def gap_probs(ts, gstar):
    g1 = ts[:, 0] / ts[:, 1]; g2 = ts[:, 1] / ts[:, 2]
    return dict(P1=float(np.mean(g1 >= gstar)), P2=float(np.mean(g2 >= gstar)),
                g1_q=[float(x) for x in np.quantile(g1, [0.05, 0.5, 0.95])], g2_q=[float(x) for x in np.quantile(g2, [0.05, 0.5, 0.95])],
                width1=float(np.quantile(g1, 0.95) - np.quantile(g1, 0.05)))

def n_excursions(post, c, lab, k, persist=5):
    """число committed-вылазок в меньшее из двух PCCA-макросостояний."""
    try: A = post.prior.pcca(2).assignments
    except Exception: return None, None
    ids = c.state_symbols; mo = np.full(k, -1); mo[ids] = A; S = mo[lab]; S = np.where(S < 0, 0, S)
    Sc = committed(S, persist); rare = int(np.argmin(np.bincount(Sc, minlength=2)))
    d = np.diff((Sc == rare).astype(int)); n_exc = int((d == 1).sum()) + int(Sc[0] == rare)
    return n_exc, float((Sc == rare).mean())

def decision(P, n_exc):
    if n_exc is not None and n_exc < NEXC: return 'отказ(n_exc)'
    return 'уровень' if P >= 0.95 else ('нет' if P <= 0.05 else 'отказ')

for T in (0.18, 0.22, 0.25, 0.28, 0.36):
    for s in (301, 302, 303):
        name = f'LJ_{T}_{s}'
        if name in res: print('пропуск', name); continue
        r = simulate(T, s, 1000000, rec_every=50); F = np.sort(r['D'][400:], axis=1); lab = microstates(F, 30, seed=0); tau = 16
        post, c, ts = post_its(lab, tau, NS); gp = gap_probs(ts, GSTAR); gs = gap_probs(ts, GSUB)
        _, _, ts_c = post_its(lab, tau, NS_CONV); gc = gap_probs(ts_c, GSTAR)
        nexc, frac = n_excursions(post, c, lab, 30)
        half = lab[:len(lab) // 2]; ph, ch, th = post_its(half, tau, NS); gh = gap_probs(th, GSTAR); nexc_h, frac_h = n_excursions(ph, ch, half, 30)
        its_ml = [float(x) for x in np.sort(post.prior.timescales(4))[::-1]]
        dec = decision(gp['P1'], nexc); dec_h = decision(gh['P1'], nexc_h)
        nondeg = bool(gh['width1'] > gp['width1'] or (nexc_h is not None and nexc_h < NEXC))
        res[name] = dict(T=T, seed=s, n_frames=int(len(lab)), n_states=int(c.n_states), its_ml=its_ml, P1=gp['P1'], P2=gp['P2'], g1_q=gp['g1_q'], g2_q=gp['g2_q'],
                         width1=gp['width1'], P2_sub13=gs['P2'], conv_P1_50=gc['P1'], n_exc=nexc, frac_rare=frac, dec=dec,
                         half=dict(P1=gh['P1'], width1=gh['width1'], n_exc=nexc_h, dec=dec_h), nondeg=nondeg)
        json.dump(res, open(OUT, 'w'), indent=1, default=float)
        print(f"{name:14s} ITS {np.round(its_ml, 1)} g1 [{gp['g1_q'][0]:.2f},{gp['g1_q'][1]:.2f},{gp['g1_q'][2]:.2f}] P1 {gp['P1']:.2f} n_exc {nexc} (доля {frac:.3f}) → {dec} "
              f"| P(g2≥1.3) {gs['P2']:.2f} P(g2≥3) {gp['P2']:.2f} | половина: ширина {gh['width1']:.2f} vs {gp['width1']:.2f}, n_exc {nexc_h} → {dec_h}; невырожд. {nondeg} | conv50 {gc['P1']:.2f} [{time.time()-t0:.0f}s]", flush=True)

lj = lambda T: [f'LJ_{T}_{s}' for s in (301, 302, 303)]
D = lambda n: res[n]['dec']
e1 = all(D(n) == 'нет' for n in lj(0.18) + lj(0.36)) and all(D(n) in ('уровень', 'отказ(n_exc)') for n in lj(0.22))
k1 = any(D(n) == 'нет' for n in lj(0.22)) or any(D(n) == 'уровень' for n in lj(0.18) + lj(0.36))
edge = lj(0.25) + lj(0.28)
e2 = all(any(D(n).startswith('отказ') for n in lj(T)) for T in (0.25, 0.28)) and not any(D(n) == 'нет' for n in edge)
k4 = all(D(n) == 'уровень' for n in edge)
e3 = sum(1 for n in edge if res[n]['P2_sub13'] >= 0.95) >= 4 and all(res[n]['P2'] <= 0.05 for n in edge)
nd = sum(1 for n in res if isinstance(res[n], dict) and res[n].get('nondeg')); e4 = nd >= 13; k2 = not e4
V = dict(PE1=dict(ok=e1, K1=k1, dec={n: D(n) for n in lj(0.18) + lj(0.22) + lj(0.36)}), PE2=dict(ok=e2, K4=k4, dec={n: (D(n), round(res[n]['P1'], 2)) for n in edge}),
         PE3=dict(ok=e3, vals={n: (res[n]['P2'], res[n]['P2_sub13']) for n in edge}), PE4=dict(ok=e4, K2=k2, n=nd))
res['verdicts'] = V; json.dump(res, open(OUT, 'w'), indent=1, default=float)
print('\n== ВЕРДИКТЫ ==')
for k, v in V.items(): print(k, 'ПОДТВЕРЖДЁН' if v['ok'] else 'не подтверждён', {a: b for a, b in v.items() if a != 'ok'})
