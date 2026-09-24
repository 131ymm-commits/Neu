"""REC-01 — LJ13: закалки из жидкости в T_q ∈ {0.10, 0.14, 0.20, 0.24} × сиды 701–720, квенч каждые 50 шагов; контроль — жидкость 0.36 × 701–710.
Плюс описательные контроли: интервал квенча 250 и допуск 1e-2 на 5 сидах при T_q = 0.20. По PREREG (2026-09-05)."""
import numpy as np, json, os, sys, time
sys.path.insert(0, '/home/claude')
from lj13_quench import quench_run, inherent
from lj13 import icosahedron
OUT = '/home/claude/rec01_lj.json'; res = json.load(open(OUT)) if os.path.exists(OUT) else {}
E_gs, _ = inherent(icosahedron()); t0 = time.time()

def phi_int(r, every, tol=1e-3):
    Eis = r['Eis']; recs = list(zip(r['rec_t'], r['rec_E'])); out = []
    for i in range(len(recs) - 1):
        a = recs[i][0] // every; b = recs[i + 1][0] // every; seg = Eis[a:b]
        if len(seg) > 1: out.append(float(np.mean(np.abs(seg - recs[i][1]) <= tol)))
    return out

def one(name, seed, Tq, quench=True, every=50, tol=1e-3, steps=200000):
    if name in res: return
    if quench: r = quench_run(seed, T_q=Tq, steps=steps, every=every, tol=tol, E_gs=E_gs)
    else: r = quench_run(seed, T_hot=0.36, T_q=0.36, equil=100000, steps=steps, every=every, tol=tol, E_gs=E_gs)
    pi = phi_int(r, every, tol)
    res[name] = dict(seed=seed, Tq=Tq, quench=quench, every=every, tol=tol, rec_t=r['rec_t'], rec_E=[float(e) for e in r['rec_E']], k_gs=r['k_gs'], t_gs=r['t_gs'],
                     n_rec=r['n_rec'], phi_trap=r['phi_trap'], phi_int=pi, phi_int_median=(float(np.median(pi)) if pi else None), frac_gs=r['frac_gs'], Eis_final=r['Eis_final'])
    json.dump(res, open(OUT, 'w'), indent=1)
    print(f"{name:18s} рекордов {r['n_rec']} k_gs {r['k_gs']} t_gs {r['t_gs']} φ_int {np.round(pi, 2)} φ_trap {r['phi_trap']:.2f} E: {np.round(r['rec_E'], 2)} [{time.time()-t0:.0f}s]", flush=True)

for Tq in (0.10, 0.14, 0.20, 0.24):
    for s in range(701, 721): one(f'Q{Tq}_{s}', s, Tq)
for s in range(701, 711): one(f'LIQ0.36_{s}', s, 0.36, quench=False)
for s in range(701, 706): one(f'Q0.2_e250_{s}', s, 0.20, every=250)
for s in range(701, 706): one(f'Q0.2_tol1e-2_{s}', s, 0.20, tol=1e-2)
print('готово', time.time() - t0)
