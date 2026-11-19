#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""DISTILL-02: заметки после данных для REPORT-DISTILL-02.md — «Коротко» (дополнение), «Для главного вопроса», «Что дальше», «После данных»
и совет. Написаны после вывода анализа теста (каркас report_d2.py закоммичен до данных, в регистрации 56eab269). Текст мой; числа
подставляются из json функциями форматирования report_d2.py — в тексте нет чисел из памяти. Производные числа пишутся в notes_derived_d2.json,
его читает ledger.py audit. Вердиктов и чтения скрипт не меняет.
  python3 notes_d2.py [--council docs/council/<стенограмма>.json]
Время заданий извлечения — только поле seconds через tools/raw_status.filtered (белый список)."""
import glob
import json
import math
import os
import subprocess
import sys

X = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(X))
sys.path.insert(0, X)
sys.path.insert(0, os.path.join(ROOT, 'tools'))
import report_d2 as RP  # noqa: E402
import raw_status  # noqa: E402

a = sys.argv[1:]
O = os.path.join(ROOT, 'gha_out/distill02_sum_test')
A = json.load(open(os.path.join(O, 'analysis.json'), encoding='utf-8'))
PW = json.load(open(os.path.join(X, 'prereg_power_d2.json'), encoding='utf-8'))
TR = json.load(open(os.path.join(O, 'trunc.json'), encoding='utf-8'))
DET = open(os.path.join(O, 'det.txt'), encoding='utf-8').read().strip()
OUT, OUT_DER = os.path.join(X, 'report_notes.json'), os.path.join(X, 'notes_derived_d2.json')
f, g, tt, ci = RP.f, RP.g, RP.tt, RP.ci
R, D, E = A['rules'], A['descr'], A['envs']
CONF = ('Р1-Т', 'Р1-Л', 'Р1Ф-Т', 'Р1Ф-Л', 'Р2-Т', 'Р4Ф-Т')
DEC = CONF + ('Р3-Л',)

# путь данных, под который написан текст
assert sorted(r for r, e in R.items() if e['active']) == sorted(DEC)
assert all(R[r]['verdict_rule'] == 'подтверждено' for r in CONF)
assert R['Р3-Л']['verdict_rule'] == 'больше' and R['Р3-Л']['mark'] == 'знак по средам разный'
assert D['length m3_c']['ci'][0] < 0 < D['length m3_c']['ci'][1] and D['length m3_o']['ci'][0] > 0
assert D['thousands m3_c']['ci'][1] < 0 and D['thousands m3_o']['ci'][0] > 0
assert len(E) == 15 and all(len(e['heads']) == 7 for e in E.values())
assert not any((e.get('fragile') or {}).get('fragile') for e in R.values())
assert DET == 'детерминизм: побайтно одинаково'


def short_env(n):
    return n.replace('_p3', '')


def envs_of(fam, ph):
    return sorted(n for n, e in E.items() if e['family'] == fam and e['phase'] == ph)


FP = (('thousands', 'test5'), ('length', 'test5'), ('thousands', 'new5'), ('length', 'new5'))
FP_RU = {('thousands', 'test5'): '«тысячи» test5', ('length', 'test5'): '«длина» test5', ('thousands', 'new5'): '«тысячи» new5',
         ('length', 'new5'): '«длина» new5 (одна среда, L_X9999)'}
prog_beats_box = {}
for fam, ph in FP:
    hs = [s for n in envs_of(fam, ph) for s in E[n]['heads_scores'].values()]
    prog_beats_box[f'{fam} {ph}'] = [sum(1 for s in hs if s['prog'] > s['box']), len(hs)]
assert all(E[n]['point']['m2_max'] <= E[n]['point']['m2'] + 1e-12 for n in E), 'текст № 213 написан под m2_max ≤ m2 во всех средах'
assert prog_beats_box['length test5'][0] == 0
m2_mean = {'thousands': R['Р2-Т']['delta'] + R['Р2-Т']['shift'], 'length': R['Р2-Л']['delta'] + R['Р2-Л']['shift']}
m3_l = {n: E[n]['point']['m3'] for n in R['Р3-Л']['names']}
share_l9 = m3_l['L_X9_p3'] / sum(m3_l.values())
lam_dev = max(abs(v - e['shift'] - e['delta']) for r, e in R.items() if r in DEC and e.get('lambda_sens') for v in e['lambda_sens'].values())
frag_top = max(p['top_share'] for e in R.values() if e.get('fragile') for p in e['fragile']['parts'].values())
hit = {f'{fam} {ph}': [RP.mean_head(A, fam, ph, 'hit_prog'), RP.mean_head(A, fam, ph, 'hit_b1')] for fam, ph in FP}
auc = {f'{fam} {ph}': [RP.mean_head(A, fam, ph, 'auc_prog'), RP.mean_head(A, fam, ph, 'auc_conf')] for fam, ph in FP}
assert all(h[0] <= h[1] + 1e-12 for h in hit.values()), 'текст написан под «программа не выше B1» во всех четырёх'
assert all(auc[k][0] < auc[k][1] for k in ('thousands test5', 'length test5', 'thousands new5')) and auc['length new5'][0] > auc['length new5'][1]
eps = {fam: [min(fm['eps'] for fm in fs.values()), max(fm['eps'] for fm in fs.values())] for fam, fs in A['formulas'].items()}
feat = {fam: {} for fam in A['formulas']}
for fam, fs in A['formulas'].items():
    for fm in fs.values():
        for w, n in zip(fm['w_round'][1:], fm['features']):
            feat[fam].setdefault(n, [0, 0])[0 if w > 0 else 1] += 1
assert feat['length'].get('prop') == [0, 7], 'текст написан под «prop со знаком − у всех семи голов на «длине»»'
exp_o = {fam: math.exp(D[f'{fam} m3_o']['delta']) for fam in ('thousands', 'length')}
summ = TR['summary']
tr_tot = {k: sum(v[k] for v in summ.values()) for k in ('n_numeric', 'n_at_max', 'n_extra_tokens')}
tr_top = max(TR['rows'], key=lambda r: r['share_at_max'])
secs = []
for p in sorted(glob.glob(os.path.join(ROOT, 'gha_out', 'distill02_test_*', 'answers_*.json'))
                + glob.glob(os.path.join(ROOT, 'gha_out', 'distill02_rep_*', 'answers_*.json'))):
    s = raw_status.filtered(json.load(open(p, encoding='utf-8'))).get('seconds')
    if s is not None:
        secs.append(s)
assert len(secs) == 108


def commit_time(rev, path=None):
    cmd = ['git', 'log', '-1', '--format=%ct', rev] + (['--', path] if path else [])
    return int(subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, check=True).stdout.strip())


last_out = max(commit_time('HEAD', d) for d in glob.glob(os.path.join(ROOT, 'gha_out', 'distill02_test_*'))
               + glob.glob(os.path.join(ROOT, 'gha_out', 'distill02_rep_*')))
launch_gap_min = (commit_time('945bbe8f') - last_out) / 60
fw = PW['fwer']['chosen']
import re  # noqa: E402
timeout_min = int(re.search(r'timeout (\d+)m', open(os.path.join(X, 'jobs', 'distill02_sum_test.sh'), encoding='utf-8').read()).group(1))
lam_shifted = {r: {k: v - e['shift'] for k, v in e['lambda_sens'].items()} for r, e in R.items() if e.get('lambda_sens')}   # как RP.lam_words
weights = {r: math.log2(PW['rules'][r]['decisive'] / A['level']) for r in DEC}                                     # как вес в RP.render
# для ledger.py audit — поля analysis.json, которые печатает отчёт (выборка по ключам, не по тексту отчёта): без вкладов задач и таблиц
# повторов, где любое четырёхзначное число находится случайно
view = dict(level=A['level'], B=A['B'], R=A['R'], lam=A['lam'], seed=A['seed'], seconds=A['seconds'],
            rules={r: dict(delta=e.get('delta'), ci=e.get('ci'), t=e.get('t_envs', {}).get('t'), crit=e.get('t_envs', {}).get('crit'),
                           signs={k: len(v) for k, v in e.get('signs', {}).items() if isinstance(v, list)},
                           top_share=[p['top_share'] for p in (e.get('fragile') or {}).get('parts', {}).values()],
                           lambda_sens=e.get('lambda_sens'), names=len(e.get('names', []))) for r, e in R.items()},
            envs={nm: dict(point=e['point'], sd=e['sd'], ood_share=e['carries']['ood_share'], heads=len(e['heads'])) for nm, e in E.items()},
            descr={k: dict(delta=e['delta'], ci=e.get('ci'), t=e.get('t_envs', {}).get('t')) for k, e in D.items()},
            formulas={fam: {h: dict(eps=fm['eps'], w_round=fm['w_round']) for h, fm in fs.items()} for fam, fs in A['formulas'].items()},
            formulas_phi={fam: {h: fm['w_round'] for h, fm in fs.items()} for fam, fs in A['formulas_phi'].items()},
            t_quantile=1 - A['level'])
json.dump(view, open(os.path.join(X, 'audit_view_d2.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
der = dict(source='notes_d2.py по analysis.json, trunc.json, det.txt, prereg_power_d2.json, полю seconds вывода заданий и времени коммитов git',
           pilot_mu={r: PW['rules'][r]['mu'] for r in DEC}, m2_mean=m2_mean, prog_beats_box=prog_beats_box, m3_length=m3_l,
           share_l9=share_l9, lambda_dev_max=lam_dev, fragile_top_max=frag_top, hit=hit, auc=auc, eps=eps, features=feat, exp_m3_o=exp_o,
           trunc_totals=tr_tot, trunc_top=dict(model=tr_top['model'], env=tr_top['env'], phase=tr_top['phase'],
                                              share_at_max=tr_top['share_at_max'], n_at_max=tr_top['n_at_max']),
           extract_seconds_min=min(secs), extract_seconds_max=max(secs), extract_minutes_max=max(secs) / 60, n_answer_files=len(secs),
           analysis_seconds=A['seconds'], analysis_minutes=A['seconds'] / 60, launch_gap_min=launch_gap_min, launch_gap_h=launch_gap_min / 60,
           fwer_confirm=fw['false_confirm'], fwer_any=fw['false_any'], n_decisive=len(DEC), errors_refs=[212, 213],
           lambda_sens_shifted=lam_shifted, weights_bits=weights, analysis_timeout_min=timeout_min)
json.dump(der, open(OUT_DER, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)

pb = prog_beats_box
short = [
    "**Все семь решающих правил — в сторону гипотезы; ожидания E1–E8 сбылись (E9 тривиальное — тоже).** Δ теста против μ пилота 3 (модель "
    "«новая среда», PREREG §6): " + '; '.join(f"{r} {f(R[r]['delta'])} / {f(PW['rules'][r]['mu'])}" for r in DEC) + ". Хрупких правил нет: "
    f"наибольший вклад одной задачи — {g(frag_top, 4)} суммы. При λ = 0, 1e-4 и 1e-2 Δ решающих правил отходит от основной не больше чем на "
    f"{g(lam_dev, 4)}.",
    "**Р3-Л «больше» держится на «прочих» смещениях.** По чтению PREREG §5, записанному до данных, вывод — «грубость нуля K или общие редкие "
    "ошибки», а не «согласие голов сверх программы»; вердикт это не меняет. «Длина»: m3_o " + f"{f(D['length m3_o']['delta'])} M4 "
    f"{ci(D['length m3_o'])}, m3_c {f(D['length m3_c']['delta'])} M4 {ci(D['length m3_c'])} — накрывает 0. Знак по средам разный: "
    + ', '.join(f"{short_env(n)} {f(v)}" for n, v in m3_l.items()) + f"; на L_X9 приходится {g(share_l9, 3)} суммы трёх сред.",
    f"**Простая программа против ящика:** на «тысячах» m2 = {g(m2_mean['thousands'], 4)} (Р2-Т), программа лучше ящика у "
    f"{pb['thousands test5'][0]} пар «голова × среда» из {pb['thousands test5'][1]}. На «длине» m2 = {g(m2_mean['length'], 4)} (Р2-Л "
    f"описательно, E8 сбылось): ящик лучше программы во всех парах ({pb['length test5'][1]} из {pb['length test5'][1]}). Ящик сверх программы видит все признаки сразу и даёт "
    "долю «прочих» по входу; что из этого даёт разрыв на «длине», не проверялось.",
    "**Вторая часть П1 (гипотеза) в данных не выполнена (описательная мера, без вердикта):** доля неверных ответов головы, которые программа "
    "называет среди трёх самых вероятных неверных, не выше, чем у B1 — " + '; '.join(
        f"{FP_RU[k]} {g(hit[f'{k[0]} {k[1]}'][0], 3)} / {g(hit[f'{k[0]} {k[1]}'][1], 3)}" for k in FP) + ". Выигрыш программы — в "
    "лог-вероятности ответа, а не в том, какие неверные числа она называет первыми; объяснение не проверялось.",
]
main_q = [
    "**Программа как оценщик «голова права» (описательно).** AUC P(верно) программы против уверенности головы (logp): " + '; '.join(
        f"{FP_RU[k]} {g(auc[f'{k[0]} {k[1]}'][0], 3)} / {g(auc[f'{k[0]} {k[1]}'][1], 3)}" for k in FP) + ". На трёх наборах собственная "
    "уверенность головы различает верные и неверные ответы лучше программы; на L_X9999 — наоборот, но это одна среда. Обманывается ли "
    "оценщик-программа под отбором (ИОИ), опыт не мерил: отбора не было.",
    "**Программа как нуль для совпадения (вопрос OCDIV-04, описательно).** Для смещений «потеря переноса» наблюдённое совпадение не выше, чем "
    f"дают программы, независимые при данном входе: m3_c «тысячи» {f(D['thousands m3_c']['delta'])} M4 {ci(D['thousands m3_c'])}, «длина» "
    f"{f(D['length m3_c']['delta'])} M4 {ci(D['length m3_c'])}. «Прочие» смещения совпадают в {g(exp_o['thousands'], 1)} раза чаще, чем "
    f"дают программы, на «тысячах» и в {g(exp_o['length'], 1)} раза — на «длине» (e^m3_o). Годный нуль совпадения должен описывать «прочие» "
    "ошибки точнее, чем частоты смещений головы с равномерным остатком. Почему головы совпадают в «прочих», не проверялось.",
    "**К словам автора «ЛЛМ нужно додестелировать до простой математики».** На сложении у семи малых открытых голов потеря переноса сводится к "
    "формуле из ≤ 3 признаков входа. Формула держится на свежих задачах и, в среднем трёх сред, на пятизначных a (Р4Ф-Т). Доля «прочих» "
    f"ошибок, которых формула не называет, — от {g(eps['thousands'][0], 3)} до {g(eps['thousands'][1], 3)} у голов на «тысячах» и от "
    f"{g(eps['length'][0], 3)} до {g(eps['length'][1], 3)} на «длине». Как голова считает внутри, опыт не проверял: программа описывает "
    "поведение, а не механизм.",
]
nxt = [
    "**Реестр:** новая запись — «подтверждено» (не «установлено»: «установлено» — после повтора с контролем на неспецифичность). Вес — "
    "верхняя оценка, в journal/support_bits.json не вносится (PREREG §11).",
    "**Контроль на неспецифичность** — программа головы A на ответах головы B (ПРОГРАММА-A-НА-B, `docs/PROPOSALS_INVENTORY.md`, совет 74). "
    "Если чужая программа объясняет ответы так же, как своя, программа описывает задачу, а не голову. Это следующий шаг линии DISTILL; ставится "
    "после очереди или по слову автора.",
    "**Очередь автора («делай все по очереди»):** следующий — LINUX-02, затем ЯДРО-UML, затем МУТАНТЫ-ДО-ПРОГОНА.",
]
notes = [
    "**Ошибка в PREREG (ERRORS № 213):** §4 и §5 называют m2_max смещённой вверх. По коду (`measures_w`) знаменатель m2_max — Σ max(ящик, "
    "программа) − B1 — не меньше знаменателя m2, поэтому m2_max ≤ m2: смещение вниз. Так во всех 15 средах; равенство — где ящик лучше "
    "программы у всех голов. На вердикты не влияет: m2_max описательная.",
    f"**Прибор (`trunc_check.py`):** из {tr_tot['n_numeric']} числовых ответов на пределе длины — {tr_tot['n_at_max']}, с лишними токенами — "
    f"{tr_tot['n_extra_tokens']}; наибольшая доля на пределе — {g(tr_top['share_at_max'], 4)} ({tr_top['model'].split('/')[-1]}, "
    f"{short_env(tr_top['env'])}, {tr_top['phase']}).",
    "**Формулы (описательно):** на «длине» у всех семи голов в формуле есть «протянут» (prop) со знаком «−» — по формуле протянутый перенос "
    "теряется реже порождённого. На «тысячах» «старший перенос» (top) входит у " + f"{sum(feat['thousands'].get('top', [0, 0]))} голов из 7, "
    f"Φ — у {sum(feat['thousands'].get('phi', [0, 0]))}. Чтение формулы — не механизм головы.",
    "**new5 (описательно):** m3_c по средам (в скобках — ст. откл. повторов): " + ', '.join(
        f"{short_env(n)} {f(E[n]['point']['m3_c'])} ({g(E[n]['sd']['m3_c'])})" for n in envs_of('thousands', 'new5'))
    + ". На T_X109 и T_X169 головы совпадают в «потере переноса» реже, чем дают их программы; на T_X139 — около нуля. Объяснение не "
    "проверялось.",
    f"**Детерминизм и порядок счёта:** повтор анализа (2 среды, B = 200, дважды) — {DET.split(': ', 1)[1]}. Каждое из 108 заданий и анализ — один прогон, повторов не было, отступлений от §12 нет. Задания "
    f"извлечения шли от {g(min(secs), 1)} до {g(max(secs), 1)} с (наибольшее — {g(max(secs) / 60, 1)} мин), анализ — {g(A['seconds'], 1)} с "
    f"({g(A['seconds'] / 60, 1)} мин) при пределе {timeout_min} мин. Анализ запущен через {g(launch_gap_min / 60, 1)} ч после последнего вывода: "
    "напоминание не дошло, процесс сессии перезапускался (ERRORS № 212). На числа это не влияет.",
    f"**Общий ложный уровень серии:** решающих правил {len(DEC)}; ложный вердикт «подтверждено», «больше» или «меньше» — не больше "
    f"{g(fw['false_confirm'], 4)}, с ложным «опровергнуто» — не больше {g(fw['false_any'], 4)}. Номинально: перенос M4 на 0,0025 для среднего "
    "сред не проверен.",
    "**Сверка чисел:** `check_report_d2.py` сравнивает числа правил, сред, описательного и ожиданий в отчёте с analysis.json по точному ключу; "
    "`ledger.py audit` — все числа отчёта против файлов данных. Для аудита из analysis.json взяты только печатаемые отчётом поля "
    "(`audit_view_d2.json`, выборка по ключам): в полном файле тысячи чисел вкладов задач делают любое совпадение случайным.",
]
council = None
if '--council' in a:
    CJ = json.load(open(os.path.join(ROOT, a[a.index('--council') + 1]), encoding='utf-8'))
    votes = CJ['votes']
    n_for = sum(v['vote'] == 'за' for v in votes)
    der.update(council_status=CJ['status'], council_for=n_for, council_n=len(votes), council_over_s=CJ['timer'].get('over_s'))
    json.dump(der, open(OUT_DER, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    council = dict(title='Совет 75 — оценка отчёта (19.11.2026)', items=[
        f"**{CJ['status'][0].upper() + CJ['status'][1:]}: {n_for} из {len(votes)} «за».** Стенограмма — "
        "`docs/council/2026-11-19_DISTILL-02-report_session75.md`."] + json.load(open(os.path.join(X, 'council75_items.json'), encoding='utf-8')))
json.dump(dict(short=short, main_q=main_q, next=nxt, notes=notes, **({'council': council} if council else {})), open(OUT, 'w', encoding='utf-8'),
          ensure_ascii=False, indent=1)
print('записано', OUT, OUT_DER)
