"""PTOL-01 — вердикты по PREREG (буква) и описательные величины (ζ_test, исчезающие моды)."""
import json, numpy as np
r = json.load(open('/home/claude/ptol01_results.json')); reps = [k for k in r if not k.startswith('T0.36')]
DK = ['D1_Epot', 'D2_Epot_m4', 'D3_dist78', 'D4_dist_lag', 'D5_D4_rff300', 'D6_D4_rff1000']
def g(k, dk, f): return r[k][dk][f]
print(f"{'траектория':12s} " + ' '.join(f"{d[:6]:>22s}" for d in DK))
for k in reps:
    print(f"{k:12s} " + ' '.join(f"r{str(g(k, d, 'r_ico')):>8s} sp{g(k, d, 'n_spur_mean'):4.1f} v{str(g(k, d, 'n_vanish')):>7s}" for d in DK))
print('\nζ (обуч.) / ζ_pruned / ζ_test / VAMP2 тест:')
for k in reps:
    print(f"{k:12s} " + ' | '.join(f"{d[:2]}: {np.round([x for x in g(k, d, 'zeta') if x is not None] or [np.nan], 2)} / {np.round([x for x in g(k, d, 'zeta_pruned') if x is not None] or [np.nan], 2)} / {np.round([x for x in g(k, d, 'zeta_test') if x is not None] or [np.nan], 2)} / {np.round([x for x in g(k, d, 'vamp2_test') if x is not None] or [np.nan], 2)}" for d in DK[2:]))
def both1(k, d): return all(x == 1 for x in g(k, d, 'r_ico'))
PP1 = dict(n_rank1_D3toD6=sum(all(both1(k, d) for d in DK[2:]) for k in reps), n_D1_unresolved=sum(all(f['n_resolved'] <= 2 for f in r[k]['D1_Epot']['folds']) for k in reps))
PP1['ok'] = PP1['n_rank1_D3toD6'] >= 5 and PP1['n_D1_unresolved'] >= 4
sp3 = [g(k, 'D3_dist78', 'n_spur_mean') for k in reps]; sp6 = [g(k, 'D6_D4_rff1000', 'n_spur_mean') for k in reps]
PP2 = dict(ok=bool(np.median(sp6) >= np.median(sp3) + 3 and sum(x <= 1 for x in sp3) >= 4), n_spur_D3=sp3, n_spur_D6=sp6, n_vanish_D3=[g(k, 'D3_dist78', 'n_vanish') for k in reps], n_vanish_D6=[g(k, 'D6_D4_rff1000', 'n_vanish') for k in reps])
def zm(k, d, f): v = [x for x in g(k, d, f) if x is not None]; return float(np.mean(v)) if v else None
pp3_a = sum(1 for k in reps if zm(k, 'D6_D4_rff1000', 'zeta_pruned') is not None and zm(k, 'D3_dist78', 'zeta') and abs(zm(k, 'D6_D4_rff1000', 'zeta_pruned') / zm(k, 'D3_dist78', 'zeta') - 1) <= 0.3)
pp3_b = sum(1 for k in reps if zm(k, 'D6_D4_rff1000', 'zeta') is not None and zm(k, 'D3_dist78', 'zeta') is not None and zm(k, 'D6_D4_rff1000', 'zeta') < zm(k, 'D3_dist78', 'zeta'))
pp3_test = sum(1 for k in reps if zm(k, 'D6_D4_rff1000', 'zeta_test') is not None and zm(k, 'D3_dist78', 'zeta') and abs(zm(k, 'D6_D4_rff1000', 'zeta_test') / zm(k, 'D3_dist78', 'zeta') - 1) <= 0.3)
PP3 = dict(ok=bool(pp3_a >= 4 and pp3_b >= 4), n_pruned_within30=pp3_a, n_zeta6_below_zeta3=pp3_b, descriptive_n_zetatest_within30=pp3_test,
           zeta3=[zm(k, 'D3_dist78', 'zeta') for k in reps], zeta6=[zm(k, 'D6_D4_rff1000', 'zeta') for k in reps], zeta6_test=[zm(k, 'D6_D4_rff1000', 'zeta_test') for k in reps])
pp4 = sum(1 for k in reps if zm(k, 'D6_D4_rff1000', 'vamp2_test') is not None and zm(k, 'D5_D4_rff300', 'vamp2_test') is not None and zm(k, 'D6_D4_rff1000', 'vamp2_test') <= zm(k, 'D5_D4_rff300', 'vamp2_test'))
PP4 = dict(ok=pp4 >= 4, n=pp4, vamp2=[[zm(k, d, 'vamp2_test') for d in DK[2:]] for k in reps])
K1 = dict(hit=sum(x <= 1 for x in sp6) >= 4); K2 = dict(hit=sum(1 for k in reps if all(sum(f['spur'][:8]) >= 3 for f in r[k]['D3_dist78']['folds'])) >= 4)
K3 = dict(hit=sum(1 for k in reps if not both1(k, 'D3_dist78')) >= 3)
ctrl = dict(shuffled_spur=[r[k]['D6_shuffled']['n_spur'] for k in reps], train5000_spur=[r[k]['D6_train5000']['n_spur'] for k in reps], train5000_vamp2=[r[k]['D6_train5000']['vamp2_test'] for k in reps],
            liquid={d: dict(r_ico=g('T0.36_s401', d, 'r_ico'), n_spur=g('T0.36_s401', d, 'n_spur_mean')) for d in DK[2:]} if 'T0.36_s401' in r else None)
V = dict(PP1=PP1, PP2=PP2, PP3=PP3, PP4=PP4, K1=K1, K2=K2, K3=K3, controls=ctrl)
json.dump(V, open('/home/claude/ptol01_summary.json', 'w'), indent=1, default=float)
print('\n== ВЕРДИКТЫ ==')
for k, v in V.items(): print(k, v)
