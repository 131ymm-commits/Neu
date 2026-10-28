#!/usr/bin/env python3
"""TRUST-03: вердикты и сводные исходы по букве PREREG-TRUST-03.md §4 из results_trust_03.json →
analysis_trust_03.json (рядом с входным файлом). Запуск: python3 analyze_trust_03.py [путь к results].

Правила исходов (одни для частей и сводных):
  знаковое и интервальное предсказание с порогом k из 10: «подтверждено» — счёт ≥ k; «опровергнуто» — счёт ≤ 10 − k;
  иначе «не показано»; сводный исход: «подтверждено» — все части подтверждены; «опровергнуто» — хоть одна
  опровергнута; иначе «не подтверждено». При числе зёрен ≠ 10 (пилот, сухой прогон) сводные исходы не считаются."""
import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import exp_trust_03 as E  # noqa: E402

# кромки заморожены при регистрации (теория — сокращённый агент, точный перебор; PREREG §2)
W_MY, W_FAR = 0.9873, 0.6891
D = W_MY - W_FAR                                          # разрыв 0,2982; u = 0 — дальновидная точка, u = 1 — близорукая

src = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, 'results_trust_03.json')
d = json.load(open(src))
th = d['theory']; seeds = d['params']['SEEDS']; NS = len(seeds); G, WIN = d['params']['G'], d['params']['WINDOW']
assert abs(th['myopic']['wG'] - W_MY) < 1e-4 and abs(th['farsighted']['wG'] - W_FAR) < 1e-4, 'теория не та, что в PREREG'
MAIN = os.path.dirname(os.path.abspath(src)) == HERE        # основной прогон — results_trust_03.json в папке опыта
if MAIN:
    assert seeds == E.SEEDS, 'тестовые зёрна не те'
FULL = seeds == E.SEEDS
if not FULL:
    print(f'внимание: зёрна {seeds[0]}–{seeds[-1]} ({NS}) — не тестовые; вердикты ниже не в зачёт, сводные исходы не считаются')
R = {(r['seed'], r['arm']): r for r in d['runs']}
assert all((s, a) in R for s in seeds for a in E.ARMS), 'неполные ячейки'
n_snap_exp = len([g for g in range(G) if (g % 10 == 0 or g == G - 1) and g >= G - WIN])
assert all(r['n_snap'] == n_snap_exp and r['n_price'] == WIN for r in R.values()), 'не то число снимков или поколений окна'
F = {k: v['final'] for k, v in R.items()}
# проверки построения разложения Прайса
for (s, a), f in F.items():
    sp = E.ARMS[a]
    if sp['council'] or not sp['within_sel']:
        assert abs(f['price_within']) < 1e-12, (s, a, 'внутригрупповая часть должна быть нулём')
    if not sp['group_sel'] or sp['m'] == 1:
        assert abs(f['price_between']) < 1e-12, (s, a, 'межгрупповая часть должна быть нулём')


def boot_ci(x, B=10000, seed=0):
    x = np.asarray(x, float); g = np.random.default_rng(seed)
    m = x[g.integers(0, len(x), (B, len(x)))].mean(1)
    return [float(x.mean()), float(np.quantile(m, 0.025)), float(np.quantile(m, 0.975))]


def outcome(count, k):
    return 'подтверждено' if count >= k else ('опровергнуто' if count <= NS - k else 'не показано')


col = lambda arm, k: [F[(s, arm)][k] for s in seeds]
u = lambda arm: [(x - W_FAR) / D for x in col(arm, 'wG')]
diff = lambda a, b, k='wG': [F[(s, a)][k] - F[(s, b)][k] for s in seeds]
V = {}


def interval(name, vals, lo, hi, k, **extra):
    c = sum(lo <= x <= hi for x in vals)
    V[name] = dict(kind='интервал', k=k, n=c, outcome=outcome(c, k), interval=[lo, hi], value=boot_ci(vals), **extra)


def sign(name, dvals, k, **extra):                       # счёт зёрен, где разность < 0
    c = sum(x < 0 for x in dvals)
    V[name] = dict(kind='знак', k=k, n=c, outcome=outcome(c, k), diff=boot_ci(dvals), **extra)


# основная семья
interval('P1', u('MYOPIC'), 1 - 1 / 3, 1 + 1 / 3, 9, wG=boot_ci(col('MYOPIC', 'wG')))
interval('P2', u('COUNCIL'), -1 / 3, 1 / 3, 9, wG=boot_ci(col('COUNCIL', 'wG')), b=boot_ci(col('COUNCIL', 'b')))
sign('P3', diff('COUNCIL', 'MYOPIC', 'logloss'), 9)
lo5, hi5 = 1 / 6, 5 / 6                                   # строго между точками с запасом шестой части разрыва
c5 = sum(lo5 < x < hi5 for x in u('DEMES'))
V['P5'] = dict(kind='интервал', k=8, n=c5, outcome=outcome(c5, 8), interval=[lo5, hi5], value=boot_ci(u('DEMES')),
               wG=boot_ci(col('DEMES', 'wG')))
sign('P6', diff('DEMES', 'DEMES_10x40'), 8, wG_10x40=boot_ci(col('DEMES_10x40', 'wG')))
interval('P7', u('DEMES_NOSEL'), 1 - 1 / 3, 1 + 1 / 3, 9, wG=boot_ci(col('DEMES_NOSEL', 'wG')))
sign('P9', diff('COUNCIL', 'DEMES'), 9)
sign('P10', diff('DEMES', 'DEMES_NOSEL'), 9)
sign('P11', diff('DEMES_POOLED', 'DEMES'), 9)
interval('P12', u('DEMES_POOLED'), -1 / 3, 1 / 3, 8, wG=boot_ci(col('DEMES_POOLED', 'wG')))
# разведка
sign('E1', diff('COUNCIL', 'MYOPIC', 'self_dec'), 7, self_dec_council=boot_ci(col('COUNCIL', 'self_dec')),
     self_dec_myopic=boot_ci(col('MYOPIC', 'self_dec')), self_dec_demes=boot_ci(col('DEMES', 'self_dec')))
interval('E2', u('COUNCIL_10x40'), -1 / 3, 1 / 3, 8, wG=boot_ci(col('COUNCIL_10x40', 'wG')))
sign('E3', diff('COUNCIL', 'COUNCIL_IND'), 7, wG_ind=boot_ci(col('COUNCIL_IND', 'wG')))       # COUNCIL < COUNCIL_IND
sign('E4', diff('DEMES', 'DEMES_IND'), 7, wG_ind=boot_ci(col('DEMES_IND', 'wG')))             # DEMES < DEMES_IND
# проверка построения (вне семьи): у COUNCIL_NOSEL на w_G нет отбора — блуждание
K1 = dict(logloss_gap=boot_ci(diff('COUNCIL_NOSEL', 'COUNCIL', 'logloss')), wG_sd_groups=boot_ci(col('COUNCIL_NOSEL', 'wG_sd_groups')),
          n_gap_ge_002=sum(x >= 0.02 for x in diff('COUNCIL_NOSEL', 'COUNCIL', 'logloss')))
# описательно (вне семьи): части Прайса; в стационарном окне межгрупповая ≈ − внутригрупповая (тождество)
D1 = {a: dict(within=boot_ci(col(a, 'price_within')), between=boot_ci(col(a, 'price_between')),
              total=boot_ci([F[(s, a)]['price_within'] + F[(s, a)]['price_between'] for s in seeds])) for a in E.ARMS}
# описательно (вне семьи): DEMES_NOWITHIN — снятие отбора на передаче при выражении своего веса; срыв — SD w_G между
# группами > 0,5 в среднем по окну (сухой прогон, зерно 960: 1,26 и w_G −0,64)
D2 = dict(wG=col('DEMES_NOWITHIN', 'wG'), sd_groups=col('DEMES_NOWITHIN', 'wG_sd_groups'),
          n_breakdown=sum(x > 0.5 for x in col('DEMES_NOWITHIN', 'wG_sd_groups')))
summary = None
if FULL:
    def combine(parts):
        oc = [V[p]['outcome'] for p in parts]
        return dict(parts=parts, outcome='подтверждено' if all(o == 'подтверждено' for o in oc)
                    else ('опровергнуто' if 'опровергнуто' in oc else 'не подтверждено'))
    summary = dict(S1_commitment=combine(['P2', 'P3', 'P9']), S2_multilevel=combine(['P5', 'P10']),
                   S3_mechanism=combine(['P11', 'P12']))
keys = ('wG', 'b', 'logloss', 'self_dec', 'acc', 'ece', 'wG_sd_groups', 'price_between', 'price_within')
arms_mean = {a: {k: boot_ci(col(a, k)) for k in keys} for a in E.ARMS}
out = dict(verdicts=V, summary=summary, construction_K1=K1, descriptive_D1=D1, descriptive_D2=D2, arms=arms_mean, theory=th, n_seeds=NS,
           frozen=dict(W_MY=W_MY, W_FAR=W_FAR, D=D), rows={str(s): {a: F[(s, a)] for a in E.ARMS} for s in seeds})
json.dump(out, open(os.path.join(os.path.dirname(os.path.abspath(src)), 'analysis_trust_03.json'), 'w'),
          ensure_ascii=False, indent=1, default=lambda o: o.item() if hasattr(o, 'item') else str(o))
for k, v in V.items():
    print(k, v['outcome'], f"{v['n']}/{NS} (k = {v['k']})",
          {kk: (np.round(vv, 4).tolist() if isinstance(vv, list) else vv) for kk, vv in v.items() if kk not in ('outcome', 'n', 'k', 'kind')})
print('K1 (проверка построения):', {k: (np.round(v, 4).tolist() if isinstance(v, list) else v) for k, v in K1.items()})
print('Д2 (DEMES_NOWITHIN, срывов из', NS, '):', D2['n_breakdown'], np.round(D2['wG'], 3).tolist())
print('сводные исходы:', summary)
