#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""DISTILL-02 «ПРОГРАММА-ГОЛОВЫ» (HYPOTHESIS.md, 394b7be2): дистилляция ответа головы на сложении в короткую программу.

Программа головы h (на семейство сред):
  ответ = a + b − Σ_j 10^j · D_j по разрядам j, куда есть перенос (D_j = 1 — перенос в разряд j потерян);
  P(D_j = 1) = σ(w · x_j), x_j — не больше 3 признаков входа (жадно по BIC), коэффициенты — две значащие цифры;
  «прочие» ошибки — доля ε головы; их смещения — по частотам головы на построении (самые частые TOP_OFFSETS, как у B1), остаток —
  равномерно по справочному множеству V (`ref_size`). Так сравнение с B1 меряет только вклад переносов во входе.
Соперники (те же данные построения, те же числовые ответы):
  B0 — «верно с частотой головы, иначе любое число из V»;
  B1 — «частоты смещений»: самые частые смещения головы на построении независимо от входа (`offset_model`);
  ящик — бустинг деревьев на признаках задачи, предсказывает класс исхода (верно, набор потерянных переносов, прочее).
Меры: средняя лог-вероятность ответа головы (на числовой ответ), доля неверных ответов в трёх самых вероятных неверных,
совпадение ошибок голов (F, K) из программ, независимых при данном входе, против наблюдённого, и оценщик P(верно) против
уверенности головы (AUC; описательно).
Правда — только от кода: сумма и переносы считаются из a и b; ответы голов читаются из сборок OCDIV-03/04."""
import itertools
import json
import math
import os
import sys
import time

import numpy as np

X_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(X_DIR))
sys.path.insert(0, os.path.join(ROOT, 'experiments', '2026-11-18_OCDIV-04'))
import ocdiv4 as C4  # noqa: E402   сборка OCDIV-04 (merge4), через него — ocdiv3 (O3), ocdiv2 (W), S
W, S = C4.W, C4.S
NC = W.NONE_CODE
FEATURES = ('pos', 'top', 'newplace', 'prop', 'chain', 'c1', 'nines', 'ood', 'phi')
PHI_BASE = ('phi',)              # база Wen и др. (arXiv 2606.03645): потенциал переноса Φ_j, только потеря переноса
MAX_FEATURES = 3
TOP_OFFSETS = 30                    # B1: столько самых частых смещений головы на построении
TOPK_WRONG = 3                      # «назван точно» — среди трёх самых вероятных неверных ответов
BOX_MIN_CLASS = 5                   # ящик: набор потерянных переносов — класс, если встретился не меньше 5 раз на построении
SEED = 9_910_000


# ───────────── строение задачи (только слагаемые)
def carry_info(a, b):
    """Переносы столбикового сложения: список (j, порождён ли перенос в разряде j − 1) для каждого разряда j, куда есть перенос
    (j = 1 — перенос в десятки). «Порождён» — сумма цифр разряда j − 1 без входящего переноса не меньше 10; иначе перенос
    протянут (9 + входящий перенос)."""
    out, c, k = [], 0, 0
    while a // 10 ** k > 0 or b // 10 ** k > 0 or c:
        da, db = (a // 10 ** k) % 10, (b // 10 ** k) % 10
        s = da + db + c
        gen = da + db >= 10
        c = 1 if s >= 10 else 0
        if c:
            out.append((k + 1, gen))
        k += 1
    return out


def chains(cpos):
    """Длина непрерывной цепочки переносов, в которую входит каждый разряд."""
    out, run = {}, []
    for j in sorted(cpos) + [None]:
        if run and (j is None or j != run[-1] + 1):
            for x in run:
                out[x] = len(run)
            run = []
        if j is not None:
            run.append(j)
    return out


def carry_potential(a, b, j):
    """Φ_j = Σ_{i=1..j} r_{j−i} / 10^i, r_k = a_k + b_k — сумма цифр разряда k без переноса (Wen и др., формула 3); перенос в разряд
    j равен ⌊Φ_j⌋."""
    return sum(((a // 10 ** (j - i)) % 10 + (b // 10 ** (j - i)) % 10) / 10 ** i for i in range(1, j + 1))


def position_features(a, b, ood):
    """Признаки (x_j) каждого разряда j с переносом; только из входа. phi = Φ_j − 1 — запас переноса (0 — на самой границе)."""
    ci = carry_info(a, b)
    cpos = [j for j, _ in ci]
    if not cpos:
        return []
    ch = chains(cpos)
    top = max(cpos)
    c1 = int(1 in cpos)
    nines = str(a).count('9')
    return [dict(j=j, pos=float(j), top=float(j == top), newplace=float(a < 10 ** j and b < 10 ** j), prop=float(not gen),
                 chain=float(ch[j]), c1=float(c1), nines=float(nines), ood=float(ood), phi=carry_potential(a, b, j) - 1.0)
            for j, gen in ci]


def lost_set(offset, cpos):
    """Смещение ответа → набор потерянных переносов (кортеж разрядов) или None («прочее»). 0 → () — ответ верный."""
    if offset == 0:
        return ()
    if offset > 0 or offset >= NC:
        return None
    s, j, D = -offset, 0, []
    while s:
        d = s % 10
        if d > 1:
            return None
        if d == 1:
            D.append(j)
        s //= 10
        j += 1
    return tuple(D) if set(D) <= set(cpos) else None


def ref_size(total):
    """|V|: справочное множество — целые с числом цифр от n − 2 до n + 1, n — цифр в верной сумме (одно на всех соперников)."""
    n = len(str(total))
    return 10 ** (n + 1) - 10 ** max(n - 3, 0)


# ───────────── логистическая формула с отбором признаков по BIC
def logit_fit(X, y, ridge=1e-6, iters=100):
    X1 = np.column_stack([np.ones(len(y)), X]) if X.size else np.ones((len(y), 1))
    w = np.zeros(X1.shape[1])
    for _ in range(iters):
        z = np.clip(X1 @ w, -30, 30)
        p = 1 / (1 + np.exp(-z))
        g = X1.T @ (y - p) - ridge * w
        H = (X1 * (p * (1 - p))[:, None]).T @ X1 + ridge * np.eye(X1.shape[1])
        step = np.linalg.solve(H, g)
        w += step
        if np.max(np.abs(step)) < 1e-9:
            break
    z = np.clip(X1 @ w, -30, 30)
    p = 1 / (1 + np.exp(-z))
    ll = float(np.sum(y * np.log(np.clip(p, 1e-12, 1)) + (1 - y) * np.log(np.clip(1 - p, 1e-12, 1))))
    return w, ll


def sig2(x):
    """Две значащие цифры (мерило «осознаваемости», как в DISTILL-01)."""
    return float(f'{x:.2g}') if x != 0 else 0.0


def fixed_formula(rows, y, feats):
    """Формула с заданными признаками (база Φ): без отбора."""
    Xc = np.array([[r[c] for c in feats] for r in rows], float)
    w, ll = logit_fit(Xc, y)
    return dict(features=list(feats), w=[float(x) for x in w], w_round=[sig2(float(x)) for x in w], ll=ll,
                bic=-2 * ll + (len(feats) + 1) * math.log(max(len(y), 2)), n=len(y))


def select_formula(rows, y):
    """Жадно по BIC: от свободного члена добавляется признак, сильнее всех снижающий BIC, пока снижает и пока признаков ≤ 3."""
    n = len(y)
    chosen, (w, ll) = [], logit_fit(np.zeros((n, 0)), y)
    bic = -2 * ll + 1 * math.log(max(n, 2))
    while len(chosen) < MAX_FEATURES:
        best = None
        for f in FEATURES:
            if f in chosen:
                continue
            cols = chosen + [f]
            Xc = np.array([[r[c] for c in cols] for r in rows], float)
            if np.all(Xc[:, -1] == Xc[0, -1]):
                continue                                      # признак постоянен на данных построения
            w2, ll2 = logit_fit(Xc, y)
            b2 = -2 * ll2 + (len(cols) + 1) * math.log(max(n, 2))
            if best is None or b2 < best[0]:
                best = (b2, f, w2, ll2)
        if best is None or best[0] >= bic:
            break
        bic, f, w, ll = best
        chosen.append(f)
    return dict(features=chosen, w=[float(x) for x in w], w_round=[sig2(float(x)) for x in w], ll=ll, bic=bic, n=n)


# ───────────── данные: смещения головы на задачах среды
def env_table(env, heads=None, with_logp=False):
    """Задачи среды и ответы голов: список задач (a, b, сумма, ood) и словарь «голова → массив смещений» (NONE_CODE — без числа)."""
    probs = env['problems']
    sums = [p['sum'] for p in probs]
    out, lp = {}, {}
    for h in env['heads']:
        if heads is not None and h['model'] not in heads:
            continue
        ans = [r['answer'] for r in h['rows']]
        out[h['model']] = W.dmat([ans], sums, list(range(len(probs))))[:, 0]
        lp[h['model']] = np.array([np.nan if r.get('logp') is None else float(r['logp']) for r in h['rows']])
    items = [dict(a=int(p['a']), b=int(p['b']), sum=int(p['sum']), ood=int(p['range'] != 'ID')) for p in probs]
    assert all(it['sum'] == it['a'] + it['b'] for it in items), 'правда не сошлась'          # второй способ правды
    return (items, out, lp) if with_logp else (items, out)


def fit_program(items, offsets, fixed=None):
    """Программа одной головы по задачам построения (числовые ответы): ε — доля «прочих»; формула P(D_j) — по задачам в опоре программы."""
    rows, y, n_num, n_other, other = [], [], 0, 0, {}
    for it, d in zip(items, offsets):
        if d >= NC:
            continue
        n_num += 1
        pf = position_features(it['a'], it['b'], it['ood'])
        D = lost_set(int(d), [r['j'] for r in pf])
        if D is None:
            n_other += 1
            other[int(d)] = other.get(int(d), 0) + 1
            continue
        for r in pf:
            rows.append(r)
            y.append(1.0 if r['j'] in D else 0.0)
    eps = n_other / n_num if n_num else float('nan')
    top = sorted(other.items(), key=lambda kv: -kv[1])[:TOP_OFFSETS]
    q = {int(dd): c / n_other for dd, c in top} if n_other else {}
    q_rest = 1 - sum(q.values()) if n_other else 1.0
    if not rows:
        form = dict(features=[], w=[0.0], w_round=[0.0], ll=0.0, bic=0.0, n=0)
    else:
        form = fixed_formula(rows, np.array(y), fixed) if fixed else select_formula(rows, np.array(y))
    return dict(eps=eps, n_numeric=n_num, n_other=n_other, n_rows=len(y), q=q, q_rest=q_rest, **form)


def p_drop(prog, r, rounded=True):
    w = prog['w_round'] if rounded else prog['w']
    z = w[0] + sum(wi * r[f] for wi, f in zip(w[1:], prog['features']))
    return 1 / (1 + math.exp(-max(-30, min(30, z))))


def program_dist(prog, it, rounded=True):
    """Распределение ответа программы на задаче: {ответ: вероятность} для опоры программы и масса «прочего» ε (на |V| чисел)."""
    pf = position_features(it['a'], it['b'], it['ood'])
    ps = [(r['j'], p_drop(prog, r, rounded)) for r in pf]
    dist = {}
    for mask in itertools.product((0, 1), repeat=len(ps)):
        pr, off = 1 - prog['eps'], 0
        for (j, p), m in zip(ps, mask):
            pr *= p if m else (1 - p)
            off += 10 ** j if m else 0
        dist[it['sum'] - off] = dist.get(it['sum'] - off, 0.0) + pr
    return dist


def other_valid(prog, it, support):
    """«Прочие» смещения головы (частоты на построении, как у B1), допустимые на задаче: ответ ≥ 0 и не из опоры программы."""
    v = {d: qq for d, qq in prog.get('q', {}).items() if it['sum'] + d >= 0 and (it['sum'] + d) not in support}
    return v, sum(v.values()) + prog.get('q_rest', 1.0)


def other_prob(prog, it, y, support):
    """P(«прочий» ответ y) = ε · Q(смещение) по частотам головы; остаток Q — равномерно по |V|."""
    v, tot = other_valid(prog, it, support)
    d = y - it['sum']
    if tot <= 0:
        return prog['eps'] / ref_size(it['sum'])
    return prog['eps'] * (v[d] / tot if d in v else (prog.get('q_rest', 1.0) / tot) / ref_size(it['sum']))


def answer_prob(prog, it, y, rounded=True, dist=None):
    dist = program_dist(prog, it, rounded) if dist is None else dist
    return dist[y] if y in dist else other_prob(prog, it, y, dist)


def offset_model(items, offsets):
    """B1: частоты смещений головы на построении (числовые ответы), самые частые TOP_OFFSETS; остальная масса — на |V|."""
    vals = [int(d) for d in offsets if d < NC]
    cnt = {}
    for d in vals:
        cnt[d] = cnt.get(d, 0) + 1
    top = sorted(cnt.items(), key=lambda kv: -kv[1])[:TOP_OFFSETS]
    n = len(vals)
    return dict(p={int(d): c / n for d, c in top}, rest=1 - sum(c for _, c in top) / n if n else 1.0, acc=cnt.get(0, 0) / n if n else float('nan'))


def b1_prob(om, it, y):
    """B1 на задаче: смещения, дающие отрицательный ответ, отбрасываются, остальное нормируется на задаче."""
    valid = {d: p for d, p in om['p'].items() if it['sum'] + d >= 0}
    tot = sum(valid.values()) + om['rest']
    d = y - it['sum']
    return (valid[d] / tot) if d in valid else (om['rest'] / tot) / ref_size(it['sum'])


def b0_prob(acc, it, y):
    return acc if y == it['sum'] else (1 - acc) / ref_size(it['sum'])


# ───────────── ящик: бустинг на признаках задачи (верхняя граница того, что признаки объясняют)
def item_vector(it, max_pos=8):
    pf = {r['j']: r for r in position_features(it['a'], it['b'], it['ood'])}
    v = []
    for j in range(1, max_pos + 1):
        r = pf.get(j)
        v += [1.0 if r else 0.0, r['prop'] if r else 0.0, r['chain'] if r else 0.0, r['top'] if r else 0.0, r['newplace'] if r else 0.0]
    v += [float(str(it['a']).count('9')), float(it['ood']), float(len(str(it['a']))), float(len(str(it['sum'])))]
    return v


def box_fit(items, offsets, seed=SEED):
    from sklearn.ensemble import HistGradientBoostingClassifier
    X, cls = [], []
    for it, d in zip(items, offsets):
        if d >= NC:
            continue
        D = lost_set(int(d), [r['j'] for r in position_features(it['a'], it['b'], it['ood'])])
        X.append(item_vector(it))
        cls.append('other' if D is None else ','.join(map(str, D)))
    counts = {c: cls.count(c) for c in set(cls)}
    cls = [c if (c == 'other' or counts[c] >= BOX_MIN_CLASS) else 'other' for c in cls]
    if len(set(cls)) < 2:
        return dict(model=None, single=cls[0] if cls else 'other')
    m = HistGradientBoostingClassifier(max_depth=3, max_iter=200, learning_rate=0.05, random_state=seed)
    m.fit(np.array(X), np.array(cls))
    return dict(model=m, single=None)


def box_classes(box, items):
    """Вероятности классов ящика для всех задач сразу (один вызов predict_proba)."""
    if box is None:
        return None
    if box['model'] is None:
        return [{box['single']: 1.0} for _ in items]
    P = box['model'].predict_proba(np.array([item_vector(it) for it in items]))
    return [dict(zip(box['model'].classes_, row)) for row in P]


def box_prob(box, it, y, prog, pr=None):
    D = lost_set(y - it['sum'], [r['j'] for r in position_features(it['a'], it['b'], it['ood'])])
    key = 'other' if D is None else ','.join(map(str, D))
    if pr is None:
        pr = box_classes(box, [it])[0]
    if key in pr and key != 'other':
        return max(pr[key], 1e-12)
    po = max(pr.get('other', 0.0), 1e-12)
    pe = dict(prog, eps=1.0)                                       # доля «прочего» — у ящика своя, распределение смещений — головы
    sup = program_dist(dict(prog, eps=0.0), it)
    return po * other_prob(pe, it, y, sup)


# ───────────── меры на задачах проверки
def head_scores(prog, om, box, items, offsets, rounded=True, logp=None, phi=None):
    """Средняя лог-вероятность ответа (на числовой ответ) у программы, B0, B1, ящика; доля неверных ответов в трёх самых вероятных
    неверных у программы и у B1; P(верно) программы для оценщика."""
    ll = dict(prog=[], b0=[], b1=[], box=[], phi=[])
    hit_p, hit_b1, n_wrong = 0, 0, 0
    b1_top = [d for d, _ in sorted(om['p'].items(), key=lambda kv: -kv[1]) if d != 0]
    pc, corr, conf = [], [], []
    bx = box_classes(box, items)
    for i, (it, d) in enumerate(zip(items, offsets)):
        if d >= NC:
            continue
        conf.append(float(logp[i]) if logp is not None else np.nan)
        y = it['sum'] + int(d)
        dist = program_dist(prog, it, rounded)
        p_prog = answer_prob(prog, it, y, rounded, dist)
        ll['prog'].append(math.log(max(p_prog, 1e-300)))
        ll['b0'].append(math.log(max(b0_prob(om['acc'], it, y), 1e-300)))
        ll['b1'].append(math.log(max(b1_prob(om, it, y), 1e-300)))
        if box is not None:
            ll['box'].append(math.log(max(box_prob(box, it, y, prog, bx[i]), 1e-300)))
        if phi is not None:
            ll['phi'].append(math.log(max(answer_prob(phi, it, y, rounded), 1e-300)))
        pc.append(dist.get(it['sum'], 0.0))
        corr.append(int(d == 0))
        if d != 0:
            n_wrong += 1
            v, tot = other_valid(prog, it, dist)
            cands = [(p, a) for a, p in dist.items() if a != it['sum']]
            cands += [(prog['eps'] * qq / tot, it['sum'] + dd) for dd, qq in v.items()] if tot > 0 else []
            wrong = sorted(cands, reverse=True)[:TOPK_WRONG]
            hit_p += int(any(a == y for _, a in wrong))
            cand = [x for x in b1_top if it['sum'] + x >= 0][:TOPK_WRONG]
            hit_b1 += int(int(d) in cand)
    out = {k: (float(np.mean(v)) if v else float('nan')) for k, v in ll.items()}
    out.update(n_numeric=len(ll['prog']), n_wrong=n_wrong, hit_prog=hit_p / n_wrong if n_wrong else float('nan'),
               hit_b1=hit_b1 / n_wrong if n_wrong else float('nan'), auc_prog=auc(pc, corr),
               auc_conf=auc([c for c in conf], corr) if logp is not None and np.all(np.isfinite(conf)) else float('nan'))
    out['_ll'] = {k: v for k, v in ll.items()}
    return out


def auc(score, label):
    s, l_ = np.asarray(score, float), np.asarray(label, int)
    pos, neg = s[l_ == 1], s[l_ == 0]
    if not len(pos) or not len(neg):
        return float('nan')
    allv = np.concatenate([pos, neg])
    order = allv.argsort()
    ranks = np.empty(len(allv))
    ranks[order] = np.arange(1, len(allv) + 1)
    for v in np.unique(allv):                                      # средние ранги при равенстве
        m = allv == v
        ranks[m] = ranks[m].mean()
    return float((ranks[:len(pos)].sum() - len(pos) * (len(pos) + 1) / 2) / (len(pos) * len(neg)))


# ───────────── совпадение ошибок голов: наблюдённое против программ, независимых при данном входе
def coincidence_stats(D):
    """D: задачи × головы, смещения (NONE_CODE — без числа). F — ложное большинство (`ocdiv2.false_major`); K — среднее по парам
    доли одинаковых смещений среди задач, где обе головы дали неверное числовое смещение."""
    F = float(W.false_major(D).mean())
    ks = []
    for i, j in itertools.combinations(range(D.shape[1]), 2):
        both = (D[:, i] != 0) & (D[:, j] != 0) & (D[:, i] < NC) & (D[:, j] < NC)
        if both.sum():
            ks.append(float((D[both, i] == D[both, j]).mean()))
    return F, (float(np.mean(ks)) if ks else float('nan'))


def sample_program(prog, it, rng, rounded=True):
    """Один ответ программы (смещение): опора по вероятностям, «прочее» — случайное число из V, не совпадающее с опорой."""
    dist = program_dist(prog, it, rounded)
    u = rng.random()
    acc = 0.0
    for y, p in dist.items():
        acc += p
        if u < acc:
            return y - it['sum']
    v, tot = other_valid(prog, it, dist)
    u2 = rng.random() * tot
    acc = 0.0
    for dd, qq in v.items():
        acc += qq
        if u2 < acc:
            return dd
    n = len(str(it['sum']))
    while True:
        y = int(rng.integers(10 ** max(n - 3, 0), 10 ** (n + 1)))
        if y not in dist:
            return y - it['sum']


def sampler(prog, it, rounded=True):
    """Таблица выборки ответа программы на задаче (смещения и накопленные вероятности; «прочее» по частотам головы, остаток — число
    из V). Строится один раз на голову и задачу."""
    dist = program_dist(prog, it, rounded)
    offs = [y - it['sum'] for y in dist]
    pr = list(dist.values())
    v, tot = other_valid(prog, it, dist)
    if tot > 0:
        offs += list(v.keys())
        pr += [prog['eps'] * qq / tot for qq in v.values()]
    return np.array(offs, np.int64), np.cumsum(pr), set(dist)


def draw(tab, it, rng):
    offs, cum, sup = tab
    u = rng.random()
    i = int(np.searchsorted(cum, u, side='right'))
    if i < len(offs):
        return int(offs[i])
    n = len(str(it['sum']))
    while True:                                                    # остаток «прочего» — случайное число из V вне опоры
        y = int(rng.integers(10 ** max(n - 3, 0), 10 ** (n + 1)))
        if y not in sup:
            return y - it['sum']


def coincidence_env(progs, items, D_obs, R, rng, rounded=True):
    """Наблюдённые F, K против среднего по R выборкам программ (без числа — на тех же местах, что у голов)."""
    F_obs, K_obs = coincidence_stats(D_obs)
    tabs = [[sampler(prog, it, rounded) if D_obs[i, k] < NC else None for i, it in enumerate(items)] for k, prog in enumerate(progs)]
    Fs, Ks = [], []
    for _ in range(R):
        Dp = D_obs.copy()
        for k in range(len(progs)):
            for i, it in enumerate(items):
                if tabs[k][i] is not None:
                    Dp[i, k] = draw(tabs[k][i], it, rng)
        f, kk = coincidence_stats(Dp)
        Fs.append(f)
        Ks.append(kk)
    return dict(F_obs=F_obs, K_obs=K_obs, F_prog=float(np.mean(Fs)), K_prog=float(np.nanmean(Ks)),
                F_ratio=F_obs / np.mean(Fs) if np.mean(Fs) > 0 else float('nan'),
                K_ratio=K_obs / np.nanmean(Ks) if np.nanmean(Ks) > 0 else float('nan'))


# ───────────── сборка данных и пилот
def load_merged(mdir):
    d, envs = S.load_new(mdir)
    return envs


def family_data(env_dicts):
    """Пул задач и смещений по головам из нескольких сред (одного семейства)."""
    items, offs = [], {}
    for env in env_dicts:
        it, o = env_table(env)
        items += it
        for h, v in o.items():
            offs.setdefault(h, []).append(v)
    n = len(items)
    offs = {h: np.concatenate(v) for h, v in offs.items() if sum(len(x) for x in v) == n}   # голова со всеми средами
    return items, offs


def fit_family(env_dicts, with_box=True):
    items, offs = family_data(env_dicts)
    out = {}
    for h, o in offs.items():
        out[h] = dict(prog=fit_program(items, o), phi=fit_program(items, o, fixed=PHI_BASE), om=offset_model(items, o),
                      box=box_fit(items, o) if with_box else None)
    return out


def eval_envs(fits, envs, R, seed, rounded=True):
    """По средам {имя: среда}: меры голов и совпадение (головы с программой; без отбора по проверке метода, описательно)."""
    rng = np.random.default_rng(seed)
    res = {}
    for name, env in envs.items():
        items, offs, lps = env_table(env, with_logp=True)
        hs = [h for h in offs if h in fits]
        heads = {}
        for h in hs:
            f = fits[h]
            sc = head_scores(f['prog'], f['om'], f['box'], items, offs[h], rounded, logp=lps[h], phi=f['phi'])
            sc.pop('_ll')
            heads[h] = sc
        D = np.column_stack([offs[h] for h in hs]) if hs else np.zeros((len(items), 0), int)
        co = coincidence_env([fits[h]['prog'] for h in hs], items, D, R, rng, rounded) if len(hs) >= 2 else None
        res[name] = dict(n=len(items), heads=heads, coincidence=co)
    return res


def summarize(res):
    """Средние по средам и головам: разности лог-вероятностей программы и соперников; доля объяснимого; совпадение."""
    rows = [(e, h, s) for e, r in res.items() for h, s in r['heads'].items() if s['n_numeric']]
    d_b1 = [s['prog'] - s['b1'] for _, _, s in rows]
    d_b0 = [s['prog'] - s['b0'] for _, _, s in rows]
    d_phi = [s['prog'] - s['phi'] for _, _, s in rows if np.isfinite(s.get('phi', np.nan))]
    expl = [(s['prog'] - s['b1']) / (s['box'] - s['b1']) for _, _, s in rows if np.isfinite(s.get('box', np.nan)) and s['box'] - s['b1'] > 1e-9]
    co = [r['coincidence'] for r in res.values() if r['coincidence']]
    return dict(n_cells=len(rows), prog_minus_b1_mean=float(np.mean(d_b1)) if d_b1 else None,
                prog_minus_b1_pos=int(sum(x > 0 for x in d_b1)), prog_minus_b0_mean=float(np.mean(d_b0)) if d_b0 else None,
                prog_minus_phi_mean=float(np.mean(d_phi)) if d_phi else None, prog_minus_phi_pos=int(sum(x > 0 for x in d_phi)),
                explained_median=float(np.median(expl)) if expl else None, explained_n=len(expl),
                hit_prog_mean=float(np.nanmean([s['hit_prog'] for _, _, s in rows])) if rows else None,
                hit_b1_mean=float(np.nanmean([s['hit_b1'] for _, _, s in rows])) if rows else None,
                K_ratio_by_env={e: r['coincidence']['K_ratio'] for e, r in res.items() if r['coincidence']},
                F_ratio_by_env={e: r['coincidence']['F_ratio'] for e, r in res.items() if r['coincidence']},
                K_ratio_median=float(np.nanmedian([c['K_ratio'] for c in co])) if co else None)


def select_envs(envs, names):
    return envs if not names else {n: e for n, e in envs.items() if n in names}


def pilot(dst, fit_dirs, eval_sets, R=50, seed=SEED):
    """Пилот: программы строятся по средам fit_dirs (сборки по семействам), проверяются на наборах eval_sets {имя: [сборки]}.
    Данные пилота и проверки пилота — уже собранные (OCDIV-03/04), всё описательно; тест DISTILL-02 — свежее извлечение."""
    t0 = time.time()
    fits, fit_envs = {}, {}
    for key, (mdir, names) in fit_dirs.items():                   # ключ построения: семейство или часть его сред (П4)
        envs = select_envs(load_merged(mdir), names)
        fit_envs[key] = sorted(envs)
        fits[key] = fit_family(list(envs.values()))
    out = dict(phase='pilot', hypothesis='394b7be2', R=R, seed=seed, features=list(FEATURES), max_features=MAX_FEATURES, fit_envs=fit_envs,
               formulas={fam: {h: {k: v for k, v in f['prog'].items()} for h, f in fs.items()} for fam, fs in fits.items()},
               formulas_phi={fam: {h: {k: v for k, v in f['phi'].items()} for h, f in fs.items()} for fam, fs in fits.items()},
               offsets_b1={fam: {h: dict(acc=f['om']['acc'], top=sorted(f['om']['p'].items(), key=lambda kv: -kv[1])[:8])
                                 for h, f in fs.items()} for fam, fs in fits.items()},
               eval={})
    for name, (fam, mdirs, names) in eval_sets.items():
        envs = {}
        for md in mdirs:
            envs.update(select_envs(load_merged(md), names))
        res = eval_envs(fits[fam], envs, R, seed + len(out['eval']))
        out['eval'][name] = dict(family=fam, envs=res, summary=summarize(res))
    out['seconds'] = round(time.time() - t0, 1)
    json.dump(out, open(dst, 'w', encoding='utf-8'), ensure_ascii=False, indent=1, default=float)
    print('пилот DISTILL-02:', {k: v['summary'] for k, v in out['eval'].items()}, '| время', out['seconds'], 'с', flush=True)
    return out


def main(a):
    if not a:
        sys.exit(__doc__)
    if a[0] == 'merge4':                                          # сборка фаз OCDIV-04 (тем же кодом, что в OCDIV-04)
        C4.merge4(a[1], a[2], a[3], a[4:])
    elif a[0] == 'merge2':                                        # сборка фаз OCDIV-02/03 (`ocdiv2.merge`)
        W.merge(a[1], a[2], a[3], a[4:])
    elif a[0] == 'pilot2':
        spec = json.load(open(a[2], encoding='utf-8'))
        pilot2(a[1], {k: (v[0], v[1]) for k, v in spec['fit'].items()}, {k: (v[0], v[1], v[2]) for k, v in spec['eval'].items()},
               R=spec.get('R', 20), B=spec.get('B', 200))
    elif a[0] == 'test':
        spec = json.load(open(a[2], encoding='utf-8'))            # {"construction": {fam: [dirs]}, "test": {фаза: [dirs]}}
        test_d2(a[1], spec['construction'], spec['test'], B=spec.get('B', B_TEST), R=spec.get('R', R_TEST))
    elif a[0] == 'pilot':
        spec = json.load(open(a[2], encoding='utf-8'))            # {"fit": {ключ: [dir, [среды] | null]}, "eval": {имя: [ключ, [dirs], [среды] | null]}}
        pilot(a[1], {k: (v[0], v[1]) for k, v in spec['fit'].items()}, {k: (v[0], v[1], v[2]) for k, v in spec['eval'].items()},
              R=spec.get('R', 50))
    else:
        sys.exit(__doc__)


# ═══════════════ часть 2: меры по средам с бутстрепом, правила и мощность (для PREREG; пилот 2 — по уже собранным данным)
LEVEL = C4.LEVEL                                                   # 0,0025 на сторону, как в программе
MIN_NUMERIC = 200                                                  # голова входит в среду, если числовых ответов не меньше 200
SHARE_MIN = 0.5                                                    # П2: «большая часть» объяснимого — больше половины


def env_arrays(fits, env, R, rng, rounded=True):
    """Для одной среды: по задачам и головам — лог-вероятности ответа у программы, B1, ящика (NaN — без числа), смещения головы и R
    выборок программ (для K из программ)."""
    items, offs, lps = env_table(env, with_logp=True)
    hs = [h for h in offs if h in fits and int((offs[h] < NC).sum()) >= MIN_NUMERIC]
    n = len(items)
    L = {k: np.full((n, len(hs)), np.nan) for k in ('prog', 'b1', 'box', 'phi', 'b0')}
    for k, h in enumerate(hs):
        f = fits[h]
        bx = box_classes(f['box'], items)
        for i, (it, d) in enumerate(zip(items, offs[h])):
            if d >= NC:
                continue
            y = it['sum'] + int(d)
            dist = program_dist(f['prog'], it, rounded)
            L['prog'][i, k] = math.log(max(answer_prob(f['prog'], it, y, rounded, dist), 1e-300))
            L['b1'][i, k] = math.log(max(b1_prob(f['om'], it, y), 1e-300))
            L['b0'][i, k] = math.log(max(b0_prob(f['om']['acc'], it, y), 1e-300))
            L['box'][i, k] = math.log(max(box_prob(f['box'], it, y, f['prog'], bx[i]), 1e-300))
            L['phi'][i, k] = math.log(max(answer_prob(f['phi'], it, y, rounded), 1e-300))
    D = np.column_stack([offs[h] for h in hs]) if hs else np.zeros((n, 0), np.int64)
    tabs = [[sampler(fits[h]['prog'], it, rounded) if D[i, k] < NC else None for i, it in enumerate(items)] for k, h in enumerate(hs)]
    S_ = []
    for _ in range(R):
        Dp = D.copy()
        for k in range(len(hs)):
            for i, it in enumerate(items):
                if tabs[k][i] is not None:
                    Dp[i, k] = draw(tabs[k][i], it, rng)
        S_.append(Dp)
    return dict(heads=hs, L=L, D=D, S=S_, n=n)


def k_stat(D, rows=None):
    Dr = D if rows is None else D[rows]
    ks = []
    for i, j in itertools.combinations(range(Dr.shape[1]), 2):
        both = (Dr[:, i] != 0) & (Dr[:, j] != 0) & (Dr[:, i] < NC) & (Dr[:, j] < NC)
        if both.any():
            ks.append(float((Dr[both, i] == Dr[both, j]).mean()))
    return float(np.mean(ks)) if ks else float('nan')


def env_point(ea, rows=None):
    """Точки мер среды на строках rows (бутстреп) или на всех задачах:
    m1 — среднее по головам разности лог-вероятностей программа − B1 (на числовой ответ); m1_phi — программа − Φ-база;
    m2 — доля объяснимого Σ(программа − B1) / Σ(max(ящик, программа) − B1) по головам: сколько программа берёт от лучшего из ящика и
    программы (≤ 1; не определена, если обе не лучше B1); m3 — ln(K наблюдённое / K из программ)."""
    L = {k: (v if rows is None else v[rows]) for k, v in ea['L'].items()}
    with np.errstate(invalid='ignore'):
        d1 = np.nanmean(L['prog'] - L['b1'], axis=0)
        dphi = np.nanmean(L['prog'] - L['phi'], axis=0)
        dbox = np.maximum(np.nanmean(L['box'] - L['b1'], axis=0), d1)
    m1 = float(np.nanmean(d1)) if len(d1) else float('nan')
    m2 = float(np.nansum(d1) / np.nansum(dbox)) if np.nansum(dbox) > 1e-12 else float('nan')
    ko = k_stat(ea['D'], rows)
    kp = float(np.nanmean([k_stat(s, rows) for s in ea['S']])) if ea['S'] else float('nan')
    m3 = float(math.log(ko / kp)) if (ko > 0 and kp > 0) else float('nan')
    return dict(m1=m1, m1_phi=float(np.nanmean(dphi)) if len(dphi) else float('nan'), m2=m2, m3=m3, K_obs=ko, K_prog=kp)


def env_measures(ea, B, rng):
    """Точки и повторы бутстрепа (строки задач с возвращением) мер среды."""
    pt = env_point(ea)
    reps = {k: [] for k in ('m1', 'm1_phi', 'm2', 'm3')}
    for _ in range(B):
        rows = rng.integers(0, ea['n'], ea['n'])
        r = env_point(ea, rows)
        for k in reps:
            reps[k].append(r[k])
    out = dict(point=pt, n=ea['n'], heads=ea['heads'])
    out['sd'] = {k: float(np.nanstd(v, ddof=1)) for k, v in reps.items()}
    return out, {k: np.array(v) for k, v in reps.items()}


def family_rule(points, boots, sds, names, kind, part_b, shift=0.0):
    """Правило по средам семейства (как OCDIV-04, `ocdiv4.rule4`): величина − shift; часть А — M4 среднего, часть Б — t по средам."""
    p = {n: points[n] - shift for n in names}
    b = {n: boots[n] - shift for n in names}
    return C4.rule4(p, b, sds, names, kind, part_b)


def power_rule(points, sds, scale, m, part_b, shift=0.0):
    """Мощность по пилоту (модель «новая среда», `ocdiv4.power_entry4`): точка среды ~ N(μ, τ² + s²)."""
    return C4.power_entry4([x - shift for x in points], sds, scale, m, part_b)


def pilot2(dst, fit_dirs, eval_sets, R=20, B=200, seed=SEED + 1000):
    """Пилот 2: меры по средам с бутстрепом и мощность правил для PREREG (данные — уже собранные, описательно)."""
    t0 = time.time()
    fits = {}
    for key, (mdir, names) in fit_dirs.items():
        fits[key] = fit_family(list(select_envs(load_merged(mdir), names).values()))
    out = dict(phase='pilot2', hypothesis='394b7be2', R=R, B=B, seed=seed, min_numeric=MIN_NUMERIC, share_min=SHARE_MIN, sets={})
    for si, (name, (key, mdirs, names)) in enumerate(eval_sets.items()):
        envs = {}
        for md in mdirs:
            envs.update(select_envs(load_merged(md), names))
        rng = np.random.default_rng(seed + 100 * si)
        res = {}
        for en, env in sorted(envs.items()):
            ea = env_arrays(fits[key], env, R, rng)
            m, _ = env_measures(ea, B, rng)
            res[en] = m
        names_ = sorted(res)
        pw = {}
        for meas, shift, kind in (('m1', 0.0, 'pos'), ('m1_phi', 0.0, 'pos'), ('m2', SHARE_MIN, 'pos'), ('m3', 0.0, 'two')):
            pts = [res[n]['point'][meas] for n in names_]
            sds = [res[n]['sd'][meas] for n in names_]
            for m_, pb in ((len(names_), len(names_) >= 4),):
                e = power_rule(pts, sds, 1.0, m_, pb, shift)
                if e is not None and kind == 'two':
                    e['power']['decisive'] = e['power']['confirm'] + e['power']['refute']
                elif e is not None:
                    e['power']['decisive'] = e['power']['confirm']
                pw[meas] = e
        out['sets'][name] = dict(key=key, envs=res, power=pw)
    out['seconds'] = round(time.time() - t0, 1)
    json.dump(out, open(dst, 'w', encoding='utf-8'), ensure_ascii=False, indent=1, default=float)
    print('пилот 2 DISTILL-02:', {k: {m: (round(v['power'][m]['power']['decisive'], 3) if v['power'][m] else None) for m in v['power']}
                                   for k, v in out['sets'].items()}, '| время', out['seconds'], 'с', flush=True)
    return out

# ═══════════════ часть 3: анализ теста (PREREG; константы задаются до регистрации, без них анализ не идёт)
# правило: (семейство, фаза, мера, вид, есть ли часть Б, сдвиг)
RULES = {'Р1-Т': ('thousands', 'test5', 'm1', 'pos', True, 0.0), 'Р1-Л': ('length', 'test5', 'm1', 'pos', False, 0.0),
         'Р2-Т': ('thousands', 'test5', 'm2', 'pos', True, SHARE_MIN), 'Р2-Л': ('length', 'test5', 'm2', 'pos', False, SHARE_MIN),
         'Р3-Т': ('thousands', 'test5', 'm3', 'two', True, 0.0), 'Р3-Л': ('length', 'test5', 'm3', 'two', False, 0.0),
         'Р4-Т': ('thousands', 'new5', 'm1', 'pos', False, 0.0)}
DESCR_MEAS = ('m1_phi',)
RULES_ACTIVE = None        # {'Р1-Т': True|False, ...}: True — правило, False — описательно (решающая мощность по пилоту < POWER_MIN)
POWER_MIN = 0.2
B_TEST, R_TEST = 4000, 20
SEED_TEST = 9_930_000


def family_of(name):
    return 'thousands' if name.startswith('T_') else 'length'


def test_d2(dst, construction, test_sets, B=B_TEST, R=R_TEST, seed=SEED_TEST):
    """Анализ теста: программы, B1, ящик и Φ-база строятся по всем сборкам построения семейства; меры — на свежих средах фаз test5 и
    new5; правила — по RULES и RULES_ACTIVE; описательное — m1_phi, совпадение F, попадание в три неверных, оценщик."""
    assert RULES_ACTIVE is not None, 'константы PREREG не заданы'
    t0 = time.time()
    fits = {}
    for fam, mdirs in construction.items():
        envs = []
        for md in mdirs:
            envs += [e for n, e in load_merged(md).items() if family_of(n) == fam]
        fits[fam] = fit_family(envs)
    out = dict(phase='test', hypothesis='394b7be2', B=B, R=R, seed=seed, level=LEVEL, rules_active=RULES_ACTIVE,
               formulas={fam: {h: f['prog'] for h, f in fs.items()} for fam, fs in fits.items()},
               formulas_phi={fam: {h: f['phi'] for h, f in fs.items()} for fam, fs in fits.items()}, envs={}, rules={}, descr={})
    boots = {}
    rng = np.random.default_rng(seed)
    for ph, mdirs in test_sets.items():
        for md in mdirs:
            for name, env in sorted(load_merged(md).items()):
                fam = family_of(name)
                ea = env_arrays(fits[fam], env, R, rng)
                m, b = env_measures(ea, B, rng)
                items, offs, lps = env_table(env, with_logp=True)
                desc = {}
                for h in ea['heads']:
                    f = fits[fam][h]
                    sc = head_scores(f['prog'], f['om'], f['box'], items, offs[h], logp=lps[h], phi=f['phi'])
                    sc.pop('_ll')
                    desc[h] = sc
                m['heads_scores'] = desc
                F_obs, _ = coincidence_stats(ea['D'])
                m['F_obs'] = F_obs
                m['F_prog'] = float(np.mean([coincidence_stats(s_)[0] for s_ in ea['S']])) if ea['S'] else float('nan')
                out['envs'][name] = dict(m, phase=ph, family=fam)
                boots[name] = b
    for rule, (fam, ph, meas, kind, part_b, shift) in RULES.items():
        names = sorted(n for n, e in out['envs'].items() if e['family'] == fam and e['phase'] == ph and np.isfinite(e['point'][meas]))
        pts = {n: out['envs'][n]['point'][meas] for n in names}
        sds = {n: out['envs'][n]['sd'][meas] for n in names}
        e = family_rule(pts, {n: boots[n][meas] for n in names}, sds, names, kind, part_b, shift) if len(names) >= 2 else dict(
            verdict_rule='не определено (сред мало)', names=names)
        e.update(active=RULES_ACTIVE[rule], measure=meas, shift=shift, names=names)
        out['rules'][rule] = e
    for meas in DESCR_MEAS:
        for fam in ('thousands', 'length'):
            names = sorted(n for n, e in out['envs'].items() if e['family'] == fam and e['phase'] == 'test5' and np.isfinite(e['point'][meas]))
            if len(names) >= 2:
                out['descr'][f'{fam} {meas}'] = C4.mean_entry({n: out['envs'][n]['point'][meas] for n in names},
                                                              {n: boots[n][meas] for n in names}, names, C4.DESCR_LEVEL)
    out['verdicts'] = {r: out['rules'][r].get('verdict_rule') for r in RULES}
    out['seconds'] = round(time.time() - t0, 1)
    json.dump(out, open(dst, 'w', encoding='utf-8'), ensure_ascii=False, indent=1, default=float)
    print('вердикт DISTILL-02:', out['verdicts'], '| время', out['seconds'], 'с', flush=True)
    return out



if __name__ == '__main__':
    main(sys.argv[1:])
