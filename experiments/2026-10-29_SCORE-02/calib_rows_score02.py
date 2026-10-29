#!/usr/bin/env python3
"""SCORE-02: ожидания §5 PREREG → строки tools/self_calibration.py (исход None) — шаг регистрации (§7).
В калибровку идёт исход основной выборки (как в SCORE-01: повтор — ставка на сильно связанный исход, в таблицу не добавляется).
Строки вставляются после строк SCORE-01; повторный запуск ничего не меняет. Импорт ничего не пишет: всё — в main().
  python3 calib_rows_score02.py [--dry]"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))


def main():
    sys.path.insert(0, HERE)
    from analyze_score02 import PRED
    p = os.path.join(ROOT, 'tools', 'self_calibration.py')
    src = open(p, encoding='utf-8').read()
    if "('SCORE-02'," in src:
        raise SystemExit('строки SCORE-02 уже есть — ничего не меняю')
    rows = ''.join(f"    ('SCORE-02', {repr(q['id'] + ' ' + q['text'] + ' (после пилота)')}, 'PREREG-SCORE-02 §5', 'вероятность', {q['expect']}, None, "
                   f"'(после пилота) основная выборка; ждёт результата'),\n" for q in PRED)
    lines = src.splitlines(keepends=True)
    last = max(i for i, l in enumerate(lines) if l.lstrip().startswith("('SCORE-01',"))
    out = ''.join(lines[:last + 1]) + rows + ''.join(lines[last + 1:])
    if '--dry' in sys.argv:
        print(rows)
    else:
        open(p, 'w', encoding='utf-8').write(out)
        print('добавлено строк:', len(PRED))


if __name__ == '__main__':
    main()
