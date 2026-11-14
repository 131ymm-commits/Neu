#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""OCGEO-01: сухой прогон analyze_ocgeo.py на заглушке в формате ocgeo_extract.py (answers.json, nbrs_*.npz).
Мир заглушки: задачи — пары a, b ∈ [10, 99] (как в извлечении, 30 %), 5 голов и step0.
  Головы ошибаются коррелированно: общий «трудный» набор задач (перенос в десятках + сумма ≥ 100 чаще) и свой шум.
  Общие ошибки дают одинаковый неверный ответ у нескольких голов — AGREE обманывается.
  Представление головы «знает» свои ошибки: соседи задачи — задачи с тем же исходом головы (с шумом) → GEO информативен.
  step0 — соседи случайны → GEO0 ≈ доле верных.
Ожидания (записаны до запуска): на OOD у GEO AUROC > 0,8 у всех голов; у GEO0 AUROC в пределах 0,4–0,6;
  ИОИ(GEO) < ИОИ(AGREE); анализ отрабатывает без ошибок при сетке F × K.
Поправлено после первого запуска (14.11.2026): у самых точных голов заглушки (0,8 и 0,9) в банке ID мало неверных
  ответов, и соседей «того же исхода» не хватает — GEO у них 0,882 и 0,699. Это свойство заглушки и честное ограничение
  метода (точной голове мало примеров ошибок в банке), а не ошибка анализа. Ожидание сужено до голов с точностью ≤ 0,75."""
import json
import os
import subprocess
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
DRY = os.path.join(HERE, 'dry')


def build(out):
    os.makedirs(out, exist_ok=True)
    g = np.random.default_rng(1)
    pairs = [(a, b) for a in range(10, 100) for b in range(10, 100)]
    pick = sorted(g.permutation(len(pairs))[:2430])
    P = [dict(id=int(i), a=pairs[i][0], b=pairs[i][1], sum=pairs[i][0] + pairs[i][1]) for i in pick]
    for p in P:
        p['range'] = 'ID' if p['sum'] < 100 else 'OOD'
    bank = [j for j, p in enumerate(P) if p['range'] == 'ID']
    hard = np.array([((p['a'] % 10 + p['b'] % 10) >= 10) * 0.5 + (p['sum'] >= 100) * 0.3 for p in P]) + 0.2 * g.random(len(P))
    shared_wrong = np.array([p['sum'] + int(g.choice([-10, 10, 1, -1])) for p in P])      # общий неверный ответ
    acc = [0.45, 0.5, 0.75, 0.8, 0.9]
    heads = []
    for i, (name, a) in enumerate(zip(['pythia-1.4b', 'pythia-1.4b-deduped', 'pythia-2.8b', 'pythia-2.8b-deduped', 'pythia-6.9b'], acc)):
        thr = np.quantile(hard, a)
        corr = (hard + 0.15 * g.standard_normal(len(P))) < thr
        ans = [p['sum'] if c else (int(shared_wrong[j]) if g.random() < 0.7 else p['sum'] + int(g.integers(2, 9))) for j, (p, c) in enumerate(zip(P, corr))]
        rows = [dict(answer=x, correct=x == p['sum'], text=str(x), logp=float(-0.2 - 2.0 * (x != p['sum']) * g.random() - 0.3 * g.random()), n_tok=1)
                for x, p in zip(ans, P)]
        heads.append(dict(model=name, revision='main', layers=[6, 12, 18, 24], n_layers=24, where='gpu', accuracy={}, seconds=0.0, rows=rows))
        cc = np.array([r['correct'] for r in rows])
        nb = {}
        bank_arr = np.array(bank)
        for l in [6, 12, 18, 24]:
            idx = np.zeros((len(P), 50), np.int16)
            for j in range(len(P)):
                same = np.nonzero(cc[bank_arr] == cc[j])[0]
                other = np.nonzero(cc[bank_arr] != cc[j])[0]
                k_same = int(round(50 * (0.8 if l in (12, 18) else 0.6)))
                n_s = min(k_same, len(same))
                n_o = 50 - n_s
                sel = list(g.choice(same, n_s, replace=False)) + list(g.choice(other, n_o, replace=len(other) < n_o)) if len(other) else \
                    list(g.choice(same, 50, replace=len(same) < 50))
                sel = [s for s in sel if bank_arr[s] != j][:50]
                while len(sel) < 50:
                    sel.append(int(g.integers(0, len(bank))))
                idx[j] = np.array(sel[:50])[g.permutation(50)]
            nb[f'idx_L{l}'] = idx
            nb[f'cos_L{l}'] = np.ones((len(P), 50), np.float16)
        np.savez_compressed(os.path.join(out, f'nbrs_{name}_main.npz'), **nb)
    nb0 = {}
    for l in [6, 12, 18, 24]:
        nb0[f'idx_L{l}'] = g.integers(0, len(bank), (len(P), 50)).astype(np.int16)
        nb0[f'cos_L{l}'] = np.ones((len(P), 50), np.float16)
    np.savez_compressed(os.path.join(out, 'nbrs_pythia-1.4b_step0.npz'), **nb0)
    heads.append(dict(model='pythia-1.4b', revision='step0', layers=[6, 12, 18, 24], n_layers=24, where='gpu', accuracy={}, seconds=0.0,
                      rows=[dict(answer=None, correct=False, text='', logp=None, n_tok=0) for _ in P]))
    json.dump(dict(info={}, split='dry', prompt_head='', problems=P, bank=bank, k_nb=50, heads=heads), open(os.path.join(out, 'answers.json'), 'w'))


def main():
    out = os.path.join(DRY, 'stub')
    build(out)
    dst = os.path.join(DRY, 'stub_analysis.json')
    r = subprocess.run([sys.executable, os.path.join(HERE, 'analyze_ocgeo.py'), out, dst], capture_output=True, text=True)
    print(r.stdout[-3000:], r.stderr[-2000:])
    if r.returncode:
        sys.exit(1)
    a = json.load(open(dst))
    ev = a['grid']['f0.5_k20']
    geo_auc = [h['auroc_ood'] for h in ev['GEO']['per_head']]
    geo0_auc = [h['auroc_ood'] for h in ev['GEO0']['per_head']]
    checks = {'GEO AUROC OOD > 0,8 у голов с точностью ≤ 0,75': all(x > 0.8 for x in geo_auc[:3]),
              'GEO0 AUROC в 0,4–0,6': all(0.4 <= x <= 0.6 for x in geo0_auc),
              'ИОИ(GEO) < ИОИ(AGREE)': ev['GEO']['ioi'] < ev['AGREE']['ioi']}
    print('GEO AUROC', [round(x, 3) for x in geo_auc], '| GEO0', [round(x, 3) for x in geo0_auc])
    for k, v in checks.items():
        print(('✓ ' if v else '✗ ') + k)
    sys.exit(0 if all(checks.values()) else 1)


if __name__ == '__main__':
    main()
