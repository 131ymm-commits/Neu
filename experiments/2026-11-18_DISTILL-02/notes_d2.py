#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""DISTILL-02: заметки после данных для REPORT-DISTILL-02.md — «Коротко» (дополнение), «Для главного вопроса», «Что дальше», «После данных»
и совет. Написаны после вывода анализа теста (каркас report_d2.py закоммичен до данных, в регистрации 56eab269). Текст мой; числа
подставляются из json функциями форматирования report_d2.py — в тексте нет чисел из памяти. Производные числа пишутся в notes_derived_d2.json,
его читает ledger.py audit. Вердиктов и чтения скрипт не меняет.
  python3 notes_d2.py   (после совета 75 — с его правками «нужно»)
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
params = {fam: {h.split('/')[-1]: RP.n_params(fm) for h, fm in fs.items()} for fam, fs in A['formulas'].items()}
p_all = [v for fs in params.values() for v in fs.values()]
olmo = {fam: next(fm['eps'] for h, fm in fs.items() if 'OLMo' in h) for fam, fs in A['formulas'].items()}
box_tot = {n: e['concentration']['box']['total'] for n, e in E.items()}
assert all(v > 0 for v in box_tot.values())
crit3 = R['Р1-Л']['t_envs']['crit']
assert all(abs(R[r]['t_envs']['crit'] - crit3) < 1e-12 for r in ('Р1-Л', 'Р1Ф-Л', 'Р3-Л', 'Р4Ф-Т'))
CJ = json.load(open(os.path.join(ROOT, 'docs/council/2026-11-19_DISTILL-02-report_session75.json'), encoding='utf-8'))
votes = CJ['votes']
n_for = sum(v['vote'] == 'за' for v in votes)
assert CJ['status'] == 'принято единогласно' and n_for == len(votes) == 4 and CJ['timer'].get('over_s') == 0
perm7 = math.factorial(7)                                                          # полный перебор меток для A-на-B
pre_lines = open(os.path.join(X, 'PREREG-DISTILL-02.md'), encoding='utf-8').read().splitlines()
line_255 = [k + 1 for k, ln in enumerate(pre_lines) if 'm2_max со смещением вверх' in ln]
assert line_255 == [255], line_255
wrong_den = box_tot['T_X89_p3'] - E['T_X89_p3']['concentration']['b1']['total']   # как посчитали формалист (раунд 2) и инженер (раунд 3)
der = dict(source='notes_d2.py по analysis.json, trunc.json, det.txt, prereg_power_d2.json, стенограмме совета 75, полю seconds вывода заданий '
                  'и времени коммитов git',
           pilot_mu={r: PW['rules'][r]['mu'] for r in DEC}, m2_mean=m2_mean, prog_beats_box=prog_beats_box, m3_length=m3_l,
           share_l9=share_l9, lambda_dev_max=lam_dev, fragile_top_max=frag_top, hit=hit, auc=auc, eps=eps, features=feat, exp_m3_o=exp_o,
           trunc_totals=tr_tot, trunc_top=dict(model=tr_top['model'], env=tr_top['env'], phase=tr_top['phase'],
                                              share_at_max=tr_top['share_at_max'], n_at_max=tr_top['n_at_max']),
           extract_seconds_min=min(secs), extract_seconds_max=max(secs), extract_minutes_max=max(secs) / 60, n_answer_files=len(secs),
           analysis_seconds=A['seconds'], analysis_minutes=A['seconds'] / 60, launch_gap_min=launch_gap_min, launch_gap_h=launch_gap_min / 60,
           fwer_confirm=fw['false_confirm'], fwer_any=fw['false_any'], n_decisive=len(DEC), errors_refs=[212, 213, 214],
           lambda_sens_shifted=lam_shifted, weights_bits=weights, analysis_timeout_min=timeout_min, n_params=params, n_params_min=min(p_all),
           n_params_max=max(p_all), b1_max_offsets=30, eps_olmo=olmo, box_total=box_tot, box_total_min=min(box_tot.values()),
           box_total_max=max(box_tot.values()), crit_n3=crit3, council_status=CJ['status'], council_for=n_for, council_n=len(votes),
           council_over_s=CJ['timer'].get('over_s'), council_seconds=CJ['timer']['end'] - CJ['timer']['start'], heads_wrong_denominator=wrong_den,
           council_number=75, perm7=perm7, prereg_line_m2max=line_255[0], z_m4=RP.z_level(A),
           trunc_summary=TR['summary'], trunc_top_n_numeric=tr_top['n_numeric'],
           m2_m4={nm: [e['point']['m2'] - RP.z_level(A) * e['sd']['m2'], e['point']['m2'] + RP.z_level(A) * e['sd']['m2']] for nm, e in E.items()})
json.dump(der, open(OUT_DER, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)

pb = prog_beats_box
r1t, r1ft = R['Р1-Т'], R['Р1Ф-Т']
short = [
    "**Что показано (совет 75, «нужно» 1).** Ошибки голов на «тысячах» частично описываются формулой потери переноса (≤ 3 признака входа) "
    "поверх таблицы частот «прочих» смещений головы с долей ε. Программа лучше B1 по лог-вероятности ответа — Р1-Т "
    f"{f(r1t['delta'])} нат на ответ, M4 {ci(r1t)}, — и лучше Φ-базы (Р1Ф-Т {f(r1ft['delta'])}, M4 {ci(r1ft)}). Вклад зависимости от входа "
    "отдельно не выделен. Опора у программы шире, чем у B1: смещения потери переноса даёт формула, и сверх них — до 30 «прочих» смещений; у "
    "B1 — не больше 30 смещений всего (TOP_OFFSETS, по коду). Контроля «σ = постоянные, без входа» не было. Параметров у программы — "
    + (f"{p_all[0]} у каждой из {len(p_all)} программ" if min(p_all) == max(p_all) else f"от {min(p_all)} до {max(p_all)}")
    + " (коэффициенты формулы, ε, частоты «прочих»), у B1 — не больше 30.",
    "**Ограничения — часть того же вывода (описательно; совет 75, «нужно» 1).** (а) Вторая часть П1 не выполнена: доля неверных ответов "
    "головы, которые программа называет среди трёх самых вероятных неверных, не выше, чем у B1, ни в одном из четырёх наборов — " + '; '.join(
        f"{FP_RU[k]} {g(hit[f'{k[0]} {k[1]}'][0], 3)} / {g(hit[f'{k[0]} {k[1]}'][1], 3)}" for k in FP) + ". (б) Как оценщик «голова права» "
    "программа хуже собственного logp головы в трёх наборах из четырёх (AUC — в разделе «Для главного вопроса»). (в) На «длине» ящик лучше "
    f"программы во всех парах «голова × среда» ({pb['length test5'][0]} пар, где программа лучше, из {pb['length test5'][1]}; m2 = "
    f"{g(m2_mean['length'], 4)}, Р2-Л описательно, E8 сбылось); на «тысячах» m2 = {g(m2_mean['thousands'], 4)}, программа лучше ящика у "
    f"{pb['thousands test5'][0]} пар из {pb['thousands test5'][1]}. (г) m2 — доля объяснимого в пространстве классов переноса: ящик предсказывает "
    "тот же словарь исходов (верно, набор потерянных переносов, «прочее»); какое именно «прочее» число назовёт голова, по входу не "
    "предсказывают ни ящик, ни программа. (д) Δ у m1 и m1_phi — наты на ответ: средняя по головам разность лог-вероятностей ответа головы. "
    "(е) Условия: одна подсказка (p = 3), сложение, семь малых открытых голов.",
    f"**Часть Б при n = 3 (совет 75, «нужно» 2).** У Р1-Л, Р1Ф-Л, Р3-Л и Р4Ф-Т порог t по средам — {g(crit3, 3)}. Перенос на новые среды "
    "«длины» и на пятизначные a (new5) при n = 3 не проверяем: он не показан и не опровергнут. Метка «на новые среды не переносится» значит "
    "именно это.",
    f"**Р3-Л «больше» держится на одной среде и на «прочих» смещениях.** На L_X9 приходится {g(share_l9, 3)} суммы трёх сред; знак по "
    "средам разный: " + ', '.join(f"{short_env(n)} {f(v)}" for n, v in m3_l.items()) + ". Хрупкость m3 по средам не измерялась (в таблице "
    "правил — «—»). По чтению PREREG §5, записанному до данных, вывод — «грубость нуля K или общие редкие ошибки», а не «согласие голов "
    f"сверх программы»; вердикт это не меняет. «Длина»: m3_o {f(D['length m3_o']['delta'])} M4 {ci(D['length m3_o'])}, m3_c "
    f"{f(D['length m3_c']['delta'])} M4 {ci(D['length m3_c'])} — накрывает 0.",
    "**Все семь решающих правил — в сторону гипотезы; ожидания E1–E8 сбылись (E9 тривиальное — тоже).** Δ теста против μ пилота 3 (модель "
    "«новая среда», PREREG §6): " + '; '.join(f"{r} {f(R[r]['delta'])} / {f(PW['rules'][r]['mu'])}" for r in DEC) + ". Хрупких правил нет: "
    f"наибольший вклад одной задачи — {g(frag_top, 4)} суммы. При λ = 0, 1e-4 и 1e-2 Δ решающих правил отходит от основной не больше чем на "
    f"{g(lam_dev, 4)}.",
]
main_q = [
    "**Главный итог для оценщика (описательно): прозрачная программа как оценщик «голова права» уступает собственной уверенности головы.** "
    "AUC P(верно) программы против logp головы: " + '; '.join(
        f"{FP_RU[k]} {g(auc[f'{k[0]} {k[1]}'][0], 3)} / {g(auc[f'{k[0]} {k[1]}'][1], 3)}" for k in FP) + ". На L_X9999 — наоборот, но это "
    "одна среда. Обманывается ли оценщик-программа под отбором (ИОИ), опыт не мерил: отбора не было.",
    "**Программа как нуль для совпадения (вопрос OCDIV-04, описательно).** Для смещений «потеря переноса» наблюдённое совпадение не выше, чем "
    f"дают программы, независимые при данном входе: m3_c «тысячи» {f(D['thousands m3_c']['delta'])} M4 {ci(D['thousands m3_c'])}, «длина» "
    f"{f(D['length m3_c']['delta'])} M4 {ci(D['length m3_c'])}. «Прочие» смещения совпадают в {g(exp_o['thousands'], 1)} раза чаще, чем "
    f"дают программы, на «тысячах» и в {g(exp_o['length'], 1)} раза — на «длине» (e^m3_o). Годный нуль совпадения должен описывать «прочие» "
    "ошибки точнее, чем частоты смещений головы с равномерным остатком. Почему головы совпадают в «прочих», не проверялось.",
    "**К словам автора «ЛЛМ нужно додестелировать до простой математики».** На сложении у семи малых открытых голов потеря переноса частично "
    "описывается формулой из ≤ 3 признаков входа; формула держится на свежих задачах и, в среднем трёх сред, на пятизначных a (Р4Ф-Т). "
    f"Доля «прочих» ошибок, которых формула не называет, — от {g(eps['thousands'][0], 3)} до {g(eps['thousands'][1], 3)} у голов на «тысячах» "
    f"и от {g(eps['length'][0], 3)} до {g(eps['length'][1], 3)} на «длине». У OLMo-2 она {g(olmo['thousands'], 3)} и {g(olmo['length'], 3)}: у этой "
    "головы формула описывает меньшинство ошибок. Как голова считает внутри, опыт не проверял: программа описывает поведение, а не механизм.",
]
nxt = [
    "**Реестр:** C-109 — «подтверждено», не «установлено». Ограничения (а)–(е) из «Коротко» — в самой формулировке записи. Вес — верхняя "
    "оценка, в journal/support_bits.json не вносится (PREREG §11). «Установлено» — только после контроля A-на-B.",
    "**Очередь (слово автора «делай все по очереди»):** следующий — LINUX-02, затем ЯДРО-UML и МУТАНТЫ-ДО-ПРОГОНА. Совет 75 предлагает сразу "
    "после LINUX-02 PREREG контроля на неспецифичность A-на-B с пилотом на T_X19.",
    "**Устройство A-на-B (совет 75, инженер и формалист):** матрица 7 × 7 на уже собранных ответах, на процессоре GHA, без API; единица — "
    f"голова: своя программа минус среднее чужих. Нуль — перестановка меток, полный перебор 7! = {perm7}, p точное; мощность — на заглушке с "
    "заложенным +δ до прогона. Правило «чужая — любая из шести» и способ сводки — в PREREG до просмотра матрицы. В том же анализе "
    "описательно — контроль «B1-расщеплённый» (σ заменить постоянными без входа): он отделит вклад входа от ширины опоры.",
    "**Решение за автором:** только A-на-B переводит C-109 в «установлено». Линию DISTILL автор выбрал сам, поэтому можно поставить A-на-B раньше "
    "LINUX-02.",
    "**Ворота 2 с LINUX-02:** у каждого направленного слова в PREREG («смещена вверх / вниз», «консервативен», «занижена», «верхняя оценка») — "
    "вывод одной строкой по коду или тест на заглушке с известным знаком (ERRORS № 213, совет 75).",
    "**В опись (пост-хок, описательно; мощности нет — родственных семейств два):** градиент родства — своя программа, программа родича "
    "(Qwen 0,5B / 1,5B, SmolLM 360M / 1,7B), чужая; m3_o внутри семейства и между семействами; почти полное разделение классов у Qwen 0,5B "
    "на «тысячах».",
]
notes = [
    "**Ошибка в PREREG (ERRORS № 213):** §4, §5 и §8 п. 2 называют m2_max смещённой вверх. По коду (`measures_w`) знаменатель m2_max — Σ "
    "max(ящик, программа) − B1 — не меньше знаменателя m2, поэтому m2_max ≤ m2: смещение вниз. Так во всех 15 средах; равенство — где ящик "
    "лучше программы у всех голов. На вердикты не влияет: m2_max описательная. Текст PREREG не меняется (регистрация — доказательство); "
    "поправка — в DEVIATIONS.md.",
    "**Направленные слова (совет 75, «нужно» 3).** «m2_max смещена» — выведено выше (№ 213). «Мощность скорее занижена» (PREREG §6) — "
    "направление не проверялось. «Вес — верхняя оценка» (§11) — верхняя, только если настоящий уровень M4 для среднего сред не ниже "
    "номинального; это не проверено.",
    f"**Знаменатель m2 (совет 75, «нужно» 5):** ящик − B1 по средам — от {f(min(box_tot.values()))} до {f(max(box_tot.values()))} нат на ответ, "
    "больше нуля во всех 15 (проверка в `check_report_d2.py`). Порога пометы «знаменатель мал» нет; у m2 рядом печатается её интервал "
    "M4 при 0,0025 (вариант инженера, совет 75). Ст. откл. самого знаменателя в analysis.json нет.",
    f"**Прибор (`trunc_check.py`):** из {tr_tot['n_numeric']} числовых ответов на пределе длины — {tr_tot['n_at_max']}, с лишними токенами — "
    f"{tr_tot['n_extra_tokens']}; наибольшая доля на пределе — {g(tr_top['share_at_max'], 4)} ({tr_top['model'].split('/')[-1]}, "
    f"{short_env(tr_top['env'])}, {tr_top['phase']}).",
    "**Формулы (описательно):** на «длине» у всех семи голов в формуле есть «протянут» (prop) со знаком «−» — по формуле протянутый перенос "
    "теряется реже порождённого. На «тысячах» «старший перенос» (top) входит у " + f"{sum(feat['thousands'].get('top', [0, 0]))} голов из 7, "
    f"Φ — у {sum(feat['thousands'].get('phi', [0, 0]))}. У Qwen 0,5B на «тысячах» коэффициенты около 20 по модулю — похоже на почти полное "
    "разделение классов на построении; не проверялось. Чтение формулы — не механизм головы.",
    "**new5 (описательно):** m3_c по средам (в скобках — ст. откл. повторов): " + ', '.join(
        f"{short_env(n)} {f(E[n]['point']['m3_c'])} ({g(E[n]['sd']['m3_c'])})" for n in envs_of('thousands', 'new5'))
    + ". На T_X109 и T_X169 головы совпадают в «потере переноса» реже, чем дают их программы; на T_X139 — около нуля. Объяснение не "
    "проверялось.",
    f"**Детерминизм и порядок счёта:** повтор анализа (2 среды, B = 200, дважды) — {DET.split(': ', 1)[1]}. Каждое из 108 заданий и анализ — "
    f"один прогон, повторов не было, отступлений от §12 нет. Задания извлечения шли от {g(min(secs), 1)} до {g(max(secs), 1)} с (наибольшее — "
    f"{g(max(secs) / 60, 1)} мин), анализ — {g(A['seconds'], 1)} с ({g(A['seconds'] / 60, 1)} мин) при пределе {timeout_min} мин. Анализ запущен "
    f"через {g(launch_gap_min / 60, 1)} ч после последнего вывода: напоминание не дошло, процесс сессии перезапускался (ERRORS № 212). На числа "
    "это не влияет.",
    f"**Общий ложный уровень серии:** решающих правил {len(DEC)}; ложный вердикт «подтверждено», «больше» или «меньше» — не больше "
    f"{g(fw['false_confirm'], 4)}, с ложным «опровергнуто» — не больше {g(fw['false_any'], 4)}. Номинально: перенос M4 на 0,0025 для среднего "
    "сред не проверен.",
    "**Сверка чисел:** `check_report_d2.py` сравнивает числа правил, сред, описательного, ε и числа параметров формул и ожиданий в отчёте с "
    "analysis.json по точному "
    "ключу, проверяет целостность строк и box.total > 0 (самопроверка от обратного — `--selftest`). `ledger.py audit` — все числа отчёта против "
    "файлов данных. Для аудита из analysis.json взяты только печатаемые отчётом поля (`audit_view_d2.json`, выборка по ключам): в полном "
    "файле тысячи чисел вкладов задач делают любое совпадение случайным.",
]
council = dict(title='Совет 75 — оценка отчёта (19.11.2026)', items=[
    f"**{CJ['status'][0].upper() + CJ['status'][1:]}: {n_for} из {len(votes)} «за» после правок «нужно»;** перебора времени нет "
    f"(заседание — {CJ['timer']['end'] - CJ['timer']['start']} с). Стенограмма — `docs/council/2026-11-19_DISTILL-02-report_session75.md`.",
    "**Правки «нужно» 1–7 внесены** (код отчёта — DEVIATIONS.md): (1) «Коротко» и C-109 — «частично описываются формулой … поверх таблицы "
    "частот», ограничения (а)–(е) в самой записи; (2) часть Б при n = 3 не проверяема, Р3-Л держится на одной среде, хрупкость m3 не "
    "измерялась; (3) направленные слова выведены или помечены; (4) сводка прибора вместо оборванной строки, проверка целостности строк с "
    "самопроверкой от обратного; (5) столбец «ящик − B1» и box.total > 0 по 15 средам; (6) число параметров программы — кодом из сохранённой "
    "программы; (7) ошибки голов — в ERRORS № 214.",
    f"**Отступление от буквы «нужно» 3:** «строку {line_255[0]} PREREG поправить» исполнено поправкой в DEVIATIONS.md, ERRORS № 213 и здесь. Текст "
    "регистрации не менялся (CLAUDE.md, п. 4).",
    "**Ошибки голов (ERRORS № 214):** формалист в раунде 2 прочёл `concentration.box.total` как выигрыш над общим нулём и вывел знаменатель m2 "
    f"на T_X89 {g(wrong_den, 3)}; инженер в раунде 3 повторил то же вычитание. По коду (`LL_PARTS['box'] = ('box', 'b1')`) box.total уже равен "
    f"ящик − B1, то есть {g(box_tot['T_X89_p3'], 4)}. Оба исправили это сами: формалист — в раунде 3, инженер — в голосовании.",
    "**Несогласия:** правило пометы «знаменатель мал» — четыре варианта; взят вариант инженера (порога нет; у m2 — её "
    "интервал M4), задан до правки таблицы. Держится ли преимущество над B1 без более широкой опоры таблицы (скептик) — ответит контроль «B1-расщеплённый».",
])
json.dump(dict(short=short, main_q=main_q, next=nxt, notes=notes, council=council), open(OUT, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print('записано', OUT, OUT_DER)
