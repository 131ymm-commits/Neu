"""ARR-01 — Аррениус попытки: время первого достижения икосаэдра из изомера −41.47 ε при T ∈ {0.10…0.20}, 20 реплик, квенч каждые 25 шагов,
потолок 5e5 шагов (цензура). По PREREG 2026-09-08. Запуск: python3 arr01_run.py <part 0|1> (T-набор по чётности)."""
import numpy as np, json, os, sys, time, warnings
warnings.filterwarnings('ignore'); sys.path.insert(0, '/home/claude')
from lj13_quench import langevin, inherent
from lj13 import N
part = int(sys.argv[1]) if len(sys.argv) > 1 else 0
TS = ([0.14, 0.18, 0.30, 0.10] if part == 0 else [0.12, 0.16, 0.20])   # порядок: 0.10 последним (почти полная цензура, самый дорогой)
OUT = f'/home/claude/arr01_results_{part}.json'; res = json.load(open(OUT)) if os.path.exists(OUT) else {}
x47 = np.load('/home/claude/lj13_x_41_47.npy'); E47 = inherent(x47)[0]; EVERY = 25; CAP = 500000; NREP = 20; t0 = time.time()
for iT, T in enumerate(TS):
    key = f'T{T:.2f}'
    if key not in res: res[key] = dict(T=T, t_gs=[], t_exit=[], cens=[], E_first_exit=[])
    for j in range(len(res[key]['t_gs']), NREP if T < 0.3 else 10):
        seed = 900 + 100 * TS.index(T) + j + 1000 * part; rng = np.random.default_rng(seed)
        x = x47.copy(); v = rng.normal(0, np.sqrt(T), (N, 3)); v -= v.mean(0)
        t_exit = None; E_exit = None; t_gs = None; t = 0
        while t < CAP:
            x, v, _ = langevin(x, v, T, EVERY, rng); t += EVERY; E, _ = inherent(x)
            if t_exit is None and abs(E - E47) > 1e-3: t_exit = t; E_exit = float(E)
            if E <= -44.32: t_gs = t; break
        res[key]['t_gs'].append(t_gs if t_gs is not None else CAP); res[key]['cens'].append(t_gs is None)
        res[key]['t_exit'].append(t_exit if t_exit is not None else CAP); res[key]['E_first_exit'].append(E_exit)
        json.dump(res, open(OUT, 'w'), indent=1)
        print(f"T={T:.2f} реплика {j:2d}: выход из −41.47 при {t_exit} (в {E_exit}), икосаэдр при {t_gs} {'(цензура)' if t_gs is None else ''} [{time.time()-t0:.0f}s]", flush=True)
    tg = np.array(res[key]['t_gs'], float); c = np.array(res[key]['cens']); tau = tg.sum() / max(1, (~c).sum())
    print(f"== T={T:.2f}: τ̂_att = {tau:.0f} шагов, цензура {c.mean():.2f}, медиана t_gs {np.median(tg):.0f}, выход из бассейна медиана {np.median(res[key]['t_exit']):.0f}", flush=True)
print('готово', time.time() - t0)
