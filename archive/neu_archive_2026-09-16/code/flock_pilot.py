"""FLOCK-01 пилот (сид 7001; калибровка): Вичек N = 256, ящик L = 16, v0 = 0.3, r = 1, η ∈ {0.3, 0.6, 1.0}; XY 16×16 при T ∈ {0.5, 0.9}; k = 16 бинов угла; лаг из ITS; необратимая ML-MSM: ρ, ω, w, рождения по полуплоскостям."""
import numpy as np, json, sys, time; sys.path.insert(0, '/home/claude')
from flock_lib import *
from cog01_lib import stationary, sym_form, restrict, spectral_radius, numerical_radius, lump
from life02_lib import life, sorts
from deeptime.markov import TransitionCountEstimator
from deeptime.markov.msm import MaximumLikelihoodMSM
t0 = time.time(); rng = np.random.default_rng(7001); out = {}

def analyze(z, k, tau, label):
    lab = angle_states(z, k); cnt = TransitionCountEstimator(lagtime=tau, count_mode='sliding').fit_fetch(lab).submodel_largest()
    msm = MaximumLikelihoodMSM(reversible=False).fit(cnt).fetch_model(); P = np.asarray(msm.transition_matrix); pi = np.asarray(msm.stationary_distribution)
    A0 = restrict(sym_form(P, pi), pi); rho = spectral_radius(A0); w = numerical_radius(A0); S = (A0 + A0.T) / 2; om = float(np.linalg.eigvalsh(S)[-1])
    Am = sym_form(P, pi); asym = float(np.linalg.norm(Am - Am.T) / np.linalg.norm(Am)); n = len(P); cuts = arc_cuts(n) if n == k else None
    recs = []
    if cuts is not None:
        for b in cuts:
            r = life(P, pi, rho, b, 2000)
            if r: recs.append(r)
    ss = sorts(recs) if recs else []
    d = dict(n_states=n, rho=rho, w=w, omega=om, delta=w - rho, omr=om - rho, asym=asym, t_rho=-tau / np.log(rho) if 0 < rho < 1 else None, n_birth=len(recs), n_cuts=(len(cuts) if cuts else None),
             tau_med=(float(np.median([r['tau'] for r in recs if r['tau']])) if any(r['tau'] for r in recs) else None), fII=(float(np.mean([x == 'II' for x in ss])) if ss else None), frac_d2pos=(float(np.mean([r['d2'] > 0 for r in recs])) if recs else None),
             polar=float(np.abs(z).mean()))
    print(label, json.dumps(d, ensure_ascii=False), f'[{time.time()-t0:.0f}s]', flush=True); return d

for eta in (0.3, 0.6, 1.0):
    z = vicsek(256, 16.0, 0.3, 1.0, eta, 20000, rng, burn=1000); out[f'vicsek_eta{eta}'] = {}
    for tau in (1, 5, 20): out[f'vicsek_eta{eta}'][f'tau{tau}'] = analyze(z, 16, tau, f'Вичек η={eta} τ={tau}')
for T in (0.5, 0.9):
    z = xy_metropolis(16, T, 6000, rng, burn=300); out[f'xy_T{T}'] = {}
    for tau in (1, 5, 20): out[f'xy_T{T}'][f'tau{tau}'] = analyze(z, 16, tau, f'XY T={T} τ={tau}')
json.dump(out, open('/home/claude/flock_pilot.json', 'w'), default=float); print('готово', f'{time.time()-t0:.0f}s')
