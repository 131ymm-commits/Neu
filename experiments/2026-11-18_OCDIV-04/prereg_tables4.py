#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""OCDIV-04: таблицы пилота для PREREG — печатаются из gha_out/ocdiv4_sum_pilot3/pilot.json (числа не переписываются руками; ERRORS № 200).
  python3 prereg_tables4.py > prereg_pilot_tables.md"""
import json
import os

X = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(X))
P = json.load(open(os.path.join(ROOT, 'gha_out/ocdiv4_sum_pilot3/pilot.json'), encoding='utf-8'))


def f(x, d=4):
    return '—' if x is None or x != x else f'{x:+.{d}f}'.replace('-', '−').replace('.', ',')


def g(x, d=4):
    return '—' if x is None or x != x else f'{x:.{d}f}'.replace('.', ',')


L = ['**Пилот по средам** (фаза pilot3, 600 задач; точки, в скобках — ст. откл. повторов, B = 1000):', '',
     '| Среда | толпа | вне диапазона / ID | оракул | Δ3c вне диапазона | Δ3c на ID | K вне диапазона | K на ID | K: вне минус ID | Т4 (N0) |',
     '|---|---|---|---|---|---|---|---|---|---|']
for fam in ('thousands', 'length'):
    for n, e in P['families'][fam]['envs'].items():
        L.append(f"| {n} | {len(e['crowd'])} | {e['n_ood']} / {e['n_id']} | {g(e['oracle_ood'], 3)} | {f(e['d3c_ood']['point'])} ({g(e['d3c_ood']['sd'])}) | "
                 f"{f(e['d3c_id']['point'])} | {f(e['k_ood']['point'])} | {f(e['k_id']['point'])} | {f(e['k_diff']['point'])} ({g(e['k_diff']['sd'])}) | "
                 f"{f(e['t4_ood']['point'])} |")
L += ['', '**Мощность по пилоту** (модель «новая среда»: точка среды ~ N(μ, τ² + s²); s — пересчёт ст. откл. пилота на тест; 200 000 наборов):', '',
      '| Правило | сред | μ | τ | s (тест) | часть А | часть Б | «подтверждено» (решающий вердикт) | при τ из верхней границы |', '|---|---|---|---|---|---|---|---|---|']
for r, v in P['power'].items():
    pw, ph = v['power'], v['power_tau_hi']
    L.append(f"| {r} | {v['n_envs']} | {f(v['mu'])} | {g(v['tau'])} | {g(v['s_test'])} | {g(pw['part_a'], 3)} | {g(pw['part_b'], 3)} | "
             f"{g(pw['decisive'], 3)} | {g(ph['confirm'] + (ph['refute'] if r == 'Р2-Т' else 0), 3)} (τ = {g(v['tau_hi'])}) |")
for r, v in P.get('power_alt', {}).items():
    pw, ph = v['power'], v['power_tau_hi']
    L.append(f"| {r}, запасной нуль | {v['n_envs']} | {f(v['mu'])} | {g(v['tau'])} | {g(v['s_test'])} | {g(pw['part_a'], 3)} | {g(pw['part_b'], 3)} | "
             f"{g(pw['confirm'], 3)} | {g(ph['confirm'], 3)} (τ = {g(v['tau_hi'])}) |")
L += ['', '**Запасной нуль N0c по средам** (Δ = F − F₀(N0 со стратами c1) вне диапазона; точки, в скобках — ст. откл. повторов): ' +
      '; '.join(f"{n} {f(e['n0c_ood']['point'])} ({g(e['n0c_ood']['sd'])})" for fam in ('thousands', 'length') for n, e in P['families'][fam]['envs'].items()) + '.']
L += ['', '**Положительный контроль N3c** (среднее по восьми средам «тысяч»; прирост Δ3c при вбросе):', '',
      '| Вброс | δ | ' + ' | '.join(['прирост'] * 1) + ' |', '|---|---|---|']
for key, name in (('spike', 'первоначальный (HYPOTHESIS §7)'), ('spike_items', 'по задачам (HYPOTHESIS-ADDENDUM)')):
    sp = P[key]
    L.append(f"| {name} | " + '; '.join(g(d, 3) for d in sp['deltas'][1:]) + ' | ' + '; '.join(f(y) for y in sp['mean_curve'][1:]) + ' |')
L += ['', '| Вброс | цель | δ* | τ заложенного прироста | часть А | часть Б | мощность Р1-Т при цели |', '|---|---|---|---|---|---|---|']
for key, name in (('spike', 'первоначальный'), ('spike_items', 'по задачам')):
    for tg, t in P[key]['targets'].items():
        pt = t['power_at_target'] or {}
        L.append(f"| {name} | +{g(float(tg), 2)} | {g(t['delta'], 3)} | {g(t['tau_increment'])} | {g(pt.get('part_a'), 3)} | {g(pt.get('part_b'), 3)} | "
                 f"{g(pt.get('confirm'), 3)} |")
L += ['', f"- Изменение K при первоначальном вбросе (среднее по средам): " + '; '.join(f"δ = {g(float(d), 2)}: {f(v)}" for d, v in P['spike_k_mean'].items()) + '.',
      f"- Годность N3c по правилу (мощность при +0,02 не меньше 0,8): по первоначальному вбросу — {'да' if P['n3c_fit_original'] else 'нет'}, "
      f"по вбросу по задачам — {'да' if P['n3c_fit'] else 'нет'}.",
      f"- Невырожденные среды (оракул ≥ 0,1): «тысячи» — {len(P['nondeg']['thousands'])} из 8, «длина» — {len(P['nondeg']['length'])} из 3.",
      f"- Правила по порогу мощности 0,2: " + ', '.join(f"{r} — {'правило' if a else 'описательно'}" for r, a in P['rules_active'].items()) + '.',
      f"- Ожидания (0,95 × мощность): " + ', '.join(f"{r} — {g(v, 4)}" for r, v in P['expect'].items()) + '.']
print('\n'.join(L))

# ── третий контроль N3c (HYPOTHESIS-ADDENDUM-2): задание 1 — кривые на Н1, задание 2 — проверка на Н2; печать из json (ERRORS № 200)
import sys  # noqa: E402
if '--control3' in sys.argv:
    CR = json.load(open(os.path.join(ROOT, 'gha_out/ocdiv4_curves3/curves3.json'), encoding='utf-8'))
    CT = json.load(open(os.path.join(ROOT, 'gha_out/ocdiv4_control3/control3.json'), encoding='utf-8'))
    M = ['', '**Третий контроль N3c** (HYPOTHESIS-ADDENDUM-2; R = ' + str(CR['R']) + '; прирост — среднее по размещениям вброса по задачам):', '',
         '| Среда | цель t_e | прирост на Н1 при δ = ' + '; '.join(g(d, 3) for d in CR['grid']) + ' | δ_e (Н1) | реализованный прирост (Н2) |',
         '|---|---|---|---|---|']
    for n, e in CR['envs'].items():
        M.append(f"| {n} | {f(CR['targets'][n])} | " + '; '.join(f(y) for y in e['curve']) + f" | {g(e['delta'], 3) if e['delta'] is not None else 'нет корня'} | "
                 f"{f(CT['realized'][n]) if CT['realized'][n] is not None else '—'} |")
    M += ['', f"- Все корни найдены: {'да' if CR['all_roots'] else 'нет'}; контроль пройден: {'да' if CT['pass'] else 'нет'}; "
              f"N3C_FIT = {CT['n3c_fit']}. Время: задание 1 — {g(CR['seconds'], 1)} с, задание 2 — {g(CT['seconds'], 1)} с."]
    print('\n'.join(M))
