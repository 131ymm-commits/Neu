#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""DISTILL-04: тесты программы-М на заглушках с известным ответом, в том числе контроли совета 77 (ворота 5):
положительный (голова ошибается операторами — М лучше нуля-Т), отрицательный (ошибки по таблице, не зависящей от входа — М не лучше),
мутант кода (из каталога убран главный оператор — преимущество М на положительной заглушке пропадает).
  python3 test_prog_m.py   — печатает ✓/✗ и «провалов: N»"""
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import prog_m as PM  # noqa: E402

D2 = PM.D2
FAILS = []


def check(name, cond, info=''):
    print(('✓ ' if cond else '✗ ') + name + (f' — {info}' if info else ''), flush=True)
    if not cond:
        FAILS.append(name)


def items_pool(n, rng, lo=1900, hi=1999):
    out = []
    for _ in range(n):
        a = int(rng.integers(lo, hi + 1))
        b = int(rng.integers(10, 999))
        out.append(dict(a=a, b=b, sum=a + b, ood=int(a + b >= 2000)))
    return out


def t_clamp():
    c = PM.candidates(1912, 99)
    check('clamp9: 1912 + 99 = 2011 → 1991', c['clamp9'] == {1991}, str(c['clamp9']))
    check('clamp9: без перехода через сотню — пусто', PM.candidates(1912, 48)['clamp9'] == set())


def t_fit_weights():
    rng = np.random.default_rng(1)
    n = 4000
    A = np.zeros((n, 2))
    U = np.full(n, 1e-5)
    lab = rng.choice(3, size=n, p=[0.6, 0.1, 0.3])
    A[lab == 0, 0] = 1.0
    A[lab == 1, 1] = 0.5                      # у оператора 1 два кандидата
    pi = PM.fit_weights(A, np.ones((n, 2)), U)
    check('веса операторов восстановлены (0,6 / 0,1 / 0,3)', np.allclose(pi, [0.6, 0.1, 0.3], atol=0.03), str(np.round(pi, 3)))


def true_head(rng, ops, pi, eps=0.3, b0=-1.5):
    prog = dict(eps=eps, q={}, q_rest=1.0, n_other=1, features=['prop'], w=[b0, 1.0], w_round=[b0, 1.0])
    return dict(prog=prog, ops=list(ops), pi=np.array(pi, float))


def table_head(rng, eps=0.3):
    """Голова, у которой «прочие» — смещения из таблицы, не зависящей от входа."""
    prog = dict(eps=eps, q={-20: 0.3, -40: 0.25, 20: 0.2, -90: 0.15}, q_rest=0.1, n_other=1, features=['prop'], w=[-1.5, 1.0], w_round=[-1.5, 1.0])
    return prog


def run_stub(sampler, heads, ops, seed, n_con=2500, n_test=1200, n_env=2):
    rng = np.random.default_rng(seed)
    con = items_pool(n_con, rng)
    offs_c = {h: np.array([sampler(h, it, rng) for it in con]) for h in heads}
    fits = {h: PM.fit_head(con, offs_c[h], ops) for h in heads}
    pts = []
    for e in range(n_env):
        te = items_pool(n_test, rng)
        offs_t = {h: np.array([sampler(h, it, rng) for it in te]) for h in heads}
        er = PM.env_rows(fits, te, offs_t, heads)
        pts.append({k: float(v[0]) for k, v in PM.measures_w(er, np.ones((1, er['n']))).items()})
    return fits, {k: float(np.mean([p[k] for p in pts])) for k in pts[0]}


OPS = ['plus10j', 'minus10j', 'shift', 'operand', 'drop_b_digit', 'drop_a_digit']


def t_controls():
    rng = np.random.default_rng(2)
    # положительный: «прочие» — пропуск цифры b (0,6), сдвиг операнда (0,2), остаток (0,2)
    pi = [0, 0, 0.2, 0, 0.6, 0, 0.2]
    th = {f'h{i}': true_head(rng, OPS, pi, eps=0.25 + 0.05 * i) for i in range(3)}
    fits, m = run_stub(lambda h, it, r: PM.sample_m(th[h], it, r), list(th), OPS, 11)
    check('положительный контроль: М лучше нуля-Т того же размера (m_M > 0,05 нат)', m['m_M'] > 0.05, f"m_M {m['m_M']:.4f}, по «прочим» {m['m_Mo']:.4f}")
    check('положительный контроль: М чаще называет неверное число среди трёх (top3 > 0)', m['top3'] > 0, f"{m['top3']:.4f}")
    w = fits['h0']['pi']
    check('положительный контроль: вес пропуска цифры b восстановлен (≈ 0,6)', abs(w[OPS.index('drop_b_digit')] - 0.6) < 0.08, str(np.round(w, 3)))
    # мутант: из каталога убран пропуск цифры b — преимущество пропадает
    ops_mut = [o for o in OPS if o != 'drop_b_digit']
    _, mm = run_stub(lambda h, it, r: PM.sample_m(th[h], it, r), list(th), ops_mut, 11)
    check('мутант кода (без пропуска цифры b): m_M падает больше чем вдвое', mm['m_M'] < 0.5 * m['m_M'], f"m_M {mm['m_M']:.4f} против {m['m_M']:.4f}")
    # отрицательный: «прочие» — по таблице смещений, не зависящей от входа (сид вне теста)
    tp = {f'h{i}': table_head(rng, eps=0.25 + 0.05 * i) for i in range(3)}
    _, mn = run_stub(lambda h, it, r: int(D2.sample_program(tp[h], it, r)), list(tp), OPS, 13)
    check('отрицательный контроль: М не лучше нуля-Т (m_M ≤ 0)', mn['m_M'] <= 0, f"m_M {mn['m_M']:.4f}")


def t_probs():
    rng = np.random.default_rng(3)
    fm = true_head(rng, ['drop_b_digit'], [1.0, 0.0])
    fm['prog_T'] = PM.table_prog(dict(fm['prog'], q={-80: 1.0}), 1)
    fm['mt_offsets'], fm['pi_mt'] = [], np.array([1.0, 0.0])
    it = dict(a=1957, b=86, sum=2043, ood=1)
    S = PM.support(fm['prog'], it)
    ck = PM.candidates(1957, 86)['drop_b_digit'] - S
    pr = [PM.q_m(fm, it, y, S) for y in sorted(ck)]
    check('Q_М: при весе 1 на одном операторе кандидаты делят массу поровну', np.allclose(pr, 1 / len(ck)), str(np.round(pr, 4)))
    p = PM.answer_probs(fm, it, 2043)
    check('верный ответ: у всех четырёх программ одна вероятность', len(set(round(x, 15) for x in p.values())) == 1)


def t_pilot_dry():
    """Сухой прогон pilot_d4.py на заглушках: сборка из папок, каталог по правилу, меры с бутстрепом, мощность."""
    import json as _json
    import tempfile
    import pilot_d4 as PL
    rng = np.random.default_rng(21)
    heads = ['Falcon3-1B-Instruct', 'OLMo-2-0425-1B-Instruct', 'Qwen2.5-0.5B-Instruct']
    pi = [0, 0, 0.2, 0, 0.6, 0, 0.2]
    th = {h: true_head(rng, OPS, pi, eps=0.3) for h in heads}

    def env(n):
        it = items_pool(n, rng)
        return dict(items=it, offs={h: np.array([PM.sample_m(th[h], x, rng) for x in it]) for h in heads})
    dirs = {'c_T': {'T_X19_p3': env(900), 'T_X29_p3': env(900)}, 'e_T': {f'T_X{x}_p3': env(400) for x in (29, 39, 49, 59)}}
    orig = (D2.load_merged, D2.env_table)
    try:
        D2.load_merged = lambda d: dirs[d]
        D2.env_table = lambda e, heads=None, with_logp=False: (e['items'], e['offs'])
        tmp = tempfile.mkdtemp()
        spec = os.path.join(tmp, 'spec.json')
        _json.dump({'construction': {'thousands': ['c_T']}, 'eval': {'test5_thousands': {'family': 'thousands', 'dirs': ['e_T']}},
                    'B': 50, 'seed': 1, 'm_test': {'thousands': 8}}, open(spec, 'w'))
        rc = PL.main([os.path.join(tmp, 'pilot.json'), spec])
        out = _json.load(open(os.path.join(tmp, 'pilot.json')))
    finally:
        D2.load_merged, D2.env_table = orig
    check('сухой прогон пилота: каталог содержит пропуск цифры b', rc == 0 and 'drop_b_digit' in out['catalog'], str(out['catalog']))
    pts = [e['point']['m_M'] for e in out['sets']['test5_thousands']['envs'].values()]
    check('сухой прогон пилота: m_M > 0 во всех средах заглушки', len(pts) == 4 and all(p > 0 for p in pts), str(np.round(pts, 3)))
    pw = out['power']['test5_thousands']['m_M']
    check('сухой прогон пилота: мощность посчитана для 8 сред теста', pw is not None and out['power']['test5_thousands']['m_test'] == 8, str(pw and pw['power']))


if __name__ == '__main__':
    t_clamp()
    t_fit_weights()
    t_probs()
    t_controls()
    t_pilot_dry()
    print('провалов:', len(FAILS), FAILS)
    sys.exit(1 if FAILS else 0)
