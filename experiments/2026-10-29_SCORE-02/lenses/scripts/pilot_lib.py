# Независимый пересчёт мер пилота SCORE-02 из выгрузок журналов (своя выгрузка совпала байт в байт), своя перестановка,
# свой AUC второго рода (попарный перебор, ничьи — ½), свой бутстреп задач (Python random, своё зерно), своя мощность.
import hashlib, json, math, os, random, sys, collections
from statistics import NormalDist
ROOT = '/home/claude/neu'; EXP = f'{ROOT}/experiments'; S2 = f'{EXP}/2026-10-29_SCORE-02'; SEL = f'{EXP}/2026-10-07_SELECT-01'
SP = '/tmp/claude-0/-home-claude/8c9bf095-e181-55d3-b75e-353e8e0f2d42/scratchpad/lenses_score02'
lab = {t: set(v['top4_4000']) for t, v in json.load(open(f'{EXP}/2026-10-28_SCORE-01/truth/check_pilot.json'))['tasks'].items()}
def myperm(t):
    seed = json.load(open(f'{SEL}/tasks/{t}.json'))['seed']
    p = list(range(8)); random.Random(int(hashlib.sha256(f'{seed}|perm'.encode()).hexdigest()[:16], 16)).shuffle(p); return p
def load_calls(path):
    calls = collections.defaultdict(dict)
    for r in map(json.loads, open(path, encoding='utf-8')):
        t, arm, k = r['id'].split('|')
        res = r.get('result') or {}
        p = res.get('p') if isinstance(res, dict) else None
        ok = isinstance(p, list) and len(p) == 8 and all(isinstance(x, (int, float)) and 0 <= x <= 1 for x in p)
        if not ok:
            calls[t][int(k)] = None; continue
        pm = myperm(t); pool_p = [None] * 8
        for i, x in enumerate(p): pool_p[pm[i]] = float(x)
        calls[t][int(k)] = pool_p
    return calls
def judg(calls_t, L):
    ok = [p for k, p in sorted(calls_t.items()) if p is not None]
    out = dict(single=[], mean=[], agree=[])
    for i in range(8):
        y = i in L
        for p in ok:
            if p[i] != 0.5: out['single'].append((max(p[i], 1 - p[i]), (p[i] > 0.5) == y))
        m = sum(p[i] for p in ok) / len(ok)
        if m != 0.5: out['mean'].append((max(m, 1 - m), (m > 0.5) == y))
        up = sum(p[i] > 0.5 for p in ok); dn = sum(p[i] < 0.5 for p in ok)
        if up != dn: out['agree'].append((max(up, dn) / (up + dn), (up > dn) == y))
    return out
def auc_pairs(js):
    pos = [c for c, o in js if o]; neg = [c for c, o in js if not o]
    if not pos or not neg: return float('nan')
    s = 0.0
    for a in pos:
        for b in neg:
            s += 1.0 if a > b else (0.5 if a == b else 0.0)
    return s / (len(pos) * len(neg))
def auc_fast(js):  # тот же смысл, сортировкой (для бутстрепа)
    pos = sorted(c for c, o in js if o); neg = sorted(c for c, o in js if not o)
    if not pos or not neg: return float('nan')
    import bisect
    s = 0.0
    for a in pos:
        lo = bisect.bisect_left(neg, a); hi = bisect.bisect_right(neg, a); s += lo + 0.5 * (hi - lo)
    return s / (len(pos) * len(neg))
def meas(js, fast=False):
    if not js: return None
    c = [x for x, _ in js]; o = [1.0 if y else 0.0 for _, y in js]
    conf = sum(c) / len(c); acc = sum(o) / len(o)
    return dict(n=len(js), auc2=(auc_fast if fast else auc_pairs)(js), acc=acc, conf=conf, self_dec=conf - acc,
                brier=sum((a - b) ** 2 for a, b in zip(c, o)) / len(c))
SPECS = [('auc2', 'agree', 'single', -1, 'X1o/XE1h'), ('self_dec', 'agree', 'single', +1, 'X2'), ('acc', 'agree', 'single', +1, 'X3'),
         ('self_dec', 'mean', 'single', -1, 'X4'), ('auc2', 'mean', 'single', +1, 'XE1o/XE2h')]
