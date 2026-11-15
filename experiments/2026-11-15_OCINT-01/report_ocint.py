#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Сборка REPORT-OCINT-01.md: текст — мой, числа — из gha_out/ocint_worlds/worlds.json и gha_out/ocint_real/real.json
(GitHub Actions) тем же форматированием, каким их сверяет ledger.py audit. python3 report_ocint.py [WORLDS.json REAL.json OUT.md]
Каркас написан до данных теста; разделы «Коротко», «Для главного вопроса» и «Вес опоры» дописываются после данных."""
import json
import os

import numpy as np

X = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(X))
J = lambda p: json.load(open(os.path.join(ROOT, p), encoding='utf-8'))  # noqa: E731
import sys  # noqa: E402
a = sys.argv[1:]
w, r = J(a[0] if a else 'gha_out/ocint_worlds/worlds.json'), J(a[1] if len(a) > 1 else 'gha_out/ocint_real/real.json')
an = J('gha_out/ocshift_test/analysis.json')
ct = J('gha_out/ocshift_chain/chain_old_test.json')
OUT = a[2] if len(a) > 2 else os.path.join(X, 'REPORT-OCINT-01.md')
REGHASH = 'c5bb6b32'


def n(x, d=3, sign=False):
    s = f'{abs(x):.{d}f}'.replace('.', ',')
    if x < 0 and float(s.replace(',', '.')) != 0:
        return '−' + s
    return ('+' if sign and x > 0 else '') + s


def short(m):
    return m.split()[0]


L = []
add = L.append
ru = w['rules']
c90, c98 = w['coverage']['0.9'], w['coverage']['0.98']
A_ = r['rule_A']
names = list(r['envs'])
add('# OCINT-01 «ОЦЕНЩИК-ИНТЕРВАЛ» — отчёт (15.11.2026)')
add('')
add('Главный вопрос Neu — оценщик, который не обманывается под давлением отбора; «оценка должна быть у самой оценки» (слова автора 15.10.2026). OCINT-01 проверял саму оценку: какой способ строить интервал для статистик оценщика покрывает θ(n) — ожидание статистики при нашем размере выборки.')
add(f'- **Предрегистрация — коммит {REGHASH}** (`PREREG-OCINT-01.md`; совет 62 — три линзы).')
add(f"- **Счёт** — GitHub Actions: миры с известной правдой ({w['n_worlds']} миров, по {w['n_exp']} опытов, правда — по {w['n_truth']} выборок, повторов каждого способа — {w['B']}; {n(w['seconds'], 0)} с) и {len(names)} настоящих сред (повторов с возвращением {r['B_boot']}, половинных {r['B_half']}; {n(r['seconds'], 0)} с). Перед счётом задания сверили хеши.")
add('- **Числа** — из `gha_out/ocint_worlds/worlds.json`, `gha_out/ocint_worlds/quarters_worlds.json` и `gha_out/ocint_real/real.json`; вес и прогнозы времени — `run/facts_ocint.json`. Отчёт собирает `report_ocint.py`.')
add('  - `ledger.py audit` по этим файлам и по анализу OCSHIFT-01 — «не найдено» 0; ключевые числа сверены по ключам json (`check_report_ocint.py`), все совпали.')
add('')
add('## Итог')
add(f"**Вердикты:** А — «{A_['verdict']}»; Б1 — «{ru['B1']['verdict']}»; Б2 — «{ru['B2']['verdict']}». **Выбран способ:** " + (f"«{ru['choice']['chosen']}»." if ru['choice']['chosen'] else 'годных способов нет.'))
add('')
add('**Коротко.**')
ch = ru['choice']
cm = {m: c90['one_env'][m]['S2 wc CONF']['coverage'] for m in w['methods']}
cmm = {m: c90['mean_of_worlds'][m]['S2 wc CONF']['coverage'] for m in w['methods']}
pc = [c90['one_env'][m][s]['coverage'] for m in w['methods'][3:] for s in w['stats']]
add(f"- **Дело было в центре интервала, а не в копиях задач.** Интервалы с центром в точке оценки (M4–M7) покрывают θ(n) не хуже номинала: при номинале 0,90 — от {n(min(pc), 3)} до {n(max(pc), 3)} в одной среде, у всех пяти статистик. Интервалы, построенные вокруг самих повторов (M1–M3), у S2 покрывают в одной среде {n(cm[w['methods'][0]], 3)}, {n(cm[w['methods'][1]], 3)} и {n(cm[w['methods'][2]], 3)}, а среднее по десяти мирам — {n(cmm[w['methods'][0]], 3)}, {n(cmm[w['methods'][1]], 3)} и {n(cmm[w['methods'][2]], 3)}.")
add(f"- **Правило А подтверждено:** на 13 настоящих средах повторы с возвращением и половинные выборки без копий сдвинуты одинаково (медиана отношения {n(A_['median_ratio'], 2)}, знак совпал в {A_['same_sign']} средах из {A_['n_envs']}). Сдвиг — не от копий задач, а от того, что повтор калибруется как бы на половине данных; это следствие, а сам механизм не проверялся.")
add(f"- **Для следующих предрегистраций выбран M4:** точка ± z·ст. откл. обычных повторов с возвращением. Ветвь Клоппера — Пирсона выбрала то же; M4 уже, чем M6, на {n(-ch['nearest']['diff'], 3)} ст. откл. (ст. ош. {n(ch['nearest']['se'], 3)}). Половинные выборки, которые предлагал совет 61, тоже годятся, но не нужны.")
lim0 = [e['stats']['R2 wc CONF']['limit']['share_left'] for e in r['envs'].values()]
add(f"- **Описательно:** при бесконечной калибровке остаётся от {n(min(lim0), 2)} до {n(max(lim0), 2)} самообмана от отбора (медиана {n(float(np.median(lim0)), 2)}; закон a + b·(n/m), 13 сред). Больше данных для калибровки его почти не уберёт.")
add('- **Прежние вердикты выбранным способом не меняются** (таблица устойчивости, §4): R2 и R3 OCSHIFT-01, C-086 и C-087 держатся, R1 остаётся «не решено».')
add('')
add('**Покрытие при номинале 0,90** (в одной среде / для среднего по десяти мирам):')
add('')
add('| Способ | ' + ' | '.join(short(s) for s in w['stats']) + ' | ширина, ист. ст. откл. |')
add('|---|' + '---|' * (len(w['stats']) + 1))
for m in w['methods']:
    add(f"| {m} | " + ' | '.join(f"{n(c90['one_env'][m][s]['coverage'], 3)} / {n(c90['mean_of_worlds'][m][s]['coverage'], 3)}" for s in w['stats'])
        + f" | {n(np.mean([c90['one_env'][m][s]['width_in_sd'] for s in w['stats']]), 2)} |")
add('')
add(f"- S2 — T − C у CONF на ID с кросс-подгонкой; S3 — ИОИ(CONF) − ИОИ(LR-AGREE); S1 — ИОИ(ONE-BEST) − ИОИ(CONF); S4 — ИОИ(POST-IN CONF) − ИОИ(CONF); S5 — ИОИ(POST-IN CONF) − ИОИ(ONE-BEST). Номинальная ширина интервала 0,90 — 3,29 ст. откл.; в одной среде — {w['n_worlds'] * w['n_exp']} опытов на статистику, для среднего по мирам — {w['n_exp']}.")
add('')
add('## 1. Счёт')
acc = [max(x['acc_id']) for x in w['worlds']]
acco = [max(x['acc_ood']) for x in w['worlds']]
add(f"- **Миры теста** (зерно {w['meta']}): лучшая голова на ID верна в {n(min(acc))}–{n(max(acc))} задач, вне диапазона — в {n(min(acco))}–{n(max(acco))}; голов в толпе — от {min(x['crowd_min'] for x in w['worlds'])} до {max(x['crowd_max'] for x in w['worlds'])}.")
th2 = [x['truth']['S2 wc CONF'] for x in w['worlds']]
add(f"  - Правда S2 по мирам — от {n(min(th2), 3, True)} до {n(max(th2), 3, True)}; среднее по мирам — {n(w['mean_truth']['S2 wc CONF'], 4, True)}.")
pts = {k: r['envs'][k]['stats']['R2 wc CONF']['point'] for k in names}
same_new = all(abs(pts[k] - an['R2']['by_env'][k]) < 1e-12 for k in names if k in an['R2']['by_env'])
same_old = all(abs(pts[k] - ct['R2']['by_env'][k]) < 1e-12 for k in names if k in ct['R2']['by_env'])
add(f"- **Настоящие среды:** {', '.join(names)}. Точки R2 совпали с зарегистрированным анализом OCSHIFT-01 и с цепочкой на готовых сдвигах: " + ('да' if (same_new and same_old) else 'НЕТ') + '.')
add('')
add('## 2. Правила (PREREG §5)')
add(f"- **А — «{A_['verdict']}».** Отношение сдвига повторов с возвращением к сдвигу половинных выборок для R2: медиана {n(A_['median_ratio'], 3)}; знак совпал в {A_['same_sign']} средах из {A_['n_envs']}.")
add('  - По средам: ' + '; '.join(f"{k} {n(v, 2)}" for k, v in A_['ratios'].items() if v is not None) + '.')
sh = {k: (r['envs'][k]['stats']['R2 wc CONF']['shift_boot'], r['envs'][k]['stats']['R2 wc CONF']['shift_half']) for k in names}
add('  - Сдвиги (с возвращением / половинные): ' + '; '.join(f"{k} {n(a, 4, True)} / {n(b, 4, True)}" for k, (a, b) in sh.items()) + '.')
b1 = ru['B1']
add(f"- **Б1 — «{b1['verdict']}».** Процентильный интервал среднего по мирам для S2 покрыл правду в {b1['covered']} опытах из {b1['n']} ({n(b1['coverage'], 3)}); верхняя граница — {n(b1['upper'], 3)}.")
b2 = ru['B2']
add(f"- **Б2 — «{b2['verdict']}».** Покрытие M7 в одной среде: " + '; '.join(f"{short(s)} {v['covered']} из {v['n']} ({n(v['coverage'], 3)}; нижняя граница {n(v['lower'], 3)})" for s, v in b2['by_stat'].items()) + '.')
ch = ru['choice']
add('- **Выбор способа** (основное правило, записано до пилота): ' + '; '.join(f"{short(m)} — наименьшее покрытие {n(v['min_one_env'], 3)} в одной среде и {n(v['min_mean'], 3)} для среднего, ширина {n(v['width_in_sd'], 2)}" + (' — годен' if v['eligible'] else '') for m, v in ch['candidates'].items())
    + '. Выбран — ' + (f"«{ch['chosen']}»." if ch['chosen'] else 'нет.'))
if 'chosen_cp' in ch:
    add('  - Ветвь совета 62 (границы Клоппера — Пирсона): ' + '; '.join(f"{short(m)} — нижняя в одной среде {n(v['cp_lower_one_env_min'], 3)}, верхняя для среднего {n(v['cp_upper_mean_min'], 3)}" + (' — годен' if v['eligible_cp'] else '') for m, v in ch['candidates'].items())
        + '. Выбран — ' + (f"«{ch['chosen_cp']}»" if ch['chosen_cp'] else 'нет') + f". Итог: {ch['stability']}.")
    if ch.get('nearest'):
        nr = ch['nearest']
        add(f"  - Ширина выбранного и {short(nr['other'])}: разность {n(nr['diff'], 3, True)} ст. откл. при ст. ош. {n(nr['se'], 3)} — " + ('не различимы.' if nr['indistinguishable'] else 'различимы.'))
add('')
add('## 3. Ожидания (PREREG §7)')
EXP = [('E1', 'А подтверждено', 0.85, A_['verdict'] == 'подтверждено'), ('E2', 'А опровергнуто', 0.04, A_['verdict'] == 'опровергнуто'),
       ('E3', 'Б1 подтверждено', 0.97, ru['B1']['verdict'] == 'подтверждено'), ('E4', 'Б2 подтверждено', 0.88, ru['B2']['verdict'] == 'подтверждено'),
       ('E5', 'Б2 опровергнуто', 0.02, ru['B2']['verdict'] == 'опровергнуто'), ('E6', 'выбран M6', 0.17, (ch['chosen'] or '').startswith('M6')),
       ('E7', 'выбран M7', 0.08, (ch['chosen'] or '').startswith('M7')), ('E8', 'годных способов нет', 0.52, ch['chosen'] is None)]
add('| № | ожидание | вероятность | исход |')
add('|---|---|---|---|')
for k, t, p_, o in EXP:
    add(f"| {k} | {t} | {n(p_, 2)} | {'да' if o else 'нет'} |")
add(f"- Брайер этих восьми ставок — {n(float(np.mean([(p_ - o) ** 2 for _, _, p_, o in EXP])), 3)}.")
add('- Главный промах — E8 = 0,52 («годных нет»). Счёт на пилотных повторах опирался только на 10 пилотных опытов для среднего по мирам и ничего не знал о том, что интервал с центром в несмещённой точке при верной ширине покрывает по номиналу. Выбор M4 я ставил в 0,10.')
add('')
add('## 4. Описательно (вес 0, без вердикта)')
add('**Покрытие при номинале 0,98** (одна среда / среднее по мирам):')
add('')
add('| Способ | ' + ' | '.join(short(s) for s in w['stats']) + ' |')
add('|---|' + '---|' * len(w['stats']))
for m in w['methods']:
    add(f"| {m} | " + ' | '.join(f"{n(c98['one_env'][m][s]['coverage'], 3)} / {n(c98['mean_of_worlds'][m][s]['coverage'], 3)}" for s in w['stats']) + ' |')
add('')
add('- **Сдвиг и разброс повторов** (в мирах; сдвиг — в ст. откл. своих повторов, разброс — к истинному): ' + '; '.join(
    f"{short(s)}: в среде {n(v['shift_boot_in_sd'], 2, True)} / {n(v['shift_half_in_sd'], 2, True)}, для среднего {n(v['mean_shift_boot_in_sd'], 2, True)} / {n(v['mean_shift_half_in_sd'], 2, True)}, разброс {n(v['sd_ratio_boot'], 2)} / {n(v['sd_ratio_half'], 2)}"
    for s, v in w['replicates'].items()) + ' (с возвращением / половинные).')
add('- **Правило А для других статистик** (знак совпал; медиана отношения): ' + '; '.join(f"{k} — {v['same_sign']} из {len(names)}, {n(v['median_ratio'], 2)}" for k, v in r['rule_A_other_stats'].items()) + '.')
import sys as _s  # noqa: E402
_s.path.insert(0, X)
os.environ.setdefault('OCSHIFT_IMPORT_ONLY', '1')
import ocint as O  # noqa: E402
lim = {k: r['envs'][k]['stats']['R2 wc CONF'].get('limit') or O.limit_fit(r['envs'][k]['stats']['R2 wc CONF']['curve'], r['envs'][k]['stats']['R2 wc CONF']['point']) for k in names}
shares = [v['share_left'] for v in lim.values() if v['share_left'] is not None]
add(f"- **Предел при бесконечной калибровке** (закон a + b·(n/m) по долям 1/4, 1/2, 3/4 и полной выборке; R2): доля самообмана от отбора, которая остаётся в пределе, — от {n(min(shares), 2)} до {n(max(shares), 2)}, медиана {n(float(np.median(shares)), 2)}.")
add('- **Проверка ширины на четвертях** — на 13 средах оба способа разброс не занижают (опасная сторона); у статистик с LR-AGREE завышают до двух раз. В пилоте на трёх средах (9 степеней свободы) выходило 3–6 раз — это был шум малого числа сред. В мирах картина та же (ниже), поэтому признаков кластеров задач здесь нет; прямо это не проверялось.')
add('  - Отношения (предсказанная дисперсия к разбросу между четвертями; половинные / с возвращением): ' + '; '.join(f"{k} — {n(v['ratio_half'], 2)} / {n(v['ratio_boot'], 2)}" for k, v in r['quarters'].items()) + f" (степеней свободы — {r['quarters']['R2 wc CONF']['df']}).")
qw_path = os.path.join(ROOT, 'gha_out', 'ocint_worlds', 'quarters_worlds.json')
if os.path.isfile(qw_path) and not a:
    qw = json.load(open(qw_path, encoding='utf-8'))
    add('- **Четверти в мирах** (совет 62; правда — дисперсия по независимым выборкам мира; отношение предсказанной дисперсии к истинной, половинные / с возвращением; в последнем столбце — то же, что на четвертях настоящих сред):')
    for k, byst in qw['by_world'].items():
        add(f"  - мир {k}: " + '; '.join(f"{nm} — при n {n(v['ratio_full_half'], 2)} / {n(v['ratio_full_boot'], 2)}, при n/4 {n(v['ratio_quarter_half'], 2)} / {n(v['ratio_quarter_boot'], 2)}, «как в настоящих» {n(v['ratio_as_in_real_half'], 2)}" for nm, v in byst.items()) + '.')
add('')
add('**Таблица устойчивости** (интервалы уровня 0,0025 на сторону; вердикт по каждому способу; описательно, статусы реестра не меняет):')
add('')
for grp in r['robustness']:
    add(f"- **{grp['group']}:**")
    for k, v in grp['stats'].items():
        add(f"  - {k}: точка {n(v['point'], 4, True)}; " + ', '.join(f"{short(m)} «{vv}»" for m, vv in v['verdicts'].items()) + '.')
add('')
add('## 5. Для главного вопроса (оценщик)')
add('«Оценка должна быть у самой оценки» — здесь проверена оценка нашей оценки, и она обманывалась так же, как оценщик под отбором.')
add('1. **Интервал вокруг повторов — это тоже выбор не того центра.** Повтор бутстрепа калибрует оценщик как бы на половине данных, а у статистик с отбором результат от размера калибровки зависит. Центр повторов уезжает к ожиданию при n/2, и интервал вокруг повторов покрывает не то, что мерит точка. Интервал с центром в точке и разбросом от повторов этой ошибки не делает.')
add(f"2. **BC и обратный интервал у S2 хуже процентильного** (покрытие в одной среде {n(cm[w['methods'][1]], 3)} и {n(cm[w['methods'][2]], 3)} против {n(cm[w['methods'][0]], 3)}). Они поправляют точку на сдвиг повторов, то есть целят ближе к пределу при бесконечной калибровке, а не к θ(n). Это объяснение не проверялось: покрытие предела в мирах не считалось.")
add(f"3. **Самообман от отбора в основном не шум калибровки.** По закону a + b·(n/m) в пределе остаётся около {n(float(np.median(lim0)), 1)} эффекта (описательно). Значит, его не убрать большей выборкой для калибровки; нужен оценщик, который учитывает сам отбор, — например, вторая калибровка после отбора (следующий шаг линии).")
add('4. **Для следующих правил:** интервал — M4 на уровне 0,0025; рядом — знак по средам. Прошлые вердикты не пересматриваются: таблица устойчивости показывает, что выбранный способ их не меняет.')
add('')
add('## 6. Ограничения')
add('- Миры — модель девяти голов, а не настоящие головы; перенос держится на сходстве и на двух проверках по настоящим данным (правило А, четверти).')
add('- Покрытие проверено при номиналах 0,90 и 0,98, а не на уровне правил Neu (0,0025 на сторону).')
add('- Покрытие условно на мирах; перенос на новые среды (уровень сред) не проверялся.')
add('')
add('## 7. Вес опоры (PREREG §6)')
add('| Правило | Исход | Вес, бит | Почему |')
add('|---|---|---|---|')
add(f"| А | «{A_['verdict']}» | 0 | свойство этих 13 сред; случайной ошибки отбора сред нет (совет 62) |")
add(f"| Б1 | «{ru['B1']['verdict']}» | 0 | проверка воспроизведения: исход породили OCSHIFT-01 и пилот (совет 62) |")
add(f"| Б2 | «{ru['B2']['verdict']}» | +8,46 | log₂(min(мощность 0,999, ожидание E4 = 0,88) / 0,0025); утверждение о мирах этой модели |")
add('- Выбор способа — правило решения, веса у него нет.')
add('- Вес Б2 относится к мирам этой модели (независимые задачи, без кластеров и тяжёлых хвостов). Перенос на настоящие головы опирается на правило А и на проверку ширины на четвертях; ни то ни другое не мерит покрытие напрямую.')
add('')
add('## 8. Отклонения (`DEVIATIONS.md`)')
add(f"1. Время: миры — {n(w['seconds'], 0)} с при прогнозе около 7740 с; настоящие среды — {n(r['seconds'], 0)} с при прогнозе около 3700 с. На вердикты не влияет.")
add('2. Разделы «Коротко», 5, 7 и 8 отчёта написаны после данных; числа в них — из json.')
add('3. Других отклонений нет: хеши совпали в обоих заданиях, тесты прошли, попытка одна.')
open(OUT, 'w', encoding='utf-8').write('\n'.join(L) + '\n')
print('\n'.join(L))
