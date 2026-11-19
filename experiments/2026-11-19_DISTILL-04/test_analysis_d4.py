#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""DISTILL-04: сухой прогон анализа теста (test_d4.py) на заглушках: замок констант PREREG, сборка из папок, правила, повтор A-на-B,
описательная «длина», детерминизм (два прогона — одинаковый вывод без seconds).
  python3 test_analysis_d4.py   — печатает ✓/✗ и «провалов: N»"""
import json
import os
import sys
import tempfile

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import test_d4 as T  # noqa: E402
import test_prog_m as TP  # noqa: E402

PM, D2 = T.PM, T.D2
FAILS = []


def check(name, cond, info=''):
    print(('✓ ' if cond else '✗ ') + name + (f' — {info}' if info else ''), flush=True)
    if not cond:
        FAILS.append(name)


def t_rep_check():
    """rep_check_d4.py на заглушке: одинаковые столбцы — доля 1; одно расхождение из четырёх — 0,75; разная длина — None."""
    import rep_check_d4 as RC
    tmp = tempfile.mkdtemp()
    for job, cols in (('distill04_rep_x_T_X14_p3', {'T_X14_p3': {'text': ['1', '2', '3', '4'], 'off': [0, 1, 2, 3], 'n': [1, 2]}}),
                      ('distill04_test_x_T_X14_p3', {'T_X14_p3': {'text': ['1', '2', '3', '5'], 'off': [0, 1, 2, 3], 'n': [1, 2, 3]}})):
        os.makedirs(os.path.join(tmp, job))
        json.dump({'model': 'x', 'cols': cols}, open(os.path.join(tmp, job, 'answers_x.json'), 'w'))
    dst = os.path.join(tmp, 'rep.json')
    RC.main([dst, tmp])
    c = json.load(open(dst))['jobs']['distill04_rep_x_T_X14_p3']['columns']['T_X14_p3']
    check('повтор извлечения: доли совпадений по столбцам (1; 0,75; разная длина — None)',
          c['off']['equal_share'] == 1.0 and c['text']['equal_share'] == 0.75 and c['n']['equal_share'] is None, str(c))


def main():
    registered = T.RULES_ACTIVE
    try:                                   # ERRORS № 230: после записи констант замок проверяется на временно стёртых константах
        T.RULES_ACTIVE = None
        T.main(['/dev/null', '/dev/null'])
        ok = False
    except AssertionError as e:
        ok = 'константы PREREG' in str(e)
    finally:
        T.RULES_ACTIVE = registered
    check('замок: без констант PREREG анализ не идёт', ok)
    try:
        T.test_lock()
        ok_reg = True
    except AssertionError:
        ok_reg = False
    check('замок: с записанными константами PREREG анализ идёт', ok_reg, str(T.RULES_ACTIVE))
    rng = np.random.default_rng(31)
    heads = TP.ab_heads = ['Falcon3-1B-Instruct', 'OLMo-2-0425-1B-Instruct', 'Qwen2.5-0.5B-Instruct', 'Qwen2.5-1.5B-Instruct',
                           'SmolLM2-1.7B-Instruct', 'SmolLM2-360M-Instruct', 'TinyLlama-1.1B-Chat-v1.0']
    ops = TP.OPS
    th = {h: TP.true_head(rng, ops, [0, 0, 0.1 + 0.05 * (i % 3), 0, 0.5, 0.1, 0.3 - 0.05 * (i % 3)], eps=0.2 + 0.03 * i, b0=-2.0 + 0.2 * i)
          for i, h in enumerate(heads)}

    def env(n, lo=1900, hi=1999):
        it = TP.items_pool(n, rng, lo, hi)
        return dict(items=it, offs={h: np.array([PM.sample_m(th[h], x, rng) for x in it]) for h in heads})
    dirs = {'c_T': {'T_X19_p3': env(700), 'T_X29_p3': env(700)}, 'c_L': {'L_X9_p3': env(500, 900, 999)},
            't_T6': {n: env(220, 100 * int(n[3:5]), 100 * int(n[3:5]) + 99) for n in T.TEST_ENVS},
            't_L6': {'L_X9999_p3': env(220, 999900, 999999)}}
    orig = (D2.load_merged, D2.env_table, T.RULES_ACTIVE, T.B_TEST)
    try:
        D2.load_merged = lambda d: dirs[d]
        D2.env_table = lambda e, heads=None, with_logp=False: (e['items'], e['offs'])
        T.RULES_ACTIVE = {'П1-Т': True, 'П1МТ-Т': True, 'П2-Т': False}
        T.B_TEST = 300
        tmp = tempfile.mkdtemp()
        spec = os.path.join(tmp, 'spec.json')
        json.dump({'construction': {'thousands': ['c_T'], 'length': ['c_L']}, 'test': {'thousands': ['t_T6']},
                   'descriptive': {'length': ['t_L6']}}, open(spec, 'w'))
        rc1 = T.main([os.path.join(tmp, 'a.json'), spec])
        rc2 = T.main([os.path.join(tmp, 'b.json'), spec])
        a, b = (json.load(open(os.path.join(tmp, f))) for f in ('a.json', 'b.json'))
        bad = dict(spec=spec)
        json.dump({'construction': {'thousands': ['c_T'], 'length': ['c_L']}, 'test': {'thousands': ['c_T']}}, open(os.path.join(tmp, 'bad.json'), 'w'))
        try:
            T.main([os.path.join(tmp, 'c.json'), os.path.join(tmp, 'bad.json')])
            ok_miss = False
        except AssertionError as e:
            ok_miss = 'нет сред' in str(e)
    finally:
        D2.load_merged, D2.env_table, T.RULES_ACTIVE, T.B_TEST = orig
    check('сухой прогон: три правила и два правила A-на-B', rc1 == 0 and set(a['rules']) == set(T.RULES) and set(a['ab']['verdicts']) == set(T.AB_RULES),
          str({k: v['verdict_final'] for k, v in a['rules'].items()}))
    check('сухой прогон: П2 помечено описательным (RULES_ACTIVE)', a['rules']['П2-Т']['verdict_final'].startswith('описательно'))
    check('сухой прогон: на заглушке, где «прочие» — операторы, П1МТ «подтверждено»', a['rules']['П1МТ-Т']['verdict_rule'] == 'подтверждено',
          a['rules']['П1МТ-Т']['verdict_rule'])
    check('сухой прогон: A-на-B — семь голов, у программы «да»', a['ab']['verdicts']['АБ-П-Т6']['k'] == 7 and a['ab']['verdicts']['АБ-П-Т6']['verdict'] == 'да',
          str({k: (v['verdict'], round(v['D'], 4)) for k, v in a['ab']['verdicts'].items()}))
    check('сухой прогон: «длина» test6L посчитана описательно', list(a['descriptive']) == ['length_test6L'])
    sl = a['ab']['slices']
    d_prog = a['ab']['verdicts']['АБ-П-Т6']['D']
    check('срезы A-на-B: «среднее чужих» по головам = D программы', abs(sl['prog']['mean']['mean'] - d_prog) < 1e-9,
          f"{sl['prog']['mean']['mean']:.6f} против {d_prog:.6f}")
    check('срезы A-на-B: медиана и «без худшей» посчитаны для обоих видов', all(set(sl[k]['mean']) == {'mean', 'median', 'drop_worst'} for k in ('prog', 'shape')))
    check('сухой прогон: в тесте ровно 8 новых сред', sorted(a['envs']) == sorted(T.TEST_ENVS))
    gap = max(abs(np.mean([v[k] for v in e['per_head'].values()]) - e['point'][k]) for e in a['envs'].values() for k in ('m_M', 'm_Mo', 'top3', 'm_MT'))
    check('по головам: среднее мер по головам = точка среды (m_M, m_Mo, top3, m_MT)', gap < 1e-12, f'наибольшее расхождение {gap:.1e}')
    ok_kin = a['op_kinship']['thousands']['n'] == 4 and all(abs(p['tv_kin']) <= 1 for p in a['op_kinship']['thousands']['pairs'])
    check('родство весов операторов: 4 головы с родичем, расстояние в [0, 1]', ok_kin, str(a['op_kinship']['thousands']['n_kin_closer']))
    w_same = {'x': dict(pi=[0.5, 0.5]), 'y': dict(pi=[0.5, 0.5])}
    T.KIN, kin0 = (('x', 'y'),), T.KIN
    try:
        k1 = T.op_kinship(w_same)
    finally:
        T.KIN = kin0
    check('родство весов операторов: одинаковые веса — расстояние 0', k1['n'] == 2 and all(p['tv_kin'] == 0 for p in k1['pairs']))
    for x in (a, b):
        x.pop('seconds')
    check('детерминизм: два прогона дают один вывод (без seconds)', json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True))
    check('замок: в тесте нет сред — СТОП', ok_miss)
    t_rep_check()
    print('провалов:', len(FAILS), FAILS)
    return 1 if FAILS else 0


if __name__ == '__main__':
    sys.exit(main())
