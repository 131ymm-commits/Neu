#!/usr/bin/env python3
"""Независимый пересчёт мер вызовов SCORE-01 (проверяющий; код опыта не импортируется).
Отображение «показанный i → кандидат пула» — разбором промпта задания и сличением плана с пулом SELECT-01.
Метки — top4_4000 из truth/check_<выборка>.json. Сравнение с evals/<этап>.json по каждому вызову и по рукам."""
import json, math, os, re, sys, pickle

EXP = '/home/claude/neu/experiments/2026-10-28_SCORE-01'
SEL = '/home/claude/neu/experiments/2026-10-07_SELECT-01'
OUT = os.path.dirname(os.path.abspath(__file__))
STAGES = ['main_opus', 'rep_opus', 'main_haiku', 'rep_haiku']
FLOOR = 1e-6
CAND = re.compile(r'^Кандидат (\d+): план (\{.*\})$', re.M)


def canon(o):
    return json.dumps(o, sort_keys=True, ensure_ascii=False)


def mapping_from_prompt(prompt, pool):
    found = CAND.findall(prompt)
    assert len(found) == 8, len(found)
    pool_c = [canon(c['plan']) for c in pool]
    m = []
    for i, (idx, js) in enumerate(found):
        assert int(idx) == i
        c = canon(json.loads(js))
        hits = [k for k, pc in enumerate(pool_c) if pc == c]
        assert len(hits) == 1, (i, hits)
        m.append(hits[0])
    assert sorted(m) == list(range(8))
    return m   # shown i -> pool m[i]


def call_measures(p_shown, mp, top4):
    pp = [None] * 8
    for i, x in enumerate(p_shown):
        pp[mp[i]] = float(x)
    lab = [1 if k in top4 else 0 for k in range(8)]
    acc_i = []
    for x, l in zip(pp, lab):
        if x == 0.5:
            acc_i.append(0.5)
        elif (x > 0.5 and l == 1) or (x < 0.5 and l == 0):
            acc_i.append(1.0)
        else:
            acc_i.append(0.0)
    acc = sum(acc_i) / 8
    conf = sum(max(x, 1 - x) for x in pp) / 8
    brier = sum((x - l) ** 2 for x, l in zip(pp, lab)) / 8
    ll = sum(-math.log(max(x if l else 1 - x, FLOOR)) for x, l in zip(pp, lab)) / 8
    pos = [x for x, l in zip(pp, lab) if l]
    neg = [x for x, l in zip(pp, lab) if not l]
    auc = sum((a > b) + 0.5 * (a == b) for a in pos for b in neg) / (len(pos) * len(neg))
    dec = max(0.0, conf - acc)
    return dict(p=pp, labels=lab, acc=acc, conf=conf, self_dec=conf - acc, brier=brier, logloss=ll, auc=auc,
                ignorance=1 - acc, deception=dec, ioi=(1 - acc) + dec, acc_items=acc_i)


def valid(res):
    p = (res or {}).get('p')
    if not isinstance(p, list) or len(p) != 8:
        return None
    for x in p:
        if isinstance(x, bool) or not isinstance(x, (int, float)) or x != x or x < 0 or x > 1:
            return None
    return p


def main():
    allrows = {}
    report = []
    for st in STAGES:
        sample = st.split('_')[0]
        jobs = [json.loads(l) for l in open(f'{EXP}/jobs/{st}_jobs.jsonl', encoding='utf-8')]
        top = {t: set(v['top4_4000']) for t, v in json.load(open(f'{EXP}/truth/check_{sample}.json'))['tasks'].items()}
        maps = {}
        for j in jobs:
            t = j['task']
            pool = json.load(open(f'{SEL}/pools/{t}.json'))
            m = mapping_from_prompt(j['prompt'], pool)
            if t in maps:
                assert maps[t] == m, f'перестановка различается внутри задачи {t}'
            maps[t] = m
        out = {}
        for l in open(f'{EXP}/run/{st}_out.jsonl', encoding='utf-8'):
            r = json.loads(l)
            assert r['id'] not in out
            out[r['id']] = r
        ids = {j['id'] for j in jobs}
        rows = {}
        for jid, r in out.items():
            t, arm, rep = jid.split('|')
            p = valid(r.get('result'))
            row = dict(task=t, arm=arm, rep=rep, valid=p is not None, out=r.get('out'), inp=r.get('inp'),
                       cost=r.get('cost_usd'), thinking=r.get('thinking'), models=r.get('models'))
            if p is not None:
                row.update(call_measures(p, maps[t], top[t]))
            rows[jid] = row
        allrows[st] = rows
        # сравнение с evals
        E = json.load(open(f'{EXP}/evals/{st}.json'))
        assert E['labels'] == 'r4000'
        maxdiff = {}
        nmis = 0
        for jid, row in rows.items():
            e = E['rows'][jid]
            assert e['valid'] == row['valid']
            if not row['valid']:
                continue
            if e['labels'] != row['labels']:
                nmis += 1
            for k in ('acc', 'conf', 'brier', 'logloss', 'auc', 'ioi', 'ignorance', 'deception', 'out'):
                d = abs(float(e[k]) - float(row[k]))
                maxdiff[k] = max(maxdiff.get(k, 0), d)
            d = max(abs(a - b) for a, b in zip(e['p'], row['p']))
            maxdiff['p'] = max(maxdiff.get('p', 0), d)
        report.append(f'{st}: заданий {len(ids)}, выгружено {len(out)}, лишних {len(set(out) - ids)}, нет записи {len(ids - set(out))}, '
                      f'годных {sum(r["valid"] for r in rows.values())}; расхождений меток {nmis}; '
                      f'наибольшая |разность| с evals: ' + ', '.join(f'{k} {v:.2e}' for k, v in maxdiff.items()))
        # сводка по рукам
        for arm in ('LOG', 'WIN', 'NONE'):
            v = [r for r in rows.values() if r['arm'] == arm and r['valid']]
            mean = lambda k: sum(r[k] for r in v) / len(v)
            pts = [(x, l) for r in v for x, l in zip(r['p'], r['labels'])]
            pos = [x for x, l in pts if l]; neg = [x for x, l in pts if not l]
            # AUC по всем — через сортировку (ранги со средними на ничьих)
            allv = sorted(set(x for x, _ in pts))
            from collections import Counter
            cp, cn = Counter(pos), Counter(neg)
            below_neg = 0; num = 0.0
            for x in allv:
                num += cp[x] * (below_neg + 0.5 * cn[x])
                below_neg += cn[x]
            aucp = num / (len(pos) * len(neg))
            s = E['summary'][arm]
            mine = dict(n=len(v), acc=mean('acc'), conf=mean('conf'), self_dec=mean('conf') - mean('acc'), brier=mean('brier'),
                        logloss=mean('logloss'), auc_pooled=aucp, ioi=mean('ioi'), ignorance=mean('ignorance'),
                        deception=mean('deception'), out=mean('out'), cost=sum(r['cost'] or 0 for r in v) / len(v))
            diffs = {k: abs(mine[k] - s[k]) for k in mine if k in s and s[k] is not None}
            report.append(f'  {st} {arm}: n {mine["n"]} (evals {s["n"]}); ' + ', '.join(f'{k} {mine[k]:.4f}' for k in
                          ('acc', 'conf', 'self_dec', 'brier', 'logloss', 'auc_pooled', 'ioi', 'ignorance', 'deception', 'out')) +
                          '; наибольшая |разность| со summary: ' + f'{max(diffs.values()):.2e}')
    pickle.dump(allrows, open(f'{OUT}/rc_rows.pkl', 'wb'))
    open(f'{OUT}/rc_measures.log', 'w').write('\n'.join(report) + '\n')
    print('\n'.join(report))


if __name__ == '__main__':
    main()
