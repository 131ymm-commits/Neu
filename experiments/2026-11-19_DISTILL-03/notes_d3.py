#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""DISTILL-03: заметки после данных — числа из gha_out/distill03_test/test.json (ERRORS № 200). Вердикт не меняют.
Печатает раздел «7. Заметки после данных» отчёта.
  python3 notes_d3.py"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)
import report_d3 as R  # noqa: E402

t = json.load(open(os.path.join(R.OUT, 'test.json'), encoding='utf-8'))
F = t['families']
r = R.r
L = []
w = L.append
w('## 7. Заметки после данных (не меняют вердикт)')
w('')
# 1. форма относительно ближайшей чужой
no = {f: F[f]['shape']['nearest_other'] for f in F}
w('1. **Форма своя относительно среднего чужих, а у ближайшей чужой — почти та же** (чтение PREREG §5, записано заранее).')
for f in F:
    w(f"   - {R.FAM[f]}: своя форма лучше любой чужой у {no[f]['heads_own_best']} голов из {F[f]['k']}; средний зазор к лучшей чужой {r(no[f]['mean'], 4, True)}; "
      f"D формы {r(F[f]['shape']['D'], 4, True)} при D программы {r(F[f]['prog']['D'], 4, True)}.")
# 2. разбивка
w('2. **Преимущество своей программы в основном — «прочие»** (частоты не-переносных ошибок головы), как в пилоте (доля 0,7735).')
for f in F:
    dc = F[f]['decomposition']
    tot = dc['total']['mean']
    w(f"   - {R.FAM[f]}: доля «прочих» {r(dc['others']['mean'] / tot, 4)}, формы {r(dc['form']['mean'] / tot, 4)}, уровня {r(dc['level']['mean'] / tot, 4)} "
      f"(всё {r(tot, 4, True)}). Порог расхождения с пилотом (0,5) не достигнут.")
w('   - Поэтому правило «П и Ф» было нужно: без АБ-Ф-Т «установлено» досталось бы в основном таблице частот (совет 76).')
# 3. без OLMo
w('3. **Без OLMo** (описательно; перебор 720, «да» было бы только при ранге 1):')
for f in F:
    parts = []
    for kind in R.ab.KINDS:
        x = F[f][kind]['without']['OLMo-2-0425-1B-Instruct']
        parts.append(f"{R.KIND[kind]} D {r(x['D'], 4, True)}, ранг {x['rank']} из {x['n_perm']}")
    w(f"   - {R.FAM[f]}: " + '; '.join(parts) + '.')
w('   - Итог не держится на одной OLMo. Проверкой это не читать: срез выбран после пилота (совет 76, п. 6).')
# 4. вклад входа
w('4. **Вклад входа** (своя программа против своей же без входа; ответ на несогласие 3 совета 75, описательно, без интервала):')
for f in F:
    ig = F[f]['input_gain']
    w(f"   - {R.FAM[f]}: {r(ig['mean'], 4, True)} нат на ответ, больше нуля у {ig['n_pos']} голов из {F[f]['k']}.")
w('   - По чтению PREREG §5 фраза C-109 «вклад зависимости от входа отдельно не выделен» заменяется числами выше. Зависимость потери переноса от входа добавляет к той же таблице «прочих».')
# 5. родство
rows = [(f, kind, h, x) for f in F for kind in R.ab.KINDS for h, x in F[f]['kinship'][kind]['per_head'].items()]
n_own = sum(x['own_minus_relative'] > 0 for *_, x in rows)
n_rel = sum(x['relative_minus_strangers'] > 0 for *_, x in rows)
w(f'5. **Родство** (две пары, мощности нет): своя лучше родича в {n_own} строках из {len(rows)}, родич лучше чужих — в {n_rel} из {len(rows)}. '
  'Ряд «своя > родич > чужие» описателен: программа несёт и родовую часть (совет 75, образ перекрёстной реакции), но своя лучше родича.')
# 6. new5
w('6. **new5** (описательно; к вопросу примешан перенос на пятизначные a):')
for f in F:
    d = F[f]['descriptive']['new5']
    w(f"   - {R.FAM[f]} ({len(d['envs_kept'])} ср.): программа — ранг {d['prog']['rank']} из {d['prog']['n_perm']}, форма — ранг {d['shape']['rank']} из {d['shape']['n_perm']} "
      f"(p {R.pval(d['shape']['p'])}).")
# 7. ожидания
w('7. **Калибровка:** все четыре «да» при ожиданиях 0,9334, 0,9286, 0,5486 и 0,5557 (строки E1–E4 в `tools/self_calibration.py`).')
fs = F['length']['shape']['D']
w(f"   - D формы на «длине» ({r(fs, 4, True)}) меньше D формы пилота «тысяч» (0,1300), по которому считалась мощность АБ-Ф-Л. Перенос пилота на «длину» здесь не подтвердился по величине; вердикт «да» от этого не меняется.")
# 8. пределы
w('8. **Пределы.**')
w('   - Те же ответы `test5`, что в DISTILL-02. Диагональ была известна, клетки вне её — нет (PREREG §2).')
w('   - Семь малых голов, одна подсказка (p = 3), сложение.')
w('   - Сильный нуль — взаимозаменяемость программ. «Да» по форме значит, что чужие формы при своём уровне хуже своей в среднем, а не что форма уникальна (заметка 1).')
w('   - В шкале `ledger.py` статуса «установлено» нет. Как у C-035, C-038 и C-044, он идёт пометой в записи, статус — «подтверждено», в карте проекта — в «установлено».')
# производные числа заметок и отчёта — в json, чтобы ledger.py audit видел их в данных (ERRORS № 200)
pil2 = json.load(open(os.path.join(ROOT, 'gha_out/distill03_power/pilot.json'), encoding='utf-8'))['families']['thousands']['decomposition']
der = dict(pilot_others_share=pil2['others']['mean'] / pil2['total']['mean'],
           shares={f: {p: F[f]['decomposition'][p]['mean'] / F[f]['decomposition']['total']['mean'] for p in ('others', 'form', 'level')} for f in F},
           kinship_rows=len(rows), kinship_own_gt_relative=n_own, kinship_relative_gt_strangers=n_rel)
json.dump(der, open(os.path.join(HERE, 'notes_derived_d3.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print('\n'.join(L))
