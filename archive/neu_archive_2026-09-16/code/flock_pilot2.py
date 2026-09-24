"""FLOCK-01 пилот 2 (сид 7002): совместное описание (x_cm-бин × θ-бин) как «лифтированный» ход стаи; η ∈ {1.0, 1.5, 2.0, 2.5, 3.0};
рождения разрезов по x (полуплоскости ящика) относительно ρ совместной цепи; τ, d₂."""
import numpy as np, json, sys, time; sys.path.insert(0, '/home/claude')
from flock_lib import *
from cog01_lib import stationary, sym_form, restrict, spectral_radius
from life02_lib import life, sorts
from deeptime.markov import TransitionCountEstimator
from deeptime.markov.msm import MaximumLikelihoodMSM
t0 = time.time(); rng = np.random.default_rng(7002); out = {}

def vicsek_xy(N, Lbox, v0, r, eta, steps, rng, burn=1000):
    pos = rng.uniform(0, Lbox, size=(N, 2)); th = rng.uniform(-np.pi, np.pi, size=N); cm = np.empty((steps, 2)); pol = np.empty(steps, dtype=complex)
    # центр масс на торе — через средние углов положения
    for t in range(burn + steps):
        d = pos[:, None, :] - pos[None, :, :]; d -= Lbox * np.round(d / Lbox); nb = (d ** 2).sum(-1) < r * r
        e = np.exp(1j * th); th = np.angle(nb @ e) + rng.uniform(-eta / 2, eta / 2, size=N)
        pos = (pos + v0 * np.column_stack([np.cos(th), np.sin(th)])) % Lbox
        if t >= burn:
            ang = np.exp(2j * np.pi * pos / Lbox).mean(0); cm[t - burn] = (np.angle(ang) % (2 * np.pi)) / (2 * np.pi) * Lbox; pol[t - burn] = e.mean()
    return cm, pol

for eta in (1.0, 1.5, 2.0, 2.5, 3.0):
    cm, pol = vicsek_xy(256, 16.0, 0.3, 1.0, eta, 30000, rng); kx, kt = 16, 8
    xb = (cm[:, 0] / 16.0 * kx).astype(int) % kx; tb = ((np.angle(pol) + np.pi) / (2 * np.pi) * kt).astype(int) % kt; joint = xb * kt + tb
    res_eta = dict(polar=float(np.abs(pol).mean()))
    for tau in (1, 5):
        cnt = TransitionCountEstimator(lagtime=tau, count_mode='sliding').fit_fetch(joint).submodel_largest()
        msm = MaximumLikelihoodMSM(reversible=False).fit(cnt).fetch_model(); P = np.asarray(msm.transition_matrix); pi = np.asarray(msm.stationary_distribution)
        states = np.asarray(cnt.state_symbols); xs = states // kt; A0 = restrict(sym_form(P, pi), pi); rho = spectral_radius(A0); S = (A0 + A0.T) / 2; om = float(np.linalg.eigvalsh(S)[-1])
        Am = sym_form(P, pi); asym = float(np.linalg.norm(Am - Am.T) / np.linalg.norm(Am))
        recs = []
        for start in range(kx // 2):
            half = set((start + i) % kx for i in range(kx // 2)); b = np.array([1 if x in half else 0 for x in xs])
            if b.min() == b.max(): continue
            r_ = life(P, pi, rho, b, 3000)
            if r_: recs.append(r_)
        ss = sorts(recs)
        res_eta[f'tau{tau}'] = dict(n_states=int(len(P)), rho=rho, omega=om, omr=om - rho, asym=asym, t_rho=-tau / np.log(rho), n_birth=len(recs), n_cuts=kx // 2, tau_med=(float(np.median([r['tau'] for r in recs if r['tau']])) if any(r['tau'] for r in recs) else None), fII=(float(np.mean([x == 'II' for x in ss])) if ss else None), frac_d2pos=(float(np.mean([r['d2'] > 0 for r in recs])) if recs else None), R_max=(max(np.log(rho) / np.log(r['Om']) for r in recs) if recs else None))
        print(f"η={eta} |P|={res_eta['polar']:.2f} τ={tau}: состояний {len(P)} ρ {rho:.4f} ω−ρ {om-rho:.4f} асим {asym:.2f} t_ρ {res_eta[f'tau{tau}']['t_rho']:.0f} | рождений x-полуплоскостей {len(recs)}/{kx//2} R_max {res_eta[f'tau{tau}']['R_max']} τ_med {res_eta[f'tau{tau}']['tau_med']} d₂>0 {res_eta[f'tau{tau}']['frac_d2pos']} fII {res_eta[f'tau{tau}']['fII']} [{time.time()-t0:.0f}s]", flush=True)
    out[f'eta{eta}'] = res_eta
json.dump(out, open('/home/claude/flock_pilot2.json', 'w'), default=float); print('готово', f'{time.time()-t0:.0f}s')
