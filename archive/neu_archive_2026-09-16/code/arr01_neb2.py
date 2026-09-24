"""ARR-01 — пост-хок: барьеры соседних маршрутов: −41.47 → −41.44 и −41.44 → икосаэдр (NEB, тот же метод)."""
import numpy as np, sys, time
sys.path.insert(0, '/home/claude')
from lj13_quench import langevin, inherent
from lj13 import icosahedron, N, energy_forces
from scipy.optimize import linear_sum_assignment
rng = np.random.default_rng(21); found = {}
x = icosahedron(); v = rng.normal(0, np.sqrt(0.36), (N, 3)); v -= v.mean(0); x, v, _ = langevin(x, v, 0.36, 20000, rng)
for trial in range(600):
    x, v, _ = langevin(x, v, 0.30, 400, rng); E, xi = inherent(x); key = round(E, 2)
    if key not in found: found[key] = xi
    if -41.45 < E < -41.43 and -41.48 < min(found) + 2.86 < -41.46 and len(found) > 8: break
x44 = found[min(found, key=lambda k: abs(k + 41.44))]; E44, x44 = inherent(x44); print('E44', E44, sorted(found)[:6])
x47 = np.load('lj13_x_41_47.npy'); x_gs = np.load('lj13_x_gs.npy'); E47 = inherent(x47)[0]; E_gs = inherent(x_gs)[0]
def kabsch(P, Q):
    P = P - P.mean(0); Q = Q - Q.mean(0); H = P.T @ Q; U, S, Vt = np.linalg.svd(H); d = np.sign(np.linalg.det(Vt.T @ U.T)); D = np.diag([1, 1, d]); R = Vt.T @ D @ U.T; return P @ R.T, Q
def align(A, B):
    A = A - A.mean(0); B = B - B.mean(0); best = None
    for it in range(60):
        Rr = np.linalg.qr(np.random.default_rng(it).normal(size=(3, 3)))[0]; A2 = A @ Rr.T; Bp = B
        for _ in range(6):
            C = ((A2[:, None, :] - B[None, :, :]) ** 2).sum(-1); ri, ci = linear_sum_assignment(C); A2p = A2[ri]; Bp = B[ci]; A2, Bp = kabsch(A2p, Bp)
        rmsd = np.sqrt(((A2 - Bp) ** 2).sum(1).mean())
        if best is None or rmsd < best[0]: best = (rmsd, A2.copy(), Bp.copy())
    return best
def neb(A, B, nimg=20, k_spr=2.0, iters=8000):
    P = np.array([A + (B - A) * i / (nimg - 1) for i in range(nimg)]); V = np.zeros_like(P); dt = 0.02
    def forces_all(P):
        Es, Fs = zip(*[energy_forces(p) for p in P]); return np.array(Es), np.array(Fs)
    def G_of(P, climb):
        Es, Fs = forces_all(P); G = np.zeros_like(P)
        for i in range(1, nimg - 1):
            tp = P[i + 1] - P[i]; tm = P[i] - P[i - 1]
            if Es[i + 1] > Es[i] > Es[i - 1]: tau = tp
            elif Es[i + 1] < Es[i] < Es[i - 1]: tau = tm
            else:
                dmax = max(abs(Es[i + 1] - Es[i]), abs(Es[i - 1] - Es[i])); dmin = min(abs(Es[i + 1] - Es[i]), abs(Es[i - 1] - Es[i]))
                tau = tp * dmax + tm * dmin if Es[i + 1] > Es[i - 1] else tp * dmin + tm * dmax
            tau = tau / (np.linalg.norm(tau) + 1e-12); Fpar = (Fs[i] * tau).sum() * tau; Fperp = Fs[i] - Fpar; Fspr = k_spr * (np.linalg.norm(tp) - np.linalg.norm(tm)) * tau
            G[i] = (Fs[i] - 2 * Fpar) if (climb is not None and i == climb) else (Fperp + Fspr)
        return Es, G
    for it in range(iters):
        climb = int(np.argmax(forces_all(P)[0])) if it > iters // 2 else None
        Es, G = G_of(P, climb); V[1:-1] = 0.9 * V[1:-1] + dt * G[1:-1]
        step = dt * V[1:-1]; nrm = np.linalg.norm(step, axis=(1, 2), keepdims=True); step = step * np.minimum(1.0, 0.05 / (nrm + 1e-12)); P[1:-1] += step
    Es, _ = forces_all(P); i = int(np.argmax(Es)); return Es, i, P
for name, A0, B0, EA, EB in (('−41.47 → −41.44', x47, x44, E47, E44), ('−41.44 → икосаэдр', x44, x_gs, E44, E_gs), ('−41.47 → икосаэдр (повтор)', x47, x_gs, E47, E_gs)):
    rmsd, A, B = align(A0, B0); Es, i, P = neb(A, B)
    qa, qb = inherent(P[max(i - 1, 0)])[0], inherent(P[min(i + 1, len(P) - 1)])[0]
    print(f"{name}: RMSD {rmsd:.2f} | TS {Es[i]:.3f} | барьер вперёд {Es[i]-EA:.3f}, назад {Es[i]-EB:.3f} | квенчи соседей TS {qa:.3f} / {qb:.3f} | профиль {np.round(Es[::2], 2)}", flush=True)
