#!/usr/bin/env python3
"""TRUST-04: вердикты и сводные исходы по букве PREREG-TRUST-04.md §4.
Вход — results_trust_04_A.json и results_trust_04_B.json в папке DIR (по умолчанию — папка опыта); для блока В —
indep/test700/results_indep_04.json (обёртка indep_runner.py). Выход — DIR/analysis_trust_04.json.
Запуск: python3 analyze_trust_04.py [DIR] [--indep ПУТЬ].

Правила исходов (одни для частей и сводных):
  знаковое и интервальное предсказание с порогом k из N: «подтверждено» — счёт ≥ k; «опровергнуто» — счёт ≤ N − k;
  иначе «не показано»;
  эквивалентность (TOST Шуирмана по ДИ Уэлча уровня CI_EQ разности средних): «подтверждено» — ДИ внутри (−δ; δ);
  «опровергнуто» — ДИ целиком вне (−δ; δ); иначе «не показано»;
  сводный: «подтверждено» — все части подтверждены; «опровергнуто» — хоть одна опровергнута; иначе «не подтверждено».
Пороги k заданы для 20 тестовых зёрен 600–619 (калибровка — pilot/v2/pilot_calib2.py). На других зёрнах (пилот, сухой
прогон) k масштабируется: ⌈k·N/20⌉, а сводные исходы не считаются."""
import glob
import hashlib
import json
import math
import os
import sys

import numpy as np
from scipy.stats import levene, spearmanr
from scipy.stats import t as tdist

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import exp_trust_04 as E  # noqa: E402

# ---- заморожено при регистрации ----
FROZEN = {'base': (0.9873, 0.6891), 'r075': (0.5768, 0.3897), 'r095': (1.7134, 1.1968), 'b03': (1.2221, 0.9622),
          'b09': (0.8328, 0.5372)}                         # (близорукая, дальновидная) w_G; assert до 1e-4 против теории
DELTA_EQ = 0.1                                             # граница эквивалентности по u
CI_EQ = None                                               # уровень ДИ Уэлча для TOST — после калибровки
K = {}                                                     # пороги k из 20 — после калибровки
K_EXPL = 15                                                # знаковые предсказания разведки: k из 20
BREAK_SD = 0.5                                             # срыв: SD w_G между группами > 0,5 в среднем по окну (Д2 TRUST-03)
INDEP_SEEDS = list(range(700, 720))
E1_ARMS = ['DEMES', 'DEMES_FREE', 'DEMES_GPOOL', 'DEMES_IND', 'DEMES_MIG', 'DEMES_SIG5', 'DEMES_r075', 'DEMES_r095',
           'DEMES_b03', 'DEMES_b09']                       # руки с отбором внутри группы по своему весу (EB6)
COMPOSITES = dict(SA=['A1', 'A2', 'A3', 'A4', 'A5', 'A6', 'A7', 'A8'], SA2=['A11', 'A12'],
                  SA3=['A2', 'A4', 'A15', 'A16', 'A17', 'A18'], SB=[f'B{i}' for i in range(1, 8)],
                  SB2=[f'B{i}' for i in range(8, 12)], SC=['C_MYOPIC', 'C_DEMES', 'C_POOLED', 'C_COUNCIL', 'C_ORDER'])
sha = lambda p: hashlib.sha256(open(p, 'rb').read()).hexdigest()

_argv, _rest, INDEP = sys.argv[1:], [], os.path.join(HERE, 'indep', 'test700', 'results_indep_04.json')
while _argv:
    _x = _argv.pop(0)
    if _x == '--indep':
        INDEP = os.path.join(HERE, _argv.pop(0))
    else:
        _rest.append(_x)
DIR = os.path.join(HERE, _rest[0]) if _rest else HERE
MAIN = os.path.abspath(DIR) == HERE
HASHES = json.load(open(os.path.join(HERE, 'prereg_hashes.json'))) if os.path.exists(os.path.join(HERE, 'prereg_hashes.json')) else None
assert CI_EQ in (0.90, 0.95) and K, 'пороги не заморожены'

# ---- загрузка и проверки входа ----
parts = {}
for p in sorted(glob.glob(os.path.join(DIR, 'results_trust_04_*.json'))):
    d = json.load(open(p)); pt = d['params']['part']
    assert pt in ('A', 'B') and pt not in parts and os.path.basename(p) == f'results_trust_04_{pt}.json', p
    parts[pt] = d
assert set(parts) == {'A', 'B'}, f'нужны части A и B, есть {sorted(parts)}'
pa, pb = parts['A']['params'], parts['B']['params']
for key in ('L_EP', 'G', 'SIG', 'WINDOW', 'SEEDS', 'code_sha256'):
    assert pa[key] == pb[key], f'части A и B различаются: {key}'
assert json.dumps(parts['A']['theory'], sort_keys=True) == json.dumps(parts['B']['theory'], sort_keys=True)
assert json.loads(json.dumps(pa['ARMS'], default=float)) == json.loads(json.dumps(E.ARMS, default=float)), 'руки не те'
assert json.loads(json.dumps(pb['ARMS'], default=float)) == json.loads(json.dumps(E.ARMS, default=float)), 'руки не те'
assert pa['G'] == E.G and pa['WINDOW'] == E.WINDOW and pa['L_EP'] == E.L_EP and pa['SIG'] == E.SIG
seeds = pa['SEEDS']; NS = len(seeds); FULL = seeds == E.SEEDS
if MAIN:
    assert FULL, 'в папке опыта — не тестовые зёрна'
    assert HASHES is not None and pa['code_sha256'] == HASHES['exp_trust_04.py'] == E.CODE_SHA256, 'код результата — не зарегистрированный'
    assert sha(os.path.abspath(__file__)) == HASHES['analyze_trust_04.py'], 'анализ — не зарегистрированный'
if not FULL:
    print(f'внимание: зёрна {seeds[0]}–{seeds[-1]} ({NS}) — не тестовые; k масштабируется, сводные исходы не считаются')
theory = parts['A']['theory']
for w, (my, far) in FROZEN.items():
    assert abs(theory[w]['myopic']['wG'] - my) < 1e-4 and abs(theory[w]['farsighted']['wG'] - far) < 1e-4, (w, theory[w])
R = {}
for pt, d in parts.items():
    want = {a for a, s in E.ARMS.items() if s['part'] == pt}
    got = {(r['seed'], r['arm']) for r in d['runs']}
    assert got == {(s, a) for s in seeds for a in want} and len(d['runs']) == len(got), f'часть {pt}: ячейки не те'
    R.update({(r['seed'], r['arm']): r for r in d['runs']})
n_snap_exp = len([g for g in range(E.G) if (g % 10 == 0 or g == E.G - 1) and g >= E.G - E.WINDOW])
assert all(r['n_snap'] == n_snap_exp and r['n_price'] == E.WINDOW for r in R.values())
F = {k: v['final'] for k, v in R.items()}
for (s, a), f in F.items():                                # проверки построения Прайса
    sp = E.ARMS[a]
    if sp['council'] or not sp['wsel']:
        assert f['price_within'] == 0.0, (s, a)
    if not sp['group_sel'] or sp['m'] == 1:
        assert abs(f['price_between']) < 1e-12, (s, a)


def uw(arm):
    my, far = FROZEN[E.ARMS[arm]['world']]
    return [(F[(s, arm)]['wG'] - far) / (my - far) for s in seeds]


col = lambda arm, k='wG': [F[(s, arm)][k] for s in seeds]
kk = lambda name: K[name] if NS == 20 else math.ceil(K[name] * NS / 20)


def boot_ci(x, B=10000, seed=0, q=(0.025, 0.975)):
    x = np.asarray(x, float); g = np.random.default_rng(seed)
    m = x[g.integers(0, len(x), (B, len(x)))].mean(1)
    return [float(x.mean()), float(np.quantile(m, q[0])), float(np.quantile(m, q[1]))]


def welch_ci(x, y, level):
    """ДИ разности средних по Уэлчу (TOST Шуирмана: эквивалентность при ДИ уровня level внутри (−δ; δ))."""
    x, y = np.asarray(x, float), np.asarray(y, float); vx, vy = x.var(ddof=1) / len(x), y.var(ddof=1) / len(y)
    se = np.sqrt(vx + vy); df = (vx + vy) ** 2 / (vx ** 2 / (len(x) - 1) + vy ** 2 / (len(y) - 1))
    h = float(tdist.ppf(1 - (1 - level) / 2, df)) * se; d = float(x.mean() - y.mean())
    return [d, d - h, d + h]


def outcome(count, k, n):
    return 'подтверждено' if count >= k else ('опровергнуто' if count <= n - k else 'не показано')


V, X = {}, {}                                              # основная семья и разведка


def interval(name, vals, lo, hi, strict=False, into=V, **extra):
    k = kk(name); c = sum((lo < x < hi) if strict else (lo <= x <= hi) for x in vals)
    into[name] = dict(kind='интервал', k=k, n=c, N=len(vals), outcome=outcome(c, k, len(vals)), interval=[lo, hi],
                      strict=strict, value=boot_ci(vals), **extra)


def sign(name, a, b, k=None, into=V, key='wG'):            # счёт зёрен (по номеру), где a < b
    k = kk(name) if k is None else k
    da = [F[(s, a)][key] - F[(s, b)][key] for s in seeds]; c = sum(x < 0 for x in da)
    into[name] = dict(kind='знак', k=k, n=c, N=NS, outcome=outcome(c, k, NS), diff=boot_ci(da), pair=[a, b])


def equiv(name, x, y, into=V, **extra):
    m, lo, hi = welch_ci(x, y, CI_EQ)
    oc = 'подтверждено' if (-DELTA_EQ < lo and hi < DELTA_EQ) else ('опровергнуто' if (lo >= DELTA_EQ or hi <= -DELTA_EQ) else 'не показано')
    into[name] = dict(kind='эквивалентность', delta=DELTA_EQ, level=CI_EQ, outcome=oc, diff_ci=[m, lo, hi], **extra)


# ---- блок А (мир base) ----
interval('A1', uw('POOLED'), -1 / 6, 1 / 6)
interval('A2', uw('POOLED_FREE'), -1 / 6, 1 / 6)
interval('A3', uw('DEMES'), 1 / 6, 5 / 6, strict=True)
interval('A4', uw('DEMES_FREE'), 1 / 6, 5 / 6, strict=True)
sign('A5', 'POOLED', 'DEMES')
sign('A6', 'POOLED_FREE', 'DEMES_FREE')
equiv('A7', uw('POOLED'), uw('POOLED_FREE'))
equiv('A8', uw('DEMES'), uw('DEMES_FREE'))
interval('A9', uw('DEMES_NOSEL'), 2 / 3, 4 / 3)
interval('A10', uw('DEMES_NOSEL_FREE'), 2 / 3, 4 / 3)
interval('A11', uw('COUNCIL_SIGN'), -1 / 3, 1 / 3)
equiv('A12', uw('COUNCIL'), uw('COUNCIL_SIGN'))
interval('A13', uw('COUNCIL'), -1 / 6, 1 / 6)
interval('A14', uw('MYOPIC'), 2 / 3, 4 / 3)
_brk = [x > BREAK_SD for x in col('DEMES_NOWITHIN', 'wG_sd_groups')]
interval('A15', uw('DEMES_NOWITHIN'), -1 / 6, 1 / 6, breakdowns=int(sum(_brk)))
interval('A16', uw('DEMES_GPOOL'), 1 / 6, 5 / 6, strict=True)
equiv('A17', uw('DEMES_GPOOL'), uw('DEMES_FREE'))
sign('A18', 'POOLED_FREE', 'DEMES_GPOOL')
# ---- блок Б (переносимость) ----
for i, c in enumerate(('r075', 'r095', 'b03', 'b09', 'IND', 'MIG', 'SIG5')):
    sign(f'B{i + 1}', f'POOLED_{c}', f'DEMES_{c}')
for i, w in enumerate(('r075', 'r095', 'b03', 'b09')):
    interval(f'B{i + 8}', uw(f'POOLED_{w}'), -1 / 3, 1 / 3)
    interval(f'B{i + 12}', uw(f'MYOPIC_{w}'), 2 / 3, 4 / 3)
# ---- блок В (независимая реализация, свои зёрна 700–719) ----
C = None
if os.path.exists(INDEP):
    ind = json.load(open(INDEP)); m = ind['meta']
    assert ind['complete'] is True, 'прогон независимой реализации не завершён'
    assert (m['noise_convention'], m['sd_init'], m['sd_mut'], m['n_gen'], m['episodes'], m['burn_in'], m['snap_every']) == \
        ('sd', 0.01, 0.04, E.G, E.L_EP, E.G - E.WINDOW, 10), 'параметры независимой реализации не те'
    iseeds = m['seeds']
    if FULL:
        assert iseeds == INDEP_SEEDS, 'зёрна независимой реализации не те'
    IR = {(r['seed'], r['arm']): r for r in ind['runs']}
    assert set(IR) == {(s, a) for s in iseeds for a in ('MYOPIC', 'DEMES', 'POOLED', 'COUNCIL')} and len(ind['runs']) == len(IR)
    th = ind['theory']; my0, far0 = FROZEN['base']
    assert abs(th['w_my'] - my0) < 1e-4 and abs(th['w_far'] - far0) < 1e-4, 'теория независимой реализации — не FROZEN'
    if MAIN:
        assert m['script_sha256'] == HASHES['indep/indep_trust_04.py'] and m['spec_sha256'] == HASHES['indep/SPEC.md']
        assert m['wrapper']['sha256'] == HASHES['indep_runner.py'], 'обёртка — не зарегистрированная'
    ui = lambda a: [(IR[(s, a)]['w_G'] - far0) / (my0 - far0) for s in iseeds]     # u — по FROZEN, не по своей теории
    C = dict(seeds=iseeds, theory=th, n=len(iseeds))
    for a in ('MYOPIC', 'DEMES', 'POOLED', 'COUNCIL'):
        equiv(f'C_{a}', ui(a), uw(a), u_indep=boot_ci(ui(a)), u_main=boot_ci(uw(a)))
    cd = sum(x < y for x, y in zip(ui('POOLED'), ui('DEMES'))); kc = K['C_ORDER'] if len(iseeds) == 20 else math.ceil(K['C_ORDER'] * len(iseeds) / 20)
    V['C_ORDER'] = dict(kind='знак', k=kc, n=cd, N=len(iseeds), outcome=outcome(cd, kc, len(iseeds)),
                        diff=boot_ci([x - y for x, y in zip(ui('POOLED'), ui('DEMES'))]))
elif MAIN:
    raise SystemExit('нет результатов независимой реализации: ' + INDEP)
# ---- разведка (в реестр — только как гипотеза) ----
_a, _b = np.array(uw('POOLED_IND')), np.array(uw('POOLED'))
_p = float(levene(_a, _b, center='median').pvalue)
_ok = bool(_a.std(ddof=1) > _b.std(ddof=1) and _p / 2 < 0.05)
X['EB1'] = dict(kind='разброс (Браун–Форсайт, односторонний 0,05)', sd_IND=float(_a.std(ddof=1)), sd_base=float(_b.std(ddof=1)),
                p_one_sided=_p / 2 if _a.std(ddof=1) > _b.std(ddof=1) else 1 - _p / 2, outcome='подтверждено' if _ok else 'не показано')
equiv('EB2', uw('POOLED_MIG'), uw('POOLED'), into=X)
sign('EB3', 'DEMES', 'DEMES_MIG', k=K_EXPL if NS == 20 else math.ceil(K_EXPL * NS / 20), into=X)
sign('EB4', 'DEMES', 'DEMES_SIG5', k=K_EXPL if NS == 20 else math.ceil(K_EXPL * NS / 20), into=X)
for _w in ('r075', 'r095', 'b03', 'b09'):
    equiv(f'EB5_{_w}', uw(f'DEMES_{_w}'), uw('DEMES'), into=X)
_ub = np.array([np.mean(uw(a)) for a in E1_ARMS])
_R = np.array([np.mean(col(a, 'V_between')) / (np.mean(col(a, 'V_between')) + np.mean(col(a, 'V_within'))) for a in E1_ARMS])
_rho = spearmanr(_ub, 1 - _R); _gap = np.abs(_ub - (1 - _R))
X['EB6'] = dict(kind='u ≈ 1 − R', arms=E1_ARMS, u=_ub.round(4).tolist(), one_minus_R=(1 - _R).round(4).tolist(), abs_gap=_gap.round(4).tolist(),
                n_within_01=int(np.sum(_gap <= 0.1)), spearman=float(_rho.statistic), spearman_p_two_sided=float(_rho.pvalue),
                outcome='подтверждено' if (np.sum(_gap <= 0.1) >= 8 and _rho.statistic > 0) else 'не показано')
# ---- проверки построения и описательное (вне семьи) ----
KC = {}
for a in ('POOLED_NOSEL', 'POOLED_NOSEL_FREE'):
    gap = [F[(s, a)]['logloss'] - F[(s, 'POOLED')]['logloss'] for s in seeds]
    KC[a] = dict(logloss_gap=boot_ci(gap), n_gap_ge_002=sum(x >= 0.02 for x in gap), wG=boot_ci(col(a)),
                 sd_groups=boot_ci(col(a, 'wG_sd_groups')), price_within=boot_ci(col(a, 'price_within')))
STEP = {a: boot_ci(col(a, 'step_sd')) for a in E.ARMS}    # K2: SD шага среднего w_G группы за поколение
BRK = {a: dict(n_break=sum(x > BREAK_SD for x in col(a, 'wG_sd_groups')),
               V_within_break=[F[(s, a)]['V_within'] for s in seeds if F[(s, a)]['wG_sd_groups'] > BREAK_SD],
               V_within_ok=boot_ci([F[(s, a)]['V_within'] for s in seeds if F[(s, a)]['wG_sd_groups'] <= BREAK_SD] or [float('nan')]))
       for a in E.ARMS}
D1 = {a: dict(within=boot_ci(col(a, 'price_within')), between=boot_ci(col(a, 'price_between'))) for a in E.ARMS}
summary = None
if FULL:
    def combine(ps):
        oc = [V[p]['outcome'] for p in ps if p in V]
        if len(oc) < len(ps):
            return dict(parts=ps, outcome='не посчитано (нет частей)')
        return dict(parts=ps, outcome='подтверждено' if all(o == 'подтверждено' for o in oc)
                    else ('опровергнуто' if 'опровергнуто' in oc else 'не подтверждено'))
    summary = {c: combine(ps) for c, ps in COMPOSITES.items()}
keys = ('wG', 'b', 'logloss', 'self_dec', 'acc', 'ece', 'wG_sd_groups', 'V_between', 'V_within', 'R', 'step_sd',
        'price_between', 'price_within')
arms_mean = {a: dict(u=boot_ci(uw(a)), **{k: boot_ci(col(a, k)) for k in keys}) for a in E.ARMS}
out = dict(verdicts=V, explore=X, summary=summary, construction=KC, step_sd=STEP, breakdowns=BRK, descriptive_price=D1,
           indep=C, arms=arms_mean, theory=theory, frozen=FROZEN, K=K, CI_EQ=CI_EQ, n_seeds=NS, seeds=seeds,
           code_sha256=pa['code_sha256'],
           rows={str(s): {a: dict(F[(s, a)], u=uw(a)[seeds.index(s)]) for a in E.ARMS} for s in seeds})
json.dump(out, open(os.path.join(DIR, 'analysis_trust_04.json'), 'w'), ensure_ascii=False, indent=1,
          default=lambda o: o.item() if hasattr(o, 'item') else str(o))


def show(v):
    return {kk_: (np.round(vv, 4).tolist() if isinstance(vv, list) and all(isinstance(x, (int, float)) for x in vv) else vv)
            for kk_, vv in v.items() if kk_ not in ('outcome', 'kind')}


for name, v in V.items():
    print(name, v['outcome'], show(v))
print('разведка:')
for name, v in X.items():
    print(' ', name, v['outcome'], show(v))
print('шаг среднего группы (SD):', {a: round(v[0], 4) for a, v in STEP.items()})
print('срывы (SD между группами > 0,5):', {a: v['n_break'] for a, v in BRK.items() if v['n_break']})
print('проверки построения:', {a: {k: (np.round(v, 4).tolist() if isinstance(v, list) else v) for k, v in d.items()} for a, d in KC.items()})
print('сводные исходы:', summary)
