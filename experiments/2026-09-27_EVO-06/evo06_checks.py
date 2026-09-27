# EVO-06: сверка кода до пилота (список совета, docs/council/2026-09-26_EVO-06_session1.md, §1 «Код и сверка до пилота»;
# расширена по рецензиям REVIEW_gate2.md 1.1 и REVIEW_workflow.md, утечка 2–3, код 6).
#  1. `//` и `%` при делителе 0 и отрицательных числах (evo01.ev).
#  2. truth.py против независимой переписи ИОИ на 50 случайных «прогонах».
#  3. Регрессия к EVO-01: FIXED16 на сиде EVO-01 воспроизводит hist (claimed, true) побитово.
#  4. Подмена выборки заявки (claim_seed) ни в одной ветви не меняет траекторию популяции (true, elite_age по поколениям
#     побитово), а у SPLIT меняет заявку; выборки отбора и заявки идут из разных потоков.
#  5. Тождество SPLIT16+16 ≡ SAME16 по траектории при общем сиде: true, true_fresh, elite_age, claimed_fresh совпадают по всем
#     поколениям, claimed различается, claimed(SPLIT16+16) == claimed_fresh(SAME16); одна начальная популяция у всех ветвей без
#     сдвига (SAME32, FIXED32, SPLIT16+16, SAME16 — поток r общий; AA32 — другая).
#  6. Подмена скрытого набора (default_rng(10^6+seed) → другой сид) не меняет claimed, claimed_fresh, elite_age ни в одной
#     ветви, кроме ORACLE, и меняет true (истина не участвует в отборе). Подмена — обёрткой над numpy.random.default_rng,
#     evo06.py не трогается.
#  7. n_labels на поколение у B0/B1/B2 = 32; сумма n_calls отличается (заявка только у элиты).
# Запуск: EVO06_GENS=20 python3 evo06_checks.py > pilot/checks.log  (полная длина для п. 3 задаётся внутри).
import os, json, sys
import numpy as np
os.environ.setdefault('EVO06_GENS', '20')
import evo06 as V
from evo03 import E
from truth import ioi

out = []
def ok(name, cond, detail=''):
    out.append((name, bool(cond), detail)); print(('OK   ' if cond else 'FAIL ') + name, detail)

def same(h1, h2, keys):
    return len(h1) == len(h2) and all(a[k] == b[k] for a, b in zip(h1, h2) for k in keys)

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
ok('FIXED16 T1 s0 побитово = EVO-01 (claimed, true по 151 поколению)', same(hist, ref, ('claimed', 'true')))
V.GENS = int(os.environ['EVO06_GENS'])

# 4. независимость отбора от выборки заявки — во всех ветвях
ARMS = ('FIXED32', 'SAME32', 'SPLIT16+16', 'AA32', 'SAME16', 'SPLIT8+8', 'RANDEVAL', 'ORACLE')
H = {a: V.run('T3', a, 996) for a in ARMS}
for a in ARMS:
    h2 = V.run('T3', a, 996, claim_seed=12345)
    ok(f'{a}: подмена выборки заявки не меняет траекторию (true, elite_age побитово)', same(H[a], h2, ('true', 'elite_age')))
    if a.startswith('SPLIT'):
        ok(f'{a}: подмена выборки заявки меняет заявку', any(p['claimed'] != q['claimed'] for p, q in zip(H[a], h2)))
ok('SPLIT: claimed == claimed_fresh', all(p['claimed'] == p['claimed_fresh'] for p in H['SPLIT16+16']))
ok('SAME: claimed по выборке отбора, claimed_fresh — по другой', any(p['claimed'] != p['claimed_fresh'] for p in H['SAME16']))

# 5. тождество SPLIT16+16 ≡ SAME16 по траектории; общая начальная популяция
h1, h3 = H['SPLIT16+16'], H['SAME16']
ok('SPLIT16+16 ≡ SAME16: true, true_fresh, elite_age, claimed_fresh совпадают по всем поколениям', same(h1, h3, ('true', 'true_fresh', 'elite_age', 'claimed_fresh')))
ok('SPLIT16+16 ≠ SAME16 по claimed', any(p['claimed'] != q['claimed'] for p, q in zip(h1, h3)))
ok('claimed(SPLIT16+16) == claimed_fresh(SAME16) по всем поколениям', all(p['claimed'] == q['claimed_fresh'] for p, q in zip(h1, h3)))
pop = lambda seed, shift=0: [E.rand_tree(np.random.default_rng((seed + shift) * 1000 + 3), 4) for _ in range(E.POP)]   # как evo06.run (T3 → tn=3)
ok('начальная популяция: SAME32 = SPLIT16+16 = FIXED32 = SAME16 (поток r без сдвига); AA32 — другая (сдвиг +500)',
   pop(996) == pop(996) and pop(996) != pop(996, 500) and V.parse_arm('AA32')[3] == 500 and all(V.parse_arm(a)[3] == 0 for a in ARMS if a != 'AA32'))

# 6. подмена скрытого набора: истина не участвует в отборе (обёртка над default_rng; evo06.py не меняется)
_orig = np.random.default_rng
def _patched(seed=None, *a, **k):
    return _orig(10 ** 6 + 777, *a, **k) if seed == 10 ** 6 + 996 else _orig(seed, *a, **k)
np.random.default_rng = _patched
try:
    H2 = {a: V.run('T3', a, 996) for a in ARMS}
finally:
    np.random.default_rng = _orig
for a in ARMS:
    if a == 'ORACLE':
        ok('ORACLE: подмена скрытого набора меняет claimed (отбор по правде — потолок)', any(p['claimed'] != q['claimed'] for p, q in zip(H[a], H2[a])))
    else:
        ok(f'{a}: подмена скрытого набора не меняет claimed, claimed_fresh, elite_age', same(H[a], H2[a], ('claimed', 'claimed_fresh', 'elite_age')))
ok('подмена скрытого набора меняет true (набор действительно другой)', any(p['true'] != q['true'] for p, q in zip(H['SAME32'], H2['SAME32'])))

# 7. бюджет
lab = {a: H[a][5]['n_labels'] for a in ('FIXED32', 'SAME32', 'SPLIT16+16')}
ok('labels на поколение: FIXED32 (после g=0) 0, SAME32 32, SPLIT16+16 32', lab == {'FIXED32': 0, 'SAME32': 32, 'SPLIT16+16': 32}, str(lab))
calls = {a: H[a][5]['n_calls'] for a in ('SAME32', 'SPLIT16+16', 'SAME16', 'SPLIT8+8')}
ok('вызовов на поколение: SAME32 9600, SPLIT16+16 4816, SAME16 4800, SPLIT8+8 2408', calls == {'SAME32': 9600, 'SPLIT16+16': 4816, 'SAME16': 4800, 'SPLIT8+8': 2408}, str(calls))

n_fail = sum(not c for _, c, _ in out)
print(f'итого: {len(out)} проверок, провалов {n_fail}')
sys.exit(1 if n_fail else 0)
