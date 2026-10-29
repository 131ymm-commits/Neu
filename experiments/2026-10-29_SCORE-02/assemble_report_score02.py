#!/usr/bin/env python3
"""SCORE-02: сборка REPORT-SCORE-02.md из report_text.md (проза с метками <!-- ТАБЛИЦЫ --> и <!-- ПРОВЕРКА -->), таблиц
run/report_tables.md (вставка дословно; их печатает report_tables_score02.py из analysis_score02.json) и блока проверки отчёта
report_check.md (если есть). Текст отчёта правится только в report_text.md. Записан после регистрации, до данных теста.
  python3 assemble_report_score02.py"""
import os

HERE = os.path.dirname(os.path.abspath(__file__))


def main():
    t = open(os.path.join(HERE, 'report_text.md'), encoding='utf-8').read()
    tab = open(os.path.join(HERE, 'run', 'report_tables.md'), encoding='utf-8').read().strip()
    assert '<!-- ТАБЛИЦЫ -->' in t, 'в report_text.md нет метки таблиц'
    t = t.replace('<!-- ТАБЛИЦЫ -->', tab)
    chk = os.path.join(HERE, 'report_check.md')
    t = t.replace('<!-- ПРОВЕРКА -->', open(chk, encoding='utf-8').read().strip() if os.path.exists(chk) else '- Проверка отчёта — после проверки агентом.')
    open(os.path.join(HERE, 'REPORT-SCORE-02.md'), 'w', encoding='utf-8').write(t)
    print('собрано: REPORT-SCORE-02.md,', len(t), 'знаков')


if __name__ == '__main__':
    main()
