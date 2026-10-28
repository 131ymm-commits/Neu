#!/usr/bin/env python3
"""TRUST-04: сверка чисел отчёта (записан после регистрации; вердиктов не меняет).
1) Каждая строка таблиц run/report_tables.md (их печатает report_tables_trust04.py из facts) должна стоять в
   REPORT-TRUST-04.md дословно — таблицы вставляются командой, не перепечаткой.
2) Каждое десятичное число прозы отчёта (вне строк таблиц) ищется среди чисел источников с тем же числом знаков:
   facts_trust_04.json, analysis_trust_04.json, pilot/v2/pilot_calib2.json, prereg_hashes.json, PREREG-TRUST-04.md,
   DEVIATIONS.md, run/test_*.log, support_bits_trust_04.json (если есть). Ненайденные печатаются для ручного разбора.
Запуск из папки опыта: python3 check_report_trust04.py"""
import json
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
rep = open(os.path.join(HERE, 'REPORT-TRUST-04.md'), encoding='utf-8').read()
tab = open(os.path.join(HERE, 'run', 'report_tables.md'), encoding='utf-8').read()
rows = [l for l in tab.splitlines() if l.startswith('|') and not set(l) <= set('|-') and not l.startswith('| Сводный |')
        and not l.startswith('| |') and not l.startswith('| Рука |') and not l.startswith('| Утверждение |')]
miss_rows = [l for l in rows if l not in rep]
print(f'строк таблиц {len(rows)}, не найдено в отчёте {len(miss_rows)}')
for l in miss_rows[:20]:
    print('  нет:', l[:160])

NUM = re.compile(r'(?<![\w.,])[−-]?\d+,\d+')


def nums_json(x, out):
    if isinstance(x, (int, float)) and not isinstance(x, bool):
        out.append(float(x))
    elif isinstance(x, dict):
        for v in x.values():
            nums_json(v, out)
    elif isinstance(x, list):
        for v in x:
            nums_json(v, out)


src_vals = []
for fn in ('facts_trust_04.json', 'analysis_trust_04.json', os.path.join('pilot', 'v2', 'pilot_calib2.json'), 'support_bits_trust_04.json'):
    p = os.path.join(HERE, fn)
    if os.path.exists(p):
        nums_json(json.load(open(p)), src_vals)
src_txt = ''
for fn in ('PREREG-TRUST-04.md', 'DEVIATIONS.md', os.path.join('run', 'test_A.log'), os.path.join('run', 'test_B.log'),
           os.path.join('run', 'test_indep.log'), os.path.join('run', 'report_tables.md')):
    p = os.path.join(HERE, fn)
    if os.path.exists(p):
        src_txt += open(p, encoding='utf-8').read()
txt_nums = set(m.replace('−', '-') for m in NUM.findall(src_txt))
prose = '\n'.join(l for l in rep.splitlines() if not l.startswith('|'))
unmatched = []
for m in NUM.findall(prose):
    s = m.replace('−', '-')
    d = len(s.split(',')[1])
    x = float(s.replace(',', '.'))
    if s in txt_nums or s.lstrip('-') in {t.lstrip('-') for t in txt_nums}:
        continue
    if any(abs(round(v, d) - x) < 10 ** (-d) / 2 or abs(round(abs(v), d) - abs(x)) < 10 ** (-d) / 2 for v in src_vals):
        continue
    unmatched.append(m)
print(f'чисел прозы {len(NUM.findall(prose))}, не найдено в источниках {len(unmatched)}: {sorted(set(unmatched))}')
