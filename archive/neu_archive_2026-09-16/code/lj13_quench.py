"""REC-01 — закалка LJ13 из жидкости с периодическими квенчами в собственные структуры (L-BFGS) и учётом рекордов."""
import numpy as np, time
from scipy.optimize import minimize
from lj13 import energy_forces, icosahedron, N

def inherent(x):
    f = lambda v: energy_forces(v.reshape(N, 3))[0]
    g = lambda v: -energy_forces(v.reshape(N, 3))[1].ravel()
    r = minimize(f, x.ravel(), jac=g, method='L-BFGS-B', options=dict(maxiter=500, gtol=1e-6))
    return float(r.fun), r.x.reshape(N, 3)

def langevin(x, v, T, steps, rng, dt=0.005, gamma=2.0):
    c1 = np.exp(-gamma * dt); c2 = np.sqrt((1 - c1 ** 2) * T); E, F = energy_forces(x)
    for _ in range(steps):
        v += 0.5 * dt * F; x += 0.5 * dt * v
        v = c1 * v + c2 * rng.normal(size=(N, 3)); x += 0.5 * dt * v
        E, F = energy_forces(x); v += 0.5 * dt * F
    return x, v, E

def quench_run(seed, T_hot=0.36, T_q=0.20, equil=100000, steps=1000000, every=250, tol=1e-3, E_gs=None):
    """Возвращает рекорды (время в шагах после закалки, энергия IS), долю захвата, k до основного состояния."""
    rng = np.random.default_rng(seed); x = icosahedron().copy(); v = rng.normal(0, np.sqrt(T_hot), (N, 3)); v -= v.mean(0)
    x, v, _ = langevin(x, v, T_hot, equil, rng)          # расплав
    v *= np.sqrt(T_q / T_hot)                              # закалка скоростей
    nq = steps // every; Eis = np.empty(nq); t0 = time.time()
    for k in range(nq):
        x, v, _ = langevin(x, v, T_q, every, rng); Eis[k], _ = inherent(x)
    # рекорды
    rec_t, rec_E = [], []; cur = np.inf; trap_hits = 0; trap_tot = 0
    for k in range(nq):
        if Eis[k] < cur - tol: cur = Eis[k]; rec_t.append((k + 1) * every); rec_E.append(cur)
        else:
            trap_tot += 1; trap_hits += int(abs(Eis[k] - cur) <= tol)
    phi_trap = trap_hits / max(1, trap_tot)
    k_gs = None; t_gs = None
    if E_gs is not None:
        for i, e in enumerate(rec_E):
            if abs(e - E_gs) <= tol: k_gs = i; t_gs = rec_t[i]; break
    return dict(rec_t=rec_t, rec_E=rec_E, phi_trap=phi_trap, k_gs=k_gs, t_gs=t_gs, n_rec=len(rec_t), Eis_final=float(Eis[-1]),
                frac_gs=float(np.mean(np.abs(Eis - (E_gs if E_gs is not None else 0)) <= tol)), secs=time.time() - t0, Eis=Eis)
