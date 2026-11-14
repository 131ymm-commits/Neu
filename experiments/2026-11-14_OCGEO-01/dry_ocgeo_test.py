#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""OCGEO-01: сухой прогон правил теста (analyze_ocgeo_test.py) на заглушках. Ожидания записаны до запуска.
Заглушка — как dry_ocgeo.build, но с параметрами: точности голов, доля общих неверных ответов, информативность соседей.
  geo_wins    — точности 0,45–0,65; 70 % неверных ответов общие (AGREE обманывается); соседи «того же исхода» 80 % →
                P1 «подтверждено», P3 «подтверждено», проверка метода пройдена;
  agree_wins  — те же точности; общих неверных ответов нет (AGREE надёжен); соседи случайные (как у step0) →
                P1 «опровергнуто», P3 «не решено», проверка метода пройдена;
  method_fail — головы с точностью до 0,95 (в ID меньше 20 неверных) → P1 и P3 «не определено (проверка метода)».
После совета 52 правило P2 стало описательным; бутстреп в сухом прогоне — 300 повторов (логика правил та же)."""
import json
import os
import subprocess
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
DRY = os.path.join(HERE, 'dry')
NAMES = ['pythia-1.4b', 'pythia-1.4b-deduped', 'pythia-2.8b', 'pythia-2.8b-deduped', 'pythia-6.9b']


def build(out, acc, shared, informative, seed):
    os.makedirs(out, exist_ok=True)
    g = np.random.default_rng(seed)
    pairs = [(a, b) for a in range(10, 100) for b in range(10, 100)]
    pick = sorted(g.permutation(len(pairs))[:2430])
    P = [dict(id=int(i), a=pairs[i][0], b=pairs[i][1], sum=pairs[i][0] + pairs[i][1]) for i in pick]
    for p in P:
        p['range'] = 'ID' if p['sum'] < 100 else 'OOD'
    bank = np.array([j for j, p in enumerate(P) if p['range'] == 'ID'])
    hard = np.array([((p['a'] % 10 + p['b'] % 10) >= 10) * 0.5 + (p['sum'] >= 100) * 0.3 for p in P]) + 0.2 * g.random(len(P))
    shared_wrong = np.array([p['sum'] + int(g.choice([-10, 10, 1, -1])) for p in P])
    heads = []
    for name, a in zip(NAMES, acc):
        cc = (hard + 0.15 * g.standard_normal(len(P))) < np.quantile(hard, a)
        ans = [p['sum'] if c else (int(shared_wrong[j]) if g.random() < shared else p['sum'] + int(g.integers(2, 60)))
               for j, (p, c) in enumerate(zip(P, cc))]
        rows = [dict(answer=x, correct=x == p['sum'], text=str(x), logp=float(-0.3 - 1.0 * (x != p['sum']) * g.random() - 0.6 * g.random()), n_tok=1)
                for x, p in zip(ans, P)]
        heads.append(dict(model=name, revision='main', layers=[6, 12, 18, 24], n_layers=24, rows=rows))
        cc = np.array([r['correct'] for r in rows])
        nb = {}
        for l in [6, 12, 18, 24]:
            idx = np.zeros((len(P), 50), np.int16)
            for j in range(len(P)):
                if informative:
                    same, other = np.nonzero(cc[bank] == cc[j])[0], np.nonzero(cc[bank] != cc[j])[0]
                    n_s = min(40, len(same))
                    sel = list(g.choice(same, n_s, replace=False)) + list(g.choice(other, 50 - n_s, replace=len(other) < 50 - n_s))
                else:
                    sel = list(g.integers(0, len(bank), 50))
                idx[j] = np.array(sel[:50])
            nb[f'idx_L{l}'] = idx
            nb[f'cos_L{l}'] = np.ones((len(P), 50), np.float16)
        np.savez_compressed(os.path.join(out, f'nbrs_{name}_main.npz'), **nb)
    nb0 = {f'idx_L{l}': g.integers(0, len(bank), (len(P), 50)).astype(np.int16) for l in [6, 12, 18, 24]}
    nb0.update({f'cos_L{l}': np.ones((len(P), 50), np.float16) for l in [6, 12, 18, 24]})
    np.savez_compressed(os.path.join(out, 'nbrs_pythia-1.4b_step0.npz'), **nb0)
    heads.append(dict(model='pythia-1.4b', revision='step0', layers=[6, 12, 18, 24], n_layers=24,
                      rows=[dict(answer=None, correct=False, text='', logp=None, n_tok=0) for _ in P]))
    json.dump(dict(info={}, split='dry', prompt_head='', problems=P, bank=bank.tolist(), k_nb=50, heads=heads),
              open(os.path.join(out, 'answers.json'), 'w'))


def main():
    U = 'не определено (проверка метода)'
    sc = {'geo_wins': ([0.45, 0.5, 0.55, 0.6, 0.65], 0.7, True, {'P1': 'подтверждено', 'P3': 'подтверждено'}, True),
          'agree_wins': ([0.45, 0.5, 0.55, 0.6, 0.65], 0.0, False, {'P1': 'опровергнуто', 'P3': 'не решено'}, True),
          'method_fail': ([0.6, 0.7, 0.8, 0.9, 0.95], 0.3, True, {'P1': U, 'P3': U}, False)}
    bad = []
    for k, (acc, shared, inf, want, method) in sc.items():
        out = os.path.join(DRY, f'test_{k}')
        build(out, acc, shared, inf, seed=len(k))
        dst = os.path.join(DRY, f'test_{k}_an.json')
        r = subprocess.run([sys.executable, os.path.join(HERE, 'analyze_ocgeo_test.py'), out, dst, '--boot', '300'], capture_output=True, text=True)
        if r.returncode:
            print(k, 'ошибка:', r.stderr[-1500:]); bad.append(k); continue
        a = json.load(open(dst))
        got = {p: a['verdicts'][p] for p in want}
        ok = got == want and a['method']['ok'] == method
        print(k, '✓' if ok else '✗', got, '| метод', a['method']['ok'], '| Δ1 %.3f Δ3 %s' % (a['P1']['delta'], a['P3']['delta']))
        if not ok:
            bad.append(k)
    json.dump({'bad': bad}, open(os.path.join(DRY, 'dry_test_summary.json'), 'w'))
    print('несовпадений:', bad)
    sys.exit(1 if bad else 0)


if __name__ == '__main__':
    main()
