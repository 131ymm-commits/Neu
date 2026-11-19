#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""DISTILL-04: нулевая серия М ≡ Т и миры-заглушки для проверки всей цепочки (совет 78, п. 5; PREREG §10).
Мир — заглушка: семь голов, построение (8 сред устройства построения, X = 19 … 89) и 8 сред теста (X = 14 … 84, как test6). Часть переноса
у голов своя (ε и свободный член); «прочие» — смесь операторов каталога (доля mix) и таблицы смещений головы. Программы подбираются тем же
кодом, что в анализе (prog_m.fit_family), строки мер — prog_m.env_rows, бутстреп — prog_m.env_measures (B повторов), правило —
distill02.family_rule (m_M, двусторонний, части А и Б), как test_d4.
Нуль М ≡ Т: в каждой задаче метки М и Т меняются местами с вероятностью 1/2 (одна монета на задачу для всех голов). Тогда разность М − Т
симметрична около нуля при любых данных, и решающий вердикт («больше» или «меньше») — ложный.
  python3 null_d4.py ВЫХОД.json --worlds N --seed0 S [--B 4000] [--n-test 2200] [--n-con 400] [--mix 0.5] [--workers 1]
Миры независимы (свои зёрна), поэтому счёт в нескольких процессах даёт тот же вывод, что в одном.
Зерно мира — [SEED_NULL, seed0 + номер мира]; не пересекается с зёрнами пилотов (9 940 000), повторов (9 940 100) и теста (9 940 400)."""
import concurrent.futures as cf
import json
import os
import platform
import sys
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import prog_m as PM  # noqa: E402

D2 = PM.D2
SEED_NULL = 9_940_700
HEADS = ('Falcon3-1B-Instruct', 'OLMo-2-0425-1B-Instruct', 'Qwen2.5-0.5B-Instruct', 'Qwen2.5-1.5B-Instruct', 'SmolLM2-1.7B-Instruct',
         'SmolLM2-360M-Instruct', 'TinyLlama-1.1B-Chat-v1.0')
CON_X = (19, 29, 39, 49, 59, 69, 79, 89)
TEST_X = (14, 24, 34, 44, 54, 64, 74, 84)
CATALOG = ('plus10j', 'minus10j', 'digit_pm1', 'shift', 'operand', 'omit_digit', 'drop_b_digit', 'drop_a_digit', 'move_b_digit', 'clamp9')
OFFSETS = (-20, -40, -90, -80, -60, -30, -50, 20, -99, 2, -102, -10)


def items_env(X, n, rng):
    a = rng.integers(100 * X, 100 * X + 100, n)
    b = rng.integers(10, 100, n)
    return [dict(a=int(x), b=int(y), sum=int(x + y), ood=int(x + y >= 100 * (X + 1))) for x, y in zip(a, b)]


def world_heads(rng, mix):
    """Головы мира: своя часть переноса, свои веса операторов и своя таблица смещений; mix — доля «прочих» от операторов."""
    out = {}
    for h in HEADS:
        b0 = float(rng.uniform(-2.5, -1.0))
        offs = rng.choice(OFFSETS, size=6, replace=False)
        qv = rng.dirichlet(np.ones(6)) * 0.8
        prog = dict(eps=float(rng.uniform(0.15, 0.5)), q={int(d): float(v) for d, v in zip(offs, qv)}, q_rest=0.2, n_other=1,
                    features=['prop'], w=[b0, 1.0], w_round=[b0, 1.0])
        pi = rng.dirichlet(np.ones(len(CATALOG) + 1))
        out[h] = dict(prog=prog, fm1=dict(prog=dict(prog, eps=1.0), ops=list(CATALOG), pi=pi), tab1=dict(prog, eps=1.0), mix=float(mix))
    return out


def sample_head(hd, it, rng):
    """Ответ головы (смещение): опора переноса по её программе; «прочее» — оператор (доля mix) или смещение её таблицы."""
    dist = D2.program_dist(hd['prog'], it, True)
    u, acc = rng.random(), 0.0
    for y, p in dist.items():
        acc += p
        if u < acc:
            return y - it['sum']
    if rng.random() < hd['mix']:
        return PM.sample_m(hd['fm1'], it, rng)
    return D2.sample_program(hd['tab1'], it, rng)


def make_world(seed, n_con=400, n_test=2200, mix=0.5):
    """Мир: головы, построение {голова: смещения}, среды теста {имя: (задачи, {голова: смещения})}."""
    rng = np.random.default_rng(seed)
    heads = world_heads(rng, mix)
    con = [it for X in CON_X for it in items_env(X, n_con, rng)]
    offs_c = {h: np.array([sample_head(hd, it, rng) for it in con]) for h, hd in heads.items()}
    test = {}
    for X in TEST_X:
        its = items_env(X, n_test, rng)
        test[f'T_X{X}_p3'] = (its, {h: np.array([sample_head(hd, it, rng) for it in its]) for h, hd in heads.items()})
    return heads, con, offs_c, test


def swap_rows(er, rng):
    """Нуль М ≡ Т: в каждой задаче (строке) метки М и Т меняются местами с вероятностью 1/2 — одна монета на задачу для всех голов."""
    coin = rng.random(er['n']) < 0.5
    L = dict(er['L'])
    L['M'] = np.where(coin[:, None], er['L']['T'], er['L']['M'])
    L['T'] = np.where(coin[:, None], er['L']['M'], er['L']['T'])
    return dict(er, L=L)


def world_verdict(seed, B, n_con, n_test, mix, null=True):
    """Вся цепочка на одном мире: подбор программ, строки мер, (нуль — перестановка М и Т), бутстреп, правило m_M — как test_d4."""
    t0 = time.time()
    heads, con, offs_c, test = make_world(seed, n_con, n_test, mix)
    fits = PM.fit_family(con, offs_c, list(CATALOG))
    rng = np.random.default_rng([SEED_NULL, seed, 1])
    pts, boots, sds = {}, {}, {}
    for en, (its, offs) in sorted(test.items()):
        er = PM.env_rows(fits, its, offs, list(HEADS))
        if null:
            er = swap_rows(er, rng)
        pt, sd, reps = PM.env_measures(er, B, rng)
        pts[en], sds[en], boots[en] = pt['m_M'], sd['m_M'], reps['m_M']
    names = sorted(test)
    e = D2.family_rule(pts, boots, sds, names, 'two', True)
    return dict(seed=int(seed), verdict=e['verdict_rule'], mean=float(np.mean([pts[n] for n in names])), t=e['t_envs']['t'],
                points=[float(pts[n]) for n in names], seconds=round(time.time() - t0, 2))


def _run(x):
    return world_verdict(*x)


def main(a):
    dst = a[0]
    opt = {k: a[a.index(k) + 1] for k in ('--worlds', '--seed0', '--B', '--n-test', '--n-con', '--mix', '--workers') if k in a}
    workers = int(opt.get('--workers', 1))
    W, s0 = int(opt['--worlds']), int(opt['--seed0'])
    B, n_test, n_con, mix = int(opt.get('--B', 4000)), int(opt.get('--n-test', 2200)), int(opt.get('--n-con', 400)), float(opt.get('--mix', 0.5))
    import scipy
    out = dict(seed_null=SEED_NULL, seed0=s0, worlds=W, seeds=[s0, s0 + W - 1], B=B, n_test=n_test, n_con=n_con, mix=mix, workers=workers,
               versions=dict(python=platform.python_version(), numpy=np.__version__, scipy=scipy.__version__), runs=[])
    t0 = time.time()
    jobs = [(s0 + w, B, n_con, n_test, mix) for w in range(W)]

    def take(r):
        out['runs'].append(r)
        print(f"мир {r['seed']}: {r['verdict']} | среднее {r['mean']:+.5f} | t {r['t']:+.3f} | {r['seconds']} с", flush=True)
        if len(out['runs']) % 10 == 0 or len(out['runs']) == W:
            out['seconds'] = round(time.time() - t0, 1)
            out['seconds_per_world_wall'] = round(out['seconds'] / len(out['runs']), 2)
            out['decisive'] = sum(x['verdict'] in ('больше', 'меньше') for x in out['runs'])
            json.dump(out, open(dst, 'w', encoding='utf-8'), ensure_ascii=False, indent=1, default=float)
    if workers > 1:
        with cf.ProcessPoolExecutor(workers) as ex:
            for r in ex.map(_run, jobs):
                take(r)
    else:
        for x in jobs:
            take(_run(x))
    print('решающих вердиктов:', out['decisive'], 'из', W, '| секунд на мир (по часам задания):', out['seconds_per_world_wall'], flush=True)
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
