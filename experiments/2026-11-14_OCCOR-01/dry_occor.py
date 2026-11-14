#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""OCCOR-01: сухой прогон цепочки на заглушках (формат answers.json — как у occor_extract.py; задачи — та же раскладка
пилота). Ожидания записаны до запуска:
  clones   — 4 клона повторяют правильность и неверный ответ первого клона с вероятностью 0,85; 7 не-клонов независимы;
             неверные ответы у всех на частых сдвигах → FAM-AGREE лучше AGREE на полном наборе (знает клонов по имени);
             доза LR-AGREE: Δ(4) − Δ(1) < 0 (с клонами есть что выучить). NB-AGREE — без ожидания: первый сухой прогон
             (ошибки равномерные, всё у потолка) дал Δ1 > 0 — NB-AGREE считает голоса клонов за независимые доводы;
  indep    — все 11 голов независимы → |Δ| NB и LR < 0,01; |Δ(4) − Δ(1)| < 0,01 у обоих;
  fail     — у трёх клонов почти нет ошибок → проверка постановки не пройдена (клонов < 3), разбор останавливается.
Бутстреп в сухом прогоне — 60 повторов (логика та же)."""
import json
import os
import subprocess
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
DRY = os.path.join(HERE, 'dry')
NAMES = [('pythia-1.4b', 'main'), ('pythia-1.4b-deduped', 'main'), ('pythia-2.8b', 'main'), ('pythia-2.8b', 'step133000'),
         ('pythia-2.8b', 'step123000'), ('pythia-2.8b', 'step113000'), ('pythia-2.8b-deduped', 'main'), ('pythia-6.9b', 'main'),
         ('pythia-6.9b-deduped', 'main'), ('opt-2.7b', 'main'), ('gpt-neo-2.7B', 'main')]


def problems():
    g = np.random.default_rng(7_300_000)
    ex = []
    while len(ex) < 4:
        a, b = int(g.integers(100, 200)), int(g.integers(10, 100))
        if (a + b < 200) == (len(ex) < 2) and (a, b) not in ex:
            ex.append((a, b))
    pairs = [(a, b) for a in range(100, 200) for b in range(10, 100) if (a, b) not in set(ex)]
    perm = np.random.default_rng(7_310_000).permutation(len(pairs))
    part = sorted(perm[:int(round(0.3 * len(pairs)))])
    P = [dict(id=int(i), a=pairs[i][0], b=pairs[i][1], sum=pairs[i][0] + pairs[i][1]) for i in part]
    for p in P:
        p['range'] = 'ID' if p['sum'] < 200 else 'OOD'
    return P


OFFS = np.array([-10, 10, -1, 1, -20, 20, 0])
OFF_P = np.array([0.3, 0.25, 0.1, 0.1, 0.1, 0.05, 0.1])                          # 0 — «прочий» неверный ответ


def wrong(g, s):
    o = int(g.choice(OFFS, p=OFF_P))
    return int(s + (o if o else int(g.integers(2, 40)) * int(g.choice([-1, 1]))))


def build(out, scen, seed):
    """Неверные ответы сосредоточены на частых сдвигах (−10, +10, ±1, ±20), как в OCGEO-01: независимые головы иногда
    совпадают в ошибке случайно. Клоны (pythia-2.8b, 4 ревизии) в сценарии clones повторяют правильность и неверный
    ответ первого клона с вероятностью 0,85 (на ID и OOD одинаково)."""
    os.makedirs(out, exist_ok=True)
    g = np.random.default_rng(seed)
    P = problems()
    s = np.array([p['sum'] for p in P])
    ood = s >= 200
    heads, first = [], None
    for name, rev in NAMES:
        is_clone = name == 'pythia-2.8b'
        acc = np.where(ood, 0.5, 0.7)
        if scen == 'fail' and is_clone and rev != 'main':
            acc = np.full(len(P), 0.999)
        ok = g.random(len(P)) < acc
        ans = [int(x) if c else wrong(g, x) for x, c in zip(s, ok)]
        if scen == 'clones' and is_clone:
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
    want = {'clones': dict(design_ok=True, fam_neg=True, lr_dose_neg=True),
            'indep': dict(design_ok=True, d1_small=True, lr_small=True, dose_small=True), 'fail': dict(design_ok=False)}
    bad = []
    for k, w in want.items():
        out = os.path.join(DRY, k)
        build(out, k, seed=len(k) * 7)
        r = subprocess.run([sys.executable, os.path.join(HERE, 'pilot_occor.py'), out, '--boot', '60', '--boot-dose', '20'], capture_output=True, text=True)
        if r.returncode:
            print(k, 'ошибка:', r.stderr[-1500:]); bad.append(k); continue
        a = json.load(open(os.path.join(HERE, 'analysis_pilot.json')))
        os.replace(os.path.join(HERE, 'analysis_pilot.json'), os.path.join(DRY, f'{k}_analysis.json'))
        got = dict(design_ok=a['design_ok'])
        if a['design_ok']:
            fd, dc = a['full_delta'], a['dose_contrast']
            d1, d1l = fd['NB-AGREE−AGREE']['point'], fd['LR-AGREE−AGREE']['point']
            fam = a['full']['FAM-AGREE']['ioi'] - a['full']['AGREE']['ioi']
            got.update(fam_neg=fam < 0, lr_dose_neg=dc['LR-AGREE']['point'] < 0, d1_small=abs(d1) < 0.01, lr_small=abs(d1l) < 0.01,
                       dose_small=abs(dc['NB-AGREE']['point']) < 0.01 and abs(dc['LR-AGREE']['point']) < 0.01)
            print(k, '| ИОИ', {e: round(v['ioi'], 4) for e, v in a['full'].items()})
            print('   Δ NB %.4f LR %.4f FAM−AGREE %.4f | Δ(4)−Δ(1): NB %.4f LR %.4f' % (d1, d1l, fam, dc['NB-AGREE']['point'], dc['LR-AGREE']['point']))
            print('   доза NB', {kk: round(v['delta_nb_agree'], 4) for kk, v in a['dose'].items()}, 'LR', {kk: round(v['delta_lr_agree'], 4) for kk, v in a['dose'].items()})
        ok = all(got.get(kk) == vv for kk, vv in w.items())
        print(k, '✓' if ok else '✗', {kk: got.get(kk) for kk in w})
        if not ok:
            bad.append(k)
    print('несовпадений:', bad)
    sys.exit(1 if bad else 0)


if __name__ == '__main__':
    main()
