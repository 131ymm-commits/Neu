"""REC-01 — синаевский ходок: рекорды посещённой глубины, захват в рекордной долине, n(t) ∝ ln t. 100 ландшафтов × θ ∈ {0.05, 0.1, 0.15}, 10^7 шагов,
векторизовано по ландшафтам. По PREREG (2026-09-05). Сиды 2000+."""
import numpy as np, json, time
OUT = '/home/claude/rec01_sinai.json'; L = 4096; NLAND = 100; STEPS = 10_000_000; res = {}; t0 = time.time()
for th in (0.05, 0.1, 0.15):
    rng = np.random.default_rng(2000 + int(th * 1000))
    U = np.cumsum(rng.standard_normal((NLAND, L)), axis=1); U -= U.min(1, keepdims=True); T = th * np.sqrt(L)
    x = rng.integers(0, L, NLAND); ar = np.arange(NLAND)
    Ucur = U[ar, x]; Urec = Ucur.copy(); rec_times = [[0] for _ in range(NLAND)]; trap = np.zeros(NLAND); trap_n = 0
    # чекпоинты для n(t): логарифмическая сетка
    grid = np.unique(np.logspace(1, 7, 61).astype(int)); n_at = np.zeros((NLAND, len(grid))); gi = 0
    for s in range(1, STEPS + 1):
        step = rng.choice([-1, 1], NLAND); xn = np.clip(x + step, 0, L - 1); Un = U[ar, xn]
        acc = rng.random(NLAND) < np.exp(-np.maximum(Un - Ucur, 0) / T)
        x = np.where(acc, xn, x); Ucur = np.where(acc, Un, Ucur)
        new = Ucur < Urec - 1e-9
        if new.any():
            for i in np.flatnonzero(new): rec_times[i].append(s)
            Urec = np.where(new, Ucur, Urec)
        if s > STEPS // 2:   # захват считаем на второй половине (после стартового переходного)
            trap += (Ucur <= Urec + T); trap_n += 1
        if gi < len(grid) and s == grid[gi]:
            n_at[:, gi] = [len(r) - 1 for r in rec_times]; gi += 1
    phi_trap = trap / trap_n
    last_dec = np.array([r[-1] >= STEPS / 10 for r in rec_times])          # рекорд в последней декаде
    # объединённые Δ_k (k ≥ 2) и подгонка n(t) ~ a + α ln t по средней кривой
    D = np.concatenate([np.diff(np.log(np.array(r[1:], float)))[1:] for r in rec_times if len(r) > 3])
    mean_n = n_at.mean(0); ok = grid >= 100; a, b = np.polyfit(np.log(grid[ok]), mean_n[ok], 1); pred = a * np.log(grid[ok]) + b
    r2 = float(1 - np.sum((mean_n[ok] - pred) ** 2) / max(1e-12, np.sum((mean_n[ok] - mean_n[ok].mean()) ** 2)))
    from scipy.stats import kstest
    ks = kstest(D, 'expon', args=(0, D.mean())).pvalue if len(D) > 10 else None
    res[f'th{th}'] = dict(theta=th, T=float(T), phi_trap_median=float(np.median(phi_trap)), phi_trap=[float(v) for v in phi_trap], frac_last_decade=float(last_dec.mean()),
                          n_rec_median=float(np.median([len(r) - 1 for r in rec_times])), alpha=float(a), r2=r2, grid=[int(g) for g in grid], mean_n=[float(v) for v in mean_n],
                          D_mean=float(D.mean()) if len(D) else None, D_cv=float(D.std() / D.mean()) if len(D) else None, ks_p=(float(ks) if ks is not None else None), n_D=int(len(D)))
    json.dump(res, open(OUT, 'w'), indent=1)
    print(f"θ={th}: φ_trap медиана {np.median(phi_trap):.2f}, рекорд в последней декаде {last_dec.mean():.2f}, рекордов медиана {np.median([len(r)-1 for r in rec_times]):.0f}, "
          f"n(t) ~ {a:.2f} ln t (R² {r2:.3f}), Δ_k: n {len(D)} mean {D.mean():.2f} CV {D.std()/D.mean():.2f} KS p {ks} [{time.time()-t0:.0f}s]", flush=True)
