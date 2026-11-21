#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""DISTILL-02: каркас отчёта — написан до вывода анализа теста (проверен на выводе сухого прогона на заглушках; входит в хеши регистрации).
Все числа — из analysis.json, prereg_power_d2.json и expect_d2.json; тексты после данных — отдельным файлом notes (short, main_q, next,
notes, council), если он задан. Вердикты — из json по PREREG; у описательных правил — слова о границе M4, не вердикт (как совет 73).
  python3 report_d2.py ANALYSIS.json POWER.json EXPECT.json OUT.md [--det DET.txt] [--trunc TRUNC.json] [--notes NOTES.json] [--commits K=V ...]"""
import json
import math
import sys

MEAS_RU = {'m1': 'программа − B1 (m1)', 'm1_phi': 'программа − Φ-база (m1_phi)', 'm2': 'доля объяснимого против ящика (m2) − 0,5',
           'm3': 'ln K наблюдённое / из программ (m3)'}
RULE_TEXT = {'Р1-Т': 'программа лучше частот смещений B1, «тысячи» (8 сред test5)', 'Р1-Л': 'то же, «длина» (3 среды test5; только часть А)',
             'Р1Ф-Т': 'программа лучше Φ-базы, «тысячи»', 'Р1Ф-Л': 'программа лучше Φ-базы, «длина» (только часть А)',
             'Р2-Т': 'программа берёт больше половины объяснимого в пространстве классов переноса против одного ящика, «тысячи»',
             'Р2-Л': 'то же, «длина»',                               # «в пространстве классов переноса» — совет 75, «нужно» 1 (DEVIATIONS.md)
             'Р3-Т': 'ошибки голов совпадают иначе, чем дают их программы, «тысячи» (двусторонне)', 'Р3-Л': 'то же, «длина» (двусторонне; часть А)',
             'Р4-Т': 'на новых средах new5 (пятизначные a) программа лучше B1 (часть А)', 'Р4Ф-Т': 'на новых средах new5 программа лучше Φ-базы (часть А)'}
DECISIVE = ('подтверждено', 'опровергнуто', 'больше', 'меньше')
FAM_RU = {'thousands': '«тысячи»', 'length': '«длина»'}


def f(x, d=4):
    if x is None or x != x:
        return '—'
    return f'{x:+.{d}f}'.replace('-', '−').replace('.', ',')


def g(x, d=4):
    if x is None or x != x:
        return '—'
    return f'{x:.{d}f}'.replace('.', ',')


def tt(x, d=2):
    return g(x, d).replace('-', '−')


def ci(e, d=4):
    return f"[{f(e['ci'][0], d)}; {f(e['ci'][1], d)}]" if e and 'ci' in e else '—'


def bound_words(e):
    if not e or 'ci' not in e:
        return '—'
    lo, hi = e['ci']
    return 'нижняя граница M4 > 0' if lo > 0 else ('верхняя граница M4 < 0' if hi < 0 else 'M4 накрывает 0')


def t_words(e):
    tb = e.get('t_envs', {})
    t, c = tb.get('t'), tb.get('crit')
    if t is None or c is None or t != t:
        return 't по средам —'
    return f"t по средам по модулю {'выше' if abs(t) > c else 'ниже'} порога"


PART_B = {'Р1-Т': True, 'Р1-Л': False, 'Р1Ф-Т': True, 'Р1Ф-Л': False, 'Р2-Т': True, 'Р2-Л': False, 'Р3-Т': True, 'Р3-Л': False, 'Р4-Т': False,
          'Р4Ф-Т': False}                                          # как distill02.RULES


def label(r, e):
    """Вердикт правила; у правила без части Б (3 среды) — оговорка «только часть А: в среднем этих сред, на новые среды не переносится»
    (урок совета 73, OCDIV-04); у описательного — слова о границе M4, не вердикт."""
    if not e.get('active'):
        return f"описательно: {bound_words(e)}; {t_words(e)}"
    v = e['verdict_rule']
    if not PART_B.get(r, True) and v in DECISIVE:
        tb = e.get('t_envs', {})
        v += (f" только по части А — в среднем этих {len(e.get('names', []))} сред; на новые среды не переносится "
              f"(t по средам {tt(tb.get('t'))}, порог {g(tb.get('crit'), 3)})")
    return v


def frag_words(e):
    fr = e.get('fragile')
    if not fr:
        return '—'
    top = max(p['top_share'] for p in fr['parts'].values())
    return f"{'хрупкий' if fr['fragile'] else 'нет'} (наибольший вклад одной задачи — {g(top, 4)} суммы)"


def lam_words(e):
    s = e.get('lambda_sens')
    if not s:
        return '—'
    return ' / '.join(f(s[k] - e.get('shift', 0.0)) for k in ('0', '0.0001', '0.01') if k in s)


def outcome(A, key):
    """Исход ожидания (PREREG §6): «R:подтверждено» — вердикт правила; «R:решающий» — вердикт в любую сторону; «Р2-Л:m2<0,5» — среднее m2
    по средам «длины» test5 меньше 0,5 (Δ правила Р2-Л = среднее m2 − 0,5 < 0); «method» — все 15 сред с конечной m1."""
    if key == 'method':
        return len(A['envs']) == 15 and all(e['point']['m1'] == e['point']['m1'] for e in A['envs'].values())
    if key == 'Р2-Л:m2<0,5':
        return A['rules']['Р2-Л'].get('delta', float('nan')) < 0
    r, v = key.split(':', 1)
    if v == 'решающий':
        return A['rules'][r]['verdict_rule'] in DECISIVE
    return A['rules'][r]['verdict_rule'] == v


def n_params(fm):
    """Свободных параметров программы (совет 75, «нужно» 6): коэффициенты формулы, ε, частоты «прочих» смещений; q_rest = 1 − Σq не свободен.
    Без строк построения w = [0.0] — постоянная, не параметр; если q покрывает все «прочие» (q_rest = 0), одна частота q не свободна."""
    nw = len(fm['w']) if (fm.get('features') or fm.get('n')) else 0
    nq = len(fm['q']) - (1 if fm['q'] and abs(fm.get('q_rest', 1.0)) < 1e-12 else 0)
    return nw + 1 + nq


def z_level(A):
    """z для M4 при уровне A['level'] на сторону (2,807 при 0,0025)."""
    import statistics
    return statistics.NormalDist().inv_cdf(1 - A['level'])


def m2_m4(A, e):
    """Интервал M4 m2 среды: точка ± z · ст. откл. повторов (вариант инженера, совет 75)."""
    z, pt, sd = z_level(A), e['point']['m2'], e['sd']['m2']
    return f"[{g(pt - z * sd, 3)}; {g(pt + z * sd, 3)}]"


def mean_head(A, fam, ph, key):
    xs = [s[key] for e in A['envs'].values() if e['family'] == fam and e['phase'] == ph for s in e.get('heads_scores', {}).values()
          if s.get(key) == s.get(key) and s.get(key) is not None]
    return sum(xs) / len(xs) if xs else float('nan')


def render(A, PW, X, notes=None, commits=None, det=None, trunc=None):
    commits = commits or {}
    L = ['# DISTILL-02 «ПРОГРАММА-ГОЛОВЫ» — отчёт', '']
    L += [f"Предрегистрация — `PREREG-DISTILL-02.md`, коммит {commits.get('prereg', '⟨регистрация⟩')}; запуск — {commits.get('launch', '⟨запуск⟩')}; "
          f"анализ — {commits.get('analysis', '⟨анализ⟩')} (`gha_out/distill02_sum_test/analysis.json`). Уровень {g(A['level'])} на сторону; "
          f"B = {A['B']}, R = {A['R']}, λ = {A['lam']:g}; зерно {A['seed']}.", '']
    L += ['## Коротко', '']
    order = [r for r, e in A['rules'].items() if e.get('active')] + [r for r, e in A['rules'].items() if not e.get('active')]
    for r in order:
        e = A['rules'][r]
        tb, sg = e.get('t_envs', {}), e.get('signs', {})
        signs = f"знак по средам: > 0 — {len(sg.get('pos', []))}, < 0 — {len(sg.get('neg', []))}, накрывает 0 — {len(sg.get('zero', []))}" if sg else ''
        L.append(f"- **{r} — {label(r, e)}.** {RULE_TEXT[r]}: {f(e.get('delta'))}, M4 {ci(e)}; t по средам {tt(tb.get('t'))} при пороге "
                 f"{g(tb.get('crit'), 3)}; {signs}" + (f"; {e['mark']}" if e.get('mark') else '') + '.')
    if notes and notes.get('short'):
        L += [f'- {x}' for x in notes['short']]
    L += ['', '## Правила', '', '| Правило | мера | Δ | M4 при 0,0025 | t по средам | порог t | знак: > 0 / < 0 / накрывает 0 | хрупкость | Δ при λ = 0 / 1e-4 / 1e-2 | вердикт |',
          '|---|---|---|---|---|---|---|---|---|---|']
    for r in order:
        e = A['rules'][r]
        tb, sg = e.get('t_envs', {}), e.get('signs', {})
        L.append(f"| {r} | {MEAS_RU[e['measure']]} | {f(e.get('delta'))} | {ci(e)} | {tt(tb.get('t'))} | {g(tb.get('crit'), 3)} | "
                 f"{len(sg.get('pos', []))} / {len(sg.get('neg', []))} / {len(sg.get('zero', []))} | {frag_words(e)} | {lam_words(e)} | {label(r, e)} |")
    L += ['', 'Часть А — нижняя граница M4 среднего сред (за вычетом сдвига) > 0; часть Б — t по средам выше t(0,9975; n − 1). Δ при других λ — '
          'среднее точек сред за вычетом того же сдвига, описательно (вердикт не меняет). «Хрупкий» — одна задача даёт больше половины суммы вкладов (PREREG §4).']
    for fam in ('thousands', 'length'):
        for ph in ('test5', 'new5'):
            names = sorted(n for n, e in A['envs'].items() if e['family'] == fam and e['phase'] == ph)
            if not names:
                continue
            L += ['', f"## По средам: {FAM_RU[fam]}, {ph} (точки; в скобках — ст. откл. повторов)", '',
                  '| Среда | голов | m1 | m1_phi | m2 | m2: M4 при 0,0025 | ящик − B1 (знаменатель m2) | m2_max | m3 | m3_c | m3_o | K набл. / прогр. | F набл. / прогр. | ood | разряды переносов |',
                  '|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|']
            for n in names:
                e = A['envs'][n]
                pt, sd = e['point'], e['sd']
                L.append(f"| {n} | {len(e['heads'])} | {f(pt['m1'])} ({g(sd['m1'])}) | {f(pt['m1_phi'])} ({g(sd['m1_phi'])}) | {g(pt['m2'], 3)} ({g(sd['m2'], 3)}) | "
                         f"{m2_m4(A, e)} | {f(e['concentration']['box']['total'])} | "
                         f"{g(pt['m2_max'], 3)} | {f(pt['m3'])} ({g(sd['m3'])}) | {f(pt['m3_c'])} | {f(pt['m3_o'])} | {g(pt['K_obs'], 3)} / {g(pt['K_prog'], 3)} | "
                         f"{g(pt['F_obs'], 3)} / {g(pt['F_prog'], 3)} | {g(e['carries']['ood_share'], 3)} | {', '.join(e['carries']['carry_positions'])} |")
            L += ['', f"Ящик − B1 — среднее по головам выигрыша ящика над B1, нат на ответ (`concentration.box.total`; совет 75, «нужно» 5). "
                  f"Порога пометы «знаменатель мал» нет; у m2 рядом — её интервал M4 при 0,0025: точка ± z · ст. откл. повторов, z = "
                  f"{g(z_level(A), 3)} (вариант инженера, совет 75; DEVIATIONS.md)."]
    L += ['', '## Описательно (PREREG §5; вердикт не меняет; M4 при уровне описательного)', '', '| Семейство и мера | Среднее | M4 | t по средам |', '|---|---|---|---|']
    for k, e in A['descr'].items():
        L.append(f"| {k} | {f(e['delta'])} | {ci(e)} | {tt(e.get('t_envs', {}).get('t'))} |")
    L += ['', '| Семейство, фаза | три неверных: программа / B1 | AUC P(верно): программа / logp головы |', '|---|---|---|']
    for fam in ('thousands', 'length'):
        for ph in ('test5', 'new5'):
            if any(e['family'] == fam and e['phase'] == ph for e in A['envs'].values()):
                L.append(f"| {FAM_RU[fam]}, {ph} | {g(mean_head(A, fam, ph, 'hit_prog'), 3)} / {g(mean_head(A, fam, ph, 'hit_b1'), 3)} | "
                         f"{g(mean_head(A, fam, ph, 'auc_prog'), 3)} / {g(mean_head(A, fam, ph, 'auc_conf'), 3)} |")
    L += ['', '## Формулы голов (построение; P(потеря переноса в разряд j) = σ(…), две значащие цифры; ε — доля «прочих»)', '',
          '| Семейство | Голова | формула | ε | параметров | Φ-база |', '|---|---|---|---|---|---|']
    for fam, fs in A['formulas'].items():
        for h, fm in fs.items():
            terms = ' '.join(f"{w:+.2g}·{n}" for w, n in zip(fm['w_round'][1:], fm['features']))
            ph = A['formulas_phi'][fam][h]
            L.append(f"| {FAM_RU[fam]} | {h.split('/')[-1]} | σ({fm['w_round'][0]:+.2g} {terms}) | {g(fm['eps'], 3)} | {n_params(fm)} | "
                     f"σ({ph['w_round'][0]:+.2g} {ph['w_round'][1]:+.2g}·phi) |")
    L += ['', 'Параметров — коэффициенты формулы, ε и частоты «прочих» смещений из сохранённой программы: len(w) + 1 + len(q); q_rest = 1 − Σq не '
          'свободен (совет 75, «нужно» 6). У B1 — не больше 30 частот смещений (TOP_OFFSETS = 30, `offset_model`).']
    L += ['', '## Детерминизм и прибор', '']
    if det:
        L.append(f"- Повтор анализа (2 среды, B = 200, дважды): {det.strip()}.")
    if trunc:                                                      # сводка полей вместо обрезки json (совет 75, «нужно» 4)
        sm = trunc['summary']
        L.append('- Прибор (`trunc_check.py`), по наборам: ' + '; '.join(
            f"{k} — пар «голова × среда» {v['n_pairs']}, числовых ответов {v['n_numeric']}, на пределе длины {v['n_at_max']}, с лишними токенами "
            f"{v['n_extra_tokens']}, ответ — начало верного {v['n_prefix_of_truth']}" for k, v in sm.items()) + '.')
        top = max(trunc['rows'], key=lambda r: r['share_at_max'])
        L.append(f"- Наибольшая доля ответов на пределе длины: {g(top['share_at_max'], 4)} — {top['model'].split('/')[-1]}, {top['env']} ({top['phase']}): "
                 f"{top['n_at_max']} из {top['n_numeric']} числовых.")
    L += ['', '## Ожидания (PREREG §6)', '', '| № | Исход | Вероятность | Сбылось |', '|---|---|---|---|']
    for e in X['expectations']:
        L.append(f"| {e['id']} | {e['text']} | {g(e['p'], 4 if e['p'] < 0.01 else 3)} | {'да' if outcome(A, e['key']) else 'нет'} |")
    if notes:
        for key, title in (('main_q', 'Для главного вопроса'), ('next', 'Что дальше')):
            if notes.get(key):
                L += ['', f'## {title}', ''] + [f'- {x}' for x in notes[key]]
    L += ['', '## Вес опоры (PREREG §11)', '', '- Веса — верхняя оценка, только если настоящий уровень M4 для среднего сред не ниже номинального 0,0025; '
          'направление не проверялось (совет 75, «нужно» 3). Не для `journal/support_bits.json`: перенос M4 на 0,0025 для среднего сред не проверен.']
    for r in order:
        e = A['rules'][r]
        pw = PW['rules'][r]
        v = e['verdict_rule']
        if not e.get('active'):
            L.append(f"- {r}: описательно — 0 бит")
            continue
        pc = pw['decisive']
        w = math.log2(pc / 0.0025) if (pc and v in ('подтверждено', 'больше', 'меньше')) else (-math.log2(pc / 0.0025) if (pc and v == 'опровергнуто') else 0.0)
        small = ' — малый вес: решает Р4-Т вместо Р4Ф-Т (PREREG §5)' if r == 'Р4-Т' else ''
        L.append(f"- {r}: {v} — {g(w, 2)} бита (log₂({g(pc, 3)} / 0,0025); верхняя оценка){small}" if w else f"- {r}: {v} — 0 бит")
    if notes and notes.get('notes'):
        L += ['', '## После данных (заметки; причина — только проверенная)', ''] + [f'- {x}' for x in notes['notes']]
    L += ['', '## Чего отчёт не утверждает', '',
          '- Что программа — механизм головы: она воспроизводит распределение ответов на этих входах; как голова считает, не проверялось.',
          '- Что результат переносится на другие задачи, подсказки и головы: сложение «тысяч» и «длины», одна подсказка (p = 3), семь малых открытых голов.',
          '- Что уровень M4 точен для среднего сред: перенос M4 на 0,0025 не проверен (номинальный уровень).']
    if notes and notes.get('council'):
        L += ['', f"## {notes['council']['title']}", ''] + [f'- {x}' for x in notes['council']['items']]
    return '\n'.join(L) + '\n'


def main(a):
    A = json.load(open(a[0], encoding='utf-8'))
    PW = json.load(open(a[1], encoding='utf-8'))
    X = json.load(open(a[2], encoding='utf-8'))
    opt = lambda k: a[a.index(k) + 1] if k in a else None   # noqa: E731
    notes = json.load(open(opt('--notes'), encoding='utf-8')) if opt('--notes') else None
    det = open(opt('--det'), encoding='utf-8').read() if opt('--det') else None
    trunc = json.load(open(opt('--trunc'), encoding='utf-8')) if opt('--trunc') else None
    commits = dict(x.split('=', 1) for x in a[a.index('--commits') + 1:]) if '--commits' in a else {}
    open(a[3], 'w', encoding='utf-8').write(render(A, PW, X, notes, commits, det, trunc))
    print('записано', a[3])


if __name__ == '__main__':
    main(sys.argv[1:])
