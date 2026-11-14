#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""OCMIX-01: сухой прогон цепочки на заглушках (формат answers.json — как у ocmix_extract.py; задачи — та же раскладка
пилота). Ожидания записаны до запуска:
  mix    — 9 голов (имена как у настоящих); точность 0,7 на ID и 0,5 на OOD; клоны (4 ревизии pythia-2.8b) повторяют
           первого клона с вероятностью 0,85. «Ошибка переноса»: на задаче с вероятностью 0,25 на OOD и 0,03 на ID каждая
           голова с вероятностью 0,6 отвечает sum − 100 (общая неверная, умеренно уверенная). 10 % прочих неверных ответов —
           уверенные одиночные. Ожидания: H1 < 0 (верхушка VETO честнее, чем у LR-AGREE); H2 < 0 (VETO лучше CONF);
  indep  — головы независимы, общих ошибок переноса и уверенных одиночных ответов нет. Ожидания: |H1| < 0,03, |H3| < 0,02;
  fail   — у пяти голов почти нет ошибок → проверку метода проходят 4 головы из 9 (< 6) → разбор останавливается.
Бутстреп в сухом прогоне — 60 повторов (логика та же). Настоящий analysis_pilot.json, если он есть, сохраняется и
возвращается на место."""
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


def problems():
    g = np.random.default_rng(7_400_000)
    ex = []
    while len(ex) < 4:
        a, b = int(g.integers(200, 300)), int(g.integers(10, 100))
        if (a + b < 300) == (len(ex) < 2) and (a, b) not in ex:
            ex.append((a, b))
    pairs = [(a, b) for a in range(200, 300) for b in range(10, 100) if (a, b) not in set(ex)]
    perm = np.random.default_rng(7_410_000).permutation(len(pairs))
    part = sorted(perm[:int(round(0.3 * len(pairs)))])
    P = [dict(id=int(i), a=pairs[i][0], b=pairs[i][1], sum=pairs[i][0] + pairs[i][1]) for i in part]
    for p in P:
        p['range'] = 'ID' if p['sum'] < 300 else 'OOD'
    return P


def build(out, scen, seed):
    os.makedirs(out, exist_ok=True)
    g = np.random.default_rng(seed)
    P = problems()
    s = np.array([p['sum'] for p in P])
    ood = s >= 300
    carry = g.random(len(P)) < np.where(ood, 0.25, 0.03) if scen == 'mix' else np.zeros(len(P), bool)
    heads, first = [], None
    for k, (name, rev) in enumerate(NAMES):
        acc = np.where(ood, 0.5, 0.7)
        if scen == 'fail' and k < 5:
            acc = np.full(len(P), 0.999)
        ok = g.random(len(P)) < acc
        ans = np.where(ok, s, s + g.integers(1, 60, len(P)) * g.choice([-1, 1], len(P)))
        lp = np.where(ok, -0.2 - 0.5 * g.random(len(P)), -1.5 - 2.0 * g.random(len(P)))
        if scen == 'mix':
            lone = (~ok) & (g.random(len(P)) < 0.1)
            lp = np.where(lone, -0.1 * g.random(len(P)), lp)
            cw = carry & (g.random(len(P)) < 0.6)
            ans = np.where(cw, s - 100, ans)
            lp = np.where(cw, -1.0 - 1.0 * g.random(len(P)), lp)
            if name == 'pythia-2.8b':
                if first is None:
                    first = (ans.copy(), lp.copy())
                else:
                    cp = g.random(len(P)) < 0.85
                    ans = np.where(cp, first[0], ans)
                    lp = np.where(cp, first[1] + 0.05 * g.standard_normal(len(P)), lp)
        rows = [dict(answer=int(a), correct=bool(a == x), text=str(int(a)), logp=float(l), n_tok=1) for a, x, l in zip(ans, s, lp)]
        heads.append(dict(model=name, repo=f'stub/{name}', revision=rev, accuracy={}, seconds=0.0, rows=rows))
    json.dump(dict(info={}, split='dry', task={}, prompt_head='', problems=P, heads=heads), open(os.path.join(out, 'answers.json'), 'w'))


def main():
    real = os.path.join(HERE, 'analysis_pilot.json')
    keep = real + '.real'
    if os.path.exists(real):
        shutil.copy(real, keep)
    want = {'mix': dict(design_ok=True, h1_neg=True, h2_neg=True), 'indep': dict(design_ok=True, h1_small=True, h3_small=True),
            'fail': dict(design_ok=False)}
    bad = []
    try:
        for k, w in want.items():
            out = os.path.join(DRY, k)
            build(out, k, seed=len(k) * 11)
            r = subprocess.run([sys.executable, os.path.join(HERE, 'pilot_ocmix.py'), out, '--boot', '60'], capture_output=True, text=True)
            if r.returncode:
                print(k, 'ошибка:', r.stderr[-1500:]); bad.append(k); continue
            a = json.load(open(real))
            os.replace(real, os.path.join(DRY, f'{k}_analysis.json'))
            got = dict(design_ok=a['design_ok'])
            if a['design_ok']:
                dl = a['deltas']
                got.update(h1_neg=dl['H1']['point'] < 0, h2_neg=dl['H2']['point'] < 0, h1_small=abs(dl['H1']['point']) < 0.03,
                           h3_small=abs(dl['H3']['point']) < 0.02)
                print(k, '| ИОИ', {e: round(v['ioi'], 4) for e, v in a['full'].items()})
                print('   верхушка', {e: round(v['top10_sel']['deception'], 4) for e, v in a['full'].items()},
                      '| H1 %.4f H2 %.4f H3 %.4f' % (dl['H1']['point'], dl['H2']['point'], dl['H3']['point']))
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
