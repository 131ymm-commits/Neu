#!/usr/bin/env python3
"""TRUST-04: вердикты и сводные исходы по букве PREREG-TRUST-04.md §4.
Вход — results_trust_04_A.json и results_trust_04_B.json в папке DIR (по умолчанию — папка опыта), для блока В —
indep/test/results_indep_04.json (если есть). Выход — DIR/analysis_trust_04.json.
Запуск: python3 analyze_trust_04.py [DIR] [--indep ПУТЬ].

Правила исходов (одни для частей и сводных):
  знаковое и интервальное предсказание с порогом k из N: «подтверждено» — счёт ≥ k; «опровергнуто» — счёт ≤ N − k;
  иначе «не показано»;
  эквивалентность (TOST Шуирмана по ДИ Уэлча 90 % разности средних): «подтверждено» — ДИ внутри (−δ; δ); «опровергнуто» —
  ДИ целиком вне (−δ; δ); иначе «не показано»;
  сводный: «подтверждено» — все части подтверждены; «опровергнуто» — хоть одна опровергнута; иначе «не подтверждено».
Сводные исходы считаются только на тестовых зёрнах (600–609)."""
import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import exp_trust_04 as E  # noqa: E402

# точки теории заморожены при регистрации (assert до 1e-4 против теории из results)
FROZEN = {'base': (0.9873, 0.6891), 'r075': (0.5768, 0.3897), 'r095': (1.7134, 1.1968), 'b03': (1.2221, 0.9622),
          'b09': (0.8328, 0.5372)}
DELTA_EQ = 0.1                                            # граница эквивалентности по u

args = [a for a in sys.argv[1:] if not a.startswith('--')]
DIR = os.path.join(HERE, args[0]) if args else HERE
INDEP = sys.argv[sys.argv.index('--indep') + 1] if '--indep' in sys.argv else os.path.join(HERE, 'indep', 'test', 'results_indep_04.json')
runs, theory, params = [], None, None
for part in ('A', 'B'):
    p = os.path.join(DIR, f'results_trust_04_{part}.json')
    d = json.load(open(p)); runs += d['runs']; theory = d['theory']; params = d['params']
    assert d['params']['part'] == part
for w, (my, far) in FROZEN.items():
    assert abs(theory[w]['myopic']['wG'] - my) < 1e-4 and abs(theory[w]['farsighted']['wG'] - far) < 1e-4, (w, theory[w])
seeds = params['SEEDS']; NS = len(seeds)
MAIN = os.path.abspath(DIR) == HERE
if MAIN:
    assert seeds == E.SEEDS and params['G'] == E.G and params['WINDOW'] == E.WINDOW, 'параметры результата не те'
    assert json.loads(json.dumps(params['ARMS'], default=float)) == json.loads(json.dumps(E.ARMS, default=float)), 'руки не те'
FULL = seeds == E.SEEDS
if not FULL:
    print(f'внимание: зёрна {seeds[0]}–{seeds[-1]} ({NS}) — не тестовые; сводные исходы не считаются')
R = {(r['seed'], r['arm']): r for r in runs}
assert all((s, a) in R for s in seeds for a in E.ARMS), 'неполные ячейки'
n_snap_exp = len([g for g in range(params['G']) if (g % 10 == 0 or g == params['G'] - 1) and g >= params['G'] - params['WINDOW']])
assert all(r['n_snap'] == n_snap_exp and r['n_price'] == params['WINDOW'] for r in R.values())
F = {k: v['final'] for k, v in R.items()}
for (s, a), f in F.items():                                # проверки построения Прайса
    sp = E.ARMS[a]
    if sp['council']:
        assert f['price_within'] == 0.0
    if not sp['group_sel'] or sp['m'] == 1:
        assert abs(f['price_between']) < 1e-12


def uw(arm):
    my, far = FROZEN[E.ARMS[arm]['world']]
    return [(F[(s, arm)]['wG'] - far) / (my - far) for s in seeds]


col = lambda arm, k='wG': [F[(s, arm)][k] for s in seeds]


def boot_ci(x, B=10000, seed=0, q=(0.025, 0.975)):
    x = np.asarray(x, float); g = np.random.default_rng(seed)
    m = x[g.integers(0, len(x), (B, len(x)))].mean(1)
    return [float(x.mean()), float(np.quantile(m, q[0])), float(np.quantile(m, q[1]))]


def welch_ci(x, y, level=0.90):
    """ДИ разности средних по Уэлчу (TOST Шуирмана: эквивалентность при ДИ 90 % внутри (−δ; δ))."""
    from scipy.stats import t as tdist
    x, y = np.asarray(x, float), np.asarray(y, float); vx, vy = x.var(ddof=1) / len(x), y.var(ddof=1) / len(y)
    se = np.sqrt(vx + vy); df = (vx + vy) ** 2 / (vx ** 2 / (len(x) - 1) + vy ** 2 / (len(y) - 1))
    h = float(tdist.ppf(1 - (1 - level) / 2, df)) * se; d = float(x.mean() - y.mean())
    return [d, d - h, d + h]


def outcome(count, k, n=None):
    n = NS if n is None else n
    return 'подтверждено' if count >= k else ('опровергнуто' if count <= n - k else 'не показано')


V = {}


def interval(name, vals, lo, hi, k, strict=False, **extra):
    c = sum((lo < x < hi) if strict else (lo <= x <= hi) for x in vals)
    V[name] = dict(kind='интервал', k=k, n=c, outcome=outcome(c, k), interval=[lo, hi], value=boot_ci(vals), **extra)


def sign(name, a, b, k, key='wG'):                         # счёт зёрен, где a < b
    da = [F[(s, a)][key] - F[(s, b)][key] for s in seeds]
    c = sum(x < 0 for x in da)
    V[name] = dict(kind='знак', k=k, n=c, outcome=outcome(c, k), diff=boot_ci(da), pair=[a, b])


def equiv(name, x, y, delta=DELTA_EQ, **extra):
    m, lo, hi = welch_ci(x, y)
    oc = 'подтверждено' if (-delta < lo and hi < delta) else ('опровергнуто' if (lo >= delta or hi <= -delta) else 'не показано')
    V[name] = dict(kind='эквивалентность', delta=delta, outcome=oc, diff_ci90=[m, lo, hi], **extra)


# ---- блок А (мир base) ----
interval('A1', uw('POOLED'), -1 / 6, 1 / 6, 8)
interval('A2', uw('POOLED_FREE'), -1 / 6, 1 / 6, 8)
interval('A3', uw('DEMES'), 1 / 6, 5 / 6, 8, strict=True)
interval('A4', uw('DEMES_FREE'), 1 / 6, 5 / 6, 8, strict=True)
sign('A5', 'POOLED', 'DEMES', 9)
sign('A6', 'POOLED_FREE', 'DEMES_FREE', 9)
equiv('A7', uw('POOLED'), uw('POOLED_FREE'))
equiv('A8', uw('DEMES'), uw('DEMES_FREE'))
interval('A9', uw('DEMES_NOSEL'), 2 / 3, 4 / 3, 9)
interval('A10', uw('DEMES_NOSEL_FREE'), 2 / 3, 4 / 3, 9)
interval('A11', uw('COUNCIL_SIGN'), -1 / 6, 1 / 6, 8)
equiv('A12', uw('COUNCIL'), uw('COUNCIL_SIGN'))
interval('A13', uw('COUNCIL'), -1 / 6, 1 / 6, 9)
interval('A14', uw('MYOPIC'), 2 / 3, 4 / 3, 9)
# ---- блок Б (переносимость) ----
for i, c in enumerate(('r075', 'r095', 'b03', 'b09', 'IND', 'MIG', 'SIG5')):
    sign(f'B{i + 1}', f'POOLED_{c}', f'DEMES_{c}', 9)
for i, w in enumerate(('r075', 'r095', 'b03', 'b09')):
    interval(f'B{i + 8}', uw(f'POOLED_{w}'), -1 / 3, 1 / 3, 8)
    interval(f'B{i + 12}', uw(f'MYOPIC_{w}'), 2 / 3, 4 / 3, 9)
# разведка блока Б
# EB1: независимый риск — |u| POOLED_IND больше, чем у POOLED (по номеру зерна); EB2: миграция POOLED не сдвигает (±0,1)
_d1 = [abs(a) - abs(b) for a, b in zip(uw('POOLED'), uw('POOLED_IND'))]
V['EB1'] = dict(kind='знак', k=7, n=sum(x < 0 for x in _d1), outcome=outcome(sum(x < 0 for x in _d1), 7), diff=boot_ci(_d1))
equiv('EB2', uw('POOLED_MIG'), uw('POOLED'))
sign('EB3', 'DEMES', 'DEMES_MIG', 7)                      # миграция: многоуровневый отбор слабее
sign('EB4', 'DEMES', 'DEMES_SIG5', 7)                     # шаг мутации ×5: остаток многоуровневого отбора больше
for _w in ('r075', 'r095', 'b03', 'b09'):                  # EB5: доля пути DEMES не зависит от мира (±0,1)
    equiv(f'EB5_{_w}', uw(f'DEMES_{_w}'), uw('DEMES'))
# ---- проверки построения (вне семьи) ----
K = {}
for a in ('POOLED_NOSEL', 'POOLED_NOSEL_FREE'):
    gap = [F[(s, a)]['logloss'] - F[(s, 'POOLED')]['logloss'] for s in seeds]
    K[a] = dict(logloss_gap=boot_ci(gap), n_gap_ge_002=sum(x >= 0.02 for x in gap), wG=boot_ci(col(a)),
                sd_groups=boot_ci(col(a, 'wG_sd_groups')), price_within=boot_ci(col(a, 'price_within')))
# ---- описательно: части Прайса ----
D1 = {a: dict(within=boot_ci(col(a, 'price_within')), between=boot_ci(col(a, 'price_between'))) for a in E.ARMS}
# ---- блок В (независимая реализация) ----
C = None
if os.path.exists(INDEP):
    ind = json.load(open(INDEP)); IR = {(r['seed'], r['arm']): r for r in ind['runs']}
    iseeds = sorted({s for s, _ in IR}); C = dict(theory=ind['theory'], seeds=iseeds)
    for a in ('MYOPIC', 'DEMES', 'POOLED', 'COUNCIL'):
        ui = [IR[(s, a)]['u'] for s in iseeds]
        equiv(f'C_{a}', ui, uw(a), u_indep=boot_ci(ui), u_main=boot_ci(uw(a)))
    cd = sum(IR[(s, 'POOLED')]['u'] < IR[(s, 'DEMES')]['u'] for s in iseeds)
    V['C_ORDER'] = dict(kind='знак', k=9, n=cd, outcome=outcome(cd, 9, len(iseeds)),
                        diff=boot_ci([IR[(s, 'POOLED')]['u'] - IR[(s, 'DEMES')]['u'] for s in iseeds]))
summary = None
if FULL:
    def combine(parts):
        oc = [V[p]['outcome'] for p in parts if p in V]
        if len(oc) < len(parts):
            return dict(parts=parts, outcome='не посчитано (нет частей)')
        return dict(parts=parts, outcome='подтверждено' if all(o == 'подтверждено' for o in oc)
                    else ('опровергнуто' if 'опровергнуто' in oc else 'не подтверждено'))
    summary = dict(SA=combine(['A1', 'A2', 'A4', 'A5', 'A6', 'A7', 'A8']), SA2=combine(['A11', 'A12']),
                   SB=combine([f'B{i}' for i in range(1, 8)]), SB2=combine([f'B{i}' for i in range(8, 12)]),
                   SC=combine(['C_MYOPIC', 'C_DEMES', 'C_POOLED', 'C_COUNCIL', 'C_ORDER']))
keys = ('wG', 'b', 'logloss', 'self_dec', 'acc', 'ece', 'wG_sd_groups', 'price_between', 'price_within')
arms_mean = {a: dict(u=boot_ci(uw(a)), **{k: boot_ci(col(a, k)) for k in keys}) for a in E.ARMS}
out = dict(verdicts=V, summary=summary, construction=K, descriptive_price=D1, indep=C, arms=arms_mean, theory=theory,
           frozen=FROZEN, n_seeds=NS, seeds=seeds,
           rows={str(s): {a: dict(F[(s, a)], u=uw(a)[seeds.index(s)]) for a in E.ARMS} for s in seeds})
json.dump(out, open(os.path.join(DIR, 'analysis_trust_04.json'), 'w'), ensure_ascii=False, indent=1,
          default=lambda o: o.item() if hasattr(o, 'item') else str(o))
for k, v in V.items():
    show = {kk: (np.round(vv, 4).tolist() if isinstance(vv, list) else vv) for kk, vv in v.items() if kk not in ('outcome', 'kind')}
    print(k, v['outcome'], show)
print('проверки построения:', {a: {k: (np.round(v, 4).tolist() if isinstance(v, list) else v) for k, v in d.items()} for a, d in K.items()})
print('сводные исходы:', summary)
