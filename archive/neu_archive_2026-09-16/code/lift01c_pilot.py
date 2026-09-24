"""LIFT-01c — пилот (калибровка кромок) на L = 64 и L = 32 (тестовые L — 128, 256, 512). Тонкая сетка c = pL, шаг 0.05.
Печатает: c_EP (смена вещественности ведущей пары), c_lo/c_up окна рождений mid, R(c = π), max R, отклонение ρ² от 1 − 2p."""
import numpy as np, json, time
from lift01c_lib import analyze, closed_form
t0 = time.time(); out = {}
for L in (32, 64):
    cs = np.round(np.arange(1.5, 4.5001, 0.05), 3); rows = [analyze(L, float(c / L)) for c in cs]
    cf = [closed_form(L, float(c / L)) for c in cs]
    comp = [r['complex_lead'] for r in rows]
    # c_EP: последняя c с комплексной парой и первая с вещественной
    c_last_complex = max([r['c'] for r in rows if r['complex_lead']] or [None]); c_first_real = min([r['c'] for r in rows if not r['complex_lead']] or [None])
    births = [r['c'] for r in rows if r['birth_mid']]
    r_pi = analyze(L, float(np.pi / L)); rmax = max(rows, key=lambda r: (r['R_mid'] or 0))
    dev = max(abs(r['rho2_minus_1m2p']) for r in rows if r['complex_lead'])
    dev_cf = max(abs(r['rho'] - c['rho_cf']) for r, c in zip(rows, cf))
    out[L] = dict(c_last_complex=c_last_complex, c_first_real=c_first_real, c_lo=min(births) if births else None, c_up=max(births) if births else None,
                  R_at_pi=r_pi['R_mid'], complex_at_pi=r_pi['complex_lead'], R_max=rmax['R_mid'], c_at_Rmax=rmax['c'], max_dev_rho2=dev, max_dev_rho_vs_cf=dev_cf,
                  rows=[dict(c=r['c'], rho=r['rho'], im=r['im_lead'], R=r['R_mid'], birth=r['birth_mid'], f=r['f_birth']) for r in rows])
    print(f"L={L}: комплексна до c={c_last_complex}, вещественна с c={c_first_real}; окно рождений mid [{out[L]['c_lo']}, {out[L]['c_up']}]; R(π)={r_pi['R_mid']:.4f} (компл.: {r_pi['complex_lead']}); R_max={rmax['R_mid']:.4f} при c={rmax['c']:.2f}; max|ρ²−(1−2p)|={dev:.2e}; max|ρ−ρ_cf|={dev_cf:.2e} [{time.time()-t0:.0f}s]")
    for r in rows[::4]: print(f"   c={r['c']:.2f} ρ={r['rho']:.6f} Im={r['im_lead']:.2e} R={r['R_mid']:.4f} рожд={r['birth_mid']} доля={r['f_birth']:.2f}")
json.dump(out, open('/home/claude/lift01c_pilot.json', 'w'), default=float)
print('ГОТОВО', f'{time.time()-t0:.0f}s')
