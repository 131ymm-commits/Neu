#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""DISTILL-02: проверки кода на заглушках (без настоящих ответов голов). Ожидания — из построения миров (ERRORS № 181, 204).
  python3 test_distill02.py        печатает ✓/✗ по каждой проверке и «провалов: N»"""
import json
import math
import os
import sys
import tempfile

import numpy as np

X_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, X_DIR)
import distill02 as D  # noqa: E402

fails = []


def check(name, ok, info=''):
    print(('✓ ' if ok else '✗ ') + name + ('' if ok else f'  [{info}]'), flush=True)
    if not ok:
        fails.append(name)


rng = np.random.default_rng(1)

# 1. Переносы: тот же узор, что ocdiv4.kappa; ⌊Φ_j⌋ — перенос в разряд j (второй способ правды)
ok_k, ok_phi = True, True
for _ in range(3000):
    a, b = int(rng.integers(100, 10 ** 6)), int(rng.integers(10, 100))
    cj = [j for j, _ in D.carry_info(a, b)]
    kap = D.C4.kappa(a, b)
    ok_k &= cj == [k + 1 for k, v in enumerate(kap) if v]
    for j in range(1, len(str(a + b)) + 1):
        ok_phi &= (math.floor(D.carry_potential(a, b, j) + 1e-12) == 1) == (j in cj)
check('переносы: тот же узор, что ocdiv4.kappa (3000 пар)', ok_k)
check('потенциал Φ_j (Wen и др.): ⌊Φ_j⌋ = перенос в разряд j (3000 пар)', ok_phi)
check('1987 + 45: переносы в 1, 2 (порождены) и 3 (протянут); Φ = 1,2 / 1,32 / 1,032',
      D.carry_info(1987, 45) == [(1, True), (2, True), (3, False)] and abs(D.carry_potential(1987, 45, 3) - 1.032) < 1e-12)

# 2. Разбор смещения
check('смещение → потерянные переносы: −100 → (2,), −110 → (1, 2), −100 без переноса в 2 → прочее, +10 → прочее, 0 → верно',
      D.lost_set(-100, [1, 2, 3]) == (2,) and D.lost_set(-110, [1, 2, 3]) == (1, 2) and D.lost_set(-100, [1, 3]) is None
      and D.lost_set(10, [1]) is None and D.lost_set(0, []) == () and D.lost_set(D.NC + 2, [1]) is None)


# 3. Мир «голова — программа»: задачи как в «тысячах», программа задана, прочие ошибки — смещение +7·10^k
def items_thousands(n, Xs, seed):
    g = np.random.default_rng(seed)
    out = []
    for _ in range(n):
        X = int(g.choice(Xs))
        a, b = int(100 * X + g.integers(0, 100)), int(g.integers(10, 100))
        out.append(dict(a=a, b=b, sum=a + b, ood=int(a + b >= 100 * (X + 1))))
    return out


TRUE = dict(features=['top', 'prop'], w=[-2.5, 2.0, 1.5], w_round=[-2.5, 2.0, 1.5], eps=0.05,
            q={7: 1 / 3, 70: 1 / 3, 700: 1 / 3}, q_rest=0.0)          # «прочие» — +7·10^k, k = 0…2, как в head_answers


def head_answers(items, prog, seed, other=lambda it, g: 7 * 10 ** int(g.integers(0, 3)), none_rate=0.01):
    g = np.random.default_rng(seed)
    out = []
    for it in items:
        if g.random() < none_rate:
            out.append(D.NC)
            continue
        if g.random() < prog['eps']:
            out.append(int(other(it, g)))
            continue
        off = 0
        for r in D.position_features(it['a'], it['b'], it['ood']):
            if g.random() < D.p_drop(prog, r):
                off -= 10 ** r['j']
        out.append(off)
    return np.array(out, np.int64)


build, fresh = items_thousands(4000, [19, 29, 49, 69, 89], 11), items_thousands(3000, [19, 29, 49, 69, 89], 12)
ob, of = head_answers(build, TRUE, 21), head_answers(fresh, TRUE, 22)
prog = D.fit_program(build, ob)
check('программа: признаки «старший перенос» и «протянут» выбраны, коэффициенты около заложенных (±0,35)',
      set(prog['features']) >= {'top', 'prop'} and abs(prog['w'][0] + 2.5) < 0.35
      and all(abs(prog['w'][1 + prog['features'].index(f)] - v) < 0.35 for f, v in (('top', 2.0), ('prop', 1.5))),
      json.dumps({k: prog[k] for k in ('features', 'w', 'eps')}))
check('программа: ε около заложенной доли прочих ошибок 0,05', abs(prog['eps'] - 0.05) < 0.015, str(prog['eps']))
dsum = D.program_dist(prog, fresh[0])
check('распределение программы на задаче суммируется к 1 − ε', abs(sum(dsum.values()) - (1 - prog['eps'])) < 1e-9)
om, box, phi = D.offset_model(build, ob), D.box_fit(build, ob), D.fit_program(build, ob, fixed=D.PHI_BASE)
sc = D.head_scores(prog, om, box, fresh, of, phi=phi)
check('мир «голова — программа»: на свежих задачах программа лучше B0, B1 и Φ-базы по лог-вероятности ответа',
      sc['prog'] > sc['b0'] and sc['prog'] > sc['b1'] and sc['prog'] > sc['phi'], json.dumps({k: sc[k] for k in ('prog', 'b0', 'b1', 'phi', 'box')}))
check('мир «голова — программа»: доля неверных ответов, названных программой в трёх самых вероятных, не меньше, чем у B1',
      sc['hit_prog'] >= sc['hit_b1'], f"{sc['hit_prog']:.3f} против {sc['hit_b1']:.3f}")
expl = (sc['prog'] - sc['b1']) / (sc['box'] - sc['b1']) if sc['box'] > sc['b1'] else float('nan')
check('мир «голова — программа»: доля объяснимого против ящика больше 0,8', expl > 0.8, str(expl))
check('оценщик: AUC P(верно) программы больше 0,5 на свежих задачах', sc['auc_prog'] > 0.5, str(sc['auc_prog']))

# 4. Мир «смещения без связи со входом»: неверный ответ — всегда −100 (и там, где переноса в сотни нет) — B1 лучше программы
ob2 = np.array([0 if g < 0.7 else -100 for g in np.random.default_rng(31).random(len(build))])
of2 = np.array([0 if g < 0.7 else -100 for g in np.random.default_rng(32).random(len(fresh))])
p2, om2 = D.fit_program(build, ob2), D.offset_model(build, ob2)
sc2 = D.head_scores(p2, om2, None, fresh, of2)
check('мир «смещение без связи со входом»: B1 лучше программы (программа не может назвать −100 без переноса в сотни)',
      sc2['b1'] > sc2['prog'], json.dumps({k: sc2[k] for k in ('prog', 'b1')}))

# 5. Совпадение: головы-программы, независимые при данном входе, → отношения около 1; общий «прочий» ответ → K больше
heads = [dict(TRUE, w=[-2.5 + 0.2 * k, 2.0, 1.5], w_round=[-2.5 + 0.2 * k, 2.0, 1.5]) for k in range(5)]
Dm = np.column_stack([head_answers(fresh, h, 40 + k) for k, h in enumerate(heads)])
co = D.coincidence_env(heads, fresh, Dm, 20, np.random.default_rng(5))
check('совпадение: при программах, независимых при данном входе, K и F наблюдённые / из программ — в [0,85; 1,15]',
      0.85 <= co['K_ratio'] <= 1.15 and 0.85 <= co['F_ratio'] <= 1.15, json.dumps(co))
shared = np.random.default_rng(6).random(len(fresh)) < 0.15
Dm2 = Dm.copy()
for k in range(Dm2.shape[1]):
    Dm2[shared & (Dm2[:, k] < D.NC), k] = 70                      # общий для задачи «прочий» ответ сверх программ
co2 = D.coincidence_env(heads, fresh, Dm2, 20, np.random.default_rng(5))
check('совпадение: общий «прочий» ответ сверх программ поднимает K наблюдённое, K из программ не меняется (±0,02), отношение K растёт',
      co2['K_obs'] > co['K_obs'] + 0.05 and abs(co2['K_prog'] - co['K_prog']) < 0.02 and co2['K_ratio'] > co['K_ratio'], json.dumps([co, co2]))
check('AUC: 1 при полном разделении, 0,5 при равных оценках', D.auc([0.1, 0.9, 0.8], [0, 1, 1]) == 1.0 and D.auc([0.5, 0.5], [0, 1]) == 0.5)

# 6. Сухой прогон цепочки: сборка в виде answers.json (как `analyze_ocshift.load_new`), пилот целиком
tmp = tempfile.mkdtemp(prefix='distill02_stub_')


def write_merged(path, env_specs, heads_progs, seed):
    os.makedirs(path, exist_ok=True)
    envs, hs = [], []
    for name, X, n in env_specs:
        its = items_thousands(n, [X], seed + X)
        envs.append(dict(name=name, family='thousands', X=X, p=3, bound=100 * (X + 1), max_new=6,
                         problems=[dict(a=it['a'], b=it['b'], sum=it['sum'], range='ID' if not it['ood'] else 'OOD') for it in its]))
    for k, hp in enumerate(heads_progs):
        cols = {}
        for e in envs:
            its = [dict(a=p['a'], b=p['b'], sum=p['sum'], ood=int(p['range'] != 'ID')) for p in e['problems']]
            offs = head_answers(its, hp, seed + 100 * k + len(e['problems']))
            ans = [None if o >= D.NC else it['sum'] + int(o) for it, o in zip(its, offs)]
            cols[e['name']] = dict(answer=ans, correct=[int(x is not None and x == it['sum']) for x, it in zip(ans, its)],
                                   logp=[float(-1.0 if x == it['sum'] else -3.0) for x, it in zip(ans, its)], n_tok=[4] * len(its))
        hs.append(dict(model=f'stub/head{k}', revision='0' * 40, cols=cols))
    json.dump(dict(envs=envs, heads=hs), open(os.path.join(path, 'answers.json'), 'w'), ensure_ascii=False)


write_merged(os.path.join(tmp, 'fit'), [('T_X19_p3', 19, 600), ('T_X49_p3', 49, 600)], heads[:4], 70)
write_merged(os.path.join(tmp, 'eval'), [('T_X29_p3', 29, 800), ('T_X69_p3', 69, 800)], heads[:4], 90)
out = D.pilot(os.path.join(tmp, 'pilot.json'), {'thousands': (os.path.join(tmp, 'fit'), None), 'T_low': (os.path.join(tmp, 'fit'), ['T_X19_p3'])},
              {'новые X': ('thousands', [os.path.join(tmp, 'eval')], None), 'перенос': ('T_low', [os.path.join(tmp, 'eval')], ['T_X69_p3'])}, R=5)
sm = out['eval']['новые X']['summary']
check('сухой прогон: пилот собирает формулы четырёх голов, Φ-базу и сводку по двум средам проверки; построение по части сред (П4)',
      len(out['formulas']['thousands']) == 4 and len(out['formulas_phi']['thousands']) == 4 and sm['n_cells'] == 8
      and set(out['eval']['новые X']['envs']) == {'T_X29_p3', 'T_X69_p3'} and out['fit_envs']['T_low'] == ['T_X19_p3']
      and set(out['eval']['перенос']['envs']) == {'T_X69_p3'}, json.dumps(sm, default=float)[:300])
check('сухой прогон: в мире «головы — программы» программа лучше B1 в каждой из 8 пар «голова × среда»',
      sm['prog_minus_b1_pos'] == 8 and sm['prog_minus_b1_mean'] > 0, json.dumps(sm, default=float)[:300])
check('сухой прогон: вывод пилота — json без NaN в формулах', all(np.isfinite(v) for f in out['formulas']['thousands'].values() for v in f['w']))

print(f'провалов: {len(fails)}')
