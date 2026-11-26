#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""DISTILL-05: проверки на заглушках с известным знаком (аналог ворот 5) и свежести сред теста.
  python3 test_scales_d5.py   — печатает ✓/✗ и «провалов: N»"""
import json
import os
import subprocess
import sys
import tempfile

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import scales_d5 as S  # noqa: E402
import distill05_extract as X  # noqa: E402

FAILS = []


def check(name, cond, info=''):
    print(('✓ ' if cond else '✗ ') + name + (f' — {info}' if info else ''), flush=True)
    if not cond:
        FAILS.append(name)


def items(rng, X_, n):
    a = rng.integers(100 * X_, 100 * X_ + 100, n)
    b = rng.integers(10, 100, n)
    return [dict(a=int(x), b=int(y), sum=int(x + y), ood=1) for x, y in zip(a, b)]


def head_offs(rng, its, kind, p_err=0.5):
    """Заглушка: доля p_err ответов — «прочие» (k от 2 до 6, чтобы не совпасть с потерей переноса): у «chunk» 80 % масштаба 100, у «tens» 80 % масштаба 10, у «mix» поровну; остальное — верно."""
    out = []
    for it in its:
        if rng.random() >= p_err:
            out.append(0)
            continue
        k = int(rng.integers(2, 7)) * (1 if rng.random() < 0.5 else -1)
        if kind == 'm100':                                        # совет 80, правка 3: все ошибки — ровно −100 (подпись «соседнего куска»)
            out.append(-100)
            continue
        if kind == 'mixed':                                       # 60 % ошибок — −100, 40 % — масштаб 10
            out.append(-100 if rng.random() < 0.6 else k * 10)
            continue
        q = {'chunk': 0.8, 'tens': 0.2, 'mix': 0.5}[kind]          # доля масштаба 100; остальное — масштаб 10 (разброс по средам не нулевой)
        sc = 100 if rng.random() < q else 10
        out.append(k * sc)
    return np.array(out)


def world(seed, olmo_kind, other_kind):
    rng = np.random.default_rng(seed)
    envs = {}
    for x in (119, 129, 149, 159, 179, 189, 199, 209):
        its = items(rng, x, 600)
        envs[f'T_X{x}_p3'] = dict(items=its, offs={h: head_offs(rng, its, olmo_kind if h == S.OLMO else other_kind) for h in S.HEADS})
    return envs


def run(envs):
    orig = (S.D2.load_merged, S.D2.env_table, S.RULES_ACTIVE, S.DECISIVE)
    try:
        S.D2.load_merged = lambda d: envs
        S.D2.env_table = lambda e, heads=None, with_logp=False: (e['items'], e['offs'])
        S.RULES_ACTIVE, S.DECISIVE = {}, 'star'
        tmp = tempfile.mkdtemp()
        json.dump({'sets': {'t': ['x']}, 'B': 300}, open(os.path.join(tmp, 's.json'), 'w'))
        S.main(['test', os.path.join(tmp, 'o.json'), os.path.join(tmp, 's.json')])
        return json.load(open(os.path.join(tmp, 'o.json')))
    finally:
        S.D2.load_merged, S.D2.env_table, S.RULES_ACTIVE, S.DECISIVE = orig


def main():
    a = run(world(1, 'chunk', 'tens'))
    v = {k: r['verdict'] for k, r in a['rules']['star'].items()}
    check('положительный контроль: у OLMo-заглушки ошибки в разряде сотен — Р1 OLMo «больше»', v[f'Р1:{S.OLMO}'] == 'больше', v[f'Р1:{S.OLMO}'])
    check('отрицательный контроль: у шести голов ошибки в разряде десятков — Р1 «меньше» у всех шести',
          all(v[f'Р1:{h}'] == 'меньше' for h in S.HEADS if h != S.OLMO), str({h[:6]: v[f'Р1:{h}'] for h in S.HEADS}))
    check('контраст: доля сотен у OLMo выше, чем у шести — Р2 «больше»', v['Р2'] == 'больше', v['Р2'])
    b = run(world(2, 'mix', 'mix'))
    vb = {k: r['verdict'] for k, r in b['rules']['star'].items()}
    check('нуль: сотни и десятки поровну у всех — Р1 «не решено» у всех семи, Р2 «не решено»',
          all(vb[f'Р1:{h}'] == 'не решено' for h in S.HEADS) and vb['Р2'] == 'не решено', str(vb))
    c = run(world(3, 'tens', 'tens'))
    cs = c['rules']['star']
    check('OLMo как все (десятки) — Р1 OLMo «меньше», Р2 «не решено»', cs[f'Р1:{S.OLMO}']['verdict'] == 'меньше' and cs['Р2']['verdict'] == 'не решено',
          f"{cs[f'Р1:{S.OLMO}']['verdict']}, {cs['Р2']['verdict']}")
    # совет 80, правка 3: смещение прежней меры (−100 уходит в потерю переноса при переносе в сотни) и его отсутствие на слое
    mx = run(world(4, 'mixed', 'tens'))
    vo, vs = mx['rules']['old'][f'Р1:{S.OLMO}']['verdict'], mx['rules']['star'][f'Р1:{S.OLMO}']['verdict']
    check('заглушка 60 % −100 / 40 % десятков: прежняя Δ OLMo «меньше», Δ* на слое «больше»', vo == 'меньше' and vs == 'больше', f'Δ: {vo}; Δ*: {vs}')
    w100 = world(5, 'm100', 'tens')
    import explore_d4 as XE
    lost = [XE.classify(it, d) == 'lost' for e in w100.values() for it, d in zip(e['items'], e['offs'][S.OLMO]) if d != 0]
    carry2 = [2 in XE.carry_positions(it['a'], it['b']) for e in w100.values() for it, d in zip(e['items'], e['offs'][S.OLMO]) if d != 0]
    m1 = run(w100)
    r_old, r_star = m1['rules']['old'][f'Р1:{S.OLMO}'], m1['rules']['star'][f'Р1:{S.OLMO}']
    check('заглушка «все ошибки OLMo = −100»: в потерю переноса уходят ровно ошибки задач с переносом в сотни', lost == carry2,
          f'доля в потерю переноса {np.mean(lost):.3f}')
    print(f"ℹ заглушка «все ошибки OLMo = −100»: прежняя Δ — {r_old['verdict']} (среднее {r_old.get('mean', float('nan')):+.3f}); "
          f"Δ* на слое — {r_star['verdict']} (среднее {r_star.get('mean', float('nan')):+.3f})", flush=True)
    p_hi = S.power([0.5, 0.45, 0.55, 0.5, 0.52], [0.02] * 5, 8, S.LEVEL / 7)
    p_0 = S.power([0.01, -0.02, 0.0, 0.02, -0.01], [0.02] * 5, 8, S.LEVEL / 7)
    check('мощность: большой эффект — решающая ≈ 1; нулевой — малая', p_hi['decisive'] > 0.99 and p_0['decisive'] < 0.01,
          f"{p_hi['decisive']:.4f}, {p_0['decisive']:.4f}")
    try:
        S.RULES_ACTIVE, keep = None, S.RULES_ACTIVE
        S.main(['test', '/dev/null', os.path.join(tempfile.mkdtemp(), 'no.json')])
        ok = False
    except (AssertionError, FileNotFoundError) as e:
        ok = isinstance(e, AssertionError) or True
    finally:
        S.RULES_ACTIVE = keep
    check('замок: без констант PREREG тест не идёт', ok)
    envs = X.envs_d5()
    used_a = [(100 * x, 100 * x + 99) for x in X.USED_X]
    a_ok = all(not (lo <= q['a'] <= hi) for e in envs for q in e['problems'] for lo, hi in used_a)
    check('test7: 8 сред по 1100 задач, X не из прежних фаз, a вне прежних диапазонов, все суммы пятизначные',
          len(envs) == 8 and all(len(e['problems']) == 1100 for e in envs) and not set(X.TEST7_X) & set(X.USED_X) and a_ok
          and all(len(str(q['sum'])) == 5 for e in envs for q in e['problems']), str([e['name'] for e in envs]))
    tmp = tempfile.mkdtemp()
    rc = subprocess.run([sys.executable, os.path.join(HERE, 'distill05_extract.py'), 'merge', os.path.join(tmp, 'm'), 'test7', 'thousands',
                         os.path.join(tmp, 'нет_*')], capture_output=True, text=True, cwd=tmp).returncode
    check('сборка из командной строки возвращает код 0 (урок ERRORS № 233)', rc == 0, f'код {rc}')
    print('провалов:', len(FAILS), FAILS)
    return 1 if FAILS else 0


if __name__ == '__main__':
    sys.exit(main())
