# EVO-06: сверка кода до пилота (список совета, docs/council/2026-09-26_EVO-06_session1.md, §1 «Код и сверка до пилота»).
#  1. `//` и `%` при делителе 0 и отрицательных числах (evo01.ev).
#  2. truth.py против независимой переписи ИОИ на 50 случайных «прогонах».
#  3. Регрессия к EVO-01: FIXED16 на сиде EVO-01 воспроизводит hist (claimed, true) побитово.
#  4. Подмена выборки заявки (claim_seed) в SPLIT не меняет траекторию популяции (true по поколениям совпадает побитово),
#     а заявка меняется; выборки отбора и заявки идут из разных потоков.
#  5. n_labels на поколение у B0/B1/B2 = 32; сумма n_calls отличается (заявка только у элиты).
# Запуск: EVO06_GENS=20 python3 evo06_checks.py  (полная длина для п. 3 задаётся внутри).
import os, json, sys
import numpy as np
os.environ.setdefault('EVO06_GENS', '20')
import evo06 as V
from evo03 import E
from truth import ioi

out = []
def ok(name, cond, detail=''):
    out.append((name, bool(cond), detail)); print(('OK   ' if cond else 'FAIL ') + name, detail)

# 1. деление и остаток
x = np.array([-7, -1, 0, 1, 7])
ok('// при делителе 0 → 0', np.all(E.ev(('/', 'x', 0), x) == 0))
ok('% при делителе 0 → 0', np.all(E.ev(('%', 'x', 0), x) == 0))
ok('// отрицательных = floor (−7//3 = −3)', np.all(E.ev(('/', 'x', 3), x) == np.array([-3, -1, 0, 0, 2])))
ok('% отрицательных = знак делителя (−7%3 = 2)', np.all(E.ev(('%', 'x', 3), x) == np.array([2, 2, 0, 1, 1])))
ok('% при отрицательном делителе (7 % −3 = −2)', np.all(E.ev(('%', 'x', -3), x) == np.array([-1, -1, 0, -2, -2])))

# 2. truth.py против независимой переписи
rng = np.random.default_rng(0); bad = 0
for _ in range(50):
    h = [dict(claimed=float(rng.random()), true=float(rng.random())) for _ in range(151)]
    a = ioi(h)
    ign = sum(1 - z['true'] for z in h) / len(h); dec = sum(max(0.0, z['claimed'] - z['true']) for z in h) / len(h)
    bad += (abs(a['ignorance'] - ign) > 1e-12) or (abs(a['deception'] - dec) > 1e-12) or (abs(a['ioi'] - ign - dec) > 1e-12)
ok('truth.py = независимая перепись на 50 прогонах', bad == 0, f'расхождений {bad}')

# 3. регрессия к EVO-01: FIXED16, T1, сид 0 (полная длина)
V.GENS = E.GENS
ref = json.load(open('../2026-09-26_EVO-01/runs/T1_FIXED16_s0.json'))['hist']
hist = V.run('T1', 'FIXED16', 0)
same = all(a['claimed'] == b['claimed'] and a['true'] == b['true'] for a, b in zip(hist, ref)) and len(hist) == len(ref)
ok('FIXED16 T1 s0 побитово = EVO-01 (claimed, true по 151 поколению)', same)
V.GENS = int(os.environ['EVO06_GENS'])

# 4. независимость заявки от отбора
h1 = V.run('T3', 'SPLIT16+16', 996); h2 = V.run('T3', 'SPLIT16+16', 996, claim_seed=12345)
ok('SPLIT16+16: подмена выборки заявки не меняет траекторию (true побитово)', all(a['true'] == b['true'] for a, b in zip(h1, h2)))
ok('SPLIT16+16: подмена выборки заявки меняет заявку', any(a['claimed'] != b['claimed'] for a, b in zip(h1, h2)))
h3 = V.run('T3', 'SAME16', 996)
ok('SPLIT16+16 и SAME16 с общим сидом: одна начальная популяция (true в g=0 совпадает)', h1[0]['true'] == h3[0]['true'])
ok('SPLIT: claimed == claimed_fresh', all(a['claimed'] == a['claimed_fresh'] for a in h1))
ok('SAME: claimed по выборке отбора, claimed_fresh — по другой', any(a['claimed'] != a['claimed_fresh'] for a in h3))

# 5. бюджет
lab = {a: V.run('T3', a, 996)[5]['n_labels'] for a in ('FIXED32', 'SAME32', 'SPLIT16+16')}
ok('labels на поколение: FIXED32 (после g=0) 0, SAME32 32, SPLIT16+16 32', lab == {'FIXED32': 0, 'SAME32': 32, 'SPLIT16+16': 32}, str(lab))
calls = {a: V.run('T3', a, 996)[5]['n_calls'] for a in ('SAME32', 'SPLIT16+16', 'SAME16')}
ok('вызовов на поколение: SAME32 9600, SPLIT16+16 4816, SAME16 4800', calls == {'SAME32': 9600, 'SPLIT16+16': 4816, 'SAME16': 4800}, str(calls))

n_fail = sum(not c for _, c, _ in out)
print(f'итого: {len(out)} проверок, провалов {n_fail}')
sys.exit(1 if n_fail else 0)
