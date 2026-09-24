# EQUIV-02 (post hoc, не предрегистрировано): глубина патча в дереве слияний.
# depth(c) = минимальное число переходов по «второму родителю» на пути от HEAD до c (0-1 BFS).
import numpy as np, pandas as pd
from collections import deque

idx = {}
par = []
for line in open('linux_parents.txt'):
    f = line.split()
    idx[f[0]] = len(par)
    par.append(f[1:])
n = len(par)
P1 = np.full(n, -1, np.int64)
P2 = [[] for _ in range(n)]
for i, ps in enumerate(par):
    if ps:
        P1[i] = idx.get(ps[0], -1)
        P2[i] = [idx[p] for p in ps[1:] if p in idx]
del par
INF = 1 << 30
dist = np.full(n, INF, np.int64)
head = 0  # первая строка git log — HEAD
dist[head] = 0
dq = deque([head])
while dq:
    u = dq.popleft()
    du = dist[u]
    v = P1[u]
    if v >= 0 and dist[v] > du:
        dist[v] = du
        dq.appendleft(v)
    for v in P2[u]:
        if dist[v] > du + 1:
            dist[v] = du + 1
            dq.append(v)
inv = {v: k for k, v in idx.items()}
df = pd.read_pickle('linux_df.pkl')
df['depth'] = df.h.map(lambda h: dist[idx[h]] if h in idx else -1)
print('unreached', (df.depth >= INF).sum())
g = df[df.depth < INF].groupby('yc').depth.agg(['mean', 'median', lambda s: (s >= 2).mean(), lambda s: (s >= 3).mean()])
g.columns = ['mean', 'median', 'share_ge2', 'share_ge3']
print(g.round(3).to_string())
from scipy.stats import spearmanr
w = g.loc[2005:2025]
print('Spearman(year, mean depth) 2005-2025:', round(spearmanr(w.index, w['mean']).correlation, 3))
g.to_csv('linux_depth_by_year.csv')
df[['h', 'depth']].to_pickle('linux_depth.pkl')
