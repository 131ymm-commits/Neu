# EQUIV-01: анализ — P1–P6 по предрегистрации (PREREG-EQUIV.md + уточнения до запуска)
import sys, glob, pickle, json, time
import numpy as np
from sklearn.cluster import KMeans
from eq01_common import *

seed = int(sys.argv[1])
mode = sys.argv[2] if len(sys.argv) > 2 else 'all'
T0 = time.time()

# ---------- отложенный набор ----------
rng = np.random.default_rng(12345)
XA, HA = sample(4000, rng=rng)
xin = XA[:, :64]
POST, BEL, NLL = forward_filter(xin)
TR = np.arange(2000)
TE = np.arange(2000, 4000)
ALL = np.arange(4000)
OPT_NLL = NLL.mean()


def inv_sqrt(S):
    w, U = np.linalg.eigh(S)
    w = np.maximum(w, 1e-300)
    return (U / np.sqrt(w)) @ U.T


def cca_fit(X, Y, reg=1e-7):
    n = X.shape[0]
    Sxx = X.T @ X / n; Syy = Y.T @ Y / n; Sxy = X.T @ Y / n
    Sxx = Sxx + reg * np.trace(Sxx) / Sxx.shape[0] * np.eye(Sxx.shape[0])
    Syy = Syy + reg * np.trace(Syy) / Syy.shape[0] * np.eye(Syy.shape[0])
    Wx = inv_sqrt(Sxx); Wy = inv_sqrt(Syy)
    U, s, Vt = np.linalg.svd(Wx @ Sxy @ Wy)
    return s, Wx @ U, Wx, Wy


def null_top(X3, Y3, Wx, Wy, nperm, rng):
    """X3: (ns, npos, dx), Y3: (ns, npos, dy); перестановка целых последовательностей."""
    ns = X3.shape[0]
    n = X3.shape[0] * X3.shape[1]
    Xf = X3.reshape(n, -1)
    tops = []
    for _ in range(nperm):
        pi = rng.permutation(ns)
        Yp = Y3[pi].reshape(n, -1)
        Sxy = Xf.T @ Yp / n
        tops.append(np.linalg.svd(Wx @ Sxy @ Wy, compute_uv=False)[0])
    return np.array(tops)


def windows(resid, logp, tau, seqs, center_from=None, center=True):
    tmax = 56 - tau
    pos = np.arange(16, tmax + 1)
    X = resid[seqs][:, pos, :].copy()
    Y = np.concatenate([logp[seqs][:, pos + tau + j, :] for j in range(8)], axis=-1)
    P = POST[seqs][:, pos, :]
    return X, Y, P, pos


def pos_center(A_tr, A_other_list, center=True):
    if center:
        mu = A_tr.mean(0, keepdims=True)
    else:
        mu = A_tr.mean((0, 1), keepdims=True)
    return [A_tr - mu] + [A - mu for A in A_other_list]


def r2(Ftr, Ptr, Fte, Pte):
    A = np.c_[Ftr, np.ones(len(Ftr))]
    Wt, *_ = np.linalg.lstsq(A, Ptr, rcond=None)
    pred = np.c_[Fte, np.ones(len(Fte))] @ Wt
    return float(1 - ((Pte - pred) ** 2).sum() / ((Pte - Pte.mean(0)) ** 2).sum())


def flat(A):
    return A.reshape(-1, A.shape[-1])


def load(step):
    with open(f'ckpt_s{seed}/p_{step:05d}.pkl', 'rb') as f:
        return pickle.load(f)


# ---------- детекторы ----------

def detectors(resid, logp, center=True, reg=1e-7, only=None):
    """Возвращает словарь R² (тест) для каждого детектора, признаки учатся на TR."""
    out = {}
    Xtr, Ytr, Ptr, pos = windows(resid, logp, 16, TR)
    Xte, Yte, Pte, _ = windows(resid, logp, 16, TE)
    Xtr, Xte = pos_center(Xtr, [Xte], center)
    Ytr, Yte = pos_center(Ytr, [Yte], center)
    xtr, xte, ptr, pte = flat(Xtr), flat(Xte), flat(Ptr), flat(Pte)
    # ПСУ
    s, A, Wx, Wy = cca_fit(xtr, flat(Ytr), reg)
    out['PSU'] = r2(xtr @ A[:, :2], ptr, xte @ A[:, :2], pte)
    out['_rho'] = s[:6].tolist()
    if only == 'PSU':
        return out
    # PCA
    C = xtr.T @ xtr / len(xtr)
    w, U = np.linalg.eigh(C)
    V2 = U[:, ::-1][:, :2]
    out['PCA'] = r2(xtr @ V2, ptr, xte @ V2, pte)
    if only == 'PSU+PCA':
        return out
    # k-means (3)
    km = KMeans(3, n_init=10, random_state=0).fit(xtr)
    oh = lambda l: np.eye(3)[l][:, :2]
    out['kmeans3'] = r2(oh(km.labels_), ptr, oh(km.predict(xte)), pte)
    # полные траектории (позиции 16..63), центрирование по позиции по TR
    Rtr = resid[TR][:, 16:64, :]
    Rte = resid[TE][:, 16:64, :]
    Rtr, Rte = pos_center(Rtr, [Rte], center)
    d = Rtr.shape[-1]
    # DMD: z_{t+1} ≈ K z_t в пространстве главных компонент (99% дисперсии)
    X1 = flat(Rtr[:, :-1]); X2 = flat(Rtr[:, 1:])
    w, U = np.linalg.eigh(X1.T @ X1)
    w, U = w[::-1], U[:, ::-1]
    r = int(np.searchsorted(np.cumsum(w) / w.sum(), 0.99) + 1)
    Vr = U[:, :r]
    Z1, Z2 = X1 @ Vr, X2 @ Vr
    Ar, *_ = np.linalg.lstsq(Z1, Z2, rcond=None)      # Z2 ≈ Z1 Ar  →  z' = Ar^T z
    lam, Wm = np.linalg.eig(Ar.T)
    order = np.argsort(-np.abs(lam))
    Winv = np.linalg.inv(Wm)

    def dmd_feats(Xa):
        b = (Winv @ (Xa @ Vr).T).T
        F = []
        for i in order:
            if len(F) >= 2:
                break
            if abs(lam[i].imag) < 1e-12:
                F.append(b[:, i].real)
            elif lam[i].imag > 0:
                F.append(b[:, i].real); F.append(b[:, i].imag)
        return np.stack(F[:2], 1)
    Xtr_a = flat(Xtr); Xte_a = flat(Xte)
    out['DMD'] = r2(dmd_feats(Xtr_a), ptr, dmd_feats(Xte_a), pte)
    out['_dmd_lams'] = [abs(complex(l)) for l in lam[order][:4]]
    out['_dmd_rank'] = r
    # SVD-причинная эмерджентность: 32 микросостояния, лаг 16
    km32 = KMeans(32, n_init=4, random_state=0).fit(flat(Rtr))
    lab = km32.labels_.reshape(Rtr.shape[0], Rtr.shape[1])
    src = lab[:, 0:32].ravel(); dst = lab[:, 16:48].ravel()
    Cm = np.bincount(src * 32 + dst, minlength=1024).reshape(32, 32).astype(float) + 1e-9
    Pt = Cm / Cm.sum(1, keepdims=True)
    Ua, sa, _ = np.linalg.svd(Pt)
    pi = Cm.sum(0) / Cm.sum()
    Ub, sb, _ = np.linalg.svd(Pt - np.outer(np.ones(32), pi))
    ltr = km32.predict(xtr); lte = km32.predict(xte)
    out['SVDCE_a'] = r2(Ua[ltr, :2], ptr, Ua[lte, :2], pte)
    out['SVDCE_b'] = r2(Ub[ltr, :2], ptr, Ub[lte, :2], pte)
    out['_svdce_sv'] = sb[:4].tolist()
    # потолок: линейный зонд из всех 64 координат
    out['probe64'] = r2(xtr, ptr, xte, pte)
    # мир как цель: CCA с истинными будущими токенами (one-hot) t+16..t+23
    Ytw = np.concatenate([np.eye(V)[xin[TR][:, pos + 16 + j]] for j in range(8)], -1)
    Ytw = Ytw - Ytw.mean((0, 1), keepdims=True)
    s_w, A_w, _, _ = cca_fit(xtr, flat(Ytw), reg)
    out['PSU_world'] = r2(xtr @ A_w[:, :2], ptr, xte @ A_w[:, :2], pte)
    return out


def spectrum_tau(resid, logp, tau, nperm, rng, seqs=ALL, center=True):
    X, Y, P, pos = windows(resid, logp, tau, seqs)
    X, = pos_center(X, [], center)
    Y, = pos_center(Y, [], center)
    s, A, Wx, Wy = cca_fit(flat(X), flat(Y))
    nt = null_top(X, Y, Wx, Wy, nperm, rng)
    thr = float(np.percentile(nt, 99))
    det = int((s > thr).sum())
    top = s[:10]
    lg = np.log(top[:-1] / top[1:])
    return dict(tau=tau, rho=[round(float(v), 4) for v in s[:10]], thr=thr, detectable=det,
                gap_at=int(np.argmax(lg) + 1), vamp2_top2=float((s[:2] ** 2).sum() / (s ** 2).sum()))


res = {'seed': seed, 'opt_nll': float(OPT_NLL)}
prng = np.random.default_rng(seed + 55)

# ---------- P5: контрольные точки ----------
if mode in ('all', 'ckpt'):
    steps = sorted(int(f.split('_')[-1][:5]) for f in glob.glob(f'ckpt_s{seed}/p_*.pkl'))
    traj = []
    for stp in steps:
        p = load(stp)
        logp, resid = model_outputs(p, xin)
        mnll = float(-np.take_along_axis(logp[:, :63], xin[:, 1:64, None], -1).mean())
        X, Y, P, pos = windows(resid, logp, 16, ALL)
        X, = pos_center(X, []); Y, = pos_center(Y, [])
        s, A, Wx, Wy = cca_fit(flat(X), flat(Y))
        thr = float(np.percentile(null_top(X, Y, Wx, Wy, 50, prng), 99))
        d = detectors(resid, logp, only='PSU+PCA')
        Xtr, _, Ptr, _ = windows(resid, logp, 16, TR); Xte, _, Pte, _ = windows(resid, logp, 16, TE)
        Xtr, Xte = pos_center(Xtr, [Xte])
        pr = r2(flat(Xtr), flat(Ptr), flat(Xte), flat(Pte))
        traj.append(dict(step=stp, nll=mnll, excess=mnll - float(NLL[:, :63].mean()), rho1=float(s[0]), rho2=float(s[1]),
                         rho3=float(s[2]), thr=thr, r2_psu=d['PSU'], r2_pca=d['PCA'], r2_probe=pr))
        print(seed, stp, {k: round(v, 4) for k, v in traj[-1].items()}, round(time.time() - T0), flush=True)
    res['traj'] = traj
    above = [t for t in traj if t['rho2'] > t['thr']]
    birth = above[0]['step'] if above else None
    r2ok = [t['step'] for t in traj if t['r2_psu'] > 0.5]
    res['P5'] = dict(birth_step=birth, first_r2_gt_05=r2ok[0] if r2ok else None,
                     passed=bool(birth is not None and r2ok and r2ok[0] - birth <= 1000 and r2ok[0] >= birth))
    json.dump(res, open(f'eq01_ckpt_s{seed}.json', 'w'), indent=1)

# ---------- финальная модель: P1–P4, P6 ----------
if mode in ('all', 'final'):
    final = sorted(int(f.split('_')[-1][:5]) for f in glob.glob(f'ckpt_s{seed}/p_*.pkl'))[-1]
    p = load(final)
    logp, resid = model_outputs(p, xin)
    res['final_step'] = final
    res['final_nll'] = float(-np.take_along_axis(logp[:, :63], xin[:, 1:64, None], -1).mean())
    res['opt_nll_63'] = float(NLL[:, :63].mean())
    base = detectors(resid, logp)
    res['R2'] = base
    print('base', base, flush=True)
    # P2: замена координат с числом обусловленности 1e3
    rr = np.random.default_rng(777 + seed)
    Q1, _ = np.linalg.qr(rr.normal(size=(D, D)))
    Q2, _ = np.linalg.qr(rr.normal(size=(D, D)))
    Rm = Q1 @ np.diag(np.logspace(0, -3, D)) @ Q2.T
    resid_r = resid @ Rm.T
    rep = detectors(resid_r, logp)
    res['R2_reparam'] = rep
    rep_ridge = detectors(resid_r, logp, reg=1e-4, only='PSU+PCA')
    base_ridge = detectors(resid, logp, reg=1e-4, only='PSU+PCA')
    res['ridge1e-4'] = dict(base=base_ridge['PSU'], reparam=rep_ridge['PSU'])
    print('reparam', rep, flush=True)
    # без центрирования по позиции (проверка устойчивости)
    res['R2_uncentered'] = detectors(resid, logp, center=False)
    # P4: шкалы
    res['tau'] = [spectrum_tau(resid, logp, tau, 200, prng) for tau in (1, 2, 4, 8, 16, 24)]
    print('tau', res['tau'], flush=True)
    # P6: объём выборки
    X, Y, P, pos = windows(resid, logp, 16, ALL)
    X, = pos_center(X, []); Y, = pos_center(Y, [])
    p6 = []
    for n in (5, 10, 20, 50, 100, 200, 400, 800, 1600, 3200):
        hits = 0; r2s = []; ths = []
        for rep_i in range(5):
            sub = prng.choice(4000, n, replace=False)
            Xs, Ys = X[sub], Y[sub]
            Xs = Xs - Xs.mean(0, keepdims=True); Ys = Ys - Ys.mean(0, keepdims=True)
            s, A, Wx, Wy = cca_fit(flat(Xs), flat(Ys))
            thr = float(np.percentile(null_top(Xs, Ys, Wx, Wy, 100 if n <= 800 else 50, prng), 99))
            hits += int(s[1] > thr); r2s.append(float(s[1])); ths.append(thr)
        p6.append(dict(n=n, hits=hits, rho2=float(np.mean(r2s)), thr=float(np.mean(ths))))
        print('P6', p6[-1], flush=True)
    res['P6'] = p6
    ok = [q['n'] for q in p6 if q['hits'] >= 4]
    res['n_star'] = ok[0] if ok else None
    # замыкание уровня (разведочно): признаки ПСУ в t → признаки ПСУ в t+16
    Xtr, Ytr, _, _ = windows(resid, logp, 16, TR)
    Xtr_c, = pos_center(Xtr, [])
    s, A, _, _ = cca_fit(flat(Xtr_c), flat(pos_center(Ytr, [])[0]))
    Rfull = resid[:, 16:64, :] - resid[TR][:, 16:64, :].mean(0, keepdims=True)
    F = Rfull @ A[:, :2]
    f0tr, f1tr = flat(F[TR][:, 0:32]), flat(F[TR][:, 16:48])
    f0te, f1te = flat(F[TE][:, 0:32]), flat(F[TE][:, 16:48])
    m0tr, m0te = flat(Rfull[TR][:, 0:32]), flat(Rfull[TE][:, 0:32])
    res['closure'] = dict(level_from_level=r2(f0tr, f1tr, f0te, f1te), level_from_micro=r2(m0tr, f1tr, m0te, f1te))
    print('closure', res['closure'], flush=True)
    json.dump(res, open(f'eq01_final_s{seed}.json', 'w'), indent=1)
print('done', round(time.time() - T0), flush=True)

if mode == 'smoke':
    last = sorted(int(f.split('_')[-1][:5]) for f in glob.glob(f'ckpt_s{seed}/p_*.pkl'))[-1]
    p = load(last)
    logp, resid = model_outputs(p, xin)
    print('step', last, 'nll', float(-np.take_along_axis(logp[:, :63], xin[:, 1:64, None], -1).mean()), 'opt', float(NLL.mean()))
    t1 = time.time()
    print(detectors(resid, logp), round(time.time() - t1, 1), 's')
    t1 = time.time()
    print(spectrum_tau(resid, logp, 16, 20, prng), round(time.time() - t1, 1), 's')
