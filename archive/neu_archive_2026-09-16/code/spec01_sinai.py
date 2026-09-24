"""SPEC-01 часть A — точные спектры синаевских ландшафтов: реньевская статистика лог-зазоров, доля выбросов верхнего зазора,
степенной закон N(g*). По PREREG (2026-09-04). Свежие сиды 1000+."""
import numpy as np, json, time
from scipy.linalg import eigh_tridiagonal
t0 = time.time(); OUT = '/home/claude/spec01_sinai.json'
NL = 100; K = 14; THETAS = (0.05, 0.075, 0.1, 0.15); LS = (1024, 4096, 16384)

def sinai_spectrum(L, theta, seed, K=14):
    rng = np.random.default_rng(seed); U = np.cumsum(rng.standard_normal(L)); T = theta * np.sqrt(L)
    wr = 0.5 * np.exp(-(U[1:] - U[:-1]) / (2 * T)); wl = 0.5 * np.exp(-(U[:-1] - U[1:]) / (2 * T))
    diag = np.zeros(L); diag[:-1] -= wr; diag[1:] -= wl; off = np.sqrt(wr * wl)
    ev = eigh_tridiagonal(diag, off, select='i', select_range=(L - K - 1, L - 1), eigvals_only=True)
    lam = np.sort(-ev); return lam

def stats(S):
    """S: (n, 12) лог-зазоры. Возвращает наклон, CV z_k, долю выбросов, N(g*) на сетке."""
    k = np.arange(1, S.shape[1] + 1); Z = S * k; ms = S.mean(0)
    slope = float(np.polyfit(np.log(k), np.log(ms), 1)[0]); cv = Z.std(0) / Z.mean(0)
    p1 = np.exp(-Z[:, 0] / Z[:, 1:].mean(1)); rate = float(np.mean(p1 <= 0.05))
    gs = np.exp(np.linspace(np.log(1.5), np.log(30), 12)); N = np.array([(S >= np.log(g)).sum(1).mean() for g in gs])
    ok = N > 0; a, b = np.polyfit(np.log(gs[ok]), np.log(N[ok]), 1); pred = a * np.log(gs[ok]) + b
    r2 = float(1 - np.sum((np.log(N[ok]) - pred) ** 2) / max(1e-12, np.sum((np.log(N[ok]) - np.log(N[ok]).mean()) ** 2)))
    return dict(slope=slope, cv_mean=float(cv.mean()), cv_k=[float(x) for x in cv], rate_top=rate, mean_s=[float(x) for x in ms],
                z1_over_rest_median=float(np.median(Z[:, 0] / Z[:, 1:].mean(1))), alpha=float(-a), r2=r2, gs=[float(g) for g in gs], N=[float(x) for x in N])

res = {}
for L in LS:
    for th in THETAS:
        S = []; depths = []
        for i in range(NL):
            lam = sinai_spectrum(L, th, 1000 + i, K); ts = 1.0 / lam[1:]; s = np.log(ts[:-1] / ts[1:]); S.append(s[:12])
        S = np.array(S); st = stats(S)
        # чувствительность к K (8 и 16 → берём первые 7 / все 12 доступных: для K=16 пересчитываем)
        st8 = stats(S[:, :7]); st50 = stats(S[:50])
        S16 = []
        for i in range(NL):
            lam = sinai_spectrum(L, th, 1000 + i, 18); ts = 1.0 / lam[1:]; s = np.log(ts[:-1] / ts[1:]); S16.append(s[:16])
        st16 = stats(np.array(S16))
        res[f'L{L}_th{th}'] = dict(L=L, theta=th, **st, K8=dict(slope=st8['slope'], cv=st8['cv_mean'], rate=st8['rate_top']),
                                   K16=dict(slope=st16['slope'], cv=st16['cv_mean'], rate=st16['rate_top']), n50=dict(slope=st50['slope'], cv=st50['cv_mean'], rate=st50['rate_top']))
        json.dump(res, open(OUT, 'w'), indent=1)
        print(f"L={L:5d} θ={th:5.3f}: наклон {st['slope']:+.2f} (K8 {st8['slope']:+.2f}, K16 {st16['slope']:+.2f}) | CV z {st['cv_mean']:.2f} | доля выбросов {st['rate_top']:.2f} | "
              f"z1/rest медиана {st['z1_over_rest_median']:.2f} | α {st['alpha']:.2f} R² {st['r2']:.3f} | ⟨s_k⟩ {np.round(st['mean_s'][:5], 2)} [{time.time()-t0:.0f}s]", flush=True)

# вердикты части A
cells = [v for v in res.values()]
s1 = all(-1.4 <= c['slope'] <= -0.8 and 0.55 <= c['cv_mean'] <= 1.15 for c in cells); k1 = sum(1 for c in cells if not (-1.4 <= c['slope'] <= -0.8 and 0.55 <= c['cv_mean'] <= 1.15)) >= 4
hi = [c for c in cells if c['theta'] >= 0.1]; s2a = all(c['rate_top'] <= 0.10 for c in hi); k3 = any(c['rate_top'] > 0.25 for c in hi)
s2b = all(res[f'L{L}_th0.05']['rate_top'] > res[f'L{L}_th0.15']['rate_top'] for L in LS)
s3a = sum(1 for c in cells if c['r2'] >= 0.95) >= 10; ratios = {L: res[f'L{L}_th0.15']['alpha'] / res[f'L{L}_th0.075']['alpha'] for L in LS}
s3b = all(1.6 <= r <= 2.4 for r in ratios.values())
res['verdicts'] = dict(PS1=dict(ok=s1, K1=k1), PS2=dict(ok=(s2a and s2b), hi_ok=s2a, mono=s2b, K3=k3), PS3=dict(ok=(s3a and s3b), r2_ok=s3a, ratios={str(L): float(r) for L, r in ratios.items()}))
json.dump(res, open(OUT, 'w'), indent=1)
print('\n== ВЕРДИКТЫ A ==', res['verdicts'])
