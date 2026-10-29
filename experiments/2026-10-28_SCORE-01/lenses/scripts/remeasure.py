# Независимый пересчёт мер вызова SCORE-01 из сырых выгрузок run_sealed2 (проверяльщик, линза 2).
import hashlib, json, math, random, sys
SC = '/home/claude/neu/experiments/2026-10-28_SCORE-01'
SEL = '/home/claude/neu/experiments/2026-10-07_SELECT-01'
def perm(t):
    seed = json.load(open(f'{SEL}/tasks/{t}.json'))['seed']
    p = list(range(8)); random.Random(int(hashlib.sha256(f'{seed}|perm'.encode()).hexdigest()[:16], 16)).shuffle(p); return p
def measures(p_shown, t, top):
    pm = perm(t)
    q = [None] * 8
    for i, x in enumerate(p_shown): q[pm[i]] = float(x)     # показанный i → пул pm[i]
    y = [1 if i in top else 0 for i in range(8)]
    acc = sum(0.5 if x == 0.5 else (1.0 if (x > 0.5) == (l == 1) else 0.0) for x, l in zip(q, y)) / 8
    conf = sum(max(x, 1 - x) for x in q) / 8
    brier = sum((x - l) ** 2 for x, l in zip(q, y)) / 8
    ll = sum(-math.log(max(x if l else 1 - x, 1e-6)) for x, l in zip(q, y)) / 8
    pos = [x for x, l in zip(q, y) if l]; neg = [x for x, l in zip(q, y) if not l]
    auc = sum(1.0 if a > b else 0.5 if a == b else 0.0 for a in pos for b in neg) / 16
    ioi = (1 - acc) + max(0.0, conf - acc)
    return dict(acc=acc, conf=conf, self_dec=conf - acc, brier=brier, logloss=ll, auc=auc, ioi=ioi, labels=y)
def valid(res):
    p = (res or {}).get('p')
    return p if isinstance(p, list) and len(p) == 8 and all(isinstance(x, (int, float)) and 0 <= x <= 1 for x in p) else None
if __name__ == '__main__':
    model = sys.argv[1]
    top = {t: set(v['top4_4000']) for t, v in json.load(open(f'{SC}/truth/check_pilot.json'))['tasks'].items()}
    E = json.load(open(f'{SC}/evals/pilot12_{model}.json'))['rows']
    recs = []
    for f in (f'{SC}/run/pilot1_{model}_out.jsonl', f'{SC}/run/pilot2_{model}_out.jsonl'):
        recs += [json.loads(l) for l in open(f, encoding='utf-8')]
    maxdiff = {}; nval = 0; miss = 0
    for r in recs:
        t = r['id'].split('|')[0]; p = valid(r.get('result'))
        row = E.get(r['id'])
        if row is None: miss += 1; continue
        if p is None:
            assert not row['valid']; continue
        nval += 1
        m = measures(p, t, top[t])
        assert m['labels'] == row['labels'], (r['id'], m['labels'], row['labels'])
        for k in ('acc', 'conf', 'brier', 'logloss', 'auc', 'ioi'):
            maxdiff[k] = max(maxdiff.get(k, 0), abs(m[k] - row[k]))
        maxdiff['self_dec'] = max(maxdiff.get('self_dec', 0), abs(m['self_dec'] - (row['conf'] - row['acc'])))
        maxdiff['out'] = max(maxdiff.get('out', 0), abs(r.get('out', 0) - row['out']))
    print(model, 'записей', len(recs), 'годных', nval, 'нет в evals', miss, 'наиб. расхождение:', {k: f'{v:.2e}' for k, v in maxdiff.items()})
