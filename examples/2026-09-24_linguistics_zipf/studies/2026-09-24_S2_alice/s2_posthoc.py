"""S2, ПОСТ-ХОК (после вердиктов, вердикты не меняет): устойчивость к выбору переводчика и точные p для ρ.
Перебираются все сочетания «по одному переводу на язык» (fr 2 × es 2 × ru 2 = 8) и пересчитываются P4–P6, P8.
Читает s2_results.json; пишет s2_posthoc.json."""
import itertools, json, os
import numpy as np
from scipy.stats import spearmanr
HERE = os.path.dirname(os.path.abspath(__file__))
R = json.load(open(os.path.join(HERE, 's2_results.json')))
PRIOR = {'fi': 1, 'ru': 6, 'cs': 8, 'de': 11, 'eo': 12, 'it': 16, 'es': 17, 'en': 19, 'fr': 20}
langs = {L: v['texts'] for L, v in R['lang'].items()}
multi = [L for L, cs in langs.items() if len(cs) > 1]

def exact_p(rho, n, side):
    # точное p по всем перестановкам (n <= 9) или Монте-Карло
    x = np.arange(n); rng = np.random.default_rng(7)
    P = np.array(list(itertools.permutations(range(n)))) if n <= 9 else np.array([rng.permutation(n) for _ in range(400000)])
    null = 1 - 6 * ((P - x) ** 2).sum(1) / (n * (n * n - 1))
    return float((null >= rho - 1e-12).mean() if side == 'ge' else (null <= rho + 1e-12).mean())

out = {'p_exact': {}}
p4 = R['P4']; p6 = R['P6']
out['p_exact']['P4'] = exact_p(p4['rho'], p4['n'], 'ge')
out['p_exact']['P6'] = exact_p(p6['rho'], p6['n'], 'le')
print(f"точное p: P4 ρ={p4['rho']:.3f}, n={p4['n']}: p={out['p_exact']['P4']:.5f};  P6 ρ={p6['rho']:.3f}, n={p6['n']}: p={out['p_exact']['P6']:.5f}")

rows = []
for combo in itertools.product(*[langs[L] for L in multi]):
    pick = {L: (dict(zip(multi, combo))[L] if L in multi else langs[L][0]) for L in langs}
    r = {L: R['r'][c] for L, c in pick.items()}
    t = {L: R['ttr_N'][c] for L, c in pick.items()}
    Ls = [L for L in r if L in PRIOR]
    rho4 = spearmanr([r[L] for L in Ls], [PRIOR[L] for L in Ls]).statistic
    rho6 = spearmanr(list(r.values()), [t[L] for L in r]).statistic
    lmax = max(r, key=r.get); lmin = min(r, key=r.get)
    d = [R['r_k'][pick[lmax]][k] - R['r_k'][pick[lmin]][k] for k in range(12)]
    row = {'выбор': {L: pick[L] for L in multi}, 'rho4': rho4, 'rho6': rho6, 'max': lmax, 'min': lmin,
           'P5': lmax in ('fr', 'en') and lmin == 'fi', 'P8_n': sum(x > 0 for x in d),
           'top3': sorted(r, key=r.get, reverse=True)[:3], 'bottom3': sorted(r, key=r.get)[:3]}
    rows.append(row)
    print(f"{row['выбор']}: ρ4={rho4:.3f} ρ6={rho6:.3f} болтливее всех {lmax}, короче всех {lmin}, P5={row['P5']}, P8 {row['P8_n']}/12; топ-3 {row['top3']}")
out['combos'] = rows
out['summary'] = {'P4_confirmed': sum(r['rho4'] >= 0.6 for r in rows), 'P5_confirmed': sum(r['P5'] for r in rows),
                  'P6_confirmed': sum(r['rho6'] <= -0.6 for r in rows), 'P8_12of12': sum(r['P8_n'] == 12 for r in rows), 'n': len(rows),
                  'max_counts': {L: sum(r['max'] == L for r in rows) for L in set(r['max'] for r in rows)},
                  'min_counts': {L: sum(r['min'] == L for r in rows) for L in set(r['min'] for r in rows)}}
print('итог по 8 сочетаниям:', out['summary'])
json.dump(out, open(os.path.join(HERE, 's2_posthoc.json'), 'w'), ensure_ascii=False, indent=1, default=float)
