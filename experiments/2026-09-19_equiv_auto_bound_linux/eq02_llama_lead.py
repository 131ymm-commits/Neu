# РАЗВЕДКА: видна ли командная структура в самоописании ДО её оформления (команды в CODEOWNERS — 2026-03-15)
exec(open('eq02_llama_psu.py').read().split("rng = np.random.default_rng(0)")[0])
rng = np.random.default_rng(1)
for q0, q1 in [('2024Q1', '2024Q4'), ('2024Q3', '2025Q2'), ('2025Q1', '2025Q4'), ('2025Q2', '2026Q1')]:
    qs = [q for q in sorted(d.q.unique()) if pd.Period(q0) <= q <= pd.Period(q1)]
    X, Y = [], []
    for qa, qb in zip(qs[:-1], qs[1:]):
        ma, mb = mat(d[d.q == qa]), mat(d[d.q == qb])
        both = ma.index.intersection(mb.index)
        xa = ma.loc[both].values; xb = mb.loc[both].values
        X.append(xa / xa.sum(1, keepdims=True)); Y.append(xb / xb.sum(1, keepdims=True))
    X, Y = np.concatenate(X), np.concatenate(Y)
    Wx, Wy, Xc, Yc = cca(X, Y)
    U, s, Vt = np.linalg.svd(Wx @ (Xc.T @ Yc / len(Xc)) @ Wy)
    null = [np.linalg.svd(Wx @ (Xc.T @ Yc[rng.permutation(len(Yc))] / len(Xc)) @ Wy, compute_uv=False)[0] for _ in range(500)]
    thr = float(np.percentile(null, 99)); det = int((s > thr).sum())
    F = Xc @ (Wx @ U)
    labs = []
    for i in range(det):
        c = np.array([np.corrcoef(F[:, i], Xc[:, j])[0, 1] if Xc[:, j].std() > 0 else 0 for j in range(len(areas))])
        labs.append(areas[int(np.argmax(np.abs(c)))])
    print(q0, '-', q1, 'пар', len(X), 'порог', round(thr, 3), 'обнаружимо', det, 'ρ', np.round(s[:det + 1], 3).tolist(), 'области:', labs)
