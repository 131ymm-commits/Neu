#!/usr/bin/env python3
"""SCORE-02: описательные факты к отчёту — не вердикты, не в зачёт. Список фактов определён после регистрации, до данных теста
(коммит этого файла); сверх него пост-хок помечается отдельно. Числа — из evals/<этап>.json, journal run/<этап>/ и truth/.
  Ф1 — ход прогона: время первой и последней записи, вызовы, исходы, ожидания сброса лимита, повторы, цена, выход в среднем;
  Ф2 — точность суждения согласия по уровню согласия (как таблица уровней пилота);
  Ф3 — точность одного вызова по корзинам уверенности (как в пилоте);
  Ф4 — похожесть пяти вызовов (урок PRED-01): доля кандидатов, у которых все годные вызовы дали одно p; доля пар вызовов на одной
       стороне (среди p ≠ 0,5); среднее |p_k − p_l|; корреляция p пар вызовов (по всем парам);
  Ф5 — пилот против теста: меры источников (описательно);
  Ф6 — Opus против Haiku на одних задачах: доля кандидатов, где стороны большинства моделей совпали, и где обе неверны.
  python3 report_facts_score02.py [--evals evals] [--run run] → report_facts_score02.json и печать (журнал — run/report_facts.log)"""
import collections
import glob
import itertools
import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import score02 as S  # noqa: E402
import score02_lib as L  # noqa: E402

STAGES = ('main_opus', 'rep_opus', 'main_haiku', 'rep_haiku')
f = lambda x, d=3: '—' if x is None or x != x else f'{x:.{d}f}'.replace('.', ',').replace('-', '−')
cbin = lambda c: min(int(round((c - 0.5) * 10, 9)), 4)


def arg(a, k, d):
    return a[a.index(k) + 1] if k in a else d


def timeline(run_dir):
    if not os.path.isdir(run_dir):
        return None
    fin, waits, retries, first, last = collections.Counter(), 0, 0, None, None
    for p in glob.glob(os.path.join(run_dir, 'WH_*.jsonl')):
        for l in open(p, encoding='utf-8'):
            try:
                o = json.loads(l)
            except ValueError:
                continue
            if not o.get('final'):
                continue
            fin[o['final']] += 1
            waits += o.get('waits') or 0
            retries += o.get('retries') or 0
            s, e = o.get('started'), o.get('finished')
            first = s if first is None or (s and s < first) else first
            last = e if last is None or (e and e > last) else last
    return dict(finals=dict(fin), waits=waits, retries=retries, first=first, last=last)


def similarity(E, K=5):
    rows = E['rows']
    by_t = collections.defaultdict(dict)
    for jid, r in rows.items():
        if r['valid']:
            by_t[r['task']][int(jid.split('|')[2])] = r['p']
    same_all, cand, pairs_side, pairs_n, dabs, xs, ys = 0, 0, 0, 0, [], [], []
    for t, calls in by_t.items():
        ps = [calls[k] for k in sorted(calls)]
        if len(ps) < 2:
            continue
        for i in range(8):
            v = [p[i] for p in ps]
            cand += 1
            same_all += int(len(set(v)) == 1)
            for a, b in itertools.combinations(v, 2):
                dabs.append(abs(a - b))
                xs.append(a); ys.append(b)
                if a != 0.5 and b != 0.5:
                    pairs_n += 1
                    pairs_side += int((a > 0.5) == (b > 0.5))
    r = float(np.corrcoef(xs, ys)[0, 1]) if len(xs) > 2 and np.std(xs) > 0 and np.std(ys) > 0 else float('nan')
    return dict(cand=cand, same_all=same_all / cand if cand else float('nan'), side_agree=pairs_side / pairs_n if pairs_n else float('nan'),
                mean_abs_diff=float(np.mean(dabs)) if dabs else float('nan'), corr=r)


def majority_sides(E, K=5):
    rows = E['rows']
    by_t = collections.defaultdict(list)
    for jid, r in rows.items():
        if r['valid']:
            by_t[r['task']].append(r['p'])
    out = {}
    for t, ps in by_t.items():
        for i in range(8):
            up = sum(1 for p in ps if p[i] > 0.5); dn = sum(1 for p in ps if p[i] < 0.5)
            if up != dn:
                out[(t, i)] = up > dn
    return out


def main():
    a = sys.argv[1:]
    ev = os.path.join(HERE, arg(a, '--evals', 'evals'))
    rd = os.path.join(HERE, arg(a, '--run', 'run'))
    out, log = dict(stages={}), []
    for st in STAGES:
        p = os.path.join(ev, f'{st}.json')
        if not os.path.exists(p):
            continue
        E = json.load(open(p, encoding='utf-8'))
        J = L.load(st, ev)
        tasks = sorted(J)
        tl = timeline(os.path.join(rd, st))
        lev, bins = {}, {}
        for t in tasks:
            for c, o in J[t]['agree']:
                x = lev.setdefault(round(c, 2), [0, 0]); x[0] += 1; x[1] += o
            for c, o in J[t]['single']:
                x = bins.setdefault(cbin(c), [0, 0]); x[0] += 1; x[1] += o
        sim = similarity(E)
        out['stages'][st] = dict(calls=E['calls'], timeline=tl, acc_by_agree={str(k): v for k, v in sorted(lev.items())},
                                 acc_by_conf_bin={str(k): v for k, v in sorted(bins.items())}, similarity=sim)
        log.append(f"== {st}: вызовов {E['calls']['n']}, годных {E['calls']['valid']}, цена {f(E['calls']['cost'], 2)} $, выход в среднем {f(E['calls']['out'], 0)} ток.")
        if tl:
            log.append(f"   Ф1: первая запись {tl['first']}, последняя {tl['last']}; исходы {tl['finals']}; ожиданий сброса лимита {tl['waits']}, повторов {tl['retries']}")
        log.append('   Ф2: точность согласия по уровню: ' + ', '.join(f'{f(k, 2)} — {f(v[1] / v[0])} ({v[0]})' for k, v in sorted(lev.items())))
        log.append('   Ф3: точность одного вызова по корзинам уверенности: ' + ', '.join(f'{f(0.5 + k / 10, 1)} — {f(v[1] / v[0])} ({v[0]})' for k, v in sorted(bins.items())))
        log.append(f"   Ф4: кандидатов {sim['cand']}; все годные вызовы дали одно p — {f(sim['same_all'])}; пар вызовов на одной стороне — {f(sim['side_agree'])}; "
                   f"среднее |p_k − p_l| — {f(sim['mean_abs_diff'])}; корреляция p пар вызовов — {f(sim['corr'])}")
    P = {m: json.load(open(os.path.join(HERE, 'pilot_describe.json'), encoding='utf-8'))[f'pilot_{m}']['measures'] for m in ('opus', 'haiku')}
    out['pilot_vs_test'] = {}
    for st in out['stages']:
        m = st.split('_')[1]
        M = L.measures(L.load(st, ev), sorted(L.load(st, ev)))
        out['pilot_vs_test'][st] = {s: dict(pilot={k: P[m][s][k] for k in ('auc2', 'acc', 'conf', 'self_dec')}, test={k: M[s][k] for k in ('auc2', 'acc', 'conf', 'self_dec')})
                                    for s in L.SOURCES}
        log.append(f'   Ф5 {st}: ' + '; '.join(f"{s}: AUC2 {f(P[m][s]['auc2'])} → {f(M[s]['auc2'])}, точность {f(P[m][s]['acc'])} → {f(M[s]['acc'])}, "
                                             f"самообман {f(P[m][s]['self_dec'])} → {f(M[s]['self_dec'])}" for s in L.SOURCES))
    out['models'] = {}
    for smp in ('main', 'rep'):
        po, ph = os.path.join(ev, f'{smp}_opus.json'), os.path.join(ev, f'{smp}_haiku.json')
        if not (os.path.exists(po) and os.path.exists(ph)):
            continue
        lab = S.labels_for(smp)
        mo, mh = majority_sides(json.load(open(po, encoding='utf-8'))), majority_sides(json.load(open(ph, encoding='utf-8')))
        common = sorted(set(mo) & set(mh))
        same = sum(1 for k in common if mo[k] == mh[k])
        both_wrong = sum(1 for k in common if mo[k] != (k[1] in lab[k[0]]) and mh[k] != (k[1] in lab[k[0]]))
        wrong_o = sum(1 for k in common if mo[k] != (k[1] in lab[k[0]]))
        wrong_h = sum(1 for k in common if mh[k] != (k[1] in lab[k[0]]))
        out['models'][smp] = dict(common=len(common), same_side=same / len(common) if common else float('nan'), both_wrong=both_wrong,
                                  wrong_opus=wrong_o, wrong_haiku=wrong_h)
        log.append(f"   Ф6 {smp}: кандидатов с суждением большинства у обеих моделей {len(common)}; стороны совпали {f(same / len(common) if common else float('nan'))}; "
                   f"неверны у Opus {wrong_o}, у Haiku {wrong_h}, у обеих {both_wrong}")
    json.dump(out, open(os.path.join(HERE, arg(a, '--json', 'report_facts_score02.json')), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    open(os.path.join(HERE, arg(a, '--log', os.path.join('run', 'report_facts.log'))), 'w', encoding='utf-8').write('\n'.join(log) + '\n')
    print('\n'.join(log))


if __name__ == '__main__':
    main()
