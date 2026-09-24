"""SORT-01 — пилот (калибровка) на L = 32, 64 (тест: 128, 256) для точного лифтированного пути; и lifted_local при L = 32 по s (тест: 64, 128)."""
import numpy as np, json, time
from sort01_lib import analyze, lifted_local
from lift01c_lib import lifted_path
t0 = time.time(); out = dict(A={}, B={})
for L in (32, 64):
    k = np.pi / L; sn = np.sin(k); cEP = L * sn / (1 + sn); rows = []
    for c in np.round(np.arange(2.0, 4.001, 0.1), 3):
        r = analyze(lifted_path(L, float(c / L)), L); r['c'] = float(c); rows.append(r)
        print(f"L={L} c={c:4.2f}: ρ={r['rho']:.5f} θ₊={r['theta']:.4f} real={r['real_lead']} t_ρ={r['t_rho']:.1f} n_max={r['n_max']} | рожд={r['born']} жизнь={r['n_life']} perm={r['permanent']} полупериод={r['half_period'] and round(r['half_period'],1)} возвр={r['returns']} q_end={r['q_end']:.3f} | d2={r['d2']:+.1e} n*={r['nstar']} τ_L02={r['tau_life02'] and round(r['tau_life02'],2)} | a₊={r['a1']:.3f} поздн.рожд n_b={r['late_birth_n']} [{time.time()-t0:.0f}s]", flush=True)
    out['A'][L] = dict(c_EP=cEP, rows=[{kk: v for kk, v in r.items() if kk != 'q_head'} for r in rows])
# (B) lifted_local по s при L = 32
L = 32; out['B'][L] = {}
for s in (0.0, 0.05, 0.1, 0.15, 0.2, 0.25, 0.3, 0.4):
    rows = []
    for c in np.round(np.arange(1.0, 4.001, 0.1), 3):
        r = analyze(lifted_local(L, float(c / L), s), L); r['c'] = float(c); rows.append(r)
    births = [r['c'] for r in rows if r['born']]; eps = [r['c'] for r in rows if not r['real_lead']]
    gap_desc = -np.log(rows[0]['C1']); best = max(rows, key=lambda r: -np.log(r['rho']))
    print(f"s={s}: окно рождений mid [{min(births) if births else None}, {max(births) if births else None}]; комплексна до c={max(eps) if eps else None}; max щель лифтинга {-np.log(best['rho']):.5f} при c={best['c']} против щели описания {gap_desc:.5f} (C1={rows[0]['C1']:.5f}); perm при c≥c_EP: {[r['c'] for r in rows if r['permanent']][:6]} [{time.time()-t0:.0f}s]", flush=True)
    out['B'][L][s] = dict(c_lo=(min(births) if births else None), c_up=(max(births) if births else None), c_last_complex=(max(eps) if eps else None), gap_desc=float(gap_desc), gap_max=float(-np.log(best['rho'])), c_gapmax=best['c'],
                          rows=[{kk: v for kk, v in r.items() if kk != 'q_head'} for r in rows])
json.dump(out, open('/home/claude/sort01_pilot.json', 'w'), default=float); print('ГОТОВО', f'{time.time()-t0:.0f}s')
