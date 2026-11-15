#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""OCSHIFT-01: загрузка сред и счёт по одной среде. Оценщики толпы — код OCCOR-01 и OCMIX-01 без изменений (через
analyze_ocrep.scores); калибровка и выбор — как analyze_ocgeo_test (изотоника по ID, наибольшая заявка, ничья «поровну»).
Новое: ONE-BEST (одна лучшая голова), самообман от отбора на ID с кросс-подгонкой, описательные варианты.

core(st, fit, cols) — все числа одного набора (точка или повтор бутстрепа) плоским словарём:
  'ioi E', 'T E', 'C E', 'brier E' — E из восьми оценщиков толпы и вариантов:
     ONE-BEST         — голова с наибольшей точностью на fit; заявка — её изотоника по logp (как у CONF); выбора нет;
     ONE-BEST+MIN     — та же голова; заявка — меньшая из её заявок CONF и LR-AGREE (описательно);
     FUSE-MIN         — заявка головы — меньшая из заявок CONF и LR-AGREE, выбор — по ней (описательно);
     POST-IN CONF / POST-IN LR-AGREE — вторая калибровка после отбора по fit, in-sample (описательно);
  'ioi MIN8', 'brier MIN8' — наименьшее среди восьми (лучший задним числом);
  'wc CONF' — T − C у CONF на fit с кросс-подгонкой по частям исходных задач (самообман от отбора без сдвига; < 0 — завышение);
  'wc ONE-BEST' — то же у ONE-BEST (голова выбирается по обучающим частям; описательно);
  'lr_one_class' — число голов с одним классом в fit."""
import json
import os
import sys

import numpy as np
from sklearn.isotonic import IsotonicRegression

HERE = os.path.dirname(os.path.abspath(__file__))
EXP = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(EXP, '2026-11-15_OCREP-01'))
import analyze_ocrep as Q  # noqa: E402

Z, M, T = Q.Z, Q.M, Q.Z.T
EVALS = Q.EVALS
MIN_EACH, MAX_NONE, MIN_HEADS = 20, 0.05, 6
K_CV = 5
VARIANTS = ('ONE-BEST', 'ONE-BEST+MIN', 'FUSE-MIN', 'POST-IN CONF', 'POST-IN LR-AGREE')
OCREP_PILOT = os.path.join(EXP, '2026-11-15_OCREP-01', 'pilot', 'out', 'answers.json')


def load_new(path):
    """answers.json вида ocshift_extract.py → (d, {имя среды: dict(meta, problems, heads)}), головы — в прежнем виде (rows).
    Правда сверяется вторым способом: correct == (ответ == a + b)."""
    d = json.load(open(os.path.join(path, 'answers.json'), encoding='utf-8'))
    envs = {}
    for env in d['envs']:
        heads = []
        for h in d['heads']:
            if 'cols' not in h:
                continue
            c = h['cols'][env['name']]
            rows = [dict(answer=a, correct=bool(k), logp=lp, n_tok=nt) for a, k, lp, nt in zip(c['answer'], c['correct'], c['logp'], c['n_tok'])]
            assert len(rows) == len(env['problems']), 'число строк не равно числу задач'
            assert all(r['correct'] == (r['answer'] == p['a'] + p['b'] == p['sum']) for r, p in zip(rows, env['problems'])), 'правда не сошлась'
            heads.append(dict(model=h['model'], revision=h['revision'], rows=rows))
        envs[env['name']] = dict(meta={k: v for k, v in env.items() if k != 'problems'}, problems=env['problems'], heads=heads)
    return d, envs


def load_old(path, name):
    """Каталог прежнего вида (answers.json OCCOR-01 / OCMIX-01 / OCREP-01) как одна среда."""
    d, heads = Q.load(path)
    return {name: dict(meta=dict(name=name, kind='old', task=d.get('task'), prompt_head=d.get('prompt_head')), problems=d['problems'], heads=heads)}


def check_block(envs, ref_path=OCREP_PILOT):
    """Сверка цепочки: блок check_ocrep_pilot против закоммиченного вывода пилота OCREP-01 (те же задачи и подсказка)."""
    ref = json.load(open(ref_path, encoding='utf-8'))
    e = envs['check_ocrep_pilot']
    n = len(e['problems'])
    same_probs = all((p['a'], p['b']) == (q['a'], q['b']) for p, q in zip(e['problems'], ref['problems'][:n]))
    out = dict(n=n, same_problems=bool(same_probs), same_prompt=bool(e['meta']['prompt_head'] == ref['prompt_head']), heads={})
    for h in e['heads']:
        rh = [x for x in ref['heads'] if x['model'] == h['model'] and x['revision'] == h['revision'] and 'rows' in x]
        if not rh:
            out['heads'][Q.label(h)] = dict(error='нет в выводе OCREP-01')
            continue
        pr = list(zip(h['rows'], rh[0]['rows'][:n]))
        dl = [abs(a['logp'] - b['logp']) for a, b in pr if a['logp'] is not None and b['logp'] is not None]
        out['heads'][Q.label(h)] = dict(same_answer=int(sum(a['answer'] == b['answer'] for a, b in pr)),
                                        none_mismatch=int(sum((a['logp'] is None) != (b['logp'] is None) for a, b in pr)),
                                        max_abs_dlogp=float(max(dl)) if dl else 0.0)
    out['n_heads'] = len(e['heads'])
    out['answers_equal'] = bool(same_probs and out['same_prompt'] and all(v.get('same_answer') == n and v.get('none_mismatch') == 0 for v in out['heads'].values()))
    out['max_abs_dlogp'] = max([v.get('max_abs_dlogp', 0.0) for v in out['heads'].values()] or [0.0])
    return out


def select(cal, y):
    """Выбор — наибольшая заявка, ничья «поровну» (как analyze_ocgeo_test.select). Возвращает t, c и веса голов."""
    mx = cal.max(0)
    tied = np.abs(cal - mx[None, :]) <= 1e-12
    w = tied / tied.sum(0)
    return (y * w).sum(0), mx, w


def meas(t, c):
    Tm, Cm = float(np.mean(t)), float(np.mean(c))
    return dict(T=Tm, C=Cm, ioi=(1 - Tm) + max(0.0, Cm - Tm), brier=float(np.mean(c * c - 2 * c * t + t)))


def iso_fit(x, y):
    return IsotonicRegression(out_of_bounds='clip', y_min=0, y_max=1).fit(np.asarray(x, float), np.asarray(y, float))


def prepare(env, seed_cv):
    """Массивы среды, проверка метода по головам, состав толпы, части кросс-подгонки (по исходным задачам ID)."""
    heads = env['heads']
    ans, corr, rid, logp = Q.arrays(dict(problems=env['problems']), heads)
    assert np.isfinite(logp).all(), 'неконечный logp'
    names, fam = [Q.label(h) for h in heads], [Q.family(h) for h in heads]
    idi, ood = np.nonzero(rid)[0], np.nonzero(~rid)[0]
    mc = {}
    for k in range(len(heads)):
        cnt = dict(id_correct=int(corr[k][rid].sum()), id_wrong=int((~corr[k][rid]).sum()),
                   ood_correct=int(corr[k][~rid].sum()), ood_wrong=int((~corr[k][~rid]).sum()))
        none = float(np.mean([a is None for a in ans[k]]))
        # Проверка метода — только по ID (правда ID оценщикам доступна); счёт по OOD записывается, но состав толпы не решает:
        # иначе правда OOD протекала бы в состав толпы (PREREG §9).
        mc[names[k]] = dict(**cnt, none_frac=none, ok=bool(min(cnt['id_correct'], cnt['id_wrong']) >= MIN_EACH and none <= MAX_NONE))
    keep = [k for k in range(len(heads)) if mc[names[k]]['ok']]
    fold_of = np.full(len(rid), -1)
    perm = np.random.default_rng(seed_cv).permutation(len(idi))
    for k in range(K_CV):
        fold_of[idi[perm[k::K_CV]]] = k
    st = dict(ag=Q.agree_matrix(ans), corr=corr, logp=logp, fam=fam, keep=keep, fold_of=fold_of)
    return st, dict(ans=ans, corr=corr, rid=rid, logp=logp, names=names, fam=fam, idi=idi, ood=ood, method=mc, keep=keep,
                    valid=bool(len(keep) >= MIN_HEADS))


def core(st, fit, cols):
    keep = st['keep']
    cs = st['corr'][keep]
    S = Q.scores(st['ag'], st['corr'], st['logp'], keep, fit, st['fam'], EVALS)
    y_c, y_f = cs[:, cols].astype(float), cs[:, fit].astype(float)
    hb = int(np.argmax(cs[:, fit].mean(1)))                                # при равенстве — первая по порядку
    out, cal, sel = {}, {}, {}

    def put(name, m):
        for k, v in m.items():
            out[f'{k} {name}'] = v
    for e in EVALS:
        cal[e] = T.calibrate(S[e], cs, fit, cols)
        t, c, _ = select(cal[e], y_c)
        sel[e] = (t, c)
        put(e, meas(t, c))
    out['ioi MIN8'] = min(out[f'ioi {e}'] for e in EVALS)
    out['brier MIN8'] = min(out[f'brier {e}'] for e in EVALS)
    put('ONE-BEST', meas(y_c[hb], cal['CONF'][hb]))
    put('ONE-BEST+MIN', meas(y_c[hb], np.minimum(cal['CONF'][hb], cal['LR-AGREE'][hb])))
    t, c, _ = select(np.minimum(cal['CONF'], cal['LR-AGREE']), y_c)
    put('FUSE-MIN', meas(t, c))
    for e in ('CONF', 'LR-AGREE'):
        ti, ci, _ = select(T.calibrate(S[e], cs, fit, fit), y_f)
        put(f'POST-IN {e}', meas(sel[e][0], iso_fit(ci, ti).predict(sel[e][1])))
    fo = st['fold_of'][fit]
    tt, cc, tb, cb = [], [], [], []
    for k in range(K_CV):
        tr, te = fit[fo != k], fit[fo == k]
        ck = T.calibrate(S['CONF'], cs, tr, te)
        t, c, _ = select(ck, cs[:, te].astype(float))
        tt.append(t)
        cc.append(c)
        hk = int(np.argmax(cs[:, tr].mean(1)))                              # ONE-BEST по обучающим частям: у неё тоже есть отбор — головы
        tb.append(cs[hk, te].astype(float))
        cb.append(ck[hk])
    out['wc CONF'] = float(np.mean(np.concatenate(tt)) - np.mean(np.concatenate(cc)))
    out['wc ONE-BEST'] = float(np.mean(np.concatenate(tb)) - np.mean(np.concatenate(cb)))
    out['lr_one_class'] = float(sum(1 for i in keep if st['corr'][i][fit].all() or (~st['corr'][i][fit]).all()))
    return out


def extras(st, info):
    """Описательное, только точка: доли выбора, отход от ONE-BEST, самообман от отбора на ID у всех восьми (кросс-подгонка
    с переподгонкой оценщика), POST по кросс-подгонке, верхние 10 %, оракул, толпа без лучшей головы."""
    keep, idi, ood, names = st['keep'], info['idi'], info['ood'], info['names']
    cs = st['corr'][keep]
    kn = [names[k] for k in keep]
    y_o = cs[:, ood].astype(float)
    acc_id, acc_ood = cs[:, idi].mean(1), cs[:, ood].mean(1)
    hb = int(np.argmax(acc_id))
    A_ = np.array([[-1 if x is None else x for x in info['ans'][k]] for k in keep])
    same_bh = (A_[:, ood] == A_[hb, ood][None, :]) & (A_[:, ood] >= 0)
    co_hb = T.calibrate(st['logp'][keep], cs, idi, ood)[hb]
    res = dict(accuracy={kn[k]: dict(id=float(acc_id[k]), ood=float(acc_ood[k])) for k in range(len(keep))},
               one_best_top10=Z.top_frac(co_hb, y_o[hb]),
               one_best=dict(head=kn[hb], acc_id=float(acc_id[hb]), acc_ood=float(acc_ood[hb]), best_ood_head=kn[int(np.argmax(acc_ood))],
                             best_ood_acc=float(acc_ood.max())),
               oracle=dict(id=float(cs[:, idi].any(0).mean()), ood=float(cs[:, ood].any(0).mean())), evaluators={})
    S = Q.scores(st['ag'], st['corr'], st['logp'], keep, idi, st['fam'], EVALS)
    cv_t, cv_c = {e: np.zeros(len(idi)) for e in EVALS}, {e: np.zeros(len(idi)) for e in EVALS}
    fo = st['fold_of'][idi]
    for k in range(K_CV):
        tr, te = idi[fo != k], idi[fo == k]
        Sk = Q.scores(st['ag'], st['corr'], st['logp'], keep, tr, st['fam'], EVALS)
        for e in EVALS:
            t, c, _ = select(T.calibrate(Sk[e], cs, tr, te), cs[:, te].astype(float))
            cv_t[e][fo == k], cv_c[e][fo == k] = t, c
    # R2 вторым способом, без бутстрепа: по задачам ID разность «точность выбранного − заявка» при кросс-подгонке (CONF);
    # среднее и его стандартная ошибка по нормальному приближению (калибровки частей считаются заданными).
    dcv = cv_t['CONF'] - cv_c['CONF']
    res['wc_conf_normal'] = dict(mean=float(dcv.mean()), se=float(dcv.std(ddof=1) / np.sqrt(len(dcv))), n=int(len(dcv)))
    for e in EVALS:
        co = T.calibrate(S[e], cs, idi, ood)
        t, c, w = select(co, y_o)
        on_bh = (w * same_bh).sum(0)
        sw = 1 - on_bh
        res['evaluators'][e] = dict(
            share={kn[k]: float(w[k].mean()) for k in range(len(keep))}, top10=Z.top_frac(c, t),
            id_crossfit=dict(T=float(cv_t[e].mean()), C=float(cv_c[e].mean()), dec=float(cv_c[e].mean() - cv_t[e].mean())),
            post_cv=meas(t, iso_fit(cv_c[e], cv_t[e]).predict(c)),
            vs_one_best=dict(switch=float(sw.mean()), T_selected_on_switch=float((w * ~same_bh * y_o).sum() / max(sw.sum(), 1e-12)),
                             T_one_best_on_switch=float((sw * y_o[hb]).sum() / max(sw.sum(), 1e-12))))
    if len(keep) - 1 >= 2:                                                  # толпа без лучшей головы
        st2 = dict(st, keep=[k for j, k in enumerate(keep) if j != hb])
        r2 = core(st2, idi, ood)
        res['without_best'] = {k: r2[k] for k in r2 if k.startswith('ioi ') or k.startswith('T ')}
    return res


def load_spec(spec):
    """spec — 'new:КАТАЛОГ' (answers.json вида ocshift_extract.py; берутся среды вида pilot/test) или 'old:ИМЯ=КАТАЛОГ'."""
    kind, rest = spec.split(':', 1)
    if kind == 'new':
        d, envs = load_new(rest)
        return d, envs
    name, path = rest.split('=', 1)
    return None, load_old(path, name)
