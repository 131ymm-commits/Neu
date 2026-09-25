# AUTO-04: анализ строго по PREREG-AUTO-04.md; NLL берётся из auto/<ветвь>_s<сид>/log.json
import json
import numpy as np
from scipy.stats import binom

SEEDS = list(range(50, 70))
nll = {a: {s: {r['step']: r['nll'] for r in json.load(open(f'auto/{a}_s{s}/log.json')) if r['kind'] == 'test'} for s in SEEDS} for a in ('A0', 'AW', 'AR')}
dW = np.array([nll['A0'][s][2000] - nll['AW'][s][2000] for s in SEEDS])
dR = np.array([nll['AR'][s][2000] - nll['AW'][s][2000] for s in SEEDS])
v = lambda k: 'подтверждено' if k >= 16 else ('опровергнуто' if k <= 10 else 'разницы нет')
bs = lambda d: [float(np.percentile(np.median(np.random.default_rng(0).choice(d, (20000, len(d))), 1), q)) for q in (2.5, 97.5)]
out = dict(
    P1=dict(n_positive=int((dW > 0).sum()), verdict=v(int((dW > 0).sum())), sign_p=float(binom.sf(int((dW > 0).sum()) - 1, 20, 0.5))),
    P2=dict(n_positive=int((dR > 0).sum()), verdict=v(int((dR > 0).sum())), sign_p=float(binom.sf(int((dR > 0).sum()) - 1, 20, 0.5))),
    P3=dict(median_dW=float(np.median(dW)), ci_dW=bs(dW), median_dR=float(np.median(dR)), ci_dR=bs(dR),
            curves={a: {st: float(np.median([nll[a][s][st] for s in SEEDS])) for st in (0, 500, 1000, 1500, 2000)} for a in nll},
            A0_sd_2000=float(np.std([nll['A0'][s][2000] for s in SEEDS], ddof=1)),
            AR_minus_A0_positive=int(sum(nll['AR'][s][2000] < nll['A0'][s][2000] for s in SEEDS))),
    rows={s: {a: nll[a][s][2000] for a in nll} for s in SEEDS})
json.dump(out, open('auto04_results.json', 'w'), ensure_ascii=False, indent=1)
for s in SEEDS:
    print(s, {a: round(nll[a][s][2000], 4) for a in nll}, 'dW', round(nll['A0'][s][2000] - nll['AW'][s][2000], 4), 'dR', round(nll['AR'][s][2000] - nll['AW'][s][2000], 4))
print(json.dumps({k: w for k, w in out.items() if k != 'rows'}, ensure_ascii=False, indent=1))
