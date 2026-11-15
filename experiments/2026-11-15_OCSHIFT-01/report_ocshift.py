#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Сборка REPORT-OCSHIFT-01.md: текст — мой, числа — из gha_out/ocshift_test/analysis.json (GitHub Actions),
run/facts_ocshift.json, gha_out/ocshift_chain/power.json тем же форматированием, каким их сверяет ledger.py audit.
  python3 report_ocshift.py [ANALYSIS.json FACTS.json OUT.md]
Каркас написан до данных теста; формулировки итога и раздела «для главного вопроса» дописываются после данных (DEVIATIONS.md)."""
import json
import os
import sys

X = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(X))
a = sys.argv[1:]
J = lambda p: json.load(open(p if os.path.isabs(p) else os.path.join(ROOT, p), encoding='utf-8'))  # noqa: E731
r = J(a[0] if a else 'gha_out/ocshift_test/analysis.json')
fa = J(a[1] if len(a) > 1 else os.path.join(X, 'run', 'facts_ocshift.json'))
pw = J('gha_out/ocshift_chain/power.json')
OUT = a[2] if len(a) > 2 else os.path.join(X, 'REPORT-OCSHIFT-01.md')
EV = ('AGREE', 'NB-AGREE', 'LR-AGREE', 'NB-IND', 'FAM-AGREE', 'CONF', 'VETO', 'MIX-LR')
V = r['method']['valid']
E = r['envs']


def n(x, d=3, sign=False):
    s = f'{abs(x):.{d}f}'.replace('.', ',')
    if x < 0 and float(s.replace(',', '.')) != 0:
        return '−' + s
    return ('+' if sign and x > 0 else '') + s


def ci(e, d=4, key='ci'):
    return f"[{n(e[key][0], d, True)}; {n(e[key][1], d, True)}]"


def reading(k):
    """PREREG §5: «не решено» при мощности < 0,05 читается как «не проверено»."""
    v = r['verdicts'][k]
    return v.replace('не решено', 'не проверено', 1) if v.startswith('не решено') and pw[k]['reading_power'] < 0.05 else v


def short(h):
    return h.replace('pythia-', '')


R1, R2, R3, R4 = r['R1'], r['R2'], r['R3'], r['R4']
D = lambda k: r[f'descr_{k}']  # noqa: E731
M, per, cnt = fa['mean'], fa['per_env'], fa['counts']
nv = fa['n_valid']
L = []
w = L.append
w('# OCSHIFT-01 «ОЦЕНЩИК-СДВИГИ» — отчёт (15.11.2026)')
w('')
w('Главный вопрос Neu — оценщик, который не обманывается под давлением отбора. OCSHIFT-01 спрашивал на десяти свежих средах (диапазоны a ∈ [X00, X99], X = 4…8, по две подсказки; те же девять голов Pythia): лучше ли одна лучшая голова, чем лучший из восьми оценщиков толпы; даёт ли сам отбор между головами самообман без сдвига; что лучше — CONF или LR-AGREE.')
w('- **Предрегистрация — коммит REGHASH** (`PREREG-OCSHIFT-01.md`; совет 60 — три линзы).')
w(f"- **Прогон** — Kaggle, Tesla T4 × 2, извлечение {n(fa.get('extraction_seconds', 0), 1)} с (`run/out/kaggle_log.json`); {fa['n_problems']['all']} задач: {fa['n_problems']['id']} ID и {fa['n_problems']['ood']} OOD в {fa['n_envs']} средах.")
w(f"  - Сырой вывод закоммичен до анализа (RAWHASH). Анализ — GitHub Actions, {n(fa['analysis_seconds'], 0)} с, {r['B']} повторов; хеши сверены в том же задании.")
w('- **Числа** — из `gha_out/ocshift_test/analysis.json`; производные — из `run/facts_ocshift.json` (`facts_ocshift.py`). Отчёт собирает `report_ocshift.py`.')
w('')
w('## Итог')
w(f"**Вердикт кода — «{r['verdict']}».** " + ('Проверки метода пройдены' if r['method']['ok'] else 'ПРОВЕРКИ МЕТОДА НЕ ПРОЙДЕНЫ')
  + f": годных сред {nv} из {fa['n_envs']}, сверка цепочки — " + ('прошла' if r['check_ok'] else 'НЕ ПРОШЛА') + '.')
w(f"- **R1 (одна голова против толпы) — «{reading('R1')}».** Среднее по средам [ИОИ(ONE-BEST) − ИОИ лучшего из восьми]: {n(R1['delta'], 4, True)}, ДИ BC 99,5 % {ci(R1)}, процентильный {ci(R1, key='ci_percentile')}.")
w(f"  - Средний ИОИ: ONE-BEST {n(M['ONE-BEST']['ioi'])}, лучший из восьми задним числом {n(M['MIN8']['ioi'])}. По точкам ONE-BEST лучше в {cnt['one_beats_min8']} средах из {nv}.")
w(f"- **R2 (самообман от отбора без сдвига) — «{reading('R2')}».** Среднее по средам [T − C у CONF на ID, кросс-подгонка]: {n(R2['delta'], 4, True)}, ДИ BC {ci(R2)}, процентильный {ci(R2, key='ci_percentile')}.")
w(f"  - Вторым способом, без бутстрепа: {n(R2['normal_descr']['mean'], 4, True)} при стандартной ошибке {n(R2['normal_descr']['se'], 4)} (описательно).")
w(f"- **R3 (CONF против LR-AGREE, слово автора) — «{reading('R3')}».** Среднее по средам [ИОИ(CONF) − ИОИ(LR-AGREE)]: {n(R3['delta'], 4, True)}, ДИ BC {ci(R3)}, процентильный {ci(R3, key='ci_percentile')}. По точкам CONF лучше в {cnt['conf_beats_lr']} средах из {nv}.")
w(f"- **R4 (различие R3 между средами) — «{reading('R4')}».** Q = {n(R4['Q'], 2)} при {R4['df']} степенях свободы; p по χ² — {R4['p_chi2']:.1e}, по бутстрепу — {R4['p_boot']:.1e}.".replace('e-0', '·10⁻').replace('e-', '·10⁻'))
w('')
w('| среда | ONE-BEST: голова | T / C / ИОИ | лучший из восьми: кто, ИОИ | LR-AGREE | CONF | оракул | голов в толпе |')
w('|---|---|---|---|---|---|---|---|')
for q in V:
    v, p = per[q], E[q]['point']
    w(f"| X = {E[q]['meta'].get('X', q)}, p = {E[q]['meta'].get('p', '')} | {short(v['one_best'])} | {n(v['T_one'])} / {n(v['C_one'])} / {n(v['ioi_one'])} | {v['best8']}, {n(v['ioi_best8'])} | "
      f"{n(p['ioi LR-AGREE'])} | {n(p['ioi CONF'])} | {n(v['oracle'])} | {fa['crowd_size'][q]} |")
w(f"| **среднее** | | {n(M['ONE-BEST']['T'])} / {n(M['ONE-BEST']['C'])} / {n(M['ONE-BEST']['ioi'])} | {n(M['MIN8']['ioi'])} | {n(M['LR-AGREE']['ioi'])} | {n(M['CONF']['ioi'])} | {n(fa['mean_oracle'])} | |")
w('')
w('## 1. Прогон')
w(f"- **Среды:** {fa['n_envs']}, годных {nv}. Голов в толпе — от {fa['crowd_size_range']['min']} до {fa['crowd_size_range']['max']} (проверка метода — только по ID).")
ex = {q: v for q, v in fa['excluded_heads'].items() if v}
w('- **Не прошли проверку метода:** ' + ('; '.join(f"{q} — {', '.join(short(h) for h in v)}" for q, v in ex.items()) if ex else 'таких голов нет') + '.')
w('- **ONE-BEST по средам:** ' + ', '.join(f"{short(h)} — {c}" for h, c in sorted(fa['one_best_heads'].items(), key=lambda t: -t[1])) + f". Лучшая на ID оказалась лучшей и вне диапазона в {cnt['one_best_is_best_ood']} средах из {nv}.")
w(f"- **Режим:** точность лучшей вне диапазона головы в среднем {n(fa['mean_best_ood_acc'])}; оракул (верна хоть одна голова) — {n(fa['mean_oracle'])}.")
c = r['check']
w(f"- **Сверка цепочки:** ответы {c['n_heads']} голов на {c['n']} задачах пилота OCREP-01 " + ('совпали' if c['answers_equal'] else 'НЕ СОВПАЛИ') + f"; наибольшее расхождение logp — {n(c['max_abs_dlogp'], 6)} (допуск {n(r['check_tol'], 3)}).")
w(f"- **Защита LR:** наибольшая доля повторов с одним классом — {n(r['lr_one_class']['max_share'], 4)}.")
w('')
w('## 2. Вердикты по PREREG (§5)')
for k, e in (('R1', R1), ('R2', R2), ('R3', R3)):
    t = e['tails']
    w(f"- **{k} — «{reading(k)}».** Δ {n(e['delta'], 4, True)}, ДИ BC {ci(e)}, процентильный {ci(e, key='ci_percentile')}; z₀ {n(e['z0'], 3, True)}.")
    w(f"  - По каждому ДИ: BC — «{e['verdict_bc']}», процентильный — «{e['verdict_percentile']}». Повторов за границами BC: {e['n_out']['bc'][0]} и {e['n_out']['bc'][1]}; процентильного: {e['n_out']['percentile'][0]} и {e['n_out']['percentile'][1]}. Половины повторов — «{t['verdict_halves'][0]}» и «{t['verdict_halves'][1]}».")
    if e['bc_note']:
        w(f"  - Метка: {e['bc_note']}. Вердикт она не меняет.")
    w(f"  - Мощность при эффекте, ужатом вдвое (по трём готовым сдвигам): {n(pw[k]['reading_power'])}.")
mt = R1['max_t']
w(f"- **R1, проверка после отбора (max-T):** наибольшее t — у {mt['best']} ({n(mt['t_max'], 2, True)}); порог {n(mt['crit'], 2)}; " + ('значимо' if mt['significant'] else 'не значимо') + '. Положительное t значит, что оценщик толпы лучше одной головы.')
w(f"- **R4:** Q = {n(R4['Q'], 2)}, степеней свободы {R4['df']}; мощность при разбросе, ужатом вдвое, — {n(pw['R4']['reading_power'])}. Неоднородность D1 по средам (описательно): Q = {n(R4['descr_R1']['Q'], 2)}.")
w('- Ложное «подтверждено» по серии из четырёх правил — не выше 0,01.')
w('')
w('## 3. Ожидания (PREREG §7)')
w('| № | ожидание | вероятность | исход |')
w('|---|---|---|---|')
txt = {'E1': 'R1 подтверждено', 'E2': 'R1 опровергнуто', 'E3': 'R2 подтверждено', 'E4': 'R3 подтверждено (CONF лучше)', 'E5': 'R3 опровергнуто (LR-AGREE лучше)',
       'E6': 'R4 подтверждено', 'E7': 'проверки метода опыта пройдены', 'E8': 'ONE-BEST — pythia-2.8b-deduped не меньше чем в 8 средах'}
for k in txt:
    w(f"| {k} | {txt[k]} | {n(fa['expectations_prereg'][k], 2)} | {'да' if fa['expectations_outcome'][k] else 'нет'} |")
w(f"- Брайер этих восьми ставок — {n(fa['brier_ocshift'], 3)}.")
w('')
w('## 4. Описательно (вес 0, без вердикта; ДИ BC 99 %)')
w(f"- Описательных сравнений с интервалом — {fa['descr_count']}, по 0,005 на сторону, без поправки; общий ложный уровень серии — до {n(fa['descr_family_level_bonferroni'], 2)} (Бонферрони, оценка).")
w('- **ONE-BEST против каждого из восьми** (среднее по средам, ИОИ; минус — ONE-BEST лучше): ' + '; '.join(f"{e} {n(D(f'ONE-BEST − {e}')['delta'], 4, True)} {ci(D(f'ONE-BEST − {e}'))}" for e in EV) + '.')
w(f"- **Брайер выбранной заявки** (ИОИ не штрафует заниженную заявку): ONE-BEST {n(M['ONE-BEST']['brier'])}, лучший из восьми {n(M['MIN8']['brier'])}; разность {n(D('Брайер ONE-BEST − MIN8')['delta'], 4, True)} {ci(D('Брайер ONE-BEST − MIN8'))}.")
w(f"- **Точность выбора:** ONE-BEST {n(M['ONE-BEST']['T'])}; LR-AGREE {n(M['LR-AGREE']['T'])} (разность {n(D('T ONE-BEST − T LR-AGREE')['delta'], 4, True)} {ci(D('T ONE-BEST − T LR-AGREE'))}); CONF {n(M['CONF']['T'])} (разность {n(D('T ONE-BEST − T CONF')['delta'], 4, True)} {ci(D('T ONE-BEST − T CONF'))}).")
sw = fa['switch']
w('- **Где выбор отходит от ответа ONE-BEST** (среднее по средам: доля задач; точность выбранного там; точность ONE-BEST там): ' + '; '.join(f"{e} — {n(sw[e]['switch'])}; {n(sw[e]['T_selected_on_switch'])}; {n(sw[e]['T_one_best_on_switch'])}" for e in ('LR-AGREE', 'CONF', 'AGREE')) + '.')
sd = fa['selection_deception']
w('- **Самообман от отбора на ID** (C − T, кросс-подгонка, только точка) и самообман вне диапазона: ' + '; '.join(f"{e} {n(sd['id_crossfit'][e], 3, True)} / {n(sd['ood'][e], 3, True)}" for e in EV) + f". У ONE-BEST на ID (отбор головы): {n(sd['one_best_id'], 3, True)}; разность с CONF {n(D('wc CONF − wc ONE-BEST')['delta'], 4, True)} {ci(D('wc CONF − wc ONE-BEST'))}.")
w(f"- **Контроль AGREE той же среды для R3** (совет 59): CONF − AGREE {n(D('CONF − AGREE')['delta'], 4, True)} {ci(D('CONF − AGREE'))}; LR-AGREE − AGREE {n(D('LR-AGREE − AGREE')['delta'], 4, True)} {ci(D('LR-AGREE − AGREE'))}; LR-AGREE − NB-IND {n(D('LR-AGREE − NB-IND')['delta'], 4, True)} {ci(D('LR-AGREE − NB-IND'))}.")
w(f"- **Вторая калибровка после отбора (POST-IN):** CONF {n(D('POST-IN CONF − CONF')['delta'], 4, True)} {ci(D('POST-IN CONF − CONF'))}; LR-AGREE {n(D('POST-IN LR-AGREE − LR-AGREE')['delta'], 4, True)} {ci(D('POST-IN LR-AGREE − LR-AGREE'))}; POST-IN CONF против ONE-BEST {n(D('POST-IN CONF − ONE-BEST')['delta'], 4, True)} {ci(D('POST-IN CONF − ONE-BEST'))}.")
w(f"- **Слияния:** FUSE-MIN против ONE-BEST — ИОИ {n(D('FUSE-MIN − ONE-BEST')['delta'], 4, True)} {ci(D('FUSE-MIN − ONE-BEST'))}, Брайер {n(D('Брайер FUSE-MIN − ONE-BEST')['delta'], 4, True)} {ci(D('Брайер FUSE-MIN − ONE-BEST'))}; ONE-BEST с заявкой min(CONF, LR-AGREE) против ONE-BEST — ИОИ {n(D('ONE-BEST+MIN − ONE-BEST')['delta'], 4, True)} {ci(D('ONE-BEST+MIN − ONE-BEST'))}, Брайер {n(D('Брайер ONE-BEST+MIN − ONE-BEST')['delta'], 4, True)} {ci(D('Брайер ONE-BEST+MIN − ONE-BEST'))}.")
t10 = fa['top10']
w('- **Верхние 10 % по заявке** (самообман, среднее по средам, точки): ' + '; '.join(f"{e} {n(t10[e], 3, True)}" for e in ('ONE-BEST', 'CONF', 'LR-AGREE', 'AGREE', 'VETO', 'MIX-LR')) + '.')
if 'without_best' in fa:
    wb = fa['without_best']
    w(f"- **Толпа без лучшей головы** (точки, среднее по {wb['n']} средам): лучшая из оставшихся — ИОИ {n(wb['ioi_one_best_of_rest'])}; лучший из восьми оценщиков — {n(wb['ioi_min8'])}; LR-AGREE — {n(wb['ioi_lr'])}.")
dom = r.get('dominance_descr')
if dom:
    w(f"- **Когда толпа не помогает** (задано до данных): ранговая корреляция по {dom['n']} средам между D1 среды и отрывом лучшей головы от второй на ID — {n(dom['spearman'], 2, True)} (ожидался минус; сред мало, без вердикта).")
dec = r.get('range_prompt_decomposition_descr', {})
if dec:
    w('- **Диапазон и подсказка** (дисперсия точек: между подсказками внутри диапазона / между средними диапазонов): ' + '; '.join(f"{k} — {n(v['var_prompt_within_range'], 5)} / {n(v['var_range_means'], 5)}" for k, v in dec.items()) + '.')
w('')
w('## 5. Для главного вопроса (оценщик)')
w('ДОПИСАТЬ ПОСЛЕ ДАННЫХ')
w('')
w('## 6. Ограничения')
w('- Одна задача (сложение), те же девять голов Pythia; свежие — диапазоны и подсказки. Вывод — про эти десять сред.')
w('- Свежие среды — другой режим, чем три готовых сдвига: головы намного слабее. Основание гипотезы и мощность взяты с готовых сдвигов.')
w('- R1 несимметричен: «подтверждено» — против лучшего задним числом (консервативно); «опровергнуто» — только с проверкой после отбора.')
w('- ИОИ не штрафует заниженную заявку; рядом — Брайер (описательно).')
w('- Бутстреп завышает самообман от отбора (R2); рядом — оценка без бутстрепа.')
w('- Литература: все источники — «сниппет»; близкий вывод о маршрутизаторах между моделями уже высказан другими.')
w('')
w('## 7. Вес опоры (PREREG §6; правило записано до данных)')
w('ДОПИСАТЬ ПОСЛЕ ДАННЫХ')
w('')
w('## 8. Отклонения')
w('ДОПИСАТЬ ПОСЛЕ ДАННЫХ')
open(OUT, 'w', encoding='utf-8').write('\n'.join(L) + '\n')
print('\n'.join(L))
