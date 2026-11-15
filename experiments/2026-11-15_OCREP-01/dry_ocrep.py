#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""OCREP-01: сухой прогон цепочки на заглушках (формат answers.json — как у ocrep_extract.py; задачи — раскладка пилота
OCREP-01). Ожидания записаны до запуска:
  clones — как заглушка clones OCCOR-01: 4 ревизии pythia-2.8b повторяют первого клона (правильность и неверный ответ) с
           вероятностью 0,85; неверные ответы на частых сдвигах. Ожидания: R1 < 0 и R2 < 0 (точки);
  indep  — головы независимы. Ожидания: |R1| < 0,03 и |R2| < 0,03 (в OCMIX-01 на такой заглушке LR-AGREE был хуже AGREE
           на 0,0235 — граница взята с запасом);
  fail   — у пяти голов почти нет ошибок → проверку метода проходят 4 из 9 (< 6) → разбор останавливается.
Бутстреп — 60 повторов. Настоящий analysis_pilot.json, если он есть, сохраняется и возвращается на место."""
import json
import os
import shutil
import subprocess
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
DRY = os.path.join(HERE, 'dry')
NAMES = [('pythia-1.4b', 'main'), ('pythia-1.4b-deduped', 'main'), ('pythia-2.8b', 'main'), ('pythia-2.8b', 'step133000'),
         ('pythia-2.8b', 'step123000'), ('pythia-2.8b', 'step113000'), ('pythia-2.8b-deduped', 'main'), ('pythia-6.9b', 'main'),
         ('pythia-6.9b-deduped', 'main')]
OFFS = np.array([-10, 10, -1, 1, -20, 20, 0])
OFF_P = np.array([0.3, 0.25, 0.1, 0.1, 0.1, 0.05, 0.1])


def problems():
    g = np.random.default_rng(7_500_000)
    ex = []
    while len(ex) < 4:
        a, b = int(g.integers(300, 400)), int(g.integers(10, 100))
        if (a + b < 400) == (len(ex) < 2) and (a, b) not in ex:
            ex.append((a, b))
    pairs = [(a, b) for a in range(300, 400) for b in range(10, 100) if (a, b) not in set(ex)]
    perm = np.random.default_rng(7_510_000).permutation(len(pairs))
    part = sorted(perm[:int(round(0.3 * len(pairs)))])
    P = [dict(id=int(i), a=pairs[i][0], b=pairs[i][1], sum=pairs[i][0] + pairs[i][1]) for i in part]
    for p in P:
        p['range'] = 'ID' if p['sum'] < 400 else 'OOD'
    return P


def wrong(g, s):
    o = int(g.choice(OFFS, p=OFF_P))
    return int(s + (o if o else int(g.integers(2, 40)) * int(g.choice([-1, 1]))))


def build(out, scen, seed):
    os.makedirs(out, exist_ok=True)
    g = np.random.default_rng(seed)
    P = problems()
    s = np.array([p['sum'] for p in P])
    ood = s >= 400
    heads, first = [], None
    for k, (name, rev) in enumerate(NAMES):
        acc = np.where(ood, 0.5, 0.7)
        if scen == 'fail' and k < 5:
            acc = np.full(len(P), 0.999)
        ok = g.random(len(P)) < acc
        ans = [int(x) if c else wrong(g, x) for x, c in zip(s, ok)]
        if scen == 'clones' and name == 'pythia-2.8b':
            if first is None:
                first = (ok.copy(), list(ans))
            else:
                cp = g.random(len(P)) < 0.85
                ok = np.where(cp, first[0], ok)
                ans = [first[1][j] if cp[j] else (int(s[j]) if ok[j] else wrong(g, s[j])) for j in range(len(P))]
        rows = [dict(answer=a, correct=a == int(x), text=str(a), logp=float(-0.2 - 1.5 * (a != x) * g.random() - 0.5 * g.random()), n_tok=1)
                for a, x in zip(ans, s)]
        heads.append(dict(model=name, repo=f'stub/{name}', revision=rev, accuracy={}, seconds=0.0, rows=rows))
    json.dump(dict(info={}, split='dry', task={}, prompt_head='', problems=P, heads=heads), open(os.path.join(out, 'answers.json'), 'w'))


def main():
    real = os.path.join(HERE, 'analysis_pilot.json')
    keep = real + '.real'
    if os.path.exists(real):
        shutil.copy(real, keep)
    want = {'clones': dict(design_ok=True, r1_neg=True, r2_neg=True), 'indep': dict(design_ok=True, r1_small=True, r2_small=True),
            'fail': dict(design_ok=False)}
    bad = []
    try:
        for k, w in want.items():
            out = os.path.join(DRY, k)
            build(out, k, seed=len(k) * 13)
            r = subprocess.run([sys.executable, os.path.join(HERE, 'pilot_ocrep.py'), out, '--boot', '60'], capture_output=True, text=True)
            if r.returncode:
                print(k, 'ошибка:', r.stderr[-1500:]); bad.append(k); continue
            a = json.load(open(real))
            os.replace(real, os.path.join(DRY, f'{k}_analysis.json'))
            got = dict(design_ok=a['design_ok'])
            if a['design_ok']:
                dl = a['deltas']
                got.update(r1_neg=dl['R1']['point'] < 0, r2_neg=dl['R2']['point'] < 0, r1_small=abs(dl['R1']['point']) < 0.03,
                           r2_small=abs(dl['R2']['point']) < 0.03)
                print(k, '| ИОИ', {e: round(v['ioi'], 4) for e, v in a['full'].items()}, '| R1 %.4f R2 %.4f R3 %.4f' % (dl['R1']['point'], dl['R2']['point'], dl['R3']['point']))
            ok = all(got.get(kk) == vv for kk, vv in w.items())
            print(k, '✓' if ok else '✗', {kk: got.get(kk) for kk in w})
            if not ok:
                bad.append(k)
    finally:
        if os.path.exists(keep):
            os.replace(keep, real)
    print('несовпадений:', bad)
    sys.exit(1 if bad else 0)


if __name__ == '__main__':
    main()
