#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""DISTILL-01 «ДИСТИЛЛЯЦИЯ-ГОЛОВ» — разведка (PLAN.md, 1d1fcc62): поведение голов на сложении → короткие формулы от признаков входа.
Описательно; на отложенных данных — пост-хок (они уже разобраны в отчётах OCDIV-01/02). Вердиктов нет.
  python3 distill.py OUT.json --fit GLOB [GLOB ...] --hold NAME=GLOB [NAME=GLOB ...] [--t4 NAME=ANALYSIS.json]
- Признаки (только из a и b): nd_a — цифр в a; carries — число переносов; new_place — сумма длиннее a; top_carry — разряд
  старшего переноса (−1, если переносов нет); chain — длина самой длинной цепочки переносов; nines — девяток в a; ood — сумма вне
  диапазона калибровки (≥ 100·(X + 1)).
- Формула ошибки головы: логистическая, жадный отбор по BIC, не больше MAX_FEAT признаков; коэффициенты округляются до двух
  значащих цифр, и меры верности считаются по ОКРУГЛЁННОЙ формуле (её человек и читает).
- Соперники на отложенных данных: константа (доля ошибок на данных построения), «чёрный ящик» на тех же признаках (бустинг деревьев
  глубины 3), собственная уверенность головы (−logp ответа; задачи без числового ответа — вне этого сравнения).
- Виды ошибки (числовые неверные ответы): d = ответ − правда; «потеря переноса» — d = −10^k; «лишний перенос» — d = +10^k;
  «потеря разряда» — в ответе меньше цифр, чем в правде; «прочее».
- Сходство голов: φ ошибок пар фактическое против φ, которое дала бы условная независимость при формулах (ковариация p̂).
- Т4 из формулы (docs/2026-11-17_T4_formula.md): F и F₀ при условной независимости голов с вероятностями p̂ и без совпадения
  неверных ответов; против наблюдённого Т4 из analysis.json (только толпа среды)."""
import glob
import json
import math
import sys

import numpy as np

FEATS = ('nd_a', 'carries', 'new_place', 'top_carry', 'chain', 'nines', 'ood')
MAX_FEAT = 3
RIDGE = 1e-3


def short(model):
    return model.split('/')[-1]


def features(a, b, X):
    s = a + b
    carries, chain, best, top, c, pos = 0, 0, 0, -1, 0, 0
    x, y = a, b
    while x or y or c:
        t = x % 10 + y % 10 + c
        c = 1 if t >= 10 else 0
        if c:
            carries += 1
            chain += 1
            best = max(best, chain)
            top = pos
        else:
            chain = 0
        x, y, pos = x // 10, y // 10, pos + 1
    return dict(nd_a=len(str(a)), carries=carries, new_place=int(len(str(s)) > len(str(a))), top_carry=top, chain=best,
                nines=str(a).count('9'), ood=int(s >= 100 * (int(X) + 1)))


def load(globs):
    """Строки: голова, среда, признаки, правда, ответ, верность, logp."""
    rows = []
    for g in globs:
        for f in sorted(glob.glob(g)):
            h = json.load(open(f, encoding='utf-8'))
            if 'cols' not in h:
                continue
            envs = {e['name']: e for e in h.get('envs', [])}
            for name, c in h['cols'].items():
                e = envs.get(name)
                if not e:
                    continue
                for (a, b), ans, ok, lp in zip(e['keys'], c['answer'], c['correct'], c['logp']):
                    r = features(int(a), int(b), e['X'])
                    r.update(head=short(h['model']), env=name, a=int(a), b=int(b), truth=int(a) + int(b), answer=ans, err=int(not ok), logp=lp)
                    rows.append(r)
    return rows


def matrix(rows, feats):
    return np.column_stack([np.ones(len(rows))] + [np.array([r[f] for r in rows], float) for f in feats])


def sig(z):
    return 1.0 / (1.0 + np.exp(-np.clip(z, -40, 40)))


def logit_fit(X, y, ridge=RIDGE, iters=100):
    w = np.zeros(X.shape[1])
    for _ in range(iters):
        p = sig(X @ w)
        g = X.T @ (y - p) - ridge * w
        H = (X * (p * (1 - p))[:, None]).T @ X + ridge * np.eye(X.shape[1])
        step = np.linalg.solve(H, g)
        w += step
        if np.max(np.abs(step)) < 1e-9:
            break
    return w


def loglik(X, y, w):
    p = np.clip(sig(X @ w), 1e-12, 1 - 1e-12)
    return float(np.sum(y * np.log(p) + (1 - y) * np.log(1 - p)))


def round2(x):
    """Две значащие цифры."""
    if x == 0 or not np.isfinite(x):
        return 0.0
    return float(round(x, -int(math.floor(math.log10(abs(x)))) + 1))


def select(rows, y):
    """Жадный отбор признаков по BIC, не больше MAX_FEAT."""
    n, chosen = len(rows), []
    X = matrix(rows, chosen)
    w = logit_fit(X, y)
    bic = -2 * loglik(X, y, w) + X.shape[1] * math.log(n)
    path = [dict(feats=[], bic=bic)]
    while len(chosen) < MAX_FEAT:
        best = None
        for f in FEATS:
            if f in chosen or len({r[f] for r in rows}) < 2:
                continue
            Xf = matrix(rows, chosen + [f])
            wf = logit_fit(Xf, y)
            b = -2 * loglik(Xf, y, wf) + Xf.shape[1] * math.log(n)
            if best is None or b < best[0]:
                best = (b, f)
        if best is None or best[0] >= bic:
            break
        bic = best[0]
        chosen.append(best[1])
        path.append(dict(feats=list(chosen), bic=bic))
    w = logit_fit(matrix(rows, chosen), y)
    return chosen, w, path


def text_formula(feats, w):
    terms = [f"{round2(w[0]):+g}"] + [f"{round2(c):+g}·{f}" for f, c in zip(feats, w[1:])]
    return 'P(ошибка) = σ(' + ' '.join(terms) + ')'


def auc(score, y):
    """AUC через ранги (связи — средним рангом)."""
    score, y = np.asarray(score, float), np.asarray(y, int)
    pos, neg = y == 1, y == 0
    if pos.sum() == 0 or neg.sum() == 0:
        return None
    order = np.argsort(score, kind='mergesort')
    ranks = np.empty(len(score))
    s = score[order]
    i = 0
    while i < len(s):
        j = i
        while j + 1 < len(s) and s[j + 1] == s[i]:
            j += 1
        ranks[order[i:j + 1]] = (i + j) / 2 + 1
        i = j + 1
    return float((ranks[pos].sum() - pos.sum() * (pos.sum() + 1) / 2) / (pos.sum() * neg.sum()))


def mean_ll(p, y):
    p = np.clip(np.asarray(p, float), 1e-12, 1 - 1e-12)
    return float(np.mean(y * np.log(p) + (1 - y) * np.log(1 - p)))


def kind(ans, truth):
    d = ans - truth
    for k in range(1, 9):
        if d == -10 ** k:
            return 'потеря переноса'
        if d == 10 ** k:
            return 'лишний перенос'
    if len(str(abs(ans))) < len(str(truth)):
        return 'потеря разряда'
    return 'прочее'


def false_major_indep(ps):
    """P(верных ≤ 1 и хоть один неверный) при независимых головах с вероятностями ошибки ps и без совпадения неверных ответов."""
    dist = np.zeros(len(ps) + 1)                      # распределение числа верных
    dist[0] = 1.0
    for p in ps:
        q = 1 - p
        dist[1:] = dist[1:] * p + dist[:-1] * q
        dist[0] *= p
    p_all_wrong = dist[0]
    return float(dist[0] + dist[1]) if len(ps) > 1 else float(p_all_wrong)


def fit_heads(rows_fit):
    out = {}
    for h in sorted({r['head'] for r in rows_fit}):
        rs = [r for r in rows_fit if r['head'] == h]
        y = np.array([r['err'] for r in rs], float)
        feats, w, path = select(rs, y)
        wr = np.array([round2(x) for x in w])
        out[h] = dict(n=len(rs), err_rate=float(y.mean()), feats=feats, coef=[float(x) for x in w], coef_rounded=[float(x) for x in wr],
                      formula=text_formula(feats, wr), bic_path=path)
    return out


def black_box(rows_fit, head):
    try:
        from sklearn.ensemble import HistGradientBoostingClassifier
    except ImportError:                                # в сессии sklearn может не быть; на GitHub Actions он ставится заданием
        return None
    rs = [r for r in rows_fit if r['head'] == head]
    X = np.array([[r[f] for f in FEATS] for r in rs], float)
    y = np.array([r['err'] for r in rs], int)
    if len(set(y)) < 2:
        return None
    return HistGradientBoostingClassifier(max_depth=3, max_iter=200, random_state=0).fit(X, y)


def evaluate(formulas, boxes, rows):
    res = {}
    for h, fm in formulas.items():
        rs = [r for r in rows if r['head'] == h]
        if not rs:
            continue
        y = np.array([r['err'] for r in rs], float)
        p_form = sig(matrix(rs, fm['feats']) @ np.array(fm['coef_rounded']))
        p_const = np.full(len(rs), min(max(fm['err_rate'], 1e-6), 1 - 1e-6))
        p_box = boxes[h].predict_proba(np.array([[r[f] for f in FEATS] for r in rs], float))[:, 1] if boxes.get(h) else p_const
        ll_c, ll_f, ll_b = mean_ll(p_const, y), mean_ll(p_form, y), mean_ll(p_box, y)
        num = [i for i, r in enumerate(rs) if r['logp'] is not None and r['answer'] is not None]
        conf = auc([-rs[i]['logp'] for i in num], [rs[i]['err'] for i in num]) if num else None
        form_num = auc([p_form[i] for i in num], [rs[i]['err'] for i in num]) if num else None
        res[h] = dict(n=len(rs), err_rate=float(y.mean()), ll_const=ll_c, ll_formula=ll_f, ll_box=ll_b,
                      share_explained=((ll_f - ll_c) / (ll_b - ll_c) if ll_b > ll_c else None),
                      auc_formula=auc(p_form, y), auc_box=auc(p_box, y), n_numeric=len(num),
                      auc_formula_numeric=form_num, auc_confidence_numeric=conf)
    return res


def kinds_table(rows):
    out = {}
    for h in sorted({r['head'] for r in rows}):
        tab = {}
        for r in rows:
            if r['head'] != h or not r['err'] or r['answer'] is None:
                continue
            key = f"ood={r['ood']}, переносов={min(r['carries'], 3)}{'+' if r['carries'] >= 3 else ''}"
            t = tab.setdefault(key, {})
            k = kind(int(r['answer']), r['truth'])
            t[k] = t.get(k, 0) + 1
        out[h] = {k: dict(n=sum(v.values()), share={kk: vv / sum(v.values()) for kk, vv in v.items()}) for k, v in sorted(tab.items())}
    return out


def pair_phi(formulas, rows):
    """По каждой среде: φ ошибок пар фактическое и при условной независимости по формулам; среднее по парам."""
    out = {}
    for env in sorted({r['env'] for r in rows}):
        by = {}
        for r in rows:
            if r['env'] == env and r['head'] in formulas:
                by.setdefault(r['head'], {})[(r['a'], r['b'])] = r
        heads = sorted(by)
        keys = sorted(set.intersection(*[set(by[h]) for h in heads])) if heads else []
        if len(heads) < 2 or len(keys) < 50:
            continue
        E = np.array([[by[h][k]['err'] for k in keys] for h in heads], float)
        P = np.array([sig(matrix([by[h][k] for k in keys], formulas[h]['feats']) @ np.array(formulas[h]['coef_rounded'])) for h in heads])
        act, pred = [], []
        for i in range(len(heads)):
            for j in range(i + 1, len(heads)):
                si, sj = E[i].std(), E[j].std()
                if si == 0 or sj == 0:
                    continue
                act.append(float(np.corrcoef(E[i], E[j])[0, 1]))
                pred.append(float(np.cov(P[i], P[j], bias=True)[0, 1] / (si * sj)))
        if act:
            out[env] = dict(n_tasks=len(keys), n_pairs=len(act), phi_actual=float(np.mean(act)), phi_from_formulas=float(np.mean(pred)),
                            share=(float(np.mean(pred) / np.mean(act)) if np.mean(act) > 0 else None))
    return out


def t4_from_formulas(formulas, rows, analysis):
    """Т4 из формул: F = среднее P(ложное большинство | p̂(j)), F₀ = P(... | средние p̂ голов) — по толпе среды из analysis.json."""
    an = json.load(open(analysis, encoding='utf-8'))
    out = {}
    for env, e in an.get('envs', {}).items():
        crowd = [h for h in e.get('crowd', []) if h in formulas]
        by = {}
        for r in rows:
            if r['env'] == env and r['head'] in crowd and r['ood']:
                by.setdefault(r['head'], {})[(r['a'], r['b'])] = r
        if len(by) < 2:
            continue
        keys = sorted(set.intersection(*[set(v) for v in by.values()]))
        P = np.array([sig(matrix([by[h][k] for k in keys], formulas[h]['feats']) @ np.array(formulas[h]['coef_rounded'])) for h in crowd if h in by])
        F = float(np.mean([false_major_indep(P[:, j]) for j in range(P.shape[1])]))
        F0 = false_major_indep(P.mean(1))
        out[env] = dict(n_ood=len(keys), crowd=len(P), F_pred=F, F0_pred=F0, T4_pred=F - F0,
                        T4_observed=e.get('T4', {}).get('point'), F_observed=e.get('T4', {}).get('F'), F0_observed=e.get('T4', {}).get('F0'))
    return out


def main(argv):
    dst = argv[0]
    fit = argv[argv.index('--fit') + 1:argv.index('--hold')] if '--fit' in argv else []
    hold_end = argv.index('--t4') if '--t4' in argv else len(argv)
    hold = dict(x.split('=', 1) for x in argv[argv.index('--hold') + 1:hold_end]) if '--hold' in argv else {}
    t4 = dict(x.split('=', 1) for x in argv[argv.index('--t4') + 1:]) if '--t4' in argv else {}
    rows_fit = load(fit)
    formulas = fit_heads(rows_fit)
    boxes = {h: black_box(rows_fit, h) for h in formulas}
    res = dict(source='DISTILL-01, разведка (PLAN.md 1d1fcc62); описательно, отложенные данные — пост-хок', feats=list(FEATS), max_feat=MAX_FEAT,
               n_fit=len(rows_fit), formulas=formulas, fit_eval=evaluate(formulas, boxes, rows_fit), kinds_fit=kinds_table(rows_fit),
               phi_fit=pair_phi(formulas, rows_fit), hold={})
    for name, g in hold.items():
        rows = load([g])
        res['hold'][name] = dict(n=len(rows), eval=evaluate(formulas, boxes, rows), phi=pair_phi(formulas, rows),
                                 t4=(t4_from_formulas(formulas, rows, t4[name]) if name in t4 else None))
    json.dump(res, open(dst, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    for h, fm in formulas.items():
        print(h, '|', fm['formula'], '| ошибок на построении', round(fm['err_rate'], 4))
    for name, hd in res['hold'].items():
        for h, e in hd['eval'].items():
            print(f"{name} {h}: доля объяснимого {e['share_explained'] if e['share_explained'] is None else round(e['share_explained'], 3)} | "
                  f"AUC формулы {e['auc_formula'] if e['auc_formula'] is None else round(e['auc_formula'], 3)} | "
                  f"AUC уверенности {e['auc_confidence_numeric'] if e['auc_confidence_numeric'] is None else round(e['auc_confidence_numeric'], 3)}")
    return res


if __name__ == '__main__':
    main(sys.argv[1:])
