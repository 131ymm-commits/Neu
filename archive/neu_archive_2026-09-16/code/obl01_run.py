"""OBL-01 — знак памяти как след рождения: D(n) = C(n) − Ωⁿ для ортогонального 2-блочного огрубления (C(n) = ⟨Pⁿh, h⟩_π), время жизни n*;
косое огрубление — контроль тождества. Семейства: случайные необратимые N = 6 (сид 2026), обратимые (сид 777), лифтированный путь A при p*. По PREREG 2026-09-14."""
import numpy as np, json, sys, time, warnings
warnings.filterwarnings('ignore'); sys.path.insert(0, '/home/claude')
from cog01_lib import stationary, sym_form, restrict, spectral_radius, all_bipartitions, random_chain, random_reversible
from scipy.stats import mannwhitneyu
OUT = '/home/claude/obl01_results.json'; t0 = time.time(); TOL = 1e-9; NMAX = 50

def auc(x, y):
    x = np.asarray(x, float); y = np.asarray(y, bool)
    if len(y) == 0 or y.all() or (~y).all(): return None
    return float(mannwhitneyu(x[y], x[~y]).statistic / (y.sum() * (~y).sum()))

def corr_seq(P, pi, h, nmax=NMAX):
    """C(n) = ⟨Pⁿh, h⟩_π, h центрирован и π-нормирован"""
    C = np.empty(nmax + 1); v = h.copy()
    for n in range(nmax + 1):
        C[n] = float(np.sum(pi * v * h)); v = P @ v
    return C

def part_stats(P, pi, rho, blocks):
    ind = (np.asarray(blocks) == np.asarray(blocks).min()).astype(float); h = ind - pi @ ind; h /= np.sqrt(np.sum(pi * h * h))
    C = corr_seq(P, pi, h); Om = C[1]; D = C - Om ** np.arange(len(C))
    neg = np.where(D[2:] < -1e-12)[0]; nstar = int(neg[0] + 2) if len(neg) else None
    return dict(Om=float(Om), born=bool(Om > rho + TOL), negborn=bool(-Om > rho + TOL), d2=float(D[2] / Om ** 2) if abs(Om) > 1e-12 else None, D2=float(D[2]), nstar=nstar)

def oblique_check(P):
    ev, R = np.linalg.eig(P); evl, Lm = np.linalg.eig(P.T); order = np.argsort(-np.abs(ev)); i = order[1]  # верхняя нетривиальная
    lam = ev[i]; r = R[:, i]; j = np.argmin(np.abs(evl - lam)); l = Lm[:, j]; Om_obl = (l @ P @ r) / (l @ r)
    return float(abs(Om_obl - lam))

res = {}
# случайные необратимые
parts = all_bipartitions(6); rng = np.random.default_rng(2026); rows = []; obl_viol = 0
for c in range(2000):
    P = random_chain(6, rng); pi = stationary(P); rho = spectral_radius(restrict(sym_form(P, pi), pi))
    if c < 200: obl_viol += int(oblique_check(P) > 1e-9)
    for b in parts:
        s = part_stats(P, pi, rho, b); s['chain'] = c; rows.append(s)
d2 = np.array([r['d2'] for r in rows], float); born = np.array([r['born'] for r in rows]); negb = np.array([r['negborn'] for r in rows]); chains = np.array([r['chain'] for r in rows])
ok = ~negb & ~np.isnan(d2)  # исключены отрицательные рождения
frac_neg_born = float(np.mean(d2[ok & born] < 0)); frac_neg_unborn = float(np.mean(d2[ok & ~born] < 0))
A = auc(-d2[ok], born[ok]); h1 = auc(-d2[ok & (chains < 1000)], born[ok & (chains < 1000)]); h2 = auc(-d2[ok & (chains >= 1000)], born[ok & (chains >= 1000)])
ns = [r['nstar'] for r in rows if r['born'] and not r['negborn']]; fin = [n for n in ns if n is not None]
res['random'] = dict(n_parts=int(ok.sum()), n_born=int((ok & born).sum()), frac_d2neg_born=frac_neg_born, frac_d2neg_unborn=frac_neg_unborn, auc=A, halves=[h1, h2],
                     d2_born_median=float(np.median(d2[ok & born])), d2_unborn_median=float(np.median(d2[ok & ~born])), nstar_finite_frac=float(len(fin) / len(ns)), nstar_median=(float(np.median(fin)) if fin else None),
                     nstar_p90=(float(np.percentile(fin, 90)) if fin else None), oblique_viol=int(obl_viol), n_negborn_excluded=int(negb.sum()))
print('случайные', json.dumps(res['random'], ensure_ascii=False), f'[{time.time()-t0:.0f}s]', flush=True)
# обратимые
rng = np.random.default_rng(777); viol = 0; d2r = []
for c in range(200):
    P = random_reversible(6, rng); pi = stationary(P); rho = spectral_radius(restrict(sym_form(P, pi), pi))
    for b in parts:
        s = part_stats(P, pi, rho, b); d2r.append(s['d2']); viol += int(s['D2'] < -1e-12)
res['reversible'] = dict(n_parts=len(d2r), viol_d2neg=int(viol), d2_median=float(np.median(d2r)), d2_min=float(np.min(d2r)))
print('обратимые', json.dumps(res['reversible'], ensure_ascii=False), flush=True)
# лифтированный путь A при p*
def lifted_path(L, p):
    n = 2 * L; P = np.zeros((n, n)); idx = lambda x, s: 2 * (x - 1) + (0 if s == 1 else 1)
    for x in range(1, L + 1):
        for s in (1, -1):
            i = idx(x, s)
            for s2, pr in ((s, 1 - p), (-s, p)):
                x2 = x + s2
                if 1 <= x2 <= L: P[i, idx(x2, s2)] += pr
                else: P[i, idx(x, -s2)] += pr
    return P
LF = {}
for L, p in ((64, 0.05), (128, 0.02), (256, 0.01)):
    P = lifted_path(L, p); pi = stationary(P); rho = spectral_radius(restrict(sym_form(P, pi), pi)); xs = np.repeat(np.arange(1, L + 1), 2)
    mid = part_stats(P, pi, rho, (xs > L // 2).astype(int)); cuts = [part_stats(P, pi, rho, (xs > k).astype(int)) for k in range(1, L)]
    bc = [c_ for c_ in cuts if c_['born']]; LF[f'L{L}'] = dict(p=p, rho=rho, mid=mid, n_cuts_born=len(bc), frac_d2neg_born_cuts=(float(np.mean([c_['d2'] < 0 for c_ in bc])) if bc else None),
                                                     frac_d2neg_all_cuts=float(np.mean([c_['d2'] < 0 for c_ in cuts])), nstar_mid=mid['nstar'])
    print(f"лифт L={L} p={p}: mid Ω {mid['Om']:.5f} ρ {rho:.5f} рожд {mid['born']} d₂ {mid['d2']:.3e} n* {mid['nstar']} | рождающих разрезов {len(bc)}, из них d₂<0: {LF[f'L{L}']['frac_d2neg_born_cuts']} | все разрезы d₂<0: {LF[f'L{L}']['frac_d2neg_all_cuts']:.2f}", flush=True)
res['lifted'] = LF
R = res['random']; V = dict(PO0=dict(rev_viol=res['reversible']['viol_d2neg'], obl_viol=R['oblique_viol'], ok=res['reversible']['viol_d2neg'] == 0 and R['oblique_viol'] == 0),
        PO1=dict(frac=R['frac_d2neg_born'], auc=R['auc'], halves=R['halves'], ok=R['frac_d2neg_born'] >= 0.5 and (R['auc'] or 0) >= 0.7 and all((h or 0) >= 0.65 for h in R['halves'])),
        PO2=dict(signs=[LF[k]['mid']['d2'] for k in LF], ok=sum(LF[k]['mid']['d2'] < 0 for k in LF) == 3), PO3=dict(frac=R['nstar_finite_frac'], ok=R['nstar_finite_frac'] >= 0.9),
        K0=res['reversible']['viol_d2neg'] > 0 or R['oblique_viol'] > 0, K1=(R['auc'] or 0) <= 0.55, K2=sum(LF[k]['mid']['d2'] >= 0 for k in LF) >= 2, K3=R['nstar_finite_frac'] < 0.6)
res['verdict'] = V; json.dump(res, open(OUT, 'w'), default=float); print('ВЕРДИКТ', json.dumps(V, default=float, ensure_ascii=False)); print('ГОТОВО', f'{time.time()-t0:.0f}s')
