#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""DISTILL-03: отчёт из вывода теста — все числа из gha_out/distill03_test/test.json (и логов задания), руками не переписываются.
Каркас написан до вывода теста (после регистрации 4b382924 и запуска 0dd19837, до просмотра test.json). Вердикты и текст для C-109 —
по PREREG §5 (правило «П и Ф», совет 76); описательное — без вердиктов. Заметки после данных — отдельным разделом, вердикт не меняют.
  python3 report_d3.py ВЫВОД_КОММИТ [--out ПАПКА] > REPORT-DISTILL-03.md"""
import json
import math
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)
import ab  # noqa: E402

OUT = os.path.join(ROOT, 'gha_out/distill03_test')
SHORT = {'Falcon3-1B-Instruct': 'Falcon 1B', 'OLMo-2-0425-1B-Instruct': 'OLMo 1B', 'Qwen2.5-0.5B-Instruct': 'Qwen 0,5B',
         'Qwen2.5-1.5B-Instruct': 'Qwen 1,5B', 'SmolLM2-1.7B-Instruct': 'SmolLM 1,7B', 'SmolLM2-360M-Instruct': 'SmolLM 360M',
         'TinyLlama-1.1B-Chat-v1.0': 'TinyLlama 1,1B'}
FAM = {'thousands': '«тысячи»', 'length': '«длина»'}
KIND = {'prog': 'программа', 'shape': 'форма'}
PILOT_OTHERS_SHARE = 0.7735          # PREREG §5: доля «прочих» в D пилота (prereg_numbers_d3.py)
SHARE_MIN = 0.5                      # PREREG §5: ниже — строка «разбивка теста разошлась с пилотом»


def r(x, n=4, sign=False):
    """Число по-русски: запятая, минус U+2212; sign — «+» у положительных."""
    if x is None or (isinstance(x, float) and not math.isfinite(x)):
        return '—'
    s = f'{x:+.{n}f}' if sign else f'{x:.{n}f}'
    return s.replace('-', '−').replace('.', ',')


def pval(p):
    return r(p, 6)


def read(name):
    p = os.path.join(OUT, name)
    return open(p, encoding='utf-8').read() if os.path.exists(p) else ''


def c109_text(v):
    """PREREG §5, таблица «П и Ф» (совет 76, п. 1): текст определяется только парой АБ-П-Т / АБ-Ф-Т."""
    P, F = v['АБ-П-Т']['verdict'], v['АБ-Ф-Т']['verdict']
    if P == 'непроверяемо':
        return ('C-109 остаётся «подтверждено»; дописывается: «контроль A-на-B не проверяем (k, наименьшее p)».', None)
    if P == 'нет':
        return ('C-109 остаётся «подтверждено» с пометой: «программа неспецифична на „тысячах“: чужие программы предсказывают ответы головы '
                'не хуже своей (D, p)».', None)
    if P == 'да' and F == 'да':
        return ('C-109 — «установлено»: программа головы своя вместе с формулой переноса.', None)
    return ('C-109 остаётся «подтверждено»; дописывается: «специфичность формулы переноса не показана».',
            '«установлено»: «ошибки головы специфичны по частотам и уровню; вклад формулы переноса не подтверждён».')


def main(a):
    global OUT
    if '--out' in a:                                   # для проверки каркаса на выводе сухого прогона
        OUT = a[a.index('--out') + 1]
        a = [x for i, x in enumerate(a) if x != '--out' and (i == 0 or a[i - 1] != '--out')]
    out_commit = a[0] if a else '—'
    t = json.load(open(os.path.join(OUT, 'test.json'), encoding='utf-8'))
    exp = json.load(open(os.path.join(HERE, 'expect_d3.json'), encoding='utf-8'))['rules']
    v = t['verdicts']
    F = t['families']
    L = []
    w = L.append
    w('# DISTILL-03 «A-НА-B» — отчёт (19.11.2026)')
    w('')
    w(f'- **Регистрация** — 4b382924 (`PREREG-DISTILL-03.md`; совет 76 принял единогласно). **Запуск** — 0dd19837. **Вывод** — {out_commit}, папка `gha_out/distill03_test/`.')
    w('- Все числа — из `test.json` и логов задания; их печатает `report_d3.py`. Его каркас написан до вывода теста. Сверка — `ledger.py audit`.')
    w('- Единицы — наты на ответ (средняя лог-вероятность, смесь λ = 1e-3).')
    w('')
    # ── коротко
    w('## Коротко')
    for rule in ab.RULES:
        x = v[rule]
        w(f"- **{rule}** ({FAM[x['family']]}, {KIND[x['kind']]}): **{x['verdict']}** — D {r(x.get('D'), 4, True)}, точное p {pval(x.get('p'))}, "
          f"голов k = {x.get('k')}, наименьшее возможное p {pval(x.get('min_p'))}.")
    txt, new = c109_text(v)
    w(f'- **C-109 по правилу «П и Ф»** (PREREG §5): {txt}')
    if new:
        w(f'- **Новое утверждение:** {new}')
    if any(v[x]['verdict'] == 'нет' for x in ('АБ-Ф-Т', 'АБ-Ф-Л')):
        w('- **«Нет» по форме не доказывает, что форма общая:** мощность формы при общем шуме около 0,58 (PREREG §6).')
    w('')
    # ── прибор
    w('## Прибор')
    hl = read('hashes.log').strip().splitlines()
    w(f"- Сверка хешей регистрации: {hl[-1] if hl else '—'}.")
    tl = read('tests.log').strip().splitlines()
    w(f"- Тесты кода: {tl[-1] if tl else '—'}.")
    rs = read('raw_status_test.log').strip().splitlines()
    w(f"- Тест замка сырого вывода (№ 180): {rs[-1] if rs else '—'}.")
    fl = [x for x in read('fits.log').strip().splitlines() if x]
    w(f"- Программы и DISTILL-02 (замок а): {fl[-1] if fl else '—'}.")
    w(f"- Детерминизм (второй прогон, побайтно без seconds): {read('det.txt').strip() or '—'}.")
    w(f"- Хеши кода в выводе: ab.py {t['code']['ab.py'][:12]}…, distill02.py {t['code']['distill02.py'][:12]}…; время счёта {r(t['seconds'], 1)} с.")
    for fam, fr in F.items():
        w(f"- {FAM[fam]}: головы в проверке — {fr.get('k')} ({', '.join(SHORT[h] for h in fr.get('heads_kept', []))}); "
          f"выкинуты головы — {[SHORT[h] for h in fr.get('heads_dropped', [])] or 'нет'}; среды — {len(fr.get('envs_kept', []))} "
          f"({', '.join(fr.get('envs_kept', []))}); выкинуты среды — {fr.get('envs_dropped') or 'нет'}.")
    w('')
    # ── решающие правила
    w('## 1. Решающие правила (PREREG §5; уровень 0,0025 на проверку, серия ≤ 0,0095)')
    w('')
    w('| правило | семейство | вид | сред | k | D | p (точное) | ранг из k! | различных D_π | вердикт |')
    w('|---|---|---|---|---|---|---|---|---|---|')
    for rule, (fam, kind) in ab.RULES.items():
        x = v[rule]
        fr = F.get(fam, {})
        rr = fr.get(kind, {})
        w(f"| {rule} | {FAM[fam]} | {KIND[kind]} | {len(fr.get('envs_kept', []))} | {x.get('k')} | {r(x.get('D'), 4, True)} | {pval(x.get('p'))} | "
          f"{rr.get('rank', '—')} из {rr.get('n_perm', '—')} | {rr.get('n_distinct', '—')} | **{x['verdict']}** |")
    w('')
    # ── по головам
    w('## 2. По головам (описательно)')
    for fam, fr in F.items():
        if fr.get('empty'):
            w(f'- {FAM[fam]}: проверять нечего (нет полных голов и сред).')
            continue
        hk = fr['heads_kept']
        w('')
        w(f"**{FAM[fam]}** — s(B, B): своя минус среднее чужих; зазор — своя минус лучшая чужая (среднее по средам); вклад входа — своя программа минус своя без входа.")
        w('')
        w('| голова | s программы | s формы | зазор программы | зазор формы | вклад входа |')
        w('|---|---|---|---|---|---|')
        for i, h in enumerate(hk):
            w(f"| {SHORT[h]} | {r(fr['prog']['s'][i][i], 4, True)} | {r(fr['shape']['s'][i][i], 4, True)} | "
              f"{r(fr['prog']['nearest_other']['per_head'][i], 4, True)} | {r(fr['shape']['nearest_other']['per_head'][i], 4, True)} | "
              f"{r(fr['input_gain']['per_head'][h], 4, True)} |")
        for kind in ab.KINDS:
            rr = fr[kind]
            wo = rr.get('without', {}).get('OLMo-2-0425-1B-Instruct')
            wo_s = (f"без OLMo — D {r(wo['D'], 4, True)}, p {pval(wo['p'])} (перебор {wo['n_perm']})" if wo else 'без OLMo — не считалось (OLMo нет в проверке)')
            w(f"- {KIND[kind]}: s > 0 у {rr['n_pos']} голов из {rr['k']}; своя первая в столбце — у {rr['own_first']}; своя лучше любой чужой "
              f"(среднее зазора по средам) — у {rr['nearest_other']['heads_own_best']}, средний зазор {r(rr['nearest_other']['mean'], 4, True)}; {wo_s}. Описательно, не проверка.")
        ig = fr['input_gain']
        w(f"- Вклад входа: среднее {r(ig['mean'], 4, True)}, больше нуля у {ig['n_pos']} голов из {len(hk)}.")
    w('')
    # ── разбивка
    w('## 3. Разбивка D программы: форма, уровень, прочие (описательно; порядок цепочки — PREREG §4)')
    w('- «Уровень» здесь — подгонка свободного члена чужой формы к частоте ошибок головы (ERRORS № 225), а не разница в точности голов; знак на настоящих данных не предсказывался.')
    for fam, fr in F.items():
        if fr.get('empty'):
            continue
        dc = fr['decomposition']
        share = dc['others']['mean'] / dc['total']['mean'] if dc['total']['mean'] else float('nan')
        w('')
        w(f'**{FAM[fam]}**')
        w('')
        w('| голова | всё | форма | уровень | прочие |')
        w('|---|---|---|---|---|')
        for h in fr['heads_kept']:
            w(f"| {SHORT[h]} | {r(dc['total']['per_head'][h], 4, True)} | {r(dc['form']['per_head'][h], 4, True)} | "
              f"{r(dc['level']['per_head'][h], 4, True)} | {r(dc['others']['per_head'][h], 4, True)} |")
        w(f"| среднее | {r(dc['total']['mean'], 4, True)} | {r(dc['form']['mean'], 4, True)} | {r(dc['level']['mean'], 4, True)} | {r(dc['others']['mean'], 4, True)} |")
        w('')
        w(f"- Доля «прочих» в D: {r(share, 4)} (в пилоте T_X19 — {r(PILOT_OTHERS_SHARE, 4)}).")
        if fam == 'thousands' and math.isfinite(share) and share < SHARE_MIN:
            w('- **Разбивка теста разошлась с пилотом; объяснение не проверялось** (PREREG §5). Вердикт и текст C-109 от этого не меняются.')
    w('')
    # ── родство
    w('## 4. Родство (описательно; две пары, мощности нет)')
    w('')
    w('| семейство | вид | голова | родич | своя − родич | родич − чужие | своя − чужие |')
    w('|---|---|---|---|---|---|---|')
    for fam, fr in F.items():
        if fr.get('empty'):
            continue
        for kind in ab.KINDS:
            for h, x in fr['kinship'][kind]['per_head'].items():
                w(f"| {FAM[fam]} | {KIND[kind]} | {SHORT[h]} | {SHORT[x['relative']]} | {r(x['own_minus_relative'], 4, True)} | "
                  f"{r(x['relative_minus_strangers'], 4, True)} | {r(x['own_minus_strangers'], 4, True)} |")
    w('')
    # ── new5
    w('## 5. new5 (описательно, без вердикта; к вопросу примешан перенос на пятизначные a)')
    w('')
    w('| семейство | сред | k | вид | D | p | ранг |')
    w('|---|---|---|---|---|---|---|')
    for fam, fr in F.items():
        d = (fr.get('descriptive') or {}).get('new5')
        if not d or d.get('empty'):
            continue
        for kind in ab.KINDS:
            w(f"| {FAM[fam]} | {len(d['envs_kept'])} | {d['k']} | {KIND[kind]} | {r(d[kind]['D'], 4, True)} | {pval(d[kind]['p'])} | {d[kind]['rank']} из {d[kind]['n_perm']} |")
    w('')
    # ── ожидания и вес
    w('## 6. Ожидания (PREREG §6) и вес опоры (§11)')
    w('')
    w('| правило | ожидание «да» | исход | вес, бит |')
    w('|---|---|---|---|')
    for rule in ab.RULES:
        x, e = v[rule], exp[rule]
        if x['verdict'] == 'да':
            bits = e['bits_yes'] if x.get('k') == 7 else None
        elif x['verdict'] == 'нет':
            bits = e['bits_no'] if x.get('k') == 7 else None
        else:
            bits = 0.0
        w(f"| {rule} | {r(e['expect'], 4)} | {x['verdict']} | {r(bits, 2, True) if bits is not None else 'по мощности при k = 6 (PREREG §6)'} |")
    w('')
    w('- Вес — модельный: мощность из модели шума пилота, по наименьшей из четырёх моделей (PREREG §11). Опыт идёт на тех же ответах `test5`, что DISTILL-02: для C-109 это отдельная группа опор «специфичность».')
    w('')
    w('## 7. Заметки после данных (не меняют вердикт)')
    w('')
    w('*(пишутся отдельно, после вывода; каждое число — из json)*')
    w('')
    return '\n'.join(L)


if __name__ == '__main__':
    print(main(sys.argv[1:]))
