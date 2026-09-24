"""LIFT-01c — прогон по PREREG (2026-09-14, вечер): L ∈ {128, 256, 512}, сетка c ∈ [1.5, 4.5] шаг 0.05 плюс точка c_EP(L).
Замкнутая форма: p_EP = sin k/(1 + sin k), ρ_EP = √((1 − sin k)/(1 + sin k)), R_EP = ln ρ_EP/ln(1 − 2/L), c_lo = 2 − 2/L,
c_up = L(1 − (1 − λ²)/(2(1 − λ cos k))), λ = 1 − 2/L, k = π/L."""
import numpy as np, json, time
from lift01c_lib import analyze, closed_form
t0 = time.time(); OUT = '/home/claude/lift01c_results.json'; res = {}
def cf_numbers(L):
    k = np.pi / L; s = np.sin(k); pEP = s / (1 + s); rho = np.sqrt((1 - s) / (1 + s)); lam = 1 - 2 / L
    q = (1 - lam ** 2) / (2 * (1 - lam * np.cos(k)))
    return dict(p_EP=float(pEP), c_EP=float(L * pEP), rho_EP=float(rho), R_EP=float(np.log(rho) / np.log(lam)), c_lo=float(2 - 2 / L), c_up=float(L * (1 - q)))
for L in (128, 256, 512):
    cf = cf_numbers(L); cs = np.round(np.arange(1.5, 4.5001, 0.05), 3)
    rows = [analyze(L, float(c / L)) for c in cs]; r_ep = analyze(L, cf['p_EP'])
    dev_cf = max(abs(r['rho'] - closed_form(L, r['p'])['rho_cf']) for r in rows)
    r_lo = analyze(L, (cf['c_EP'] - 0.05) / L); r_hi = analyze(L, (cf['c_EP'] + 0.05) / L)
    births = [r['c'] for r in rows if r['birth_mid']]; rmax = max(rows, key=lambda r: (r['R_mid'] or 0))
    viol = int(sum(1 for r in rows if r['birth_mid'] and r['rho'] >= 1))  # формальный K0 (ω считался в LIFT-01b: рождений при ω ≤ ρ там 0)
    res[L] = dict(cf=cf, dev_rho_vs_cf=dev_cf, complex_at_EP_minus=r_lo['complex_lead'], complex_at_EP_plus=r_hi['complex_lead'],
                  R_at_pEP=r_ep['R_mid'], rho_at_pEP=r_ep['rho'], im_at_pEP=r_ep['im_lead'], c_first_birth=min(births) if births else None,
                  c_last_birth=max(births) if births else None, R_max_grid=rmax['R_mid'], c_at_Rmax=rmax['c'], f_birth_at_EP=r_ep['f_birth'],
                  rows=[dict(c=r['c'], rho=r['rho'], im=r['im_lead'], R=r['R_mid'], birth=r['birth_mid'], f=r['f_birth']) for r in rows])
    print(f"L={L}: dev(ρ, формула)={dev_cf:.1e}; пара при c_EP−0.05 компл.={r_lo['complex_lead']}, при c_EP+0.05 компл.={r_hi['complex_lead']}; "
          f"R(p_EP)={r_ep['R_mid']:.6f} vs R_EP={cf['R_EP']:.6f}; окно [{res[L]['c_first_birth']}, {res[L]['c_last_birth']}] vs [{cf['c_lo']:.4f}, {cf['c_up']:.4f}]; "
          f"R_max(сетка)={rmax['R_mid']:.5f} при c={rmax['c']:.2f}; доля рождающих разрезов в EP {r_ep['f_birth']:.3f} [{time.time()-t0:.0f}s]", flush=True)
V = {}
V['PC1'] = dict(ok=all(res[L]['complex_at_EP_minus'] and not res[L]['complex_at_EP_plus'] for L in res))
V['PC2'] = dict(dev=[abs(res[L]['R_at_pEP'] - res[L]['cf']['R_EP']) for L in res]); V['PC2']['ok'] = all(d < 1e-6 for d in V['PC2']['dev'])
V['PC3'] = dict(lo=[(res[L]['c_first_birth'], res[L]['cf']['c_lo']) for L in res], up=[(res[L]['c_last_birth'], res[L]['cf']['c_up']) for L in res])
V['PC3']['ok'] = all(res[L]['c_first_birth'] is not None and res[L]['cf']['c_lo'] <= res[L]['c_first_birth'] <= res[L]['cf']['c_lo'] + 0.05 + 1e-9
                     and res[L]['cf']['c_up'] - 0.05 - 1e-9 <= res[L]['c_last_birth'] <= res[L]['cf']['c_up'] for L in res)
V['PC4'] = dict(grid_below_EP=[res[L]['R_max_grid'] < res[L]['cf']['R_EP'] for L in res], growth=res[512]['cf']['R_EP'] - res[128]['cf']['R_EP'])
V['PC4']['ok'] = all(V['PC4']['grid_below_EP']) and V['PC4']['growth'] > 0.005
V['K1'] = not V['PC1']['ok']; V['K2'] = any(d > 1e-3 for d in V['PC2']['dev']); V['K3'] = not V['PC3']['ok']
V['K0'] = any(res[L]['dev_rho_vs_cf'] > 1e-6 for L in res)  # контррасчёт: стенка ломает формулу
json.dump(dict(res=res, verdict=V), open(OUT, 'w'), default=float)
print('ВЕРДИКТ', json.dumps(V, default=float, ensure_ascii=False)); print('ГОТОВО', f'{time.time()-t0:.0f}s')
