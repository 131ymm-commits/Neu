#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""OCPOST-01 «ОЦЕНЩИК-ПОСЛЕ-ОТБОРА»: вторая калибровка после отбора.
  python3 ocpost.py test   RESULT.json [--boot 10000] [--workers W] SPEC [SPEC ...]
  python3 ocpost.py pilot  RESULT.json [--boot 1000] [--workers W] [--ref ANALYSIS.json] SPEC [SPEC ...]
  python3 ocpost.py worlds RESULT.json [--meta SEED] [--first 0] [--worlds 30] [--exp 200] [--truth 2000] [--boot 200] [--workers 4]
  python3 ocpost.py tail   RESULT.json PART.json [PART.json ...]
SPEC — как в analyze_ocshift_test: 'new:КАТАЛОГ' (answers.json вида ocpost_extract.py / ocshift_extract.py; берутся среды
вида test, блок сверки проверяется против вывода OCREP-01) или 'old:ИМЯ=КАТАЛОГ'.

Статистики одной среды (post_stats) — только уверенность голов (оценщик CONF); калибровка, выбор и мера — зарегистрированный
код OCSHIFT-01 (analyze_ocshift: select, meas, iso_fit; analyze_ocgeo_test.calibrate):
  CONF      — изотоника logp каждой головы по ID, выбор наибольшей заявки (ничья «поровну»);
  POST-CV   — вторая калибровка: изотоника «выбранная заявка → верен ли выбранный ответ» по парам ID вне частей
              (головы откалиброваны по четырём частям из пяти, выбор — на пятой), применяется к выбранным заявкам OOD;
  ONE-BEST  — голова с наибольшей точностью на ID, её собственная откалиброванная заявка;
  FIXED     — голова, закреплённая по имени до данных (pythia-2.8b-deduped; в мирах — голова 6), её заявка; отбора нет;
  POST-IN   — вторая калибровка по парам ID в выборке (описательно, как в OCSHIFT-01);
  wc CONF   — T − C у CONF на ID с кросс-подгонкой (как в OCSHIFT-01); wc ONE-BEST — то же у ONE-BEST (описательно);
  wc POST   — T − C у POST-CV на ID с вложенной кросс-подгонкой: для внешней части k вторая калибровка учится на парах
              внутренних частей j ≠ k (головы откалиброваны по частям ∉ {k, j}) и применяется к выбранным заявкам части k
              (головы откалиброваны по частям ≠ k);
  wc FIXED  — T − C у FIXED на ID с кросс-подгонкой (отрицательный контроль: отбора нет).
Части кросс-подгонки закреплены за исходными задачами ID (как в OCSHIFT-01): копии задачи в выборке остаются в одной части.
Интервал — M4 (OCINT-01): точка ± z·ст. откл. повторов бутстрепа, z = Φ⁻¹(1 − LEVEL)."""
import json
import multiprocessing as mp
import os
import sys
import time

import numpy as np
from scipy import optimize
from scipy.stats import norm, spearmanr
from sklearn._isotonic import _make_unique

HERE = os.path.dirname(os.path.abspath(__file__))
EXP = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(EXP, '2026-11-15_OCSHIFT-01'))
sys.path.insert(0, os.path.join(EXP, '2026-11-15_OCINT-01'))
import analyze_ocshift as S  # noqa: E402
import analyze_ocshift_test as A  # noqa: E402  (range_guard, heterogeneity)
import ocint as O  # noqa: E402  (миры: world_params, draw)

Q, T = S.Q, S.T
K_CV = S.K_CV
LEVEL, DESCR_LEVEL = 0.0025, 0.005
Z = float(norm.ppf(1 - LEVEL))
BAND = 0.02                                   # полоса эквивалентности P3 и N
SEED_CV, SEED_BOOT = 7_620_000, 7_830_000     # части — как в OCSHIFT-01 (7 620 000 + 10·X + p); бутстреп — новое зерно
META_T, META_T_PILOT = 7_840_000, 7_890_000   # миры проверки хвоста Т (тест) и пилота
MIN_VALID_FRAC = 0.8
CHECK_TOL = 1e-3
FIXED_NAME, FIXED_WORLD = 'pythia-2.8b-deduped', 6
TAIL_MAX = 0.0075                             # Т: доля односторонних промахов M4 при LEVEL — не выше втрое большей номинала
EST = ('CONF', 'POST-CV', 'ONE-BEST', 'FIXED', 'POST-IN')
RULES = {'P0': ('wc CONF', None, 'sign'), 'P1': ('ioi POST-CV', 'ioi CONF', 'sign'), 'P2': ('ioi POST-CV', 'ioi ONE-BEST', 'sign'),
         'P3': ('wc POST', None, 'equiv'), 'N': ('wc FIXED', None, 'equiv')}
DESCR = {'Брайер POST-CV − ONE-BEST': ('brier POST-CV', 'brier ONE-BEST'), 'Брайер POST-CV − CONF': ('brier POST-CV', 'brier CONF'),
         'P2: разность незнания': ('ign POST-CV', 'ign ONE-BEST'), 'P2: разность самообмана': ('dec POST-CV', 'dec ONE-BEST'),
         'самообман POST-CV вне диапазона': ('dec POST-CV', None), 'самообман CONF вне диапазона': ('dec CONF', None),
         'самообман ONE-BEST вне диапазона': ('dec ONE-BEST', None), 'самообман FIXED вне диапазона': ('dec FIXED', None),
         'POST-IN − POST-CV': ('ioi POST-IN', 'ioi POST-CV'), 'POST-CV − FIXED': ('ioi POST-CV', 'ioi FIXED'),
         'ONE-BEST − FIXED': ('ioi ONE-BEST', 'ioi FIXED'), 'wc ONE-BEST': ('wc ONE-BEST', None),
         'wc POST − wc CONF': ('wc POST', 'wc CONF'), 'wc FIXED − wc ONE-BEST': ('wc FIXED', 'wc ONE-BEST')}
U = 'не определено (проверка метода)'
UF = 'не определено (голова FIXED вне толпы в годной среде)'
UN = 'не определено (отрицательный контроль N опровергнут)'


# ───────────── изотоника без проверок входа (тот же расчёт, что sklearn 1.9.1; равенство — test_ocpost.py)
FAST = True                                   # False — зарегистрированный путь OCSHIFT-01 (T.calibrate, S.iso_fit) для сверки


def iso_predict(x, y, q):
    """Как IsotonicRegression(out_of_bounds='clip', y_min=0, y_max=1).fit(x, y).predict(q) в sklearn 1.9.1 (_build_y,
    isotonic_regression, _build_f, _transform) — те же шаги и те же вызовы, без проверок входа: порядок lexsort((y, x)),
    _make_unique, scipy.optimize.isotonic_regression, обрезка в [0, 1], удаление лишних точек, обрезка запроса в [min x, max x],
    линейная интерполяция. interp1d(kind='linear') при одномерном y в scipy 1.18.1 считает через np.interp
    (_call_linear_np) — здесь np.interp вызывается прямо; равенство с sklearn до бита — test_ocpost.py."""
    x = np.ascontiguousarray(x, dtype=np.float64)
    y = np.ascontiguousarray(y, dtype=np.float64)
    order = np.lexsort((y, x))
    xs, ys = x[order], y[order]
    ux, uy, uw = (np.asarray(a) for a in _make_unique(xs, ys, np.ones_like(xs)))
    yy = np.asarray(optimize.isotonic_regression(y=uy, weights=uw, increasing=True).x, dtype=np.float64)
    np.clip(yy, 0.0, 1.0, yy)
    lo, hi = np.min(ux), np.max(ux)
    keep = np.ones((len(yy),), dtype=bool)
    keep[1:-1] = np.logical_or(np.not_equal(yy[1:-1], yy[:-2]), np.not_equal(yy[1:-1], yy[2:]))
    X, Y = ux[keep], yy[keep]
    qq = np.clip(np.ascontiguousarray(q, dtype=np.float64).reshape(-1), lo, hi)
    if len(Y) == 1:
        return Y.repeat(qq.shape)
    return np.interp(qq, X, Y)


def calibrate(M, corr, fit_idx, cols):
    """Как analyze_ocgeo_test.calibrate (изотоника по задачам fit_idx, предсказание на cols)."""
    if not FAST:
        return T.calibrate(M, corr, fit_idx, cols)
    out = np.zeros((M.shape[0], len(cols)))
    for i in range(M.shape[0]):
        out[i] = iso_predict(M[i][fit_idx], corr[i][fit_idx].astype(float), M[i][cols])
    return out


def iso_map(x, y, q):
    """Как analyze_ocshift.iso_fit(x, y).predict(q)."""
    return S.iso_fit(x, y).predict(q) if not FAST else iso_predict(x, y, q)


# ───────────── статистики одной выборки
def post_stats(st, fit, cols, fx):
    """Все числа одной выборки (точка или повтор бутстрепа) плоским словарём. fx — номер головы FIXED в толпе или None."""
    keep = st['keep']
    cs = st['corr'][keep]
    L = st['logp'][keep]                                         # оценщик CONF: заявка головы — её logp (analyze_ocrep.scores)
    y_c, y_f = cs[:, cols].astype(float), cs[:, fit].astype(float)
    hb = int(np.argmax(y_f.mean(1)))                             # при равенстве — первая по порядку
    out = {}

    def put(name, t, c):
        m = S.meas(t, c)
        for k in ('T', 'C', 'ioi', 'brier'):
            out[f'{k} {name}'] = m[k]
        out[f'ign {name}'] = 1 - m['T']
        out[f'dec {name}'] = max(0.0, m['C'] - m['T'])
    cal = calibrate(L, cs, fit, cols)
    t, c, _ = S.select(cal, y_c)
    put('CONF', t, c)
    put('ONE-BEST', y_c[hb], cal[hb])
    if fx is not None:
        put('FIXED', y_c[fx], cal[fx])
    ti, ci, _ = S.select(calibrate(L, cs, fit, fit), y_f)
    put('POST-IN', t, iso_map(ci, ti, c))
    fo = st['fold_of'][fit]
    parts = [fit[fo == k] for k in range(K_CV)]
    tt, cc, tb, cb, tf, cf = [], [], [], [], [], []
    for k in range(K_CV):                                        # внешняя кросс-подгонка: как wc CONF в analyze_ocshift.core
        tr = fit[fo != k]
        ck = calibrate(L, cs, tr, parts[k])
        tk, ckk, _ = S.select(ck, cs[:, parts[k]].astype(float))
        tt.append(tk)
        cc.append(ckk)
        hk = int(np.argmax(cs[:, tr].mean(1)))
        tb.append(cs[hk, parts[k]].astype(float))
        cb.append(ck[hk])
        if fx is not None:
            tf.append(cs[fx, parts[k]].astype(float))
            cf.append(ck[fx])
    cv_t, cv_c = np.concatenate(tt), np.concatenate(cc)
    put('POST-CV', t, iso_map(cv_c, cv_t, c))
    out['wc CONF'] = float(np.mean(cv_t) - np.mean(cv_c))
    out['wc ONE-BEST'] = float(np.mean(np.concatenate(tb)) - np.mean(np.concatenate(cb)))
    out['wc FIXED'] = float(np.mean(np.concatenate(tf)) - np.mean(np.concatenate(cf))) if fx is not None else float('nan')
    # вложенная кросс-подгонка: калибровка голов по частям ∉ {k, j} — одна на пару, предсказание сразу на части k и j
    inner = {}
    for k in range(K_CV):
        for j in range(k + 1, K_CV):
            tr = fit[(fo != k) & (fo != j)]
            te = np.concatenate([parts[k], parts[j]])
            ck = calibrate(L, cs, tr, te)
            nk = len(parts[k])
            inner[(j, k)] = S.select(ck[:, :nk], cs[:, parts[k]].astype(float))[:2]     # для внешней части j: пары части k
            inner[(k, j)] = S.select(ck[:, nk:], cs[:, parts[j]].astype(float))[:2]     # для внешней части k: пары части j
    tp, cp_ = [], []
    for k in range(K_CV):
        it = np.concatenate([inner[(k, j)][0] for j in range(K_CV) if j != k])
        ic = np.concatenate([inner[(k, j)][1] for j in range(K_CV) if j != k])
        tp.append(tt[k])
        cp_.append(iso_map(ic, it, cc[k]))
    out['wc POST'] = float(np.mean(np.concatenate(tp)) - np.mean(np.concatenate(cp_)))
    if fx is None:
        for k in ('T', 'C', 'ioi', 'brier', 'ign', 'dec'):
            out[f'{k} FIXED'] = float('nan')
    out['one_best_is_fixed'] = float(fx is not None and hb == fx)
    return out


def val(d, pair):
    return d[pair[0]] - (d[pair[1]] if pair[1] else 0.0)


def m4(point, boot, level=LEVEL):
    sd = float(np.std(boot, ddof=1))
    z = float(norm.ppf(1 - level))
    return [float(point - z * sd), float(point + z * sd)], sd


def verdict(kind, iv):
    lo, hi = iv
    if kind == 'sign':
        return 'подтверждено' if hi < 0 else ('опровергнуто' if lo > 0 else 'не решено')
    if lo >= -BAND and hi <= BAND:
        return 'подтверждено'
    return 'опровергнуто' if (hi < -BAND or lo > BAND) else 'не решено'


# ───────────── счёт в процессах
_W = {}


def _init(cfg):
    _W.clear()
    _W.update(cfg)


def _init_worker(cfg):
    from threadpoolctl import threadpool_limits
    threadpool_limits(1)
    _init(cfg)


def _pmap(fn, items, cfg, workers, chunk=None):
    if workers <= 1:
        _init(cfg)
        return [fn(x) for x in items]
    with mp.get_context('fork').Pool(workers, initializer=_init_worker, initargs=(cfg,)) as pool:
        return pool.map(fn, items, chunksize=chunk or max(1, len(items) // (8 * workers)))


def _rep(fc):
    r = post_stats(_W['st'], fc[0], fc[1], _W['fx'])
    return [r[k] for k in _W['keys']]


def fixed_index(info):
    names = [info['names'][k] for k in info['keep']]
    return names.index(FIXED_NAME) if FIXED_NAME in names else None


def env_boot(env, off, B, workers):
    """Точка и B повторов бутстрепа одной среды (вложенный: выборка ID, затем OOD; как в OCSHIFT-01)."""
    st, info = S.prepare(env, SEED_CV + off)
    r = dict(n_id=int(len(info['idi'])), n_ood=int(len(info['ood'])), method=info['method'], crowd=[info['names'][k] for k in info['keep']],
             valid=info['valid'], seed_cv=SEED_CV + off, seed_boot=SEED_BOOT + off)
    if not info['valid']:
        return r, None, None
    fx = fixed_index(info)
    r['fixed_in_crowd'] = fx is not None
    pt = post_stats(st, info['idi'], info['ood'], fx)
    keys = sorted(pt)
    g = np.random.default_rng(SEED_BOOT + off)
    draws = [(g.choice(info['idi'], len(info['idi'])), g.choice(info['ood'], len(info['ood']))) for _ in range(B)]
    bt = np.array(_pmap(_rep, draws, dict(st=st, keys=keys, fx=fx), workers), float).T
    keep = info['keep']
    cs = st['corr'][keep]
    acc_id, acc_ood = cs[:, info['idi']].mean(1), cs[:, info['ood']].mean(1)
    hb = int(np.argmax(acc_id))
    r['point'] = pt
    r['extras'] = dict(accuracy={r['crowd'][k]: dict(id=float(acc_id[k]), ood=float(acc_ood[k])) for k in range(len(keep))},
                       one_best=r['crowd'][hb], one_best_is_fixed=bool(fx is not None and hb == fx),
                       id_gap=float(np.sort(acc_id)[-1] - np.sort(acc_id)[-2]), oracle_ood=float(cs[:, info['ood']].any(0).mean()))
    return r, pt, {k: bt[j] for j, k in enumerate(keys)}


def load_envs(specs):
    envs, check, src = {}, None, []
    for spec in specs:
        d, e = S.load_spec(spec)
        if d is not None:
            check = S.check_block(e)
            src.append(dict(spec=spec, mode=d.get('mode'), info=d.get('info'), design=d.get('design'),
                            head_errors=[f"{h['model']}@{h['revision']}: {h['error']}" for h in d['heads'] if 'error' in h]))
            e = {k: v for k, v in e.items() if v['meta'].get('kind') == 'test'}
        else:
            src.append(dict(spec=spec))
        envs.update(e)
    return envs, check, src


def offset(meta, i):
    return (10 * meta['X'] + meta['p']) if 'X' in meta else i


# ───────────── тест
def test(dst, specs, B=10000, workers=1):
    t00 = time.time()
    envs, check, src = load_envs(specs)
    names = list(envs)
    res = dict(sources=src, level=LEVEL, z=Z, band=BAND, B=B, check=check, check_tol=CHECK_TOL, envs={})
    check_ok = True if check is None else bool(check['answers_equal'] and check['max_abs_dlogp'] <= CHECK_TOL and check['n_heads'] == 9)
    res['check_ok'] = check_ok
    pts, boots, valid = {}, {}, []
    for i, name in enumerate(names):
        t0 = time.time()
        meta = envs[name]['meta']
        r, pt, bt = env_boot(envs[name], offset(meta, i), B, workers)
        r['meta'] = meta
        if pt is not None:
            valid.append(name)
            pts[name], boots[name] = pt, bt
            r['rules_env'] = {k: dict(point=float(val(pt, p[:2])), sd=float(np.std(val(bt, p[:2]), ddof=1))) for k, p in RULES.items()}
        r['seconds'] = round(time.time() - t0, 1)
        res['envs'][name] = r
        print(f"{name}: ID {r['n_id']}, OOD {r['n_ood']}, толпа {len(r['crowd'])}, годна {r['valid']}, {r['seconds']} с", flush=True)
    m = len(valid)
    method_ok = bool(check_ok and m >= int(np.ceil(MIN_VALID_FRAC * len(names))) and m >= 1)
    fixed_ok = bool(all(res['envs'][n].get('fixed_in_crowd') for n in valid))
    res['method'] = dict(ok=method_ok, n_envs=len(names), n_valid=m, valid=valid, fixed_in_all_valid=fixed_ok)
    if m == 0:
        res['verdicts'] = {k: U for k in RULES}
        res['verdicts']['Т'] = 'проверяется отдельно (tail)'
        json.dump(res, open(dst, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
        return res
    group = {n: envs[n]['meta'].get('X', n) for n in valid}

    def mean_entry(pair, level):
        pt = float(np.mean([val(pts[n], pair) for n in valid]))
        bt = np.mean([val(boots[n], pair) for n in valid], 0)
        iv, sd = m4(pt, bt, level)
        return dict(delta=pt, ci=iv, boot_sd=sd, boot_shift=float(np.mean(bt) - pt), share_below_0=float(np.mean(bt < 0)),
                    level=level, by_env={n: float(val(pts[n], pair)) for n in valid}), bt
    for k, (a, b, kind) in RULES.items():
        e, bt = mean_entry((a, b), LEVEL)
        v = verdict(kind, e['ci'])
        if kind == 'sign':                                         # предохранитель «без одного диапазона» (совет 60, п. 5)
            v, e['leave_one_range_out'] = A.range_guard(v, e['by_env'], group)
        e['verdict_rule'] = v
        e['verdict'] = U if not method_ok else (UF if (k == 'N' and not fixed_ok) else v)
        res[k] = e
    if res['N']['verdict'] == 'опровергнуто' and res['P3']['verdict'] not in (U,):
        res['P3']['verdict_before_N'] = res['P3']['verdict']
        res['P3']['verdict'] = UN
    for k, pair in DESCR.items():
        if any(not np.isfinite(val(pts[n], pair)) for n in valid):
            continue
        res[f'descr_{k}'] = mean_entry(pair, DESCR_LEVEL)[0]
    # правило чтения P2 (HYPOTHESIS): «подтверждено» по ИОИ при Брайере POST-CV хуже ONE-BEST
    bri = res.get('descr_Брайер POST-CV − ONE-BEST')
    if bri is not None:
        iv, _ = m4(bri['delta'], np.mean([val(boots[n], DESCR['Брайер POST-CV − ONE-BEST']) for n in valid], 0), LEVEL)
        side = 'хуже' if iv[0] > 0 else ('лучше' if iv[1] < 0 else 'вывода нет')
        res['P2']['brier_reading'] = dict(ci=iv, side=side,
                                          note=('по ИОИ лучше за счёт заниженных заявок, по Брайеру хуже'
                                                if (res['P2']['verdict'] == 'подтверждено' and side == 'хуже') else ''))
    # чтение P3 при P0 (записано до данных): без подтверждённого P0 нельзя сказать, что вторая калибровка что-то «сняла»
    res['P3']['reading'] = ('самообман на ID после второй калибровки — в полосе ±0,02; что он был, показывает P0'
                            if res['P0']['verdict'] == 'подтверждено' else 'P0 не подтверждено: «снят» не читается, только «в полосе»')
    if res['N']['verdict'] != 'подтверждено':
        res['P3']['reading'] += '; отрицательный контроль N не подтверждён: несмещённость счёта T − C без отбора не показана'
    d_ign, d_dec = res.get('descr_P2: разность незнания'), res.get('descr_P2: разность самообмана')
    if d_ign and d_dec:
        assert abs(d_ign['delta'] + d_dec['delta'] - res['P2']['delta']) < 1e-9, 'разложение P2 не сошлось'
    if m >= 2:
        res['P2']['heterogeneity_descr'] = A.heterogeneity([val(pts[n], RULES['P2'][:2]) for n in valid],
                                                           [val(boots[n], RULES['P2'][:2]) for n in valid])
    if m >= 4:
        gap = [res['envs'][n]['extras']['id_gap'] for n in valid]
        d2 = [val(pts[n], RULES['P2'][:2]) for n in valid]
        rho = spearmanr(gap, d2)
        res['P2']['dominance_descr'] = dict(spearman=float(rho[0]), p=float(rho[1]), n=m, note='описательно; n мало')
    res['verdicts'] = {k: res[k]['verdict'] for k in RULES}
    res['verdicts']['Т'] = 'проверяется отдельно (tail)'
    res['verdict'] = '; '.join(f'{k}: {v}' for k, v in res['verdicts'].items())
    res['seconds'] = round(time.time() - t00, 1)
    json.dump(res, open(dst, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print('вердикт:', res['verdict'])
    for k in RULES:
        e = res[k]
        print(f"{k}: Δ {e['delta']:+.4f} M4 [{e['ci'][0]:+.4f}; {e['ci'][1]:+.4f}] ст. откл. {e['boot_sd']:.4f} сдвиг {e['boot_shift']:+.4f}"
              + (f" | без диапазона: {e['leave_one_range_out']['holds']}" if 'leave_one_range_out' in e else ''))
    print('сверка цепочки:', None if check is None else dict(answers_equal=check['answers_equal'], max_abs_dlogp=check['max_abs_dlogp']),
          '| годных сред', m, 'из', len(names), '| время', res['seconds'], 'с')
    return res


# ───────────── пилот: сверка с OCSHIFT-01 и мощность
REPRO = {'ioi CONF': 'ioi CONF', 'ioi ONE-BEST': 'ioi ONE-BEST', 'wc CONF': 'wc CONF', 'wc ONE-BEST': 'wc ONE-BEST',
         'ioi POST-IN': 'ioi POST-IN CONF', 'brier CONF': 'brier CONF', 'T CONF': 'T CONF', 'C CONF': 'C CONF'}


def power_one(kind, mu, tau, s, m, z=Z):
    """Мощность правила для среднего по m свежим средам: точка ~ N(mu, (tau² + s²)/m), полуширина M4 = z·s/√m."""
    se, h = np.sqrt((tau ** 2 + s ** 2) / m), z * s / np.sqrt(m)
    if kind == 'sign':
        return float(norm.cdf((-mu - h) / se)), float(norm.sf((-mu + h) / se))     # подтверждено, опровергнуто
    if h >= BAND:
        return 0.0, float(norm.cdf((-BAND - h - mu) / se) + norm.sf((BAND + h - mu) / se))
    return float(norm.cdf((BAND - h - mu) / se) - norm.cdf((-BAND + h - mu) / se)), float(norm.cdf((-BAND - h - mu) / se) + norm.sf((BAND + h - mu) / se))


def pilot(dst, specs, B=1000, workers=1, ref=None, m_new=5):
    t00 = time.time()
    envs, check, src = load_envs(specs)
    names = list(envs)
    res = dict(sources=src, B=B, level=LEVEL, z=Z, band=BAND, m_new=m_new, envs={})
    pts, boots = {}, {}
    for i, name in enumerate(names):
        t0 = time.time()
        meta = envs[name]['meta']
        r, pt, bt = env_boot(envs[name], offset(meta, i), B, workers)
        r['meta'] = meta
        if pt is not None:
            pts[name], boots[name] = pt, bt
            r['rules_env'] = {k: dict(point=float(val(pt, p[:2])), sd=float(np.std(val(bt, p[:2]), ddof=1)),
                                      boot_shift=float(np.mean(val(bt, p[:2])) - val(pt, p[:2]))) for k, p in RULES.items()}
            r['descr_env'] = {k: dict(point=float(val(pt, p)), sd=float(np.std(val(bt, p), ddof=1))) for k, p in DESCR.items()
                              if np.isfinite(val(pt, p))}
        r['seconds'] = round(time.time() - t0, 1)
        r['seconds_per_rep'] = round(r['seconds'] / max(B, 1), 4)
        res['envs'][name] = r
        print(f"{name}: годна {r['valid']}, {r['seconds']} с ({r['seconds_per_rep']} с на повтор на {workers} проц.)", flush=True)
    valid = list(pts)
    if ref:                                                       # сверка с зарегистрированным анализом OCSHIFT-01 (точки)
        rr = json.load(open(ref, encoding='utf-8'))
        rep = {}
        for n in valid:
            if n not in rr['envs'] or 'point' not in rr['envs'][n]:
                continue
            rp = rr['envs'][n]['point']
            d = {k: abs(pts[n][k] - rp[v]) for k, v in REPRO.items()}
            d['ioi POST-CV'] = abs(pts[n]['ioi POST-CV'] - rr['envs'][n]['extras']['evaluators']['CONF']['post_cv']['ioi'])
            d['brier POST-CV'] = abs(pts[n]['brier POST-CV'] - rr['envs'][n]['extras']['evaluators']['CONF']['post_cv']['brier'])
            d['crowd'] = float(res['envs'][n]['crowd'] != rr['envs'][n]['crowd'])
            rep[n] = d
        res['reproduction'] = dict(max_abs=max(max(v.values()) for v in rep.values()) if rep else None, by_env=rep, ref=ref)
    # мощность: модель «новая среда» (mu, tau по пилотным средам) и перебор наборов «одна среда на диапазон»
    pw = {}
    for k, (a, b, kind) in RULES.items():
        x = np.array([val(pts[n], (a, b)) for n in valid])
        s = np.array([res['envs'][n]['rules_env'][k]['sd'] for n in valid])
        if not np.all(np.isfinite(x)):
            continue
        mu, s_rms = float(x.mean()), float(np.sqrt(np.mean(s ** 2)))
        tau = float(np.sqrt(max(0.0, x.var(ddof=1) - np.mean(s ** 2)))) if len(x) > 1 else 0.0
        conf, ref_ = power_one(kind, mu, tau, s_rms, m_new)
        pw[k] = dict(mu=mu, tau=tau, s_rms=s_rms, power_confirm=conf, power_refute=ref_, kind=kind)
        byx = {}
        for n in valid:
            byx.setdefault(envs[n]['meta'].get('X', n), []).append(n)
        if all(len(v) == 2 for v in byx.values()) and len(byx) == m_new:
            outc = {}
            xs = sorted(byx)
            for mask in range(2 ** len(xs)):
                sel = [byx[xx][(mask >> j) & 1] for j, xx in enumerate(xs)]
                ptm = float(np.mean([val(pts[n], (a, b)) for n in sel]))
                btm = np.mean([val(boots[n], (a, b)) for n in sel], 0)
                iv, _ = m4(ptm, btm)
                v = verdict(kind, iv)
                if kind == 'sign':
                    v, _ = A.range_guard(v, {n: float(val(pts[n], (a, b))) for n in sel}, {n: envs[n]['meta']['X'] for n in sel})
                outc[v] = outc.get(v, 0) + 1
            pw[k]['subsets'] = dict(n=2 ** len(xs), outcomes=outc)
    res['power'] = pw
    res['seconds'] = round(time.time() - t00, 1)
    json.dump(res, open(dst, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print(json.dumps(dict(power=pw, reproduction_max_abs=res.get('reproduction', {}).get('max_abs')), ensure_ascii=False, indent=1))
    return res


# ───────────── миры: проверка хвоста M4 (Т)
TAIL_KEYS = list(RULES) + ['Брайер POST-CV − ONE-BEST', 'самообман POST-CV вне диапазона']
TAIL_PAIRS = {**{k: v[:2] for k, v in RULES.items()}, **{k: DESCR[k] for k in TAIL_KEYS[len(RULES):]}}


def _world_point(st, idi, ood):
    fx = st['keep'].index(FIXED_WORLD) if FIXED_WORLD in st['keep'] else None
    return post_stats(st, idi, ood, fx), fx


def _truth(ki):
    k, i = ki
    g = np.random.default_rng([_W['meta'], 1, k, i])
    st, idi, ood = O.draw(_W['pars'][k], g)
    p, fx = _world_point(st, idi, ood)
    return [val(p, TAIL_PAIRS[s]) for s in TAIL_KEYS] + [float(fx is not None)]


def _exp(ki):
    k, i = ki
    g = np.random.default_rng([_W['meta'], 2, k, i])
    st, idi, ood = O.draw(_W['pars'][k], g)
    p, fx = _world_point(st, idi, ood)
    pv = np.array([val(p, TAIL_PAIRS[s]) for s in TAIL_KEYS])
    rb = []
    for _ in range(_W['B']):
        r = post_stats(st, g.choice(idi, len(idi)), g.choice(ood, len(ood)), fx)
        rb.append([val(r, TAIL_PAIRS[s]) for s in TAIL_KEYS])
    rb = np.array(rb)
    return pv.tolist(), rb.mean(0).tolist(), rb.std(0, ddof=1).tolist(), len(st['keep']), float(fx is not None)


def worlds(dst, meta=META_T, first=0, n_worlds=30, n_exp=200, n_truth=2000, B=200, workers=4):
    """Миры first … first + n_worlds − 1 (модель OCINT-01, ocint.world_params и ocint.draw; среда 1000 ID и 1200 OOD).
    Правда θ(n) — среднее статистики по n_truth выборкам; в каждом из n_exp опытов — точка, среднее и ст. откл. B повторов."""
    t0 = time.time()
    ks = list(range(first, first + n_worlds))
    pars = {k: O.world_params(k, meta) for k in ks}
    cfg = dict(meta=meta, pars=pars, B=B)
    res = dict(meta=meta, first=first, n_worlds=n_worlds, n_exp=n_exp, n_truth=n_truth, B=B, keys=TAIL_KEYS, level=LEVEL, z=Z, worlds=[])
    for k in ks:
        tr = np.array(_pmap(_truth, [(k, i) for i in range(n_truth)], cfg, workers, chunk=8))
        ex = _pmap(_exp, [(k, i) for i in range(n_exp)], cfg, workers, chunk=1)
        p = pars[k]
        res['worlds'].append(dict(k=k, acc_id=[float(norm.cdf(x)) for x in p['mu_id']], acc_ood=[float(norm.cdf(x - d)) for x, d in zip(p['mu_id'], p['drop'])],
                                  truth=dict(zip(TAIL_KEYS, map(float, tr[:, :-1].mean(0)))), sd_true=dict(zip(TAIL_KEYS, map(float, tr[:, :-1].std(0, ddof=1)))),
                                  fixed_share_truth=float(tr[:, -1].mean()),
                                  point=[e[0] for e in ex], boot_mean=[e[1] for e in ex], boot_sd=[e[2] for e in ex],
                                  crowd=[e[3] for e in ex], fixed=[e[4] for e in ex], seconds=round(time.time() - t0, 1)))
        json.dump(res, open(dst, 'w', encoding='utf-8'), ensure_ascii=False)
        print(f'мир {k}: правда {n_truth}, опыты {n_exp} × {B} повторов, {time.time() - t0:.0f} с', flush=True)
    res['seconds'] = round(time.time() - t0, 1)
    json.dump(res, open(dst, 'w', encoding='utf-8'), ensure_ascii=False)
    return res


def cp(x, n, level, side):
    return O.cp(x, n, level, side)


def tail(dst, parts):
    """Т: доли односторонних промахов M4 (уровень LEVEL на сторону) по всем опытам всех миров; правило — по границам
    Клоппера — Пирсона: «подтверждено», если у каждой статистики P0–P3, N и каждой стороны верхняя граница (уровень LEVEL)
    < TAIL_MAX; «опровергнуто», если хоть у одной нижняя граница (уровень LEVEL / 10, поправка на 10 проверок) > TAIL_MAX."""
    W, metas = [], set()
    for f in parts:
        r = json.load(open(f, encoding='utf-8'))
        metas.add(r['meta'])
        W += r['worlds']
    assert len(metas) == 1, 'части из разных миров'
    ks = [w['k'] for w in W]
    assert len(set(ks)) == len(ks), 'мир повторён в частях'
    out = dict(meta=metas.pop(), n_worlds=len(W), worlds=sorted(ks), level=LEVEL, z=Z, tail_max=TAIL_MAX, stats={})
    n_chk = 2 * len(RULES)
    for si, s in enumerate(TAIL_KEYS):
        lo_m, hi_m, nn, per_world, shift, ratio, nan_n = 0, 0, 0, [], [], [], 0
        for w in W:
            th = w['truth'][s]
            P = np.array([p[si] for p in w['point']])
            SD = np.array([x[si] for x in w['boot_sd']])
            BM = np.array([x[si] for x in w['boot_mean']])
            ok = np.isfinite(P) & np.isfinite(SD) & np.isfinite(th)
            nan_n += int((~ok).sum())
            P, SD, BM = P[ok], SD[ok], BM[ok]
            lo, hi = P - Z * SD, P + Z * SD
            a, b = int((th < lo).sum()), int((th > hi).sum())
            lo_m += a
            hi_m += b
            nn += len(P)
            per_world.append(dict(k=w['k'], miss_low=a, miss_high=b, n=int(len(P))))
            shift.append(float(np.mean((BM - P) / np.maximum(SD, 1e-12))))
            ratio.append(float(np.sqrt(np.mean(SD ** 2)) / max(w['sd_true'][s], 1e-12)))
        e = dict(n=nn, n_nan=nan_n, miss_low=lo_m, miss_high=hi_m, rate_low=lo_m / max(nn, 1), rate_high=hi_m / max(nn, 1),
                 upper_low=cp(lo_m, nn, LEVEL, 'hi'), upper_high=cp(hi_m, nn, LEVEL, 'hi'),
                 lower_low=cp(lo_m, nn, LEVEL / n_chk, 'lo'), lower_high=cp(hi_m, nn, LEVEL / n_chk, 'lo'),
                 sd_ratio_mean=float(np.mean(ratio)), shift_in_sd_mean=float(np.mean(shift)), by_world=per_world,
                 truth_by_world={w['k']: w['truth'][s] for w in W})
        out['stats'][s] = e
    rs = [out['stats'][s] for s in RULES]
    conf = all(e['upper_low'] < TAIL_MAX and e['upper_high'] < TAIL_MAX for e in rs)
    refu = any(e['lower_low'] > TAIL_MAX or e['lower_high'] > TAIL_MAX for e in rs)
    out['verdict'] = 'подтверждено' if (conf and not refu) else ('опровергнуто' if refu else 'не решено')
    # описательно: среднее по группам из 5 миров (как среднее по 5 средам теста); ст. откл. среднего — √Σsd² / 5
    grp = []
    for g0 in range(0, len(W) - len(W) % 5, 5):
        grp.append(W[g0:g0 + 5])
    md = {}
    for si, s in enumerate(TAIL_KEYS):
        a = b = n = 0
        for G in grp:
            th = np.mean([w['truth'][s] for w in G])
            ne = min(len(w['point']) for w in G)
            for j in range(ne):
                P = np.mean([w['point'][j][si] for w in G])
                SD = np.sqrt(np.sum([w['boot_sd'][j][si] ** 2 for w in G])) / len(G)
                if not (np.isfinite(P) and np.isfinite(SD)):
                    continue
                a += int(th < P - Z * SD)
                b += int(th > P + Z * SD)
                n += 1
        md[s] = dict(n=n, miss_low=a, miss_high=b)
    out['mean_of_5_descr'] = md
    json.dump(out, open(dst, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print('Т:', out['verdict'])
    for s in TAIL_KEYS:
        e = out['stats'][s]
        print(f"{s}: n {e['n']}, промахов снизу {e['miss_low']} (верх. гр. {e['upper_low']:.4f}), сверху {e['miss_high']} (верх. гр. {e['upper_high']:.4f}), "
              f"ст. откл. повторов / истинное {e['sd_ratio_mean']:.3f}, сдвиг {e['shift_in_sd_mean']:+.3f} ст. откл.")
    return out


def args_of(a, name, default, cast=int):
    return cast(a[a.index(name) + 1]) if name in a else default


def positional(a, flags):
    skip = set()
    for f in flags:
        if f in a:
            skip |= {a.index(f), a.index(f) + 1}
    return [x for i, x in enumerate(a) if i not in skip]


if __name__ == '__main__':
    cmd, a = sys.argv[1], sys.argv[2:]
    W = args_of(a, '--workers', os.cpu_count() or 1)
    if cmd == 'test':
        pos = positional(a, ('--boot', '--workers'))
        test(pos[0], pos[1:], args_of(a, '--boot', 10000), W)
    elif cmd == 'pilot':
        pos = positional(a, ('--boot', '--workers', '--ref'))
        pilot(pos[0], pos[1:], args_of(a, '--boot', 1000), W, args_of(a, '--ref', None, str))
    elif cmd == 'worlds':
        pos = positional(a, ('--meta', '--first', '--worlds', '--exp', '--truth', '--boot', '--workers'))
        worlds(pos[0], args_of(a, '--meta', META_T), args_of(a, '--first', 0), args_of(a, '--worlds', 30), args_of(a, '--exp', 200),
               args_of(a, '--truth', 2000), args_of(a, '--boot', 200), W)
    elif cmd == 'tail':
        tail(a[0], a[1:])
    else:
        raise SystemExit(__doc__)
