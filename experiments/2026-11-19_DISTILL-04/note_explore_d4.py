#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""DISTILL-04: записка разведки — числа из gha_out/distill04_explore2/explore.json и tokenizers.json (ERRORS № 200).
Разведка описательная, на данных построения и уже виденных test5/new5; на тест DISTILL-04 (новые ответы) не влияет.
  python3 note_explore_d4.py > NOTE-explore.md"""
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
E1 = json.load(open(os.path.join(ROOT, 'gha_out/distill04_explore/explore.json'), encoding='utf-8'))
E = json.load(open(os.path.join(ROOT, 'gha_out/distill04_explore2/explore.json'), encoding='utf-8'))
TK = json.load(open(os.path.join(ROOT, 'gha_out/distill04_explore2/tokenizers.json'), encoding='utf-8'))
SHORT = {'Falcon3-1B-Instruct': 'Falcon 1B', 'OLMo-2-0425-1B-Instruct': 'OLMo 1B', 'Qwen2.5-0.5B-Instruct': 'Qwen 0,5B',
         'Qwen2.5-1.5B-Instruct': 'Qwen 1,5B', 'SmolLM2-1.7B-Instruct': 'SmolLM 1,7B', 'SmolLM2-360M-Instruct': 'SmolLM 360M',
         'TinyLlama-1.1B-Chat-v1.0': 'TinyLlama 1,1B'}
FAM = {'thousands': '«тысячи»', 'length': '«длина»'}
OP_RU = {'plus10j': '+10^j', 'minus10j': '−10^j без переноса', 'digit_pm1': 'цифра ±1', 'shift': 'сдвиг операнда', 'operand': 'ответ-слагаемое',
         'omit_digit': 'пропуск цифры суммы', 'dup_digit': 'повтор цифры суммы', 'transpose': 'перестановка цифр', 'concat': 'склейка слагаемых',
         'drop_b_digit': 'пропуск цифры b', 'drop_a_digit': 'пропуск цифры a', 'move_b_digit': 'цифра b не в своём разряде',
         'move_a_digit': 'цифра a не в своём разряде'}


def r(x, n=3):
    return f'{x:.{n}f}'.replace('.', ',')


L = []
w = L.append
w('# DISTILL-04 «ПРОЧИЕ» — разведка «прочих» ошибок (19.11.2026; описательно, до PREREG)')
w('')
w('- Задания GitHub Actions: первая разведка — запуск 53f49563, вывод a2b5306e; вторая (добавлены операторы цифр слагаемых и примеры) — запуск 8ccf90a6, вывод 64e094ff.')
w('- Данные — ответы построения (тест OCDIV-03, пилот и тест OCDIV-04) и уже виденные test5/new5 DISTILL-02. Новых ответов голов нет; тест DISTILL-04 будет на новых ответах.')
w('- «Прочий» ответ — числовой, неверный и не объяснимый потерей переносов (`distill02.lost_set`). Один ответ может подходить под несколько операторов.')
w('- Числа печатает `note_explore_d4.py` из json.')
w('')
w('## 1. Доля «прочих» и покрытие')
w('')
w('| голова | семейство | «прочих» среди числовых | объяснено операторами (разведка 1) | объяснено операторами (разведка 2) | покрыто таблицей на test5 |')
w('|---|---|---|---|---|---|')
for fam in ('thousands', 'length'):
    for h, st in E['construction'][fam].items():
        st1 = E1['construction'][fam][h]
        tb = E['sets'][f'test5_{fam}'][h]['table']['share']
        w(f"| {SHORT[h]} | {FAM[fam]} | {r(st['share_other'])} | {r(st1['union']['share'])} | {r(st['union']['share'])} | {r(tb)} |")
w('')
w('- Первые два столбца покрытия — на построении. Таблица — 30 самых частых «прочих» смещений головы на построении (как q программы DISTILL-02), применённая к test5.')
w('- Покрытие — не вероятность: оператор даёт 1–4 кандидата на задачу, таблица — 30 смещений на любую задачу. Сравнение по лог-вероятности — в пилоте.')
w('')
w('## 2. Какие операторы (построение, доля «прочих» ответов)')
for fam in ('thousands', 'length'):
    w('')
    w(f'**{FAM[fam]}**')
    w('')
    ops = [o for o in E['ops'] if max(st['by_op'][o]['share'] for st in E['construction'][fam].values()) >= 0.01]
    w('| голова | ' + ' | '.join(OP_RU[o] for o in ops) + ' |')
    w('|---|' + '---|' * len(ops))
    for h, st in E['construction'][fam].items():
        w(f'| {SHORT[h]} | ' + ' | '.join(r(st['by_op'][o]['share']) for o in ops) + ' |')
    rare = [OP_RU[o] for o in E['ops'] if o not in ops]
    w('')
    w(f"- Меньше 0,01 у всех голов: {', '.join(rare) if rare else 'нет'}.")
w('')
w('## 3. Что осталось необъяснённым (построение, «тысячи»; верх по частоте)')
w('')
for h, st in E['construction']['thousands'].items():
    w(f"- {SHORT[h]}: " + ', '.join(f'{d:+d} ({n})' for d, n in st['unexplained_top'][:6]) + '.')
w('')
w('- Примеры (вывод разведки 2, `unexplained_examples`):')
for h in ('SmolLM2-1.7B-Instruct', 'TinyLlama-1.1B-Chat-v1.0'):
    st = E['construction']['thousands'][h]
    for d, ex in list(st['unexplained_examples'].items())[:1]:
        w(f"  - {SHORT[h]}, смещение {int(d):+d}: " + '; '.join(f'{a} + {b} = {s} → {y}' for a, b, s, y in ex[:5]) + '.')
w('  - В обоих примерах верная сумма перешла через 2000, а ответ остался ниже 2000 с верной цифрой единиц. У TinyLlama при смещении −20 это «199u» (u — верная цифра единиц), у SmolLM 1,7B при −40 — нет (1973, 1964). Это наблюдение по примерам, доля не считалась.')
w('')
w('## 4. Токенизаторы (`tokenizers.json`, только токенизаторы)')
w('')
for h, x in TK['heads'].items():
    ps = [q for q in x['pieces']['2043'] if q.strip()]
    one = all(len(q.strip()) == 1 for q in ps)
    empty = len(ps) < len(x['pieces']['2043'])
    w(f"- {SHORT[h]}: 2043 → {x['pieces']['2043']}; по одной цифре — {'да' if one else 'нет'}{' (плюс пустой служебный кусок в начале)' if empty else ''}.")
w('')
w('- OLMo режет числа группами по три цифры слева направо, остальные шесть — по одной цифре. У OLMo же самая большая доля «прочих». Связь не проверялась (Singh и Strouse описывают такие ошибки у GPT-3.5/4 — записка литературы).')
w('')
w('## 5. Для каталога PREREG (предложение; решает PREREG и совет)')
w('- Брать операторы, которые хоть у одной головы объясняют не меньше 0,01 «прочих» на построении (§2).')
w('- «Зажим» у перехода через сотню первого слагаемого — y = 100·⌊a/100⌋ + 90 + (s mod 10) (§3, TinyLlama) — отдельный кандидат с пометой «найден в разведке по примерам»; его долю посчитать до PREREG.')
w('- Не брать: повтор цифры, перестановку, склейку и другие операторы ниже 0,01 у всех голов.')
w('- Сравнение с нулём «таблица того же размера» — по лог-вероятности на свежих задачах; разведка этого не показывает (§1, примечание).')
print('\n'.join(L))
