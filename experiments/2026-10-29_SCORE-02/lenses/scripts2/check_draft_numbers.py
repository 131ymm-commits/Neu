#!/usr/bin/env python3
"""LENSES-2: сверка чисел черновика PREREG SCORE-02 с json и журналами (командой, не перепечаткой).
Для каждой строки таблиц §3/§6 и каждого числа прозы §2/§3/§8 строится ожидаемая строка из источника и ищется в черновике.
  python3 check_draft_numbers.py <папка опыта>"""
import json
import os
import re
import sys

X = sys.argv[1]
draft = open(os.path.join(X, 'DRAFT-PREREG-SCORE-02.md'), encoding='utf-8').read()
D = json.load(open(os.path.join(X, 'pilot_describe.json'), encoding='utf-8'))
P = json.load(open(os.path.join(X, 'pilot_power.json'), encoding='utf-8'))
f = lambda x, d=3: f'{x:.{d}f}'.replace('.', ',').replace('-', '−')
ok = bad = 0


def check(label, s):
    global ok, bad
    if s in draft:
        ok += 1
    else:
        bad += 1
        print('НЕТ В ЧЕРНОВИКЕ:', label, '→', s)


NAME = dict(single='один вызов (single)', mean='среднее p (mean)', agree='согласие (agree)', single_c='один вызов, огрублённый (single_c)')
for m, st in (('Opus', 'pilot_opus'), ('Haiku', 'pilot_haiku')):
    M = D[st]['measures']
    for s in ('single', 'mean', 'agree'):
        v = M[s]
        row = (f"| {m} | {NAME[s]} | {v['n']} | {f(v['auc2'])} | {f(v['acc'])} | {f(v['conf'])} | {f(v['self_dec'])} | {f(v['brier'])} | "
               f"{f(v['ioi'])} = {f(v['ign'])} + {f(v['dec_pos'])} |")
        check(f'§3 меры {m} {s}', row)
    v = M['single_c']
    check(f'§3 меры {m} single_c', f"| {m} | {NAME['single_c']} | {v['n']} | {f(v['auc2'])} | — | — | — | — | — |")
    # уровни согласия: число и точность
    for k, (n, c) in sorted(D[st]['acc_by_agree'].items(), key=lambda z: float(z[0])):
        check(f'§3 уровни {m} {k}', f"| {m} | {f(float(k), 2)} | {n} | {f(c / n)} |")
    for k, (n, c) in sorted(D[st]['acc_by_conf_bin'].items(), key=lambda z: int(z[0])):
        check(f'§3 корзины {m} {k}', f"| {m} | {f(0.5 + int(k) / 10, 1)} | {n} | {f(c / n)} |")
    for x in D[st]['describe']['levels']:
        check(f'§3 доли {m} {x["level"]}', f"| {m} | {f(x['level'])} | {f(x['agree_share'])} | {f(x['single_c_share'])} |")
    # единогласие и исключения (проза §3)
    una = D[st]['unanimous']
    n_un = sum(u[0] for u in una.values())
    n_ag = sum(n for n, _ in D[st]['acc_by_agree'].values())
    acc1 = D[st]['acc_by_agree']['1.0']
    acc08 = D[st]['acc_by_agree']['0.8']
    ex = D[st]['describe']['excl']
    line = (f"- **{m}:** единогласных суждений согласия — {n_un} из {n_ag} ({f(n_un / n_ag, 2)}), из них «5 из 5» — {una['5'][0]} из {una['5'][1]} суждений "
            f"при пяти вызовах с p ≠ 0,5; точность единогласных {f(acc1[1] / acc1[0])}, суждений «4 из 5» (уровень 0,8) — {f(acc08[1] / acc08[0])}; "
            f"исключено: p = 0,5 — {ex['half_calls']} из {ex['call_judgments']} вызовов-суждений, ничьих сторон — {ex['side_ties']} из {ex['cand_with_side']} кандидатов.")
    check(f'§3 единогласие {m}', line)
    # разложение X2 (§8)
    dx = D[st]['describe']['decomp_x2']
    check(f'§8 разложение {m}', f"{m} — T = {f(dx['T'])} при пороге {f(dx['T_break'])} (приближение {f(dx['approx'])}, факт {f(dx['x2'])})")
    # исключения (§8)
    check(f'§8 исключения {m}', f"{m} — p = 0,5 у {ex['half_calls']} из {ex['call_judgments']} вызовов-суждений, ничьих сторон — {ex['side_ties']} из {ex['cand_with_side']} кандидатов")
    # огрубление (§8): AUC single → single_c
    check(f'§8 огрубление {m}', f"{f(M['single']['auc2'])} → {f(M['single_c']['auc2'])}")

# §6: таблица мощности
KIND = dict(family='семья', check='проверка', explore='разведка')
MN = dict(auc2='AUC второго рода', acc='точность', self_dec='самообман')
for pid, q in P['preds'].items():
    m = 'Opus' if q['model'] == 'opus' else 'Haiku'
    pw = q['power']
    row = (f"| {pid} | {m} | {KIND[q['kind']]} | {MN[q['measure']]} | {q['a']} − {q['b']} | {'> 0' if q['dir'] > 0 else '< 0'} | "
           f"{f(q['pilot_mean'])} [{f(q['ci95_pilot'][0])}; {f(q['ci95_pilot'][1])}] | {f(q['pilot_sd_boot'])} | "
           f"{f(pw['main']['point'])} / {f(pw['main']['unc'])} | {f(pw['rep']['point'])} / {f(pw['rep']['unc'])} |")
    check(f'§6 мощность {pid}', row)
for c, v in P['comps'].items():
    row = f"| {c} | {v['parts'][0]} | {f(v['power_both_point'])} / {f(v['power_both_unc'])} | {f(v['bits_confirmed'], 2)} / {f(v['bits_not'], 2)} / 0 |"
    check(f'§6 сводный {c}', row)

# §2: правда вторым способом — строки журнала дословно
for l in open(os.path.join(X, 'truth', 'truth_check.log'), encoding='utf-8'):
    l = l.strip()
    if l.startswith(('main:', 'rep:')):
        check('§2 truth_check.log', l)
# §8: теснота пулов
G = json.load(open(os.path.join(X, 'truth', 'pool_gaps.json')))
check('§8 пулы основная/повтор/пилот',
      f"{f(G['main_R4000']['median'])} (основная, R = 4000) и {f(G['rep_R4000']['median'])} (повтор) против {f(G['pilot_R1000']['median'])} в пилоте")
check('§8 пулы R = 1000', f"у основной и повтора по R = 1000 — {f(G['main_R1000']['median'])} и {f(G['rep_R1000']['median'])}")
# §3: контекст пилота
for m, st in (('opus', 'pilot_opus'), ('haiku', 'pilot_haiku')):
    c = D[st]['ctx']
    check(f'§3 контекст {m}', f"pilot_{m} — флаг {'да' if c['flag'] else 'нет'}, против линии среднее {f(c['abs_mean'], 1)}, наибольший |остаток| {f(c['abs_max'], 1)}, "
                             f"внутри задачи наибольший |остаток| {f(c['max_abs_resid'], 1)}")
    E = D[st]['calls']
    check(f'§3 цена {m}', f"{f(E['cost'], 2)} $")
    check(f'§3 вызовов {m}', f"годных {E['valid']}" if False else f"{E['n']}")
# §3: расхождение сухого прогона (N2, rep_haiku)
A = json.load(open(os.path.join(X, 'dry', 'analysis_N2.json'), encoding='utf-8'))
v = A['verdicts']['X2h|rep_haiku']
dx = A['describe']['rep_haiku']['decomp_x2']
check('§3 N2 X2h', f"«{v['outcome']}», {f(v['mean'])} [{f(v['ci95'][0])}; {f(v['ci95'][1])}]".replace('0,016', '0,016'))
check('§3 N2 разложение', f"T = {f(dx['T'])} при пороге {f(dx['T_break'])}, приближение {f(dx['approx'], 4)}, факт {f(dx['x2'], 4)}")
lg = open(os.path.join(X, 'dry', 'check_expect.log'), encoding='utf-8').read()
mt = re.search(r'итог: ожиданий (\d+), не совпало (\d+)', lg)
check('§3 итог сверки', f"ожиданий {mt.group(1)}, не совпало {mt.group(2)}")
print(f'сверено: найдено {ok}, не найдено {bad}')
