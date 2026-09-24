"""FLOCK-01 — стая Вичека: рождения x-полуплоскостей в совместном описании (x_cm × θ); η ∈ {2.0, 3.0, 4.0, 2π}; 3 сида; τ = 5. По PREREG 2026-09-14 (вечер)."""
import numpy as np, json, sys, time; sys.path.insert(0, '/home/claude')
src = open('/home/claude/flock_pilot2.py').read(); exec(src.split("for eta in")[0].split("t0 = time.time()")[0]); exec("def vicsek_xy" + src.split("def vicsek_xy")[1].split("for eta in")[0])
t0 = time.time(); OUT = '/home/claude/flock01_results.json'; res = {}; kx, kt = 16, 8; tau = 5
for eta in (2.0, 3.0, 4.0, 2 * np.pi):
    key = f'eta{eta:.3f}'; res[key] = []
    for seed in (7101, 7102, 7103):
        rng = np.random.default_rng(seed); cm, pol = vicsek_xy(256, 16.0, 0.3, 1.0, eta, 30000, rng)
        xb = (cm[:, 0] / 16.0 * kx).astype(int) % kx; tb = ((np.angle(pol) + np.pi) / (2 * np.pi) * kt).astype(int) % kt; joint = xb * kt + tb
        cnt = TransitionCountEstimator(lagtime=tau, count_mode='sliding').fit_fetch(joint).submodel_largest()
        msm = MaximumLikelihoodMSM(reversible=False).fit(cnt).fetch_model(); P = np.asarray(msm.transition_matrix); pi = np.asarray(msm.stationary_distribution)
        states = np.asarray(cnt.state_symbols); xs = states // kt; A0 = restrict(sym_form(P, pi), pi); rho = spectral_radius(A0); S = (A0 + A0.T) / 2; om = float(np.linalg.eigvalsh(S)[-1])
        Am = sym_form(P, pi); asym = float(np.linalg.norm(Am - Am.T) / np.linalg.norm(Am)); recs = []
        for start in range(kx // 2):
            half = set((start + i) % kx for i in range(kx // 2)); b = np.array([1 if x in half else 0 for x in xs])
            if b.min() == b.max(): continue
            r_ = life(P, pi, rho, b, 3000)
            if r_: recs.append(r_)
        ss = sorts(recs); d = dict(seed=seed, polar=float(np.abs(pol).mean()), n_states=int(len(P)), rho=rho, omega=om, omr=om - rho, asym=asym, t_rho=-tau / np.log(rho), n_birth=len(recs),
                                   R_max=(max(np.log(rho) / np.log(r['Om']) for r in recs) if recs else None), frac_d2pos=(float(np.mean([r['d2'] > 0 for r in recs])) if recs else None), fII=(float(np.mean([x == 'II' for x in ss])) if ss else None),
                                   tau_med=(float(np.median([r['tau'] for r in recs if r['tau']])) if any(r['tau'] for r in recs) else None), viol=int(len(recs) > 0 and om <= rho + 1e-9))
        res[key].append(d); print(f"η={eta:.2f} сид {seed}: |P| {d['polar']:.2f} ρ {rho:.4f} ω−ρ {om-rho:.4f} асим {asym:.2f} t_ρ {d['t_rho']:.0f} | рождений {len(recs)}/8 R_max {d['R_max']} d₂>0 {d['frac_d2pos']} fII {d['fII']} τ {d['tau_med']} нар {d['viol']} [{time.time()-t0:.0f}s]", flush=True)
        json.dump(res, open(OUT, 'w'), default=float)
g = lambda k: res[k]; e3, e2, e4, ec = g('eta3.000'), g('eta2.000'), g('eta4.000'), g(f'eta{2*np.pi:.3f}')
ok3 = sum(d['n_birth'] >= 3 for d in e3); d2pos3 = [d['frac_d2pos'] for d in e3 if d['frac_d2pos'] is not None]; fII3 = [d['fII'] for d in e3 if d['fII'] is not None]; Rm3 = [d['R_max'] for d in e3 if d['R_max']]
V = dict(K0=any(d['viol'] for k in res for d in res[k]) or any(d['n_birth'] > 0 for d in ec),
         PV1=dict(seeds_ge3=ok3, d2pos=d2pos3, fII=fII3, R_max=Rm3, ok=ok3 >= 2 and bool(d2pos3) and np.mean(d2pos3) >= 0.8 and bool(fII3) and np.mean(fII3) >= 0.8 and bool(Rm3) and max(Rm3) >= 1.02),
         PV2=dict(births=[d['n_birth'] for d in e2], ok=all(d['n_birth'] == 0 for d in e2)), PV3=dict(births=[d['n_birth'] for d in ec], asym=[d['asym'] for d in ec], ok=all(d['n_birth'] == 0 for d in ec) and all(d['asym'] <= 0.3 for d in ec)),
         PV4=dict(births=[d['n_birth'] for d in e4], ok=sum(d['n_birth'] > 0 for d in e4) >= 2),
         K1=sum(d['n_birth'] == 0 for d in e3) >= 2, K2=sum(d['n_birth'] > 0 for d in e2) >= 2, K3=bool(d2pos3) and np.mean(d2pos3) < 0.5)
res['verdict'] = V; json.dump(res, open(OUT, 'w'), default=float); print('ВЕРДИКТ', json.dumps(V, default=float, ensure_ascii=False)); print('ГОТОВО', f'{time.time()-t0:.0f}s')
