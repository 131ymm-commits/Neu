# РАЗВЕДКА (post hoc): ПСУ на сообществе llama.cpp — какие «уровни специализации» сами себя предсказывают
import numpy as np, pandas as pd, re, json
from collections import Counter

recs = []
cur = None
for line in open('llama_files.txt', 'rb').read().decode('utf-8', 'replace').split('\n'):
    if line.startswith('@@\x1f'):
        f = line.split('\x1f')
        cur = dict(h=f[1], ct=int(f[2]), ae=f[3].lower(), an=f[4], files=[])
        recs.append(cur)
    elif line.strip() and cur is not None:
        cur['files'].append(line.strip())


def area(p):
    m = re.match(r'ggml/src/ggml-([a-z0-9]+)', p)
    if m:
        return 'ggml-' + m.group(1)
    if p.startswith('ggml/'):
        return 'ggml-core'
    m = re.match(r'tools/([^/]+)/', p)
    if m:
        return 'tools-' + m.group(1)
    if p.startswith('examples/'):
        return 'examples'
    if p.startswith('common/'):
        return 'common'
    if p.startswith('src/'):
        return 'src'
    if p.startswith('convert') or p.startswith('gguf-py/') or p.startswith('conversion/'):
        return 'convert'
    if p.startswith('.github/') or p.startswith('ci/') or p.startswith('cmake') or 'CMakeLists' in p or p.startswith('.devops'):
        return 'build-ci'
    if p.startswith('tests/'):
        return 'tests'
    if p.startswith('docs/') or p.endswith('.md'):
        return 'docs'
    if p.startswith('scripts/'):
        return 'scripts'
    if p.startswith('vendor/'):
        return 'vendor'
    return 'other'


rows = []
for r in recs:
    areas = sorted(set(area(p) for p in r['files']))
    for a in areas:
        rows.append((r['h'], r['ct'], r['ae'], a, 1 / len(areas)))
d = pd.DataFrame(rows, columns=['h', 'ct', 'ae', 'area', 'w'])
d['q'] = pd.to_datetime(d.ct, unit='s').dt.to_period('Q')
cnt = d.area.value_counts()
keep = cnt[cnt >= 60].index            # редкие области — в «other»
d.loc[~d.area.isin(keep), 'area'] = 'other'
areas = sorted(d.area.unique())
print(len(areas), 'областей:', areas)
A = {a: i for i, a in enumerate(areas)}


def mat(sub):
    g = sub.groupby(['ae', 'area']).w.sum().unstack(fill_value=0).reindex(columns=areas, fill_value=0)
    return g


def inv_sqrt(S):
    w, U = np.linalg.eigh(S)
    return (U / np.sqrt(np.maximum(w, 1e-12))) @ U.T


def cca(X, Y, reg=1e-3):
    X = X - X.mean(0); Y = Y - Y.mean(0); n = len(X)
    Sxx = X.T @ X / n; Syy = Y.T @ Y / n
    Sxx += reg * np.trace(Sxx) / len(Sxx) * np.eye(len(Sxx)); Syy += reg * np.trace(Syy) / len(Syy) * np.eye(len(Syy))
    Wx, Wy = inv_sqrt(Sxx), inv_sqrt(Syy)
    return Wx, Wy, X, Y


rng = np.random.default_rng(0)
out = {}
for label, q0, q1 in [('2024', '2024Q1', '2024Q4'), ('2025-26', '2025Q1', '2026Q3')]:
    qs = [q for q in sorted(d.q.unique()) if pd.Period(q0) <= q <= pd.Period(q1)]
    X, Y = [], []
    for qa, qb in zip(qs[:-1], qs[1:]):
        ma, mb = mat(d[d.q == qa]), mat(d[d.q == qb])
        both = ma.index.intersection(mb.index)
        # доли: чем автор занимался в квартале → чем займётся в следующем
        xa = ma.loc[both].values; xb = mb.loc[both].values
        X.append(xa / xa.sum(1, keepdims=True)); Y.append(xb / xb.sum(1, keepdims=True))
    X, Y = np.concatenate(X), np.concatenate(Y)
    Wx, Wy, Xc, Yc = cca(X, Y)
    s = np.linalg.svd(Wx @ (Xc.T @ Yc / len(Xc)) @ Wy, compute_uv=False)
    null = [np.linalg.svd(Wx @ (Xc.T @ Yc[rng.permutation(len(Yc))] / len(Xc)) @ Wy, compute_uv=False)[0] for _ in range(500)]
    thr = float(np.percentile(null, 99))
    det = int((s > thr).sum())
    lg = np.log(s[:det] / s[1:det + 1]) if det > 0 else np.array([0])
    out[label] = dict(pairs=len(X), rho=[round(float(v), 3) for v in s[:16]], thr=round(thr, 3), detectable=det,
                      largest_gap_after=int(np.argmax(lg) + 1))
    print(label, out[label])
json.dump(out, open('llama_psu.json', 'w'), indent=1)

# какие области несут обнаружимые моды (2025–26): корреляция канонической переменной с долями областей
qs = [q for q in sorted(d.q.unique()) if pd.Period('2025Q1') <= q <= pd.Period('2026Q3')]
X, Y = [], []
for qa, qb in zip(qs[:-1], qs[1:]):
    ma, mb = mat(d[d.q == qa]), mat(d[d.q == qb])
    both = ma.index.intersection(mb.index)
    xa = ma.loc[both].values; xb = mb.loc[both].values
    X.append(xa / xa.sum(1, keepdims=True)); Y.append(xb / xb.sum(1, keepdims=True))
X, Y = np.concatenate(X), np.concatenate(Y)
Wx, Wy, Xc, Yc = cca(X, Y)
U, s, Vt = np.linalg.svd(Wx @ (Xc.T @ Yc / len(Xc)) @ Wy)
F = Xc @ (Wx @ U)
modes = []
for i in range(11):
    c = np.array([np.corrcoef(F[:, i], Xc[:, j])[0, 1] if Xc[:, j].std() > 0 else 0 for j in range(len(areas))])
    top = np.argsort(-np.abs(c))[:2]
    modes.append((i + 1, round(float(s[i]), 3), [(areas[j], round(float(c[j]), 2)) for j in top]))
    print(modes[-1])
json.dump(modes, open('llama_psu_modes.json', 'w'))
