# Сводка EQUIV-01 (P1–P6, сиды 0–2) и EQUIV-01B (Q1–Q9, сиды 3–5) строго по предрегистрациям
import json, os, numpy as np

out = {}
S = [0, 1, 2]
fin = {s: json.load(open(f'eq01_final_s{s}.json')) for s in S if os.path.exists(f'eq01_final_s{s}.json')}
ck = {s: json.load(open(f'eq01_ckpt_s{s}.json')) for s in S if os.path.exists(f'eq01_ckpt_s{s}.json')}
print('=== EQUIV-01 (исходная предрегистрация), сиды', sorted(fin))
if fin:
    r2 = {s: fin[s]['R2'] for s in fin}
    rep = {s: fin[s]['R2_reparam'] for s in fin}
    psu = [r2[s]['PSU'] for s in fin]
    print('R² ПСУ:', np.round(psu, 3), 'потолок:', np.round([r2[s]['probe64'] for s in fin], 3))
    P1 = dict(values=psu, spread=float(max(psu) - min(psu)), passed=bool(min(psu) >= 0.8 and max(psu) - min(psu) <= 0.10),
              killed=bool(min(psu) < 0.5))
    dpsu = [rep[s]['PSU'] - r2[s]['PSU'] for s in fin]
    dpca = [rep[s]['PCA'] - r2[s]['PCA'] for s in fin]
    P2 = dict(d_psu=dpsu, d_pca=dpca, passed=bool(max(abs(x) for x in dpsu) <= 0.02 and sum(abs(x) >= 0.10 for x in dpca) >= 2),
              killed=bool(max(abs(x) for x in dpsu) > 0.05))
    comp = {}
    for s in fin:
        o = r2[s]
        comp[s] = {'PCA': o['PCA'], 'kmeans3': o['kmeans3'], 'DMD': o['DMD'], 'SVDCE': max(o['SVDCE_a'], o['SVDCE_b'])}
    beats = {k: sum(comp[s][k] > r2[s]['PSU'] + 0.02 for s in fin) for k in comp[list(fin)[0]]}
    P3 = dict(competitors=comp, psu=psu, passed=bool(all(r2[s]['PSU'] >= max(comp[s].values()) - 0.02 for s in fin)),
              failed=bool(any(v >= 2 for v in beats.values())))
    t1 = [next(t for t in fin[s]['tau'] if t['tau'] == 1)['detectable'] for s in fin]
    t24 = [next(t for t in fin[s]['tau'] if t['tau'] == 24)['detectable'] for s in fin]
    P4 = dict(det_tau1=t1, det_tau24=t24, passed=bool(min(t1) >= 4 and max(t24) <= 3))
    P6 = {s: fin[s]['n_star'] for s in fin}
    out['EQUIV01'] = dict(P1=P1, P2=P2, P3=P3, P4=P4, P6=P6)
    for k, v in out['EQUIV01'].items():
        print(k, v)
if ck:
    P5 = {s: ck[s]['P5'] for s in ck}
    at_init = {s: ck[s]['traj'][0]['rho2'] > ck[s]['traj'][0]['thr'] for s in ck}
    out.setdefault('EQUIV01', {})['P5'] = dict(per_seed=P5, rho2_above_null_at_init=at_init)
    print('P5', P5, 'ρ₂ выше порога уже при инициализации:', at_init)

S2 = [3, 4, 5]
fb = {s: json.load(open(f'eq01b_final_s{s}.json')) for s in S2 if os.path.exists(f'eq01b_final_s{s}.json')}
cb = {s: json.load(open(f'eq01b_ckpt_s{s}.json')) for s in S2 if os.path.exists(f'eq01b_ckpt_s{s}.json')}
print('=== EQUIV-01B (вторая предрегистрация), сиды', sorted(fb))
if fb:
    f = {s: fb[s]['final'] for s in fb}
    sp = {s: {(x['kind'], x['tau']): x for x in fb[s]['spectra']} for s in fb}
    Q = {}
    ratio = {s: f[s]['PSU2'] / f[s]['ceiling'] for s in fb}
    Q['Q1'] = dict(psu2=[f[s]['PSU2'] for s in fb], ceiling=[f[s]['ceiling'] for s in fb], ratio=list(ratio.values()),
                   passed=bool(min(ratio.values()) >= 0.90), killed=bool(min(ratio.values()) < 0.75))
    Q['Q2'] = dict(diff=[f[s]['PSU2'] - f[s]['PSU_linear'] for s in fb],
                   passed=bool(min(f[s]['PSU2'] - f[s]['PSU_linear'] for s in fb) >= 0.30))
    names = ['PCA', 'kmeans3', 'DMD', 'SVDCE', 'PSU_linear']
    beats = {k: sum(f[s][k] > f[s]['PSU2'] + 0.02 for s in fb) for k in names}
    Q['Q3'] = dict(others={s: {k: round(f[s][k], 3) for k in names} for s in fb},
                   passed=bool(all(f[s]['PSU2'] >= max(f[s][k] for k in names) - 0.02 for s in fb)),
                   failed=bool(any(v >= 2 for v in beats.values())))
    Q['Q4'] = dict(gap_at=[sp[s][('own2', 16)]['gap_at'] for s in fb], detectable=[sp[s][('own2', 16)]['detectable'] for s in fb],
                   passed=bool(all(sp[s][('own2', 16)]['gap_at'] == 2 and sp[s][('own2', 16)]['detectable'] >= 2 for s in fb)))
    Q['Q5'] = dict(rho_own=[f[s]['rho_own'][:2] for s in fb], rho_world=[f[s]['rho_world'][:2] for s in fb],
                   r2_own=[f[s]['PSU2'] for s in fb], r2_world=[f[s]['PSU2_world'] for s in fb],
                   passed=bool(all(f[s]['rho_own'][0] > f[s]['rho_world'][0] and f[s]['rho_own'][1] > f[s]['rho_world'][1]
                                   and f[s]['PSU2'] >= f[s]['PSU2_world'] - 0.02 for s in fb)))
    Q['Q6'] = dict(d=[f[s]['PSU2_reparam'] - f[s]['PSU2'] for s in fb],
                   passed=bool(max(abs(f[s]['PSU2_reparam'] - f[s]['PSU2']) for s in fb) <= 0.02))
    Q['Q7'] = dict(det_tau1=[sp[s][('own2', 1)]['detectable'] for s in fb], gap_tau24=[sp[s][('own2', 24)]['gap_at'] for s in fb],
                   passed=bool(all(sp[s][('own2', 1)]['detectable'] >= 4 and sp[s][('own2', 24)]['gap_at'] == 2 for s in fb)))
    Q['Q9'] = dict(ratio=[f[s]['PSU2_cat'] / f[s]['ceiling_cat'] for s in fb],
                   passed=bool(all(f[s]['PSU2_cat'] >= 0.90 * f[s]['ceiling_cat'] for s in fb)))
    out['EQUIV01B'] = Q
    for k, v in Q.items():
        print(k, v)
if cb:
    q8 = {}
    for s in cb:
        tr = cb[s]['traj']
        b = next((t['step'] for t in tr if t['rho2'] > t['thr']), None)
        c = next((t['step'] for t in tr if t['ceiling'] >= 0.5), None)
        q8[s] = dict(birth_psu2=b, ceiling_ge_05=c, at_init=bool(tr[0]['rho2'] > tr[0]['thr']),
                     late_by=(None if b is None or c is None else b - c))
    lates = [v['late_by'] for v in q8.values() if v['late_by'] is not None]
    out.setdefault('EQUIV01B', {})['Q8'] = dict(per_seed=q8, passed=bool(all(v['late_by'] is not None and v['late_by'] <= 250 for v in q8.values())),
                                                 failed=bool(sum(x > 500 for x in lates) >= 2))
    print('Q8', out['EQUIV01B']['Q8'])
json.dump(out, open('eq01_summary.json', 'w'), indent=1, default=float)
