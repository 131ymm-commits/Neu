# РАЗВЕДКА (post hoc, не предрегистрировано): почему линейная ПСУ не видит тему
import sys, glob, pickle, numpy as np, jax, jax.numpy as jnp
from eq01_common import *
import eq01_common as C
seed = int(sys.argv[1]); step = int(sys.argv[2])
p = pickle.load(open(f'ckpt_s{seed}/p_{step:05d}.pkl', 'rb'))
def fwd_all(p, x):
    B_, T_ = x.shape
    h = p['WE'][x] + p['WP'][:T_]
    mask = jnp.tril(jnp.ones((T_, T_), dtype=bool)); dh = D // H; outs = [h]
    for lp in p['layers']:
        z = C._ln(h, lp['ln1_g'], lp['ln1_b']); qkv = z @ lp['Wqkv']; q, k, v = jnp.split(qkv, 3, -1)
        q = q.reshape(B_, T_, H, dh).transpose(0, 2, 1, 3); k = k.reshape(B_, T_, H, dh).transpose(0, 2, 1, 3); v = v.reshape(B_, T_, H, dh).transpose(0, 2, 1, 3)
        att = jax.nn.softmax(jnp.where(mask, (q @ k.transpose(0, 1, 3, 2)) / np.sqrt(dh), -1e9), -1)
        h = h + (att @ v).transpose(0, 2, 1, 3).reshape(B_, T_, D) @ lp['Wo']; outs.append(h)
        z = C._ln(h, lp['ln2_g'], lp['ln2_b']); h = h + jax.nn.gelu(z @ lp['W1'] + lp['b1']) @ lp['W2'] + lp['b2']; outs.append(h)
    lnf = C._ln(h, p['lnf_g'], p['lnf_b'])
    return jax.nn.log_softmax(lnf @ p['WU'], -1), outs, lnf
f = jax.jit(fwd_all)
rng = np.random.default_rng(12345); XA, HA = sample(4000, rng=rng); xin = XA[:, :64]
POST, BEL, NLL = forward_filter(xin)
lps, acts = [], None
L_ = []
for i in range(0, 4000, 500):
    lp, outs, lnf = f(p, jnp.asarray(xin[i:i+500]))
    lps.append(np.asarray(lp, np.float64)); L_.append([np.asarray(o, np.float64) for o in outs] + [np.asarray(lnf, np.float64)])
logp = np.concatenate(lps)
names = ['emb', 'L1attn', 'L1', 'L2attn', 'L2(final)', 'lnf']
acts = {nm: np.concatenate([l[j] for l in L_]) for j, nm in enumerate(names)}
TR, TE = np.arange(2000), np.arange(2000, 4000); pos = np.arange(16, 41)
def cen(A): mu = A[TR].mean(0, keepdims=True); return A - mu
def r2(Ftr, Ptr, Fte, Pte):
    A = np.c_[Ftr, np.ones(len(Ftr))]; Wt, *_ = np.linalg.lstsq(A, Ptr, rcond=None)
    pred = np.c_[Fte, np.ones(len(Fte))] @ Wt; return 1 - ((Pte - pred) ** 2).sum() / ((Pte - Pte.mean(0)) ** 2).sum()
def inv_sqrt(S):
    w, U = np.linalg.eigh(S); w = np.maximum(w, 1e-300); return (U / np.sqrt(w)) @ U.T
def cca(X, Y, reg=1e-7):
    n = len(X); Sxx = X.T @ X / n; Syy = Y.T @ Y / n; Sxy = X.T @ Y / n
    Sxx += reg * np.trace(Sxx) / len(Sxx) * np.eye(len(Sxx)); Syy += reg * np.trace(Syy) / len(Syy) * np.eye(len(Syy))
    Wx = inv_sqrt(Sxx); U, s, Vt = np.linalg.svd(Wx @ Sxy @ inv_sqrt(Syy)); return s, Wx @ U
fl = lambda A: A.reshape(-1, A.shape[-1])
P = POST[:, pos]; ptr, pte = fl(P[TR]), fl(P[TE])
BELp = BEL[:, pos]
print('== линейный зонд темы (R², тест) и совместной веры 9-мерной ==')
for nm in names:
    X = cen(acts[nm][:, pos]); print(nm, round(r2(fl(X[TR]), ptr, fl(X[TE]), pte), 3), 'belief9', round(r2(fl(X[TR]), fl(BELp[TR]), fl(X[TE]), fl(BELp[TE])), 3))
Xcat = cen(np.concatenate([acts['L1'][:, pos], acts['L2(final)'][:, pos]], -1))
print('concat L1+L2', round(r2(fl(Xcat[TR]), ptr, fl(Xcat[TE]), pte), 3))
# цели
Ylin = np.concatenate([logp[:, pos + 16 + j] for j in range(8)], -1)
pr = np.exp(logp)
Ybig = sum(np.einsum('nti,ntj->ntij', np.eye(6)[xin[:, pos + 16 + j]], pr[:, pos + 16 + j]).reshape(4000, len(pos), 36) for j in range(8)) / 8
Ytrue = sum(np.einsum('nti,ntj->ntij', np.eye(6)[xin[:, pos + 16 + j]], np.eye(6)[XA[:, pos + 17 + j]]).reshape(4000, len(pos), 36) for j in range(8)) / 8
for Xn, Xa in [('L2(final)', acts['L2(final)'][:, pos]), ('L1', acts['L1'][:, pos]), ('concat', np.concatenate([acts['L1'][:, pos], acts['L2(final)'][:, pos]], -1))]:
    X = cen(Xa)
    for Yn, Ya in [('linear outputs', Ylin), ('own bigram (token⊗own prediction)', Ybig), ('true bigrams', Ytrue)]:
        Y = cen(Ya)
        s, A = cca(fl(X[TR]), fl(Y[TR]))
        print(f'X={Xn:10s} Y={Yn:36s} rho={np.round(s[:4],3)} R2(2 feats)={r2(fl(X[TR]) @ A[:, :2], ptr, fl(X[TE]) @ A[:, :2], pte):.3f}')
