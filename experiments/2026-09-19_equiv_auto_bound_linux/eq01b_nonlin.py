# РАЗВЕДКА (post hoc): ПСУ-2 с нелинейным словарём по X (линейные координаты + индикаторы k-means)
import sys, json, numpy as np
sys.argv = ['x', sys.argv[1], 'none']
exec(open('eq01b_analyze.py').read().split("res = {'seed'")[0])
p = load(8000)
logp, r1, r2_ = model_outputs_layers(p, xin)
Y, pos = target(logp, 16, 'own2')
X = cen(r2_[:, pos]); Yc = cen(Y); P = POST[:, pos]
xtr, xte = fl(X[TR]), fl(X[TE])
res = {}
for kk in (32, 64, 128):
    km = KMeans(kk, n_init=3, random_state=0).fit(xtr)
    Htr = np.eye(kk)[km.labels_]; Hte = np.eye(kk)[km.predict(xte)]
    for name, (Ftr, Fte) in {'indicators': (Htr, Hte), 'linear+indicators': (np.c_[xtr, Htr], np.c_[xte, Hte])}.items():
        mu = Ftr.mean(0)
        s, A, _, _ = cca_fit(Ftr - mu, fl(Yc[TR]), reg=1e-6)
        res[f'{name}_{kk}'] = r2((Ftr - mu) @ A[:, :2], fl(P[TR]), (Fte - mu) @ A[:, :2], fl(P[TE]))
        # потолок того же словаря: линейный зонд со всех признаков
        res[f'ceiling_{name}_{kk}'] = r2(Ftr, fl(P[TR]), Fte, fl(P[TE]))
print(seed, {k: round(v, 3) for k, v in res.items()})
json.dump(res, open(f'eq01b_nonlin_s{seed}.json', 'w'), indent=1)
