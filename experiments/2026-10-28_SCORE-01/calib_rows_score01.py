#!/usr/bin/env python3
"""SCORE-01: ожидания §5 PREREG → строки tools/self_calibration.py (исход None) — шаг регистрации 3 (§7).
В калибровку идёт исход основной выборки: повтор — ставка с тем же ожиданием на сильно связанный исход (те же промпты и модели),
и в таблицу он не добавляется, чтобы не удваивать вес. Строки вставляются после строк TRUST-04; повторный запуск ничего не меняет.
  python3 calib_rows_score01.py [--dry]"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
sys.path.insert(0, HERE)
from analyze_score01 import PRED  # noqa: E402

p = os.path.join(ROOT, 'tools', 'self_calibration.py')
src = open(p, encoding='utf-8').read()
if "('SCORE-01'," in src:
    raise SystemExit('строки SCORE-01 уже есть — ничего не меняю')
rows = ''.join(f"    ('SCORE-01', {repr(q['id'] + ' (' + q['model'] + ') ' + q['text'] + ' (после пилота)')}, 'PREREG-SCORE-01 §5', 'вероятность', {q['expect']}, None, "
               f"'(после пилота) основная выборка; ждёт результата'),\n" for q in PRED)
lines = src.splitlines(keepends=True)
last = max(i for i, l in enumerate(lines) if l.lstrip().startswith("('TRUST-04',"))
out = ''.join(lines[:last + 1]) + rows + ''.join(lines[last + 1:])
if '--dry' in sys.argv:
    print(rows)
else:
    open(p, 'w', encoding='utf-8').write(out)
    print('добавлено строк:', len(PRED))
