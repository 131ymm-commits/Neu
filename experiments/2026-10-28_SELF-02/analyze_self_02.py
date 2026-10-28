#!/usr/bin/env python3
"""SELF-02: вердикты по букве PREREG-SELF-02.md §4 из results_self_02.json → analysis_self_02.json."""
import json
import os
import sys

import numpy as np
from scipy.stats import spearmanr

HERE = os.path.dirname(os.path.abspath(__file__))
src = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, 'results_self_02.json')
d = json.load(open(src))
A, B = d['A'], d['B']
S, T, O, OT, OB = range(5)


def a_rows(q):
    return sorted([r for r in A if r['q'] == q], key=lambda r: r['seed'])


def b_rows(q, arm):
    return sorted([r for r in B if r['q'] == q and r['arm'] == arm], key=lambda r: r['seed'])


def med(x):
    return float(np.median(x))


def boot_med(x, Bn=10000, seed=0):
    x = np.asarray(x, float); g = np.random.default_rng(seed)
    m = np.median(x[g.integers(0, len(x), (Bn, len(x)))], 1)
    return [float(np.median(x)), float(np.quantile(m, 0.025)), float(np.quantile(m, 0.975))]


V = {}
m1 = np.mean([r['mlp'] for r in a_rows(1.0)], 0)
V['R1'] = dict(ok=bool(m1[S] >= 0.80 and m1[O] <= 0.20), self=float(m1[S]), other=float(m1[O]))
w0 = sum(r['mlp'][S] > r['mlp'][O] for r in a_rows(0.0)); w1 = sum(r['mlp'][S] > r['mlp'][O] for r in a_rows(1.0))
V['R2'] = dict(ok=bool(2 <= w0 <= 8 and w1 >= 9), wins_q0=int(w0), wins_q1=int(w1))
w5 = sum(r['mlp'][S] > r['mlp'][O] for r in a_rows(0.5))
V['R3'] = dict(ok=bool(w5 >= 8), wins=int(w5))
V['R4'] = dict(ok=bool(m1[T] >= 0.70 and m1[OT] <= 0.20), tool=float(m1[T]), other_tool=float(m1[OT]))
mo = np.mean([r['ood'] for r in a_rows(1.0)], 0); wo = sum(r['ood'][S] > r['ood'][O] for r in a_rows(1.0))
V['R5'] = dict(ok=bool(mo[S] >= 0.80 and wo >= 9), self_ood=float(mo[S]), other_ood=float(mo[O]), wins=int(wo))
sums = [r['mlp'][S] + r['mlp'][O] for r in a_rows(0.0)]
shares = [r['mlp'][S] / (r['mlp'][S] + r['mlp'][O]) for r in a_rows(0.0)]
V['R6'] = dict(ok=bool(sum(0.75 <= x <= 0.95 for x in sums) >= 9 and sum(0.2 <= x <= 0.8 for x in shares) >= 7),
               n_sum=int(sum(0.75 <= x <= 0.95 for x in sums)), n_share=int(sum(0.2 <= x <= 0.8 for x in shares)),
               sums=[round(x, 3) for x in sums], shares=[round(x, 3) for x in shares])
V['same_as_s1'] = all(r['same_as_s1'] for r in A)


def rho(r, i):
    th = r['t_half']; return th[i] / th[S]


def first(r):           # +1: SELF раньше OTHER, −1: позже, 0: одновременно
    th = r['t_half']; return int(np.sign(th[O] - th[S]))


rs = b_rows(1.0, 'lin2_small')
V['P1'] = dict(ok=bool(sum(first(r) == 1 for r in rs) >= 9 and 1.10 <= med([rho(r, O) for r in rs]) <= 1.30),
               self_first=int(sum(first(r) == 1 for r in rs)), rho=boot_med([rho(r, O) for r in rs]))
V['P2'] = dict(ok=bool(sum(r['t_half'][OB] > r['t_half'][O] for r in rs) >= 9 and 1.30 <= med([rho(r, OB) for r in rs]) <= 1.70),
               object_last=int(sum(r['t_half'][OB] > r['t_half'][O] for r in rs)), rho=boot_med([rho(r, OB) for r in rs]))
r0 = b_rows(0.0, 'lin2_small')
V['P3'] = dict(ok=bool(sum(first(r) == 1 for r in r0) < 9 and sum(first(r) == -1 for r in r0) < 9
                       and 0.95 <= med([rho(r, O) for r in r0]) <= 1.05),
               self_first=int(sum(first(r) == 1 for r in r0)), other_first=int(sum(first(r) == -1 for r in r0)),
               rho=boot_med([rho(r, O) for r in r0]))
r5 = b_rows(0.5, 'lin2_small')
m0, m5, m1_ = med([rho(r, O) for r in r0]), med([rho(r, O) for r in r5]), med([rho(r, O) for r in rs])
paired = sum(rho(a, O) < rho(b, O) for a, b in zip(r5, rs))
V['P4'] = dict(ok=bool(m0 < m5 < m1_ and paired >= 8), med_q0=m0, med_q05=m5, med_q1=m1_, paired=int(paired))
rt = b_rows(1.0, 'tanh2_small')
V['P5'] = dict(ok=bool(sum(first(r) == 1 for r in rt) >= 9 and med([rho(r, O) for r in rt]) >= 1.10),
               self_first=int(sum(first(r) == 1 for r in rt)), rho=boot_med([rho(r, O) for r in rt]))
rich = [r for q in (0.5, 1.0) for r in b_rows(q, 'lin2_small')]
ratio = [rho(r, O) / r['rho_theory_other'] for r in rich]
allr = [r for q in (0.0, 0.5, 1.0) for r in b_rows(q, 'lin2_small')]
sp_rich = float(spearmanr([rho(r, O) for r in allr], [r['rho_theory_other'] for r in allr]).correlation)
V['P6'] = dict(ok=bool(0.90 <= med(ratio) <= 1.05 and sp_rich >= 0.8), ratio=boot_med(ratio), spearman=sp_rich,
               ratio_object=boot_med([rho(r, OB) / r['rho_theory_object'] for r in rich]))
lz = [r for q in (0.0, 0.5, 1.0) for r in b_rows(q, 'lin2_lazy')]
sp_lazy = float(spearmanr([rho(r, O) for r in lz], [r['rho_theory_other'] for r in lz]).correlation)
lz1 = b_rows(1.0, 'lin2_lazy')
V['P7'] = dict(ok=bool(sp_lazy < 0.5 and sum(first(r) == 1 for r in lz1) <= 8), spearman=sp_lazy,
               self_first_q1=int(sum(first(r) == 1 for r in lz1)), rho_q1=boot_med([rho(r, O) for r in lz1]))
l1 = [r for r in B if r['arm'] == 'lin1']
V['P8'] = dict(ok=bool(all(len(set(r['t_half'])) == 1 for r in l1)), n=len(l1),
               n_equal=int(sum(len(set(r['t_half'])) == 1 for r in l1)))
out = dict(verdicts=V, t_half={f"{r['arm']}_q{r['q']}_s{r['seed']}": r['t_half'] for r in B},
           rho_theory={f"q{r['q']}_s{r['seed']}": [r['rho_theory_other'], r['rho_theory_object']] for r in B if r['arm'] == 'lin2_small'},
           part_A_means={str(q): np.mean([r['mlp'] for r in a_rows(q)], 0).round(4).tolist() for q in (0.0, 0.5, 1.0)},
           part_A_ood_q1=mo.round(4).tolist())
json.dump(out, open(os.path.join(os.path.dirname(os.path.abspath(src)), 'analysis_self_02.json'), 'w'), ensure_ascii=False, indent=1)
for k, v in V.items():
    print(k, v if isinstance(v, bool) else ('✓' if v['ok'] else '✗', {kk: vv for kk, vv in v.items() if kk != 'ok'}))
