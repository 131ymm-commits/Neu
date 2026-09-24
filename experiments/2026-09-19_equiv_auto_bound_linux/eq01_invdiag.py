# ДИАГНОСТИКА (post hoc): инвариантность ПСУ к замене координат в зависимости от риджа
import sys, numpy as np
sys.argv = ['x', sys.argv[1], 'none']
exec(open('eq01_analyze.py').read().split("# ---------- P5")[0])
p = load(8000)
logp, resid = model_outputs(p, xin)
rr = np.random.default_rng(777 + seed)
Q1, _ = np.linalg.qr(rr.normal(size=(D, D))); Q2, _ = np.linalg.qr(rr.normal(size=(D, D)))
Rm = Q1 @ np.diag(np.logspace(0, -3, D)) @ Q2.T
Xtr, Ytr, Ptr, pos = windows(resid, logp, 16, TR); Xte, Yte, Pte, _ = windows(resid, logp, 16, TE)
Xtr, Xte = pos_center(Xtr, [Xte]); Ytr, Yte = pos_center(Ytr, [Yte])
w = np.linalg.eigvalsh(flat(Xtr).T @ flat(Xtr) / len(flat(Xtr)))
print('число обусловленности Σxx исходное: %.2e' % (w[-1] / w[0]))
for reg in (1e-4, 1e-7, 1e-10, 1e-13, 0.0):
    out = []
    for M_ in (np.eye(D), Rm):
        xtr, xte = flat(Xtr) @ M_.T, flat(Xte) @ M_.T
        s, A, _, _ = cca_fit(xtr, flat(Ytr), reg)
        out.append((r2(xtr @ A[:, :2], flat(Ptr), xte @ A[:, :2], flat(Pte)), s[1]))
    print(f'ридж {reg:g}: R² исходн. {out[0][0]:.4f} после замены {out[1][0]:.4f}  Δ={out[1][0]-out[0][0]:+.4f}  ρ₂ {out[0][1]:.4f}/{out[1][1]:.4f}')
