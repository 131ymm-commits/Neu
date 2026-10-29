#!/usr/bin/env python3
"""SCORE-02: вердикты по букве PREREG. Перед вердиктами сверяет хеши (prereg_hashes.json) и покрытие заданий; проверяет контекст
голов каждого этапа (ctx_check.py SCORE-01, линия пилота 3 SCORE-01 — промпт тот же; флаг → чтение «не показано (контекст)»).
Меры и бутстреп — score02_lib.py; суждения — evals/<этап>.json (score02.py metrics).
Направленное предсказание: 95 % интервал бутстрепа задач (B = 10 000, процентили; края по модулю меньше 1e−12 — ноль) целиком на
предсказанной стороне — «подтверждено», целиком на другой — «опровергнуто», иначе — «не показано». Потери: годных вызовов меньше 90 %
заданий этапа — «не показано (потери)».
Описательно (не вердикты): ИОИ источников, огрубление одного вызова (контроль X1oc), разложение самообмана согласия (§8), исключения.
  python3 analyze_score02.py [--stages main_opus,…] [--dry] → analysis_score02.json и печать (журнал — run/analysis_score02.log)
  --dry: суждения из dry/evals, контекст из dry/ctx_<этап>.json, хеши не сверяются, вывод — в dry/"""
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
# Предсказания — по пилоту (PREREG §3–§4); одинаковы для основной выборки и повтора.
# kind: family — семья (в реестр с весом, §6); check — проверка (почти арифметика, §8: вердикт и калибровка, без веса);
# explore — разведка (вне семьи, в реестр только гипотезой).
PRED = [
    P(id='X1o', expect=0.7, model='opus', measure='auc2', a='agree', b='single', dir=-1, kind='family',
      text='Opus: AUC второго рода согласия пяти вызовов меньше, чем у словесной уверенности одного вызова'),
    P(id='X1oc', expect=0.5, model='opus', measure='auc2', a='agree', b='single_c', dir=-1, kind='family',
      text='Opus, контроль равной грубости: AUC второго рода согласия меньше, чем у словесной уверенности одного вызова, '
           'огрублённой до распределения уровней согласия этапа'),
    P(id='X2o', expect=0.95, model='opus', measure='self_dec', a='agree', b='single', dir=+1, kind='family',
      text='Opus: самообман доли согласных вызовов (как вероятности) больше, чем у словесной уверенности одного вызова'),
    P(id='X3o', expect=0.55, model='opus', measure='acc', a='agree', b='single', dir=+1, kind='family',
      text='Opus: точность суждения большинства пяти вызовов выше, чем у одного вызова'),
    P(id='X4o', expect=0.95, model='opus', measure='self_dec', a='mean', b='single', dir=-1, kind='check',
      text='проверка, Opus: самообман среднего p пяти вызовов меньше, чем у одного вызова (почти арифметика)'),
    P(id='XE1o', expect=0.25, model='opus', measure='auc2', a='mean', b='single', dir=+1, kind='explore',
      text='разведка, Opus: AUC второго рода среднего p пяти вызовов больше, чем у одного вызова'),
    P(id='X2h', expect=0.95, model='haiku', measure='self_dec', a='agree', b='single', dir=+1, kind='family',
      text='Haiku: самообман доли согласных вызовов (как вероятности) больше, чем у словесной уверенности одного вызова'),
    P(id='X3h', expect=0.45, model='haiku', measure='acc', a='agree', b='single', dir=+1, kind='family',
      text='Haiku: точность суждения большинства пяти вызовов выше, чем у одного вызова'),
    P(id='X4h', expect=0.95, model='haiku', measure='self_dec', a='mean', b='single', dir=-1, kind='check',
      text='проверка, Haiku: самообман среднего p пяти вызовов меньше, чем у одного вызова (почти арифметика)'),
    P(id='XE1h', expect=0.2, model='haiku', measure='auc2', a='agree', b='single', dir=+1, kind='explore',
      text='разведка, Haiku: AUC второго рода согласия пяти вызовов больше, чем у одного вызова (знак условный: в пилоте меньше 1 SD)'),
    P(id='XE2h', expect=0.25, model='haiku', measure='auc2', a='mean', b='single', dir=+1, kind='explore',
      text='разведка, Haiku: AUC второго рода среднего p пяти вызовов больше, чем у одного вызова'),
]
for _q in PRED:
    _q['family'] = _q['kind'] == 'family'
COMP = dict(SA_opus=['X1o'], SAc_opus=['X1oc'], SB_opus=['X2o'], SC_opus=['X3o'], SB_haiku=['X2h'], SC_haiku=['X3h'])
CONTROL = dict(SA_opus='SAc_opus')   # «установлено» для SA_opus — только при контроле равной грубости, подтверждённом в обеих выборках


def sha(p):
    return hashlib.sha256(open(p, 'rb').read()).hexdigest()


def check_hashes():
    import prereg_hashes
    H = json.load(open(os.path.join(HERE, 'prereg_hashes.json'), encoding='utf-8'))
    now = prereg_hashes.compute()
    bad = sorted(set(H) ^ set(now)) + [k for k in H if k in now and now[k] != H[k]]
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
    lo, hi = L.ci95(BS[spec])
    d = p['dir']
    if (lo > 0 and d > 0) or (hi < 0 and d < 0):
        out = 'подтверждено'
    elif (hi < 0 and d > 0) or (lo > 0 and d < 0):
        out = 'опровергнуто'
    else:
        out = 'не показано'
    return dict(outcome=out, mean=mu, ci95=[lo, hi], n_tasks=len(tasks), a=M[p['a']], b=M[p['b']])


def describe(J, cand, tasks, E):
    """Описательное (не вердикты): огрубление (уровни согласия и доли), разложение X2, исключения, единогласие."""
    _, lv = L.coarse_map(J, tasks)
    rows = E['rows']
    half = sum(1 for r in rows.values() if r['valid'] for x in r['p'] if x == 0.5)
    calls = sum(8 for r in rows.values() if r['valid'])
    ties = sum(1 for t in tasks for r, n in cand[t] if n and 2 * r == n)
    nc = sum(len(cand[t]) for t in tasks)
    return dict(levels=[dict(level=v, agree_share=q, single_c_share=g) for v, q, g in lv], decomp_x2=L.decomp_x2(J, cand, tasks),
                excl=dict(half_calls=half, call_judgments=calls, side_ties=ties, cand_with_side=nc))


def main():
    a = sys.argv[1:]
    stages = a[a.index('--stages') + 1].split(',') if '--stages' in a else list(STAGES)
    dry = '--dry' in a
    R = dict(hashes=None if dry else check_hashes(), coverage={}, ctx={}, measures={}, describe={}, verdicts={}, composites={}, readings={},
             status={}, pred=PRED, comp=COMP, control=CONTROL)
    log = []
    evals_dir = os.path.join(HERE, 'dry', 'evals') if dry else os.path.join(HERE, 'evals')
    for st in stages:
        model = st.split('_')[1]
        cov = coverage(st, evals_dir)
        R['coverage'][st] = cov
        c = ctx(st, os.path.join(HERE, 'dry', f'ctx_{st}.json') if dry else None)
        R['ctx'][st] = {k: c[k] for k in ('flag', 'why', 'n', 'skipped', 'abs_mean', 'abs_max', 'max_abs_resid', 'frac_resid_gt', 'frac_abs_gt', 'config') if k in c}
        J = L.load(st, evals_dir)
        cand = L.load_cand(st, evals_dir)
        E = json.load(open(os.path.join(evals_dir, f'{st}.json'), encoding='utf-8'))
        tasks = sorted(J)
        log.append(f'{st}: заданий {cov["jobs"]}, записей {cov["rows"]}, нет записи {cov["missing"]}, негодных {cov["invalid"]}; '
                   f'контекст — флаг {c["flag"]} ({"; ".join(c["why"]) or "нет"})')
        preds = [q for q in PRED if q['model'] == model]
        M = L.measures(J, tasks)
        R['measures'][st] = M
        D = describe(J, cand, tasks, E)
        R['describe'][st] = D
        for s in L.SOURCES:
            v = M[s]
            log.append(f'  {s:6s}: суждений {v["n"]}, AUC2 {v["auc2"]:.4f}, точность {v["acc"]:.4f}, уверенность {v["conf"]:.4f}, '
                       f'самообман {v["self_dec"]:+.4f}, Брайер {v["brier"]:.4f}, ИОИ {v["ioi"]:.4f} = незнание {v["ign"]:.4f} + самообман⁺ {v["dec_pos"]:.4f}')
        log.append(f'  single_c: AUC2 {M["single_c"]["auc2"]:.4f}; уровни согласия (доля agree / доля single после огрубления): '
                   + ', '.join(f'{x["level"]:.3f} — {x["agree_share"]:.3f} / {x["single_c_share"]:.3f}' for x in D['levels']))
        dx = D['decomp_x2']
        log.append(f'  разложение X2: T = {dx["T"]:.4f} (порог {dx["T_break"]:.4f}), приближение {dx["approx"]:+.4f}, факт {dx["x2"]:+.4f}; '
                   f'единогласных суждений agree {dx["unanimous"]:.3f}; исключено: p = 0,5 — {D["excl"]["half_calls"]} из {D["excl"]["call_judgments"]}, '
                   f'ничьих сторон — {D["excl"]["side_ties"]} из {D["excl"]["cand_with_side"]}')
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
            why = (['контекст'] if c['flag'] else []) + (['потери'] if any(o == 'не показано (потери)' for o in outs) else [])
            R['readings'][f'{cname}|{st}'] = f"не показано ({'; '.join(why)})" if why else co
            log.append(f'  сводный {cname}: {co}; чтение — {R["readings"][f"{cname}|{st}"]}')
    for cname in COMP:
        mdl = cname.split('_')[1]
        rd = [R['readings'].get(f'{cname}|{s}_{mdl}') for s in ('main', 'rep')]
        if None in rd:
            continue
        tech = sorted({w for r in rd if r.startswith('не показано (') for w in r[len('не показано ('):-1].split('; ')})
        if tech:
            s = f"не показано ({'; '.join(tech)}) — технический исход, вес 0 бит (§6)"
        elif rd == ['подтверждено', 'подтверждено']:
            if cname in CONTROL:
                crd = [R['readings'].get(f'{CONTROL[cname]}|{x}_{mdl}') for x in ('main', 'rep')]
                if crd == ['подтверждено', 'подтверждено']:
                    s = 'установлено (повторено; контроль равной грубости подтверждён в обеих выборках; причина не проверялась)'
                else:
                    s = (f'подтверждено (повторено); контроль равной грубости не подтверждён (основная: {crd[0]}; повтор: {crd[1]}) — '
                         f'разрыв может объясняться грубостью шкалы согласия')
            else:
                s = 'подтверждено (повторено; причина не проверялась)'
        else:
            s = f'{rd[0]}; повтор: {rd[1]}'
        R['status'][cname] = dict(main=rd[0], rep=rd[1], status=s, technical=bool(tech))
        log.append(f'статус {cname}: {s}')
    out_dir = os.path.join(HERE, 'dry') if dry else HERE
    json.dump(R, open(os.path.join(out_dir, 'analysis_score02.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    open(os.path.join(HERE, 'dry' if dry else 'run', 'analysis_score02.log'), 'w', encoding='utf-8').write('\n'.join(log) + '\n')
    print('\n'.join(log))


if __name__ == '__main__':
    main()
