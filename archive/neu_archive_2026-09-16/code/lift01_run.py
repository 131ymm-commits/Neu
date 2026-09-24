"""LIFT-01 — лифтинг ускоряет моды, но не огрублённые описания: лифтированный путь (x, σ), переворот с вероятностью p; 2-блочные лумпинги по
непрерывным разрезам сайтов и по направлению против ρ лифтированной цепи; ω = λ_max(S), w — числовой радиус. По PREREG 2026-09-14."""
import numpy as np, json, sys, time, warnings
warnings.filterwarnings('ignore'); sys.path.insert(0, '/home/claude')
from cog01_lib import stationary, sym_form, restrict, spectral_radius, numerical_radius, lump
from scipy.stats import spearmanr
OUT = '/home/claude/lift01_results.json'; t0 = time.time(); TOL = 1e-9

def lifted_path(L, p, boundary='A'):
    n = 2 * L; P = np.zeros((n, n)); idx = lambda x, s: 2 * (x - 1) + (0 if s == 1 else 1)
    for x in range(1, L + 1):
        for s in (1, -1):
            i = idx(x, s)
            for s2, pr in ((s, 1 - p), (-s, p)):
                x2 = x + s2
                if 1 <= x2 <= L: P[i, idx(x2, s2)] += pr
                elif boundary == 'A': P[i, idx(x, -s2)] += pr          # стена: переворот и стояние
                else: P[i, idx(x - s2, -s2)] += pr                     # стена: переворот и шаг назад
    return P

def analyze(L, p, boundary):
    P = lifted_path(L, p, boundary); pi = stationary(P); A0 = restrict(sym_form(P, pi), pi)
    rho = spectral_radius(A0); w = numerical_radius(A0, n_angles=(240 if L >= 128 else 720)); S = (A0 + A0.T) / 2; omega = float(np.linalg.eigvalsh(S)[-1])
    xs = np.repeat(np.arange(1, L + 1), 2); ss = np.tile([1, -1], L)
    l2 = []
    for k in range(1, L):
        PY, _ = lump(P, pi, (xs > k).astype(int)); l2.append(float(PY[0, 0] + PY[1, 1] - 1.0))
    l2 = np.array(l2); PYs, _ = lump(P, pi, (ss < 0).astype(int)); l2s = float(PYs[0, 0] + PYs[1, 1] - 1.0)
    births = l2 > rho + TOL; mid = l2[L // 2 - 1]
    R = lambda lam: (float(np.log(rho) / np.log(lam)) if (0 < lam < 1 and 0 < rho < 1) else None)
    u = lambda lam: (float((lam - rho) / (w - rho)) if w - rho > 1e-12 else None)
    return dict(L=L, p=p, boundary=boundary, rho=rho, w=w, omega=omega, delta=w - rho, n_cuts=L - 1, n_birth=int(births.sum()), f_birth=float(births.mean()),
                birth_positions=[int(k + 1) for k in np.where(births)[0]][:12], l2_mid=float(mid), birth_mid=bool(mid > rho + TOL), R_mid=R(mid), u_mid=u(mid),
                l2_max=float(l2.max()), k_max=int(np.argmax(l2) + 1), R_max=R(float(l2.max())), l2_sigma=l2s, birth_sigma=bool(l2s > rho + TOL), R_sigma=R(l2s),
                n_neg=int((l2 < 0).sum()), viol=int(births.sum() > 0 and omega <= rho + TOL), t_rho=float(-1 / np.log(rho)) if 0 < rho < 1 else None)

Ls = [8, 16, 32, 64, 128, 256]; base = [0.5, 0.3, 0.2, 0.1, 0.05, 0.02, 0.01, 0.005, 0.002]; rows = []
for L in Ls:
    ps = sorted(set(base + [1 / L, 2 / L, 4 / L]), reverse=True)
    for boundary in (('A', 'B') if L >= 32 else ('A',)):
        for p in ps:
            if p > 0.5: continue
            r = analyze(L, p, boundary); rows.append(r)
            print(f"L={L:3d} {boundary} p={p:.4f} ρ {r['rho']:.5f} ω {r['omega']:.5f} w {r['w']:.5f} | разрезов рождает {r['n_birth']:3d}/{r['n_cuts']:3d} | mid λ₂ {r['l2_mid']:.5f} R {r['R_mid']} u {r['u_mid']} | σ λ₂ {r['l2_sigma']:.4f} рожд {r['birth_sigma']} R {r['R_sigma']} | max λ₂ {r['l2_max']:.5f} k {r['k_max']} | нар {r['viol']} [{time.time()-t0:.0f}s]", flush=True)
json.dump(dict(rows=rows), open(OUT, 'w'), default=float)

# вердикты
def pstar(L, b):
    rr = [r for r in rows if r['L'] == L and r['boundary'] == b]; return min(rr, key=lambda r: r['rho'])
V = {}
V['PL1_births_p05'] = int(sum(r['n_birth'] + int(r['birth_sigma']) for r in rows if abs(r['p'] - 0.5) < 1e-12)); V['viol_total'] = int(sum(r['viol'] for r in rows))
ok2 = []; ok4 = []; ok5 = []; k1 = True
for L in (32, 64, 128, 256):
    ra = pstar(L, 'A'); rb = pstar(L, 'B'); ok2.append(bool(ra['R_mid'] is not None and ra['R_mid'] >= 1.2)); ok4.append(bool(ra['birth_sigma'])); ok5.append(bool(rb['R_mid'] is not None and rb['R_mid'] >= 1.2))
    if any(r['R_mid'] is not None and r['R_mid'] > 1 for r in rows if r['L'] == L and r['boundary'] == 'A'): k1 = False
    V[f'pstar_A_L{L}'] = dict(p=ra['p'], rho=ra['rho'], t_rho=ra['t_rho'], R_mid=ra['R_mid'], u_mid=ra['u_mid'], f_birth=ra['f_birth'], R_sigma=ra['R_sigma'], birth_sigma=ra['birth_sigma'], omega=ra['omega'], w=ra['w'])
    V[f'pstar_B_L{L}'] = dict(p=rb['p'], rho=rb['rho'], R_mid=rb['R_mid'], f_birth=rb['f_birth'], birth_sigma=rb['birth_sigma'])
r64 = sorted([r for r in rows if r['L'] == 64 and r['boundary'] == 'A'], key=lambda r: -r['p']); pst = pstar(64, 'A')['p']
seg = [r for r in r64 if r['p'] >= pst - 1e-12]; sp = spearmanr([r['f_birth'] for r in seg], [r['p'] for r in seg]).correlation if len(seg) > 2 else None
beyond = [r for r in r64 if r['p'] < pst - 1e-12]; fmax_beyond = max((r['f_birth'] for r in beyond), default=None)
V['PL3'] = dict(spearman_f_p_above_pstar=(None if sp is None or np.isnan(sp) else float(sp)), f_at_pstar=pstar(64, 'A')['f_birth'], f_max_beyond_pstar=fmax_beyond, f_curve=[(r['p'], r['f_birth'], r['R_mid']) for r in r64])
V['PL2'] = dict(ok_count=int(sum(ok2)), ok=sum(ok2) >= 3); V['PL4'] = dict(ok_count=int(sum(ok4)), ok=sum(ok4) >= 3); V['PL5'] = dict(ok_count=int(sum(ok5)), ok=sum(ok5) >= 3)
V['K0'] = bool(V['PL1_births_p05'] > 0 or V['viol_total'] > 0); V['K1'] = bool(k1); V['K2'] = bool(sp is not None and not np.isnan(sp) and sp > -0.5)
V['K3'] = bool(V['PL2']['ok'] and sum(1 for L in (32, 64, 128, 256) if pstar(L, 'B')['R_mid'] is not None and pstar(L, 'B')['R_mid'] <= 1) >= 3)
json.dump(dict(rows=rows, verdict=V), open(OUT, 'w'), default=float); print('ВЕРДИКТ', json.dumps(V, default=float, ensure_ascii=False)); print('ГОТОВО', f'{time.time()-t0:.0f}s')
