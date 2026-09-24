"""SUB-01 часть B — свип дальности потенциала Морзе ρ ∈ [3, 14] (100 «веществ»): рампы охлаждения/нагрева (окно гистерезиса),
спектральный отпечаток ζ при сосуществовании (байесовский постериор, как SPEC-01), закалка с рекордами (как REC-01).
По PREREG (2026-09-05). Запуск: python3 sub01_morse.py <part 0|1> (чётные/нечётные индексы ρ)."""
import numpy as np, json, os, sys, time, warnings
warnings.filterwarnings('ignore'); sys.path.insert(0, '/home/claude')
from morse13 import *
from mol_levels_lib import microstates
from deeptime.markov import TransitionCountEstimator
from deeptime.markov.msm import BayesianMSM, MaximumLikelihoodMSM
part = int(sys.argv[1]) if len(sys.argv) > 1 else 0
OUT = f'/home/claude/sub01_morse_{part}.json'; res = json.load(open(OUT)) if os.path.exists(OUT) else {}
RHOS = np.round(np.linspace(3.0, 14.0, 100), 3)[part::2]; t0 = time.time()
STEPS_RAMP = 120000; STEPS_COEX = 200000; STEPS_Q = 150000; T_HI, T_LO = 0.6, 0.05

def smooth_cross(T, E, Emid, down, w=25):
    Es = np.convolve(E, np.ones(w) / w, 'valid'); Ts = T[w // 2: w // 2 + len(Es)]
    idx = np.flatnonzero((Es < Emid) if down else (Es > Emid)); return (float(Ts[idx[0]]) if idx.size else None)

def spacing_stats(ts, tau):
    r = ts[ts > tau]
    if len(r) < 4: return None
    s = np.log(r[:-1] / r[1:]); k = np.arange(1, len(s) + 1); z = k * s
    return dict(p1=float(np.exp(-z[0] / z[1:].mean())), z1_rest=float(z[0] / z[1:].mean()), m=len(s), z=[float(v) for v in z[:5]])

def zeta_test(F, tau=4, k=100, ns=200):
    lab = microstates(F, k, seed=0)
    c = TransitionCountEstimator(lagtime=tau, count_mode='effective').fit_fetch(lab.astype(int)).submodel_largest()
    msm = MaximumLikelihoodMSM(reversible=True).fit(c).fetch_model(); post = BayesianMSM(n_samples=ns, reversible=True).fit(msm).fetch_model()
    ml = spacing_stats(np.sort(msm.timescales(14))[::-1], tau); ps = []; zr = []; ms = []
    for mm in post.samples:
        st = spacing_stats(np.sort(mm.timescales(14))[::-1], tau)
        if st is None: ms.append(0); continue
        ps.append(st['p1']); zr.append(st['z1_rest']); ms.append(st['m'])
    unresolved = np.mean(np.array(ms) < 3) > 0.5; PL = float(np.mean(np.array(ps) <= 0.05)) if ps else 0.0
    dec = 'отказ:не разрешён' if unresolved else ('уровень' if PL >= 0.95 else ('нет' if PL <= 0.05 else 'отказ'))
    return dict(PL=PL, zeta_median=(float(np.median(zr)) if zr else None), dec=dec, its_ml=[float(x) for x in np.sort(msm.timescales(14))[::-1][:6]], z_ml=(ml['z'] if ml else None), m_median=float(np.median(ms)))

for rho in RHOS:
    name = f'rho{rho:.3f}'
    if name in res: continue
    rho = float(rho); rng = np.random.default_rng(int(rho * 1000) + 5000); t1 = time.time()
    Egs, xgs = basin_hop(rho, seed=int(rho * 100), hops=30); Eico, _ = inherent(icosahedron(), rho)
    # 1) рампы: расплав при T_HI, охлаждение T_HI → T_LO, нагрев обратно
    x = icosahedron(); v = rng.normal(0, np.sqrt(T_HI), (N, 3)); v -= v.mean(0); x, v, _ = langevin(x, v, T_HI, 20000, rng, rho)
    cool = lambda s: T_HI - (T_HI - T_LO) * s / STEPS_RAMP; x, v, oc = langevin(x, v, T_HI, STEPS_RAMP, rng, rho, rec_every=100, Tsched=cool)
    heat = lambda s: T_LO + (T_HI - T_LO) * s / STEPS_RAMP; x, v, oh = langevin(x, v, T_LO, STEPS_RAMP, rng, rho, rec_every=100, Tsched=heat)
    Tc = np.array([o[0] for o in oc]); Ec = np.array([o[1] for o in oc]); Th = np.array([o[0] for o in oh]); Eh = np.array([o[1] for o in oh])
    Ehot = Ec[Tc > T_HI - 0.05].mean(); Ecold = Ec[Tc < T_LO + 0.05].mean(); Emid = 0.5 * (Ehot + Ecold)
    Tf = smooth_cross(Tc, Ec, Emid, True); Tm = smooth_cross(Th, Eh, Emid, False)
    W = (Tm - Tf) if (Tf is not None and Tm is not None) else None
    # 2) сосуществование: T* = (Tf + Tm)/2 (или Tf, если плавление не найдено)
    Tstar = 0.5 * (Tf + Tm) if W is not None else (Tf or 0.3)
    x = icosahedron(); v = rng.normal(0, np.sqrt(Tstar), (N, 3)); v -= v.mean(0); x, v, _ = langevin(x, v, Tstar, 20000, rng, rho)
    x, v, ox = langevin(x, v, Tstar, STEPS_COEX, rng, rho, rec_every=25)
    F = np.sort(np.array([o[2] for o in ox]), axis=1); Ex = np.array([o[1] for o in ox])
    zt = zeta_test(F, tau=4, k=100, ns=200)
    # доля времени в твёрдом (E ниже середины) при T* — санити сосуществования
    frac_solid = float(np.mean(Ex < Emid))
    # 3) закалка: расплав T_HI → 0.5·T*; IS каждые 100 шагов; рекорды; k_gs до E_gs (допуск 1e-3)
    Tq = 0.5 * Tstar; x = icosahedron(); v = rng.normal(0, np.sqrt(T_HI), (N, 3)); v -= v.mean(0); x, v, _ = langevin(x, v, T_HI, 20000, rng, rho); v *= np.sqrt(Tq / T_HI)
    nq = STEPS_Q // 100; Eis = np.empty(nq)
    for k in range(nq):
        x, v, _ = langevin(x, v, Tq, 100, rng, rho); Eis[k], _ = inherent(x, rho)
    rec_t, rec_E = [], []; cur = np.inf
    for k in range(nq):
        if Eis[k] < cur - 1e-3: cur = Eis[k]; rec_t.append((k + 1) * 100); rec_E.append(float(cur))
    k_gs = next((i for i, e in enumerate(rec_E) if abs(e - Egs) <= 1e-3), None)
    pi = []
    for i in range(len(rec_E) - 1):
        a = rec_t[i] // 100; b = rec_t[i + 1] // 100; seg = Eis[a:b]
        if len(seg) > 1: pi.append(float(np.mean(np.abs(seg - rec_E[i]) <= 1e-3)))
    res[name] = dict(rho=rho, E_gs=float(Egs), E_ico=float(Eico), ico_is_gs=bool(abs(Egs - Eico) < 1e-3), Tf=Tf, Tm=Tm, W=W, Tstar=float(Tstar), Ehot=float(Ehot), Ecold=float(Ecold),
                     frac_solid_coex=frac_solid, zeta=zt, Tq=float(Tq), n_rec=len(rec_t), rec_E=rec_E, rec_t=rec_t, k_gs=k_gs, phi_int=pi, secs=time.time() - t1)
    json.dump(res, open(OUT, 'w'), indent=1, default=float)
    print(f"ρ={rho:6.3f}: E_gs {Egs:.3f} (ico {'да' if res[name]['ico_is_gs'] else 'НЕТ'}) | Tf {Tf} Tm {Tm} W {None if W is None else round(W,3)} | T* {Tstar:.3f} тв.доля {frac_solid:.2f} | ζ {zt['zeta_median']} {zt['dec']} ITS {np.round(zt['its_ml'][:4],1)} | закалка: рекордов {len(rec_t)} k_gs {k_gs} φ_int {np.round(pi,2)} [{time.time()-t0:.0f}s]", flush=True)
print('готово', time.time() - t0)
