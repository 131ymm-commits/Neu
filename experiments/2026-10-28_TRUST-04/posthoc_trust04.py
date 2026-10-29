#!/usr/bin/env python3
"""TRUST-04: пост-хок числа по проверке отчёта (lenses/REPORT_CHECK.md, находки 1–4, 11–14, 16) — НЕ В ЗАЧЁТ.
Записан 29.10.2026 после результатов теста и после проверки отчёта; вердиктов не меняет, новых не порождает.
Вход:
  analysis_trust_04.json — зёрна (rows), руки (arms), сходимость (dynamics), теория;
  pilot/v2/analysis_trust_04.json — сходимость пилота v2 (зёрна 1100–1109);
  indep/test700/results_indep_04.json — вторая реализация (u — по FROZEN мира base, как в анализе).
Выход: posthoc_trust_04.json и run/posthoc_trust_04.md (числа для отчёта; check_report_trust04.py берёт md как источник).
Интервалы — тот же бутстреп по зёрнам, что в analyze_trust_04.py (B = 10000, генератор 0); Уэлч — тот же, 95 %.
Запуск из папки опыта: python3 posthoc_trust04.py"""
import json
import os
import sys

import numpy as np
from scipy.stats import binom
from scipy.stats import t as tdist

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import exp_trust_04 as E  # noqa: E402  (описание рук; при импорте не исполняется)

A = json.load(open(os.path.join(HERE, 'analysis_trust_04.json')))
P = json.load(open(os.path.join(HERE, 'pilot', 'v2', 'analysis_trust_04.json')))
IND = json.load(open(os.path.join(HERE, 'indep', 'test700', 'results_indep_04.json')))
seeds = A['seeds']; NS = len(seeds)
assert NS == 20 and seeds == list(range(600, 620))
u = lambda arm: np.array([A['rows'][str(s)][arm]['u'] for s in seeds])
col = lambda arm, k: np.array([A['rows'][str(s)][arm][k] for s in seeds])


def boot_ci(x, B=10000, seed=0, q=(0.025, 0.975)):          # как в analyze_trust_04.py
    x = np.asarray(x, float); g = np.random.default_rng(seed)
    m = x[g.integers(0, len(x), (B, len(x)))].mean(1)
    return [float(x.mean()), float(np.quantile(m, q[0])), float(np.quantile(m, q[1]))]


def welch_ci(x, y, level):                                   # как в analyze_trust_04.py
    x, y = np.asarray(x, float), np.asarray(y, float); vx, vy = x.var(ddof=1) / len(x), y.var(ddof=1) / len(y)
    se = np.sqrt(vx + vy); df = (vx + vy) ** 2 / (vx ** 2 / (len(x) - 1) + vy ** 2 / (len(y) - 1))
    h = float(tdist.ppf(1 - (1 - level) / 2, df)) * se; d = float(x.mean() - y.mean())
    return [d, d - h, d + h]


# самопроверка: тот же бутстреп даёт те же средние и интервалы, что в анализе
for a in A['arms']:
    assert np.allclose(boot_ci(u(a)), A['arms'][a]['u'], rtol=0, atol=1e-12), a
out = dict(note='пост-хок, не в зачёт: числа по проверке отчёта (lenses/REPORT_CHECK.md); вердиктов не меняет')

# 1. Кромки A1 и A3 в мирах и условиях блока Б (находка 1): A1 — |u| ≤ 1/6 (нестрого), A3 — 1/6 < u < 5/6 (строго)
EDGE = {}
for c in ('base', 'r075', 'r095', 'b03', 'b09', 'IND', 'MIG', 'SIG5'):
    pa, da = ('POOLED', 'DEMES') if c == 'base' else (f'POOLED_{c}', f'DEMES_{c}')
    up, ud = u(pa), u(da)
    EDGE[c] = dict(pooled=pa, demes=da, pooled_abs_le_1_6=int(np.sum(np.abs(up) <= 1 / 6)),
                   pooled_abs_le_1_3=int(np.sum(np.abs(up) <= 1 / 3)), pooled_max_abs=float(np.abs(up).max()),
                   demes_in_1_6_5_6=int(np.sum((ud > 1 / 6) & (ud < 5 / 6))), demes_ge_5_6=int(np.sum(ud >= 5 / 6)),
                   demes_le_1_6=int(np.sum(ud <= 1 / 6)))
out['edges_A1_A3'] = EDGE

# 2. COUNCIL_SIGN по исходной кромке 1/6 (до пилота v1 у A11 стояло 1/6; находка 3)
cs = u('COUNCIL_SIGN')
out['council_sign'] = dict(abs_le_1_6=int(np.sum(np.abs(cs) <= 1 / 6)), max_abs=float(np.abs(cs).max()), u=boot_ci(cs))

# 3. Лог-потеря: Уэлч 95 % (описательно; находка 11) и теоретический разрыв близорукой и дальновидной точек мира base
th = A['theory']['base']
out['logloss_welch'] = dict(MYOPIC_minus_POOLED=welch_ci(col('MYOPIC', 'logloss'), col('POOLED', 'logloss'), 0.95),
                            DEMES_minus_POOLED=welch_ci(col('DEMES', 'logloss'), col('POOLED', 'logloss'), 0.95),
                            theory_gap_myopic_minus_farsighted=th['myopic']['logloss'] - th['farsighted']['logloss'])

# 4. Части Прайса по рукам (находка 12): E1 — особь действует своим весом и передаёт его ∝ своей F, при отборе групп
E1 = ['DEMES', 'DEMES_FREE', 'DEMES_GPOOL', 'DEMES_IND', 'DEMES_MIG', 'DEMES_SIG5', 'DEMES_r075', 'DEMES_r095', 'DEMES_b03', 'DEMES_b09']
NOE1 = ['POOLED', 'POOLED_FREE', 'COUNCIL', 'COUNCIL_SIGN', 'POOLED_r075', 'POOLED_r095', 'POOLED_b03', 'POOLED_b09',
        'POOLED_IND', 'POOLED_MIG', 'POOLED_SIG5', 'DEMES_NOWITHIN']        # отбор групп есть, E1 нет
NOGS = ['MYOPIC', 'DEMES_NOSEL', 'DEMES_NOSEL_FREE']                         # E1 есть, отбора групп нет (одна группа или без отбора)
for a in E1:
    s = E.ARMS[a]; assert s['expr'] == 'own' and s['wsel'] and s['group_sel'] and not s['council'], a
for a in NOE1:
    s = E.ARMS[a]; assert s['group_sel'] and (s['expr'] == 'pool' or not s['wsel']), a
pw = {a: float(A['arms'][a]['price_within'][0]) for a in A['arms']}
pb = {a: float(A['arms'][a]['price_between'][0]) for a in A['arms']}
e1_04 = [a for a in E1 if E.ARMS[a]['sig'] == E.SIG]
out['price'] = dict(E1_sig004_within_min=min(pw[a] for a in e1_04), E1_sig004_within_max=max(pw[a] for a in e1_04),
                    E1_sig004_arms=e1_04, DEMES_SIG5_within=pw['DEMES_SIG5'], DEMES_SIG5_between=pb['DEMES_SIG5'],
                    E1_sum_abs_max=max(abs(pw[a] + pb[a]) for a in E1),
                    noE1_within_abs_max=max(abs(pw[a]) for a in NOE1), noE1_between_abs_max=max(abs(pb[a]) for a in NOE1),
                    no_group_sel_within={a: pw[a] for a in NOGS})

# 5. EB6: сдвиг (1 − R̄) − ū с бутстрепом по зёрнам (находка 14); R̄ = V̄_между / (V̄_между + V̄_внутри), как в анализе
g = np.random.default_rng(0); IDX = g.integers(0, NS, (10000, NS))
EB6 = {}
for a in E1:
    uu, vb, vw = u(a), col(a, 'V_between'), col(a, 'V_within')
    off = lambda ix: (1 - vb[ix].mean(-1) / (vb[ix].mean(-1) + vw[ix].mean(-1))) - uu[ix].mean(-1)
    pt = float(off(np.arange(NS))); bs = off(IDX)
    EB6[a] = dict(offset=[pt, float(np.quantile(bs, 0.025)), float(np.quantile(bs, 0.975))],
                  abs_gap=[abs(pt), float(np.quantile(np.abs(bs), 0.025)), float(np.quantile(np.abs(bs), 0.975))])
    assert abs(abs(pt) - A['explore']['EB6']['abs_gap'][E1.index(a)]) < 6e-5, a   # тот же зазор, что в анализе (там 4 знака)
pos = [a for a in E1 if EB6[a]['offset'][0] > 0]
out['EB6_boot'] = dict(arms=EB6, n_u_below_1_minus_R=len(pos), offsets_below=[min(EB6[a]['offset'][0] for a in pos), max(EB6[a]['offset'][0] for a in pos)],
                       n_offset_ci_excludes_0=sum(EB6[a]['offset'][1] > 0 or EB6[a]['offset'][2] < 0 for a in E1),
                       SIG5_abs_gap_ci_covers_0_1=bool(EB6['DEMES_SIG5']['abs_gap'][1] <= 0.1 <= EB6['DEMES_SIG5']['abs_gap'][2]))

# 6. Сходимость: сколько из 31 интервала «разность половин окна» не накрывают 0 — против случайного при 95 % (находка 13)
excl = lambda dyn: [a for a, v in dyn.items() if v['half_diff'][1] > 0 or v['half_diff'][2] < 0]
ex_t, ex_p = excl(A['dynamics']), excl(P['dynamics'])
nA = len(A['dynamics'])
out['halves'] = dict(n_arms=nA, excluded_test=ex_t, excluded_pilot=ex_p, expected=nA * 0.05,
                     p_ge_observed=float(binom.sf(len(ex_t) - 1, nA, 0.05)), assumption='интервалы независимы и покрывают ровно 95 %',
                     pilot_seeds=[P['seeds'][0], P['seeds'][-1]],
                     pilot_half_diff={a: P['dynamics'][a]['half_diff'] for a in ('POOLED', 'DEMES', 'DEMES_NOSEL_FREE', 'MYOPIC', 'DEMES_IND')},
                     test_half_diff={a: A['dynamics'][a]['half_diff'] for a in ex_t + ['POOLED_IND', 'DEMES_IND']},
                     shift_over_A1_edge={a: abs(A['dynamics'][a]['half_diff'][0]) / (1 / 6) for a in ex_t})

# 7. Сдвиг u > 0 у 12 рук без E1 «прихода к точке» (находки 4 и 16), в обеих реализациях
sh = {a: A['arms'][a]['u'] for a in NOE1}
ten = [a for a in NOE1 if a not in ('POOLED_SIG5', 'POOLED_IND')]
my0, far0 = A['frozen']['base']
IR = {(r['seed'], r['arm']): r for r in IND['runs']}; iseeds = IND['meta']['seeds']
ui = lambda a: [(IR[(s, a)]['w_G'] - far0) / (my0 - far0) for s in iseeds]
for a in ('POOLED', 'COUNCIL', 'DEMES', 'MYOPIC'):          # самопроверка против анализа
    assert np.allclose(boot_ci(ui(a)), A['verdicts'][f'C_{a}']['u_indep'], rtol=0, atol=1e-12), a
out['noE1_shift'] = dict(arms={a: sh[a] for a in NOE1}, n_ci_above_0=sum(sh[a][1] > 0 for a in NOE1),
                         ten_range=[min(sh[a][0] for a in ten), max(sh[a][0] for a in ten)], ten=ten,
                         indep={a: boot_ci(ui(a)) for a in ('POOLED', 'COUNCIL')},
                         E1_base_free=[A['arms']['DEMES_FREE']['u'][0], A['arms']['DEMES_GPOOL']['u'][0]],
                         noE1_base_free=[A['arms']['POOLED_FREE']['u'][0], A['arms']['DEMES_NOWITHIN']['u'][0]])
json.dump(out, open(os.path.join(HERE, 'posthoc_trust_04.json'), 'w'), ensure_ascii=False, indent=1)

# ---- строки для отчёта (числа — отсюда; check_report_trust04.py сверяет прозу с этим файлом) ----
f = lambda x, d=4: f'{x:.{d}f}'.replace('.', ',').replace('-', '−')
ci = lambda v: f'{f(v[0])} [{f(v[1])}; {f(v[2])}]'
L = ['# TRUST-04 — пост-хок по проверке отчёта (не в зачёт; `posthoc_trust04.py` → `posthoc_trust_04.json`)', '']
L.append('## Кромки A1 (|u| POOLED ≤ 1/6) и A3 (1/6 < u DEMES < 5/6) по условиям, зёрен из 20')
L.append('| Условие | POOLED: \\|u\\| ≤ 1/6 | ≤ 1/3 | max \\|u\\| | DEMES: в (1/6; 5/6) | ≥ 5/6 | ≤ 1/6 |')
L.append('|---|---|---|---|---|---|---|')
for c, e in EDGE.items():
    L.append(f"| {c} | {e['pooled_abs_le_1_6']} | {e['pooled_abs_le_1_3']} | {f(e['pooled_max_abs'])} | {e['demes_in_1_6_5_6']} | {e['demes_ge_5_6']} | {e['demes_le_1_6']} |")
c_ = out['council_sign']
L += ['', f"- COUNCIL_SIGN по исходной кромке 1/6: {c_['abs_le_1_6']} из 20, наибольшее |u| {f(c_['max_abs'])}; u {ci(c_['u'])}."]
lw = out['logloss_welch']
L.append(f"- Лог-потеря (Уэлч 95 %, описательно): MYOPIC − POOLED {ci(lw['MYOPIC_minus_POOLED'])}, DEMES − POOLED {ci(lw['DEMES_minus_POOLED'])}; "
         f"разрыв теории близорукая − дальновидная {f(lw['theory_gap_myopic_minus_farsighted'])}.")
pr = out['price']
L.append(f"- Внутригрупповая часть Прайса у рук с E1 при σ = 0,04: {f(pr['E1_sig004_within_min'])}–{f(pr['E1_sig004_within_max'])}; у DEMES_SIG5 "
         f"{f(pr['DEMES_SIG5_within'])} (межгрупповая {f(pr['DEMES_SIG5_between'])}); наибольшая |сумма частей| у рук с E1 {f(pr['E1_sum_abs_max'])}; "
         f"у рук без E1 |внутри| ≤ {f(pr['noE1_within_abs_max'])}, |между| ≤ {f(pr['noE1_between_abs_max'])}; без отбора групп "
         f"({', '.join(pr['no_group_sel_within'])}) |внутри| ≤ {f(max(abs(v) for v in pr['no_group_sel_within'].values()), 5)}.")
L += ['', '## EB6: сдвиг (1 − R̄) − ū, бутстреп по зёрнам 95 %', '| Рука | (1 − R̄) − ū | \\|ū − (1 − R̄)\\| |', '|---|---|---|']
for a, e in EB6.items():
    L.append(f"| {a} | {ci(e['offset'])} | {ci(e['abs_gap'])} |")
eb = out['EB6_boot']
L.append(f"\n- ū ниже 1 − R̄ у {eb['n_u_below_1_minus_R']} из 10 рук, на {f(eb['offsets_below'][0])}–{f(eb['offsets_below'][1])}; "
         f"интервал сдвига не накрывает 0 у {eb['n_offset_ci_excludes_0']} из 10; интервал зазора DEMES_SIG5 накрывает кромку 0,1: "
         f"{'да' if eb['SIG5_abs_gap_ci_covers_0_1'] else 'нет'}.")
hv = out['halves']
L += ['', '## Сходимость: разность половин окна',
      f"- Не накрывают 0 в тесте: {len(ex_t)} из {nA} ({', '.join(ex_t)}); ожидаемо при 95 % — {f(hv['expected'], 2)}; "
      f"P(≥ {len(ex_t)}) = {f(hv['p_ge_observed'], 2)} (если интервалы независимы и покрывают ровно 95 %).",
      f"- В пилоте v2 (зёрна {hv['pilot_seeds'][0]}–{hv['pilot_seeds'][1]}) не накрывали 0: {', '.join(ex_p) or 'нет'}.",
      '- Пилот v2: ' + '; '.join(f'{a} {ci(v)}' for a, v in hv['pilot_half_diff'].items()) + '.',
      '- Тест: ' + '; '.join(f'{a} {ci(v)}' for a, v in hv['test_half_diff'].items()) + '.',
      '- |Сдвиг| в долях кромки A1 (1/6): ' + ', '.join(f'{a} {f(v, 2)}' for a, v in hv['shift_over_A1_edge'].items()) + '.']
ns = out['noE1_shift']
L += ['', '## Сдвиг u > 0 у 12 рук без E1 (отбор групп есть)',
      f"- Интервал u выше 0 у {ns['n_ci_above_0']} из 12; у десяти рук u {f(ns['ten_range'][0])}–{f(ns['ten_range'][1])}, "
      f"POOLED_SIG5 {ci(ns['arms']['POOLED_SIG5'])}, POOLED_IND {ci(ns['arms']['POOLED_IND'])}.",
      '- По рукам: ' + '; '.join(f'{a} {ci(v)}' for a, v in ns['arms'].items()) + '.',
      f"- Вторая реализация: POOLED {ci(ns['indep']['POOLED'])}, COUNCIL {ci(ns['indep']['COUNCIL'])}.",
      f"- Мир base, раздельное наследование: с E1 — DEMES_FREE {f(ns['E1_base_free'][0])}, DEMES_GPOOL {f(ns['E1_base_free'][1])}; "
      f"без E1 — POOLED_FREE {f(ns['noE1_base_free'][0])}, DEMES_NOWITHIN {f(ns['noE1_base_free'][1])}."]
open(os.path.join(HERE, 'run', 'posthoc_trust_04.md'), 'w', encoding='utf-8').write('\n'.join(L) + '\n')
print('\n'.join(L))
