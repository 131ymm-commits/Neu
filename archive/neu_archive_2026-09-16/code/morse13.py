"""SUB-01 часть B — 13-атомные кластеры Морзе: V = Σ e^{ρ(1−r)}(e^{ρ(1−r)} − 2) (ε = r0 = 1), дальность ρ как «сорт вещества».
BAOAB-Ланжевен как в lj13.py, мягкий сферический конфайнмент, квенчи L-BFGS, базин-хоппинг для E_gs."""
import numpy as np
from scipy.optimize import minimize
N = 13; IU = np.triu_indices(N, 1)

def energy_forces(x, rho, rc=2.6, kc=10.0):
    d = x[:, None, :] - x[None, :, :]; r = np.sqrt((d ** 2).sum(-1)); np.fill_diagonal(r, 1.0)
    u = np.exp(rho * (1.0 - r)); np.fill_diagonal(u, 0.0)
    e_pair = u * (u - 2.0); E = 0.5 * e_pair.sum()
    fmag = 2.0 * rho * u * (u - 1.0) / r               # F_i = Σ_j fmag_ij * (x_i − x_j)/r_ij ... уже делим на r
    np.fill_diagonal(fmag, 0.0)
    F = (fmag[:, :, None] * d).sum(1)
    xc = x - x.mean(0); rr = np.linalg.norm(xc, axis=1); over = np.maximum(rr - rc, 0)
    E += 0.5 * kc * (over ** 2).sum(); F -= (kc * over / np.maximum(rr, 1e-12))[:, None] * xc
    return E, F

def icosahedron():
    phi = (1 + 5 ** 0.5) / 2
    v = np.array([[0, 1, phi], [0, -1, phi], [0, 1, -phi], [0, -1, -phi], [1, phi, 0], [-1, phi, 0], [1, -phi, 0], [-1, -phi, 0], [phi, 0, 1], [-phi, 0, 1], [phi, 0, -1], [-phi, 0, -1]], float)
    v /= np.linalg.norm(v[0]); v *= 1.0
    return np.vstack([np.zeros(3), v])

def inherent(x, rho):
    f = lambda v: energy_forces(v.reshape(N, 3), rho)[0]; g = lambda v: -energy_forces(v.reshape(N, 3), rho)[1].ravel()
    r = minimize(f, x.ravel(), jac=g, method='L-BFGS-B', options=dict(maxiter=800, gtol=1e-7)); return float(r.fun), r.x.reshape(N, 3)

def basin_hop(rho, seed=0, hops=60, T=0.5, amp=0.4):
    rng = np.random.default_rng(seed); E, x = inherent(icosahedron(), rho); best = (E, x.copy()); cur = (E, x.copy())
    for _ in range(hops):
        xt = cur[1] + amp * rng.standard_normal((N, 3)); Et, xt = inherent(xt, rho)
        if Et < cur[0] or rng.random() < np.exp(-(Et - cur[0]) / T): cur = (Et, xt)
        if Et < best[0] - 1e-6: best = (Et, xt.copy())
    return best

def langevin(x, v, T, steps, rng, rho, dt=0.005, gamma=2.0, rec_every=0, Tsched=None):
    c1 = np.exp(-gamma * dt); E, F = energy_forces(x, rho); out = []
    for s in range(steps):
        Tt = T if Tsched is None else Tsched(s); c2 = np.sqrt((1 - c1 ** 2) * Tt)
        v += 0.5 * dt * F; x += 0.5 * dt * v; v = c1 * v + c2 * rng.normal(size=(N, 3)); x += 0.5 * dt * v
        E, F = energy_forces(x, rho); v += 0.5 * dt * F
        if rec_every and (s + 1) % rec_every == 0: out.append((Tt, E, np.linalg.norm(x[IU[0]] - x[IU[1]], axis=1).astype(np.float32)))
    return x, v, out
