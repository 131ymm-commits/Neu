"""LJ13 cluster Langevin MD (reduced units, BAOAB), soft spherical confinement; records Epot, pair distances, Q6."""
import numpy as np
N = 13
IU = np.triu_indices(N, 1)

def energy_forces(x, rc=2.6, kc=10.0):
    d = x[:, None, :] - x[None, :, :]
    r2 = (d ** 2).sum(-1); np.fill_diagonal(r2, 1.0)
    inv6 = 1.0 / r2 ** 3; inv12 = inv6 ** 2
    e_pair = 4 * (inv12 - inv6); np.fill_diagonal(e_pair, 0.0)
    E = 0.5 * e_pair.sum()
    fmag = (24 * (2 * inv12 - inv6) / r2); np.fill_diagonal(fmag, 0.0)
    F = (fmag[:, :, None] * d).sum(1)
    # confinement relative to centre of mass
    xc = x - x.mean(0); r = np.linalg.norm(xc, axis=1); over = np.maximum(r - rc, 0)
    E += 0.5 * kc * (over ** 2).sum()
    F -= (kc * over / np.maximum(r, 1e-12))[:, None] * xc
    return E, F

def icosahedron():
    phi = (1 + 5 ** 0.5) / 2
    v = np.array([[0, 1, phi], [0, -1, phi], [0, 1, -phi], [0, -1, -phi], [1, phi, 0], [-1, phi, 0], [1, -phi, 0], [-1, -phi, 0], [phi, 0, 1], [-phi, 0, 1], [phi, 0, -1], [-phi, 0, -1]], float)
    v /= np.linalg.norm(v[0]); v *= 1.09   # ~ LJ equilibrium shell radius
    return np.vstack([np.zeros(3), v])

def q6(x, cut=1.4):
    from scipy.special import sph_harm_y
    d = x[:, None, :] - x[None, :, :]; r = np.linalg.norm(d, axis=-1); np.fill_diagonal(r, 9)
    i, j = np.where((r < cut) & (np.triu(np.ones((N, N)), 1) > 0))
    b = d[i, j]; th = np.arccos(np.clip(b[:, 2] / np.linalg.norm(b, axis=1), -1, 1)); ph = np.arctan2(b[:, 1], b[:, 0])
    q = 0.0
    for m in range(-6, 7):
        y = sph_harm_y(6, m, th, ph).mean(); q += abs(y) ** 2
    return float(np.sqrt(4 * np.pi / 13 * q))

def simulate(T, seed, steps, dt=0.005, gamma=2.0, rec_every=40, x0=None, Tsched=None, want_q6=False):
    rng = np.random.default_rng(seed)
    x = icosahedron().copy() if x0 is None else x0.copy()
    v = rng.normal(0, np.sqrt(T), (N, 3)); v -= v.mean(0)
    E, F = energy_forces(x)
    nrec = steps // rec_every
    Ep = np.empty(nrec); Dp = np.empty((nrec, len(IU[0])), np.float32); Q = np.empty(nrec) if want_q6 else None; Ts = np.empty(nrec)
    c1 = np.exp(-gamma * dt); k = 0
    for s in range(steps):
        Tt = T if Tsched is None else Tsched(s)
        c2 = np.sqrt((1 - c1 ** 2) * Tt)
        v += 0.5 * dt * F; x += 0.5 * dt * v
        v = c1 * v + c2 * rng.normal(size=(N, 3)); x += 0.5 * dt * v
        E, F = energy_forces(x); v += 0.5 * dt * F
        if (s + 1) % rec_every == 0:
            Ep[k] = E; Dp[k] = np.linalg.norm(x[IU[0]] - x[IU[1]], axis=1); Ts[k] = Tt
            if want_q6: Q[k] = q6(x)
            k += 1
    return dict(Ep=Ep, D=Dp, Q=Q, T=Ts, x=x)
