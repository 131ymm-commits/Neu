"""FLOCK-01 — стая Вичека (2D, периодический ящик) и равновесный аналог (XY на решётке, метрополисова динамика) с одной наблюдаемой — углом поляризации."""
import numpy as np

def vicsek(N, Lbox, v0, r, eta, steps, rng, burn=1000):
    """Вичек (стандартная угловая шумовая версия): θ_i ← ⟨θ⟩_{соседи в r} + U(−η/2, η/2); возвращает поляризацию P(t) (комплексная: |P| и угол)."""
    pos = rng.uniform(0, Lbox, size=(N, 2)); th = rng.uniform(-np.pi, np.pi, size=N); out = np.empty(steps, dtype=complex)
    for t in range(burn + steps):
        d = pos[:, None, :] - pos[None, :, :]; d -= Lbox * np.round(d / Lbox); nb = (d ** 2).sum(-1) < r * r
        e = np.exp(1j * th); mean = nb @ e; th = np.angle(mean) + rng.uniform(-eta / 2, eta / 2, size=N)
        pos = (pos + v0 * np.column_stack([np.cos(th), np.sin(th)])) % Lbox
        if t >= burn: out[t - burn] = e.mean()
    return out

def xy_metropolis(Lside, T, sweeps, rng, burn=200):
    """XY на квадратной решётке Lside², метрополис с локальными поворотами (обратимая динамика); наблюдаемая — намагниченность (комплексная) после каждого свипа."""
    n = Lside * Lside; th = rng.uniform(-np.pi, np.pi, size=(Lside, Lside)); out = np.empty(sweeps, dtype=complex)
    for s in range(burn + sweeps):
        for _ in range(n):
            i, j = rng.integers(0, Lside, size=2); old = th[i, j]; new = old + rng.uniform(-1.0, 1.0)
            nbsum = np.cos(old - th[(i + 1) % Lside, j]) + np.cos(old - th[i - 1, j]) + np.cos(old - th[i, (j + 1) % Lside]) + np.cos(old - th[i, j - 1])
            nbsum_new = np.cos(new - th[(i + 1) % Lside, j]) + np.cos(new - th[i - 1, j]) + np.cos(new - th[i, (j + 1) % Lside]) + np.cos(new - th[i, j - 1])
            dE = -(nbsum_new - nbsum)
            if dE <= 0 or rng.random() < np.exp(-dE / T): th[i, j] = new
        if s >= burn: out[s - burn] = np.exp(1j * th).mean()
    return out

def angle_states(z, k):
    """дискретизация угла поляризации на k бинов"""
    return ((np.angle(z) + np.pi) / (2 * np.pi) * k).astype(int) % k

def arc_cuts(k):
    """2-блочные разрезы угла: все дуги длины k/2 (полуплоскости направлений) — k/2 различных"""
    cuts = []
    for start in range(k // 2):
        b = np.zeros(k, int); b[[(start + i) % k for i in range(k // 2)]] = 1; cuts.append(b)
    return cuts
