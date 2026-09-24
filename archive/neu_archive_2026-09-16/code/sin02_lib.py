"""SIN-02 — numba-ходок по синаевскому ландшафту."""
import numpy as np
from numba import njit

@njit(cache=True)
def walk(U, vid, bot, T, steps, seed, grid, maxrec):
    np.random.seed(seed); L = U.shape[0]; x = np.random.randint(0, L); Ucur = U[x]
    cur_v = vid[x]; rec_bot = bot[cur_v]; rec_v = cur_v
    rec_t = np.zeros(maxrec, np.int64); rec_d = np.zeros(maxrec); nrec = 0
    n_at = np.zeros(grid.shape[0], np.int64); gi = 0; in_rec = 0; gmin_t = -1; gmin_v = np.argmin(bot)
    for s in range(1, steps + 1):
        xn = x + (1 if np.random.random() < 0.5 else -1)
        if xn < 0: xn = 0
        if xn >= L: xn = L - 1
        dU = U[xn] - Ucur
        if dU <= 0 or np.random.random() < np.exp(-dU / T): x = xn; Ucur = U[xn]
        cur_v = vid[x]
        if bot[cur_v] < rec_bot - 1e-9:
            rec_bot = bot[cur_v]; rec_v = cur_v
            if nrec < maxrec: rec_t[nrec] = s; rec_d[nrec] = rec_bot; nrec += 1
            if cur_v == gmin_v and gmin_t < 0: gmin_t = s
        if cur_v == rec_v: in_rec += 1
        while gi < grid.shape[0] and s >= grid[gi]: n_at[gi] = nrec; gi += 1
    return rec_t[:nrec], rec_d[:nrec], n_at, in_rec / steps, gmin_t

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

