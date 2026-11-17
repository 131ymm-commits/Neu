#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""LINUX-01: записка пилота по мерам PLAN.md. Вход: gha_out/linux01_eval/eval.json (оценка переводов) и check.json (обвязка в том
же прогоне), translations/<голова>/<модуль>.json (расход токенов и цена по CLI), sealing_facts.json, gha_out/linux01_probe*/.
Числа — из json; производные (суммы, доли, цена на строку) — в note_derived.json. Описательно; вес 0 (PLAN).
Вердикт «верен» считает harness/run.py (закоммичен до переводов); здесь он только читается.
  python3 note_linux01.py"""
import json
import os
import re
import subprocess

X = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(X))
G = os.path.join(ROOT, 'gha_out')
E = json.load(open(os.path.join(G, 'linux01_eval', 'eval.json'), encoding='utf-8'))
C = json.load(open(os.path.join(G, 'linux01_eval', 'check.json'), encoding='utf-8'))
S = json.load(open(os.path.join(X, 'sealing_facts.json'), encoding='utf-8'))
HEADS = ['haiku', 'sonnet', 'opus']
NAME = {'haiku': 'Haiku 5.5', 'sonnet': 'Sonnet 5.5', 'opus': 'Opus 5.5'}
MODS = list(E['modules'])
T = {(h, m): json.load(open(os.path.join(X, 'translations', h, f'{m}.json'), encoding='utf-8')) for h in HEADS for m in MODS}
OUT = os.path.join(X, 'NOTE-LINUX-01.md')


def n(x, k=3):
    if x is None:
        return '—'
    s = f'{abs(x):.{k}f}'.replace('.', ',')
    return ('−' if x < 0 and float(s.replace(',', '.')) != 0 else '') + s


def i(x):
    return '—' if x is None else f'{x:,}'.replace(',', ' ')


def git(*a):
    return subprocess.run(['git', '-C', ROOT] + list(a), capture_output=True, text=True).stdout.strip()


def clean(s, k=150):
    s = ''.join(c if 32 <= ord(c) < 127 or ord(c) > 0xa0 else f'\\x{ord(c):02x}' for c in (s or ''))
    return (s[:k] + '…') if len(s) > k else s


R = {m: E['modules'][m]['heads'] for m in MODS}
der = dict(cells={}, heads={}, expectations={}, l4_witness=[])
for m in MODS:
    for h in HEADS:
        r = R[m].get(h)
        k = (r or {}).get('kunit') or {}
        df = (r or {}).get('diff') or {}
        der['cells'][f'{h}/{m}'] = dict(
            present=r is not None, compiled=bool(r and r['compiled']), linked=bool(r and r.get('linked')), correct=bool(r and r['correct']),
            kunit_total=k.get('total'), kunit_failed=k.get('failed'),
            kunit_passed=(k['total'] - k['failed']) if k else None,
            diff_n=sum(v['n'] for v in df.values()) if df else None,
            diff_mismatches=sum(v['mismatches'] for v in df.values()) if df else None,
            diff_crashed_chunks=sum(v['crashed_chunks'] for v in df.values()) if df else None,
            diff_mismatch_share=(sum(v['mismatches'] for v in df.values()) / sum(v['n'] for v in df.values())) if df else None)
        c = der['cells'][f'{h}/{m}']
        if c['compiled'] and c['linked'] and c['kunit_failed'] == 0 and c['diff_mismatches']:
            der['l4_witness'].append(f'{h}/{m}')

c_total = sum(E['modules'][m]['c_lines'] for m in MODS)
der['c_lines_total'] = c_total
for h in HEADS:
    us = [T[(h, m)].get('usage') or {} for m in MODS]
    tin = sum(u.get('input_tokens', 0) + u.get('cache_read_input_tokens', 0) + u.get('cache_creation_input_tokens', 0) for u in us)
    tout = sum(u.get('output_tokens', 0) for u in us)
    cost = sum(T[(h, m)].get('total_cost_usd') or 0 for m in MODS)
    der['heads'][h] = dict(
        correct=sum(der['cells'][f'{h}/{m}']['correct'] for m in MODS), modules=len(MODS),
        tokens_in=tin, tokens_out=tout, cost_usd=cost, seconds=sum(T[(h, m)].get('seconds') or 0 for m in MODS),
        tokens_in_per_c_line=tin / c_total, tokens_out_per_c_line=tout / c_total, cost_usd_per_c_line=cost / c_total,
        cost_usd_per_1000_c_lines=1000 * cost / c_total, cost_usd_per_million_c_lines=1e6 * cost / c_total,
        rs_lines=sum((R[m].get(h) or {}).get('rs_lines', 0) for m in MODS), unsafe=sum((R[m].get(h) or {}).get('unsafe', 0) for m in MODS))
der['cost_usd_all'] = sum(v['cost_usd'] for v in der['heads'].values())
H = der['heads']
EXP = [('L1', 'Opus 5.5: верны не меньше 5 модулей из 6', 0.70, H['opus']['correct'] >= 5),
       ('L2', 'Sonnet 5.5: верны не меньше 5 модулей из 6', 0.60, H['sonnet']['correct'] >= 5),
       ('L3', 'Haiku 5.5: верны не меньше 4 модулей из 6', 0.50, H['haiku']['correct'] >= 4),
       ('L4', 'хотя бы один перевод проходит все тесты KUnit, но расходится с оригиналом', 0.50, bool(der['l4_witness'])),
       ('L5', 'cmdline.c: верен хотя бы у одной головы из трёх', 0.60, any(der['cells'][f'{h}/cmdline']['correct'] for h in HEADS))]
der['expectations'] = {k: dict(text=t, p=p, outcome=o) for k, t, p, o in EXP}
# обвязка в том же прогоне
chk = C['modules']
der['check'] = dict(kunit_cases=sum(v['kunit']['total'] for v in chk.values()), kunit_failed=sum(v['kunit']['failed'] for v in chk.values()),
                    self_diff_mismatches=sum(x['mismatches'] for v in chk.values() for x in v['self_diff'].values()),
                    self_diff_n=sum(x['n'] for v in chk.values() for x in v['self_diff'].values()),
                    kunit_cases_without_rational=sum(v['kunit']['total'] for k_, v in chk.items() if k_ != 'rational'))
json.dump(der, open(os.path.join(X, 'note_derived.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)

# коммиты: план, обвязка, переводы, оценка
P = 'experiments/2026-11-17_LINUX-01/'
c_plan = git('log', '--diff-filter=A', '--format=%h', '--', P + 'PLAN.md').splitlines()[-1]
c_run = git('log', '-1', '--format=%h', '--', P + 'harness/run.py')
c_tr = git('log', '--diff-filter=A', '--format=%h', '--', P + 'translations/opus/cmdline.rs').splitlines()[-1]
c_ev = git('log', '-1', '--format=%h', '--', 'gha_out/linux01_eval/eval.json')
run_before = subprocess.run(['git', '-C', ROOT, 'merge-base', '--is-ancestor', c_run, c_tr]).returncode == 0


def cell(h, m):
    c, r = der['cells'][f'{h}/{m}'], R[m].get(h)
    if not c['present']:
        return 'нет перевода'
    if not c['compiled']:
        return 'не собрался'
    if not c['linked']:
        return 'не слинковался'
    kk = f"KUnit {c['kunit_passed']}/{c['kunit_total']}" if c['kunit_total'] is not None else 'KUnit не запустился'
    dd = f"расх. {i(c['diff_mismatches'])} из {i(c['diff_n'])}" if c['diff_n'] is not None else 'сравнение не запустилось'
    return ('**верен**' if c['correct'] else 'неверен') + f' · {kk} · {dd}'


L = []
add = L.append
add('# LINUX-01 «ПЕРЕВОД-МОДУЛЯ» — записка пилота')
add('')
add(f'**Слово автора:** «делай пилот с модулем Линукса.» План — `PLAN.md`, коммит {c_plan}. Он закоммичен до переводов. '
    f'Вердикт «верен» считает `harness/run.py`; последний раз он менялся в {c_run}, '
    + ('то есть до переводов' if run_before else '**после переводов — проверить!**') + f' (переводы — {c_tr}). Оценка — GitHub Actions, коммит результатов {c_ev}.')
add('')
add('Описательно, вес опоры: 0 бит (PLAN: «записи в реестр — только описательные, вес 0»).')
add('')
add('## Итог')
add('')
add('Верных переводов из 6: ' + ', '.join(f"{NAME[h]} — {H[h]['correct']}" for h in HEADS) + '. '
    '«Верен» значит: собрался, прошёл все случаи KUnit модуля и не разошёлся с оригиналом ни на одном из 100 000 случайных входов на функцию.')
add('')
add('| Модуль (строк C) | ' + ' | '.join(NAME[h] for h in HEADS) + ' |')
add('|---|' + '---|' * len(HEADS))
for m in MODS:
    add(f"| {m} ({E['modules'][m]['c_lines']}) | " + ' | '.join(cell(h, m) for h in HEADS) + ' |')
add('')
add('«Расх.» — входы, на которых перевод ответил не так, как оригинал. Если порция из 1000 входов упала (паника Rust или сигнал), '
    'все её входы считаются расхождениями: это верхняя граница.')
add('')
add('## Ожидания (PLAN, до переводов)')
add('')
add('| № | Исход | Вероятность | Сбылось |')
add('|---|---|---|---|')
for k, t, p, o in EXP:
    add(f'| {k} | {t} | {n(p, 2)} | {"да" if o else "нет"} |')
if der['l4_witness']:
    add('')
    add('L4 — переводы, которые прошли все тесты KUnit и разошлись с оригиналом: ' + ', '.join(der['l4_witness']) + '.')
add('')
add('## Расход (по ответу CLI: usage, total_cost_usd)')
add('')
add(f'Строк исходника C во всех шести модулях: {i(c_total)} (непустые). Вход — поручение с исходником и системный промпт CLI; '
    'выход включает рассуждение модели.')
add('')
add('| Голова | Верных | Токенов на входе | Токенов на выходе | Цена, $ | $ на строку C | $ на 1000 строк C | Строк Rust | unsafe |')
add('|---|---|---|---|---|---|---|---|---|')
for h in HEADS:
    v = H[h]
    add(f"| {NAME[h]} | {v['correct']} из {v['modules']} | {i(v['tokens_in'])} | {i(v['tokens_out'])} | {n(v['cost_usd'], 4)} | "
        f"{n(v['cost_usd_per_c_line'], 6)} | {n(v['cost_usd_per_1000_c_lines'], 3)} | {i(v['rs_lines'])} | {v['unsafe']} |")
add('')
add(f"Всего за 18 переводов: {n(der['cost_usd_all'], 4)} $ по расчёту CLI (цены API). Переводы шли через сессию Claude Code, "
    'ключ API автора не использовался.')
add('')
add('**Пост-хок, арифметика (не мера PLAN):** при той же цене на строку миллион строк C стоил бы ' +
    ', '.join(f"{NAME[h]} — {n(H[h]['cost_usd_per_million_c_lines'], 0)} $" for h in HEADS) +
    '. Это нижняя оценка для простого кода: шесть модулей — чистые функции без зависимостей. Перевод драйвера требует заголовков и соседних '
    'файлов во входе, а неверные переводы — повторов. Не проверялось.')
add('')
add('## Где ошибки')
add('')
bad = [(h, m) for m in MODS for h in HEADS if not der['cells'][f'{h}/{m}']['correct']]
if not bad:
    add('Неверных переводов нет.')
for h, m in bad:
    r = R[m].get(h) or {}
    if r and not r.get('compiled'):
        first = next((ln for ln in (r.get('compile_err') or '').splitlines() if 'error' in ln), '')
        add(f'- {h}/{m}: не собрался — `{clean(first)}`')
        continue
    k = r.get('kunit') or {}
    fails = [f"{c['case']}" + (f"[{c['param']}]" if c['param'] else '') + (' (упал)' if c['crashed'] else '')
             for c in k.get('cases', []) if not c['ok']]
    ex = [f"{fn}: `{clean(v['example'])}`" for fn, v in (r.get('diff') or {}).items() if v['mismatches']]
    add(f'- {h}/{m}: KUnit — ' + (', '.join(fails[:4]) + (' …' if len(fails) > 4 else '') if fails else 'все случаи прошли') +
        '; сравнение — ' + ('; '.join(ex[:3]) if ex else 'расхождений нет'))
add('')
MUT = os.path.join(G, 'linux01_mutants', 'mutants.json')
add('## Может ли оценщик провалить перевод (пост-хок, мутанты; вердиктов PLAN не меняет)')
add('')
if os.path.exists(MUT):
    M = json.load(open(MUT, encoding='utf-8'))
    t = M['total']
    add(f"Мутантов делает скрипт механически (`harness/mutants.py`), головы не участвуют: одна правка в переводе — сравнение (`<`↔`<=`, `==`↔`!=`), "
        f"плюс-минус, логика (`&&`↔`||`), сдвиг, константа N→N+1. До {M['per_file']} мест на файл, зерно {M['seed']}. "
        f"Всего {i(t['generated'])} мутантов; не собрались {i(t['stillborn'])} — в доли не входят; живых {i(t['alive'])}. "
        f"Сравнение — {i(M['n'])} входов на функцию, как в оценке.")
    add('')
    add('| Модуль | Живых | Убил KUnit | Убило сравнение | KUnit пропустил, сравнение поймало | Сравнение пропустило, KUnit поймал | Выжили оба |')
    add('|---|---|---|---|---|---|---|')
    for m, v in list(M['by_module'].items()) + [('**всего**', t)]:
        add(f"| {m} | {v['alive']} | {v['killed_kunit']} | {v['killed_diff']} | {v['kunit_missed_diff_caught']} | {v['diff_missed_kunit_caught']} | "
            f"{v['survived_both']} |")
    add('')
    add(f"Доля убитых: KUnit — {n(t['share_killed_kunit'])}, сравнением — {n(t['share_killed_diff'])}. "
        f"Зависания (считаются убийством): KUnit — {t['kunit_timeouts']}, сравнение — {t['diff_timeouts']}. По видам правки (убил KUnit / убило сравнение из живых): "
        + '; '.join(f"{k} — {v['killed_kunit']}/{v['killed_diff']} из {v['alive']}" for k, v in M['by_kind'].items()) + '.')
    add('')
    add('«Выжили оба» — либо эквивалентные мутанты (правка не меняет поведения: например, убран короткий путь), либо слепые места обоих '
        'оценщиков. По одному они не разбирались.')
else:
    add('Замер идёт (`jobs/linux01_mutants.sh`).')
add('')
add('## Честность замера')
add('')
add(f"- Обвязка в том же прогоне: оригиналы на C — {der['check']['kunit_cases']} случаев KUnit, провалено {der['check']['kunit_failed']}; "
    f"оригинал против самого себя — {i(der['check']['self_diff_mismatches'])} расхождений на {i(der['check']['self_diff_n'])} входах.")
add(f"- Запечатывание (`sealing_facts.json`, `harness/sealing_facts.py`): {sum(r['ok'] for r in S['rows'])} из {S['n']} переводов прошли "
    'все проверки: хеш поручения совпадает с закоммиченным, `--tools ""`, папка вызова вне репозитория и пуста, модель ответа — заказанная.')
add('- Тестов и обвязки головы не видели: в поручении только исходник модуля, условия сборки и смысл макросов (`prompts/`).')
add(f"- Сборка Rust: {E['rustc']}, `-C overflow-checks=on -C panic=abort` (как CONFIG_RUST_OVERFLOW_CHECKS).")
add('- Отклонения от плана — `DEVIATIONS.md`. До записки я видел вердикты cmdline в хвосте журнала (ERRORS № 193).')
add('')
add('## Ступень Б — в ядре (проба раннера)')
add('')
p1 = open(os.path.join(G, 'linux01_probe', 'probe.log'), encoding='utf-8').read()
kv = re.search(r'ядро: (\w+) (\S+)', p1)
mv = re.search(r'минимальные версии: (.*)', p1)
add(f"- Проба 1: ядро {kv.group(2)} (коммит {kv.group(1)[:12]}). `make LLVM=1 rustavailable` — «Rust is available!»; минимальные версии: {mv.group(1)}. "
    'KUnit в UML не запустился: тест rational нельзя включить из kunitconfig (ERRORS № 192).')
p2f = os.path.join(G, 'linux01_probe2', 'probe.log')
if os.path.exists(p2f):
    p2 = open(p2f, encoding='utf-8').read()
    ran = re.findall(r'Ran \d+ tests.*', p2) or re.findall(r'Testing complete.*', p2)
    code = re.search(r'KUnit в UML: код (\d+)', p2)
    add(f"- Проба 2 (пять модулей, без rational): kunit.py — код {code.group(1) if code else '?'}; " + ('; '.join(r.strip() for r in ran) if ran else 'итога нет') +
        f". Это тесты оригиналов на C в настоящем ядре (User Mode Linux). В обвязке ступени А у тех же пяти модулей случаев "
        f"тоже {der['check']['kunit_cases_without_rational']}, если считать каждый параметр отдельно: исполнитель вне ядра насчитывает столько же "
        "(совпадение числа, а не поимённая сверка).")
else:
    add('- Проба 2 (пять модулей, без rational): идёт.')
add('- Перевод внутри ядра — только отдельным планом (PLAN, ступень Б).')
add('')
add('## Чего записка не утверждает')
add('')
add('- Что Линукс можно перевести: шесть малых модулей без драйверов, работа вне ядра.')
add('- Что переводы эквивалентны оригиналу: 100 000 случайных входов на функцию — выборка, не доказательство.')
add('- Что переводы идиоматичны или безопасны: мерилось только поведение.')
add('- Что исход повторится: каждая голова переводила каждый модуль один раз.')
open(OUT, 'w', encoding='utf-8').write('\n'.join(L) + '\n')
print('записка:', OUT)
print('верных:', {h: H[h]['correct'] for h in HEADS}, '| ожидания:', {k: o for k, _, _, o in EXP})
