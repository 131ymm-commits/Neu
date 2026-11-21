#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""DISTILL-02: мощность правил PREREG по пилоту 3 (gha_out/distill02_pilot3/pilot3.json; меры — по совету 74) с тем числом сред и
частями, какие будут в тесте; модель «новая среда» (`ocdiv4.power_entry4`), 200 000 наборов. Пишет prereg_power_d2.json и печатает
таблицу для PREREG.
Правило активности (PREREG §5; совет 74):
  1. решающая мощность не меньше POWER_MIN = 0,2 и при τ пилота, и при τ из верхней границы — одно правило для всех;
  2. Р2-Л и Р3-Т — описательно по решению совета 74 (Р2-Л — ожидание «m2 < 0,5» в калибровку);
  3. из Р4-Т (программа − B1) и Р4Ф-Т (программа − Φ-база) на new5 решает Р4Ф-Т, если он проходит п. 1; иначе Р4-Т, если проходит
     п. 1 (тогда его гипотеза — «программа знает места переноса лучше частот», вес в реестре — малый); второй — описательно.
  python3 prereg_power_d2.py"""
import json
import os
import sys

X = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(X))
sys.path.insert(0, X)
import distill02 as D  # noqa: E402

SRC = 'gha_out/distill02_pilot3/pilot3.json'
# правило → (набор пилота 3, число сред в тесте); мера, вид, часть Б и сдвиг — из distill02.RULES. Р4 и Р4Ф — заменитель: программы по
# средам X = 19–49 пилота OCDIV-04, проверка на X = 59–89 теста OCDIV-04 (без экстраполяции по разряду; new5 — те же разряды 1–3)
SOURCE = {'Р1-Т': ('T_test3', 8), 'Р1-Л': ('L_test3', 3), 'Р1Ф-Т': ('T_test3', 8), 'Р1Ф-Л': ('L_test3', 3), 'Р2-Т': ('T_test3', 8),
          'Р2-Л': ('L_test3', 3), 'Р3-Т': ('T_test3', 8), 'Р3-Л': ('L_test3', 3), 'Р4-Т': ('T_transfer', 3), 'Р4Ф-Т': ('T_transfer', 3)}
COUNCIL_DESCR = ('Р2-Л', 'Р3-Т')                                   # совет 74, п. 5


def decisive(e, kind, key='power'):
    return (e[key]['confirm'] + e[key]['refute']) if kind == 'two' else e[key]['confirm']


def active_rules(rules):
    """Правило активности PREREG §5 по записям мощности {правило: {decisive, decisive_tau_hi}}."""
    passes = {r: bool(e['decisive'] >= D.POWER_MIN and e['decisive_tau_hi'] >= D.POWER_MIN) for r, e in rules.items()}
    act = {r: (passes[r] and r not in COUNCIL_DESCR) for r in rules}
    if passes['Р4Ф-Т']:
        act['Р4-Т'] = False
    else:
        act['Р4Ф-Т'] = False
    return act, passes


def main():
    P = json.load(open(os.path.join(ROOT, SRC), encoding='utf-8'))
    assert P['lam'] == D.LAMBDA and P['phase'] == 'pilot3', 'пилот 3 посчитан не с той смесью'
    out = {}
    for rule, (fam, ph, meas, kind, part_b, shift) in D.RULES.items():
        src, m = SOURCE[rule]
        envs = P['sets'][src]['envs']
        pts = [envs[n]['point'][meas] for n in sorted(envs)]
        sds = [envs[n]['sd'][meas] for n in sorted(envs)]
        e = D.power_rule(pts, sds, 1.0, m, part_b, shift)
        e.update(decisive=decisive(e, kind), decisive_tau_hi=decisive(e, kind, 'power_tau_hi'), source=src, m=m)
        out[rule] = e
    act, passes = active_rules(out)
    for r in out:
        out[r].update(passes=passes[r], active=act[r])
    # Р2-Л — в калибровку: P(среднее m2 по 3 средам < 0,5) в той же модели «новая среда» (нормальное приближение)
    from scipy.stats import norm
    e = out['Р2-Л']
    mu = e['mu'] + D.SHARE_MIN                                    # power_rule считает от m2 − 0,5
    sd_mean = ((e['tau'] ** 2 + e['s_test'] ** 2) / e['m']) ** 0.5
    sd_hi = ((e['tau_hi'] ** 2 + e['s_test'] ** 2) / e['m']) ** 0.5
    p2l = dict(mu_m2=mu, p_below=float(norm.cdf((D.SHARE_MIN - mu) / sd_mean)), p_below_tau_hi=float(norm.cdf((D.SHARE_MIN - mu) / sd_hi)))
    # общий ложный уровень серии (§7) — для выбранной ветви и для другой ветви выбора Р4 / Р4Ф (формалист, совет 74)
    def fw(a):
        n1 = sum(1 for r, on in a.items() if on and D.RULES[r][3] == 'pos')
        n2 = sum(1 for r, on in a.items() if on and D.RULES[r][3] == 'two')
        return dict(n_one_sided=n1, n_two_sided=n2, false_confirm=(n1 + 2 * n2) * D.LEVEL, false_any=(2 * n1 + 2 * n2) * D.LEVEL)
    other = dict(act)
    if passes['Р4Ф-Т'] and passes['Р4-Т']:
        other['Р4Ф-Т'], other['Р4-Т'] = act['Р4-Т'], act['Р4Ф-Т']
    fwer = dict(chosen=fw(act), other_branch=fw(other))
    json.dump(dict(source=SRC, power_min=D.POWER_MIN, council_descriptive=list(COUNCIL_DESCR), rules=out, active=act, r2l_calibration=p2l, fwer=fwer),
              open(os.path.join(X, 'prereg_power_d2.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1, default=float)

    def g(x, d=3):
        return '—' if x is None else f'{x:.{d}f}'.replace('.', ',')

    def f(x, d=4):
        return '—' if x is None else f'{x:+.{d}f}'.replace('-', '−').replace('.', ',')
    print('| Правило | набор пилота 3 | сред в тесте | мера | вид | части | μ | τ | s | часть А | часть Б | решающая | при τ из верхней границы | итог |')
    print('|---|---|---|---|---|---|---|---|---|---|---|---|---|---|')
    for rule, (fam, ph, meas, kind, part_b, shift) in D.RULES.items():
        e = out[rule]
        why = 'правило' if act[rule] else ('описательно (совет 74)' if rule in COUNCIL_DESCR else
                                          'описательно (решает Р4Ф-Т)' if rule == 'Р4-Т' and passes['Р4Ф-Т'] else
                                          'описательно (решает Р4-Т)' if rule == 'Р4Ф-Т' and not passes['Р4Ф-Т'] and passes['Р4-Т'] else
                                          'описательно (мощность ниже 0,2)')
        print(f"| {rule} | {e['source']} | {e['m']} | {meas}{' − ' + g(shift, 1) if shift else ''} | {'двусторонний' if kind == 'two' else 'больше'} | "
              f"{'А и Б' if part_b else 'А'} | {f(e['mu'])} | {g(e['tau'], 4)} | {g(e['s_test'], 4)} | {g(e['power']['part_a'])} | "
              f"{g(e['power']['part_b'])} | {g(e['decisive'])} | {g(e['decisive_tau_hi'])} (τ = {g(e['tau_hi'], 4)}) | {why} |")
    print(f"\nР2-Л в калибровку: P(среднее m2 по 3 средам < 0,5) = {g(p2l['p_below'])} при τ пилота, {g(p2l['p_below_tau_hi'])} при τ из верхней "
          f"границы (среднее m2 пилота {g(p2l['mu_m2'])})")
    print(f"\nОбщий ложный уровень: выбранная ветвь {fwer['chosen']}; другая ветвь выбора Р4 / Р4Ф {fwer['other_branch']}")
    print('\nRULES_ACTIVE =', act)


if __name__ == '__main__':
    main()
