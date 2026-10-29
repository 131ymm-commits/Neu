#!/usr/bin/env python3
"""Смысловая сверка чисел прозы REPORT-TRUST-04.md: число → величина, к которой оно отнесено в тексте → значение из json.
Источники: myrecalc.json (свой пересчёт из сырых results), analysis_trust_04.json, calib_trust04.json, PREREG §6, журналы."""
import json, re, math
import numpy as np

D = '/home/claude/neu/experiments/2026-10-28_TRUST-04'
S = '/tmp/claude-0/-home-claude/8c9bf095-e181-55d3-b75e-353e8e0f2d42/scratchpad/rc04b'
rep = open(f'{D}/REPORT-TRUST-04.md', encoding='utf-8').read().splitlines()
my = json.load(open(f'{S}/myrecalc.json'))
an = json.load(open(f'{D}/analysis_trust_04.json'))
cal = json.load(open(f'{D}/calib_trust04.json'))
V, X = my['V'], my['X']
ARM = an['arms']
fmt = lambda x, d=4: f'{x:.{d}f}'.replace('.', ',').replace('-', '−')
checks = []   # (строка отчёта, текст-числа, ожидаемое строкой, что это)


def c(line, s, val, d, what):
    checks.append((line, s, fmt(val, d), what))


# строка 7: отношение времён
c(7, '2,37', cal['timing']['test_B'] / cal['timing']['test_A'], 2, 'время B / время A (тест)')
c(7, '1,15', cal['timing']['pilot_B'] / cal['timing']['pilot_A'], 2, 'время B / время A (пилот v2)')
# строка 22
c(22, '0,0511', V['A1']['value'][0], 4, 'u POOLED, среднее')
c(22, '0,0591', V['A2']['value'][0], 4, 'u POOLED_FREE, среднее')
c(22, '0,4472', V['A3']['value'][0], 4, 'u DEMES, среднее')
c(22, '0,4690', V['A4']['value'][0], 4, 'u DEMES_FREE, среднее')
# строка 23: A7, A8 (Уэлч)
for i, s in enumerate(['−0,0080', '−0,0375', '0,0214']):
    c(23, s, V['A7']['diff_ci'][i], 4, f'A7 разность/ДИ Уэлча [{i}]')
for i, s in enumerate(['−0,0219', '−0,0506', '0,0069']):
    c(23, s, V['A8']['diff_ci'][i], 4, f'A8 разность/ДИ Уэлча [{i}]')
# строка 25
c(25, '0,4690', V['A4']['value'][0], 4, 'u DEMES_FREE')
c(25, '0,4520', V['A16']['value'][0], 4, 'u DEMES_GPOOL')
for i, s in enumerate(['−0,0170', '−0,0415', '0,0074']):
    c(25, s, V['A17']['diff_ci'][i], 4, f'A17 [{i}]')
# строка 26
c(26, '0,0591', V['A2']['value'][0], 4, 'u POOLED_FREE')
for i, s in enumerate(['0,0275', '0,0076', '0,0474']):
    c(26, s, V['A15']['value_nb'][i], 4, f'u DEMES_NOWITHIN без срыва, бутстреп [{i}]')
# строка 29
c(29, '0,0127', ARM['COUNCIL_SIGN']['step_sd'][0], 4, 'SD шага COUNCIL_SIGN')
c(29, '0,0400', ARM['COUNCIL']['step_sd'][0], 4, 'SD шага COUNCIL')
for i, s in enumerate(['0,0310', '0,0045', '0,0576']):
    c(29, s, V['A11']['value'][i], 4, f'u COUNCIL_SIGN [{i}]')
for i, s in enumerate(['0,0110', '−0,0261', '0,0482']):
    c(29, s, V['A12']['diff_ci'][i], 4, f'A12 [{i}]')
for i, s in enumerate(['0,0420', '0,0189', '0,0653']):
    c(29, s, V['A13']['value'][i], 4, f'u COUNCIL [{i}]')
# строка 32: диапазон u POOLED_w (B8–B11) и u MYOPIC_w (B12–B15)
bpool = [V[f'B{i}']['value'][0] for i in (8, 9, 10, 11)]
bmy = [V[f'B{i}']['value'][0] for i in (12, 13, 14, 15)]
c(32, '0,0419', min(bpool), 4, 'мин u POOLED_w, B8–B11')
c(32, '0,0640', max(bpool), 4, 'макс u POOLED_w, B8–B11')
c(32, '0,9969', min(bmy), 4, 'мин u MYOPIC_w, B12–B15')
c(32, '1,0257', max(bmy), 4, 'макс u MYOPIC_w, B12–B15')
# строка 33: POOLED_IND (описательно, не предсказание)
for i, s in enumerate(['0,1747', '0,1249', '0,2261']):
    c(33, s, ARM['POOLED_IND']['u'][i], 4, f'u POOLED_IND [{i}]')
# строка 35
for i, s in enumerate(['−0,0279', '−0,0532', '−0,0027']):
    c(35, s, V['C_MYOPIC']['diff_ci'][i], 4, f'C_MYOPIC [{i}]')
c(36, '−0,4212', V['C_ORDER']['diff'][0], 4, 'C_ORDER: средняя разность u POOLED − DEMES (незав.)')
# строка 37 и 277, 301: вес реестра (analysis)
for cid, s in zip(('C-048', 'C-049', 'C-050'), ('5,18', '5,39', '5,34')):
    for ln in (37, 277, 301):
        c(ln, s, an['registry'][cid]['bits'], 2, f'вес {cid}')
# строка 39–43 разведка
c(39, '0,1193', X['EB1']['sd_IND'], 4, 'SD u POOLED_IND')
c(39, '0,0412', X['EB1']['sd_base'], 4, 'SD u POOLED')
for i, s in enumerate(['−0,0242', '−0,0515', '0,0031']):
    c(40, s, X['EB2']['diff_ci'][i], 4, f'EB2 [{i}]')
c(41, '0,6781', ARM['DEMES_MIG']['u'][0], 4, 'u DEMES_MIG')
c(41, '0,8289', ARM['DEMES_SIG5']['u'][0], 4, 'u DEMES_SIG5')
c(43, '0,0305', X['EB6']['gap']['DEMES_MIG'], 4, 'EB6 зазор MIG')
c(43, '0,0840', X['EB6']['gap']['DEMES_SIG5'], 4, 'EB6 зазор SIG5')
c(43, '0,927', X['EB6']['rho'], 3, 'ρ Спирмена')
c(43, '0,1957', X['EB6']['gap']['DEMES_IND'], 4, 'EB6 зазор DEMES_IND')
# строка 180 (таблица-текст) пропущена — проверена в tables_vs_raw
# строка 270: самообман
sd = {a: ARM[a]['self_dec'][0] for a in ARM}
others = {a: v for a, v in sd.items() if a not in ('POOLED_NOSEL', 'POOLED_NOSEL_FREE')}
c(270, '−0,0026', min(others.values()), 4, f'мин самообмана (кроме NOSEL pooled): {min(others, key=others.get)}')
c(270, '0,0005', max(others.values()), 4, f'макс самообмана (кроме NOSEL pooled): {max(others, key=others.get)}')
c(270, '0,0248', sd['POOLED_NOSEL'], 4, 'самообман POOLED_NOSEL')
# строка 271: сходимость
for a, ss in (('POOLED', ['−0,0803', '−0,1384', '−0,0203']), ('DEMES', ['0,0299', '0,0019', '0,0598']),
              ('DEMES_NOSEL_FREE', ['−0,0320', '−0,0609', '−0,0026'])):
    for i, s in enumerate(ss):
        c(271, s, an['dynamics'][a]['half_diff'][i], 4, f'половины окна {a} [{i}]')
# строка 276/301: веса сводных (§6 таблица, pilot_calib2.json)
cal2 = json.load(open(f'{D}/pilot/v2/pilot_calib2.json'))['bits']['95']
for comp, s in zip(('SA', 'SA2', 'SA3', 'SB', 'SB2', 'SC'), ('5,3', '5,2', '5,3', '10,0', '10,0', '5,3')):
    for ln in (276, 301):
        c(ln, s, cal2[comp]['bits'], 1, f'вес {comp} (pilot_calib2)')
# строка 278: Бонферрони
c(278, '0,2206', my['fam38'], 4, 'сумма ложных уровней 38 частей (§6)')
c(278, '0,1035', 0.0253 + 0.0274 + 0.0248 + 0.0002 + 0.0002 + 0.0256, 4, 'сумма ложных уровней 6 сводных (§6)')
# строки 281–282: калибровка
c(281, '0,9209', cal['trust04']['conf'], 4, 'средняя уверенность TRUST-04')
c(281, '0,0104', cal['trust04']['brier'], 4, 'Брайер TRUST-04')
c(281, '−0,0791', cal['trust04']['self_dec'], 4, 'самообман TRUST-04')
c(282, '0,8916', cal['post_pilot']['conf'], 4, 'средняя уверенность класса')
c(282, '0,9802', cal['post_pilot']['share'], 4, 'доля подтверждённых класса')
c(282, '0,0301', cal['post_pilot']['brier'], 4, 'Брайер класса')
c(282, '−0,0886', cal['post_pilot']['self_dec'], 4, 'самообман класса')

bad = []
for ln, s, exp, what in checks:
    line = rep[ln - 1]
    present = re.search(rf'(?<![\d,]){re.escape(s)}(?![\d])', line) is not None
    if s != exp or not present:
        bad.append((ln, s, exp, what, 'нет в строке' if not present else ''))
print('проверено чисел прозы (со смыслом):', len(checks))
print('расхождений:', len(bad))
for b in bad:
    print('  ', b)
print('уникальных (строка, число):', len({(a, b) for a, b, _, _ in checks}))
