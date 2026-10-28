#!/usr/bin/env python3
"""TRUST-01: вердикты и сводные исходы по букве PREREG-TRUST-01.md §4 из results_trust_01.json →
analysis_trust_01.json (рядом с входным файлом). Запуск: python3 analyze_trust_01.py [путь к results]."""
import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
src = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, 'results_trust_01.json')
d = json.load(open(src))
th = d['theory']
w_ex, w_ml, w_naive = np.array(th['w_exact']), np.array(th['w_ml']), np.array(th['w_naive'])
R = np.array(d['params']['R_IND'])
ARMS = d['params']['ARMS']
runs = {(r['seed'], r['arm']): r for r in d['runs']}
seeds = sorted({r['seed'] for r in d['runs']})
DRY = 'dry' in os.path.dirname(os.path.abspath(src))
assert len(seeds) == (2 if DRY else 10) and all((s, a) in runs for s in seeds for a in ARMS)
IDENT = [0, 1, 2, 4, 5]          # w0, r0.55, r0.65, r0.85, r0.92 — опознаваемые по отдельности
UNPAIRED = [1, 2, 4, 5]          # независимые источники вне пары «источник 0,75 + пересказ»
PAIR = [3, 6]                    # r0.75 и COPY — почти коллинеарны, опознаётся сумма
lg = np.log(R / (1 - R))
lin = R - 0.5

# второй способ правды: ML против точных весов; выборочные метрики против точных
assert th['max_abs_ml_minus_exact'] <= 0.025, th['max_abs_ml_minus_exact']
gap2 = max(abs(r['exact']['self_dec'] - r['test']['self_dec']) for r in d['runs'])
assert gap2 <= 0.003, gap2


def w(s, a):
    return np.array(runs[(s, a)]['w_final'])


def sse_fit(y, x):
    k = float(y @ x / (x @ x)); return float(((y - k * x) ** 2).sum())


def scale(v):
    """Масштаб по опознаваемым частям, без w0: √(Σ w² четырёх источников вне пары + (сумма пары)²)."""
    v = np.asarray(v, float)
    return float(np.sqrt((v[UNPAIRED] ** 2).sum() + v[PAIR].sum() ** 2))


def boot_ci(x, B=10000, seed=0):
    x = np.asarray(x, float); g = np.random.default_rng(seed)
    m = x[g.integers(0, len(x), (B, len(x)))].mean(1)
    return [float(np.mean(x)), float(np.quantile(m, 0.025)), float(np.quantile(m, 0.975))]


rows = {}
for s in seeds:
    wk = w(s, 'KELLY')
    dev = np.concatenate([np.abs(wk[IDENT] - w_ex[IDENT]), [abs(wk[PAIR].sum() - w_ex[PAIR].sum())]])
    yk = wk[UNPAIRED]
    sd = {a: runs[(s, a)]['exact']['self_dec'] for a in ARMS}
    rows[s] = dict(
        mad=float(dev.mean()), maxdev=float(dev.max()), scale_ratio=scale(wk) / scale(w_ex),
        sse_logit=sse_fit(yk, lg[[u - 1 for u in UNPAIRED]]), sse_lin=sse_fit(yk, lin[[u - 1 for u in UNPAIRED]]),
        pair_sum=float(wk[PAIR].sum()), w0_dev=float(abs(wk[0] - w_ex[0])),
        sd=sd, acc={a: runs[(s, a)]['exact']['acc'] for a in ARMS}, ece={a: runs[(s, a)]['exact']['ece'] for a in ARMS},
        scale={a: scale(w(s, a)) / scale(w_ex) for a in ARMS}, neff={a: runs[(s, a)]['neff_late'] for a in ARMS},
        shifted_gap_kelly=runs[(s, 'KELLY')]['exact_shifted']['self_dec'] - th['exact_shifted_exact']['self_dec'],
        acc_scale_late=[scale(t['w']) for t in runs[(s, 'ACC')]['traj'] if t['g'] in (750, 1499)],
    )
n = len(seeds)
cnt = lambda f: int(sum(bool(f(rows[s])) for s in seeds))


def sign_outcome(count, k):
    """Счётное предсказание «в ≥ k из 10»: подтверждено при count ≥ k; опровергнуто при count ≤ 10 − k; иначе не показано."""
    return 'подтверждено' if count >= k else ('опровергнуто' if count <= 10 - k else 'не показано')


V = {}
c_mad = float(np.mean([rows[s]['mad'] for s in seeds]))
c_sc = cnt(lambda r: 0.9 <= r['scale_ratio'] <= 1.2); c_cal = cnt(lambda r: abs(r['sd']['KELLY']) <= 0.015)
V['T1'] = dict(ok=bool(c_mad <= 0.15 and c_sc >= 9 and c_cal >= 9), mad=boot_ci([rows[s]['mad'] for s in seeds]),
               scale_ratio_in=c_sc, calibrated=c_cal, scale_ratio=boot_ci([rows[s]['scale_ratio'] for s in seeds]),
               sd_kelly=boot_ci([rows[s]['sd']['KELLY'] for s in seeds]))
c2 = cnt(lambda r: r['sse_logit'] < r['sse_lin'])
V['T2'] = dict(ok=c2 >= 9, wins=c2, outcome=sign_outcome(c2, 9),
               sse_diff=boot_ci([rows[s]['sse_lin'] - rows[s]['sse_logit'] for s in seeds]))
c3 = cnt(lambda r: r['pair_sum'] <= 1.6)
V['T3'] = dict(ok=c3 >= 9, n_ok=c3, pair_sum=boot_ci([rows[s]['pair_sum'] for s in seeds]),
               exact=float(w_ex[PAIR].sum()), naive=float(w_naive[PAIR].sum()))
c4 = cnt(lambda r: r['w0_dev'] <= 0.25)
V['T4'] = dict(ok=c4 >= 9, n_ok=c4, w0_dev=boot_ci([rows[s]['w0_dev'] for s in seeds]))
c5 = cnt(lambda r: r['sd']['INDEP'] >= 0.02 and r['scale']['INDEP'] >= 1.5)        # оба условия в одном зерне
c5sd = cnt(lambda r: r['sd']['INDEP'] >= 0.02)
V['T5'] = dict(ok=c5 >= 9, joint=c5, sd_only=c5sd, outcome=sign_outcome(c5, 9),
               sd_indep=boot_ci([rows[s]['sd']['INDEP'] for s in seeds]),
               scale_indep=boot_ci([rows[s]['scale']['INDEP'] for s in seeds]))
neff_ratio = float(np.median([rows[s]['neff']['KLUCK'] / rows[s]['neff']['INDEP'] for s in seeds]))
c5c = cnt(lambda r: abs(r['sd']['KLUCK']) <= 0.015)
V['T5c'] = dict(ok=bool(c5c >= 9 and 0.5 <= neff_ratio <= 2.0), calibrated=c5c, neff_ratio_kluck_indep=neff_ratio,
                sd_kluck=boot_ci([rows[s]['sd']['KLUCK'] for s in seeds]))
c6a = cnt(lambda r: abs(r['sd']['ACC']) > abs(r['sd']['KELLY']))
V['T6a'] = dict(ok=c6a >= 8, n=c6a, outcome=sign_outcome(c6a, 8), sd_acc=boot_ci([rows[s]['sd']['ACC'] for s in seeds]))
c6b = cnt(lambda r: r['acc_scale_late'][1] > r['acc_scale_late'][0])
V['T6b'] = dict(ok=c6b >= 7, n=c6b, outcome=sign_outcome(c6b, 7))
gap = {a: float(np.mean([abs(rows[s]['acc'][a] - rows[s]['acc']['KELLY']) for s in seeds])) for a in ARMS if a != 'KELLY'}
V['T7'] = dict(ok=all(v <= 0.005 for v in gap.values()), gap=gap)
c8 = cnt(lambda r: abs(r['shifted_gap_kelly']) <= 0.01)
V['T8'] = dict(ok=c8 >= 9, n=c8, gap=boot_ci([rows[s]['shifted_gap_kelly'] for s in seeds]),
               exact_shifted=th['exact_shifted_exact']['self_dec'])
c9 = cnt(lambda r: r['sd']['CONTEST'] > r['sd']['KELLY6'])
V['T9'] = dict(ok=c9 >= 7, n=c9, outcome=sign_outcome(c9, 7),
               diff_contest_kelly6=boot_ci([rows[s]['sd']['CONTEST'] - rows[s]['sd']['KELLY6'] for s in seeds]),
               diff_contest_kelly=boot_ci([rows[s]['sd']['CONTEST'] - rows[s]['sd']['KELLY'] for s in seeds]),
               diff_kelly6_kelly=boot_ci([rows[s]['sd']['KELLY6'] - rows[s]['sd']['KELLY'] for s in seeds]))
for k in ('T1', 'T3', 'T4', 'T5c', 'T7', 'T8'):
    V[k]['outcome'] = 'подтверждено' if V[k]['ok'] else 'не подтверждено'

# тезис «калибровку решает форма выплаты» (PREREG §4)
if V['T1']['ok'] and V['T5']['ok'] and V['T5c']['ok']:
    thesis = 'подтверждено'
elif c5sd <= 2 or cnt(lambda r: abs(r['sd']['KELLY']) > 0.02) >= 5 or cnt(lambda r: abs(r['sd']['KLUCK']) > 0.02) >= 5:
    thesis = 'опровергнуто'
else:
    thesis = 'не подтверждено'

summary = {a: {k: boot_ci([rows[s][k][a] for s in seeds]) for k in ('sd', 'acc', 'ece', 'scale', 'neff')} for a in ARMS}
out = dict(verdicts=V, thesis=thesis, per_seed=rows, summary=summary, dry=DRY,
           theory=dict(w_exact=w_ex.tolist(), w_ml=w_ml.tolist(), w_naive=w_naive.tolist(),
                       max_abs_ml_minus_exact=th['max_abs_ml_minus_exact'], exact_exact=th['exact_exact'],
                       exact_naive=th['exact_naive'], exact_shifted_exact=th['exact_shifted_exact']),
           second_method_max_gap_self_dec=gap2, n_seeds=n)
json.dump(out, open(os.path.join(os.path.dirname(os.path.abspath(src)), 'analysis_trust_01.json'), 'w'), ensure_ascii=False, indent=1)
for k, v in V.items():
    print(k, '✓' if v['ok'] else '✗', v['outcome'], {kk: vv for kk, vv in v.items() if kk not in ('ok', 'outcome')})
print('тезис:', thesis)
for a, m in summary.items():
    print(a, {k: [round(x, 4) for x in v] for k, v in m.items()})
