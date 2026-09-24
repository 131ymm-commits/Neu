# EQUIV-02: уровни в потоке патчей Linux (H1–H4, ёмкость k)
import numpy as np, pandas as pd, json, datetime as dt
from scipy.stats import spearmanr

raw = open('linux_sob.txt', 'rb').read().decode('utf-8', 'replace').split('\x1e')[1:]
rows = []
for r in raw:
    f = r.rstrip('\n').split('\x1f')
    if len(f) < 5:
        continue
    h, at, ae, ce, sob = f[0], int(f[1]), f[2].strip().lower(), f[3].strip().lower(), f[4].strip()
    nsob = len([s for s in sob.split('\x1d') if s.strip()]) if sob else 0
    rows.append((h, at, ae, ce, nsob))
df = pd.DataFrame(rows, columns=['h', 'at', 'ae', 'ce', 'nsob'])
_ct = []
for line in open('linux_ct.txt', 'rb').read().decode('utf-8', 'replace').split('\n'):
    f = line.split('\x1f')
    if len(f) >= 2 and f[1].isdigit():
        _ct.append((f[0], int(f[1])))
ct = pd.DataFrame(_ct, columns=['h', 'ct'])
df = df.merge(ct[['h', 'ct']], on='h', how='left')
print('commits', len(df), 'missing ct', df.ct.isna().sum())
df['ya'] = pd.to_datetime(df['at'], unit='s').dt.year
df['yc'] = pd.to_datetime(df['ct'], unit='s').dt.year
df['linus'] = df.ce.str.startswith('torvalds@')
df.to_pickle('linux_df.pkl')

years = list(range(2005, 2027))
res = {}
per = []
for y in years:
    dc = df[df.yc == y]
    da = df[df.ya == y]
    thr = dc.groupby('ce').size()
    per.append(dict(year=y, volume=len(dc), n_authors=da.ae.nunique(), n_committers=dc.ce.nunique(),
                    p90=float(np.percentile(thr, 90)), p50=float(np.percentile(thr, 50)),
                    p99=float(np.percentile(thr, 99)), max_thr=int(thr.max()),
                    linus_share=float(dc.linus.mean()), sob_mean=float(dc.nsob.mean()),
                    sob_ge3=float((dc.nsob >= 3).mean()),
                    committers_ge100=int((thr >= 100).sum()), committers_ge500=int((thr >= 500).sum())))
per = pd.DataFrame(per).set_index('year')
pd.set_option('display.width', 200)
print(per.round(3))
per.to_csv('linux_yearly.csv')

# H1
w = per.loc[2008:2025]
p90_ratio = w.p90.max() / w.p90.min()
auth_growth = per.loc[2025, 'n_authors'] / per.loc[2008, 'n_authors']
sp_cv = spearmanr(w.n_committers, w.volume).correlation
res['H1'] = dict(p90_min=w.p90.min(), p90_max=w.p90.max(), p90_ratio=p90_ratio, authors_2008=int(per.loc[2008, 'n_authors']),
                 authors_2025=int(per.loc[2025, 'n_authors']), author_growth=auth_growth, spearman_committers_volume=sp_cv,
                 passed=bool(p90_ratio <= 3 and auth_growth >= 2 and sp_cv >= 0.8), killed=bool(p90_ratio > 5))
k = float(np.median(w.p90))
res['k'] = k
# H2
res['H2'] = dict(linus_2006=per.loc[2006, 'linus_share'], linus_2025=per.loc[2025, 'linus_share'],
                 ratio=per.loc[2006, 'linus_share'] / max(per.loc[2025, 'linus_share'], 1e-9),
                 passed=bool(per.loc[2006, 'linus_share'] > 5 * per.loc[2025, 'linus_share']))
# H3
w3 = per.loc[2005:2025]
sp3 = spearmanr(w3.index, w3.sob_mean).correlation
res['H3'] = dict(spearman_year_sob=sp3, sob_2005=w3.sob_mean.iloc[0], sob_2025=w3.sob_mean.iloc[-1], passed=bool(sp3 >= 0.7))
# H4
cten = df.groupby('ce').yc.agg(['min', 'max'])
aten = df.groupby('ae').ya.agg(['min', 'max'])
ct_med = float(np.median(cten['max'] - cten['min'] + 1))
at_med = float(np.median(aten['max'] - aten['min'] + 1))
jc, ja = [], []
for y in range(2005, 2025):
    c1 = set(df.ce[df.yc == y]); c2 = set(df.ce[df.yc == y + 1])
    a1 = set(df.ae[df.ya == y]); a2 = set(df.ae[df.ya == y + 1])
    jc.append(len(c1 & c2) / len(c1 | c2)); ja.append(len(a1 & a2) / len(a1 | a2))
res['H4'] = dict(median_tenure_committers=ct_med, median_tenure_authors=at_med,
                 mean_tenure_committers=float((cten['max'] - cten['min'] + 1).mean()),
                 mean_tenure_authors=float((aten['max'] - aten['min'] + 1).mean()),
                 jaccard_committers=float(np.mean(jc)), jaccard_authors=float(np.mean(ja)),
                 n_committer_ids=len(cten), n_author_ids=len(aten),
                 passed=bool(ct_med >= 3 * at_med and np.mean(jc) >= 0.60 and np.mean(ja) <= 0.45))
# не вырожденный вариант H4 — только «существенные» коммиттеры (≥ 50 применённых патчей за всё время)
big = df.groupby('ce').size()
bigc = big[big >= 50].index
res['H4_extra'] = dict(median_tenure_committers_ge50=float(np.median((cten.loc[bigc, 'max'] - cten.loc[bigc, 'min'] + 1))),
                       n=len(bigc))
aut = df.groupby('ae').size()
biga = aut[aut >= 50].index
res['H4_extra']['median_tenure_authors_ge50'] = float(np.median((aten.loc[biga, 'max'] - aten.loc[biga, 'min'] + 1)))
res['jaccard_by_year'] = dict(committers=[round(x, 3) for x in jc], authors=[round(x, 3) for x in ja])


def conv(o):
    if isinstance(o, (np.floating, np.integer)):
        return o.item()
    if isinstance(o, np.bool_):
        return bool(o)
    raise TypeError(type(o))


print(json.dumps(res, indent=1, default=conv, ensure_ascii=False))
json.dump(res, open('eq02_results.json', 'w'), indent=1, default=conv, ensure_ascii=False)
