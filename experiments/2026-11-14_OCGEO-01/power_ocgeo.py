#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""OCGEO-01: мощность до прогона по пилоту 1 → power.json. Оценка Монте-Карло.
Правило P1 (PREREG §5): разность ИОИ(GEO) − ИОИ(AGREE) на задачах OOD теста; ДИ 95 % — бутстреп по задачам OOD
(калибровка по ID теста закреплена). Гипотеза описи: разность < 0 (GEO лучше). Подтверждено — верхняя граница ДИ < 0;
опровергнуто — нижняя граница > 0; иначе «не решено».
Модель: задачи OOD теста — выборка с возвращением из задач OOD пилота (пары исходов выбранной головы и заявки у обоих
оценщиков — парно). Размер — число задач OOD теста (из разбиения в ocgeo_extract.py).
Сценарии: «по пилоту» — как есть; «осторожный» — разность вдвое меньше (каждой задаче GEO добавляется сдвиг заявки
к AGREE на половину разности средних) — оценка грубая, для сведения.
ДИ 99 % (после пересмотра 14.11: с ДИ 95 % ложный уровень серии из трёх правил был бы 0,075). Ложный уровень каждого
исхода — 0,005. Веса (заранее): log₂(мощность «осторожного» / 0,005) для исхода, который даёт данные."""
import json
import os
import sys

import numpy as np
from sklearn.isotonic import IsotonicRegression

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import analyze_ocgeo as A  # noqa: E402

GEO_F, GEO_K = 0.25, 50          # лучшая по ИОИ настройка GEO на пилоте (сетка 4 × 4) — выбор в пользу GEO


def per_problem(d, heads, base, nb, f, k):
    S, corr, rng_id = A.scores(d, heads, base, nb, f, k)
    tgt = ~rng_id
    cols = np.nonzero(tgt)[0]
    out = {}
    for e in ('GEO', 'AGREE', 'CONF', 'GEO0', 'INPUT'):
        M = S[e]
        cal = np.zeros_like(M, dtype=float)
        for i in range(len(heads)):
            iso = IsotonicRegression(out_of_bounds='clip', y_min=0, y_max=1).fit(M[i][rng_id], corr[i][rng_id].astype(float))
            cal[i] = iso.predict(M[i])
        pick = cal[:, tgt].argmax(0)
        out[e] = (corr[pick, cols].astype(float), cal[pick, cols])
    return out


def ioi(t, c):
    T, C = t.mean(-1), c.mean(-1)
    return (1 - T) + np.maximum(0, C - T)


def main():
    d, heads, base, nb = A.load(os.path.join(HERE, 'pilot1', 'out'))
    v = per_problem(d, heads, base, nb, GEO_F, GEO_K)
    tg, cg = v['GEO']
    ta, ca = v['AGREE']
    n_pilot = len(tg)
    # число задач OOD теста — по разбиению ocgeo_extract.py
    pairs = [(a, b) for a in range(10, 100) for b in range(10, 100)]
    ex = {(67, 68), (56, 67)}                       # пары из подсказки (пилот 0), исключены
    pairs = [p for p in pairs if p not in ex]
    perm = np.random.default_rng(7_200_000).permutation(len(pairs))
    test = perm[int(round(0.3 * len(pairs))):]
    n_test_ood = int(sum(pairs[i][0] + pairs[i][1] >= 100 for i in test))
    g = np.random.default_rng(707)
    diff_pilot = float(ioi(tg, cg) - ioi(ta, ca))

    def sim(shift_frac, reps=2000, inner=1000):
        conf = ref = 0
        cg2 = cg - shift_frac * (cg.mean() - ca.mean())         # «осторожный»: заявка GEO ближе к AGREE
        for _ in range(reps):
            j = g.integers(0, n_pilot, n_test_ood)
            a1, a2, b1, b2 = tg[j], cg2[j], ta[j], ca[j]
            jj = g.integers(0, n_test_ood, (inner, n_test_ood))
            dd = ioi(a1[jj], a2[jj]) - ioi(b1[jj], b2[jj])
            lo, hi = np.percentile(dd, [0.5, 99.5])
            conf += hi < 0
            ref += lo > 0
        return conf / reps, ref / reps
    c1, r1 = sim(0.0)
    c2, r2 = sim(0.5)

    # P2: ИОИ(AGREE) − ИОИ(CONF), то же устройство (500 × 500); «осторожный» — разность вдвое меньше (сдвиг заявки CONF)
    tc, cc = v['CONF']

    def sim2(shift_frac, reps=500, inner=500):
        conf = ref = 0
        d0 = ioi(ta, ca) - ioi(tc, cc)
        cc2 = cc + shift_frac * d0                                # сдвиг заявки CONF уменьшает |разность| примерно вдвое
        for _ in range(reps):
            j = g.integers(0, n_pilot, n_test_ood)
            jj = g.integers(0, n_test_ood, (inner, n_test_ood))
            dd = ioi(ta[j][jj], ca[j][jj]) - ioi(tc[j][jj], cc2[j][jj])
            lo, hi = np.percentile(dd, [0.5, 99.5])
            conf += hi < 0
            ref += lo > 0
        return conf / reps, ref / reps
    p2c1, p2r1 = sim2(0.0)
    p2c2, p2r2 = sim2(0.5)

    # P3: средняя разность AUROC (GEO − GEO0) — нормальное приближение: ДИ теста = ДИ пилота × √(n_пилот / n_тест)
    S, corr, rng_id = A.scores(d, heads, base, nb, GEO_F, GEO_K)
    cols = np.nonzero(~rng_id)[0]
    def md(ix):
        vals = [A.auroc(S['GEO'][i][cols][ix], corr[i][cols][ix]) - A.auroc(S['GEO0'][i][cols][ix], corr[i][cols][ix]) for i in range(len(heads))]
        return float(np.mean(vals))
    est = md(np.arange(len(cols)))
    bs = [md(g.integers(0, len(cols), len(cols))) for _ in range(400)]
    se_test = float(np.std(bs) * np.sqrt(n_pilot / n_test_ood))
    from math import erf, sqrt
    Phi = lambda z: 0.5 * (1 + erf(z / sqrt(2)))           # noqa: E731
    p3 = {'по пилоту': Phi(est / se_test - 2.576), 'осторожный': Phi(est / 2 / se_test - 2.576)}
    lg = lambda pw: float(np.log2(max(pw, 1e-3) / 0.005)) if pw > 0 else 0.0     # noqa: E731
    out = dict(geo_setting=dict(f=GEO_F, k=GEO_K), n_pilot_ood=n_pilot, n_test_ood=n_test_ood, diff_pilot=diff_pilot,
               pilot_ioi={e: float(ioi(*v[e])) for e in v},
               power={'по пилоту': dict(confirm=c1, refute=r1), 'осторожный': dict(confirm=c2, refute=r2)},
               false_level=0.005,
               weights_bits=dict(confirm=lg(c2), refute=lg(r2)),
               P2=dict(diff_pilot=float(ioi(ta, ca) - ioi(tc, cc)),
                       power={'по пилоту': dict(confirm=p2c1, refute=p2r1), 'осторожный': dict(confirm=p2c2, refute=p2r2)},
                       weights_bits=dict(confirm=lg(p2c2), refute=lg(p2r2))),
               P3=dict(diff_pilot=est, se_test=se_test, power=p3, weights_bits=dict(confirm=lg(p3['осторожный'])),
                       note='нормальное приближение по бутстрепу пилота (400 повторов)'),
               series_false_level=0.005 * 3,
               note='оценка Монте-Карло (P1: 2000 × 1000; P2: 500 × 500); вес — по «осторожному» сценарию для исхода, который даёт данные; '
                    'ложный уровень каждого правила — 0,005 (одна сторона ДИ 99 %), серии — не выше 0,015')
    json.dump(out, open(os.path.join(HERE, 'power.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print(json.dumps(out, ensure_ascii=False, indent=1))


if __name__ == '__main__':
    main()
