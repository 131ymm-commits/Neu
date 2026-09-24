# РАЗВЕДКА (post hoc, не предрегистрировано): совпадение «своего» и «мирового» уровня по ходу обучения;
# ошибка замыкания и доля VAMP-2 для ПСУ-2 на финальной модели
import sys, json
import numpy as np
sys.argv = ['x', sys.argv[1], 'none']
exec(open('eq01b_analyze.py').read().split("res = {'seed'")[0])


def feats(Xfull, logp, kind, tau=16):
    Y, pos = target(logp, tau, kind)
    X = cen(Xfull[:, pos]); Y = cen(Y)
    s, A, _, _ = cca_fit(fl(X[TR]), fl(Y[TR]))
    return X, A[:, :2], s


def cos_angles(F1, F2):
    F1 = F1 - F1.mean(0); F2 = F2 - F2.mean(0)
    Q1, _ = np.linalg.qr(F1); Q2, _ = np.linalg.qr(F2)
    return np.linalg.svd(Q1.T @ Q2, compute_uv=False)


out = {'seed': seed, 'traj': []}
for stp in [0, 250, 500, 1000, 2000, 4000, 8000]:
    p = load(stp)
    logp, r1, r2_ = model_outputs_layers(p, xin)
    X, Ao, so = feats(r2_, logp, 'own2')
    _, Aw, sw = feats(r2_, logp, 'world2')
    _, Al, sl = feats(r2_, logp, 'linear')
    c_ow = cos_angles(fl(X[TE]) @ Ao, fl(X[TE]) @ Aw)
    c_lw = cos_angles(fl(X[TE]) @ Al, fl(X[TE]) @ Aw)
    out['traj'].append(dict(step=stp, cos_own_world=c_ow.tolist(), cos_linear_world=c_lw.tolist(),
                            rho_own=so[:3].tolist(), rho_world=sw[:3].tolist()))
    print(stp, 'cos(своё, мир)', np.round(c_ow, 3), 'cos(линейное, мир)', np.round(c_lw, 3), 'ρ своё', np.round(so[:3], 3), 'ρ мир', np.round(sw[:3], 3), flush=True)
# финал: замыкание и VAMP-2
Y, pos = target(logp, 16, 'own2')
Rfull = r2_[:, 16:64] - r2_[TR][:, 16:64].mean(0, keepdims=True)
F = Rfull @ Ao
f0tr, f1tr, f0te, f1te = fl(F[TR][:, 0:32]), fl(F[TR][:, 16:48]), fl(F[TE][:, 0:32]), fl(F[TE][:, 16:48])
m0tr, m0te = fl(Rfull[TR][:, 0:32]), fl(Rfull[TE][:, 0:32])
out['closure'] = dict(level_from_level=r2(f0tr, f1tr, f0te, f1te), level_from_micro=r2(m0tr, f1tr, m0te, f1te))
out['vamp2_top2_own'] = float((so[:2] ** 2).sum() / (so ** 2).sum())
print('замыкание', out['closure'], 'VAMP-2 доля двух мод', round(out['vamp2_top2_own'], 3))
json.dump(out, open(f'eq01b_extra_s{seed}.json', 'w'), indent=1)
