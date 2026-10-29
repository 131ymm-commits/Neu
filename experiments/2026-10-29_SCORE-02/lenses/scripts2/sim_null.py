#!/usr/bin/env python3
"""LENSES-2: доля «подтверждено» у X1oc (agree − single_c < 0) и X1o (agree − single < 0) на заглушке nulldgp.
Каждый повтор: выборка из n задач → суждения score02.judgments → карта огрубления по всей выборке → бутстреп задач (B, мультиномиальные
веса ≡ пересэмпл с возвращением) → 95 % процентильный интервал (края |x| < 1e−12 — ноль) → исход по букве analyze_score02.verdict.
С --refit на первых R_refit повторах считается и вариант, где карта пересчитывается на каждом пересэмпле (B_refit).
  SCORE02_COPY=<копия> python3 sim_null.py <opus|haiku> <s> <n> <R> <зерно> <выход.jsonl> [--refit R_refit B_refit] [ключ=значение …]"""
import json
import os
import sys
import time

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fastlib as F  # noqa: E402
import nulldgp as G  # noqa: E402

a = sys.argv[1:]
model, s, n, R, seed, out = a[0], float(a[1]), int(a[2]), int(a[3]), int(a[4]), a[5]
refit = (int(a[a.index('--refit') + 1]), int(a[a.index('--refit') + 2])) if '--refit' in a else (0, 0)
P = dict(G.OPUS if model == 'opus' else G.HAIKU, s=s)
for kv in a[6:]:
    if '=' in kv:
        k, v = kv.split('=')
        P[k] = float(v)
B = 10000
rng = np.random.default_rng(seed)


def outcome(lo, hi, d=-1):
    if (lo > 0 and d > 0) or (hi < 0 and d < 0):
        return 'подтверждено'
    if (hi < 0 and d > 0) or (lo > 0 and d < 0):
        return 'опровергнуто'
    return 'не показано'


t0 = time.time()
with open(out, 'w') as fh:
    for r in range(R):
        J = G.gen_stage(rng, P, n)
        tasks = sorted(J)
        H = F.prep(J, tasks)
        one = np.ones((1, n))
        pt = {k: float(F.boot_auc(H[k], one)[0]) for k in ('agree', 'single', 'single_c')}
        W = rng.multinomial(n, np.full(n, 1 / n), size=B).astype(float)
        ba = F.boot_auc(H['agree'], W)
        d1 = ba - F.boot_auc(H['single'], W)
        dc = ba - F.boot_auc(H['single_c'], W)
        c1, cc = F.ci95(d1), F.ci95(dc)
        rec = dict(r=r, auc=pt, d1=pt['agree'] - pt['single'], dc=pt['agree'] - pt['single_c'], ci1=c1, cic=cc,
                   x1o=outcome(*c1), x1oc=outcome(*cc), sd1=float(np.nanstd(d1)), sdc=float(np.nanstd(dc)), nlev=len(H['lv']),
                   shares=[float(x) for x in H['single_c'].sum((0, 2)) / H['single_c'].sum()])
        if r < refit[0]:
            Wr = W[:refit[1]]
            dcr = F.boot_auc(H['agree'], Wr) - F.refit_single_c(J, tasks, Wr)
            dcf = F.boot_auc(H['agree'], Wr) - F.boot_auc(H['single_c'], Wr)
            rec.update(cic_refit=F.ci95(dcr), cic_fixedB=F.ci95(dcf), x1oc_refit=outcome(*F.ci95(dcr)), x1oc_fixedB=outcome(*F.ci95(dcf)),
                       sdc_refit=float(np.nanstd(dcr)), sdc_fixedB=float(np.nanstd(dcf)))
        fh.write(json.dumps(rec, ensure_ascii=False) + '\n')
print(f'{model} s = {s} n = {n}: повторов {R}, {time.time() - t0:.0f} с')
