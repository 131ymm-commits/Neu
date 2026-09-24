"""WORM-01 — прогон по PREREG (2026-09-16): тест — куски 2–5 (объединённый: 4 траектории в одной MSM; и по кускам), k = 30, K = 11,
лаги 8/16/23/32/46; нуль — 50 многомерных iAAFT на кусок (объединённый нуль — суррогаты всех кусков в одной MSM). Сиды — crc32 имён.
Контроли без кромок: k = 60 на объединённом тесте; leave-one-piece-out объединённого теста. Числа — worm01_results.json."""
import numpy as np, json, time, zlib
from worm01_lib import *
t0 = time.time(); OUT = '/home/claude/worm01_results.json'; NS = 50; K = 11; k = 30; TAUS = (8, 16, 23, 32, 46)
X, pieces = load_pieces(); test_pieces = pieces[1:]; Xs = [X[a:b] for a, b in test_pieces]; dls = [angular_momentum_label(x)[0] for x in Xs]
def full_analysis(Xlist, dlist, kk=k):
    labs = labels_for(Xlist, K, kk, seed=0); out = {}
    for tau in TAUS:
        r = analyze(labs, tau, dir_labels=dlist, K=K); nm = analyze_named(labs, tau, dlist, K); r['named'] = nm; out[tau] = r
    return out
def null_analysis(Xlist, seed_name, kk=k):
    rng = np.random.default_rng(zlib.crc32(seed_name.encode())); sur = {tau: [] for tau in TAUS}
    for j in range(NS):
        Ys = [iaaft_multi(x, rng) for x in Xlist]; dl = [angular_momentum_label(y)[0] for y in Ys]; ls = labels_for(Ys, K, kk, seed=0)
        for tau in TAUS:
            r = analyze(ls, tau, dir_labels=dl, K=K); r['named'] = analyze_named(ls, tau, dl, K); sur[tau].append(r)
    return sur
def summarize(data, sur):
    S = {}
    for tau in TAUS:
        d = data[tau]; s = sur[tau]; e = np.array([x['e_plus'] for x in s], float); ap = np.array([x['a_plus'] if x['a_plus'] is not None else np.nan for x in s], float)
        f = np.array([x['f_est'] for x in s], float); bc = np.array([x['bacc_dir'] for x in s], float)
        S[tau] = dict(rho=d['rho'], rho_plus=d['rho_plus'], rho_gap=d['rho_gap'], theta_rho=d['theta_rho'], alternating=d['alternating'], complex_rho=d['complex_rho'], C1=d['C1'], e_plus=d['e_plus'],
                      born_plus=d['born_plus'], a_plus=d['a_plus'], n_life=d['n_life'], n_max=d['n_max'], perm=d['perm'], perm1=bool(d['perm'] and d['a_plus'] is not None and d['a_plus'] > 1),
                      t_rho_plus_frames=d['t_rho_plus_frames'], t_w_frames=d['t_w_frames'], f_est=d['f_est'], bacc_dir=d['bacc_dir'], block_frac=d['block_frac'], n_states=d['n_states'],
                      named_born=(None if d['named'].get('degenerate') else d['named']['born_plus']), named_e=(None if d['named'].get('degenerate') else d['named']['e_plus']), named_agree=d['named'].get('agree_pcca'),
                      sur_e_p95=float(np.percentile(e, 95)), sur_e_max=float(e.max()), sur_e_med=float(np.median(e)), e_above=bool(d['e_plus'] > np.percentile(e, 95)),
                      sur_born_frac=float(np.mean([x['born_plus'] for x in s])), sur_a_p95=float(np.nanpercentile(ap, 95)), a_above=bool(d['a_plus'] is not None and d['a_plus'] > np.nanpercentile(ap, 95)),
                      sur_perm_frac=float(np.mean([x['perm'] for x in s])), sur_alt_frac=float(np.mean([x['alternating'] for x in s])), sur_rho_med=float(np.median([x['rho'] for x in s])),
                      sur_rho_plus_med=float(np.median([x['rho_plus'] for x in s])), sur_f_med=float(np.nanmedian(f)), sur_f_p95=float(np.nanpercentile(f, 95)), f_above=bool(np.isfinite(d['f_est']) and d['f_est'] > np.nanpercentile(f, 95)),
                      sur_bacc_p95=float(np.percentile(bc, 95)), sur_named_born_frac=float(np.mean([bool(x['named'].get('born_plus')) for x in s if not x['named'].get('degenerate')])) if any(not x['named'].get('degenerate') for x in s) else None)
    return S
def loo_pooled():
    out = {}
    for i in range(len(Xs)):
        Xl = [x for j, x in enumerate(Xs) if j != i]; dl = [d for j, d in enumerate(dls) if j != i]; dd = full_analysis(Xl, dl)
        out[f'без куска {i+2}'] = {tau: dict(rho=dd[tau]['rho'], rho_plus=dd[tau]['rho_plus'], alternating=dd[tau]['alternating'], e_plus=dd[tau]['e_plus'], born_plus=dd[tau]['born_plus'], a_plus=dd[tau]['a_plus'], f_est=dd[tau]['f_est'], bacc_dir=dd[tau]['bacc_dir']) for tau in TAUS}
    return out
# ---- объединённый тест ----
print('объединённый тест: кадров', sum(len(x) for x in Xs), 'куски', [len(x) for x in Xs], flush=True)
pooled_data = full_analysis(Xs, dls); pooled_sur = null_analysis(Xs, 'WORM-01-pooled'); pooled = summarize(pooled_data, pooled_sur)
for tau in TAUS:
    d = pooled[tau]; print(f"ОБЪЕД τ={tau}: ρ={d['rho']:.3f} ρ₊={d['rho_plus']:.3f} черед={d['alternating']} θ={d['theta_rho']:.2f} | e₊={d['e_plus']:+.3f} (нуль P95 {d['sur_e_p95']:+.3f}, max {d['sur_e_max']:+.3f}) сверх={d['e_above']} рожд₊={d['born_plus']} a₊={d['a_plus']:.2f} (P95 {d['sur_a_p95']:.2f}) жизнь={d['n_life']}/{d['n_max']} пост={d['perm']} | f={d['f_est']:.2f} (нуль мед {d['sur_f_med']:.2f} P95 {d['sur_f_p95']:.2f}) сверх={d['f_above']} | точн={d['bacc_dir']:.3f} (нуль P95 {d['sur_bacc_p95']:.3f}) | именов: рожд={d['named_born']} e₊={d['named_e']} [{time.time()-t0:.0f}s]", flush=True)
k60 = full_analysis(Xs, dls, kk=60); k60s = {tau: dict(rho=k60[tau]['rho'], rho_plus=k60[tau]['rho_plus'], alternating=k60[tau]['alternating'], theta_rho=k60[tau]['theta_rho'], e_plus=k60[tau]['e_plus'], born_plus=k60[tau]['born_plus'], a_plus=k60[tau]['a_plus'], n_life=k60[tau]['n_life'], n_max=k60[tau]['n_max'], f_est=k60[tau]['f_est'], bacc_dir=k60[tau]['bacc_dir']) for tau in TAUS}
print('k=60 (контроль):', {tau: (round(v['rho'], 3), round(v['rho_plus'], 3), v['alternating'], round(v['e_plus'], 3), round(v['bacc_dir'], 3), round(v['f_est'], 2)) for tau, v in k60s.items()}, flush=True)
loo = loo_pooled(); print('LOO по кускам (τ=23):', {kk: (round(v[23]['rho'], 3), round(v[23]['rho_plus'], 3), v[23]['alternating'], round(v[23]['e_plus'], 3), round(v[23]['bacc_dir'], 3)) for kk, v in loo.items()}, flush=True)
# ---- по кускам ----
per = {}
for i, (x, dl) in enumerate(zip(Xs, dls)):
    name = f'кусок {i+2}'; dd = full_analysis([x], [dl]); ss = null_analysis([x], f'WORM-01-{name}'); per[name] = summarize(dd, ss)
    d = per[name][23]; print(f"{name} ({len(x)} кадров) τ=23: ρ={d['rho']:.3f} ρ₊={d['rho_plus']:.3f} черед={d['alternating']} e₊={d['e_plus']:+.3f} (P95 {d['sur_e_p95']:+.3f}) сверх={d['e_above']} a₊={d['a_plus']:.2f} жизнь={d['n_life']}/{d['n_max']} пост∧a>1={d['perm1']} f={d['f_est']:.2f} точн={d['bacc_dir']:.3f} [{time.time()-t0:.0f}s]", flush=True)
# ---- вердикты ----
P = pooled; cnt = lambda key, tau: int(sum(bool(per[n][tau][key]) for n in per))
V = dict(PW1=bool(P[23]['alternating'] and P[23]['rho_plus'] < P[23]['rho'] and (not P[46]['alternating']) and cnt('alternating', 23) >= 2),
         PW2=bool(P[23]['e_above'] and P[23]['born_plus'] and cnt('e_above', 23) >= 3 and (not P[8]['e_above'])),
         PW3=bool(P[23]['bacc_dir'] >= 0.70 and sum(per[n][23]['bacc_dir'] >= 0.70 for n in per) >= 2),
         PW3b=bool(sum(1 for tau in TAUS if P[tau]['named_born'] is False) >= 4),
         PW4=bool((not P[23]['perm']) and (not P[32]['perm']) and P[23]['a_plus'] < 1 and P[32]['a_plus'] < 1 and (not P[23]['a_above']) and cnt('perm1', 23) <= 2),
         PW5=bool(P[23]['f_above'] and P[23]['f_est'] >= 1.4 and P[46]['f_est'] >= 1.3),
         K1=bool((not P[23]['alternating']) and cnt('alternating', 23) <= 1), K2=bool(not P[23]['e_above']), K3=bool(P[23]['bacc_dir'] < 0.60), K4=bool(P[46]['f_est'] < 1.15), K5=bool(P[23]['perm'] and P[23]['a_plus'] > 1),
         counts=dict(alt23=cnt('alternating', 23), e_above23=cnt('e_above', 23), bacc70_23=int(sum(per[n][23]['bacc_dir'] >= 0.70 for n in per)), perm1_23=cnt('perm1', 23), e_above8=cnt('e_above', 8)))
json.dump(dict(pooled={str(t): v for t, v in pooled.items()}, per_piece={n: {str(t): v for t, v in d.items()} for n, d in per.items()}, k60={str(t): v for t, v in k60s.items()}, loo={n: {str(t): v for t, v in d.items()} for n, d in loo.items()}, verdict=V,
               params=dict(NS=NS, K=K, k=k, taus=TAUS, pieces=[list(map(int, p)) for p in test_pieces], fs=16, seed='crc32(name)')), open(OUT, 'w'), ensure_ascii=False, default=float, indent=0)
print('ВЕРДИКТ', json.dumps(V, ensure_ascii=False)); print('ГОТОВО', f'{time.time()-t0:.0f}s')
