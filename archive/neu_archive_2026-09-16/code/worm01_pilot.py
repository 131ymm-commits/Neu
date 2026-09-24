"""WORM-01 — пилот (2026-09-16): кусок 1 (кадры 0–8682; в тест НЕ входит) × 50 многомерных iAAFT-суррогатов; k = 30, K = 11, лаги 8/16/23/32/46.
Калибровка LOO ложных уровней правил «> P95 по 50» (e₊, a₊), нуль-доли рождений₊, распределение нуля по ρ, ρ₊, чередованию, f_est, точности направления.
Числа — worm01_pilot.json."""
import numpy as np, json, time, zlib
from worm01_lib import *
t0 = time.time(); OUT = '/home/claude/worm01_pilot.json'; NS = 50; K = 11; k = 30; TAUS = (8, 16, 23, 32, 46)
X, pieces = load_pieces(); a, b = pieces[0]; P1 = X[a:b]; dirlab, _ = angular_momentum_label(P1)
labs = labels_for([P1], K, k, seed=0); data = {tau: analyze(labs, tau, dir_labels=[dirlab], K=K) for tau in TAUS}
rng = np.random.default_rng(zlib.crc32(b'WORM-01-pilot-piece1')); sur = {tau: [] for tau in TAUS}
for j in range(NS):
    Y = iaaft_multi(P1, rng); dl, _ = angular_momentum_label(Y); ls = labels_for([Y], K, k, seed=0)
    for tau in TAUS: sur[tau].append(analyze(ls, tau, dir_labels=[dl], K=K))
    if j % 10 == 9: print(f'суррогат {j+1}/{NS} [{time.time()-t0:.0f}s]', flush=True)
calib = {}
for tau in TAUS:
    S = sur[tau]; e = np.array([s['e_plus'] for s in S], float); ap = np.array([s['a_plus'] if s['a_plus'] is not None else np.nan for s in S], float)
    fp_e = []; fp_a = []
    for j in range(NS):
        oth = np.delete(np.arange(NS), j); fp_e.append(bool(e[j] > np.percentile(e[oth], 95))); fp_a.append(bool(ap[j] > np.nanpercentile(ap[oth], 95)))
    d = data[tau]
    calib[tau] = dict(data=d, sur_e_p95=float(np.percentile(e, 95)), sur_e_max=float(e.max()), sur_e_med=float(np.median(e)), sur_born_frac=float(np.mean([s['born_plus'] for s in S])),
                      sur_a_p95=float(np.nanpercentile(ap, 95)), sur_a_med=float(np.nanmedian(ap)), sur_perm_frac=float(np.mean([s['perm'] for s in S])),
                      sur_rho_med=float(np.median([s['rho'] for s in S])), sur_rho_plus_med=float(np.median([s['rho_plus'] for s in S])), sur_alt_frac=float(np.mean([s['alternating'] for s in S])),
                      sur_gap_p95=float(np.percentile([s['rho_gap'] for s in S], 95)), sur_gap_med=float(np.median([s['rho_gap'] for s in S])),
                      sur_f_med=float(np.nanmedian([s['f_est'] for s in S])), sur_f_p95=float(np.nanpercentile([s['f_est'] for s in S], 95)),
                      sur_bacc_med=float(np.median([s['bacc_dir'] for s in S])), sur_bacc_p95=float(np.percentile([s['bacc_dir'] for s in S], 95)),
                      fp_e=float(np.mean(fp_e)), fp_a=float(np.mean(fp_a)), e_above=bool(d['e_plus'] > np.percentile(e, 95)), a_above=bool(d['a_plus'] > np.nanpercentile(ap, 95)),
                      bacc_above=bool(d['bacc_dir'] > np.percentile([s['bacc_dir'] for s in S], 95)))
    c = calib[tau]
    print(f"τ={tau}: данные e₊={d['e_plus']:+.3f} рожд₊={d['born_plus']} a₊={d['a_plus']:.2f} ρ={d['rho']:.3f} ρ₊={d['rho_plus']:.3f} черед={d['alternating']} f={d['f_est']:.2f} точн={d['bacc_dir']:.3f} | нуль: e₊ P95 {c['sur_e_p95']:+.3f} (max {c['sur_e_max']:+.3f}, мед {c['sur_e_med']:+.3f}), рожд₊ {c['sur_born_frac']:.2f}, a₊ P95 {c['sur_a_p95']:.2f}, пост {c['sur_perm_frac']:.2f}, ρ мед {c['sur_rho_med']:.3f}, ρ₊ мед {c['sur_rho_plus_med']:.3f}, черед {c['sur_alt_frac']:.2f}, Δρ P95 {c['sur_gap_p95']:.3f}, f мед {c['sur_f_med']:.2f} (P95 {c['sur_f_p95']:.2f}), точн мед {c['sur_bacc_med']:.3f} (P95 {c['sur_bacc_p95']:.3f}) | ложные: e {c['fp_e']:.3f}, a {c['fp_a']:.3f} | сверх: e {c['e_above']} a {c['a_above']} точн {c['bacc_above']}")
json.dump(dict(calib={str(t): v for t, v in calib.items()}, params=dict(NS=NS, K=K, k=k, taus=TAUS, piece=[int(a), int(b)]), sur={str(t): v for t, v in sur.items()}), open(OUT, 'w'), ensure_ascii=False, default=float)
print('ГОТОВО', f'{time.time()-t0:.0f}s')
