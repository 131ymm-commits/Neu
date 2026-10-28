#!/usr/bin/env python3
"""SCORE-01: обвязка. Головы — только через tools/run_sealed2.py (claude -p --tools "", пустая папка).
  python3 score01.py jobs <этап> <выборка> [n] [best|half] → run/<этап>_jobs.jsonl (руки LOG и WIN, по вызову на задачу;
                                                        формат best — «фактически лучший из 8», half — «в лучшей половине»)
  python3 score01.py truth <выборка>                  → truth/<выборка>.json: правда 8 кандидатов и фактически лучший
  python3 score01.py metrics <этап> <выборка> <выгрузка run_sealed2 export> [best|half] → evals/<этап>.json и меры по рукам
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
ARMS_ALL = ('LOG', 'WIN', 'NONE')          # NONE — без строки о правиле оплаты (добавлена после микропилота 1, только формат half)
PAIRS = (('WIN', 'LOG'), ('NONE', 'LOG'), ('WIN', 'NONE'))   # разность «первая − вторая» по задачам
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


def cmd_jobs(stage, sample, n=None, fmt='best', arms=None, rep='0'):
    """arms — через запятую (по умолчанию LOG,WIN); rep — номер повтора в id задания (по умолчанию 0)."""
    os.makedirs(os.path.join(HERE, 'run'), exist_ok=True)
    ts = sample_tasks(sample)[:int(n) if n and n != 'all' else None]
    arms = tuple(arms.split(',')) if arms else ARMS
    assert all(a in ARMS_ALL for a in arms) and (fmt == 'half' or 'NONE' not in arms), arms
    path = os.path.join(HERE, 'run', f'{stage}_jobs.jsonl')
    with open(path, 'w', encoding='utf-8') as fh:
        for t in ts:
            tk, pl, pm = task(t), pool(t), perm(t)
            shown = [pl[j] for j in pm]
            for arm in arms:
                pr = (P.prompt if fmt == 'best' else P.prompt_half)(arm, sim.RULES['WH'](tk), shown)
                fh.write(json.dumps(dict(task=t, id=f'{t}|{arm}|{rep}', arm=arm, prompt=pr, schema=P.SCHEMA if fmt == 'best' else P.SCHEMA_H),
                                    ensure_ascii=False) + '\n')
    print(path, len(ts) * len(arms), 'заданий;', len(ts), 'задач;', 'руки', arms, 'хеши промпта:', P.hashes())


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


def valid_half(res):
    p = (res or {}).get('p')
    if not isinstance(p, list) or len(p) != 8 or any(not isinstance(x, (int, float)) or math.isnan(x) or x < 0 or x > 1 for x in p):
        return None
    return [float(x) for x in p]


def auc(scores, labels):
    pos = [s for s, l in zip(scores, labels) if l]; neg = [s for s, l in zip(scores, labels) if not l]
    if not pos or not neg:
        return float('nan')
    return sum((a > b) + 0.5 * (a == b) for a in pos for b in neg) / (len(pos) * len(neg))


def cmd_metrics_half(stage, sample, export, labels='r1000'):
    """Формат «в лучшей половине»: метка кандидата — в четвёрке лучших по правде (ничьи — по sha256); меры по 8 ответам вызова.
    labels: r1000 — правда sim.truth (R = 1000, округление до 0,01; truth/<выборка>.json);
            r4000 — четвёрка по среднему 4000 реализаций (первые 1000 — те же; truth/check_<выборка>.json, truth_check.py)."""
    tru = json.load(open(os.path.join(HERE, 'truth', f'{sample}.json')))['tasks']
    top4000 = None
    if labels == 'r4000':
        top4000 = {t: set(v['top4_4000']) for t, v in json.load(open(os.path.join(HERE, 'truth', f'check_{sample}.json')))['tasks'].items()}
    rec = {}
    for ex in export.split(','):                      # несколько выгрузок через запятую (руки из разных прогонов)
        for r in map(json.loads, open(ex, encoding='utf-8')):
            assert r['id'] not in rec, f'повтор id {r["id"]} в выгрузках'
            rec[r['id']] = r
    rows, pts = {}, {a: [] for a in ARMS_ALL}
    for jid, r in rec.items():
        t, arm, _ = jid.split('|'); pm = perm(t); tr = tru[t]['truth']
        order = sorted(range(8), key=lambda i: (-tr[i], hkey(t, i))); top = set(order[:4]) if top4000 is None else top4000[t]
        ps = valid_half(r.get('result'))
        row = dict(task=t, arm=arm, valid=ps is not None, error=r.get('error'), inp=r.get('inp', 0), out=r.get('out', 0), cost=r.get('cost_usd'))
        if ps is not None:
            pp = [0.0] * 8
            for i, x in enumerate(ps):
                pp[pm[i]] = x
            lab = [int(i in top) for i in range(8)]
            ll = [-math.log(max(x if l else 1 - x, P_FLOOR)) for x, l in zip(pp, lab)]
            acc = [1.0 if (x > 0.5) == bool(l) and x != 0.5 else (0.5 if x == 0.5 else 0.0) for x, l in zip(pp, lab)]
            conf = [max(x, 1 - x) for x in pp]
            row.update(p=pp, labels=lab, logloss=sum(ll) / 8, brier=sum((x - l) ** 2 for x, l in zip(pp, lab)) / 8, acc=sum(acc) / 8,
                       conf=sum(conf) / 8, sum_p=sum(pp), auc=auc(pp, lab))
            # ИОИ вызова (experiments/truth.py): незнание 1 − T + самообман max(0, C − T), T — точность, C — уверенность
            row.update(ignorance=1 - row['acc'], deception=max(0.0, row['conf'] - row['acc']))
            row['ioi'] = row['ignorance'] + row['deception']
            pts[arm] += [(x, l, c, a) for x, l, c, a in zip(pp, lab, conf, acc)]
        rows[jid] = row
    summ = {}
    for arm in ARMS_ALL:
        v = [x for x in rows.values() if x['arm'] == arm and x['valid']]
        if not v:
            continue
        mean = lambda k: sum(x[k] for x in v) / len(v)
        P_ = pts[arm]; bins = {}
        for x, l, c, a in P_:
            bins.setdefault(min(int((c - 0.5) * 10), 4), []).append((c, a))
        ece = sum(len(b) / len(P_) * abs(sum(c for c, _ in b) / len(b) - sum(a for _, a in b) / len(b)) for b in bins.values())
        summ[arm] = dict(n=len(v), invalid=sum(1 for x in rows.values() if x['arm'] == arm and not x['valid']), logloss=mean('logloss'),
                         brier=mean('brier'), acc=mean('acc'), conf=mean('conf'), self_dec=mean('conf') - mean('acc'),
                         auc_pooled=auc([x for x, *_ in P_], [l for _, l, *_ in P_]), ece=ece, sum_p=mean('sum_p'),
                         n_half=sum(1 for x, *_ in P_ if x == 0.5), inp=mean('inp'), out=mean('out'),
                         ioi=mean('ioi'), ignorance=mean('ignorance'), deception=mean('deception'),
                         cost=(sum(x['cost'] or 0 for x in v) / len(v)) if any(x['cost'] for x in v) else None)
    paired = {}
    for hi, lo in PAIRS:
        if hi not in summ or lo not in summ:
            continue
        pair = {}
        for t in sorted({x['task'] for x in rows.values()}):
            a, b = rows.get(f'{t}|{lo}|0'), rows.get(f'{t}|{hi}|0')
            if a and b and a['valid'] and b['valid']:
                pair[t] = {k: b[k] - a[k] for k in ('logloss', 'acc', 'conf', 'brier', 'ioi')}
                pair[t]['self_dec'] = (b['conf'] - b['acc']) - (a['conf'] - a['acc'])
        pd = {}
        for k in ('logloss', 'acc', 'conf', 'brier', 'self_dec', 'ioi'):
            d = [x[k] for x in pair.values()]
            if len(d) > 1:
                m = sum(d) / len(d); sd = math.sqrt(sum((x - m) ** 2 for x in d) / (len(d) - 1))
                pd[k] = dict(n=len(d), mean=m, sd=sd)
        paired[f'{hi}_minus_{lo}'] = pd
    os.makedirs(os.path.join(HERE, 'evals'), exist_ok=True)
    json.dump(dict(stage=stage, sample=sample, format='half', labels=labels, rows=rows, summary=summ,
                   paired_WIN_minus_LOG=paired.get('WIN_minus_LOG', {}), paired=paired),
              open(os.path.join(HERE, 'evals', f'{stage}.json'), 'w'), ensure_ascii=False, indent=1)
    for arm, s_ in summ.items():
        print(arm, {k: (round(v, 4) if isinstance(v, float) else v) for k, v in s_.items()})
    for name, pd in paired.items():
        print(f'{name} по задачам:', {k: {kk: round(vv, 4) if isinstance(vv, float) else vv for kk, vv in v.items()} for k, v in pd.items()})


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
        fmt = sys.argv[5] if len(sys.argv) > 5 else 'best'
        if fmt == 'half':
            cmd_metrics_half(*sys.argv[2:5])
        elif fmt == 'half4':
            cmd_metrics_half(*sys.argv[2:5], labels='r4000')
        else:
            cmd_metrics(*sys.argv[2:5])
    else:
        sys.exit(__doc__)
