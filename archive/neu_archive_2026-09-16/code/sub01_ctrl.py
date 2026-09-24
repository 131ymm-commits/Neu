"""SUB-01 — недоделанные контроли (a) рампа ×2 медленнее на 5 ρ, (b) второй сид на 5 ρ (разброс W), (d) сходимость ζ 200 против 50 образцов на 3 ρ.
Описательно, по PREREG SUB-01 (контроли названы до прогона)."""
import numpy as np, json, sys, time, warnings
warnings.filterwarnings('ignore'); sys.path.insert(0, '/home/claude')
from morse13 import *
from mol_levels_lib import microstates
from deeptime.markov import TransitionCountEstimator
from deeptime.markov.msm import BayesianMSM, MaximumLikelihoodMSM
T_HI, T_LO = 0.6, 0.05; t0 = time.time(); out = dict(ramp2=[], seed2=[], zeta_conv=[])
def smooth_cross(T, E, Emid, down, w=25):
    Es = np.convolve(E, np.ones(w) / w, 'valid'); Ts = T[w // 2: w // 2 + len(Es)]
    idx = np.flatnonzero((Es < Emid) if down else (Es > Emid)); return (float(Ts[idx[0]]) if idx.size else None)
def ramps(rho, seed, steps):
    rng = np.random.default_rng(seed); x = icosahedron(); v = rng.normal(0, np.sqrt(T_HI), (N, 3)); v -= v.mean(0); x, v, _ = langevin(x, v, T_HI, 20000, rng, rho)
    cool = lambda s: T_HI - (T_HI - T_LO) * s / steps; x, v, oc = langevin(x, v, T_HI, steps, rng, rho, rec_every=100, Tsched=cool)
    heat = lambda s: T_LO + (T_HI - T_LO) * s / steps; x, v, oh = langevin(x, v, T_LO, steps, rng, rho, rec_every=100, Tsched=heat)
    Tc = np.array([o[0] for o in oc]); Ec = np.array([o[1] for o in oc]); Th = np.array([o[0] for o in oh]); Eh = np.array([o[1] for o in oh])
    Ehot = Ec[Tc > T_HI - 0.05].mean(); Ecold = Ec[Tc < T_LO + 0.05].mean(); Emid = 0.5 * (Ehot + Ecold)
    Tf = smooth_cross(Tc, Ec, Emid, True); Tm = smooth_cross(Th, Eh, Emid, False)
    return Tf, Tm, ((Tm - Tf) / Tm if (Tf and Tm) else None)
base = {}
for p in (0, 1):
    try: base.update(json.load(open(f'/home/claude/sub01_morse_{p}.json')))
    except FileNotFoundError: pass
def nearest(rho): k = min(base, key=lambda k: abs(base[k]['rho'] - rho)); return base[k]
for rho in (3.5, 6.0, 8.5, 11.0, 13.5):
    b = nearest(rho); rho0 = b['rho']; seed0 = int(rho0 * 1000) + 5000
    Tf2, Tm2, W2 = ramps(rho0, seed0, 240000); Tf1, Tm1, W1 = ramps(rho0, seed0 + 77, 120000)
    W0 = (b['W'] / b['Tm']) if (b['W'] is not None and b['Tm']) else None
    out['ramp2'].append(dict(rho=rho0, Tf_base=b['Tf'], Tm_base=b['Tm'], Wrel_base=W0, Tf_slow=Tf2, Tm_slow=Tm2, Wrel_slow=W2))
    out['seed2'].append(dict(rho=rho0, Wrel_base=W0, Wrel_seed2=W1, Tf_seed2=Tf1, Tm_seed2=Tm1))
    print(f"ρ={rho0:.2f}: база T_f {b['Tf']} T_m {b['Tm']} W/T_m {None if W0 is None else round(W0, 3)} | рампа ×2 медленнее: T_f {Tf2} T_m {Tm2} W/T_m {None if W2 is None else round(W2, 3)} | второй сид: W/T_m {None if W1 is None else round(W1, 3)} [{time.time()-t0:.0f}s]", flush=True)
    json.dump(out, open('/home/claude/sub01_ctrl.json', 'w'), indent=1, default=float)
def spacing_stats(ts, tau):
    r = ts[ts > tau]
    if len(r) < 4: return None
    s = np.log(r[:-1] / r[1:]); k = np.arange(1, len(s) + 1); z = k * s; return dict(p1=float(np.exp(-z[0] / z[1:].mean())), m=len(s))
for rho in (5.0, 9.0, 13.0):
    b = nearest(rho); rho0 = b['rho']; Tstar = b['Tstar']; rng = np.random.default_rng(int(rho0 * 1000) + 9000)
    x = icosahedron(); v = rng.normal(0, np.sqrt(Tstar), (N, 3)); v -= v.mean(0); x, v, _ = langevin(x, v, Tstar, 20000, rng, rho0); x, v, ox = langevin(x, v, Tstar, 200000, rng, rho0, rec_every=25)
    F = np.sort(np.array([o[2] for o in ox]), axis=1); lab = microstates(F, 100, seed=0)
    c = TransitionCountEstimator(lagtime=4, count_mode='effective').fit_fetch(lab.astype(int)).submodel_largest(); msm = MaximumLikelihoodMSM(reversible=True).fit(c).fetch_model()
    PL = {}
    for ns in (50, 200):
        post = BayesianMSM(n_samples=ns, reversible=True).fit(msm).fetch_model(); ps = []; ms = []
        for mm in post.samples:
            st = spacing_stats(np.sort(mm.timescales(14))[::-1], 4)
            if st is None: ms.append(0); continue
            ps.append(st['p1']); ms.append(st['m'])
        PL[ns] = float(np.mean(np.array(ps) <= 0.05)) if ps else 0.0
    out['zeta_conv'].append(dict(rho=rho0, PL50=PL[50], PL200=PL[200], PL_base=b['zeta']['PL'], dec_base=b['zeta']['dec']))
    print(f"ρ={rho0:.2f}: P_L 50 образцов {PL[50]:.2f}, 200 образцов {PL[200]:.2f} (база {b['zeta']['PL']:.2f}, {b['zeta']['dec']}) [{time.time()-t0:.0f}s]", flush=True)
    json.dump(out, open('/home/claude/sub01_ctrl.json', 'w'), indent=1, default=float)
print('готово', time.time() - t0)
