"""CORE-01p (CORE-01′) — постериорная надёжность спектрального зазора как критерий числа уровней.
Байесовский MSM (deeptime, эффективные счётчики) как варьирующий нуль. По PREREG (2026-09-04).
Замороженные параметры конвейера — как в MOL-002 / CORE-01."""
import numpy as np, scipy.io as sio, glob, os, json, sys, time
sys.path.insert(0, '/home/claude')
from mol_levels_lib import microstates, disc_mi
from deeptime.markov import TransitionCountEstimator
from deeptime.markov.msm import BayesianMSM, MaximumLikelihoodMSM

t0 = time.time(); OUT = '/home/claude/core01p_results.json'
NS = 200; NS_CONV = 50; GSTAR = 3.0; GSUB = 1.3
res = json.load(open(OUT)) if os.path.exists(OUT) else {}

def post_its(lab, tau, n_samples, count_mode='effective', k_ts=4, seed=0):
    c = TransitionCountEstimator(lagtime=tau, count_mode=count_mode).fit_fetch(lab.astype(int)).submodel_largest()
    msm = MaximumLikelihoodMSM(reversible=True).fit(c).fetch_model()
    post = BayesianMSM(n_samples=n_samples, reversible=True).fit(msm, ignore_counting_mode=(count_mode != 'effective')).fetch_model()
    ts = np.array([m.timescales(k_ts) for m in post.samples])
    ts = np.sort(ts, axis=1)[:, ::-1]
    return post, c, ts

def gap_probs(ts, gstar):
    g1 = ts[:, 0] / ts[:, 1]; g2 = ts[:, 1] / ts[:, 2]
    return dict(P1=float(np.mean(g1 >= gstar)), P2=float(np.mean(g2 >= gstar)),
                g1_q=[float(x) for x in np.quantile(g1, [0.05, 0.5, 0.95])], g2_q=[float(x) for x in np.quantile(g2, [0.05, 0.5, 0.95])],
                width1=float(np.quantile(g1, 0.95) - np.quantile(g1, 0.05)))

def decision(P): return 'уровень' if P >= 0.95 else ('нет' if P <= 0.05 else 'отказ')

def closure_kl(P, pi, A, steps=5):
    """KL-замыкание (по мотивам pymergence.inconsistency_sum_over_starts): дельта-старты на микросостояниях, π-взвешенно."""
    nA = A.max() + 1; L = np.zeros((P.shape[0], nA)); L[np.arange(P.shape[0]), A] = 1.0
    M = (np.diag(pi) @ P @ L); M = (L.T @ M) / (L.T @ pi)[:, None]  # π-взвешенное огрубление
    tot = 0.0; Ps = np.eye(P.shape[0]); Ms = np.eye(nA)
    for s in range(1, steps + 1):
        Ps = Ps @ P; Ms = Ms @ M
        q = Ps @ L                      # микро-эволюция → огрубление (строки: старт i)
        m = L @ Ms                      # огрубление старта → макро-эволюция
        nz = q > 1e-12
        kl = np.sum(np.where(nz, q * np.log(np.where(nz, q, 1) / np.maximum(m, 1e-12)), 0.0), axis=1)
        tot += float(pi @ kl)
    return tot

def closure_percentile(post, c, seed=0, nrand=200):
    prior = post.prior; P = prior.transition_matrix; pi = prior.stationary_distribution
    try: A = prior.pcca(2).assignments
    except Exception: return None
    kl0 = closure_kl(P, pi, A); rng = np.random.default_rng(seed); sizes = np.bincount(A, minlength=2)
    null = []
    for _ in range(nrand):
        perm = rng.permutation(len(A)); Ar = np.zeros(len(A), int); Ar[perm[sizes[0]:]] = 1
        null.append(closure_kl(P, pi, Ar))
    null = np.array(null)
    return dict(kl=kl0, null_q05=float(np.quantile(null, 0.05)), null_med=float(np.median(null)), pct=float(np.mean(null <= kl0)), sizes=sizes.tolist())

def psi_both(S, X, tau, nbins=8):
    v = disc_mi(S[:-tau], S[tau:]); mis = []
    for j in range(X.shape[1]):
        q = np.quantile(X[:, j], np.linspace(0, 1, nbins + 1)[1:-1]); xb = np.searchsorted(q, X[:, j]); mis.append(disc_mi(xb[:-tau], S[tau:]))
    return dict(psi_prime=float(v - max(mis)), psi_sum=float(v - sum(mis)), I=float(v))

def analyze(name, F, k, tau, X_for_psi=None):
    if name in res and 'P1' in res[name]: print('пропуск', name); return
    lab = microstates(F, k, seed=0)
    post, c, ts = post_its(lab, tau, NS); gp = gap_probs(ts, GSTAR); gsub = gap_probs(ts, GSUB)
    _, _, ts_c = post_its(lab, tau, NS_CONV); gp_c = gap_probs(ts_c, GSTAR)
    _, _, ts_s = post_its(lab, tau, NS, count_mode='sliding'); gp_s = gap_probs(ts_s, GSTAR)
    half = lab[:len(lab) // 2]; _, _, ts_h = post_its(half, tau, NS); gp_h = gap_probs(ts_h, GSTAR)
    clo = closure_percentile(post, c)
    ps = None
    if X_for_psi is not None:
        try:
            A = post.prior.pcca(2).assignments; ids = c.state_symbols; mo = np.full(k, -1); mo[ids] = A; S = mo[lab]; ok = S >= 0
            ps = psi_both(S[ok], X_for_psi[ok], tau)
        except Exception as e: ps = dict(err=str(e))
    its_ml = [float(x) for x in np.sort(post.prior.timescales(4))[::-1]]
    r = dict(k=k, tau=tau, n_frames=int(len(lab)), n_states=int(c.n_states), eff_counts=float(c.count_matrix.sum()), its_ml=its_ml,
             P1=gp['P1'], P2=gp['P2'], g1_q=gp['g1_q'], g2_q=gp['g2_q'], width1=gp['width1'], dec1=decision(gp['P1']),
             P2_sub13=gsub['P2'], P1_sub13=gsub['P1'],
             conv_P1_50=gp_c['P1'], sliding_P1=gp_s['P1'], sliding_width1=gp_s['width1'],
             half_width1=gp_h['width1'], half_P1=gp_h['P1'], half_dec1=decision(gp_h['P1']), closure=clo, psi=ps)
    res[name] = r; json.dump(res, open(OUT, 'w'), indent=1, default=float)
    print(f"{name:22s} эфф.счётч {r['eff_counts']:7.0f} ITS {np.round(its_ml, 1)} g1 [{gp['g1_q'][0]:.2f},{gp['g1_q'][1]:.2f},{gp['g1_q'][2]:.2f}] "
          f"P1 {gp['P1']:.2f} → {r['dec1']} | P2 {gp['P2']:.2f} P(g2≥1.3) {gsub['P2']:.2f} | половина: ширина {gp_h['width1']:.2f} vs {gp['width1']:.2f} P1 {gp_h['P1']:.2f} "
          f"| sliding P1 {gp_s['P1']:.2f} | conv50 {gp_c['P1']:.2f} | замыкание pct {None if not clo else round(clo['pct'],3)} "
          f"| ψ′ {None if not ps or 'err' in ps else round(ps['psi_prime'],3)} ψ_sum {None if not ps or 'err' in ps else round(ps['psi_sum'],3)} [{time.time()-t0:.0f}s]", flush=True)

# ---- LJ13: сиды 301–303 × T ----
from lj13 import simulate
for T in (0.18, 0.22, 0.25, 0.28, 0.36):
    for s in (301, 302, 303):
        name = f'LJ_{T}_{s}'
        if name in res: print('пропуск', name); continue
        r = simulate(T, s, 500000, rec_every=50); F = np.sort(r['D'][300:], axis=1)
        analyze(name, F, 30, 16, X_for_psi=F)
# ---- дипептид ----
for f in sorted(glob.glob('/home/claude/mol_ala2_m5_T*_s*.npz')):
    T = int(f.split('_T')[1].split('_')[0]); d = np.load(f); sc = d['scal']; phi, psi = sc[:, 0], sc[:, 1]
    F = np.column_stack([np.cos(phi), np.sin(phi), np.cos(psi), np.sin(psi)])
    analyze(f'DIP_{T}_{os.path.basename(f)[-7:-4]}', F, 30, 25, X_for_psi=F)
# ---- сон ----
for psg_p in sorted(glob.glob('/home/claude/combsleepnet/example_data/psg/*.mat')):
    nm = os.path.basename(psg_p).split('-')[0]; psg = sio.loadmat(psg_p)['psg']
    F = np.log10(np.mean(psg.astype(np.float64) ** 2, axis=2) + 1e-20)
    analyze('SLEEP_' + nm, F, 30, 4, X_for_psi=F)

# ---- вердикты по PREREG ----
def P1(n): return res[n]['P1']
lj = lambda T: [f'LJ_{T}_{s}' for s in (301, 302, 303)]
far_no = lj(0.18) + lj(0.36); far_yes = lj(0.22); edge = lj(0.25) + lj(0.28)
d1_ok = all(P1(n) <= 0.05 for n in far_no) and all(P1(n) >= 0.95 for n in far_yes)
k1 = any(P1(n) >= 0.95 for n in far_no) or any(P1(n) <= 0.05 for n in far_yes)
d2_ok = all(any(0.05 < P1(n) < 0.95 for n in lj(T)) for T in (0.25, 0.28)) and not any(P1(n) <= 0.05 for n in edge)
k4 = all(P1(n) >= 0.95 for n in edge)
sl = [n for n in res if n.startswith('SLEEP')]; n_no = sum(1 for n in sl if P1(n) <= 0.05)
d3_ok = n_no >= 5; k3 = n_no <= 2
d4_ok = sum(1 for n in edge if res[n]['P2_sub13'] >= 0.95) >= 4 and all(res[n]['P2'] <= 0.05 for n in edge)
allk = [n for n in res if isinstance(res[n], dict) and 'half_width1' in res[n]]
grow = sum(1 for n in allk if res[n]['half_width1'] > res[n]['width1']); d5_ok = grow >= 24; k2 = not d5_ok
dip = [n for n in res if n.startswith('DIP')]; dip_hi = [n for n in dip if not n.startswith('DIP_300')]; dip_lo = [n for n in dip if n.startswith('DIP_300')]
d6_ok = sum(1 for n in dip_hi if P1(n) >= 0.95) >= 4 and all(P1(n) < 0.95 for n in dip_lo)
V = dict(PD1=dict(ok=d1_ok, K1=k1, vals={n: P1(n) for n in far_no + far_yes}),
         PD2=dict(ok=d2_ok, K4=k4, vals={n: P1(n) for n in edge}),
         PD3=dict(ok=d3_ok, K3=k3, n_no=n_no, vals={n: P1(n) for n in sl}),
         PD4=dict(ok=d4_ok, vals={n: (res[n]['P2'], res[n]['P2_sub13']) for n in edge}),
         PD5=dict(ok=d5_ok, K2=k2, grow=grow, total=len(allk)),
         PD6=dict(ok=d6_ok, vals={n: P1(n) for n in dip}))
res['verdicts'] = V; json.dump(res, open(OUT, 'w'), indent=1, default=float)
print('\n== ВЕРДИКТЫ ==')
for k, v in V.items(): print(k, 'ПОДТВЕРЖДЁН' if v['ok'] else 'не подтверждён', {a: b for a, b in v.items() if a != 'ok'})
