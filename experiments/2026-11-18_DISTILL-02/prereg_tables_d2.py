#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""DISTILL-02: таблицы пилотов для PREREG — печатаются из gha_out/distill02_pilot/pilot.json (пилот 1) и gha_out/distill02_pilot3/pilot3.json
(пилот 3 — меры по совету 74; пилот 2 тех же наборов — gha_out/distill02_pilot2/pilot2.json, прежние меры, в регистрацию не идёт).
Числа не переписываются руками (ERRORS № 200).  python3 prereg_tables_d2.py"""
import json
import os

X = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(X))
P1 = json.load(open(os.path.join(ROOT, 'gha_out/distill02_pilot/pilot.json'), encoding='utf-8'))
P3 = json.load(open(os.path.join(ROOT, 'gha_out/distill02_pilot3/pilot3.json'), encoding='utf-8'))


def f(x, d=4):
    return '—' if x is None or x != x else f'{x:+.{d}f}'.replace('-', '−').replace('.', ',')


def g(x, d=3):
    return '—' if x is None or x != x else f'{x:.{d}f}'.replace('.', ',')


L = ['**Пилот 1 — сводка** (программы — по пилоту OCDIV-04; среднее по парам «голова × среда»; прежняя обрезка log p; описательно):', '',
     '| Набор проверки | пар | программа − B1 | больше 0 | программа − Φ-база | больше 0 | доля объяснимого, медиана | три неверных: программа / B1 | K: наблюдённое / из программ, медиана |',
     '|---|---|---|---|---|---|---|---|---|']
for name, ev in P1['eval'].items():
    s = ev['summary']
    L.append(f"| {name} | {s['n_cells']} | {f(s['prog_minus_b1_mean'])} | {s['prog_minus_b1_pos']} | {f(s['prog_minus_phi_mean'])} | {s['prog_minus_phi_pos']} | "
             f"{g(s['explained_median'])} | {g(s['hit_prog_mean'])} / {g(s['hit_b1_mean'])} | {g(s['K_ratio_median'])} |")
L += ['', f"**Пилот 3 — меры по средам** (совет 74: смесь λ = {P3['lam']:g}, зерно среды, выборки программ в повторах; точки, в скобках — ст. откл. "
      f"повторов, B = {P3['B']}, R = {P3['R']}):", '',
      '| Набор | среда | голов | m1 | m1_phi | m2 | m2_max | m3 | m3_c | m3_o |', '|---|---|---|---|---|---|---|---|---|---|']
for name, st in P3['sets'].items():
    for en, e in st['envs'].items():
        pt, sd = e['point'], e['sd']
        L.append(f"| {name} | {en} | {len(e['heads'])} | {f(pt['m1'])} ({g(sd['m1'], 4)}) | {f(pt['m1_phi'])} ({g(sd['m1_phi'], 4)}) | "
                 f"{g(pt['m2'])} ({g(sd['m2'])}) | {g(pt['m2_max'])} | {f(pt['m3'])} ({g(sd['m3'], 4)}) | {f(pt['m3_c'])} | {f(pt['m3_o'])} |")
L += ['', '**Пилот 3 — хвост и смесь** (описательно; «наибольший вклад» — одной задачи к сумме программа − B1; m1 при λ = 0 — прежняя обрезка 1e-300):', '',
      '| Набор | среда | наибольший вклад одной задачи | задач на половину суммы | m1 при λ = 0 | m1 при 1e-4 | m1 при 1e-3 | m1 при 1e-2 |', '|---|---|---|---|---|---|---|---|']
for name, st in P3['sets'].items():
    for en, e in st['envs'].items():
        c, s = e['concentration']['b1'], e['lambda_sens']
        L.append(f"| {name} | {en} | {g(c['top_share'], 4)} | {g(c['half_tasks_share'])} | {f(s['0']['m1'])} | {f(s['0.0001']['m1'])} | "
                 f"{f(e['point']['m1'])} | {f(s['0.01']['m1'])} |")
L += ['', '**Формулы потери переноса по пилоту OCDIV-04** (P(потеря переноса в разряд j) = σ(…); коэффициенты — две значащие цифры; ε — доля «прочих» ошибок):', '',
      '| Семейство | Голова | формула | ε | Φ-база |', '|---|---|---|---|---|']
for fam in ('T', 'L'):
    for h, fm in P1['formulas'][fam].items():
        terms = ' '.join(f"{w:+.2g}·{n}" for w, n in zip(fm['w_round'][1:], fm['features']))
        ph = P1['formulas_phi'][fam][h]
        L.append(f"| {fam} | {h.split('/')[-1]} | σ({fm['w_round'][0]:+.2g} {terms}) | {g(fm['eps'])} | σ({ph['w_round'][0]:+.2g} {ph['w_round'][1]:+.2g}·phi) |")
if '--dry' not in __import__('sys').argv:
    print('\n'.join(L))


def dry_block():
    """Сухой прогон (совет 74, п. 10): числа — из prereg_derived_d2.json (разбор вывода gha_out/distill02_dry/)."""
    d = json.load(open(os.path.join(X, 'prereg_derived_d2.json'), encoding='utf-8')).get('dry')
    if not d:
        return '(сухой прогон ещё не готов)'
    return '\n'.join([
        f"- Основной прогон анализа на заглушках (B = 4000, R = 20, 15 сред, 4 процесса, {d['cores']} ядра раннера) — {d['main_s']:.0f} с "
        f"({d['main_min']:.1f} мин; порог совета — 60 мин); по выводу анализа — {d['analysis_s']:.1f} с.",
        f"- Память машины: до прогона {d['mem_before_mb']} МБ, наибольшая {d['mem_peak_mb']} МБ (прирост {d['mem_peak_over_mb']} МБ); "
        f"наибольший размер одного процесса — {d['max_rss_kb']} КБ.",
        f"- Продолжение с готовых сред (тот же spec) — {d['resume_s']:.0f} с; вывод тот же, кроме времени: {'да' if d['resume_same'] else 'НЕТ'}.",
        f"- Повтор на детерминизм (2 среды, B = 200, дважды) — {d['det_s']:.0f} с; побайтно одинаково: {'да' if d['det_same'] else 'НЕТ'}."])


if __name__ == '__main__' and '--dry' in __import__('sys').argv:
    print(dry_block())
