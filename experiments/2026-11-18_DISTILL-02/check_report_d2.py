#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""DISTILL-02: сверка ключевых чисел отчёта по точному ключу — каждое число вердиктов, сред и описательного печатается тем же форматом, что в
report_d2.py, из analysis.json и ищется в тексте отчёта. Пишет check_report_d2.log рядом с отчётом; выход 1 при пропуске.
  python3 check_report_d2.py [--selftest] ANALYSIS.json EXPECT.json REPORT.md
После совета 75 (DEVIATIONS.md): целостность строк отчёта, столбец «ящик − B1» и box.total > 0 по 15 средам, число параметров программ."""
import json
import os
import sys

X = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, X)
import report_d2 as RP  # noqa: E402


PAIRS = (('(', ')'), ('[', ']'), ('{', '}'), ('«', '»'))


def broken_lines(md):
    """Строки с непарными скобками (), [], {}, «» или с нечётным числом кавычек " — признак обрыва (совет 75, «нужно» 4: прибор обрывался
    на json.dumps(...)[:300])."""
    return [ln for ln in md.splitlines() if any(ln.count(o) != ln.count(c) for o, c in PAIRS) or ln.count('"') % 2]


def selftest():
    """Проверка от обратного: строка, оборванная как прежний вывод прибора, должна ловиться; целая строка отчёта — нет."""
    cut = '- Прибор (`trunc_check.py`): ' + json.dumps({'rows': [{'file': 'x', 'n_numeric': 2200, 'n_prefix_of_truth': 0}]})[:40] + '.'
    ok = '| T_X19_p3 | 7 | +0,1485 (0,0064) | σ(+1.1 -20·prop) | [+0,1950; +0,2073] | «тысячи» |'
    assert broken_lines(cut) == [cut], 'самопроверка: оборванная строка не поймана'
    assert broken_lines(ok) == [], 'самопроверка: целая строка помечена как оборванная'
    print('самопроверка целостности строк: оборванная поймана, целая пропущена')


def main(a):
    if '--selftest' in a:
        selftest()
        a = [x for x in a if x != '--selftest']
    A = json.load(open(a[0], encoding='utf-8'))
    EX = json.load(open(a[1], encoding='utf-8'))
    md = open(a[2], encoding='utf-8').read()
    checks = []

    def need(name, s):
        checks.append((name, s, s in md))
    for r, e in A['rules'].items():
        if 'ci' not in e:
            need(f'rules.{r}.verdict', e['verdict_rule'])
            continue
        need(f'rules.{r}.delta', RP.f(e['delta']))
        need(f'rules.{r}.ci', RP.ci(e))
        need(f'rules.{r}.t', RP.tt(e['t_envs']['t']))
        need(f'rules.{r}.label', RP.label(r, e))
        if e.get('fragile'):
            need(f'rules.{r}.fragile', RP.frag_words(e))
        if e.get('lambda_sens'):
            need(f'rules.{r}.lambda', RP.lam_words(e))
        if not e.get('active'):                                  # у описательных — слова о границе, не вердикт
            head = md.split('## Ожидания')[0]
            checks.append((f'rules.{r}.нет вердиктного слова в строке правила', f'| {r} |',
                           all(e['verdict_rule'] not in line for line in head.splitlines() if line.startswith(f'| {r} |'))))
    for n, e in A['envs'].items():
        pt, sd = e['point'], e['sd']
        need(f'envs.{n}.m1', f"{RP.f(pt['m1'])} ({RP.g(sd['m1'])})")
        need(f'envs.{n}.m1_phi', f"{RP.f(pt['m1_phi'])} ({RP.g(sd['m1_phi'])})")
        need(f'envs.{n}.m2', f"{RP.g(pt['m2'], 3)} ({RP.g(sd['m2'], 3)})")
        need(f'envs.{n}.m3', f"{RP.f(pt['m3'])} ({RP.g(sd['m3'])})")
        bt = e['concentration']['box']['total']                     # знаменатель m2: ящик − B1 (совет 75, «нужно» 5)
        need(f'envs.{n}.box_total', f"| {RP.g(pt['m2'], 3)} ({RP.g(sd['m2'], 3)}) | {RP.f(bt)} |")
        checks.append((f'envs.{n}.box_total > 0', RP.f(bt), bt > 0))
    for fam, fs in A['formulas'].items():
        for h, fm in fs.items():
            need(f'formulas.{fam}.{h}.params', f"| {RP.g(fm['eps'], 3)} | {RP.n_params(fm)} |")
    bad_lines = broken_lines(md)
    checks.append(('целостность строк (скобки и кавычки парны)', f'оборванных строк: {len(bad_lines)}', not bad_lines))
    for k, e in A['descr'].items():
        need(f'descr.{k}', f"| {k} | {RP.f(e['delta'])} | {RP.ci(e)} |")
    for e in EX['expectations']:
        need(f"expect.{e['id']}", f"| {e['id']} | {e['text']} | {RP.g(e['p'], 4 if e['p'] < 0.01 else 3)} | {'да' if RP.outcome(A, e['key']) else 'нет'} |")
    bad = [c for c in checks if not c[2]]
    log = [f"{'✓' if ok else '✗'} {name}: {s}" for name, s, ok in checks] + [f'проверок: {len(checks)}; пропусков: {len(bad)}']
    open(os.path.join(os.path.dirname(os.path.abspath(a[2])), 'check_report_d2.log'), 'w', encoding='utf-8').write('\n'.join(log) + '\n')
    print(log[-1])
    sys.exit(1 if bad else 0)


if __name__ == '__main__':
    main(sys.argv[1:])
