#!/usr/bin/env python3
"""SCORE-01: сверка чисел отчёта (записан после регистрации, до результатов теста; вердиктов не меняет; образец — TRUST-04).
1) Каждая строка таблиц run/report_tables.md (их печатает report_tables_score01.py из analysis_score01.json) стоит в
   REPORT-SCORE-01.md дословно: таблицы вставляются командой (assemble_report_score01.py), не перепечаткой.
2) Каждое десятичное число прозы (вне строк таблиц) встречается дословно (как строка, без знака) в источниках:
   run/report_tables.md, PREREG-SCORE-01.md, DEVIATIONS.md, run/posthoc_*.md (пост-хок, если есть), журналы run/*.log.
   Нестрогое сравнение со всеми числами json почти ничего не проверяет (урок TRUST-04), поэтому json сюда не входит.
  python3 check_report_score01.py [REPORT-SCORE-01.md]"""
import glob
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
NUM = re.compile(r'(?<![\w.,])[−-]?\d+,\d+')


def main():
    rep = open(sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, 'REPORT-SCORE-01.md'), encoding='utf-8').read()
    tab = open(os.path.join(HERE, 'run', 'report_tables.md'), encoding='utf-8').read()
    rows = [l for l in tab.splitlines() if l.startswith('|') and not set(l) <= set('|-')]
    miss_rows = [l for l in rows if l not in rep]
    print(f'строк таблиц {len(rows)}, не найдено в отчёте {len(miss_rows)}')
    for l in miss_rows[:20]:
        print('  нет:', l[:160])
    src = tab
    for fn in ['PREREG-SCORE-01.md', 'DEVIATIONS.md'] + sorted(glob.glob(os.path.join(HERE, 'run', 'posthoc_*.md'))) + \
              sorted(glob.glob(os.path.join(HERE, 'run', '*.log'))):
        p = fn if os.path.isabs(fn) else os.path.join(HERE, fn)
        if os.path.exists(p):
            src += '\n' + open(p, encoding='utf-8', errors='replace').read()
    have = set(m.replace('−', '-').lstrip('-') for m in NUM.findall(src))
    prose = '\n'.join(l for l in rep.splitlines() if not l.startswith('|'))
    found = NUM.findall(prose)
    miss = sorted(set(m for m in found if m.replace('−', '-').lstrip('-') not in have))
    print(f'чисел прозы {len(found)}, не найдено в источниках {len(miss)}: {miss}')


if __name__ == '__main__':
    main()
