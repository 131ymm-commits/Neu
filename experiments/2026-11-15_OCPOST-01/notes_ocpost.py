#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""OCPOST-01: тексты разделов «Коротко», «Для главного вопроса» и «Что дальше» отчёта. Они написаны после данных теста
(DEVIATIONS п. 2). Текст мой; числа подставляются из json счёта тем же форматированием, что в report_ocpost.py, —
чтобы в тексте не было чисел из памяти. Скрипт пишет report_notes.json рядом с собой, вердиктов не меняет.
  python3 notes_ocpost.py [ANALYSIS.json TAIL.json FACTS.json OUT.json]
По умолчанию: gha_out/ocpost_test/analysis.json, gha_out/ocpost_tail_sum/tail.json, gha_out/ocpost_facts/facts_ocpost.json,
report_notes.json рядом со скриптом."""
import json
import os
import sys

X = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(X))
a = sys.argv[1:]
J = lambda p: json.load(open(p if os.path.isabs(p) else os.path.join(ROOT, p), encoding='utf-8'))  # noqa: E731
an = J(a[0] if a else 'gha_out/ocpost_test/analysis.json')
tl = J(a[1] if len(a) > 1 else 'gha_out/ocpost_tail_sum/tail.json')
fc = J(a[2] if len(a) > 2 else 'gha_out/ocpost_facts/facts_ocpost.json')
ex = json.load(open(os.path.join(X, 'expect_ocpost.json'), encoding='utf-8'))


def n(x, d=4, sign=True):                     # то же, что report_ocpost.n
    if x is None:
        return '—'
    s = f'{abs(x):.{d}f}'.replace('.', ',')
    if x < 0 and float(s.replace(',', '.')) != 0:
        return '−' + s
    return ('+' if sign and x > 0 and float(s.replace(',', '.')) != 0 else '') + s


def iv(ci, d=4):
    return f'[{n(ci[0], d)}; {n(ci[1], d)}]'


valid = an['method']['valid']
nv = len(valid)
short_name = lambda e: e.split('_')[0]  # noqa: E731
D = lambda k: an[f'descr_{k}']  # noqa: E731
sc = fc['sign_count']
fs = an['N']['fixed_split_descr']
het, dom = an['P2']['heterogeneity_descr'], an['P2']['dominance_descr']
p2_env = {e: an['envs'][e]['rules_env']['P2']['point'] for e in valid}
p2_pos = [short_name(e) for e in valid if p2_env[e] > 0]
p2_neg = [short_name(e) for e in valid if p2_env[e] < 0]
w = fc['weights']
power_p2 = ex['rules']['P2']['power_confirm_guard']
dec = {e: D(f'самообман {e} вне диапазона')['delta'] for e in ('CONF', 'POST-CV', 'FIXED')}
rule_stats = ('P0', 'P1', 'P2', 'P3', 'N')
max_miss = max(max(tl['stats'][s]['miss_low'], tl['stats'][s]['miss_high']) for s in rule_stats)
n_exp = tl['stats']['P0']['n']
assert all(an[k]['verdict'] == v for k, v in (('P0', 'подтверждено'), ('P1', 'подтверждено'), ('P3', 'подтверждено'), ('N', 'подтверждено')))
assert an['P2']['verdict'].startswith('не решено')

if tl['verdict'] == 'подтверждено':
    t_line = (f"**Т — «подтверждено»:** на {tl['n_worlds']} свежих мирах модели девяти голов ({n_exp} опытов на статистику) у M4 при 0,0025 "
              f"промахов на сторону не больше {max_miss} при границе правила 64. Т проверяет интервал одной среды; перенос на среднее пяти сред "
              f"не проверен (среднее по пяти мирам — описательно).")
elif tl['verdict'] == 'не решено':
    t_line = (f"**Т — «не решено»:** на {tl['n_worlds']} свежих мирах ({n_exp} опытов на статистику) наибольшее число промахов на сторону — "
              f"{max_miss}; это выше границы «подтверждено» (64) и ниже границы «опровергнуто». Вердикты P0–P3 и N остаются; ложный уровень "
              f"веса взят из Т (PREREG §10).")
else:
    t_line = (f"**Т — «опровергнуто»:** на {tl['n_worlds']} свежих мирах ({n_exp} опытов на статистику) наибольшее число промахов на сторону — "
              f"{max_miss}. Вердикты P0–P3 и N остаются, вес опоры у всех — 0 (PREREG §10).")
w_line = (f"**Вес опоры** (PREREG §10): P0 {n(w['P0']['bits'], 2, False)} бит, P1 {n(w['P1']['bits'], 2, False)} бит, "
          f"P3 {n(w['P3']['bits'], 2, False)} бит; P2 («не решено»), N и Т — 0 бит.")

short = [
    (f"**Внутри диапазона вторая калибровка после отбора сняла самообман от отбора: остаток — в полосе ±0,02, на этих пяти средах.** У CONF wc = {n(an['P0']['delta'])} "
     f"(P0 — повтор C-090 на свежих задачах с подсказкой p = 2; знак в {sc['P0']['neg']} средах из {nv}). После второй калибровки — "
     f"{n(an['P3']['delta'])}, в полосе ±0,02 (P3). Отрицательный контроль N — одна голова без отбора, закреплена по имени до данных: "
     f"{n(an['N']['delta'])}, в полосе. Но в {fs['n_same']} средах из {nv} лучшая на ID голова и есть FIXED, поэтому N не отделяет "
     f"поправку от совпадения голов."),
    (f"**Вне диапазона POST-CV лучше CONF по ИОИ на {n(abs(an['P1']['delta']), 4, False)}** (P1; знак в {sc['P1']['neg']} средах из {nv}). "
     f"По Брайеру POST-CV тоже лучше: M4 при 0,0025 {iv(an['P1']['brier_reading']['ci'])}. Но самообман вне диапазона остаётся: у POST-CV "
     f"{n(dec['POST-CV'], 4, False)}, у CONF {n(dec['CONF'], 4, False)} (описательно). У одной головы без отбора (FIXED) он тоже есть — "
     f"{n(dec['FIXED'], 4, False)}: вне диапазона самообман бывает и без отбора. Объяснение не проверялось."),
    (f"**P2 — толпа со второй калибровкой против одной лучшей головы — «не решено»;** при мощности {n(power_p2, 2, False)} это ожидаемый "
     f"исход. Среды расходятся: POST-CV хуже одной головы в {len(p2_pos)} средах ({', '.join(p2_pos)}) и лучше в {len(p2_neg)} "
     f"({', '.join(p2_neg)}); Q Кохрена {n(het['Q'], 2, False)} при {het['df']} степенях свободы. Чем больше отрыв лучшей головы на ID, "
     f"тем хуже POST-CV против неё: ранговая корреляция {n(dom['spearman'], 2, False)} (n = {dom['n']}; описательно)."),
    (f"**Описательно (вес 0).** Простой сдвиг заявок SHIFT не отличим от второй калибровки: разность ИОИ POST-CV − SHIFT "
     f"{n(D('POST-CV − SHIFT')['delta'])}, M4 при 0,005 {iv(D('POST-CV − SHIFT')['ci'])}. По Брайеру они тоже не отличимы: "
     f"M4 при 0,005 {iv(D('Брайер POST-CV − SHIFT')['ci'])}. Одна заранее названная голова FIXED лучше POST-CV по ИОИ на "
     f"{n(D('POST-CV − FIXED')['delta'], 4, False)} (M4 при 0,005 {iv(D('POST-CV − FIXED')['ci'])}). Выигрыша от формы изотонного "
     f"отображения эти данные не показали."),
    t_line,
    w_line,
]
EXPECT = (   # вероятности — таблица PREREG §6 (записаны до данных); исход — по вердиктам этого отчёта
    ('E1', 'P0 «подтверждено»', 0.95, an['P0']['verdict'] == 'подтверждено'),
    ('E2', 'P1 «подтверждено»', 0.95, an['P1']['verdict'] == 'подтверждено'),
    ('E3', 'P2 «подтверждено»', 0.18, an['P2']['verdict'] == 'подтверждено'),
    ('E4', 'P2 «опровергнуто»', 0.085, an['P2']['verdict'] == 'опровергнуто'),
    ('E5', 'P3 «подтверждено»', 0.94, an['P3']['verdict'] == 'подтверждено'),
    ('E6', 'N «подтверждено»', 0.95, an['N']['verdict'] == 'подтверждено'),
    ('E7', 'Т «подтверждено»', 0.85, tl['verdict'] == 'подтверждено'),
    ('E8', 'Брайер POST-CV − ONE-BEST: нижняя граница M4 при 0,0025 > 0', 0.72, an['P2']['brier_reading']['ci'][0] > 0),
)
expect = [f"{e} — {what}: {n(p, 3 if p < 0.1 else 2, False)} → {'сбылось' if ok else 'не сбылось'}." for e, what, p, ok in EXPECT]
expect.append(f"E8 подробно: разность Брайера POST-CV − ONE-BEST, M4 при 0,0025 — {iv(an['P2']['brier_reading']['ci'])}; по Брайеру "
              f"POST-CV против одной лучшей головы — «{an['P2']['brier_reading']['side']}». Я ждал «хуже» с вероятностью 0,72.")
main_question = [
    (f"**Оценщик под отбором обманывается внутри диапазона и на свежих средах (P0), а вторая калибровка снимает этот самообман до остатка в полосе ±0,02 (P3).** "
     f"Калибровку учили на ID, на парах вне частей кросс-подгонки. Вывод относится к пяти средам опыта: девять голов Pythia, сложение, "
     f"подсказка p = 2. C-090 теперь повторён на новых данных вместе с отрицательным контролем N. По правилу CLAUDE.md это повтор с "
     f"контролем на неспецифичность; статус «установлено» для C-090 выносится на совет 65."),
    (f"**Вне диапазона поправка, выученная на ID, честности не даёт.** Самообман POST-CV — {n(dec['POST-CV'], 4, False)}, и даже одна "
     f"голова без отбора обманывается на {n(dec['FIXED'], 4, False)}. Честная оценка вне диапазона — отдельная задача: калибровка на ID "
     f"её не решает ни у толпы, ни у одной головы (описательно)."),
    (f"**Против одной заранее названной головы толпа с отбором и второй калибровкой по этим данным не выигрывает.** P2 не решено, "
     f"FIXED лучше описательно. Простой сдвиг на wc дал то же, что изотонная калибровка. Для поправки на отбор здесь хватило знать "
     f"величину самообмана на ID (описательно)."),
]
nxt = [
    "Совет 65 — по этому отчёту. Затем реестр: C-090 получает вторую группу опор, новые записи — P1, P3 и описательные. Потом калибровка E1–E8 и карта проекта.",
    ("По слову автора 15.11.2026 следующая линия — оценщик на головах Claude через API. Правда — от кода, у трат — счётчик с остановкой, "
     "прогоны — задания gha_par. Ворота те же: гипотеза, литература, пилот, PREREG, совет."),
    ("В опись, без прогона (новые линии заморожены): поправка, которая учитывает сдвиг диапазона, — самообман вне диапазона "
     "остаётся и у POST-CV, и у FIXED."),
    "В опись, без прогона: связь P2 с отрывом лучшей головы на ID — проверить заранее записанным правилом на новых средах.",
]
out = dict(short=short, expect=expect, main_question=main_question, next=nxt,
           source='notes_ocpost.py: текст написан после данных (DEVIATIONS п. 2); числа — из analysis.json, tail.json, facts_ocpost.json')
dst = a[3] if len(a) > 3 else os.path.join(X, 'report_notes.json')
json.dump(out, open(dst, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print('записано', dst)
