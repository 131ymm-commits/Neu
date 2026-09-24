# ДИАГНОСТИКА (post hoc): Q6 — инвариантность ПСУ-2 при разном ридже
import sys, numpy as np
sys.argv = ['x', sys.argv[1], 'none']
exec(open('eq01b_analyze.py').read().split("res = {'seed'")[0])
p = load(8000)
logp, r1, r2_ = model_outputs_layers(p, xin)
rr = np.random.default_rng(777 + seed)
Q1_, _ = np.linalg.qr(rr.normal(size=(D, D))); Q2_, _ = np.linalg.qr(rr.normal(size=(D, D)))
Rm = Q1_ @ np.diag(np.logspace(0, -3, D)) @ Q2_.T
for reg in (1e-7, 1e-10, 1e-13):
    a, _ = psu(r2_, logp, 'own2', reg=reg); b, _ = psu(r2_ @ Rm.T, logp, 'own2', reg=reg)
    print(seed, f'ридж {reg:g}: R² {a:.4f} → {b:.4f}, Δ = {b - a:+.4f}')
