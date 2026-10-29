#!/usr/bin/env python3
"""SCORE-02: мощность предсказаний PREREG §4 по пилоту (20 задач, 5 вызовов на задачу; evals/pilot_<модель>.json) и веса в битах (§6).
Для каждой части: пилотный контраст μ и SD бутстрепа задач пилота (B = 4000); SE теста n задач — SD × √(20 / n).
  в точке — Φ(направление·μ / SE − 1,96); с неопределённостью пилота — среднее этой величины по бутстрепу пилота (μ_b вместо μ).
Нормальное приближение (вердикт теста — по бутстреп-интервалу). Сводный — одна часть, его мощность — мощность части.
Вес (§6; правило заменяет соглашение SCORE-01 — проверка отчёта SCORE-01, находка 11): основная выборка и повтор — одна проверка
с совместным исходом. P — меньшая из двух мощностей «в обеих выборках» (произведение по 100 и 59 задачам, в точке и с
неопределённостью); α — 0,025 (одна выборка: систематическая ошибка прошла бы обе). Подтверждено в обеих — log₂(P / α);
любой другой исход — log₂((1 − P) / (1 − α)), 1 − P не меньше 0,001.
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
            pw = {}
            for smp, n in N_TEST.items():
                se = sd * math.sqrt(len(tasks) / n)
                pw[smp] = dict(point=PHI(q['dir'] * mu / se - Z), unc=sum(PHI(q['dir'] * x / se - Z) for x in xs) / len(xs))
            out['preds'][q['id']] = dict(model=m, measure=q['measure'], a=q['a'], b=q['b'], dir=q['dir'], family=q['family'],
                                         pilot_mean=mu, pilot_sd_boot=sd, pilot_tasks=len(tasks), z_pilot=mu / sd if sd > 0 else None, power=pw,
                                         ci95_pilot=[L.pct(xs, 0.025), L.pct(xs, 0.975)])
            log.append(f"{q['id']:5s} {q['measure']} {q['a']} − {q['b']} {'> 0' if q['dir'] > 0 else '< 0'}: пилот {f(mu)} [{f(L.pct(xs, 0.025))}; "
                       f"{f(L.pct(xs, 0.975))}], SD бутстрепа {f(sd)} ({f(abs(mu) / sd if sd else 0, 2)} SD); мощность — основная {f(pw['main']['point'], 3)} "
                       f"в точке, {f(pw['main']['unc'], 3)} с неопределённостью; повтор {f(pw['rep']['point'], 3)} и {f(pw['rep']['unc'], 3)}")
    for c, parts in COMP.items():
        p = out['preds'][parts[0]]['power']
        both = min(p['main']['point'] * p['rep']['point'], p['main']['unc'] * p['rep']['unc'])
        Pw = min(both, 0.999)
        w_ok = math.log2(Pw / ALPHA)
        w_no = math.log2(max(1 - Pw, 0.001) / (1 - ALPHA))
        out['comps'][c] = dict(parts=parts, power_both=both, bits_confirmed=w_ok, bits_not=w_no)
        log.append(f'{c}: мощность «подтверждено в обеих» {f(both, 3)}; вес — {f(w_ok, 2)} бита при подтверждении в обеих, {f(w_no, 2)} иначе')
    json.dump(out, open(os.path.join(HERE, 'pilot_power.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    open(os.path.join(HERE, 'run', 'pilot_power.log'), 'w', encoding='utf-8').write('\n'.join(log) + '\n')
    print('\n'.join(log))


if __name__ == '__main__':
    main()
