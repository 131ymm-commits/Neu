#!/usr/bin/env python3
"""TRUST-04: сверка чисел отчёта (записан после регистрации; вердиктов не меняет).
1) Каждая строка таблиц run/report_tables.md (их печатает report_tables_trust04.py из facts) должна стоять в
   REPORT-TRUST-04.md дословно — таблицы вставляются командой (assemble_report_trust04.py), не перепечаткой.
2) Каждое десятичное число прозы (вне строк таблиц) должно дословно (как строка, до знака) встречаться в источниках:
   run/report_tables.md, PREREG-TRUST-04.md, DEVIATIONS.md, журналы run/test_*.log и pilot/v2/pilot_*.log, calib_trust04.json,
   с 29.10 — run/posthoc_trust_04.md (пост-хок по проверке отчёта, не в зачёт).
   Нестрогое сравнение со всеми числами json (первая версия скрипта) почти ничего не проверяло: чисел в json тысячи.
Запуск из папки опыта: python3 check_report_trust04.py"""
import json
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
rep = open(os.path.join(HERE, 'REPORT-TRUST-04.md'), encoding='utf-8').read()
tab = open(os.path.join(HERE, 'run', 'report_tables.md'), encoding='utf-8').read()
rows = [l for l in tab.splitlines() if l.startswith('|') and not set(l) <= set('|-')]
miss_rows = [l for l in rows if l not in rep]
print(f'строк таблиц {len(rows)}, не найдено в отчёте {len(miss_rows)}')
for l in miss_rows[:20]:
    print('  нет:', l[:160])


def flat(x):
    if isinstance(x, dict):
        return ' '.join(flat(v) for v in x.values())
    if isinstance(x, list):
        return ' '.join(flat(v) for v in x)
    return str(x)


src = tab
for fn in ('PREREG-TRUST-04.md', 'DEVIATIONS.md', 'run/test_A.log', 'run/test_B.log', 'run/test_indep.log', 'pilot/v2/pilot_A.log', 'pilot/v2/pilot_B.log',
           'run/posthoc_trust_04.md'):   # пост-хок (posthoc_trust04.py; добавлен 29.10 после проверки отчёта)
    p = os.path.join(HERE, fn)
    if os.path.exists(p):
        src += open(p, encoding='utf-8').read()
src += ' ' + flat(json.load(open(os.path.join(HERE, 'calib_trust04.json')))).replace('.', ',')
NUM = re.compile(r'(?<![\w.,])[−-]?\d+,\d+')
have = set(m.replace('−', '-').lstrip('-') for m in NUM.findall(src))
prose = '\n'.join(l for l in rep.splitlines() if not l.startswith('|'))
found = NUM.findall(prose)
miss = sorted(set(m for m in found if m.replace('−', '-').lstrip('-') not in have))
print(f'чисел прозы {len(found)}, не найдено в источниках {len(miss)}: {miss}')
