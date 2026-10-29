#!/usr/bin/env python3
"""SCORE-02: мощность предсказаний PREREG §4 по пилоту (20 задач, 5 вызовов на задачу; evals/pilot_<модель>.json) и веса в битах (§6).
Для каждого предсказания: пилотный контраст μ и SD бутстрепа задач пилота (B = 4000); SE теста из n задач — SD × √(20 / n).
  в точке — Φ(направление·μ / SE − 1,96); с неопределённостью пилота — среднее этой величины по бутстрепу пилота (μ_b вместо μ).
Нормальное приближение (вердикт теста — по бутстреп-интервалу).
Сводный (одна часть) — «подтверждено в обеих выборках»: в точке Φ_осн(μ)·Φ_повт(μ); с неопределённостью — среднее по бутстрепу
пилота произведения Φ_осн(μ_b)·Φ_повт(μ_b): эффект у двух выборок общий (LENSES-1, L2-3; было произведение средних — занижало).
Вес (§6; правило заменяет соглашение SCORE-01 — проверка отчёта SCORE-01, находка 11): основная выборка и повтор — одна проверка
с совместным исходом. P — меньшая из двух мощностей «в обеих» (в точке и с неопределённостью), не больше 0,999; α — 0,025 (одна
выборка: систематическая ошибка прошла бы обе). Подтверждено в обеих — log₂(P / α); любой другой исход по данным —
log₂((1 − P) / (1 − α)), 1 − P не меньше 0,001; технический исход (контекст, потери) — 0 бит (LENSES-1, L3-3).
Проверки (почти арифметика) и разведка — мощность считается, веса нет.
  python3 power_score02.py   → pilot_power.json и печать (журнал — run/pilot_power.log)"""
import json
import math
import os
import sys
from statistics import NormalDist

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import score02_lib as L  # noqa: E402
from analyze_score02 import PRED, COMP  # noqa: E402

Z = NormalDist().inv_cdf(0.975)
PHI = NormalDist().cdf
B = 4000
N_TEST = dict(main=100, rep=59)
ALPHA = 0.025
f = lambda x, d=3: f'{x:.{d}f}'.replace('.', ',').replace('-', '−')


def main():
    out = dict(B=B, n_test=N_TEST, alpha=ALPHA, preds={}, comps={})
    log = []
    draws = {}
    for m in ('opus', 'haiku'):
        J = L.load(f'pilot_{m}')
        tasks = sorted(J)
        preds = [q for q in PRED if q['model'] == m]
        M = L.measures(J, tasks)
        BS = L.bootstrap(J, tasks, [(q['measure'], q['a'], q['b']) for q in preds], B=B, name=f'power|{m}')
        for q in preds:
            sp = (q['measure'], q['a'], q['b'])
            mu = L.contrast(M, sp)
            xs = BS[sp]
            mb = sum(xs) / len(xs)
            sd = math.sqrt(sum((x - mb) ** 2 for x in xs) / (len(xs) - 1))
            se = {smp: sd * math.sqrt(len(tasks) / n) for smp, n in N_TEST.items()}
            phi = lambda x, smp, d=q['dir'], se=se: PHI(d * x / se[smp] - Z)   # значения по умолчанию: без них лямбда возьмёт q и se последней итерации
            pw = {smp: dict(point=phi(mu, smp), unc=sum(phi(x, smp) for x in xs) / len(xs)) for smp in N_TEST}
            draws[q['id']] = (mu, xs, phi)
            lo, hi = L.ci95(xs)
            out['preds'][q['id']] = dict(model=m, measure=q['measure'], a=q['a'], b=q['b'], dir=q['dir'], kind=q['kind'], family=q['family'],
                                         pilot_mean=mu, pilot_sd_boot=sd, pilot_tasks=len(tasks), z_pilot=mu / sd if sd > 0 else None, power=pw,
                                         ci95_pilot=[lo, hi])
            log.append(f"{q['id']:5s} {q['measure']} {q['a']} − {q['b']} {'> 0' if q['dir'] > 0 else '< 0'} ({q['kind']}): пилот {f(mu)} [{f(lo)}; "
                       f"{f(hi)}], SD бутстрепа {f(sd)} ({f(abs(mu) / sd if sd else 0, 2)} SD); мощность — основная {f(pw['main']['point'], 3)} "
                       f"в точке, {f(pw['main']['unc'], 3)} с неопределённостью; повтор {f(pw['rep']['point'], 3)} и {f(pw['rep']['unc'], 3)}")
    for c, parts in COMP.items():
        mu, xs, phi = draws[parts[0]]
        point = phi(mu, 'main') * phi(mu, 'rep')
        unc = sum(phi(x, 'main') * phi(x, 'rep') for x in xs) / len(xs)
        Pw = min(point, unc, 0.999)
        w_ok = math.log2(Pw / ALPHA)
        w_no = math.log2(max(1 - Pw, 0.001) / (1 - ALPHA))
        out['comps'][c] = dict(parts=parts, power_both_point=point, power_both_unc=unc, power_both=min(point, unc), bits_confirmed=w_ok, bits_not=w_no,
                               bits_technical=0.0)
        log.append(f'{c}: мощность «подтверждено в обеих» — {f(point, 3)} в точке, {f(unc, 3)} с неопределённостью; вес — {f(w_ok, 2)} бита при '
                   f'подтверждении в обеих, {f(w_no, 2)} при другом исходе по данным, 0 при техническом')
    json.dump(out, open(os.path.join(HERE, 'pilot_power.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    open(os.path.join(HERE, 'run', 'pilot_power.log'), 'w', encoding='utf-8').write('\n'.join(log) + '\n')
    print('\n'.join(log))


if __name__ == '__main__':
    main()
