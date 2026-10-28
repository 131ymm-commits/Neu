#!/usr/bin/env python3
"""TRUST-03: вердикты и сводные исходы по букве PREREG-TRUST-03.md §4 из results_trust_03.json →
analysis_trust_03.json (рядом с входным файлом). Запуск: python3 analyze_trust_03.py [путь к results]."""
import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import exp_trust_03 as E  # noqa: E402

src = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, 'results_trust_03.json')
d = json.load(open(src))
th = d['theory']; seeds = d['params']['SEEDS']; NS = len(seeds)
R = {(r['seed'], r['arm']): r['final'] for r in d['runs']}
assert all((s, a) in R for s in seeds for a in E.ARMS), 'неполные ячейки'
W_MY, W_FAR = th['myopic']['wG'], th['farsighted']['wG']
assert abs(W_MY - 0.9873) < 1e-3 and abs(W_FAR - 0.6891) < 2e-3, 'теория не та, что в PREREG'
if NS != 10:
    print(f'внимание: зёрен {NS}, пороги PREREG заданы для 10 — вердикты ниже не в зачёт (пилот или сухой прогон)')


def boot_ci(x, B=10000, seed=0):
    x = np.asarray(x, float); g = np.random.default_rng(seed)
    m = x[g.integers(0, len(x), (B, len(x)))].mean(1)
    return [float(x.mean()), float(np.quantile(m, 0.025)), float(np.quantile(m, 0.975))]


def sign_outcome(count, k):
    return 'подтверждено' if count >= k else ('опровергнуто' if count <= NS - k else 'не показано')


col = lambda arm, k: [R[(s, arm)][k] for s in seeds]
V = {}
c1 = sum(abs(x - W_MY) <= 0.15 for x in col('MYOPIC', 'wG'))
V['P1'] = dict(ok=c1 >= 9, n=c1, wG=boot_ci(col('MYOPIC', 'wG')))
c2a = sum(abs(x - W_FAR) <= 0.1 for x in col('COUNCIL', 'wG'))
c2b = sum(abs(x - W_FAR) < abs(x - W_MY) for x in col('COUNCIL', 'wG'))
V['P2'] = dict(ok=bool(c2a >= 9 and c2b >= 9), n_near=c2a, n_closer=c2b, wG=boot_ci(col('COUNCIL', 'wG')),
               b=boot_ci(col('COUNCIL', 'b')))
c3 = sum(R[(s, 'COUNCIL')]['logloss'] < R[(s, 'MYOPIC')]['logloss'] for s in seeds)
V['P3'] = dict(ok=c3 >= 9, n=c3, outcome=sign_outcome(c3, 9),
               diff=boot_ci([R[(s, 'COUNCIL')]['logloss'] - R[(s, 'MYOPIC')]['logloss'] for s in seeds]))
c4 = sum(R[(s, 'COUNCIL_NOSEL')]['logloss'] - R[(s, 'COUNCIL')]['logloss'] >= 0.02 for s in seeds)
V['P4'] = dict(ok=c4 >= 9, n=c4, outcome=sign_outcome(c4, 9),
               diff=boot_ci([R[(s, 'COUNCIL_NOSEL')]['logloss'] - R[(s, 'COUNCIL')]['logloss'] for s in seeds]),
               wG_sd_groups=boot_ci(col('COUNCIL_NOSEL', 'wG_sd_groups')))
lo, hi = W_FAR + 0.05, W_MY - 0.05
c5 = sum(lo < x < hi for x in col('DEMES', 'wG'))
V['P5'] = dict(ok=c5 >= 8, n=c5, interval=[lo, hi], wG=boot_ci(col('DEMES', 'wG')))
c6 = sum(R[(s, 'DEMES')]['wG'] < R[(s, 'DEMES_10x40')]['wG'] for s in seeds)
V['P6'] = dict(ok=c6 >= 8, n=c6, outcome=sign_outcome(c6, 8), wG_10x40=boot_ci(col('DEMES_10x40', 'wG')),
               diff=boot_ci([R[(s, 'DEMES')]['wG'] - R[(s, 'DEMES_10x40')]['wG'] for s in seeds]))
c7 = sum(abs(x - W_MY) <= 0.15 for x in col('DEMES_NOSEL', 'wG'))
V['P7'] = dict(ok=c7 >= 9, n=c7, wG=boot_ci(col('DEMES_NOSEL', 'wG')))
e1 = sum(R[(s, 'COUNCIL')]['self_dec'] < R[(s, 'MYOPIC')]['self_dec'] for s in seeds)
V['E1'] = dict(ok=e1 >= 7, n=e1, outcome=sign_outcome(e1, 7),
               diff=boot_ci([R[(s, 'COUNCIL')]['self_dec'] - R[(s, 'MYOPIC')]['self_dec'] for s in seeds]),
               self_dec_council=boot_ci(col('COUNCIL', 'self_dec')), self_dec_myopic=boot_ci(col('MYOPIC', 'self_dec')))
e2 = sum(abs(x - W_FAR) <= 0.1 for x in col('COUNCIL_10x40', 'wG'))
V['E2'] = dict(ok=e2 >= 8, n=e2, wG=boot_ci(col('COUNCIL_10x40', 'wG')))
# P8 (после пилота 3): разложение Прайса в DEMES — отбор внутри групп тянет w_G вверх, отбор групп — вниз
assert all(abs(R[(s, a)]['price_within']) < 1e-12 for s in seeds for a in E.ARMS if E.ARMS[a]['council']), \
    'у общего гена группы внутригрупповая часть Прайса должна быть нулём'
assert all(abs(R[(s, a)]['price_between']) < 1e-12 for s in seeds for a in E.ARMS
           if not E.ARMS[a]['group_sel'] or E.ARMS[a]['m'] == 1), 'без отбора групп межгрупповая часть должна быть нулём'
c8 = sum(R[(s, 'DEMES')]['price_within'] > 0 and R[(s, 'DEMES')]['price_between'] < 0 for s in seeds)
V['P8'] = dict(ok=c8 >= 9, n=c8, outcome=sign_outcome(c8, 9), within=boot_ci(col('DEMES', 'price_within')),
               between=boot_ci(col('DEMES', 'price_between')), within_nosel=boot_ci(col('DEMES_NOSEL', 'price_within')),
               within_10x40=boot_ci(col('DEMES_10x40', 'price_within')))
for k in ('P1', 'P2', 'P5', 'P7', 'E2'):
    V[k]['outcome'] = 'подтверждено' if V[k]['ok'] else 'не подтверждено'
# сводные исходы (PREREG §4)
if V['P2']['ok'] and V['P3']['ok'] and V['P4']['ok']:
    s1 = 'подтверждено'
elif (sum(abs(x - W_FAR) > 0.15 for x in col('COUNCIL', 'wG')) >= 5
      or sum(R[(s, 'COUNCIL')]['logloss'] >= R[(s, 'MYOPIC')]['logloss'] for s in seeds) >= 5):
    s1 = 'опровергнуто'
else:
    s1 = 'не подтверждено'
if V['P5']['ok'] and V['P6']['ok']:
    s2 = 'подтверждено'
elif sum(x >= hi for x in col('DEMES', 'wG')) >= 5 or c6 <= 3:
    s2 = 'опровергнуто'
else:
    s2 = 'не подтверждено'
summary = dict(council_reaches_farsighted=s1, multilevel_partial_dose=s2)
arms_mean = {a: {k: boot_ci(col(a, k)) for k in ('wG', 'b', 'logloss', 'self_dec', 'acc', 'ece', 'wG_sd_groups',
                                                 'price_between', 'price_within')} for a in E.ARMS}
out = dict(verdicts=V, summary=summary, arms=arms_mean, theory=th, n_seeds=NS,
           rows={str(s): {a: R[(s, a)] for a in E.ARMS} for s in seeds})
json.dump(out, open(os.path.join(os.path.dirname(os.path.abspath(src)), 'analysis_trust_03.json'), 'w'),
          ensure_ascii=False, indent=1, default=lambda o: o.item() if hasattr(o, 'item') else str(o))
for k, v in V.items():
    print(k, '✓' if v['ok'] else '✗', v['outcome'], {kk: (np.round(vv, 4).tolist() if isinstance(vv, list) else vv)
                                                    for kk, vv in v.items() if kk not in ('ok', 'outcome')})
print('сводные исходы:', summary)
