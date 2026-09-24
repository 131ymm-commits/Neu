"""REC-01b — синаевский ходок с ПРАВИЛЬНЫМИ наблюдаемыми (после класса B в REC-01/Синай): рекорды по h-долинам (h = 2T, экстремумы
Невё–Питмана), захват = доля времени в долине текущего рекорда, Δ_k между долинными рекордами. Те же ландшафты (сиды 2000+), 10^7 шагов."""
import numpy as np, json, time
from scipy.stats import kstest
OUT = '/home/claude/rec01b_sinai.json'; L = 4096; NLAND = 100; STEPS = 10_000_000; res = {}; t0 = time.time()

def h_valleys(U, h):
    """h-долины (чередующиеся экстремумы с гистерезисом h): максимумы — границы долин; возвращает id долины узла и глубины дна."""
    n = len(U); maxima = []; imin = 0; imax = 0; state = 0
    for j in range(1, n):
        if state == 0:
            if U[j] < U[imin]: imin = j
            if U[j] > U[imax]: imax = j
            if U[imax] - U[imin] >= h:
                if imax > imin: state = 1; imax = j if U[j] > U[imax] else imax
                else: maxima.append(imax); state = -1; imin = j
        elif state == 1:      # после минимума ищем максимум
            if U[j] > U[imax]: imax = j
            elif U[j] < U[imax] - h: maxima.append(imax); state = -1; imin = j
        else:                 # после максимума ищем минимум
            if U[j] < U[imin]: imin = j
            elif U[j] > U[imin] + h: state = 1; imax = j
    bounds = sorted(set([0] + [m for m in maxima if 0 < m < n] + [n])); vid = np.zeros(n, int); bottoms = []
    for k in range(len(bounds) - 1):
        a, b = bounds[k], bounds[k + 1]; vid[a:b] = k; bottoms.append(U[a:b].min())
    return vid, np.array(bottoms)

for th in (0.05, 0.1, 0.15):
    rng = np.random.default_rng(2000 + int(th * 1000))
    U = np.cumsum(rng.standard_normal((NLAND, L)), axis=1); U -= U.min(1, keepdims=True); T = th * np.sqrt(L)
    VID = []; BOT = []
    for i in range(NLAND):
        v, b = h_valleys(U[i], 2 * T); VID.append(v); BOT.append(b)
    nval = np.array([len(b) for b in BOT])
    x = rng.integers(0, L, NLAND); ar = np.arange(NLAND); Ucur = U[ar, x]
    cur_v = np.array([VID[i][x[i]] for i in range(NLAND)]); rec_bot = np.array([BOT[i][cur_v[i]] for i in range(NLAND)]); rec_v = cur_v.copy()
    rec_times = [[0] for _ in range(NLAND)]; in_rec = np.zeros(NLAND); n_cnt = 0
    grid = np.unique(np.logspace(1, 7, 61).astype(int)); n_at = np.zeros((NLAND, len(grid))); gi = 0
    for s in range(1, STEPS + 1):
        step = rng.choice([-1, 1], NLAND); xn = np.clip(x + step, 0, L - 1); Un = U[ar, xn]
        acc = rng.random(NLAND) < np.exp(-np.maximum(Un - Ucur, 0) / T)
        x = np.where(acc, xn, x); Ucur = np.where(acc, Un, Ucur)
        if s % 50 == 0:
            cur_v = np.array([VID[i][x[i]] for i in range(NLAND)]); bot = np.array([BOT[i][cur_v[i]] for i in range(NLAND)])
            new = bot < rec_bot - 1e-9
            for i in np.flatnonzero(new): rec_times[i].append(s)
            rec_bot = np.where(new, bot, rec_bot); rec_v = np.where(new, cur_v, rec_v)
            in_rec += (cur_v == rec_v); n_cnt += 1
        if gi < len(grid) and s >= grid[gi]:
            n_at[:, gi] = [len(r) - 1 for r in rec_times]; gi += 1
    phi_trap = in_rec / n_cnt
    last_dec = np.array([r[-1] >= STEPS / 10 for r in rec_times])
    D = np.concatenate([np.diff(np.log(np.array(r[1:], float)))[1:] for r in rec_times if len(r) > 3])
    mean_n = n_at.mean(0); ok = grid >= 100; a, b = np.polyfit(np.log(grid[ok]), mean_n[ok], 1); pred = a * np.log(grid[ok]) + b
    r2 = float(1 - np.sum((mean_n[ok] - pred) ** 2) / max(1e-12, np.sum((mean_n[ok] - mean_n[ok].mean()) ** 2)))
    ks = float(kstest(D, 'expon', args=(0, D.mean())).pvalue) if len(D) > 10 else None
    # линейно-пуассоновский контроль: те же числа событий, равномерные времена на [50, STEPS]
    Dl = np.concatenate([np.diff(np.log(np.sort(rng.uniform(50, STEPS, len(r) - 1))))[1:] for r in rec_times if len(r) > 3])
    ksl = float(kstest(Dl, 'expon', args=(0, Dl.mean())).pvalue) if len(Dl) > 10 else None
    res[f'th{th}'] = dict(theta=th, T=float(T), n_valleys_median=float(np.median(nval)), phi_trap_median=float(np.median(phi_trap)), phi_trap=[float(v) for v in phi_trap],
                          frac_last_decade=float(last_dec.mean()), n_rec_median=float(np.median([len(r) - 1 for r in rec_times])), alpha=float(a), r2=r2,
                          grid=[int(g) for g in grid], mean_n=[float(v) for v in mean_n], D_mean=float(D.mean()), D_cv=float(D.std() / D.mean()), ks_p=ks, n_D=int(len(D)), ks_linear_control=ksl)
    json.dump(res, open(OUT, 'w'), indent=1)
    print(f"θ={th}: h-долин медиана {np.median(nval):.0f}; φ_trap медиана {np.median(phi_trap):.2f}; рекорд в последней декаде {last_dec.mean():.2f}; рекордов медиана {np.median([len(r)-1 for r in rec_times]):.0f}; "
          f"n(t) ~ {a:.2f} ln t (R² {r2:.3f}); Δ_k: n {len(D)} mean {D.mean():.2f} CV {D.std()/D.mean():.2f} KS p {ks:.3g}; лин.контроль KS p {ksl:.3g} [{time.time()-t0:.0f}s]", flush=True)
