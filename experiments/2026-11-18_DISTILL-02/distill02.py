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
Меры: средняя лог-вероятность ответа головы (на числовой ответ; вероятность каждого соперника смешана с равномерной по V:
(1 − λ)·p + λ/|V|, λ = 1e-3 — совет 74), доля неверных ответов в трёх самых вероятных неверных, совпадение ошибок голов (F, K)
из программ, независимых при данном входе, против наблюдённого, и оценщик P(верно) против уверенности головы (AUC; описательно).
  python3 distill02.py merge4|merge2|merge_d2 ВЫХОД ФАЗА СЕМЕЙСТВО ПАПКИ...   — сборки
  python3 distill02.py pilot ВЫХОД.json SPEC.json | pilot3 ВЫХОД.json SPEC.json  — пилоты (описательно)
  python3 distill02.py test ВЫХОД.json SPEC.json                                — анализ теста (нужны константы PREREG)
Правда — только от кода: сумма и переносы считаются из a и b; ответы голов читаются из сборок OCDIV-03/04."""
import hashlib
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
        ll['prog'].append(mlog(p_prog, it['sum']))                  # смесь λ (совет 74, п. 1), как в мерах сред
        ll['b0'].append(mlog(b0_prob(om['acc'], it, y), it['sum']))
        ll['b1'].append(mlog(b1_prob(om, it, y), it['sum']))
        if box is not None:
            ll['box'].append(mlog(box_prob(box, it, y, prog, bx[i]), it['sum']))
        if phi is not None:
            ll['phi'].append(mlog(answer_prob(phi, it, y, rounded), it['sum']))
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
def merge_d2(out_dir, phase, family, job_dirs):
    """Сборка свежих фаз DISTILL-02 тем же кодом, что OCDIV-02 и OCDIV-04 (`ocdiv2.merge`: сверка номеров задач, ключей (a, b),
    sha256 подсказки и ревизий — СТОП при расхождении); на время вызова `ocdiv2.D2.envs_ocdiv2` отдаёт среды `distill02_extract.envs_d2`."""
    sys.path.insert(0, X_DIR)
    import distill02_extract as XD
    assert phase in XD.PHASES5, phase
    orig = W.D2.envs_ocdiv2
    W.D2.envs_ocdiv2 = lambda ph, fams=None: XD.envs_d2(ph, fams)
    try:
        return W.merge(out_dir, phase, family, job_dirs)
    finally:
        W.D2.envs_ocdiv2 = orig


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


# ═══════════════ часть 2: меры по средам с бутстрепом, правила и мощность (совет 74: смесь λ, зерно среды, выборки программ в повторах)
LEVEL = C4.LEVEL                                                   # 0,0025 на сторону, как в программе
MIN_NUMERIC = 200                                                  # голова входит в среду, если числовых ответов не меньше 200
SHARE_MIN = 0.5                                                    # П2: «большая часть» объяснимого — больше половины
LAMBDA = 1e-3                                                      # совет 74, п. 1: смесь (1 − λ)·p + λ/|V| — одна для всех соперников, фаз и
#                                                                    сред; по суждению, без пилотных исходов; записана до пересчёта пилотов
LAMBDA_SENS = (0.0, 1e-2, 1e-4)                                    # описательно, в точке: 0 — прежняя обрезка max(p, 1e-300)
FRAGILE = 0.5                                                      # «хрупкий»: одна задача даёт больше половины суммы вкладов (совет 74)
COMPETITORS = ('prog', 'b1', 'b0', 'box', 'phi')
MEASURES = ('m1', 'm1_phi', 'm2', 'm2_max', 'm3', 'm3_c', 'm3_o')
LL_PARTS = {'b1': ('prog', 'b1'), 'phi': ('prog', 'phi'), 'box': ('box', 'b1')}   # вклады задач: разности лог-вероятностей
FRAG_PARTS = {'m1': ('b1',), 'm1_phi': ('phi',), 'm2': ('b1', 'box'), 'm2_max': ('b1', 'box')}
REST = np.int64(-(2 ** 61))                                        # «остаток» в таблице выборки — заменяется случайным числом из V
CHUNK = 500                                                        # повторы бутстрепа для мер по лог-вероятностям — частями (память)


def mixed_log(p, V, lam=None):
    """log((1 − λ)·p + λ/|V|) — одна смесь для всех соперников (совет 74, п. 1). |V| — `ref_size` задачи: целые с числом цифр от n − 2
    до n + 1, n — цифр в верной сумме; ответ с p = 0 даёт log(λ/|V|), в том числе вне V. λ = 0 — прежняя обрезка max(p, 1e-300)."""
    lam = LAMBDA if lam is None else lam
    p = np.asarray(p, float)
    if lam == 0:
        return np.log(np.maximum(p, 1e-300))
    return np.log((1 - lam) * p + lam / np.asarray(V, float))


def mlog(p, total, lam=None):
    """То же для одного ответа (описательные меры голов)."""
    return float(mixed_log(p, ref_size(total), lam))


def _h64(s):
    return int.from_bytes(hashlib.sha256(str(s).encode('utf-8')).digest()[:8], 'little')


def env_seed(seed, name, phase):
    """Зерно среды (совет 74, п. 7): SeedSequence(зерно, имя, фаза) — числа среды не зависят от того, какие среды прошли до неё.
    Два потока: строки бутстрепа и выборки программ."""
    sb, sp = np.random.SeedSequence([int(seed), _h64(name), _h64(phase)]).spawn(2)
    return np.random.default_rng(sb), np.random.default_rng(sp)


def _nanmean(a, axis=-1):
    a = np.asarray(a, float)
    ok = np.isfinite(a)
    c = ok.sum(axis)
    return np.where(c > 0, np.where(ok, a, 0.0).sum(axis) / np.maximum(c, 1), np.nan)


def alias_table(probs):
    """Таблица Уокера (метод Воуза): выборка из конечного распределения за два случайных числа."""
    K = len(probs)
    pr = np.asarray(probs, float)
    pr = pr * K / pr.sum()
    acc, ali = np.ones(K), np.arange(K)
    small = [i for i in range(K) if pr[i] < 1.0]
    large = [i for i in range(K) if pr[i] >= 1.0]
    while small and large:
        s, g = small.pop(), large.pop()
        acc[s], ali[s] = pr[s], g
        pr[g] = pr[g] + pr[s] - 1.0
        (small if pr[g] < 1.0 else large).append(g)
    return acc, ali


def env_sampler(progs, items, D, rounded=True):
    """Таблицы выборки ответов программ: для каждой головы и задачи с числовым ответом — опора программы (верный ответ и наборы
    потерянных переносов), «прочие» смещения по частотам головы и «остаток» — случайное число из V вне опоры (как `sampler` и `draw`);
    метка «потеря переноса» — у смещений опоры, кроме 0."""
    n, H = D.shape
    tidx = np.full((n, H), -1, np.int64)
    tabs = []
    for k in range(H):
        for i, it in enumerate(items):
            if D[i, k] >= NC:
                continue
            prog = progs[k]
            dist = program_dist(prog, it, rounded)
            offs = [y - it['sum'] for y in dist]
            pr = list(dist.values())
            car = [o != 0 for o in offs]
            nsup = len(offs)
            v, tot = other_valid(prog, it, dist)
            if tot > 0:
                offs += list(v.keys())
                pr += [prog['eps'] * qq / tot for qq in v.values()]
                car += [False] * len(v)
            rest = max(0.0, 1.0 - sum(pr))
            if rest > 1e-15:
                offs.append(int(REST))
                pr.append(rest)
                car.append(False)
            acc, ali = alias_table(pr)
            tidx[i, k] = len(tabs)
            nd = len(str(it['sum']))
            tabs.append((offs, acc, ali, car, nsup, it['sum'], 10 ** max(nd - 3, 0), 10 ** (nd + 1)))
    T, KM = len(tabs), max((len(t[0]) for t in tabs), default=1)
    S = dict(tidx=tidx, off=np.zeros((T, KM), np.int64), acc=np.ones((T, KM)), ali=np.zeros((T, KM), np.int64),
             car=np.zeros((T, KM), bool), K=np.zeros(T, np.int64), nsup=np.zeros(T, np.int64), sum=np.zeros(T, np.int64),
             lo=np.zeros(T, np.int64), hi=np.zeros(T, np.int64))
    for t, (offs, acc, ali, car, nsup, sm, lo, hi) in enumerate(tabs):
        K = len(offs)
        S['off'][t, :K], S['acc'][t, :K], S['ali'][t, :K], S['car'][t, :K] = offs, acc, ali, car
        S['K'][t], S['nsup'][t], S['sum'][t], S['lo'][t], S['hi'][t] = K, nsup, sm, lo, hi
    return S


def draw_many(S, tt, rng):
    """Смещения ответов программ по таблицам tt (метод Уокера); «остаток» — случайное число из V, не из опоры программы."""
    K = S['K'][tt]
    j = np.minimum((rng.random(len(tt)) * K).astype(np.int64), K - 1)
    u = rng.random(len(tt))
    col = np.where(u < S['acc'][tt, j], j, S['ali'][tt, j])
    off = S['off'][tt, col]
    car = S['car'][tt, col]
    r = np.flatnonzero(off == REST)
    cols = np.arange(S['off'].shape[1])[None, :]
    while len(r):
        t_r = tt[r]
        o = rng.integers(S['lo'][t_r], S['hi'][t_r]) - S['sum'][t_r]
        bad = ((S['off'][t_r] == o[:, None]) & (cols < S['nsup'][t_r][:, None])).any(1)
        off[r[~bad]] = o[~bad]
        r = r[bad]
    return off, car


def sample_D(S, D, idx, R, rng):
    """R выборок ответов программ на строках idx (у каждой строки повтора — своя выборка); без числа — на тех же местах, что у голов."""
    Di = D[idx]
    T = S['tidx'][idx]
    valid = T >= 0
    off, car = draw_many(S, np.tile(T[valid], R), rng)
    Dp = np.repeat(Di[None], R, axis=0)
    Cp = np.zeros(Dp.shape, bool)
    Dp[:, valid] = off.reshape(R, -1)
    Cp[:, valid] = car.reshape(R, -1)
    return Dp, Cp


def k_parts(Dp, Cp):
    """K по стопке (r, m, H): среднее по парам голов доли одинаковых смещений среди задач, где обе дали неверное числовое смещение (пары
    без таких задач не входят; NaN — нет ни одной); Kc — то же для одинаковых смещений «потеря переноса» (−Σ 10^j по разрядам с
    переносом), Ko = K − Kc — «прочие» (совет 74, п. 5)."""
    I, J = np.triu_indices(Dp.shape[-1], 1)
    wrong = (Dp != 0) & (Dp < NC)
    both = wrong[..., I] & wrong[..., J]
    same = both & (Dp[..., I] == Dp[..., J])
    nb = both.sum(-2).astype(float)
    with np.errstate(invalid='ignore', divide='ignore'):
        k = np.where(nb > 0, same.sum(-2) / nb, np.nan)
        kc = np.where(nb > 0, (same & Cp[..., I]).sum(-2) / nb, np.nan)
    return _nanmean(k), _nanmean(kc)


def _lr(a, b):
    return float(math.log(a / b)) if (np.isfinite(a) and np.isfinite(b) and a > 0 and b > 0) else float('nan')


def k_measures(ko, kco, kp, kcp):
    """m3 = ln(K наблюдённое / K из программ); m3_c и m3_o — то же по «потере переноса» и по «прочим» (описательно)."""
    K_obs, Kc_obs = float(ko[0]), float(kco[0])
    K_prog, Kc_prog = float(_nanmean(kp, 0)), float(_nanmean(kcp, 0))
    Ko_obs, Ko_prog = K_obs - Kc_obs, K_prog - Kc_prog
    return dict(m3=_lr(K_obs, K_prog), m3_c=_lr(Kc_obs, Kc_prog), m3_o=_lr(Ko_obs, Ko_prog), K_obs=K_obs, K_prog=K_prog,
                Kc_obs=Kc_obs, Kc_prog=Kc_prog, Ko_obs=Ko_obs, Ko_prog=Ko_prog)


def measures_w(ea, L, Wm):
    """Меры по лог-вероятностям на строках с кратностями Wm (повторы × задачи): m1 — среднее по головам разности программа − B1 на
    числовой ответ; m1_phi — программа − Φ-база; m2 — доля объяснимого Σ(программа − B1) / Σ(ящик − B1) по головам (совет 74, п. 4:
    решающая — от одного ящика; NaN, если ящик не лучше B1); m2_max — от лучшего из ящика и программы (описательно, смещена вверх)."""
    M = ea['M']
    cnt = Wm @ M

    def hm(x, y):
        return (Wm @ np.where(M > 0, L[x] - L[y], 0.0)) / cnt
    d1, dphi, dbox = hm('prog', 'b1'), hm('prog', 'phi'), hm('box', 'b1')
    s1, sb, sbm = d1.sum(1), dbox.sum(1), np.maximum(dbox, d1).sum(1)
    with np.errstate(invalid='ignore', divide='ignore'):
        return dict(m1=d1.mean(1), m1_phi=dphi.mean(1), m2=np.where(sb > 1e-12, s1 / sb, np.nan), m2_max=np.where(sbm > 1e-12, s1 / sbm, np.nan))


def env_arrays(fits, env, rounded=True):
    """Для одной среды: по задачам и головам — вероятности ответа у программы, B1, B0, ящика и Φ-базы (NaN — без числа), их смеси λ,
    смещения головы и метки «потеря переноса», таблицы выборки программ. Головы — с числовыми ответами не меньше MIN_NUMERIC."""
    items, offs, lps = env_table(env, with_logp=True)
    hs = [h for h in offs if h in fits and int((offs[h] < NC).sum()) >= MIN_NUMERIC]
    n = len(items)
    V = np.array([ref_size(it['sum']) for it in items], float)
    P = {k: np.full((n, len(hs)), np.nan) for k in COMPETITORS}
    for k, h in enumerate(hs):
        f = fits[h]
        bx = box_classes(f['box'], items)
        for i, (it, d) in enumerate(zip(items, offs[h])):
            if d >= NC:
                continue
            y = it['sum'] + int(d)
            dist = program_dist(f['prog'], it, rounded)
            P['prog'][i, k] = answer_prob(f['prog'], it, y, rounded, dist)
            P['b1'][i, k] = b1_prob(f['om'], it, y)
            P['b0'][i, k] = b0_prob(f['om']['acc'], it, y)
            P['box'][i, k] = box_prob(f['box'], it, y, f['prog'], bx[i])
            P['phi'][i, k] = answer_prob(f['phi'], it, y, rounded)
    L = {k: mixed_log(P[k], V[:, None]) for k in COMPETITORS}
    D = np.column_stack([offs[h] for h in hs]) if hs else np.zeros((n, 0), np.int64)
    C = np.zeros(D.shape, bool)
    for i, it in enumerate(items):
        cpos = [j for j, _ in carry_info(it['a'], it['b'])]
        for k in range(len(hs)):
            if 0 != D[i, k] < NC:
                C[i, k] = bool(lost_set(int(D[i, k]), cpos))
    S_ = env_sampler([fits[h]['prog'] for h in hs], items, D, rounded)
    return dict(heads=hs, P=P, L=L, V=V, D=D, C=C, S=S_, M=np.isfinite(L['prog']).astype(float), n=n, items=items, offs=offs, lps=lps)


def env_measures(ea, B, rng_boot, rng_prog, R):
    """Точки и повторы бутстрепа мер среды. Строки задач — с возвращением (поток rng_boot, все повторы одним вызовом); выборки
    программ для K из программ — R на каждую строку точки и каждого повтора (поток rng_prog: сначала точка, потом повторы по порядку)."""
    n = ea['n']
    pt = {k: float(v[0]) for k, v in measures_w(ea, ea['L'], np.ones((1, n))).items()}
    ko, kco = k_parts(ea['D'][None], ea['C'][None])
    Dp, Cp = sample_D(ea['S'], ea['D'], np.arange(n), R, rng_prog)
    kp, kcp = k_parts(Dp, Cp)
    pt.update(k_measures(ko, kco, kp, kcp))
    has = ea['D'].shape[1] > 0
    pt['F_obs'] = float(W.false_major(ea['D']).mean()) if has else float('nan')
    pt['F_prog'] = float(np.mean([W.false_major(Dp[r]).mean() for r in range(R)])) if has and R else float('nan')
    IDX = rng_boot.integers(0, n, (B, n))
    reps = {k: np.full(B, np.nan) for k in MEASURES}
    for s in range(0, B, CHUNK):
        Wb = np.stack([np.bincount(r, minlength=n) for r in IDX[s:s + CHUNK]]).astype(float)
        for k, v in measures_w(ea, ea['L'], Wb).items():
            reps[k][s:s + CHUNK] = v
    for b in range(B):
        idx = IDX[b]
        ko, kco = k_parts(ea['D'][idx][None], ea['C'][idx][None])
        Dp, Cp = sample_D(ea['S'], ea['D'], idx, R, rng_prog)
        kp, kcp = k_parts(Dp, Cp)
        r = k_measures(ko, kco, kp, kcp)
        for k in ('m3', 'm3_c', 'm3_o'):
            reps[k][b] = r[k]
    sd = {k: (float(np.nanstd(v, ddof=1)) if np.isfinite(v).sum() > 1 else float('nan')) for k, v in reps.items()}
    return dict(point=pt, sd=sd, nan_reps={k: int((~np.isfinite(v)).sum()) for k, v in reps.items()}, n=n, heads=ea['heads']), reps


def contributions(ea, L):
    """Вклад каждой задачи в меру среды: c_i = (1/H) Σ_h Δ_ih / n_h по числовым ответам; Σ_i c_i — точка меры (m1 для «b1»,
    m1_phi для «phi»; для «box» — среднее по головам ящик − B1)."""
    M = ea['M']
    nh = np.maximum(M.sum(0), 1)
    H = max(M.shape[1], 1)
    return {p: (np.where(M > 0, L[x] - L[y], 0.0) / nh).sum(1) / H for p, (x, y) in LL_PARTS.items()}


def concentration(c):
    """Наибольший вклад одной задачи по модулю к модулю суммы; доля задач, на которые приходится больше половины суммы (по знаку
    суммы, от самых больших вкладов)."""
    c = np.asarray(c, float)
    tot = float(c.sum())
    if not len(c) or tot == 0:
        return dict(total=tot, top_share=float('nan'), half_tasks_share=float('nan'))
    cs = np.cumsum(np.sort(np.sign(tot) * c)[::-1])
    k = int(np.argmax(cs > 0.5 * abs(tot))) + 1 if (cs > 0.5 * abs(tot)).any() else len(c)
    return dict(total=tot, top_share=float(np.abs(c).max() / abs(tot)), half_tasks_share=k / len(c))


def sens_points(ea):
    """Чувствительность к λ (описательно, в точке, без бутстрепа): m1, m1_phi, m2, m2_max при λ = 0 (прежняя обрезка), 1e-2 и 1e-4."""
    out = {}
    for lam in LAMBDA_SENS:
        L = {k: mixed_log(ea['P'][k], ea['V'][:, None], lam) for k in COMPETITORS}
        out[f'{lam:g}'] = {k: float(v[0]) for k, v in measures_w(ea, L, np.ones((1, ea['n']))).items()}
    return out


def carry_summary(items):
    """Строение задач среды (из кода, не из ответов): доля вне диапазона (ood) и число задач с переносом в каждый разряд."""
    pos = {}
    for it in items:
        for j, _ in carry_info(it['a'], it['b']):
            pos[j] = pos.get(j, 0) + 1
    return dict(ood_share=float(np.mean([it['ood'] for it in items])) if items else float('nan'),
                carry_positions={str(j): pos[j] for j in sorted(pos)})


def env_result(fits, env, name, phase, B, R, seed, rounded=True, descriptive=True, keep_contrib=True):
    """Всё по одной среде: меры с бутстрепом (зерно — имя и фаза), вклады задач и их сосредоточенность, чувствительность к λ, строение
    задач; описательно — меры каждой головы (`head_scores`)."""
    rng_boot, rng_prog = env_seed(seed, name, phase)
    ea = env_arrays(fits, env, rounded)
    m, reps = env_measures(ea, B, rng_boot, rng_prog, R)
    con = contributions(ea, ea['L'])
    m['concentration'] = {p: concentration(c) for p, c in con.items()}
    if keep_contrib:
        m['contrib'] = {p: [float(x) for x in c] for p, c in con.items()}
    m['lambda_sens'] = sens_points(ea)
    m['carries'] = carry_summary(ea['items'])
    if descriptive:
        desc = {}
        for h in ea['heads']:
            f = fits[h]
            sc = head_scores(f['prog'], f['om'], f['box'], ea['items'], ea['offs'][h], rounded, logp=ea['lps'][h], phi=f['phi'])
            sc.pop('_ll')
            desc[h] = sc
        m['heads_scores'] = desc
    return m, reps


def family_rule(points, boots, sds, names, kind, part_b, shift=0.0):
    """Правило по средам семейства — та же логика, что `ocdiv4.rule4` (часть А — M4 среднего при 0,0025, `ocdiv4.mean_entry`; часть Б —
    t по средам, `ocdiv4.t_envs`; знак по средам — `ocdiv4.env_signs`), величина − shift. Метки вердикта — свои: у одностороннего
    «подтверждено» / «опровергнуто» / «в среднем этих сред (на новые среды не переносится)» / «не решено»; у двустороннего — «больше» /
    «меньше» (с той же оговоркой, если есть только часть А) / «не решено»."""
    p = {n: points[n] - shift for n in names}
    b = {n: boots[n] - shift for n in names}
    e = C4.mean_entry(p, b, names, LEVEL)
    tb = C4.t_envs(p)
    e['t_envs'] = tb
    e['signs'] = C4.env_signs(p, sds, names)
    a = e['verdict']
    b_up = bool(np.isfinite(tb['t']) and tb['t'] > tb['crit'])
    b_dn = bool(np.isfinite(tb['t']) and tb['t'] < -tb['crit'])
    up, dn = ('подтверждено', 'опровергнуто') if kind == 'pos' else ('больше', 'меньше')
    if a == 'подтверждено' and (b_up or not part_b):
        v = up
    elif a == 'опровергнуто' and (b_dn or not part_b):
        v = dn
    elif a == 'подтверждено':
        v = f'в среднем этих сред: {up} (на новые среды не переносится)' if kind == 'two' else 'в среднем этих сред (на новые среды не переносится)'
    elif a == 'опровергнуто' and kind == 'two':
        v = f'в среднем этих сред: {dn} (на новые среды не переносится)'
    else:
        v = 'не решено'
    e['verdict_rule'] = v
    e['mark'] = 'знак по средам разный' if (e['signs']['neg'] and e['signs']['pos']) else None
    return e


def power_rule(points, sds, scale, m, part_b, shift=0.0):
    """Мощность по пилоту (модель «новая среда», `ocdiv4.power_entry4`): точка среды ~ N(μ, τ² + s²)."""
    return C4.power_entry4([x - shift for x in points], sds, scale, m, part_b)


POWER_SETS = (('m1', 0.0, 'pos'), ('m1_phi', 0.0, 'pos'), ('m2', SHARE_MIN, 'pos'), ('m2_max', SHARE_MIN, 'pos'), ('m3', 0.0, 'two'))


def pilot_sets(dst, fit_dirs, eval_sets, R=20, B=200, seed=SEED + 2000, phase='pilot3'):
    """Пилот 3 (совет 74): те же наборы, что пилот 2 (запуск e5785e6a), по новым мерам — смесь λ, зерно среды (имя, набор), выборки
    программ в повторах бутстрепа, m2 от одного ящика, разбивка m3; мощность правил для PREREG. Данные — уже собранные, описательно."""
    t0 = time.time()
    fits = {key: fit_family(list(select_envs(load_merged(mdir), names).values())) for key, (mdir, names) in fit_dirs.items()}
    out = dict(phase=phase, hypothesis='394b7be2', R=R, B=B, seed=seed, lam=LAMBDA, min_numeric=MIN_NUMERIC, share_min=SHARE_MIN,
               code_sha256=code_sha(), sets={})
    for name, (key, mdirs, names) in eval_sets.items():
        envs = {}
        for md in mdirs:
            envs.update(select_envs(load_merged(md), names))
        res = {en: env_result(fits[key], env, en, name, B, R, seed, descriptive=False, keep_contrib=False)[0] for en, env in sorted(envs.items())}
        names_ = sorted(res)
        pw = {}
        for meas, shift, kind in POWER_SETS:
            e = power_rule([res[n]['point'][meas] for n in names_], [res[n]['sd'][meas] for n in names_], 1.0, len(names_), len(names_) >= 4, shift)
            if e is not None:
                e['power']['decisive'] = e['power']['confirm'] + (e['power']['refute'] if kind == 'two' else 0.0)
            pw[meas] = e
        out['sets'][name] = dict(key=key, envs=res, power=pw)
    out['seconds'] = round(time.time() - t0, 1)
    json.dump(out, open(dst, 'w', encoding='utf-8'), ensure_ascii=False, indent=1, default=float)
    print(f'{phase} DISTILL-02: время', out['seconds'], 'с; сред', sum(len(v['envs']) for v in out['sets'].values()), flush=True)
    return out


# ═══════════════ часть 3: анализ теста (PREREG; константы задаются до регистрации, без них анализ не идёт)
# правило: (семейство, фаза, мера, вид, есть ли часть Б, сдвиг)
RULES = {'Р1-Т': ('thousands', 'test5', 'm1', 'pos', True, 0.0), 'Р1-Л': ('length', 'test5', 'm1', 'pos', False, 0.0),
         'Р1Ф-Т': ('thousands', 'test5', 'm1_phi', 'pos', True, 0.0), 'Р1Ф-Л': ('length', 'test5', 'm1_phi', 'pos', False, 0.0),
         'Р2-Т': ('thousands', 'test5', 'm2', 'pos', True, SHARE_MIN), 'Р2-Л': ('length', 'test5', 'm2', 'pos', False, SHARE_MIN),
         'Р3-Т': ('thousands', 'test5', 'm3', 'two', True, 0.0), 'Р3-Л': ('length', 'test5', 'm3', 'two', False, 0.0),
         'Р4-Т': ('thousands', 'new5', 'm1', 'pos', False, 0.0), 'Р4Ф-Т': ('thousands', 'new5', 'm1_phi', 'pos', False, 0.0)}
DESCR_MEAS = ('m2_max', 'm3_c', 'm3_o')                            # описательно, по обоим семействам test5 (совет 74, пп. 4–5)
RULES_ACTIVE = None        # {'Р1-Т': True|False, ...}: True — правило, False — описательно (PREREG §5: правило активности по пилоту 3)
POWER_MIN = 0.2
B_TEST, R_TEST = 4000, 20
SEED_TEST = 9_930_000


def family_of(name):
    return 'thousands' if name.startswith('T_') else 'length'


def code_sha():
    return hashlib.sha256(open(os.path.abspath(__file__), 'rb').read()).hexdigest()


def fragility(envs, names, meas):
    """«Хрупкий» (совет 74, п. 1): вклады задач всех сред правила в сумму разностей лог-вероятности; хрупкий, если одна задача даёт по
    модулю больше половины модуля суммы. Для m2 — отдельно числитель (программа − B1) и знаменатель (ящик − B1), хрупкий — если хоть
    один. Плюс доля задач, на которые приходится больше половины суммы; по каждой среде — описательно."""
    parts = FRAG_PARTS.get(meas)
    if not parts or not names:
        return None
    out = {}
    for p in parts:
        c = np.concatenate([np.asarray(envs[n]['contrib'][p], float) for n in names])
        e = concentration(c)
        e['fragile'] = bool(np.isfinite(e['top_share']) and e['top_share'] > FRAGILE)
        e['by_env_top_share'] = {n: envs[n]['concentration'][p]['top_share'] for n in names}
        out[p] = e
    return dict(parts=out, fragile=any(v['fragile'] for v in out.values()))


def load_part(path, meta):
    if not path or not os.path.exists(path):
        return None
    r = json.load(open(path, encoding='utf-8'))
    return r if r.get('meta') == meta else None


_POOL = {}


def _pool_init(fits, args):
    _POOL.update(fits=fits, args=args)


def _env_job(job):
    fam, ph, name, env = job
    a = _POOL['args']
    m, reps = env_result(_POOL['fits'][fam], env, name, ph, a['B'], a['R'], a['seed'])
    return name, m, {k: [float(x) for x in v] for k, v in reps.items()}


def test_d2(dst, construction, test_sets, B=B_TEST, R=R_TEST, seed=SEED_TEST, part_dir=None, only=None, no_time=False, workers=1):
    """Анализ теста: программы, B1, ящик и Φ-база строятся по всем сборкам построения семейства; меры — на свежих средах фаз test5 и
    new5; правила — по RULES и RULES_ACTIVE; описательное — m2_max, разбивка m3, хрупкость, λ = 0 / 1e-2 / 1e-4, совпадение F, попадание
    в три неверных, оценщик. Каждая среда пишется в part_dir/<фаза>__<имя>.json; при старте готовые (те же зерно, B, R, λ и код)
    берутся оттуда. only — только эти среды (повтор на детерминизм); no_time — без времени в выводе (побайтное сравнение)."""
    assert RULES_ACTIVE is not None, 'константы PREREG не заданы'
    t0 = time.time()
    meta = dict(seed=seed, B=B, R=R, lam=LAMBDA, code=code_sha())
    todo = []
    for ph, mdirs in test_sets.items():
        for md in mdirs:
            for name, env in sorted(load_merged(md).items()):
                if only is None or name in only:
                    todo.append((ph, name, env))
    fits = {}
    for fam in sorted({family_of(n) for _, n, _ in todo}):
        envs = []
        for md in construction[fam]:
            envs += [e for n, e in load_merged(md).items() if family_of(n) == fam]
        fits[fam] = fit_family(envs)
    out = dict(phase='test', hypothesis='394b7be2', B=B, R=R, seed=seed, lam=LAMBDA, level=LEVEL, rules_active=RULES_ACTIVE,
               code_sha256=meta['code'], only=only,
               formulas={fam: {h: f['prog'] for h, f in fs.items()} for fam, fs in fits.items()},
               formulas_phi={fam: {h: f['phi'] for h, f in fs.items()} for fam, fs in fits.items()}, envs={}, rules={}, descr={})
    if part_dir:
        os.makedirs(part_dir, exist_ok=True)
    res, need = {}, []
    for ph, name, env in todo:
        part = os.path.join(part_dir, f'{ph}__{name}.json') if part_dir else None
        r = load_part(part, meta)
        if r is None:
            need.append((family_of(name), ph, name, env))
        else:
            res[name] = r
    args = dict(B=B, R=R, seed=seed)
    _pool_init(fits, args)

    def keep(name, m, reps, ph, fam):
        r = dict(m, phase=ph, family=fam, boots=reps, meta=meta)
        if part_dir:
            json.dump(r, open(os.path.join(part_dir, f'{ph}__{name}.json'), 'w', encoding='utf-8'), ensure_ascii=False, default=float)
        res[name] = r
    if workers > 1 and len(need) > 1:                             # процессы «spawn»: без унаследованных потоков OpenMP и BLAS
        import multiprocessing as mp
        with mp.get_context('spawn').Pool(workers, initializer=_pool_init, initargs=(fits, args)) as pool:
            for (fam, ph, _, _), (name, m, reps) in zip(need, pool.imap(_env_job, need)):
                keep(name, m, reps, ph, fam)
    else:
        for job in need:
            name, m, reps = _env_job(job)
            keep(name, m, reps, job[1], job[0])
    boots = {}
    for ph, name, _ in todo:
        r = dict(res[name])
        boots[name] = {k: np.array(v, float) for k, v in r.pop('boots').items()}
        r.pop('meta', None)
        out['envs'][name] = r
    for rule, (fam, ph, meas, kind, part_b, shift) in RULES.items():
        names = sorted(n for n, e in out['envs'].items() if e['family'] == fam and e['phase'] == ph and np.isfinite(e['point'][meas]))
        pts = {n: out['envs'][n]['point'][meas] for n in names}
        sds = {n: out['envs'][n]['sd'][meas] for n in names}
        e = family_rule(pts, {n: boots[n][meas] for n in names}, sds, names, kind, part_b, shift) if len(names) >= 2 else dict(
            verdict_rule='не определено (сред мало)', names=names)
        e.update(active=RULES_ACTIVE[rule], measure=meas, shift=shift, names=names, fragile=fragility(out['envs'], names, meas))
        if meas in ('m1', 'm1_phi', 'm2') and names:
            e['lambda_sens'] = {lam: float(np.mean([out['envs'][n]['lambda_sens'][lam][meas] for n in names])) for lam in
                                out['envs'][names[0]]['lambda_sens']}
        out['rules'][rule] = e
    for meas in DESCR_MEAS:
        for fam in ('thousands', 'length'):
            names = sorted(n for n, e in out['envs'].items() if e['family'] == fam and e['phase'] == 'test5' and np.isfinite(e['point'][meas]))
            if len(names) >= 2:
                out['descr'][f'{fam} {meas}'] = C4.mean_entry({n: out['envs'][n]['point'][meas] for n in names},
                                                              {n: boots[n][meas] for n in names}, names, C4.DESCR_LEVEL)
    out['verdicts'] = {r: out['rules'][r].get('verdict_rule') for r in RULES}
    if not no_time:
        out['seconds'] = round(time.time() - t0, 1)
    json.dump(out, open(dst, 'w', encoding='utf-8'), ensure_ascii=False, indent=1, default=float)
    print('вердикт DISTILL-02:', {r: (v, out['rules'][r]['active']) for r, v in out['verdicts'].items()},
          '' if no_time else f"| время {out['seconds']} с", flush=True)
    return out


def main(a):
    if not a:
        sys.exit(__doc__)
    if a[0] == 'merge4':                                          # сборка фаз OCDIV-04 (тем же кодом, что в OCDIV-04)
        C4.merge4(a[1], a[2], a[3], a[4:])
    elif a[0] == 'merge2':                                        # сборка фаз OCDIV-02/03 (`ocdiv2.merge`)
        W.merge(a[1], a[2], a[3], a[4:])
    elif a[0] == 'merge_d2':                                      # сборка свежих фаз DISTILL-02 (test5, new5)
        merge_d2(a[1], a[2], a[3], a[4:])
    elif a[0] == 'pilot3':                                        # пилот 3 (совет 74); пилот 2 — код коммита e5785e6a
        spec = json.load(open(a[2], encoding='utf-8'))
        pilot_sets(a[1], {k: (v[0], v[1]) for k, v in spec['fit'].items()}, {k: (v[0], v[1], v[2]) for k, v in spec['eval'].items()},
                   R=spec.get('R', 20), B=spec.get('B', 200))
    elif a[0] == 'test':
        spec = json.load(open(a[2], encoding='utf-8'))            # {"construction": {fam: [dirs]}, "test": {фаза: [dirs]}, ...}
        test_d2(a[1], spec['construction'], spec['test'], B=spec.get('B', B_TEST), R=spec.get('R', R_TEST), part_dir=spec.get('part_dir'),
                only=spec.get('only'), no_time=spec.get('no_time', False), workers=spec.get('workers', 1))
    elif a[0] == 'pilot':
        spec = json.load(open(a[2], encoding='utf-8'))            # {"fit": {ключ: [dir, [среды] | null]}, "eval": {имя: [ключ, [dirs], [среды] | null]}}
        pilot(a[1], {k: (v[0], v[1]) for k, v in spec['fit'].items()}, {k: (v[0], v[1], v[2]) for k, v in spec['eval'].items()},
              R=spec.get('R', 50))
    else:
        sys.exit(__doc__)


if __name__ == '__main__':
    main(sys.argv[1:])
