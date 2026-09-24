# EQUIV-02 H5 (разведочный): спектр канонических корреляций маршрутизации «автор → коммиттер» по годам
import numpy as np, pandas as pd
from scipy.sparse.csgraph import connected_components
from scipy.sparse import coo_matrix

df = pd.read_pickle('linux_df.pkl')
mg = pd.read_pickle('linux_merges.pkl')
trees = mg[mg.linus].groupby('y').tree.nunique()
rng = np.random.default_rng(0)


def ca_spectrum(a, c):
    ai, au = pd.factorize(a)
    ci, cu = pd.factorize(c)
    N = np.zeros((len(au), len(cu)))
    N = np.bincount(ai * len(cu) + ci, minlength=len(au) * len(cu)).reshape(len(au), len(cu)).astype(float)
    P = N / N.sum()
    r = P.sum(1); cc = P.sum(0)
    S = (P - np.outer(r, cc)) / np.sqrt(np.outer(r, cc))
    s = np.linalg.svd(S, compute_uv=False)
    return s, N


from scipy.sparse.linalg import svds
from scipy.sparse import csr_matrix


def ca_top(a, c):
    ai, au = pd.factorize(a)
    ci, cu = pd.factorize(c)
    N = csr_matrix((np.ones(len(ai)), (ai, ci)), shape=(len(au), len(cu)))
    n = N.sum(); r = np.asarray(N.sum(1)).ravel() / n; cc = np.asarray(N.sum(0)).ravel() / n
    # S = D_r^-1/2 P D_c^-1/2 - sqrt(r) sqrt(c)^T ; верхнее нетривиальное сингулярное число = второе у первой части
    A = csr_matrix(N / n).multiply(1 / np.sqrt(r)[:, None]).multiply(1 / np.sqrt(cc)[None, :])
    s = svds(A.tocsr(), k=3, return_singular_vectors=False)
    return np.sort(s)[::-1][1]


out = []
for y in range(2006, 2026):
    d = df[df.yc == y]
    ac = d.ae.value_counts(); cc = d.ce.value_counts()
    d = d[d.ae.isin(ac[ac >= 5].index) & d.ce.isin(cc[cc >= 5].index)]
    s, N = ca_spectrum(d.ae.values, d.ce.values)
    # нулевая модель: перестановка коммиттеров между патчами (маргиналы сохраняются)
    null = []
    for _ in range(20):
        sp = ca_top(d.ae.values, rng.permutation(d.ce.values))
        null.append(sp)
    thr = np.percentile(null, 99)
    det = int((s > thr).sum())
    # связные компоненты двудольного графа
    na, nc = N.shape
    ii, jj = np.nonzero(N)
    G = coo_matrix((np.ones(len(ii)), (ii, na + jj)), shape=(na + nc, na + nc))
    ncomp = connected_components(G, directed=False)[0]
    ss = s[:det + 1]
    lg = np.log(np.maximum(ss[:-1], 1e-12) / np.maximum(ss[1:], 1e-12))
    gap_pos = int(np.argmax(lg) + 1) if len(lg) else 0
    n_near1 = int((s > 0.99).sum()); n_09 = int((s > 0.9).sum())
    out.append(dict(year=y, authors=na, committers=nc, patches=int(N.sum()), null_thr=round(thr, 3), detectable=det,
                    rho_gt_099=n_near1, rho_gt_09=n_09, components=ncomp, largest_gap_at=gap_pos,
                    trees_linus=int(trees.get(y, 0))))
res = pd.DataFrame(out).set_index('year')
print(res.to_string())
res.to_csv('linux_h5.csv')
from scipy.stats import spearmanr
print('Spearman(gap_pos, trees)', spearmanr(res.largest_gap_at, res.trees_linus).correlation)
print('Spearman(rho>0.9, trees)', spearmanr(res.rho_gt_09, res.trees_linus).correlation)
print('Spearman(detectable, committers)', spearmanr(res.detectable, res.committers).correlation)
