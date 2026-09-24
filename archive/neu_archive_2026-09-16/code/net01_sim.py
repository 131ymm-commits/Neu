"""NET-01 — траектории LJ13 с квенчем на каждом кадре (каждые 50 шагов): E_IS и отсортированные расстояния. Запуск: python3 net01_sim.py <T> <seed>"""
import numpy as np, sys, time, warnings
warnings.filterwarnings('ignore'); sys.path.insert(0, '/home/claude')
from lj13 import energy_forces, icosahedron, N, IU
from lj13_quench import inherent
T = float(sys.argv[1]); seed = int(sys.argv[2]); STEPS = 1_000_000; EVERY = 50; dt = 0.005; gamma = 2.0
rng = np.random.default_rng(seed); x = icosahedron().copy(); v = rng.normal(0, np.sqrt(T), (N, 3)); v -= v.mean(0); E, F = energy_forces(x)
# уравновешивание 100 000 шагов при T (без записи)
c1 = np.exp(-gamma * dt); c2 = np.sqrt((1 - c1 ** 2) * T); t0 = time.time()
for s in range(100000):
    v += 0.5 * dt * F; x += 0.5 * dt * v; v = c1 * v + c2 * rng.normal(size=(N, 3)); x += 0.5 * dt * v; E, F = energy_forces(x); v += 0.5 * dt * F
nrec = STEPS // EVERY; Eis = np.empty(nrec); Ep = np.empty(nrec); Dp = np.empty((nrec, len(IU[0])), np.float32); k = 0
for s in range(STEPS):
    v += 0.5 * dt * F; x += 0.5 * dt * v; v = c1 * v + c2 * rng.normal(size=(N, 3)); x += 0.5 * dt * v; E, F = energy_forces(x); v += 0.5 * dt * F
    if (s + 1) % EVERY == 0:
        Ep[k] = E; Dp[k] = np.sort(np.linalg.norm(x[IU[0]] - x[IU[1]], axis=1)); Eis[k] = inherent(x)[0]; k += 1
np.savez_compressed(f'/home/claude/net01_T{T:.2f}_s{seed}.npz', Ep=Ep, D=Dp, Eis=Eis)
print(f'T={T} сид {seed}: {nrec} кадров, IS различных (1e-3) {len(np.unique(np.round(Eis, 3)))}, доля икосаэдра {np.mean(Eis <= -44.32):.3f} [{time.time()-t0:.0f}s]', flush=True)
