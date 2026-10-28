#!/usr/bin/env python3
"""TRUST-04: происхождение пилота (вторая проверка по трём линзам, правка 7). Пилот v1 (`pilot/results_trust_04_A.json`,
`_B.json`, `_B_sig5.json`) шёл до правок второй проверки; по времени файлов и коммитов — кодом 9f99db2 (руки ×5 — кодом
27108be), но версия кода в json не записана, поэтому и нужна эта сверка. Пилот v2
(`pilot/v2/`) — нынешний код на тех же зёрнах 1100–1109. Здесь: все ячейки v1 сверяются с v2 бит в бит по всем ключам
итога v1 и по снимкам траектории (общие ключи). Новые руки (DEMES_NOWITHIN, DEMES_GPOOL) есть только в v2.
Запуск из папки опыта: python3 pilot/v2/compare_v1.py > pilot/v2/compare_v1.log"""
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
P1 = os.path.dirname(HERE)
v1, v2 = {}, {}
for name in ('results_trust_04_A.json', 'results_trust_04_B.json', 'results_trust_04_B_sig5.json'):
    for r in json.load(open(os.path.join(P1, name)))['runs']:
        assert (r['seed'], r['arm']) not in v1
        v1[(r['seed'], r['arm'])] = r
for name in ('results_trust_04_A.json', 'results_trust_04_B.json'):
    for r in json.load(open(os.path.join(HERE, name)))['runs']:
        assert (r['seed'], r['arm']) not in v2
        v2[(r['seed'], r['arm'])] = r
n_fin = n_traj = 0; bad = []
for key, r1 in sorted(v1.items()):
    r2 = v2[key]
    for k, x in r1['final'].items():
        n_fin += 1
        if r2['final'][k] != x:
            bad.append((key, 'final', k, x, r2['final'][k]))
    assert len(r1['traj']) == len(r2['traj']), key
    for t1, t2 in zip(r1['traj'], r2['traj']):
        for k, x in t1.items():
            n_traj += 1
            if t2[k] != x:
                bad.append((key, 'traj', t1['g'], k, x, t2[k]))
only_v2 = sorted({a for _, a in v2} - {a for _, a in v1})
print(f'ячеек v1: {len(v1)}, все есть в v2; сверено значений итога: {n_fin}, снимков (ключ × снимок): {n_traj}')
print(f'расхождений: {len(bad)}')
for b in bad[:20]:
    print('  ', b)
print(f'руки только в v2: {only_v2}')
print('ИТОГ:', 'пилот v1 воспроизведён нынешним кодом бит в бит' if not bad else 'ЕСТЬ РАСХОЖДЕНИЯ')
