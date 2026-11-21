#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""LINUX-01, пост-хок: разбор мутантов, которых не убил ни KUnit, ни сравнение (gha_out/linux01_mutants2/mutants.json).
Классы — по чтению кода (Claude), тестом не доказаны: «мёртвый код» (строка после безусловного return binary_gcd в gcd()),
«эквивалентный» (правка не меняет поведения; причина — в поле why), «слепое пятно» (поведение меняется, но входов, на которых
это видно, нет ни в генераторе сравнения, ни в тестах KUnit). Правило привязано к тексту строки: если текст не совпал — «не разобран».
  python3 harness/review_survivors.py MUTANTS.json OUT.json"""
import json
import os
import re
import sys

X = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FN = re.compile(r'^\s*(?:pub\s+)?(?:extern\s+"C"\s+)?(?:unsafe\s+)?fn\s+(\w+)')


def enclosing_fn(src, line):
    for k in range(line - 1, -1, -1):
        m = FN.match(src[k])
        if m:
            return m.group(1)
    return None


def gcd_return_line(src):
    """Строка (с 1) безусловного return binary_gcd(...) в экспортируемой gcd(); None, если его нет."""
    inside = False
    for k, s in enumerate(src, 1):
        if FN.match(s):
            inside = FN.match(s).group(1) == 'gcd'
        if inside and re.search(r'return\s+binary_gcd\(', s):
            return k
    return None


def classify(r, src):
    t, f, mod = src[r['line'] - 1], r['frm'], r['module']
    fn = enclosing_fn(src, r['line'])
    if mod == 'gcd':
        ret = gcd_return_line(src)
        if fn == 'gcd' and ret and r['line'] > ret:
            return 'мёртвый код', f'после return binary_gcd (строка {ret}): ключ efficient_ffs включён, медленный путь не исполняется'
        if fn == 'binary_gcd' and f == '1' and re.search(r'if [ab] == 1\b', t):
            return 'эквивалентный', 'короткий выход: после сдвига число нечётно; без выхода цикл даёт тот же ответ'
        if fn == 'binary_gcd' and f == '<' and 'a < b' in t:
            return 'эквивалентный', 'случай a == b уже вернул ответ строкой выше'
    if mod == 'int_sqrt' and f == '<=' and 'x <= 1' in t:
        return 'эквивалентный', 'при x = 1 цикл даёт 1, как и ранний выход'
    if mod == 'int_log' and fn == 'intlog10' and f == '0' and 'value == 0' in t:
        return 'эквивалентный', 'intlog10(1) = 0 и без раннего выхода; при 0 срабатывает проверка в intlog2, ответ 0'
    if mod == 'rational' and fn == 'min' and f == '<' and 'a < b' in t:
        return 'эквивалентный', 'при a == b min возвращает то же значение'
    if mod == 'cmdline':
        ctx = ' '.join(src[max(0, r['line'] - 3):r['line']])
        if fn == 'get_range' and f == '1' and re.search(r'(^|[{\s])-1\b', t) and 'upper_range < *pint' in ctx:
            return 'эквивалентный', 'знак результата get_range: вызывающий проверяет только range_nums < 0'
        if fn == 'get_options' and f == '>' and 'range_nums > n' in t:
            return 'эквивалентный', 'при range_nums == n исходный код тоже доводит i до nints и выходит из цикла; ints и указатель те же'
        if fn == 'next_arg' and f == '1' and re.search(r'\b(in_quote|quoted) = 1\b', t):
            return 'эквивалентный', 'флаг сравнивается только с нулём и переключается через (x == 0)'
        if f == '13' and '9..=13' in t:
            return 'слепое пятно', ('байта 14 нет ни в генераторе сравнения, ни в тестах KUnit; isspace всех трёх переводов совпадает с ядром '
                                    '(9–13, 32, 160) по чтению кода')
    return 'не разобран', ''


def main(a):
    M = json.load(open(a[0], encoding='utf-8'))
    surv = [r for r in M['rows'] if r.get('compiled') and r.get('linked') and not r['killed_kunit'] and not r['killed_diff']]
    rows = []
    for r in surv:
        src = open(os.path.join(X, 'translations', r['head'], f"{r['module']}.rs"), encoding='utf-8').read().splitlines()
        cls, why = classify(r, src)
        rows.append(dict(head=r['head'], module=r['module'], line=r['line'], frm=r['frm'], to=r['to'], fn=enclosing_fn(src, r['line']),
                         text=src[r['line'] - 1].strip()[:120], cls=cls, why=why))
    counts = {}
    for x in rows:
        counts[x['cls']] = counts.get(x['cls'], 0) + 1
    t = M['total']
    eq = counts.get('мёртвый код', 0) + counts.get('эквивалентный', 0)
    nonequiv = t['alive'] - eq
    res = dict(method='чтение кода (Claude), тестом не доказано', survivors=len(rows), counts=counts,
               behavior_changing=nonequiv, behavior_changing_killed_diff=t['killed_diff'], behavior_changing_killed_kunit=t['killed_kunit'],
               share_behavior_changing_killed_diff=t['killed_diff'] / nonequiv, share_behavior_changing_killed_kunit=t['killed_kunit'] / nonequiv,
               rows=rows)
    json.dump(res, open(a[1], 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print('выживших:', len(rows), '| по классам:', counts, '| меняющих поведение:', nonequiv,
          '| убило сравнение', t['killed_diff'], '| убил KUnit', t['killed_kunit'])
    for x in rows:
        if x['cls'] == 'не разобран':
            print('  НЕ РАЗОБРАН:', x)
    return 0 if 'не разобран' not in counts else 1


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
