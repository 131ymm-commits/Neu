#!/usr/bin/env python3
"""TRUST-01: вердикты по букве PREREG-TRUST-01.md §4 из results_trust_01.json → analysis_trust_01.json.
Запуск: python3 analyze_trust_01.py [путь к results] (по умолчанию results_trust_01.json рядом)."""
import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
src = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, 'results_trust_01.json')
d = json.load(open(src))
th = d['theory']
w_ml, w_naive = np.array(th['w_ml']), np.array(th['w_naive'])
R = np.array(d['params']['R_IND'])
runs = {(r['seed'], r['arm']): r for r in d['runs']}
seeds = sorted({r['seed'] for r in d['runs']})
IDENT = [0, 1, 2, 4, 5]          # w0, r0.55, r0.65, r0.85, r0.92 — опознаваемые по отдельности
UNPAIRED = [1, 2, 4, 5]          # независимые источники вне пары «источник 0,75 + пересказ»
PAIR = [3, 6]                    # r0.75 и COPY — почти коллинеарны, опознаётся сумма
lg = np.log(R / (1 - R))
lin = R - 0.5


def w(s, a):
    return np.array(runs[(s, a)]['w_final'])


def sse_fit(y, x):
    k = float(y @ x / (x @ x)); return float(((y - k * x) ** 2).sum())


def scale(v):
    """Масштаб по опознаваемым частям: четыре источника вне пары и сумма пары (раздел пары не опознаётся)."""
    v = np.asarray(v, float)
    return float(np.sqrt((v[UNPAIRED] ** 2).sum() + v[PAIR].sum() ** 2))


rows = {}
for s in seeds:
    wk = w(s, 'KELLY')
    dev = np.concatenate([np.abs(wk[IDENT] - w_ml[IDENT]), [abs(wk[PAIR].sum() - w_ml[PAIR].sum())]])
    yk = wk[UNPAIRED]
    rows[s] = dict(
        mad=float(dev.mean()), maxdev=float(dev.max()), scale_ratio=scale(wk) / scale(w_ml),
        sd_kelly=runs[(s, 'KELLY')]['test']['self_dec'],
        sse_logit=sse_fit(yk, lg[[u - 1 for u in UNPAIRED]]), sse_lin=sse_fit(yk, lin[[u - 1 for u in UNPAIRED]]),
        pair_sum=float(wk[PAIR].sum()), w0_dev=float(abs(wk[0] - w_ml[0])),
        sd={a: runs[(s, a)]['test']['self_dec'] for a in ('KELLY', 'INDEP', 'ACC', 'CONTEST')},
        acc={a: runs[(s, a)]['test']['acc'] for a in ('KELLY', 'INDEP', 'ACC', 'CONTEST')},
        ece={a: runs[(s, a)]['test']['ece'] for a in ('KELLY', 'INDEP', 'ACC', 'CONTEST')},
        scale={a: scale(w(s, a)) / scale(w_ml) for a in ('KELLY', 'INDEP', 'ACC', 'CONTEST')},
        shifted_sd_kelly=runs[(s, 'KELLY')]['shifted']['self_dec'],
        acc_scale_late=[scale(t['w']) for t in runs[(s, 'ACC')]['traj'] if t['g'] in (750, 1499)],
    )
n = len(seeds)
cnt = lambda f: int(sum(bool(f(rows[s])) for s in seeds))


def boot_ci(x, B=10000, seed=0):
    x = np.asarray(x, float); g = np.random.default_rng(seed)
    m = x[g.integers(0, len(x), (B, len(x)))].mean(1)
    return [float(np.mean(x)), float(np.quantile(m, 0.025)), float(np.quantile(m, 0.975))]


V = {}
c1 = (np.mean([rows[s]['mad'] for s in seeds]) <= 0.15, cnt(lambda r: 0.9 <= r['scale_ratio'] <= 1.2) >= 9,
      cnt(lambda r: abs(r['sd_kelly']) <= 0.015) >= 9)
V['T1'] = dict(ok=all(c1), mad_mean=float(np.mean([rows[s]['mad'] for s in seeds])),
               scale_ratio_in=cnt(lambda r: 0.9 <= r['scale_ratio'] <= 1.2), calibrated=cnt(lambda r: abs(r['sd_kelly']) <= 0.015))
V['T2'] = dict(ok=cnt(lambda r: r['sse_logit'] < r['sse_lin']) >= 9, wins=cnt(lambda r: r['sse_logit'] < r['sse_lin']))
V['T3'] = dict(ok=cnt(lambda r: r['pair_sum'] <= 1.6) >= 9, n_ok=cnt(lambda r: r['pair_sum'] <= 1.6),
               pair_sum_mean=float(np.mean([rows[s]['pair_sum'] for s in seeds])),
               ml=float(w_ml[PAIR].sum()), naive=float(w_naive[PAIR].sum()))
V['T4'] = dict(ok=cnt(lambda r: r['w0_dev'] <= 0.25) >= 9, n_ok=cnt(lambda r: r['w0_dev'] <= 0.25))
V['T5'] = dict(ok=cnt(lambda r: r['sd']['INDEP'] >= 0.02) >= 9 and cnt(lambda r: r['scale']['INDEP'] >= 1.5) >= 9,
               n_sd=cnt(lambda r: r['sd']['INDEP'] >= 0.02), n_scale=cnt(lambda r: r['scale']['INDEP'] >= 1.5),
               sd_ci=boot_ci([rows[s]['sd']['INDEP'] for s in seeds]))
V['T6a'] = dict(ok=cnt(lambda r: abs(r['sd']['ACC']) > abs(r['sd']['KELLY'])) >= 8,
                n=cnt(lambda r: abs(r['sd']['ACC']) > abs(r['sd']['KELLY'])),
                sd_acc_ci=boot_ci([rows[s]['sd']['ACC'] for s in seeds]))
V['T6b'] = dict(ok=cnt(lambda r: r['acc_scale_late'][1] > r['acc_scale_late'][0]) >= 7,
                n=cnt(lambda r: r['acc_scale_late'][1] > r['acc_scale_late'][0]))
gap = {a: float(np.mean([abs(rows[s]['acc'][a] - rows[s]['acc']['KELLY']) for s in seeds])) for a in ('INDEP', 'ACC', 'CONTEST')}
V['T7'] = dict(ok=all(v <= 0.005 for v in gap.values()), gap=gap)
V['T8'] = dict(ok=cnt(lambda r: r['shifted_sd_kelly'] >= 0.03) >= 9, n=cnt(lambda r: r['shifted_sd_kelly'] >= 0.03),
               ci=boot_ci([rows[s]['shifted_sd_kelly'] for s in seeds]), ml=th['shifted_ml']['self_dec'])
V['T9'] = dict(ok=cnt(lambda r: r['sd']['CONTEST'] > r['sd']['KELLY']) >= 7, n=cnt(lambda r: r['sd']['CONTEST'] > r['sd']['KELLY']),
               diff_ci=boot_ci([rows[s]['sd']['CONTEST'] - rows[s]['sd']['KELLY'] for s in seeds]))
summary = {a: {k: boot_ci([rows[s][k][a] for s in seeds]) for k in ('sd', 'acc', 'ece', 'scale')} for a in ('KELLY', 'INDEP', 'ACC', 'CONTEST')}
out = dict(verdicts=V, per_seed=rows, summary=summary, theory=dict(w_ml=w_ml.tolist(), w_naive=w_naive.tolist(),
           test_ml=th['test_ml'], test_naive=th['test_naive'], shifted_ml=th['shifted_ml']), n_seeds=n)
json.dump(out, open(os.path.join(os.path.dirname(os.path.abspath(src)), 'analysis_trust_01.json'), 'w'), ensure_ascii=False, indent=1)
for k, v in V.items():
    print(k, '✓' if v['ok'] else '✗', {kk: vv for kk, vv in v.items() if kk != 'ok'})
for a, m in summary.items():
    print(a, {k: [round(x, 4) for x in v] for k, v in m.items()})
