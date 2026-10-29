#!/usr/bin/env python3
"""TRUST-04: сборка REPORT-TRUST-04.md из report_text.md и таблиц run/report_tables.md (вставка дословно) и
блока проверки отчёта (report_check.md, если есть). Текст отчёта правится только в report_text.md.
Запуск из папки опыта: python3 assemble_report_trust04.py"""
import os
HERE = os.path.dirname(os.path.abspath(__file__))
t = open(os.path.join(HERE, 'report_text.md'), encoding='utf-8').read()
tab = open(os.path.join(HERE, 'run', 'report_tables.md'), encoding='utf-8').read().strip()
t = t.replace('<!-- ТАБЛИЦЫ -->', tab.replace('### ', '### '))
chk = os.path.join(HERE, 'report_check.md')
t = t.replace('<!-- ПРОВЕРКА -->', open(chk, encoding='utf-8').read().strip() if os.path.exists(chk) else '- Проверка отчёта — после проверки агентом.')
open(os.path.join(HERE, 'REPORT-TRUST-04.md'), 'w', encoding='utf-8').write(t)
print('собрано: REPORT-TRUST-04.md,', len(t), 'знаков')
