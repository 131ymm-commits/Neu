# TRUST-03, пилот 3: калибровка P8 (разложение Прайса) по зёрнам 970–972 → pilot/pilot_calib_price.json
import json, os
import numpy as np
from scipy.stats import norm, binom
HERE = os.path.dirname(os.path.abspath(__file__))
r = json.load(open(os.path.join(HERE, 'results_trust_03.json')))
R = {(x['seed'], x['arm']): x['final'] for x in r['runs']}
seeds = sorted({s for s, _ in R})
out = {}
for arm in ('DEMES', 'DEMES_10x40', 'DEMES_NOSEL', 'MYOPIC', 'COUNCIL', 'COUNCIL_10x40', 'COUNCIL_NOSEL'):
    w = np.array([R[(s, arm)]['price_within'] for s in seeds]); b = np.array([R[(s, arm)]['price_between'] for s in seeds])
    out[arm] = dict(within=w.tolist(), between=b.tolist(), within_mean=float(w.mean()), within_sd=float(w.std(ddof=1)),
                    between_mean=float(b.mean()), between_sd=float(b.std(ddof=1)))
d = out['DEMES']
# мощность P8: P(внутри > 0 и между < 0 на зерне) в нормальном приближении (независимость частей — допущение), затем P(≥ 9 из 10)
for mult in (1.0, 1.5):
    p = norm.cdf(d['within_mean'] / (mult * d['within_sd'])) * norm.cdf(-d['between_mean'] / (mult * d['between_sd']))
    out[f'P8_power_sd_x{mult}'] = float(1 - binom.cdf(8, 10, p)); out[f'P8_p_seed_sd_x{mult}'] = float(p)
out['P8_false_level_sign'] = float(1 - binom.cdf(8, 10, 0.5))   # нуль: знак «внутри > 0» на зерне — монета
json.dump(out, open(os.path.join(HERE, 'pilot_calib_price.json'), 'w'), ensure_ascii=False, indent=1)
print(json.dumps({k: (v if not isinstance(v, dict) else {kk: (round(vv, 6) if isinstance(vv, float) else vv) for kk, vv in v.items() if not isinstance(vv, list)}) for k, v in out.items()}, ensure_ascii=False, indent=1))
