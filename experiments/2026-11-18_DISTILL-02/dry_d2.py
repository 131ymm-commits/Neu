#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""DISTILL-02: сухой прогон анализа теста на заглушках (совет 74, п. 10) — те же размеры, что в тесте: построение «тысяч» — 5 сред × 2200
(как тест OCDIV-03) + 8 × 600 (пилот OCDIV-04) + 8 × 2200 (тест OCDIV-04), «длины» — 3 × 600 + 3 × 2200; тест — 11 сред test5 и 4 среды
new5 по 2200 задач (задачи — из `distill02_extract.envs_d2`, тем же кодом, что извлечение); 7 голов-заглушек — программы с разными
признаками, долями «прочих» ошибок и «без числа». Ответы голов — только заглушки: настоящих ответов здесь нет.
  python3 dry_d2.py make DIR              — пишет сборки DIR/c_T_o3, c_T_p3, c_T_t3, c_L_p3, c_L_t3, t_T_5, t_L_5, t_T_n, t_L_n и DIR/spec_*.json
  python3 dry_d2.py run OUT.json SPEC.json — анализ теста (`distill02.test_d2`) на заглушках; константы PREREG ещё не заданы, поэтому
                                            здесь все правила условно активны — только для времени, памяти и детерминизма"""
import json
import os
import sys

import numpy as np

X_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, X_DIR)
import distill02 as D  # noqa: E402
import distill02_extract as XD  # noqa: E402

HEADS = [dict(features=f, w=w, w_round=w, eps=e, none=nr) for f, w, e, nr in (
    (['top', 'prop'], [-2.5, 2.0, 1.5], 0.05, 0.01), (['pos', 'chain'], [-3.0, 0.6, 0.4], 0.08, 0.02),
    (['phi', 'top'], [-1.5, -4.0, 1.0], 0.12, 0.01), (['newplace', 'prop', 'c1'], [-2.8, 1.2, 1.0, 0.5], 0.04, 0.03),
    (['nines', 'ood'], [-3.2, 0.3, 1.1], 0.15, 0.01), (['top'], [-2.0, 1.4], 0.20, 0.02), (['chain', 'phi', 'pos'], [-2.2, 0.5, -2.0, 0.2], 0.10, 0.01))]


def other_offset(it, g):
    """«Прочая» ошибка заглушки: цифра d·10^k со знаком (тяжёлый хвост), иногда — выпавшая старшая цифра или случайное число."""
    u = g.random()
    if u < 0.75:
        k = int(min(g.geometric(0.45) - 1, len(str(it['sum'])) - 1))
        return int((1 if g.random() < 0.5 else -1) * int(g.integers(1, 10)) * 10 ** k)
    if u < 0.9:
        s = str(it['sum'])
        return int(s[1:] or '0') - it['sum']
    return int(g.integers(10 ** max(len(str(it['sum'])) - 2, 0), 10 ** len(str(it['sum'])))) - it['sum']


def answers(items, h, g):
    out = []
    for it in items:
        if g.random() < h['none']:
            out.append(None)
            continue
        if g.random() < h['eps']:
            y = it['sum'] + other_offset(it, g)
            out.append(y if y >= 0 else None)
            continue
        off = 0
        for r in D.position_features(it['a'], it['b'], it['ood']):
            if g.random() < D.p_drop(h, r):
                off -= 10 ** r['j']
        out.append(it['sum'] + off)
    return out


def items_of(X, n, g):
    out = []
    for _ in range(n):
        a, b = int(100 * X + g.integers(0, 100)), int(g.integers(10, 100))
        out.append(dict(a=a, b=b, sum=a + b, range='ID' if a + b < 100 * (X + 1) else 'OOD'))
    return out


def write(path, envs, seed):
    os.makedirs(path, exist_ok=True)
    g = np.random.default_rng(seed)
    hs = []
    for k, h in enumerate(HEADS):
        cols = {}
        for e in envs:
            its = [dict(a=p['a'], b=p['b'], sum=p['sum'], ood=int(p['range'] != 'ID')) for p in e['problems']]
            ans = answers(its, h, g)
            cols[e['name']] = dict(answer=ans, correct=[int(x is not None and x == it['sum']) for x, it in zip(ans, its)],
                                   logp=[float(-0.5 if x == it['sum'] else -2.5) + float(g.normal(0, 0.3)) for x, it in zip(ans, its)],
                                   n_tok=[len(str(it['sum'])) for it in its])
        hs.append(dict(model=f'stub/head{k}', revision='0' * 40, cols=cols))
    json.dump(dict(envs=envs, heads=hs), open(os.path.join(path, 'answers.json'), 'w', encoding='utf-8'), ensure_ascii=False)


def env_stub(fam, X, n, g, p=3):
    code = 'T' if fam == 'thousands' else 'L'
    return dict(name=f'{code}_X{X}_p{p}', family=fam, X=X, p=p, bound=100 * (X + 1), max_new=6 if fam == 'thousands' else 10,
                problems=items_of(X, n, g))


def env_real(e):
    return dict(name=e['name'], family=e['family'], X=e['X'], p=e['p'], bound=e['bound'], max_new=e['max_new'],
                problems=[dict(a=q['a'], b=q['b'], sum=q['sum'], range=q['range']) for q in e['problems']])


def main(dst):
    g = np.random.default_rng(9_940_000)
    T8, L3 = (19, 29, 39, 49, 59, 69, 79, 89), (9, 99, 999)
    write(os.path.join(dst, 'c_T_o3'), [env_stub('thousands', X, 2200, g) for X in (19, 29, 39, 49, 59)], 1)
    write(os.path.join(dst, 'c_T_p3'), [env_stub('thousands', X, 600, g) for X in T8], 2)
    write(os.path.join(dst, 'c_T_t3'), [env_stub('thousands', X, 2200, g) for X in T8], 3)
    write(os.path.join(dst, 'c_L_p3'), [env_stub('length', X, 600, g) for X in L3], 4)
    write(os.path.join(dst, 'c_L_t3'), [env_stub('length', X, 2200, g) for X in L3], 5)
    t5, n5 = XD.envs_d2('test5'), XD.envs_d2('new5')
    write(os.path.join(dst, 't_T_5'), [env_real(e) for e in t5 if e['family'] == 'thousands'], 6)
    write(os.path.join(dst, 't_L_5'), [env_real(e) for e in t5 if e['family'] == 'length'], 7)
    write(os.path.join(dst, 't_T_n'), [env_real(e) for e in n5 if e['family'] == 'thousands'], 8)
    write(os.path.join(dst, 't_L_n'), [env_real(e) for e in n5 if e['family'] == 'length'], 9)
    cons = {'thousands': [os.path.join(dst, x) for x in ('c_T_o3', 'c_T_p3', 'c_T_t3')], 'length': [os.path.join(dst, x) for x in ('c_L_p3', 'c_L_t3')]}
    test = {'test5': [os.path.join(dst, 't_T_5'), os.path.join(dst, 't_L_5')], 'new5': [os.path.join(dst, 't_T_n'), os.path.join(dst, 't_L_n')]}
    json.dump(dict(construction=cons, test=test, B=4000, R=20, workers=4, part_dir=os.path.join(dst, 'envs')),
              open(os.path.join(dst, 'spec_main.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    for k in (1, 2):
        json.dump(dict(construction=cons, test=test, B=200, R=20, only=['T_X19_p3', 'L_X9_p3'], no_time=True),
                  open(os.path.join(dst, f'spec_det{k}.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print('заглушки DISTILL-02 записаны:', dst, flush=True)


def run(dst, spec_path):
    spec = json.load(open(spec_path, encoding='utf-8'))
    D.RULES_ACTIVE = {r: True for r in D.RULES}                  # только сухой прогон: вердикты заглушек ничего не значат
    D.test_d2(dst, spec['construction'], spec['test'], B=spec['B'], R=spec['R'], part_dir=spec.get('part_dir'), only=spec.get('only'),
              no_time=spec.get('no_time', False), workers=spec.get('workers', 1))


if __name__ == '__main__':
    if sys.argv[1:2] == ['make']:
        main(sys.argv[2])
    elif sys.argv[1:2] == ['run']:
        run(sys.argv[2], sys.argv[3])
    else:
        raise SystemExit(__doc__)
