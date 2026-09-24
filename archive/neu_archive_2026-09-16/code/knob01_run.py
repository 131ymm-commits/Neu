"""KNOB-01 — ненормальность как ручка: P_θ = P₀ + θ·D⁻¹K (антисимметричный ток без дивергенции); δ(θ), рождения на 2-разбиениях, инвариантность лумпированных λ₂;
AUC(δ) против AUC(σ) на случайных цепях COG-01. По PREREG 2026-09-09."""
import numpy as np, json, sys, time, warnings
warnings.filterwarnings('ignore'); sys.path.insert(0, '/home/claude')
from cog01_lib import *
from scipy.stats import spearmanr, mannwhitneyu
OUT = '/home/claude/knob01_results.json'; t0 = time.time(); rng = np.random.default_rng(777)
def entropy_production(P, pi):
    s = 0.0
    for i in range(len(P)):
        for j in range(len(P)):
            if P[i, j] > 0 and P[j, i] > 0: s += pi[i] * P[i, j] * np.log(P[i, j] / (pi[j] * P[j, i]))
    return float(s)
N = 6; parts = all_bipartitions(N); fam = []; viol = dict(stat=0, lump=0, theta0=0)
for it in range(200):
    P0 = random_reversible(N, rng); pi = stationary(P0); Fl = pi[:, None] * P0; K = np.zeros((N, N))
    for _c in range(3):
        m = int(rng.integers(3, N + 1)); cyc = rng.permutation(N)[:m]; amp = min(Fl[cyc[i], cyc[(i + 1) % m]] for i in range(m))
        for i in range(m): a, b = cyc[i], cyc[(i + 1) % m]; K[a, b] += amp; K[b, a] -= amp
    G = K / pi[:, None]
    # θ_max: все элементы P0 + θG ≥ 0
    neg = G < 0; th_max = float(np.min(-P0[neg] / G[neg])) if neg.any() else 1.0; th_max *= 0.999
    thetas = np.linspace(0, th_max, 11); rows = []
    l2_0 = None
    for th in thetas:
        P = P0 + th * G
        if np.any(P < -1e-12): viol['stat'] += 1
        if np.linalg.norm(pi @ P - pi) > 1e-10: viol['stat'] += 1
        A0 = restrict(sym_form(P, pi), pi); rho = spectral_radius(A0); w = numerical_radius(A0)
        l2 = np.array([lambda2(lump(P, pi, b)[0]) for b in parts]); births = int(np.sum(l2 > rho + 1e-9))
        if l2_0 is None: l2_0 = l2
        if np.max(np.abs(l2 - l2_0)) > 1e-10: viol['lump'] += 1
        if th == 0 and births > 0: viol['theta0'] += 1
        rows.append(dict(theta=float(th), rho=rho, w=w, delta=w - rho, births=births, frac=births / len(parts), sigma=entropy_production(P, pi), l2max=float(l2.max())))
    d = np.array([r['delta'] for r in rows]); fr = np.array([r['frac'] for r in rows]); th = thetas
    sp_d = float(spearmanr(th, d)[0]) if d.std() > 0 else None; sp_f = float(spearmanr(th, fr)[0]) if fr.std() > 0 else None
    # лог-лог наклон δ(θ) по узлам 1..5 (θ > 0)
    ok = (d[1:6] > 1e-14); slope = float(np.polyfit(np.log(th[1:6][ok]), np.log(d[1:6][ok]), 1)[0]) if ok.sum() >= 3 else None
    fam.append(dict(theta_max=th_max, rows=rows, spearman_delta=sp_d, spearman_frac=sp_f, slope=slope, rho_drop=bool(rows[-1]['rho'] < rows[0]['rho']), frac_max=float(fr[-1]), any_birth=bool(fr.max() > 0)))
    if it % 50 == 0: print(f'пара {it}: θ_max {th_max:.3f} δ(θ_max) {d[-1]:.4f} рождений {fr[-1]:.2f} ρ {rows[0]["rho"]:.3f}→{rows[-1]["rho"]:.3f} наклон {slope} [{time.time()-t0:.0f}s]', flush=True)
sp_d = [f['spearman_delta'] for f in fam if f['spearman_delta'] is not None]; sp_f = [f['spearman_frac'] for f in fam if f['spearman_frac'] is not None and f['any_birth']]
slopes = [f['slope'] for f in fam if f['slope'] is not None]
V = dict(viol=viol, n=len(fam), frac_pairs_delta_monotone=float(np.mean([s >= 0.9 for s in sp_d])), slope_median=float(np.median(slopes)), slope_q=[float(np.percentile(slopes, 25)), float(np.percentile(slopes, 75))],
         frac_rho_drop=float(np.mean([f['rho_drop'] for f in fam])), mean_frac_births_thmax=float(np.mean([f['frac_max'] for f in fam])), frac_pairs_any_birth=float(np.mean([f['any_birth'] for f in fam])),
         frac_pairs_births_monotone=(float(np.mean([s >= 0.8 for s in sp_f])) if sp_f else None), n_pairs_with_births=len(sp_f),
         halves=[float(np.mean([f['frac_max'] for f in fam[:100]])), float(np.mean([f['frac_max'] for f in fam[100:]]))])
# средняя кривая δ(θ/θ_max) и рождений
grid = np.linspace(0, 1, 11); V['curve'] = dict(theta_rel=[float(g) for g in grid], delta_median=[float(np.median([f['rows'][i]['delta'] for f in fam])) for i in range(11)], frac_mean=[float(np.mean([f['rows'][i]['frac'] for f in fam])) for i in range(11)], rho_median=[float(np.median([f['rows'][i]['rho'] for f in fam])) for i in range(11)], w_median=[float(np.median([f['rows'][i]['w'] for f in fam])) for i in range(11)], sigma_median=[float(np.median([f['rows'][i]['sigma'] for f in fam])) for i in range(11)])
# AUC(δ) против AUC(σ) на случайных необратимых цепях (как COG-01, сид 2026 — воспроизведение выборки)
rng2 = np.random.default_rng(2026); A = {}
for fam_name, gen in (('rev', random_reversible), ('nonrev', random_chain)):
    for n in (3, 4, 6):
        parts_n = all_bipartitions(n); dd, ss, bb = [], [], []
        for i in range(2000):
            P = gen(n, rng2); pi = stationary(P); A0 = restrict(sym_form(P, pi), pi); rho = spectral_radius(A0); w = numerical_radius(A0)
            if fam_name == 'rev': continue
            born = any(lambda2(lump(P, pi, b)[0]) > rho + 1e-9 for b in parts_n); dd.append(w - rho); ss.append(entropy_production(P, pi)); bb.append(born)
        if fam_name == 'rev': continue
        dd, ss, bb = np.array(dd), np.array(ss), np.array(bb)
        auc = lambda x: float(mannwhitneyu(x[bb], x[~bb]).statistic / (bb.sum() * (~bb).sum()))
        A[f'n{n}'] = dict(auc_delta=auc(dd), auc_sigma=auc(ss), spearman_delta_sigma=float(spearmanr(dd, ss)[0]), frac_born=float(bb.mean()))
        print(f'случайные n={n}: AUC δ {A[f"n{n}"]["auc_delta"]:.3f}  AUC σ {A[f"n{n}"]["auc_sigma"]:.3f}  ρ_S(δ,σ) {A[f"n{n}"]["spearman_delta_sigma"]:.2f} [{time.time()-t0:.0f}s]', flush=True)
V['auc'] = A
V['PK1'] = dict(ok=bool(V['frac_pairs_delta_monotone'] >= 0.8 and 1.5 <= V['slope_median'] <= 2.5)); V['PK2'] = dict(ok=bool((V['frac_pairs_births_monotone'] or 0) >= 0.7 and V['mean_frac_births_thmax'] >= 0.1)); V['PK2p'] = dict(ok=bool(viol['lump'] == 0))
V['PK3'] = dict(ok=bool(all(A[k]['auc_delta'] >= A[k]['auc_sigma'] + 0.05 for k in ('n3', 'n6'))))
V['K0'] = dict(hit=bool(viol['stat'] > 0 or viol['lump'] > 0 or viol['theta0'] > 0)); V['K1'] = dict(hit=bool(V['mean_frac_births_thmax'] < 0.02)); V['K2'] = dict(hit=bool(any(A[k]['auc_sigma'] >= A[k]['auc_delta'] for k in A))); V['K3'] = dict(hit=bool(V['frac_pairs_delta_monotone'] < 0.5))
V['degenerate_first_run'] = 'K = M − Mᵀ: θ_max ≈ 0.000–0.007, δ(θ_max) ≈ 0.003 — заменено циклическими токами (поправка PREREG)'; json.dump(dict(verdicts=V, families=fam), open(OUT, 'w'), default=float)
print('== ВЕРДИКТЫ KNOB-01 ==', json.dumps({k: v for k, v in V.items() if k != 'curve'}, ensure_ascii=False, default=float)); print('кривая:', json.dumps(V['curve'], default=float))
