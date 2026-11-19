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


NORM_MAX = 1e-3                 # PREREG §4 «Нормировка» (совет 78, п. 6): порог наибольшей по задачам |недостача М − недостача Т| / ε


def mass_by_enum(fm, it):
    """Перебор всех значений V ∪ C (C — кандидаты операторов и смещения таблиц): суммы вероятностей М, Т, Т30, М+Т на задаче."""
    dist = D2.program_dist(fm['prog'], it, True)
    S = set(dist)
    cand = PM.candidates(it['a'], it['b'])
    s, n = it['sum'], len(str(it['sum']))
    V = range(10 ** max(n - 3, 0), 10 ** (n + 1))
    assert len(V) == D2.ref_size(s)
    C = set().union(*[cand[op] for op in fm['ops']]) | {s + int(d) for d in list(fm['prog']['q']) + list(fm['mt_offsets']) if s + int(d) >= 0}
    eps = fm['prog']['eps']
    tot = dict(M=0.0, T=0.0, T30=0.0, MT=0.0)
    for y in set(V) | C:
        if y in dist:
            for k in tot:
                tot[k] += dist[y]
            continue
        tot['M'] += eps * PM.q_m(fm, it, y, S, cand)
        tot['T'] += D2.answer_prob(fm['prog_T'], it, y, True, dist)
        tot['T30'] += D2.answer_prob(fm['prog'], it, y, True, dist)
        tot['MT'] += eps * PM.q_m(fm, it, y, S, cand, mt=True)
    return tot, dict(S=S, cand=cand, V=V, dist=dist)


def deficit_formula(fm, it, aux):
    """Недостача по формуле (PREREG §4): М — ε·(π_U/Z)·(|S ∩ V| − |C' ∖ V|)/|V|; Т — ε·(q_rest/tot)·(|S ∩ V| + |T_valid ∩ V|)/|V|."""
    S, cand, V = aux['S'], aux['cand'], aux['V']
    eps, s = fm['prog']['eps'], it['sum']
    lo, hi = V.start, V.stop
    live = [cand[op] - S for op in fm['ops']]
    Z = sum(p for p, ck in zip(fm['pi'][:-1], live) if ck) + fm['pi'][-1]
    out_v = len(set().union(*live) - set(V)) if live else 0
    d_m = eps * (fm['pi'][-1] / Z) * (sum(lo <= y < hi for y in S) - out_v) / len(V)
    pt = fm['prog_T']
    valid = {s + int(d) for d, q in pt['q'].items() if s + int(d) >= 0 and s + int(d) not in S}
    tot_t = sum(q for d, q in pt['q'].items() if s + int(d) >= 0 and s + int(d) not in S) + pt['q_rest']
    d_t = eps * (pt['q_rest'] / tot_t) * (sum(lo <= y < hi for y in S) + sum(lo <= y < hi for y in valid)) / len(V)
    return d_m, d_t


def t_norm():
    """Совет 78, п. 6: суммы М, Т, Т30 и М+Т по V ∪ C не больше 1 (допуск 1e-12); недостача ε − Σ_{y ∉ S} P(y) у М и у Т по задачам;
    формулы недостачи сверены с перебором; наибольшая по задачам |недостача М − недостача Т| / ε печатается (порог NORM_MAX — правило
    PREREG, ветвь выбирается по нему, а не по исходу теста)."""
    q = {-20: 0.25, -40: 0.15, 20: 0.1, -90: 0.05, 2: 0.05}
    prog = dict(eps=0.3, q=q, q_rest=0.4, n_other=100, features=['prop'], w=[-1.0, 1.0], w_round=[-1.0, 1.0])
    fm = dict(prog=prog, ops=list(OPS), pi=np.array([0.1, 0.05, 0.1, 0.05, 0.3, 0.1, 0.3]), prog_T=PM.table_prog(prog, 3),
              mt_offsets=[-20, -40], pi_mt=np.array([0.1, 0.05, 0.05, 0.05, 0.2, 0.05, 0.2, 0.1, 0.2]))
    tasks = [(457, 86), (199, 99), (805, 17), (360, 45), (898, 99), (1957, 86)]
    worst, gap, rows = 0.0, 0.0, []
    for a, b in tasks:
        it = dict(a=a, b=b, sum=a + b, ood=0)
        tot, aux = mass_by_enum(fm, it)
        worst = max(worst, max(tot.values()) - 1.0)
        d_m, d_t = 1.0 - tot['M'], 1.0 - tot['T']
        f_m, f_t = deficit_formula(fm, it, aux)
        gap = max(gap, abs(d_m - f_m), abs(d_t - f_t))
        rows.append((a, b, d_m / prog['eps'], d_t / prog['eps']))
    check('нормировка: суммы М, Т, Т30, М+Т по V ∪ C не больше 1 (допуск 1e-12)', worst <= 1e-12, f'наибольший избыток {worst:.1e}')
    check('нормировка: недостача М и Т по формуле PREREG совпадает с перебором (1e-12)', gap <= 1e-12, f'расхождение {gap:.1e}')
    mx = max(abs(r[2] - r[3]) for r in rows)
    for a, b, dm, dt in rows:
        print(f'  недостача / ε: {a} + {b} — М {dm:.3e}, Т {dt:.3e}, |М − Т| {abs(dm - dt):.3e}')
    print(f'ℹ нормировка (заглушка): наибольшая по задачам |недостача М − недостача Т| / ε = {mx:.3e}; порог PREREG {NORM_MAX:g} — '
          + ('не выше порога' if mx <= NORM_MAX else 'ВЫШЕ порога'), flush=True)


if __name__ == '__main__':
    t_norm()
    t_clamp()
    t_fit_weights()
    t_probs()
    t_controls()
    t_pilot_dry()
    print('провалов:', len(FAILS), FAILS)
    sys.exit(1 if FAILS else 0)
