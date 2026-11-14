#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""SPECTRUM-02: мощность до прогона → power.json. Оценка Монте-Карло по пилоту (6 блоков, зёрна 159000+; тест — 20
блоков, зёрна 151000+). Модель: блоки теста — выборка с возвращением из блоков пилота (величины блока целиком).
Правила (PREREG §5): N = 30 блоков, знаковое правило K = 23 из 30 (P1, P2, P3); P4 — пул-показатель α_AB, ДИ 99 %
(бутстреп по блокам) строго внутри полосы (1/3; 2/3): отличает λ^(−1/2) от λ^(−1/3) и λ^(−2/3) (урок ERRORS № 146).
Сначала считалось N = 20 и полоса [0,40; 0,60]: мощность P4 по пилоту 0,217 — мало; затем сравнены N = 20 и 30 при
полосе (1/3; 2/3): по пилоту 0,872 и 0,967, осторожно 0,632 и 0,895 (оценка Монте-Карло; выбрано N = 30).
Сценарии:
  «по пилоту» — величины пилота как есть;
  «осторожный» — эффекты P1–P3 вдвое меньше (каждый блок сдвинут на половину среднего пилота, разброс тот же),
     для P4 истинный пул-показатель 0,45 (вместо пилотного) и разброс ln t в 1,5 раза больше.
Ложные уровни: P1–P3 — P(X ≥ 23 | n = 30, p = ½) (номинальный нуль знака); P4 — доля «подтверждено» при истинном
показателе на границе полосы (1/3 и 2/3, берётся большая), тот же разброс, что «по пилоту».
Веса (заранее): подтверждение — log₂(мощность «осторожного» / ложный уровень); опровержение —
log₂((1 − мощность «по пилоту»)/(1 − ложный уровень)); «не решено» — 0. P3 веса не несёт: та же группа опор, что P2."""
import json
import os
from math import comb, log2

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
N, K = 30, 23
BAND = (1 / 3, 2 / 3)
CI_LEVEL = 99.0
AB = ['A0', 'AB13', 'AB23', 'AB1']
sf = lambda k, n, p: sum(comb(n, i) * p ** i * (1 - p) ** (n - i) for i in range(k, n + 1))   # noqa: E731
ALPHA_SIGN = sf(K, N, 0.5)


def pooled_alpha(lt, ll):
    """lt, ll — (повторы, блоки, 4): ln t и ln λ_max; α = −наклон ln(медиана t) на ln(медиана λ)."""
    mt, ml = np.median(lt, axis=-2), np.median(ll, axis=-2)          # (повторы, 4)
    x = ml - ml.mean(-1, keepdims=True)
    y = mt - mt.mean(-1, keepdims=True)
    return -(x * y).sum(-1) / (x * x).sum(-1)


def p4_power(lt, ll, g, reps=1000, inner=1000, slope_to=None, noise=1.0):
    """Доля «подтверждено» по P4 при выборке N блоков из пилота."""
    nb = lt.shape[0]
    base = pooled_alpha(lt[None], ll[None])[0]
    lt = lt.copy()
    xc = ll - ll.mean(1, keepdims=True)
    if noise != 1.0:                                                   # разброс ln t между блоками × noise
        lt = lt.mean(0, keepdims=True) + noise * (lt - lt.mean(0, keepdims=True))
    if slope_to is not None:                                           # сдвиг наклона: ln t ← ln t − (α* − α̂)·(ln λ − среднее)
        lt = lt - (slope_to - base) * xc
    ok = 0
    for _ in range(reps):
        idx = g.integers(0, nb, N)
        LT, LL = lt[idx], ll[idx]
        bi = g.integers(0, N, (inner, N))
        a = pooled_alpha(LT[bi], LL[bi])
        lo, hi = np.percentile(a, [(100 - CI_LEVEL) / 2, 100 - (100 - CI_LEVEL) / 2])
        ok += BAND[0] <= lo and hi <= BAND[1]
    return ok / reps


def sign_power(v, g, shift=0.0, reps=20000):
    v = np.asarray(v) - shift
    idx = g.integers(0, len(v), (reps, N))
    return float(((v[idx] > 0).sum(1) >= K).mean())


def main():
    a = json.load(open(os.path.join(HERE, 'pilot', 'pilot_6_analysis.json'), encoding='utf-8'))
    t, lm = a['descr']['t_align'], a['descr']['lam_max']
    nb = len(t['A0'])
    v1 = [np.log(t['A0'][b] / t['A1'][b]) for b in range(nb)]
    v2 = [np.log(t['A1'][b] / t['AB1'][b]) for b in range(nb)]
    v3 = a['P3']['diff']
    lt = np.log(np.array([[t[c][b] for c in AB] for b in range(nb)]))
    ll = np.log(np.array([[lm[c][b] for c in AB] for b in range(nb)]))
    g = np.random.default_rng(404)
    pw = {}
    for name, v in (('P1', v1), ('P2', v2), ('P3', v3)):
        pw[name] = {'по пилоту': sign_power(v, g), 'осторожный': sign_power(v, g, shift=np.mean(v) / 2)}
    pw['P4'] = {'по пилоту': p4_power(lt, ll, g), 'осторожный': p4_power(lt, ll, g, slope_to=0.45, noise=1.5)}
    fl4 = max(p4_power(lt, ll, g, slope_to=BAND[0]), p4_power(lt, ll, g, slope_to=BAND[1]))
    false = {'P1': ALPHA_SIGN, 'P2': ALPHA_SIGN, 'P3': ALPHA_SIGN, 'P4': fl4}
    bits = {}
    for p in ('P1', 'P2', 'P4'):
        bits[p] = {'confirm': log2(max(pw[p]['осторожный'], 1e-9) / max(false[p], 1e-4)),
                   'refute': min(0.0, log2(max(1 - pw[p]['по пилоту'], 1e-4) / (1 - false[p])))}
    bits['P3'] = {'confirm': 0.0, 'refute': 0.0, 'note': 'та же группа опор, что P2'}
    out = dict(N=N, K=K, band=BAND, ci_level=CI_LEVEL, pilot_blocks=nb,
               pilot=dict(P1_ln_ratio=v1, P2_ln_ratio=v2, P3_diff=v3, P4_pooled_alpha=float(pooled_alpha(lt[None], ll[None])[0])),
               false_level=false, power=pw, weights_bits=bits,
               series_false_level_weighted=float(false['P1'] + false['P2'] + false['P4']),
               note='оценка Монте-Карло; P4 при истинном показателе на границе полосы — доля ложного «подтверждено»')
    json.dump(out, open(os.path.join(HERE, 'power.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print(json.dumps({k: out[k] for k in ('false_level', 'power', 'weights_bits', 'series_false_level_weighted')}, ensure_ascii=False, indent=1))
    print('пул-показатель пилота α_AB:', out['pilot']['P4_pooled_alpha'])


if __name__ == '__main__':
    main()
