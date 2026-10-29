#!/usr/bin/env python3
"""SCORE-02: вердикты по букве PREREG. Перед вердиктами сверяет хеши (prereg_hashes.json) и покрытие заданий; проверяет контекст
голов каждого этапа (ctx_check.py SCORE-01, линия пилота 3 SCORE-01 — промпт тот же; флаг → чтение «не показано (контекст)»).
Меры и бутстреп — score02_lib.py; суждения — evals/<этап>.json (score02.py metrics).
Направленное предсказание: 95 % интервал бутстрепа задач (B = 10 000, процентили) целиком на предсказанной стороне — «подтверждено»,
целиком на другой — «опровергнуто», иначе — «не показано». Потери: годных вызовов меньше 90 % заданий этапа — «не показано (потери)».
  python3 analyze_score02.py [--stages main_opus,…] [--dry] → analysis_score02.json и печать (журнал — run/analysis_score02.log)"""
import hashlib
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
SC1 = os.path.join(ROOT, 'experiments', '2026-10-28_SCORE-01')
sys.path.insert(0, HERE)
import score02_lib as L  # noqa: E402

STAGES = ('main_opus', 'rep_opus', 'main_haiku', 'rep_haiku')
B = 10000
MIN_VALID = 0.9
P = lambda **k: k
# Предсказания — по пилоту (PREREG §4); одинаковы для основной выборки и повтора. Заполняются до регистрации.
PRED = [  # направления — по пилоту (PREREG §3); разведка — вне семьи, в реестр только гипотезой
    P(id='X1o', model='opus', measure='auc2', a='agree', b='single', dir=-1, family=True,
      text='Opus: AUC второго рода согласия пяти вызовов меньше, чем у словесной уверенности одного вызова'),
    P(id='X2o', model='opus', measure='self_dec', a='agree', b='single', dir=+1, family=True,
      text='Opus: самообман доли согласных вызовов (как вероятности) больше, чем у словесной уверенности одного вызова'),
    P(id='X3o', model='opus', measure='acc', a='agree', b='single', dir=+1, family=True,
      text='Opus: точность суждения большинства пяти вызовов выше, чем у одного вызова'),
    P(id='X4o', model='opus', measure='self_dec', a='mean', b='single', dir=-1, family=True,
      text='Opus: самообман среднего p пяти вызовов меньше, чем у одного вызова'),
    P(id='XE1o', model='opus', measure='auc2', a='mean', b='single', dir=+1, family=False,
      text='разведка, Opus: AUC второго рода среднего p пяти вызовов больше, чем у одного вызова'),
    P(id='X2h', model='haiku', measure='self_dec', a='agree', b='single', dir=+1, family=True,
      text='Haiku: самообман доли согласных вызовов (как вероятности) больше, чем у словесной уверенности одного вызова'),
    P(id='X3h', model='haiku', measure='acc', a='agree', b='single', dir=+1, family=True,
      text='Haiku: точность суждения большинства пяти вызовов выше, чем у одного вызова'),
    P(id='X4h', model='haiku', measure='self_dec', a='mean', b='single', dir=-1, family=True,
      text='Haiku: самообман среднего p пяти вызовов меньше, чем у одного вызова'),
    P(id='XE1h', model='haiku', measure='auc2', a='agree', b='single', dir=+1, family=False,
      text='разведка, Haiku: AUC второго рода согласия пяти вызовов больше, чем у одного вызова (знак условный: в пилоте меньше 1 SE)'),
    P(id='XE2h', model='haiku', measure='auc2', a='mean', b='single', dir=+1, family=False,
      text='разведка, Haiku: AUC второго рода среднего p пяти вызовов больше, чем у одного вызова'),
]
COMP = dict(SA_opus=['X1o'], SB_opus=['X2o'], SC_opus=['X3o'], SD_opus=['X4o'], SB_haiku=['X2h'], SC_haiku=['X3h'], SD_haiku=['X4h'])
ESTABLISH = {c: True for c in COMP}   # PREREG §4: свойства двух прочтений одних и тех же вызовов, вмешательства нет


def sha(p):
    return hashlib.sha256(open(p, 'rb').read()).hexdigest()


def check_hashes():
    H = json.load(open(os.path.join(HERE, 'prereg_hashes.json'), encoding='utf-8'))
    bad = [k for k, v in H.items() if sha(os.path.join(HERE, k)) != v]
    assert not bad, f'хеши не совпали: {bad}'
    return len(H)


def coverage(st, evals_dir):
    jobs = [json.loads(l)['id'] for l in open(os.path.join(HERE, 'jobs', f'{st.split("_")[0]}_jobs.jsonl'), encoding='utf-8')]
    E = json.load(open(os.path.join(evals_dir, f'{st}.json'), encoding='utf-8'))
    rows = E['rows']
    missing = [j for j in jobs if j not in rows]
    stray = [j for j in rows if j not in set(jobs)]
    assert not stray, f'{st}: в выгрузке задания не из файла заданий: {stray[:5]}'
    valid = sum(1 for j in jobs if j in rows and rows[j]['valid'])
    return dict(jobs=len(jobs), rows=len(rows), missing=len(missing), invalid=len(jobs) - len(missing) - valid, valid=valid)


def ctx(st, ctx_json=None):
    if ctx_json:
        return json.load(open(ctx_json, encoding='utf-8'))
    sys.path.insert(0, SC1)
    import ctx_check as C
    return C.stage(os.path.join(HERE, 'run', st), os.path.join(HERE, 'jobs', f'{st.split("_")[0]}_jobs.jsonl'))


def verdict(p, M, BS, tasks, cov):
    if cov['valid'] < MIN_VALID * cov['jobs']:
        return dict(outcome='не показано (потери)', n_tasks=len(tasks))
    spec = (p['measure'], p['a'], p['b'])
    mu = L.contrast(M, spec)
    xs = BS[spec]
    lo, hi = L.pct(xs, 0.025), L.pct(xs, 0.975)
    d = p['dir']
    if (lo > 0 and d > 0) or (hi < 0 and d < 0):
        out = 'подтверждено'
    elif (hi < 0 and d > 0) or (lo > 0 and d < 0):
        out = 'опровергнуто'
    else:
        out = 'не показано'
    return dict(outcome=out, mean=mu, ci95=[lo, hi], n_tasks=len(tasks), a=M[p['a']], b=M[p['b']])


def main():
    a = sys.argv[1:]
    stages = a[a.index('--stages') + 1].split(',') if '--stages' in a else list(STAGES)
    dry = '--dry' in a
    R = dict(hashes=None if dry else check_hashes(), coverage={}, ctx={}, verdicts={}, composites={}, readings={}, status={}, pred=PRED)
    log = []
    evals_dir = os.path.join(HERE, 'dry', 'evals') if dry else os.path.join(HERE, 'evals')
    for st in stages:
        model = st.split('_')[1]
        cov = coverage(st, evals_dir)
        R['coverage'][st] = cov
        c = ctx(st, os.path.join(HERE, 'dry', f'ctx_{st}.json') if dry else None)
        R['ctx'][st] = {k: c[k] for k in ('flag', 'why', 'n', 'skipped', 'abs_mean', 'abs_max', 'max_abs_resid', 'frac_resid_gt', 'frac_abs_gt', 'config') if k in c}
        J = L.load(st, evals_dir)
        tasks = sorted(J)
        log.append(f'{st}: заданий {cov["jobs"]}, записей {cov["rows"]}, нет записи {cov["missing"]}, негодных {cov["invalid"]}; '
                   f'контекст — флаг {c["flag"]} ({"; ".join(c["why"]) or "нет"})')
        preds = [q for q in PRED if q['model'] == model]
        M = L.measures(J, tasks)
        R['measures'] = R.get('measures', {}); R['measures'][st] = M
        BS = L.bootstrap(J, tasks, [(q['measure'], q['a'], q['b']) for q in preds], B=B, name=st)
        for p in preds:
            v = verdict(p, M, BS, tasks, cov)
            R['verdicts'][f"{p['id']}|{st}"] = v
            log.append(f"  {p['id']:4s} {p['measure']} {p['a']} − {p['b']} {'> 0' if p['dir'] > 0 else '< 0'} → {v['outcome']}"
                       + (f"; {v['mean']:+.4f} [{v['ci95'][0]:+.4f}; {v['ci95'][1]:+.4f}], задач {v['n_tasks']}" if 'mean' in v else ''))
        for cname, parts in COMP.items():
            if not cname.endswith(model):
                continue
            outs = [R['verdicts'][f'{pid}|{st}']['outcome'] for pid in parts]
            co = 'подтверждено' if all(o == 'подтверждено' for o in outs) else ('опровергнуто' if any(o == 'опровергнуто' for o in outs) else 'не подтверждено')
            R['composites'][f'{cname}|{st}'] = dict(parts=parts, outcome=co)
            R['readings'][f'{cname}|{st}'] = 'не показано (контекст)' if c['flag'] else co
            log.append(f'  сводный {cname}: {co}; чтение — {R["readings"][f"{cname}|{st}"]}')
    for cname in COMP:
        mdl = cname.split('_')[1]
        rd = [R['readings'].get(f'{cname}|{s}_{mdl}') for s in ('main', 'rep')]
        if None in rd:
            continue
        if rd == ['подтверждено', 'подтверждено']:
            s = 'установлено' if ESTABLISH.get(cname) else 'подтверждено (повторено; причина не проверялась)'
        else:
            s = f'{rd[0]}; повтор: {rd[1]}'
        R['status'][cname] = dict(main=rd[0], rep=rd[1], status=s)
        log.append(f'статус {cname}: {s}')
    json.dump(R, open(os.path.join(HERE, 'dry' if dry else '', 'analysis_score02.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    open(os.path.join(HERE, 'dry' if dry else 'run', 'analysis_score02.log'), 'w', encoding='utf-8').write('\n'.join(log) + '\n')
    print('\n'.join(log))


if __name__ == '__main__':
    main()
