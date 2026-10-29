#!/usr/bin/env python3
"""TRUST-04: таблицы отчёта из facts_trust_04.json (числа в отчёт — командой, не перепечаткой). Вердиктов не меняет;
записан после регистрации 9c37e56 и до просмотра результатов теста; 29.10, после проверки отчёта (находка 6), R печатается
с 4 знаками — как хранится в facts (было 3 знака от уже округлённого числа: двойное округление).
Запуск из папки опыта: python3 report_tables_trust04.py [папка с facts, по умолчанию — опыт] > run/report_tables.md"""
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
DIR = os.path.join(HERE, sys.argv[1]) if len(sys.argv) > 1 else HERE
F = json.load(open(os.path.join(DIR, 'facts_trust_04.json')))
CAL = json.load(open(os.path.join(HERE, 'pilot', 'v2', 'pilot_calib2.json')))['bits']['95']
f = lambda x, d=4: '—' if x is None else (f'{x:.{d}f}'.replace('.', ',').replace('-', '−'))
ci = lambda v: f'{f(v[0])} [{f(v[1])}; {f(v[2])}]'
okey = lambda k: (k[0], int(re.sub(r'\D', '', k) or 0), k)
DESC = dict(
    A1='\\|u\\| POOLED ≤ 1/6', A2='\\|u\\| POOLED_FREE ≤ 1/6', A3='u DEMES в (1/6; 5/6)', A4='u DEMES_FREE в (1/6; 5/6)',
    A5='w_G POOLED < DEMES', A6='w_G POOLED_FREE < DEMES_FREE', A7='POOLED ≡ POOLED_FREE', A8='DEMES ≡ DEMES_FREE',
    A9='\\|u − 1\\| DEMES_NOSEL ≤ 1/3', A10='\\|u − 1\\| DEMES_NOSEL_FREE ≤ 1/3', A11='\\|u\\| COUNCIL_SIGN ≤ 1/3', A12='COUNCIL ≡ COUNCIL_SIGN',
    A13='\\|u\\| COUNCIL ≤ 1/6', A14='\\|u − 1\\| MYOPIC ≤ 1/3', A15='\\|u\\| DEMES_NOWITHIN ≤ 1/6 (без срыва)', A16='u DEMES_GPOOL в (1/6; 5/6)',
    A17='DEMES_GPOOL ≡ DEMES_FREE', A18='w_G POOLED_FREE < DEMES_GPOOL',
    B1='знак, r075', B2='знак, r095', B3='знак, b03', B4='знак, b09', B5='знак, IND', B6='знак, MIG', B7='знак, SIG5',
    B8='\\|u\\| POOLED_r075 ≤ 1/3', B9='\\|u\\| POOLED_r095 ≤ 1/3', B10='\\|u\\| POOLED_b03 ≤ 1/3', B11='\\|u\\| POOLED_b09 ≤ 1/3',
    B12='\\|u − 1\\| MYOPIC_r075 ≤ 1/3', B13='\\|u − 1\\| MYOPIC_r095 ≤ 1/3', B14='\\|u − 1\\| MYOPIC_b03 ≤ 1/3', B15='\\|u − 1\\| MYOPIC_b09 ≤ 1/3',
    C_MYOPIC='независимая ≡ основная, MYOPIC', C_DEMES='независимая ≡ основная, DEMES', C_POOLED='независимая ≡ основная, POOLED',
    C_COUNCIL='независимая ≡ основная, COUNCIL', C_ORDER='независимая: u POOLED < DEMES')


def row(k, v):
    if v['kind'] == 'эквивалентность':
        res = f"разность {ci(v['diff_ci'])}"
    elif 'diff' in v:
        res = f"{v['n']} из {v['N']} (порог {v['k']}); разность {ci(v['diff'])}"
    else:
        res = f"{v['n']} из {v['N']} (порог {v['k']}); среднее {ci(v['value'])}"
        if 'breakdowns' in v:
            res += f"; срывов {v['breakdowns']}" + (f"; без срыва {ci(v['value_no_breakdown'])}" if v.get('value_no_breakdown') else '')
    return f"| {k} | {DESC.get(k, '')} | {res} | {v['outcome']} |"


print('### Сводные исходы\n')
print('| Сводный | Части | Вердикт | Чтение | Вес при подтверждении (§6) |')
print('|---|---|---|---|---|')
for c, s in (F['summary'] or {}).items():
    r = (F['readings'] or {}).get(c, {})
    why = ('; ' + '; '.join(r['why'])) if r.get('why') else ''
    print(f"| {c} | {', '.join(s['parts'])} | {s['outcome']} | {r.get('reading', '—')}{why} | {f(CAL[c]['bits'], 1)} бита |")
for blk, pref in (('Блок А', 'A'), ('Блок Б', 'B'), ('Блок В', 'C_')):
    print(f'\n### {blk}\n\n| | Предсказание | Итог | Исход |\n|---|---|---|---|')
    for k in sorted([k for k in F['verdicts'] if k.startswith(pref) and (pref != 'A' or not k.startswith('C_'))], key=okey):
        print(row(k, F['verdicts'][k]))
print('\n### Разведка\n\n| | Итог | Исход |\n|---|---|---|')
for k, v in F['explore'].items():
    if k == 'EB1':
        res = f"SD u {f(v['sd_IND'])} против {f(v['sd_base'])}, p одност. {f(v['p_one_sided'])}"
    elif k == 'EB6':
        res = (f"\\|ū − (1 − R̄)\\| MIG {f(v['gap_MIG'])}, SIG5 {f(v['gap_SIG5'])}; в пределах 0,1 — {v['n_within_01']} из 10; "
               f"ρ Спирмена {f(v['spearman'], 3)}")
    elif v['kind'] == 'эквивалентность':
        res = f"разность {ci(v['diff_ci'])}"
    else:
        res = f"{v['n']} из {v['N']} (порог {v['k']}); разность {ci(v['diff'])}"
    print(f"| {k} | {res} | {v['outcome']} |")
print('\n### Руки (среднее по 20 зёрнам [95 % бутстреп])\n')
print('| Рука | u | w_G | Лог-потеря | Точность | Самообман | R | SD шага |')
print('|---|---|---|---|---|---|---|---|')
for a, m in F['arms'].items():
    print(f"| {a} | {ci(m['u'])} | {f(m['wG'][0])} | {f(m['logloss'][0])} | {f(m['acc'][0])} | {f(m['self_dec'][0])} | {f(m['R'][0])} | {f(m['step_sd'][0])} |")
print('\n### EB6 по рукам с отбором внутри группы по своему весу\n\n| Рука | ū | 1 − R̄ | Разность |\n|---|---|---|---|')
e6 = F['explore']['EB6']
for a, uu, r_, g in zip(['DEMES', 'DEMES_FREE', 'DEMES_GPOOL', 'DEMES_IND', 'DEMES_MIG', 'DEMES_SIG5', 'DEMES_r075', 'DEMES_r095', 'DEMES_b03', 'DEMES_b09'],
                       e6['u'], e6['one_minus_R'], e6['abs_gap']):
    print(f'| {a} | {f(uu)} | {f(r_)} | {f(g)} |')
print('\n### Срывы (рук с σ = 0,04)\n')
for a, b in F['breakdowns'].items():
    if b['n']:
        print(f"- {a}: {b['n']} из 20 (зёрна {', '.join(map(str, b['seeds']))}); V_внутри в срывах {', '.join(f(x) for x in b['V_within'])}, "
              f"без срыва — {f(b['V_within_ok'])}; u в срывах {', '.join(f(x) for x in b['u'])}, без срыва — {ci(b['u_ok'])}.")
print(f"- SD шага DEMES_NOWITHIN без срывов — {ci(F['step_sd_nowithin_no_breakdown'])}.")
print('\n### Сходимость: разность половин окна (2000–2999 минус 1000–1999), среднее [95 %]; зёрен < 0\n')
print('| Рука | Разность | Зёрен < 0 |\n|---|---|---|')
for a, d in F['dynamics'].items():
    print(f"| {a} | {ci(d['half_diff'])} | {d['n_half_neg']} |")
print('\n### Реестр: повтор утверждений TRUST-03\n\n| Утверждение | Части | Исход | Вес |\n|---|---|---|---|')
for cid, r in (F['registry'] or {}).items():
    print(f"| {cid} | {', '.join(r['parts'])} | {r['outcome']} | {f(r['bits'], 2)} бита |")
print('\n### Проверки построения\n')
for a, k in F['construction'].items():
    print(f"- {a}: разность лог-потери с POOLED {ci(k['logloss_gap'])}, зёрен с разностью ≥ 0,02 — {k['n_gap_ge_002']}; "
          f"w_G {ci(k['wG'])}; SD между группами {ci(k['sd_groups'])}.")
print('\n### Части Прайса (среднее по зёрнам)\n\n| Рука | Внутри групп | Между группами |\n|---|---|---|')
for a, p in F['price'].items():
    print(f"| {a} | {f(p['within'], 5)} | {f(p['between'], 5)} |")
