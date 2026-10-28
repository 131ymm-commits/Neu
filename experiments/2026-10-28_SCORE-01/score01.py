#!/usr/bin/env python3
"""SCORE-01: обвязка. Головы — только через tools/run_sealed2.py (claude -p --tools "", пустая папка).
  python3 score01.py jobs <этап> <выборка> [n]        → run/<этап>_jobs.jsonl (руки LOG и WIN, по одному вызову на задачу)
  python3 score01.py truth <выборка>                  → truth/<выборка>.json: правда 8 кандидатов и фактически лучший
  python3 score01.py metrics <этап> <выборка> <выгрузка run_sealed2 export> → evals/<этап>.json и печать мер по рукам
Выборки: pilot — WH 7001–7012 и 7301–7312 SELECT-01 (их соль утрачена; своя соль pilot_salt.txt);
main — WH 8001–8100 (salts/main_salt.txt SELECT-01); rep — WH 8101–8200 (salts/rep_salt.txt). Задача без пула пропускается.
Порядок кандидатов у голов — одна перестановка на задачу по sha256(сид|perm), как в SELECT-01 (общая для рук).
Ничьи: у правды и у argmax вероятностей — по sha256(задача|кандидат), меньший хеш выигрывает."""
import hashlib
import json
import math
import os
import random
import secrets
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SEL = os.path.join(HERE, '..', '2026-10-07_SELECT-01')
sys.path.insert(0, SEL)
sys.path.insert(0, HERE)
import sim  # noqa: E402  (симулятор WH SELECT-01)
import prompts_score as P  # noqa: E402

ARMS = ('LOG', 'WIN')
P_FLOOR = 1e-6


def sample_tasks(name):
    ids = {'pilot': list(range(7001, 7013)) + list(range(7301, 7313)), 'main': list(range(8001, 8101)),
           'rep': list(range(8101, 8201))}[name]
    return [f'WH_{s}' for s in ids if os.path.exists(os.path.join(SEL, 'pools', f'WH_{s}.json'))]


def salt(name):
    if name == 'pilot':
        p = os.path.join(HERE, 'pilot_salt.txt')
        if not os.path.exists(p):
            open(p, 'w').write(secrets.token_hex(32))
        return open(p).read().strip()
    return open(os.path.join(SEL, 'salts', f'{name}_salt.txt')).read().strip()


task = lambda t: json.load(open(os.path.join(SEL, 'tasks', f'{t}.json')))
pool = lambda t: json.load(open(os.path.join(SEL, 'pools', f'{t}.json')))
hkey = lambda t, i: hashlib.sha256(f'{t}|{i}'.encode()).hexdigest()


def perm(t, k=8):
    p = list(range(k))
    random.Random(int(hashlib.sha256(f'{task(t)["seed"]}|perm'.encode()).hexdigest()[:16], 16)).shuffle(p)
    return p


def argmax_tie(t, xs):
    m = max(xs)
    return min((i for i, x in enumerate(xs) if x == m), key=lambda i: hkey(t, i))


def cmd_jobs(stage, sample, n=None):
    os.makedirs(os.path.join(HERE, 'run'), exist_ok=True)
    ts = sample_tasks(sample)[:int(n) if n else None]
    path = os.path.join(HERE, 'run', f'{stage}_jobs.jsonl')
    with open(path, 'w', encoding='utf-8') as fh:
        for t in ts:
            tk, pl, pm = task(t), pool(t), perm(t)
            shown = [pl[j] for j in pm]
            for arm in ARMS:
                fh.write(json.dumps(dict(task=t, id=f'{t}|{arm}|0', arm=arm, prompt=P.prompt(arm, sim.RULES['WH'](tk), shown),
                                         schema=P.SCHEMA), ensure_ascii=False) + '\n')
    print(path, len(ts) * len(ARMS), 'заданий;', len(ts), 'задач;', 'хеши промпта:', P.hashes())


def cmd_truth(sample):
    os.makedirs(os.path.join(HERE, 'truth'), exist_ok=True); s = salt(sample); out = {}
    for t in sample_tasks(sample):
        tr = [sim.truth(task(t), c['plan'], s) for c in pool(t)]
        out[t] = dict(truth=tr, best=argmax_tie(t, tr))
    json.dump(dict(sample=sample, salt_sha256=hashlib.sha256(s.encode()).hexdigest(), tasks=out),
              open(os.path.join(HERE, 'truth', f'{sample}.json'), 'w'), indent=0)
    print('правда:', len(out), 'задач')


def valid_p(res):
    p = (res or {}).get('p')
    if not isinstance(p, list) or len(p) != 8 or any(not isinstance(x, (int, float)) or x < 0 or math.isnan(x) for x in p):
        return None
    s = sum(p)
    return [x / s for x in p] if s > 0 else None


def cmd_metrics(stage, sample, export):
    tru = json.load(open(os.path.join(HERE, 'truth', f'{sample}.json')))['tasks']
    rec = {r['id']: r for r in map(json.loads, open(export, encoding='utf-8'))}
    rows = {}
    for jid, r in rec.items():
        t, arm, _ = jid.split('|'); pm = perm(t); best = tru[t]['best']
        ps = valid_p(r.get('result'))
        row = dict(task=t, arm=arm, valid=ps is not None, error=r.get('error'), inp=r.get('inp', 0), out=r.get('out', 0),
                   cost=r.get('cost_usd'), models=r.get('models'))
        if ps is not None:
            pp = [0.0] * 8
            for i, x in enumerate(ps):
                pp[pm[i]] = x                                     # показанный i → кандидат пула pm[i]
            ch = argmax_tie(t, pp); conf = max(pp)
            row.update(p=pp, choice=ch, best=best, acc=int(ch == best), conf=conf, p_best=pp[best],
                       logloss=-math.log(max(pp[best], P_FLOOR)), floored=pp[best] < P_FLOOR,
                       brier=sum((x - (1.0 if i == best else 0.0)) ** 2 for i, x in enumerate(pp)),
                       regret=(tru[t]['truth'][best] - tru[t]['truth'][ch]))
        rows[jid] = row
    summ = {}
    for arm in ARMS:
        v = [x for x in rows.values() if x['arm'] == arm and x['valid']]
        if not v:
            continue
        mean = lambda k: sum(x[k] for x in v) / len(v)
        bins = {}
        for x in v:
            bins.setdefault(min(int(x['conf'] * 5), 4), []).append(x)
        ece = sum(len(b) / len(v) * abs(sum(x['conf'] for x in b) / len(b) - sum(x['acc'] for x in b) / len(b)) for b in bins.values())
        summ[arm] = dict(n=len(v), invalid=sum(1 for x in rows.values() if x['arm'] == arm and not x['valid']),
                         logloss=mean('logloss'), acc=mean('acc'), conf=mean('conf'), self_dec=mean('conf') - mean('acc'),
                         brier=mean('brier'), ece=ece, p_best=mean('p_best'), floored=sum(x['floored'] for x in v),
                         inp=mean('inp'), out=mean('out'),
                         cost=(sum(x['cost'] or 0 for x in v) / len(v)) if any(x['cost'] for x in v) else None)
    pair = {}
    for t in sorted({x['task'] for x in rows.values()}):
        a, b = rows.get(f'{t}|LOG|0'), rows.get(f'{t}|WIN|0')
        if a and b and a['valid'] and b['valid']:
            pair[t] = {k: b[k] - a[k] for k in ('logloss', 'acc', 'conf', 'brier')}
            pair[t]['self_dec'] = (b['conf'] - b['acc']) - (a['conf'] - a['acc'])
    pd = {}
    for k in ('logloss', 'acc', 'conf', 'brier', 'self_dec'):
        d = [x[k] for x in pair.values()]
        if len(d) > 1:
            m = sum(d) / len(d); sd = math.sqrt(sum((x - m) ** 2 for x in d) / (len(d) - 1))
            pd[k] = dict(n=len(d), mean=m, sd=sd)
    os.makedirs(os.path.join(HERE, 'evals'), exist_ok=True)
    json.dump(dict(stage=stage, sample=sample, rows=rows, summary=summ, paired_WIN_minus_LOG=pd),
              open(os.path.join(HERE, 'evals', f'{stage}.json'), 'w'), ensure_ascii=False, indent=1)
    for arm, s in summ.items():
        print(arm, {k: (round(v, 4) if isinstance(v, float) else v) for k, v in s.items()})
    print('WIN − LOG по задачам:', {k: {kk: round(vv, 4) if isinstance(vv, float) else vv for kk, vv in v.items()} for k, v in pd.items()})


if __name__ == '__main__':
    c = sys.argv[1]
    if c == 'jobs':
        cmd_jobs(*sys.argv[2:])
    elif c == 'truth':
        cmd_truth(sys.argv[2])
    elif c == 'metrics':
        cmd_metrics(*sys.argv[2:5])
    else:
        sys.exit(__doc__)
