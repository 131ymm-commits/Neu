#!/usr/bin/env python3
"""TRUST-04, блок В: запуск независимой реализации (`indep/indep_trust_04.py`, без изменений) на зёрнах, которые не
совпадают с зёрнами основной реализации.

Зачем (ERRORS № 112 (е)): генераторы обеих реализаций — default_rng(seed·100 + номер руки), и номера MYOPIC (0) и
DEMES (1) совпадают. При общих зёрнах старт этих рук побитно одинаков. Здесь у независимой реализации свои зёрна:
  --pilot1205 — 1205–1209 (вторая половина пилота, к 1200–1204 агента) → indep/pilot1205/results_indep_04.json;
  --test700   — 700–719 (тест блока В, 20 зёрен)                  → indep/test700/results_indep_04.json.
Формат вывода — как у indep_trust_04.mode_runs; в meta дописывается wrapper (путь и sha256 этого файла).
Запуск из папки опыта: python3 indep_runner.py --test700
"""
import hashlib
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, 'indep'))
import indep_trust_04 as I  # noqa: E402

MODES = {'pilot1205': list(range(1205, 1210)), 'test700': list(range(700, 720))}

# генераторы независимой реализации не пересекаются с генераторами основной (seed·100 + поток 0…30)
_main = {s * 100 + k for s in list(range(600, 620)) + list(range(1100, 1110)) + [1150, 1151] for k in range(31)}
_ind = {s * 100 + k for ss in MODES.values() for s in ss for k in I.ARM_ID.values()}
assert not (_main & _ind), 'генераторы реализаций пересекаются'


def sha256(path):
    return hashlib.sha256(open(path, 'rb').read()).hexdigest()


if __name__ == '__main__':
    modes = [m for m in MODES if f'--{m}' in sys.argv]
    assert len(modes) == 1, f'нужен ровно один режим: {list(MODES)}'
    mode = modes[0]
    I.SEEDS = {mode: MODES[mode]}
    I.mode_runs(mode, 'sd')
    path = os.path.join(HERE, 'indep', mode, 'results_indep_04.json')
    d = json.load(open(path, encoding='utf-8'))
    assert d['complete'] and d['meta']['seeds'] == MODES[mode]
    d['meta']['wrapper'] = dict(path=os.path.relpath(os.path.abspath(__file__), HERE), sha256=sha256(os.path.abspath(__file__)))
    I.write_json(path, d)
    print(f'обёртка: {mode}, зёрна {MODES[mode][0]}–{MODES[mode][-1]}; meta.wrapper дописан в {path}')
