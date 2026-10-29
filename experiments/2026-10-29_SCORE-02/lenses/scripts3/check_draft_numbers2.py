#!/usr/bin/env python3
"""LENSES-3: сверка новых чисел черновика (после правок по LENSES-2) с json и журналами командой.
  python3 check_draft_numbers2.py <папка опыта>"""
import json
import os
import re
import sys

X = sys.argv[1]
draft = open(os.path.join(X, 'DRAFT-PREREG-SCORE-02.md'), encoding='utf-8').read()
f = lambda x, d=3: f'{x:.{d}f}'.replace('.', ',').replace('-', '−')
ok = bad = 0


def check(label, s):
    global ok, bad
    if s in draft:
        ok += 1
    else:
        bad += 1
        print('НЕТ В ЧЕРНОВИКЕ:', label, '→', s)


# первый прогон — dry/run1
A = json.load(open(os.path.join(X, 'dry', 'run1', 'analysis_N2.json'), encoding='utf-8'))
v = A['verdicts']['X2h|rep_haiku']; dx = A['describe']['rep_haiku']['decomp_x2']
check('§3 прогон 1, N2 X2h', f"«{v['outcome']}», {f(v['mean'])} [{f(v['ci95'][0])}; {f(v['ci95'][1])}]")
check('§3 прогон 1, N2 разложение', f"T = {f(dx['T'])} при пороге {f(dx['T_break'])}, приближение {f(dx['approx'], 4)}, факт {f(dx['x2'], 4)}")
check('§3 прогон 1, N2 статус', f"status SB_haiku: «{A['status']['SB_haiku']['status']}»")
m = re.search(r'итог: ожиданий (\d+), не совпало (\d+)', open(os.path.join(X, 'dry', 'run1', 'check_expect.log'), encoding='utf-8').read())
check('§3 прогон 1, итог', f'ожиданий {m.group(1)}, не совпало {m.group(2)}')
# второй прогон
m = re.search(r'итог: ожиданий (\d+), не совпало (\d+)', open(os.path.join(X, 'dry', 'check_expect2.log'), encoding='utf-8').read())
check('§3 прогон 2, итог', f'ожиданий {m.group(1)}, не совпало {m.group(2)}')
A3 = json.load(open(os.path.join(X, 'dry', 'analysis_A3.json'), encoding='utf-8'))
v = A3['verdicts']['X1o|main_opus']
check('§3 прогон 2, A3 X1o', f"verdicts X1o|main_opus: «{v['outcome']}», {f(v['mean'])} [{f(v['ci95'][0])}; {f(v['ci95'][1])}]")
check('§3 прогон 2, A3 статус', f"status SA_opus: «{A3['status']['SA_opus']['status']}»")
for br in ('A', 'D', 'Dm', 'A3'):
    v = json.load(open(os.path.join(X, 'dry', f'analysis_{br}.json'), encoding='utf-8'))['verdicts']['X1o|main_opus']
    check(f'§3 прогон 2, {br} X1o', f"{br} {f(v['mean'])} [{f(v['ci95'][0])}; {f(v['ci95'][1])}]")
# §5: z пилота X3
P = json.load(open(os.path.join(X, 'pilot_power.json'), encoding='utf-8'))
zo, zh = P['preds']['X3o']['z_pilot'], P['preds']['X3h']['z_pilot']
print(f'z пилота: X3o {zo!r}, X3h {zh!r}')
check('§5 z X3', f"{f(zo, 2)} SD у Opus и {f(zh, 2)} у Haiku")
# §6: нуль контроля — числа из lenses/scripts2/null/summary.log (LENSES-2)
S = open(os.path.join(X, 'lenses', 'scripts2', 'null', 'summary.log'), encoding='utf-8').read()
i100 = float(re.search(r'n = 100: доля «подтверждено» X1oc при Δc = 0 \(линейно по 3 точкам\) ([0-9.]+)', S).group(1))
i59 = float(re.search(r'n = 59: доля «подтверждено» X1oc при Δc = 0 \(линейно по 3 точкам\) ([0-9.]+)', S).group(1))
check('§6 нуль', f'около {f(i100)} на 100 задачах и {f(i59)} на 59')
h1 = float(re.search(r'hi_s060_n100: .*?X1oc подтверждено ([0-9.]+)', S).group(1)); h2 = float(re.search(r'hi_s060_n59: .*?X1oc подтверждено ([0-9.]+)', S).group(1))
check('§6 нуль, единогласие', f'{f(h1)}–{f(h2)}')
# §8 и §0: Ferrer (числа источника, сниппет LENSES-2) и Ding
for s in ('0,018, 0,027', '−0,001', 'ECE 0,30 против 0,32', 'K = 10, 48 вопросов', 'ρ 0,31 против 0,21', '0,1871 против 0,1889'):
    check('источники/SCORE-01', s)
print(f'сверено: найдено {ok}, не найдено {bad}')
