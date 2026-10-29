#!/usr/bin/env python3
"""LENSES-2: быстрый пересчёт AUC второго рода и бутстрепа задач по гистограммам (для изучения нуля X1oc).
Семантика — как score02_lib: суждения всех задач вместе, AUC через средние ранги (ничьи — ½), single_c — по coarse_map всей выборки
этапа, края в бутстрепе не пересчитываются (или пересчитываются — refit=True, для сравнения), пересэмпл задач с возвращением.
Импорт ничего не пишет."""
import numpy as np


def hist(J, tasks, src, vals):
    """Гистограмма суждений источника по задачам: (n_tasks, V, 2) — [неверных, верных] на значение vals[v]."""
    pos = {v: i for i, v in enumerate(vals)}
    H = np.zeros((len(tasks), len(vals), 2))
    for ti, t in enumerate(tasks):
        for c, o in J[t][src]:
            H[ti, pos[c], int(o)] += 1
    return H


def auc_from_hist(H):
    """H: (..., V, 2), значения по возрастанию. AUC = P(верное > неверного) + ½ P(равны)."""
    neg, pos = H[..., 0], H[..., 1]
    cneg = np.cumsum(neg, axis=-1) - neg
    num = (pos * (cneg + 0.5 * neg)).sum(-1)
    den = pos.sum(-1) * neg.sum(-1)
    with np.errstate(invalid='ignore', divide='ignore'):
        return np.where(den > 0, num / den, np.nan)


def coarse_map(J, tasks, EPS=1e-12):
    """Копия score02_lib.coarse_map (сверяется с оригиналом в validate)."""
    import bisect
    av = [c for t in tasks for c, _ in J[t]['agree']]
    sv = sorted(c for t in tasks for c, _ in J[t]['single'])
    if not av or not sv:
        return {}, []
    lv = sorted(set(av))
    q = [sum(1 for c in av if c == v) / len(av) for v in lv]
    Q = list(np.cumsum(q))
    Q[-1] = 1.0
    N = len(sv)
    cmap = {}
    for x in sorted(set(sv)):
        lo, hi = bisect.bisect_left(sv, x), bisect.bisect_right(sv, x)
        r = (lo + (hi - lo) / 2) / N
        j = next(k for k, Qk in enumerate(Q) if r <= Qk + EPS)
        cmap[x] = lv[j]
    return cmap, lv


def prep(J, tasks):
    """Гистограммы agree, single, single_c (по карте всей выборки)."""
    av = sorted({c for t in tasks for c, _ in J[t]['agree']})
    sv = sorted({c for t in tasks for c, _ in J[t]['single']})
    cmap, lv = coarse_map(J, tasks)
    Hc = np.zeros((len(tasks), len(lv), 2))
    li = {v: i for i, v in enumerate(lv)}
    for ti, t in enumerate(tasks):
        for c, o in J[t]['single']:
            Hc[ti, li[cmap[c]], int(o)] += 1
    return dict(agree=hist(J, tasks, 'agree', av), single=hist(J, tasks, 'single', sv), single_c=Hc, sv=sv, lv=lv, cmap=cmap)


def weights(rng, n, B):
    """Пересэмпл как в score02_lib.bootstrap: B раз rng.integers(0, n, n) → число вхождений каждой задачи."""
    idx = rng.integers(0, n, size=(B, n))
    W = np.zeros((B, n))
    for b in range(B):
        W[b] = np.bincount(idx[b], minlength=n)
    return W


def boot_auc(Hs, W):
    n = Hs.shape[0]
    return auc_from_hist(np.einsum('bn,nvk->bvk', W, Hs))


def ci95(xs, EPS=1e-12):
    ys = xs[~np.isnan(xs)]
    if len(ys) == 0:
        return [np.nan, np.nan]
    lo, hi = np.quantile(ys, 0.025), np.quantile(ys, 0.975)
    return [0.0 if abs(x) < EPS else float(x) for x in (lo, hi)]


def refit_single_c(J, tasks, W):
    """Вариант для сравнения: карта огрубления пересчитывается на каждом пересэмпле (по весам задач)."""
    out = np.empty(W.shape[0])
    sv = sorted({c for t in tasks for c, _ in J[t]['single']})
    si = {v: i for i, v in enumerate(sv)}
    av = sorted({c for t in tasks for c, _ in J[t]['agree']})
    ai = {v: i for i, v in enumerate(av)}
    Hs = hist(J, tasks, 'single', sv)
    Ha = hist(J, tasks, 'agree', av)
    for b in range(W.shape[0]):
        hs = np.einsum('n,nvk->vk', W[b], Hs)   # (V, 2)
        ha = np.einsum('n,nvk->vk', W[b], Ha).sum(-1)
        cnt = hs.sum(-1)
        N = cnt.sum()
        keep = ha > 0
        lv = [v for v, k in zip(av, keep) if k]
        q = ha[keep] / ha.sum()
        Q = np.cumsum(q); Q[-1] = 1.0
        below = np.cumsum(cnt) - cnt
        r = (below + cnt / 2) / N
        j = np.searchsorted(Q, r - 1e-12, side='left')   # наименьший j: Q_j >= r − EPS, то есть r <= Q_j + EPS
        j = np.minimum(j, len(lv) - 1)
        hc = np.zeros((len(lv), 2))
        for vi in range(len(sv)):
            if cnt[vi] > 0:
                hc[j[vi]] += hs[vi]
        out[b] = auc_from_hist(hc)
    return out
