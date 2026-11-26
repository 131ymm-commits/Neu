#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""DISTILL-05 «ТОКЕН-ОПЕРАТОРЫ», короткая проверка (решение автора): доли масштабов «прочих» смещений по каждой голове на пятизначных
суммах. «Прочий» ответ — числовой, неверный, не потеря переносов (`explore_d4.classify`). Масштаб смещения d — наибольшая степень 10,
делящая |d| (explore_d5.scale): 0 — единицы, 1 — десятки, 2 — сотни.
  Мера головы в среде: Δ = s100 − s10 (доли масштабов 100 и 10 среди её «прочих»). Механизм «соседний кусок» у OLMo (куски по три цифры)
  предсказывает Δ > 0: первый кусок пятизначной суммы кончается разрядом сотен. Контраст C = s100(OLMo) − среднее s100 шести голов.
  Интервал среды — бутстреп по задачам (строки одни для всех голов); правило по средам — часть А (M4 среднего сред: точка ± z · ст. откл.
  повторов среднего) и часть Б (t по средам против t(1 − уровень; m − 1)), как distill02.family_rule, но с уровнем как параметром.
  Варианты меры (совет 80): 'star' — решающая Δ* на слое без переноса в разряды 1 и 2 (там −10 и −100 попадают в «прочие» одинаково);
  'old' — прежняя Δ по всем пятизначным суммам (−100 уходит в потерю переноса при переносе в сотни: s100 занижена, Δ смещена к «меньше»);
  'all' — Δ по всем неверным числовым ответам, вместе с потерей переноса (описательно). Решающий вариант — DECISIVE (константа PREREG).
  python3 scales_d5.py pilot ВЫХОД.json SPEC.json   — уже виденные пятизначные суммы: меры, мощность для 8 сред теста
  python3 scales_d5.py test ВЫХОД.json SPEC.json    — тест (константы PREREG)
SPEC: {"sets": {имя: [папки сборок]}}; учитываются только задачи с пятизначной суммой."""
import hashlib
import json
import os
import sys
import time

import numpy as np
from scipy.stats import norm, t as student_t

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(ROOT, 'experiments', '2026-11-19_DISTILL-04'))
import explore_d4 as XE  # noqa: E402
import explore_d5 as X5  # noqa: E402

D2 = XE.D2
OLMO = 'OLMo-2-0425-1B-Instruct'
HEADS = ('Falcon3-1B-Instruct', 'OLMo-2-0425-1B-Instruct', 'Qwen2.5-0.5B-Instruct', 'Qwen2.5-1.5B-Instruct', 'SmolLM2-1.7B-Instruct',
         'SmolLM2-360M-Instruct', 'TinyLlama-1.1B-Chat-v1.0')
N_DIGITS = 5
MIN_OTHER = 30                     # голова входит в среду, если у неё не меньше 30 «прочих» ответов
LEVEL = 0.0025                     # на сторону: Р1 OLMo (главное, HYPOTHESIS П1) и Р2; шесть контрольных голов (П2) — LEVEL / 6 (Бонферрони)
TEST_ENVS = tuple(f'T_X{x}_p3' for x in (119, 129, 149, 159, 179, 189, 199, 209))
B_TEST, SEED = 4000, 9_950_000
# PREREG §5–§6: правило активности по пилоту (gha_out/distill05_pilot/pilot.json; prereg_numbers_d5.py сверяет): True — решающее
DECISIVE = None                    # PREREG §4: 'star' или 'old' — по правилу выбора меры (prereg_numbers_d5.py)
RULES_ACTIVE = {'Р1:Falcon3-1B-Instruct': False, 'Р1:OLMo-2-0425-1B-Instruct': True, 'Р1:Qwen2.5-0.5B-Instruct': False,
                'Р1:Qwen2.5-1.5B-Instruct': False, 'Р1:SmolLM2-1.7B-Instruct': True, 'Р1:SmolLM2-360M-Instruct': False,
                'Р1:TinyLlama-1.1B-Chat-v1.0': False, 'Р2': False}


def level_of(key):
    """Уровень на сторону: Р1 OLMo и Р2 — LEVEL; Р1 шести контрольных голов — LEVEL / 6."""
    return LEVEL if key in ('Р2', f'Р1:{OLMO}') else LEVEL / 6


VARIANTS = ('star', 'old', 'all')


def in_stratum(it):
    """Слой без переноса в разряды десятков и сотен (совет 80): задаётся только по (a, b)."""
    return not (set(XE.carry_positions(it['a'], it['b'])) & {1, 2})


def rows(items, offs_by_head, variant='old'):
    """Задачи с пятизначной суммой (у 'star' — только слой без переноса); по головам — метка ответа меры («прочий»; у 'all' — любой
    неверный числовой) и масштаб смещения (−1 — не входит)."""
    keep = [i for i, it in enumerate(items) if len(str(it['sum'])) == N_DIGITS and (variant != 'star' or in_stratum(it))]
    oth = {h: np.zeros(len(keep), bool) for h in offs_by_head}
    sc = {h: np.full(len(keep), -1) for h in offs_by_head}
    take = ('other', 'lost') if variant == 'all' else ('other',)
    for h, o in offs_by_head.items():
        for j, i in enumerate(keep):
            if XE.classify(items[i], o[i]) in take:
                oth[h][j] = True
                sc[h][j] = X5.scale(o[i])
    return dict(n=len(keep), other=oth, scale=sc, variant=variant)


def shares(R, W):
    """Доли масштабов 1, 10, 100 среди «прочих» каждой головы при весах задач W (строки — точка или повторы бутстрепа)."""
    out = {}
    for h in R['other']:
        o = R['other'][h].astype(float)
        den = W @ o
        with np.errstate(invalid='ignore', divide='ignore'):
            out[h] = {k: (W @ (R['scale'][h] == k).astype(float)) / den for k in (0, 1, 2)}
            out[h]['ge3'] = (W @ (R['scale'][h] >= 3).astype(float)) / den
        out[h]['n_other'] = den
    return out


def env_measures(R, B, rng, heads):
    """Точка и повторы: Δ по головам и контраст C. Голова с < MIN_OTHER «прочих» в среде — NaN."""
    n = R['n']
    W = np.vstack([np.ones((1, n)), np.stack([np.bincount(rng.integers(0, n, n), minlength=n) for _ in range(B)]).astype(float)])
    S = shares(R, W)
    delta = {h: (S[h][2] - S[h][1]) if R['other'][h].sum() >= MIN_OTHER else np.full(B + 1, np.nan) for h in heads}
    six = [h for h in heads if h != OLMO and R['other'][h].sum() >= MIN_OTHER]
    c = (S[OLMO][2] - np.mean([S[h][2] for h in six], axis=0)) if (R['other'][OLMO].sum() >= MIN_OTHER and six) else np.full(B + 1, np.nan)
    sh = {h: {str(k): float(S[h][k][0]) for k in (0, 1, 2)} | dict(ge3=float(S[h]['ge3'][0]), n_other=int(R['other'][h].sum())) for h in heads}
    return dict(delta={h: v for h, v in delta.items()}, contrast=c, shares=sh)


def rule(points, boots, level, part_b=True):
    """Правило по средам (как distill02.family_rule): А — точка среднего сред ± z(уровень) · ст. откл. повторов среднего; Б — t по средам
    против t(1 − уровень; m − 1). «больше» / «меньше» — А и Б в одну сторону; только А — «в среднем этих сред: …»; иначе «не решено»."""
    names = [n for n in points if np.isfinite(points[n])]
    m = len(names)
    if m < 2:
        return dict(verdict='не решено', m=m)
    x = np.array([points[n] for n in names])
    bm = np.nanmean(np.stack([boots[n] for n in names]), axis=0)
    mean, sd = float(x.mean()), float(np.nanstd(bm, ddof=1))
    z = float(norm.ppf(1 - level))
    lo, hi = mean - z * sd, mean + z * sd
    tt = float(mean / (x.std(ddof=1) / np.sqrt(m))) if x.std(ddof=1) > 0 else float('nan')
    crit = float(student_t.ppf(1 - level, m - 1))
    a_up, a_dn = lo > 0, hi < 0
    b_up, b_dn = (tt > crit, tt < -crit) if part_b else (True, True)
    if a_up and b_up:
        v = 'больше'
    elif a_dn and b_dn:
        v = 'меньше'
    elif a_up or a_dn:
        v = 'в среднем этих сред: ' + ('больше' if a_up else 'меньше') + ' (на новые среды не переносится)'
    else:
        v = 'не решено'
    return dict(verdict=v, mean=mean, ci=[lo, hi], boot_sd=sd, t=tt, crit=crit, z=z, m=m, level=level, by_env={n: float(points[n]) for n in names})


def power(points, sds, m, level, n=200_000, seed=SEED + 7):
    """Модель «новая среда» (как ocdiv4.power_entry4): точка среды ~ N(μ, τ² + s²); μ, τ, s — из пилота."""
    x, sp = np.asarray(points, float), np.asarray(sds, float)
    ok = np.isfinite(x) & np.isfinite(sp)
    x, sp = x[ok], sp[ok]
    if len(x) < 2:
        return None
    s = float(np.sqrt(np.mean(sp ** 2)))
    tau = float(np.sqrt(max(0.0, x.var(ddof=1) - s ** 2)))
    g = np.random.default_rng(seed)
    X = g.normal(x.mean(), np.sqrt(tau ** 2 + s ** 2), size=(n, m))
    mean, sd = X.mean(1), X.std(1, ddof=1)
    h = norm.ppf(1 - level) * s / np.sqrt(m)
    tt = mean / (sd / np.sqrt(m))
    crit = student_t.ppf(1 - level, m - 1)
    up, dn = (mean - h > 0) & (tt > crit), (mean + h < 0) & (tt < -crit)
    return dict(mu=float(x.mean()), tau=tau, s=s, n_envs=int(len(x)), more=float(up.mean()), less=float(dn.mean()), decisive=float(up.mean() + dn.mean()))


def load(dirs):
    out = []
    for d in dirs:
        out += list(D2.load_merged(d).items())
    return out


def code_hashes():
    h = lambda p: hashlib.sha256(open(p, 'rb').read()).hexdigest()   # noqa: E731
    return {os.path.basename(p): h(p) for p in (os.path.abspath(__file__), X5.__file__, XE.__file__, D2.__file__)}


def measure_sets(spec, B, heads):
    """По каждой среде и варианту меры: точка и повторы бутстрепа (свой поток зёрен на вариант: ключ «набор:среда:номер:вариант»)."""
    res = {}
    for name, dirs in spec['sets'].items():
        for k, (en, env) in enumerate(load(dirs)):
            items, offs = D2.env_table(env)
            hv = {h: offs[h] for h in heads if h in offs}
            key = f'{name}:{en}:{k}'
            var = {}
            for v in VARIANTS:
                R = rows(items, hv, v)
                if R['n'] == 0:
                    continue
                rng = np.random.default_rng([SEED, int.from_bytes(f'{key}:{v}'.encode(), 'little') % (2 ** 32)])
                var[v] = dict(n=R['n'], **env_measures(R, B, rng, [h for h in heads if h in R['other']]))
            if var:
                res[key] = dict(env=en, **var)
    return res


def env_view(v):
    return dict(n=v['n'], shares=v['shares'], delta={h: float(v['delta'][h][0]) for h in v['delta']}, contrast=float(v['contrast'][0]))


def main(a):
    t0 = time.time()
    mode, dst, spec = a[0], a[1], json.load(open(a[2], encoding='utf-8'))
    heads = list(HEADS)
    if mode == 'test':
        assert RULES_ACTIVE is not None and DECISIVE in ('star', 'old'), 'константы PREREG не записаны: анализ теста не идёт'
    B = int(spec.get('B', B_TEST if mode == 'test' else 400))
    M = measure_sets(spec, B, heads)
    if mode == 'test':
        names = {v['env']: k for k, v in M.items()}
        miss = [n for n in TEST_ENVS if n not in names]
        assert not miss, f'в тесте нет сред: {miss}'
        assert len(names) == len(M), 'одна среда теста дважды'
        M = {n: M[names[n]] for n in TEST_ENVS}
    out = dict(mode=mode, code=code_hashes(), B=B, seed=SEED, level=LEVEL, min_other=MIN_OTHER, decisive=DECISIVE,
               envs={k: dict(env=v['env'], **{var: env_view(v[var]) for var in VARIANTS if var in v}) for k, v in M.items()})
    keys = [f'Р1:{h}' for h in heads] + ['Р2']

    def series(var, key):
        pick = (lambda x: x['contrast']) if key == 'Р2' else (lambda x: x['delta'].get(key[3:]))
        return {n: pick(v[var]) for n, v in M.items() if var in v and pick(v[var]) is not None}
    if mode == 'pilot':
        out['power'] = {}
        for var in ('star', 'old'):
            out['power'][var] = {}
            for key in keys:
                ser = series(var, key)
                out['power'][var][key] = power([float(x[0]) for x in ser.values()], [float(np.nanstd(x[1:], ddof=1)) for x in ser.values()],
                                               len(TEST_ENVS), level_of(key))
                e = out['power'][var][key]
                print(var, key, {kk: (round(vv, 4) if isinstance(vv, float) else vv) for kk, vv in (e or {}).items()}, flush=True)
    else:
        out['rules'] = {}
        for var in VARIANTS:
            out['rules'][var] = {}
            for key in keys:
                ser = series(var, key)
                e = rule({n: float(x[0]) for n, x in ser.items()}, {n: x[1:] for n, x in ser.items()}, level_of(key))
                out['rules'][var][key] = dict(e, active=bool(var == DECISIVE and RULES_ACTIVE.get(key, True)))
                print(var, key, '|', e['verdict'], '| среднее', round(e.get('mean', float('nan')), 4), flush=True)
    out['seconds'] = round(time.time() - t0, 1)
    json.dump(out, open(dst, 'w', encoding='utf-8'), ensure_ascii=False, indent=1, default=float)
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
