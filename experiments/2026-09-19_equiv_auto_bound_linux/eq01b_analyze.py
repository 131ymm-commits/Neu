# EQUIV-01B: анализ по PREREG-EQUIV-B (ПСУ-2: цель — собственная переходная статистика модели)
import sys, glob, pickle, json, time
import numpy as np
from sklearn.cluster import KMeans
from eq01_common import *

seed = int(sys.argv[1])
mode = sys.argv[2] if len(sys.argv) > 2 else 'all'
DATA_SEED = int(sys.argv[3]) if len(sys.argv) > 3 else 54321
T0 = time.time()
rng = np.random.default_rng(DATA_SEED)
XA, HA = sample(4000, rng=rng)
xin = XA[:, :64]
POST, BEL, NLL = forward_filter(xin)
TR, TE, ALL = np.arange(2000), np.arange(2000, 4000), np.arange(4000)
E6 = np.eye(V)


def inv_sqrt(S):
    w, U = np.linalg.eigh(S)
    return (U / np.sqrt(np.maximum(w, 1e-300))) @ U.T


def cca_fit(X, Y, reg=1e-7):
    n = X.shape[0]
    Sxx = X.T @ X / n; Syy = Y.T @ Y / n; Sxy = X.T @ Y / n
    Sxx = Sxx + reg * np.trace(Sxx) / len(Sxx) * np.eye(len(Sxx))
    Syy = Syy + reg * np.trace(Syy) / len(Syy) * np.eye(len(Syy))
    Wx, Wy = inv_sqrt(Sxx), inv_sqrt(Syy)
    U, s, Vt = np.linalg.svd(Wx @ Sxy @ Wy)
    return s, Wx @ U, Wx, Wy


def null_top(X3, Y3, Wx, Wy, nperm, rng):
    ns, n = X3.shape[0], X3.shape[0] * X3.shape[1]
    Xf = X3.reshape(n, -1)
    out = []
    for _ in range(nperm):
        Yp = Y3[rng.permutation(ns)].reshape(n, -1)
        out.append(np.linalg.svd(Wx @ (Xf.T @ Yp / n) @ Wy, compute_uv=False)[0])
    return np.array(out)


def target(logp, tau, kind):
    pos = np.arange(16, 56 - tau + 1)
    if kind == 'linear':
        Y = np.concatenate([logp[:, pos + tau + j, :] for j in range(8)], -1)
    elif kind == 'own2':
        pr = np.exp(logp)
        Y = sum(np.einsum('nti,ntj->ntij', E6[xin[:, pos + tau + j]], pr[:, pos + tau + j]).reshape(len(xin), len(pos), 36)
                for j in range(8)) / 8
    elif kind == 'world2':
        Y = sum(np.einsum('nti,ntj->ntij', E6[XA[:, pos + tau + j]], E6[XA[:, pos + tau + j + 1]]).reshape(len(xin), len(pos), 36)
                for j in range(8)) / 8
    return Y, pos


def cen(A, center=True):
    mu = A[TR].mean(0, keepdims=True) if center else A[TR].mean((0, 1), keepdims=True)
    return A - mu


def r2(Ftr, Ptr, Fte, Pte):
    A = np.c_[Ftr, np.ones(len(Ftr))]
    Wt, *_ = np.linalg.lstsq(A, Ptr, rcond=None)
    pred = np.c_[Fte, np.ones(len(Fte))] @ Wt
    return float(1 - ((Pte - pred) ** 2).sum() / ((Pte - Pte.mean(0)) ** 2).sum())


fl = lambda A: A.reshape(-1, A.shape[-1])


def psu(Xfull, logp, kind, tau=16, reg=1e-7):
    Y, pos = target(logp, tau, kind)
    X = cen(Xfull[:, pos]); Y = cen(Y)
    P = POST[:, pos]
    s, A, _, _ = cca_fit(fl(X[TR]), fl(Y[TR]), reg)
    return r2(fl(X[TR]) @ A[:, :2], fl(P[TR]), fl(X[TE]) @ A[:, :2], fl(P[TE])), s


def ceiling(Xfull, tau=16):
    pos = np.arange(16, 56 - tau + 1)
    X = cen(Xfull[:, pos]); P = POST[:, pos]
    return r2(fl(X[TR]), fl(P[TR]), fl(X[TE]), fl(P[TE]))


def others(Xfull):
    pos = np.arange(16, 41)
    X = cen(Xfull[:, pos]); P = POST[:, pos]
    xtr, xte, ptr, pte = fl(X[TR]), fl(X[TE]), fl(P[TR]), fl(P[TE])
    out = {}
    w, U = np.linalg.eigh(xtr.T @ xtr)
    V2 = U[:, ::-1][:, :2]
    out['PCA'] = r2(xtr @ V2, ptr, xte @ V2, pte)
    km = KMeans(3, n_init=10, random_state=0).fit(xtr)
    oh = lambda l: np.eye(3)[l][:, :2]
    out['kmeans3'] = r2(oh(km.labels_), ptr, oh(km.predict(xte)), pte)
    R = cen(Xfull[:, 16:64])
    X1, X2 = fl(R[TR][:, :-1]), fl(R[TR][:, 1:])
    w, U = np.linalg.eigh(X1.T @ X1)
    w, U = w[::-1], U[:, ::-1]
    r = int(np.searchsorted(np.cumsum(w) / w.sum(), 0.99) + 1)
    Vr = U[:, :r]
    Ar, *_ = np.linalg.lstsq(X1 @ Vr, X2 @ Vr, rcond=None)
    lam, Wm = np.linalg.eig(Ar.T)
    order = np.argsort(-np.abs(lam)); Winv = np.linalg.inv(Wm)

    def dmd(Xa):
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
    out['DMD'] = r2(dmd(xtr), ptr, dmd(xte), pte)
    km32 = KMeans(32, n_init=4, random_state=0).fit(fl(R[TR]))
    lab = km32.labels_.reshape(len(TR), 48)
    Cm = np.bincount(lab[:, 0:32].ravel() * 32 + lab[:, 16:48].ravel(), minlength=1024).reshape(32, 32) + 1e-9
    Pt = Cm / Cm.sum(1, keepdims=True)
    Ua = np.linalg.svd(Pt)[0]
    Ub = np.linalg.svd(Pt - np.outer(np.ones(32), Cm.sum(0) / Cm.sum()))[0]
    ltr, lte = km32.predict(xtr), km32.predict(xte)
    out['SVDCE'] = max(r2(Ua[ltr, :2], ptr, Ua[lte, :2], pte), r2(Ub[ltr, :2], ptr, Ub[lte, :2], pte))
    return out


def spectrum(Xfull, logp, kind, tau, nperm, rng):
    Y, pos = target(logp, tau, kind)
    X = Xfull[:, pos]
    X = X - X.mean(0, keepdims=True); Y = Y - Y.mean(0, keepdims=True)
    s, A, Wx, Wy = cca_fit(fl(X), fl(Y))
    thr = float(np.percentile(null_top(X, Y, Wx, Wy, nperm, rng), 99))
    top = s[:10]
    return dict(tau=tau, kind=kind, rho=[round(float(v), 4) for v in top], thr=round(thr, 4), detectable=int((s > thr).sum()),
                gap_at=int(np.argmax(np.log(top[:-1] / top[1:])) + 1))


def load(step):
    return pickle.load(open(f'ckpt_s{seed}/p_{step:05d}.pkl', 'rb'))


res = {'seed': seed, 'data_seed': DATA_SEED}
prng = np.random.default_rng(seed + 99)
steps = sorted(int(f.split('_')[-1][:5]) for f in glob.glob(f'ckpt_s{seed}/p_*.pkl'))

if mode in ('all', 'final'):
    p = load(steps[-1])
    logp, r1, r2_ = model_outputs_layers(p, xin)
    Xcat = np.concatenate([r1, r2_], -1)
    f = {}
    f['ceiling'] = ceiling(r2_)
    f['PSU2'], s_own = psu(r2_, logp, 'own2')
    f['PSU_linear'], s_lin = psu(r2_, logp, 'linear')
    f['PSU2_world'], s_w = psu(r2_, logp, 'world2')
    f.update(others(r2_))
    f['rho_own'] = s_own[:4].tolist(); f['rho_world'] = s_w[:4].tolist(); f['rho_linear'] = s_lin[:4].tolist()
    # Q6
    rr = np.random.default_rng(777 + seed)
    Q1_, _ = np.linalg.qr(rr.normal(size=(D, D))); Q2_, _ = np.linalg.qr(rr.normal(size=(D, D)))
    Rm = Q1_ @ np.diag(np.logspace(0, -3, D)) @ Q2_.T
    f['PSU2_reparam'], _ = psu(r2_ @ Rm.T, logp, 'own2')
    f['PCA_reparam'] = others(r2_ @ Rm.T)['PCA']
    # Q9
    f['ceiling_cat'] = ceiling(Xcat)
    f['PSU2_cat'], _ = psu(Xcat, logp, 'own2')
    res['final'] = f
    print('final', {k: (round(v, 4) if isinstance(v, float) else v) for k, v in f.items()}, flush=True)
    # Q4, Q7
    res['spectra'] = [spectrum(r2_, logp, 'own2', tau, 200, prng) for tau in (1, 16, 24)]
    res['spectra'].append(spectrum(r2_, logp, 'world2', 16, 200, prng))
    res['spectra'].append(spectrum(r2_, logp, 'linear', 16, 200, prng))
    for sp in res['spectra']:
        print(sp, flush=True)
    json.dump(res, open(f'eq01b_final_s{seed}.json', 'w'), indent=1)

if mode in ('all', 'ckpt'):
    traj = []
    for stp in steps:
        p = load(stp)
        logp, r1, r2_ = model_outputs_layers(p, xin)
        Y, pos = target(logp, 16, 'own2')
        X = r2_[:, pos]
        X = X - X.mean(0, keepdims=True); Yc = Y - Y.mean(0, keepdims=True)
        s, A, Wx, Wy = cca_fit(fl(X), fl(Yc))
        thr = float(np.percentile(null_top(X, Yc, Wx, Wy, 50, prng), 99))
        c = ceiling(r2_)
        p2, _ = psu(r2_, logp, 'own2')
        pl, sl = psu(r2_, logp, 'linear')
        mnll = float(-np.take_along_axis(logp[:, :63], xin[:, 1:64, None], -1).mean())
        traj.append(dict(step=stp, excess=mnll - float(NLL.mean()), rho1=float(s[0]), rho2=float(s[1]), rho3=float(s[2]),
                         thr=thr, ceiling=c, psu2=p2, psu_lin=pl, rho2_lin=float(sl[1])))
        print(seed, {k: round(v, 4) for k, v in traj[-1].items()}, round(time.time() - T0), flush=True)
    res['traj'] = traj
    json.dump(res, open(f'eq01b_ckpt_s{seed}.json', 'w'), indent=1)
print('done', round(time.time() - T0), flush=True)
