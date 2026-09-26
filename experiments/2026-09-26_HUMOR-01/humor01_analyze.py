# HUMOR-01: анализ (AUC, бутстрап, Холм) и расчёт мощности. Один и тот же код для прогона и моделирования.
#   python3 humor01_analyze.py power            -> power.json (до прогона)
#   python3 humor01_analyze.py round0 <dir>     -> power_round0.json (после раунда 0, только справочно)
#   python3 humor01_analyze.py run <dir>        -> results.json
import json, sys, math
from collections import Counter
import numpy as np
from humor01_plan import (SEED_BOOT, SEED_POWER, HELD_TOPICS, TRAIN_TOPICS, TRAIN_JUDGES, JURY, CONTROLS, words, accepted)

B_MAIN = 10000


def boot_auc(mats, idx):
    """mats: {topic: матрица nA×nB средних по судьям баллов за A}; idx: {topic: (ia (B,nA'), ib (B,nB'))} -> AUC по повторам (B,)."""
    per = []
    for t, M in mats.items():
        ia, ib = idx[t]
        per.append(M[ia[:, :, None], ib[:, None, :]].mean(axis=(1, 2)))
    return np.mean(per, axis=0)


def resample(rng, sizes, B):
    """sizes: {cond: {topic: n}} -> одинаковые индексы шуток условия во всех сравнениях, где оно участвует."""
    return {c: {t: rng.integers(0, n, size=(B, n)) for t, n in d.items()} for c, d in sizes.items()}


def comp_boot(S, conds, sizes, B, seed):
    """S: {comp: (condA, condB, {topic: (J, nA, nB)})}. Возвращает точечные AUC и повторы (темы фиксированы, шутки
    каждого условия пересэмплируются независимо внутри темы, общие для сравнений)."""
    rng = np.random.default_rng(seed)
    R = resample(rng, sizes, B)
    point, reps = {}, {}
    for comp, (ca, cb, mats) in S.items():
        mean = {t: m.mean(axis=0) for t, m in mats.items()}
        point[comp] = float(np.mean([m.mean() for m in mean.values()]))
        reps[comp] = boot_auc(mean, {t: (R[ca][t], R[cb][t]) for t in mats})
    return point, reps


def p_one(x):  # доля повторов ≤ 0
    return float(np.mean(x <= 0))


def ci(x):
    return [float(np.quantile(x, 0.025)), float(np.quantile(x, 0.975))]


def binom_p(k, n):  # точное одностороннее P(X ≥ k), p = 0,5
    return sum(math.comb(n, i) for i in range(k, n + 1)) / 2 ** n


def holm(ps, alpha=0.05):
    order = sorted(ps, key=lambda k: ps[k])
    ok, go = {}, True
    for r, k in enumerate(order):
        thr = alpha / (len(order) - r)
        go = go and ps[k] <= thr
        ok[k] = dict(p=ps[k], threshold=thr, passed=bool(go))
    return ok


def decide(point, reps, human):
    """P2, P4 — большее из двух односторонних бутстрап-p (с поправкой на A/A); P5 — точное биномиальное; Холм."""
    aa = np.abs(reps['BASE-BASE2'] - 0.5)
    ps = {}
    for P, comp in (('P2', 'MEMO-BASE'), ('P4', 'MEMO-NOFB')):
        d = reps[comp] - 0.5
        ps[P] = max(p_one(d), p_one(d - aa))
    ps['P5'] = binom_p(human[0], human[1])
    return holm(ps)


# ---------------------------------------------------------------- моделирование мощности
def solve_delta(auc, sig_taste, sig_noise, tie):
    from statistics import NormalDist
    z = NormalDist().inv_cdf((auc - tie / 2) / (1 - tie))
    return z * math.sqrt(2 * (1 + sig_taste ** 2 + sig_noise ** 2))


def simulate(rng, delta, sig_taste=0.5, sig_noise=1.0, tie=0.05, n=6, T=4, J=3, p_human=None, B=2000):
    conds = {'MEMO': delta, 'BASE': 0.0, 'BASE2': 0.0, 'NOFB': 0.0}
    q = {c: rng.normal(m, 1, size=(T, n)) for c, m in conds.items()}
    taste = {c: rng.normal(0, sig_taste, size=(J, T, n)) for c in conds}
    S = {}
    for comp, (a, b) in {'MEMO-BASE': ('MEMO', 'BASE'), 'MEMO-NOFB': ('MEMO', 'NOFB'), 'BASE-BASE2': ('BASE', 'BASE2')}.items():
        mats = {}
        for t in range(T):
            ua = q[a][t][None, :, None] + taste[a][:, t][:, :, None] + rng.normal(0, sig_noise, (J, n, n))
            ub = q[b][t][None, None, :] + taste[b][:, t][:, None, :] + rng.normal(0, sig_noise, (J, n, n))
            y = (ua > ub).astype(float)
            y[rng.random((J, n, n)) < tie] = 0.5
            mats[t] = y
        S[comp] = (a, b, mats)
    sizes = {c: {t: n for t in range(T)} for c in conds}
    point, reps = comp_boot(S, conds, sizes, B, int(rng.integers(1 << 31)))
    k = int(rng.binomial(20, p_human if p_human is not None else 0.5))
    return decide(point, reps, (k, 20))


def power(nsim=400, B=2000, auc=0.65, sig_taste=0.5, sig_noise=1.0, tie=0.05, seed=SEED_POWER):
    rng = np.random.default_rng(seed)
    out = {}
    for name, a, ph in (('alt', auc, auc), ('null', 0.5, 0.5)):
        d = solve_delta(a, sig_taste, sig_noise, tie)
        res = [simulate(rng, d, sig_taste, sig_noise, tie, p_human=ph, B=B) for _ in range(nsim)]
        out[name] = dict(delta=d, **{P: float(np.mean([r[P]['passed'] for r in res])) for P in ('P2', 'P4', 'P5')},
                         any=float(np.mean([any(r[P]['passed'] for P in r) for r in res])))
    return dict(nsim=nsim, B=B, auc=auc, sig_taste=sig_taste, sig_noise=sig_noise, tie=tie, n_per_cond=24, seed=seed, **out)


def round0_power(D):
    """После раунда 0: доля разброса оценок, приходящаяся на шутку (общая для судей), -> пересчёт мощности. Только справочно."""
    p1 = json.load(open(f'{D}/part1.json'))
    r0 = p1['rounds'][0]
    keys = [j['key'] for j in r0['jokes']]
    X = np.array([[(r0['scores'][jk].get(k) or {}).get('score', np.nan) for k in keys] for jk, _ in TRAIN_JUDGES], float)
    X = X - np.nanmean(X, axis=1, keepdims=True)
    joke = np.nanmean(X, axis=0)
    v_joke = max(np.nanvar(joke, ddof=1) - np.nanmean(np.nanvar(X, axis=0, ddof=1)) / X.shape[0], 1e-6)
    v_res = np.nanmean(np.nanvar(X, axis=0, ddof=1))
    s = math.sqrt(v_res / v_joke)  # шум судьи в единицах разброса качества шуток
    return dict(v_joke=float(v_joke), v_resid=float(v_res), sig_judge_rel=s,
                power=power(sig_taste=s * 0.5, sig_noise=s * math.sqrt(0.75)))


# ---------------------------------------------------------------- анализ прогона
def score_of(pres, resp):
    """1 — выбрана шутка условия A, 0 — другая, 0,5 — нет разбираемого ответа."""
    if resp is None or resp.get('choice') not in (1, 2): return 0.5
    return 1.0 if (resp['choice'] == 1) == pres['a_first'] else 0.0


def run(D):
    p1, p3 = json.load(open(f'{D}/part1.json')), json.load(open(f'{D}/part3.json'))
    P = json.load(open(f'{D}/plan3.json'))
    plan, J = P['plan'], P['jokes']
    ans, prob = {}, {}
    labels = sorted({r['label'] for r in p3['records']})
    for lb in labels:
        rec = accepted(p3['records'], lb)
        prob[lb] = rec.get('problem')
        for it in ((rec.get('response') or {}).get('items') or []): ans[(lb, it['id'])] = it
    res = dict(n_calls_meaning=len(labels), unparsed={}, flags={})
    hk, tk = [k for k, _ in HELD_TOPICS], [k for k, _ in TRAIN_TOPICS]
    comps = {'MEMO-BASE': ('MEMO', 'BASE'), 'MEMO-NOFB': ('MEMO', 'NOFB'), 'BASE-BASE2': ('BASE', 'BASE2'),
             'R4-R0': ('R4', 'R0'), 'R4-NOFB4': ('R4', 'NOFB4')}

    def mats(comp, judges, prefix, topics, only=None):
        ca, cb = comps[comp]
        out = {t: np.full((len(judges), len(J[ca][t]), len(J[cb][t])), np.nan) for t in topics}
        for n, jk in enumerate(judges):
            call = f'{prefix}{jk}'
            for p in plan:
                if p['call'] == call and p.get('kind') == 'main' and p['comp'] == comp and (only is None or only(p)):
                    out[p['topic']][n, p['a'], p['b']] = score_of(p, ans.get((call, p['id'])))
        return out

    jury = [k for k, _ in JURY]
    trj = [k for k, _ in TRAIN_JUDGES]
    # доля неразбираемых
    for lb in labels:
        ps = [p for p in plan if p['call'] == lb and p.get('kind') in ('main', 'repeat', 'control')]
        if ps: res['unparsed'][lb] = sum(1 for p in ps if (lb, p['id']) not in ans or ans[(lb, p['id'])].get('choice') not in (1, 2)) / len(ps)
    # контроли жюри: сильная выбрана в обоих порядках каждой контрольной пары
    flagged = {}
    for lb in labels:
        if not lb.startswith('J:'): continue
        bad = False
        for s, w in {(p['strong'], p['weak']) for p in plan if p['call'] == lb and p.get('kind') == 'control'}:
            for p in plan:
                if p['call'] == lb and p.get('kind') == 'control' and p['strong'] == s:
                    if score_of(p, ans.get((lb, p['id']))) != 1.0: bad = True
        flagged[lb] = bad
    res['flags']['jury'] = flagged
    # основной перенос
    S = {c: (comps[c][0], comps[c][1], mats(c, jury, f'J:{c}:', hk)) for c in ('MEMO-BASE', 'MEMO-NOFB', 'BASE-BASE2')}
    sizes = {c: {t: len(J[c][t]) for t in hk} for c in ('MEMO', 'BASE', 'BASE2', 'NOFB')}
    for c, (_, _, m) in S.items():
        for t in m: m[t] = np.where(np.isnan(m[t]), 0.5, m[t])
    point, reps = comp_boot(S, None, sizes, B_MAIN, SEED_BOOT)
    res['auc'] = {c: dict(point=point[c], ci95=ci(reps[c]), per_topic={t: float(S[c][2][t].mean()) for t in hk},
                          per_judge={jk: float(np.mean([S[c][2][t][n].mean() for t in hk])) for n, jk in enumerate(jury)}) for c in S}
    human = json.load(open(f'{D}/human_answers.json')) if __import__('os').path.exists(f'{D}/human_answers.json') else None
    hk_ = (human['memo_wins'], human['n']) if human else (0, 20)
    res['holm'] = decide(point, reps, hk_)
    res['human'] = human
    # устойчивость: без помеченных судей жюри
    Sx = {}
    for c, (a, b, m) in S.items():
        keep = [n for n, jk in enumerate(jury) if not flagged.get(f'J:{c}:{jk}')]
        Sx[c] = (a, b, {t: m[t][keep] for t in m}) if keep else None
    if all(Sx.values()):
        px, rx = comp_boot(Sx, None, sizes, B_MAIN, SEED_BOOT)
        res['robust_unflagged'] = {c: dict(point=px[c], ci95=ci(rx[c])) for c in Sx}
    # длина: доля побед более длинной; AUC по парам с разницей длин ≤ 20 %
    longer, near = [], {c: [] for c in S}
    for p in plan:
        if p.get('kind') != 'main' or not p['call'].startswith('J:'): continue
        ca, cb = comps[p['comp']]
        la, lb_ = words(J[ca][p['topic']][p['a']]), words(J[cb][p['topic']][p['b']])
        s = score_of(p, ans.get((p['call'], p['id'])))
        if la != lb_ and s != 0.5: longer.append(s if la > lb_ else 1 - s)
        if abs(la - lb_) / max(la, lb_, 1) <= 0.2: near[p['comp']].append(s)
    res['length'] = dict(longer_wins=float(np.mean(longer)) if longer else None, n=len(longer),
                         auc_len20={c: (float(np.mean(v)) if v else None, len(v)) for c, v in near.items()},
                         mean_words={c: float(np.mean([words(x) for t in J[c] for x in J[c][t]])) for c in J})
    # согласие порядков (24 повторные пары)
    agree = {}
    for lb in labels:
        if not lb.startswith('J:'): continue
        first = {(p['pair']): p for p in plan if p['call'] == lb and p.get('kind') == 'main'}
        ag = []
        for p in plan:
            if p['call'] == lb and p.get('kind') == 'repeat':
                s1, s2 = score_of(first[p['pair']], ans.get((lb, first[p['pair']]['id']))), score_of(p, ans.get((lb, p['id'])))
                if s1 != 0.5 and s2 != 0.5: ag.append(s1 == s2)
        agree[lb] = (float(np.mean(ag)) if ag else None, len(ag))
    res['order_agreement'] = agree
    # позиционный сдвиг: доля выбора первой шутки
    firsts = [it['choice'] == 1 for (lb, _), it in ans.items() if lb.startswith(('J:', 'F:')) and it.get('choice') in (1, 2)]
    res['first_chosen'] = float(np.mean(firsts)) if firsts else None
    # P1, P3: финальная проверка раунд 4 против раунда 0
    Mt = mats('R4-R0', trj, 'F:', tk); Mj = mats('R4-R0', jury, 'F:', tk)
    Mn = mats('R4-NOFB4', trj, 'F:', tk)
    for m in (Mt, Mj, Mn):
        for t in m: m[t] = np.where(np.isnan(m[t]), 0.5, m[t])
    sz = {c: {t: len(J[c][t]) for t in tk} for c in ('R4', 'R0', 'NOFB4')}
    pt, rt = comp_boot({'train': ('R4', 'R0', Mt), 'jury': ('R4', 'R0', Mj), 'r4_nofb4': ('R4', 'NOFB4', Mn)}, None, sz, B_MAIN, SEED_BOOT + 1)
    res['P1'] = dict(auc=pt['train'], ci95=ci(rt['train']), p=p_one(rt['train'] - 0.5), confirmed=p_one(rt['train'] - 0.5) < 0.05)
    d = rt['train'] - rt['jury']
    res['P3'] = dict(diff=pt['train'] - pt['jury'], auc_jury=pt['jury'], ci95=ci(d), p=p_one(d), confirmed=p_one(d) < 0.05)
    res['R4_vs_NOFB4_train'] = dict(auc=pt['r4_nofb4'], ci95=ci(rt['r4_nofb4']))
    # средние оценки раундов и контроли судей обучения
    means, tflags = [], []
    ctl = {c['key']: c['kind'] for c in CONTROLS}
    for r in p1['rounds']:
        rk = {j['key'] for j in r['jokes']}
        row = {}
        fl = {}
        for jk in trj:
            sc = r['scores'][jk]
            row[jk] = float(np.mean([v['score'] for k, v in sc.items() if k in rk and v]))
            st = [v['score'] for k, v in sc.items() if ctl.get(k) == 'strong' and v]
            wk = [v['score'] for k, v in sc.items() if ctl.get(k) == 'weak' and v]
            fl[jk] = not (st and wk and np.mean(st) > np.mean(wk))
        nk = [k for k in r['scores'][trj[0]] if k.startswith('N')]
        if nk: row['NOFB4'] = float(np.mean([r['scores'][jk][k]['score'] for jk in trj for k in nk if r['scores'][jk].get(k)]))
        means.append(dict(r=r['r'], **row)); tflags.append(dict(r=r['r'], judges=fl, round_flagged=all(fl.values())))
    res['round_means'], res['flags']['train'] = means, tflags
    # разнообразие приёмов (энтропия, бит) и архивист
    lab = accepted(p3['records'], 'LABEL'); la = {it['id']: it['technique'] for it in ((lab or {}).get('response') or {}).get('items', [])}
    div = {}
    for c in ('R0', 'R4', 'MEMO', 'BASE', 'NOFB'):
        cnt = Counter(la.get(p['id']) for p in plan if p['call'] == 'LABEL' and p['cond'] == c)
        cnt.pop(None, None)
        n = sum(cnt.values())
        div[c] = dict(entropy=float(-sum(v / n * math.log2(v / n) for v in cnt.values())) if n else None, distinct=len(cnt), counts=dict(cnt))
    res['diversity'] = div
    arc = accepted(p3['records'], 'ARCHIVE'); ka = {it['id']: it['known'] for it in ((arc or {}).get('response') or {}).get('items', [])}
    res['archive'] = {c: float(np.mean([ka[p['id']] for p in plan if p['call'] == 'ARCHIVE' and p['cond'] == c and p['id'] in ka] or [np.nan]))
                      for c in ('MEMO', 'BASE', 'BASE2', 'NOFB', 'CTRL')}
    res['archive_controls'] = {p['topic']: ka.get(p['id']) for p in plan if p['call'] == 'ARCHIVE' and p['cond'] == 'CTRL'}
    res['problems'] = {k: v for k, v in prob.items() if v}
    return res


if __name__ == '__main__':
    cmd = sys.argv[1]
    if cmd == 'power':
        out = dict(prereg_auc065=power(), extra_auc075=power(auc=0.75))  # 0,75 — справочно
        json.dump(out, open('power.json', 'w'), ensure_ascii=False, indent=1); print(json.dumps(out, ensure_ascii=False, indent=1))
    elif cmd == 'round0':
        out = round0_power(sys.argv[2])
        json.dump(out, open(f'{sys.argv[2]}/power_round0.json', 'w'), ensure_ascii=False, indent=1); print(json.dumps(out, ensure_ascii=False, indent=1))
    elif cmd == 'run':
        out = run(sys.argv[2])
        json.dump(out, open(f'{sys.argv[2]}/results.json', 'w'), ensure_ascii=False, indent=1); print(json.dumps(out, ensure_ascii=False, indent=1)[:6000])
