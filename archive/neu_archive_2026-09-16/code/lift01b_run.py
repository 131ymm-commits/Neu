"""LIFT-01b — контроль правила стенки (вариант B_ε: переворот и шаг назад + ленивость ε) и тонкая сетка p = c/L для LIFT-01. По PREREG 2026-09-14.
λ₂ разрезов — через потоки через разрез (точно для 2-блочного лумпинга): λ₂ = 1 − Φ_k (1/π_A + 1/π_B)."""
import numpy as np, json, sys, time, warnings
warnings.filterwarnings('ignore'); sys.path.insert(0, '/home/claude')
from cog01_lib import stationary, sym_form, restrict, spectral_radius
OUT = '/home/claude/lift01b_results.json'; t0 = time.time(); TOL = 1e-9; EPS = 0.05

def lifted_path(L, p, variant):
    n = 2 * L; P = np.zeros((n, n)); idx = lambda x, s: 2 * (x - 1) + (0 if s == 1 else 1); lazy = EPS if variant == 'B' else 0.0
    for x in range(1, L + 1):
        for s in (1, -1):
            i = idx(x, s); P[i, i] += lazy
            for s2, pr in ((s, (1 - p) * (1 - lazy)), (-s, p * (1 - lazy))):
                x2 = x + s2
                if 1 <= x2 <= L: P[i, idx(x2, s2)] += pr
                elif variant == 'A': P[i, idx(x, -s2)] += pr
                else: P[i, idx(x - s2, -s2)] += pr
    return P

def analyze(L, p, variant):
    P = lifted_path(L, p, variant); pi = stationary(P); A0 = restrict(sym_form(P, pi), pi); rho = spectral_radius(A0)
    S = (A0 + A0.T) / 2; omega = float(np.linalg.eigvalsh(S)[-1]); F = pi[:, None] * P
    # кумулятивные потоки: разрез k → A = первые 2k состояний (x ≤ k)
    l2 = np.empty(L - 1)
    for k in range(1, L):
        a = 2 * k; flux = F[:a, a:].sum(); piA = pi[:a].sum(); piB = 1 - piA; l2[k - 1] = 1 - flux * (1 / piA + 1 / piB)
    births = l2 > rho + TOL; mid = float(l2[L // 2 - 1]); R = (float(np.log(rho) / np.log(mid)) if (0 < mid < 1 and 0 < rho < 1) else None)
    return dict(L=L, p=p, variant=variant, rho=rho, omega=omega, l2_mid=mid, R_mid=R, birth_mid=bool(mid > rho + TOL), n_birth=int(births.sum()), f_birth=float(births.mean()),
                viol=int(births.sum() > 0 and omega <= rho + TOL), t_rho=(float(-1 / np.log(rho)) if 0 < rho < 1 else None))

Ls = [32, 64, 128, 256, 512]; cs = [1, 1.25, 1.5, 1.75, 2, 2.25, 2.5, 2.75, 3, 3.5, 4, 5, 6]; rows = []
for L in Ls:
    for variant in ('A', 'B'):
        for p in [0.5] + [c / L for c in cs]:
            r = analyze(L, p, variant); rows.append(r)
            print(f"L={L:3d} {variant} p={p:.5f} (c={p*L:5.2f}) ρ {r['rho']:.6f} ω {r['omega']:.6f} | mid λ₂ {r['l2_mid']:.6f} R {r['R_mid']} рожд {r['birth_mid']} | разрезов {r['n_birth']:3d}/{L-1} | нар {r['viol']} [{time.time()-t0:.0f}s]", flush=True)
json.dump(dict(rows=rows, eps=EPS), open(OUT, 'w'), default=float)
def sel(L, v): return [r for r in rows if r['L'] == L and r['variant'] == v]
def pstar(L, v): return min([r for r in sel(L, v) if r['p'] < 0.5], key=lambda r: r['rho'])
V = dict(births_p05=int(sum(r['n_birth'] for r in rows if r['p'] == 0.5)), viol_total=int(sum(r['viol'] for r in rows)),
         rho_p05_B=[(L, sel(L, 'B')[0]['rho']) for L in Ls], degenerate_B=any(sel(L, 'B')[0]['rho'] > 1 - 1e-6 for L in Ls))
V['PL1b'] = {f'L{L}': dict(p=pstar(L, 'B')['p'], c=pstar(L, 'B')['p'] * L, R=pstar(L, 'B')['R_mid'], f=pstar(L, 'B')['f_birth']) for L in Ls}
V['PL1b']['ok'] = all(pstar(L, 'B')['R_mid'] and pstar(L, 'B')['R_mid'] > 1 for L in (64, 128, 256, 512)) and all(pstar(L, 'B')['R_mid'] and pstar(L, 'B')['R_mid'] >= 1.2 for L in (128, 256, 512))
V['K1b'] = all((r['R_mid'] or 0) <= 1 for L in (64, 128, 256, 512) for r in sel(L, 'B'))
w = [r['p'] for r in sel(256, 'A') if r['birth_mid']]; V['PL2b'] = dict(p_lo=(min(w) if w else None), p_hi=(max(w) if w else None), ratio=((max(w) / min(w)) if w else None), n_points=len(w))
V['PL2b']['ok'] = bool(w) and 1.5 <= V['PL2b']['ratio'] <= 3.5; V['K2b'] = (not w) or V['PL2b']['ratio'] < 1.25 or V['PL2b']['ratio'] > 5
V['PL3b'] = {f'L{L}': dict(p=pstar(L, 'A')['p'], c=pstar(L, 'A')['p'] * L, R=pstar(L, 'A')['R_mid'], f=pstar(L, 'A')['f_birth']) for L in Ls}
r512 = pstar(512, 'A')['R_mid']; V['PL3b']['ok'] = bool(r512 and 1.2 <= r512 <= 1.4); V['K3b'] = bool(r512 is None or r512 < 1.1)
V['PL4b'] = dict(A={L: pstar(L, 'A')['p'] * L for L in Ls}, B={L: pstar(L, 'B')['p'] * L for L in Ls}); V['PL4b']['ok'] = all(2 <= pstar(L, v)['p'] * L <= 3.5 for L in (128, 256, 512) for v in ('A', 'B'))
V['K0'] = V['births_p05'] > 0 or V['viol_total'] > 0
json.dump(dict(rows=rows, eps=EPS, verdict=V), open(OUT, 'w'), default=float); print('ВЕРДИКТ', json.dumps(V, default=float, ensure_ascii=False)); print('ГОТОВО', f'{time.time()-t0:.0f}s')
