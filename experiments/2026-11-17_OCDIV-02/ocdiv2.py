#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""OCDIV-02 «ОЦЕНЩИК-ТРУДНЫЙ-СДВИГ»: сборка ответов, статистики Т1–Т4, разбор пилота с правилом выбора семейства (HYPOTHESIS.md,
коммит 7187bab5) и мощность. Анализ теста — после PREREG.
  python3 ocdiv2.py merge OUT_DIR PHASE FAMILY JOB_DIR [JOB_DIR ...]   — answers.json вида ocdiv.merge (формат analyze_ocshift)
  python3 ocdiv2.py pilot RESULT.json MERGED_THOUSANDS MERGED_LENGTH [--boot 200] [--workers 4] [--test-phase test|test2]
  python3 ocdiv2.py test  RESULT.json MERGED_DIR [--boot 10000] [--workers 4]   — тест (константы FAMILY_TEST, T3_HEADS, T2_DESCRIPTIVE,
      T4_STRATA задаются в PREREG по пилоту)
Код счёта — зарегистрированный код прежних опытов: проверка метода и массивы — analyze_ocshift.prepare (в масштабе теста —
ocdiv.prepare_scaled); оценщики — ocpost.post_stats и ocdiv.agree_conf (ocdiv.stats_div); калибровка головы — ocpost.calibrate.
Новое здесь: Т3 (доля незамеченного разрыва), Т4 (ложное большинство и перестановочный нуль), безусловное совпадение ошибок,
правило выбора семейства и мощность правил вида «over» (Т1) и «unit» (Т3)."""
import glob
import itertools
import json
import os
import sys
import time
import warnings

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
EXP = os.path.dirname(HERE)
ROOT = os.path.dirname(EXP)
sys.path.insert(0, os.path.join(EXP, '2026-11-16_OCDIV-01'))
sys.path.insert(0, HERE)
import ocdiv as V  # noqa: E402   OCDIV-01 (регистрация c626aa32): CROWD, FIXED_NEW, prepare_scaled, stats_div, vendor, agg_power, power_rule
import ocdiv2_extract as D2  # noqa: E402
P, S = V.P, V.S

CROWD, FIXED_NEW = V.CROWD, V.FIXED_NEW
FAM_INDEX = {f: i for i, f in enumerate(D2.FAMILIES)}
# правило выбора семейства (HYPOTHESIS.md, записано до пилота). MAX_SEC: в HYPOTHESIS было 1,5 с на задачу; до пилота заменено условием
# «задание теста (2200 задач одной среды) у самой медленной головы — не больше половины лимита шага neu-par (340 мин)» — 4,6 с на задачу
# (DECISIONS 17.11.2026: по 1,5 с не прошёл бы и OCDIV-01 — SmolLM2-1.7B, 3437,4 с на 2200 задач)
DROP_MIN, DROP_HEADS_MIN, PASS_HEADS_MIN, PASS_ENVS_MIN = 0.10, 3, 6, 4
MAX_SEC = round(0.5 * 340 * 60 / 2200, 1)
SEED_CV2, SEED_BOOT_PILOT, SEED_NULL, SEED_NULL_BOOT, SEED_POWER = 8_200_000, 8_300_000, 8_400_000, 8_450_000, 8_600_000
K_NULL_POINT, K_NULL_BOOT = 1000, 10          # перестановок нуля: для точки и для каждого повтора бутстрепа
NONE_CODE = np.int64(2 ** 62)                 # ответ без числа: код NONE_CODE + номер головы — не совпадает ни с чем и не голос


def off_of(meta):
    """Смещение зёрен среды: 100·(номер семейства) + 10·(номер X в семействе) + p."""
    fam = meta['family']
    return 100 * FAM_INDEX[fam] + 10 * list(D2.FAMILIES[fam]['X']).index(int(meta['X'])) + int(meta['p'])


def kind_of(d):
    """Вид ошибки (HYPOTHESIS): «перенос» — |d| записывается только нулями и единицами и кончается нулём; «прочее» — иначе."""
    s = str(abs(int(d)))
    return 'перенос' if (s[-1] == '0' and set(s) <= {'0', '1'}) else 'прочее'


def carries(a, b):
    """Число разрядов с переносом при сложении a + b (строение задачи, без ответов голов)."""
    c, k = 0, 0
    while a or b or c:
        s = a % 10 + b % 10 + c
        c = 1 if s >= 10 else 0
        k += c
        a, b = a // 10, b // 10
    return k


# ───────────── сборка
def merge(out_dir, phase, family, job_dirs):
    """Сборка ответов голов на средах одного семейства. Номера задач, ключи (a, b) и sha256 подсказки сверяются со средами
    ocdiv2_extract.envs_ocdiv2; любое расхождение, повтор среды или разная ревизия одной головы — СТОП. Голова, у которой есть не все
    среды семейства или ревизия не совпала с регистрацией OCDIV-01 (ocdiv.CROWD), уходит в head_errors."""
    envs = D2.envs_ocdiv2(phase, (family,))
    per, errors = {}, []
    for jd in job_dirs:
        for f in sorted(glob.glob(os.path.join(jd, 'answers_*.json'))):
            h = json.load(open(f, encoding='utf-8'))
            rel = os.path.relpath(f, ROOT)
            if h.get('phase') != phase:
                continue
            if 'error' in h or 'cols' not in h:
                errors.append(dict(model=h.get('model'), error=h.get('error', 'нет cols'), file=rel))
                continue
            rev = h.get('commit') or h['revision']
            r = per.setdefault(h['repo'], dict(commit=rev, cols={}, seconds_env={}, files=[], versions=[], cpu_models=[]))
            if rev != r['commit']:
                raise SystemExit(f"СТОП: у {h['repo']} ревизия {rev} в {rel} не равна {r['commit']} в другом файле той же головы")
            h_env = {x['name']: x for x in h.get('envs', [])}
            used = False
            for e in envs:
                if e['name'] not in h['cols']:
                    continue
                he = h_env.get(e['name'], {})
                if he.get('idx') is None or list(he['idx']) != list(e['idx']):
                    raise SystemExit(f"СТОП: номера задач среды {e['name']} у {h['repo']} не совпали со средой ({rel})")
                if 'keys' not in he or [list(k) for k in he['keys']] != [[q['a'], q['b']] for q in e['problems']]:
                    raise SystemExit(f"СТОП: ключи задач (a, b) среды {e['name']} у {h['repo']} не совпали ({rel})")
                if he.get('prompt_sha256') != D2.DX.prompt_sha(e['prompt_head']):
                    raise SystemExit(f"СТОП: подсказка среды {e['name']} у {h['repo']} не совпала ({rel})")
                if e['name'] in r['cols']:
                    raise SystemExit(f"СТОП: среда {e['name']} у {h['repo']} пришла дважды ({rel})")
                if any(len(v) != len(e['problems']) for v in h['cols'][e['name']].values() if isinstance(v, list)):
                    raise SystemExit(f"СТОП: длина столбцов среды {e['name']} у {h['repo']} не равна числу задач ({rel})")
                r['cols'][e['name']] = h['cols'][e['name']]
                r['seconds_env'][e['name']] = (h.get('seconds_env') or {}).get(e['name'])
                used = True
            if used:
                r['files'].append(rel)
                r['versions'].append(h.get('versions') or {})
                r['cpu_models'].append(h.get('cpu_model'))
    heads = []
    for repo, r in per.items():
        nm = repo.split('/')[-1]
        if len(r['cols']) != len(envs):
            errors.append(dict(model=repo, error=f"сред {len(r['cols'])} из {len(envs)}", file=', '.join(r['files'])))
            continue
        if nm not in CROWD or CROWD[nm] != f"{repo}@{r['commit']}":
            errors.append(dict(model=repo, error=f"ревизия {r['commit']} не та, что в ocdiv.CROWD", file=', '.join(r['files'])))
            continue
        heads.append(dict(model=nm, repo=repo, revision=r['commit'], vendor=V.vendor(repo), seconds_env=r['seconds_env'],
                          n_tasks=sum(len(e['problems']) for e in envs), files=r['files'], versions=r['versions'], cpu_models=r['cpu_models'],
                          cols={e['name']: r['cols'][e['name']] for e in envs}))
    heads.sort(key=lambda h: list(CROWD).index(h['model']))
    os.makedirs(out_dir, exist_ok=True)
    for e in envs:
        e['kind'] = 'test'                                  # S.load_new берёт все среды; метка — для ocpost.load_envs
    d = dict(mode=phase, family=family, envs=envs, heads=heads, head_errors=errors, keys_checked=True,
             info=dict(merged_by='ocdiv2.py merge', when=time.strftime('%Y-%m-%d %H:%M UTC', time.gmtime())))
    json.dump(d, open(os.path.join(out_dir, 'answers.json'), 'w', encoding='utf-8'), ensure_ascii=False)
    print(f'собрано: {phase}, семейство {family}: голов {len(heads)}, ошибок {len(errors)}, сред {len(envs)} → {out_dir}/answers.json')
    for x in errors:
        print('  ошибка:', x)
    return d


# ───────────── совпадение ответов и голоса
def dmat(ans, sums, cols):
    """Смещения d = ответ − правда, (задачи cols × головы); без числа — NONE_CODE + номер головы."""
    nh = len(ans)
    D = np.empty((len(cols), nh), np.int64)
    for k in range(nh):
        for r, j in enumerate(cols):
            x = ans[k][j]
            D[r, k] = (NONE_CODE + k) if x is None else (int(x) - int(sums[j]))
    return D


def false_major(D):
    """По задачам (строки D): какой-нибудь неверный ответ набрал не меньше голосов, чем верный (и хотя бы один голос)."""
    numeric = D < NONE_CODE
    mult = (D[:, :, None] == D[:, None, :]).sum(2)                 # сколько голов дали тот же ответ (у «без числа» — 1)
    c = ((D == 0) & numeric).sum(1)
    w = np.where(numeric & (D != 0), mult, 0).max(1)
    return (w >= 1) & (w >= c)


def permute_cols(D, rng, strata=None):
    """Нуль: внутри каждой головы (столбца) строки переставляются между задачами (внутри страты, если она задана)."""
    out = np.empty_like(D)
    n = D.shape[0]
    groups = [np.arange(n)] if strata is None else [np.nonzero(strata == s)[0] for s in np.unique(strata)]
    for k in range(D.shape[1]):
        col = D[:, k]
        for g in groups:
            out[g, k] = col[g[rng.permutation(len(g))]]
    return out


def f_stats(D, rng, K, strata=None):
    """F, F₀ (среднее по K перестановкам) и F − F₀."""
    F = float(false_major(D).mean())
    F0 = float(np.mean([false_major(permute_cols(D, rng, strata)).mean() for _ in range(K)]))
    return F, F0, F - F0


def uncond(D, labels, pairs):
    """Безусловное совпадение ошибок пары: доля задач, где обе головы ошиблись одним и тем же ответом; по видам ошибок."""
    out = []
    kinds = np.vectorize(lambda d: kind_of(d) if (d != 0 and d < NONE_CODE) else '')(D) if D.size else D
    for i, j in pairs:
        same = (D[:, i] == D[:, j]) & (D[:, i] != 0) & (D[:, i] < NONE_CODE)
        row = dict(i=labels[i], j=labels[j], u=float(same.mean()),
                   both_wrong=float(((D[:, i] != 0) & (D[:, i] < NONE_CODE) & (D[:, j] != 0) & (D[:, j] < NONE_CODE)).mean()))
        for k in ('перенос', 'прочее'):
            row[f'u {k}'] = float((same & (kinds[:, i] == k)).mean())
        out.append(row)
    return out


# ───────────── статистики среды
def t3_parts(st, fit, cols, hidx):
    """Т3: числитель Σ(C − T вне диапазона), знаменатель Σ(T на ID − T вне диапазона) по головам hidx (номера среди keep)."""
    if not hidx:
        return float('nan'), float('nan'), float('nan')
    keep = st['keep']
    cs, L = st['corr'][keep][hidx], st['logp'][keep][hidx]
    cal = P.calibrate(L, cs, fit, cols)
    C, To, Ti = cal.mean(1), cs[:, cols].mean(1), cs[:, fit].mean(1)
    num, den = float(np.sum(C - To)), float(np.sum(Ti - To))
    return num, den, (num / den if den > 0 else float('nan'))


def env_point(st, fit, cols, fx, hidx):
    """Все числа одной выборки (точка или повтор бутстрепа): оценщики (ocdiv.stats_div), Т1, Т2, Т3."""
    r = V.stats_div(st, fit, cols, fx)
    r['T1'] = r['C POST-CV'] - r['T POST-CV']
    r['T2'] = r['ioi AGREE'] - r['ioi POST-CV']
    r['T3 num'], r['T3 den'], r['T3'] = t3_parts(st, fit, cols, hidx)
    r['D3'] = r['C FIXED'] - r['T FIXED']
    r['AGREE − CONF'] = r['ioi AGREE'] - r['ioi CONF (core)']
    return r


def _rep_env(fc):
    W = P._W
    r = env_point(W['st'], fc[0], fc[1], W['fx'], W['hidx'])
    return [r[k] for k in W['keys']]


RULE_KEYS = ('T1', 'T2', 'T3', 'D3', 'AGREE − CONF', 'wc CONF', 'wc POST', 'wc FIXED')


def env_analysis(env, seed_cv, seed_boot, seed_null, seed_null_boot, n_id_test, hnames_t3, B, workers, K_point=K_NULL_POINT, K_boot=K_NULL_BOOT,
                 keep_boot=False):
    """Одна среда: проверка метода в масштабе теста, точки и ст. откл. повторов (B) правил, Т4 и описательные числа.
    keep_boot — вернуть и сами повторы (поля _boot, _boot_T4; в json не пишутся): для среднего по средам в анализе теста."""
    st, info = V.prepare_scaled(env, seed_cv, n_id_test)
    names = [info['names'][k] for k in info['keep']]
    cs_all = info['corr']
    rid = info['rid']
    acc = {info['names'][k].split('@')[0]: dict(id=float(cs_all[k][rid].mean()), ood=float(cs_all[k][~rid].mean()),
                                               none=float(np.mean([a is None for a in info['ans'][k]]))) for k in range(len(info['names']))}
    out = dict(n_id=int(rid.sum()), n_ood=int((~rid).sum()), method={k.split('@')[0]: v for k, v in info['method'].items()},
               min_each=info.get('min_each'), crowd=[nm.split('@')[0] for nm in names],
               valid=bool(info['valid']), acc=acc)
    if not info['valid']:
        return out
    fx = next((i for i, nm in enumerate(names) if nm.split('@')[0] == FIXED_NEW), None)
    hidx = [i for i, nm in enumerate(names) if nm.split('@')[0] in hnames_t3]
    idi, ood = info['idi'], info['ood']
    pt = env_point(st, idi, ood, fx, hidx)
    gb = np.random.default_rng(seed_boot)
    draws = [(gb.choice(idi, len(idi)), gb.choice(ood, len(ood))) for _ in range(B)]
    bt = np.array(P._pmap(_rep_env, draws, dict(st=st, keys=list(RULE_KEYS), fx=fx, hidx=hidx), workers), float)
    out['point'] = {k: float(pt[k]) for k in pt if isinstance(pt[k], (int, float))}
    with warnings.catch_warnings():                    # статистика, не определённая в среде (Т3 без голов списка), — NaN без предупреждений
        warnings.simplefilter('ignore', RuntimeWarning)
        out['sd'] = {k: float(np.nanstd(bt[:, j], ddof=1)) for j, k in enumerate(RULE_KEYS)}
        out['boot_shift'] = {k: float(np.nanmean(bt[:, j]) - pt[k]) for j, k in enumerate(RULE_KEYS)}
    out['fixed_in_crowd'], out['t3_heads'] = fx is not None, [names[i].split('@')[0] for i in hidx]
    if keep_boot:
        out['_boot'] = {k: bt[:, j] for j, k in enumerate(RULE_KEYS)}
    cs_k = st['corr'][info['keep']]                      # C − T вне диапазона у каждой головы толпы (калибровка на ID, описательно)
    cal_o = P.calibrate(st['logp'][info['keep']], cs_k, idi, ood)
    out['ct_ood_by_head'] = {names[k].split('@')[0]: float(cal_o[k].mean() - cs_k[k, ood].mean()) for k in range(len(names))}
    # Т4: голоса толпы (головы keep) вне диапазона
    keep = info['keep']
    ans_k = [info['ans'][k] for k in keep]
    sums = [p['sum'] for p in env['problems']]
    D = dmat(ans_k, sums, list(ood))
    strata = np.array([carries(env['problems'][j]['a'], env['problems'][j]['b']) for j in ood])
    gn = np.random.default_rng(seed_null)
    F, F0, dF = f_stats(D, gn, K_point)
    _, F0s, dFs = f_stats(D, gn, K_point, strata)
    gbn = np.random.default_rng(seed_null_boot)
    bF, bFs = [], []
    for _ in range(B):
        rows = gbn.integers(0, len(ood), len(ood))
        Db, sb = D[rows], strata[rows]
        bF.append(f_stats(Db, gbn, K_boot)[2])
        bFs.append(f_stats(Db, gbn, K_boot, sb)[2])
    out['T4'] = dict(F=F, F0=F0, point=dF, sd=float(np.std(bF, ddof=1)), F0_strata=F0s, point_strata=dFs, sd_strata=float(np.std(bFs, ddof=1)),
                     strata_counts={int(s): int((strata == s).sum()) for s in np.unique(strata)})
    if keep_boot:
        out['_boot_T4'] = (np.array(bF), np.array(bFs))
    out['oracle_ood'] = float(st['corr'][keep][:, ood].any(0).mean())
    pairs = list(itertools.combinations(range(len(names)), 2))
    vend = [V.vendor(CROWD[nm.split('@')[0]].split('@')[0]) for nm in names]
    u = uncond(D, [nm.split('@')[0] for nm in names], pairs)
    for row, (i, j) in zip(u, pairs):
        row['same_vendor'] = vend[i] == vend[j]
    out['uncond_ood'] = u
    return out


# ───────────── правила и мощность
def verdict2(kind, iv, band=P.BAND):
    """sign — «подтверждено», если верх < 0; pos — если низ > 0; over (Т1) — если низ > +band, «опровергнуто» — интервал в полосе;
    unit (Т3) — «подтверждено», если интервал внутри (0; 1), «опровергнуто», если целиком ≥ 1 или ≤ 0."""
    lo, hi = iv
    if not (np.isfinite(lo) and np.isfinite(hi)):
        return 'не решено'
    if kind == 'sign':
        return 'подтверждено' if hi < 0 else ('опровергнуто' if lo > 0 else 'не решено')
    if kind == 'pos':
        return 'подтверждено' if lo > 0 else ('опровергнуто' if hi < 0 else 'не решено')
    if kind == 'over':
        return 'подтверждено' if lo > band else ('опровергнуто' if (lo >= -band and hi <= band) else 'не решено')
    if kind == 'unit':
        return 'подтверждено' if (lo > 0 and hi < 1) else ('опровергнуто' if (lo >= 1 or hi <= 0) else 'не решено')
    raise ValueError(kind)


RULES2 = {'T1': 'over', 'T2': 'sign', 'T3': 'unit', 'T4': 'pos'}


def power_mc(kind, mu, tau, s, m=5, z=P.Z, n=200_000, seed=SEED_POWER, guard=True):
    """Мощность правила для среднего по m средам: точка среды ~ N(mu, tau² + s²), полуширина M4 = z·s/√m (как ocdiv.power_rule),
    Монте-Карло; у знаковых правил (sign, pos) — с предохранителем «без одной среды». Возвращает (подтверждено, опровергнуто)."""
    g = np.random.default_rng(seed)
    x = g.normal(mu, np.sqrt(tau ** 2 + s ** 2), size=(n, m))
    mean = x.mean(1)
    h = z * s / np.sqrt(m)
    lo, hi = mean - h, mean + h
    holds = np.ones(n, bool)
    if guard and kind in ('sign', 'pos'):
        loo = (x.sum(1, keepdims=True) - x) / (m - 1)
        holds = np.all(loo * mean[:, None] > 0, axis=1)
    band = P.BAND
    if kind == 'sign':
        c, r = (hi < 0) & holds, (lo > 0) & holds
    elif kind == 'pos':
        c, r = (lo > 0) & holds, (hi < 0) & holds
    elif kind == 'over':
        c, r = lo > band, (lo >= -band) & (hi <= band)
    else:
        c, r = (lo > 0) & (hi < 1), (lo >= 1) | (hi <= 0)
    return float(c.mean()), float(r.mean())


def power_from_envs(points, sds, scale, kind, m=5):
    """μ и τ — по средам пилота (τ обрезана по нулю), s — ст. откл. среды пилота, пересчитанное на тест (scale = √(n_пилот / n_тест)).
    Даются мощность при оценке τ и при τ = s (совет 64, п. 6)."""
    x, sp = np.asarray(points, float), np.asarray(sds, float)
    ok = np.isfinite(x) & np.isfinite(sp)
    x, sp = x[ok], sp[ok]
    if len(x) < 2:
        return None
    s_test = float(np.sqrt(np.mean(sp ** 2)) * scale)
    tau = float(np.sqrt(max(0.0, x.var(ddof=1) - np.mean(sp ** 2))))
    c, r = power_mc(kind, float(x.mean()), tau, s_test, m)
    cs, rs = power_mc(kind, float(x.mean()), s_test, s_test, m)
    return dict(kind=kind, n_envs=int(len(x)), mu=float(x.mean()), tau=tau, s_pilot_rms=float(np.sqrt(np.mean(sp ** 2))), s_test=s_test,
                power_confirm=c, power_refute=r, power_confirm_tau_s=cs, power_refute_tau_s=rs)


# ───────────── пилот
def test_id_count(fam, X, test_phase='test'):
    """Число задач ID в среде теста — по строению среды (ответы не читаются)."""
    ph = D2.PHASES[test_phase]
    e = D2.env_of(fam, X, ph['p'], ph['n'], ph['start'], ph['prompt'])
    return sum(p['range'] == 'ID' for p in e['problems'])


def family_summary(fam, envs_res, head_secs):
    names = list(CROWD)
    drop = {}
    for nm in names:
        v = [envs_res[e]['acc'][nm]['id'] - envs_res[e]['acc'][nm]['ood'] for e in envs_res if nm in envs_res[e]['acc']]
        drop[nm] = float(np.mean(v)) if v else float('nan')
    pass_envs = {nm: int(sum(bool(envs_res[e]['method'].get(nm, {}).get('ok')) for e in envs_res)) for nm in names}
    none_max = {nm: float(max(envs_res[e]['acc'][nm]['none'] for e in envs_res if nm in envs_res[e]['acc'])) for nm in names}
    drop_mean = float(np.nanmean(list(drop.values())))
    heads_drop = [nm for nm in names if np.isfinite(drop[nm]) and drop[nm] >= DROP_MIN]
    heads_pass = [nm for nm in names if pass_envs[nm] >= PASS_ENVS_MIN]
    max_sec = float(max(head_secs.values())) if head_secs else float('nan')
    ok = bool(drop_mean >= DROP_MIN and len(heads_drop) >= DROP_HEADS_MIN and len(heads_pass) >= PASS_HEADS_MIN and max_sec <= MAX_SEC)
    return dict(family=fam, drop_by_head=drop, drop_mean=drop_mean, heads_drop_ge=heads_drop, pass_envs=pass_envs, heads_pass_4of5=heads_pass,
                none_max=none_max, sec_per_task=head_secs, max_sec_per_task=max_sec, qualifies=ok,
                rule=dict(drop_min=DROP_MIN, drop_heads_min=DROP_HEADS_MIN, pass_heads_min=PASS_HEADS_MIN, pass_envs_min=PASS_ENVS_MIN, max_sec=MAX_SEC))


def pilot(dst, mdirs, B=200, workers=1, test_phase='test'):
    t0 = time.time()
    res = dict(phase='pilot', test_phase=test_phase, B=B, families={}, envs={}, head_errors={})
    for fam, mdir in mdirs.items():
        d, envs = S.load_new(mdir)
        res['head_errors'][fam] = d.get('head_errors', [])
        hs = {h['model']: h for h in d['heads']}
        secs = {nm: float(sum(v for v in h['seconds_env'].values() if v) / max(1, h['n_tasks'])) for nm, h in hs.items()}
        # предварительный проход без бутстрепа: точность голов → список голов Т3 (разрыв ≥ 0,10 в среднем по средам семейства)
        pre = {}
        for name, env in envs.items():
            meta = env['meta']
            st, info = V.prepare_scaled(env, SEED_CV2 + off_of(meta), test_id_count(fam, meta['X'], test_phase))
            rid = info['rid']
            pre[name] = dict(acc={info['names'][k].split('@')[0]: dict(id=float(info['corr'][k][rid].mean()), ood=float(info['corr'][k][~rid].mean()),
                                                                      none=float(np.mean([a is None for a in info['ans'][k]])))
                                  for k in range(len(info['names']))},
                             method={k.split('@')[0]: v for k, v in info['method'].items()})
        summ = family_summary(fam, pre, secs)
        t3h = summ['heads_drop_ge']
        out_envs = {}
        for name, env in envs.items():
            meta = env['meta']
            o = off_of(meta)
            r = env_analysis(env, SEED_CV2 + o, SEED_BOOT_PILOT + o, SEED_NULL + o, SEED_NULL_BOOT + o, test_id_count(fam, meta['X'], test_phase), t3h, B,
                             workers, K_point=200, K_boot=5)
            r['meta'] = {k: meta.get(k) for k in ('family', 'X', 'p', 'bound', 'max_new', 'prompt')}
            r['n_test_ood'] = D2.N_TEST - test_id_count(fam, meta['X'], test_phase)
            out_envs[name] = r
            print(f"{name}: годна {r['valid']}, толпа {len(r['crowd'])}, {round(time.time() - t0)} с", flush=True)
        res['envs'].update(out_envs)
        # мощность правил на тесте (5 сред); s пересчитывается по числу задач вне диапазона (Т1, Т2, Т4) или всех задач (Т3)
        valid = [n for n in out_envs if out_envs[n]['valid']]
        pw = {}
        if len(valid) >= 2:
            n_ood_p = np.mean([out_envs[n]['n_ood'] for n in valid])
            n_ood_t = np.mean([out_envs[n]['n_test_ood'] for n in valid])
            n_all_p = np.mean([out_envs[n]['n_id'] + out_envs[n]['n_ood'] for n in valid])
            sc_ood, sc_all = float(np.sqrt(n_ood_p / n_ood_t)), float(np.sqrt(n_all_p / D2.N_TEST))
            for k, kind in RULES2.items():
                if k == 'T4':
                    pts, sds = [out_envs[n]['T4']['point'] for n in valid], [out_envs[n]['T4']['sd'] for n in valid]
                    pts_s, sds_s = [out_envs[n]['T4']['point_strata'] for n in valid], [out_envs[n]['T4']['sd_strata'] for n in valid]
                    pw['T4 (страты по числу переносов)'] = power_from_envs(pts_s, sds_s, sc_ood, kind)
                else:
                    pts, sds = [out_envs[n]['point'][k] for n in valid], [out_envs[n]['sd'][k] for n in valid]
                pw[k] = power_from_envs(pts, sds, sc_all if k == 'T3' else sc_ood, kind)
            for k, kind in (('D3', 'over'), ('AGREE − CONF', 'sign'), ('wc CONF', 'sign')):
                pw[k + ' (описательно)'] = power_from_envs([out_envs[n]['point'][k] for n in valid], [out_envs[n]['sd'][k] for n in valid], sc_ood, kind)
            summ['scale'] = dict(ood=sc_ood, all=sc_all, n_ood_pilot=float(n_ood_p), n_ood_test=float(n_ood_t))
        summ['power'] = pw
        summ['n_valid'] = len(valid)
        res['families'][fam] = summ
    for f, s_ in res['families'].items():           # HYPOTHESIS-2: семейство годно, только если годны не меньше 4 сред из 5
        s_['qualifies_envs'] = bool(s_['n_valid'] >= PASS_ENVS_MIN)
        s_['qualifies'] = bool(s_['qualifies'] and s_['qualifies_envs'])
    good = [f for f, s_ in res['families'].items() if s_['qualifies']]
    res['chosen'] = max(good, key=lambda f: res['families'][f]['drop_mean']) if good else None
    res['verdict'] = (f"выбрано семейство {res['chosen']}" if res['chosen'] else 'годного семейства нет: теста нет, перепроектирование (HYPOTHESIS)')
    res['seconds'] = round(time.time() - t0, 1)
    json.dump(res, open(dst, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print(res['verdict'])
    for f, s_ in res['families'].items():
        print(f, 'годно', s_['qualifies'], '| средний разрыв', round(s_['drop_mean'], 4), '| голов с разрывом ≥ 0,10:', len(s_['heads_drop_ge']),
              '| голов с проверкой ≥ 4 из 5:', len(s_['heads_pass_4of5']), '| с на задачу (макс.)', round(s_['max_sec_per_task'], 3))
    return res


# ───────────── тест (константы — в PREREG по пилоту, до данных теста)
FAMILY_TEST = None        # 'thousands' | 'length' — по правилу выбора семейства на пилоте
TEST_PHASE = 'test2'      # HYPOTHESIS-2: тест — подсказка только из ID (p = 3)
T3_HEADS = None           # головы Т3: разрыв ID − OOD на пилоте выбранного семейства не меньше 0,10
T2_DESCRIPTIVE = None     # True, если мощность Т2 по пилоту меньше 0,2 (HYPOTHESIS)
T4_STRATA = None          # False — нуль без страт (HYPOTHESIS); True — со стратами по числу переносов
SEED_BOOT_TEST, SEED_NULL_TEST, SEED_NULL_BOOT_TEST = 8_350_000, 8_420_000, 8_470_000
Z_SENS = 1.5              # как в OCDIV-01: вердикт «чувствителен к уровню», если z* < 2,807 × 1,5


def z_star2(kind, delta, sd, band=P.BAND):
    """z, при котором меняется вердикт (совет 66, п. 6): sign, pos — |Δ|/s; over — расстояние точки до края полосы; unit — до ближайшей
    из границ 0 и 1."""
    if not (np.isfinite(delta) and np.isfinite(sd) and sd > 0):
        return float('nan')
    if kind in ('sign', 'pos'):
        return float(abs(delta) / sd)
    if kind == 'over':
        return float((delta - band) / sd) if delta > band else float((band - abs(delta)) / sd)
    return float(min(abs(delta), abs(1 - delta)) / sd)


def repeat_check(main_glob, rep_glob):
    """Совет 67 («можно»): одно задание теста повторено под другим именем — совпали ли ответы и logp (детерминизм на процессорах)."""
    out = []
    mains = {}
    for f in glob.glob(main_glob):
        h = json.load(open(f, encoding='utf-8'))
        for nm, c in (h.get('cols') or {}).items():
            mains[(h['model'], nm)] = (c, h.get('cpu_model'), os.path.relpath(f, ROOT))
    for f in sorted(glob.glob(rep_glob)):
        h = json.load(open(f, encoding='utf-8'))
        for nm, c in (h.get('cols') or {}).items():
            m = mains.get((h['model'], nm))
            if not m:
                continue
            a1, a2 = m[0]['answer'], c['answer']
            l1, l2 = m[0]['logp'], c['logp']
            dl = [abs(x - y) for x, y in zip(l1, l2) if x is not None and y is not None]
            out.append(dict(model=h['model'], env=nm, n=len(a1), answers_equal=float(np.mean([x == y for x, y in zip(a1, a2)])),
                            max_abs_dlogp=(float(max(dl)) if dl else None), cpu_main=m[1], cpu_rep=h.get('cpu_model'), file_main=m[2],
                            file_rep=os.path.relpath(f, ROOT)))
    return out


def test(dst, mdir, B=10000, workers=1):
    assert FAMILY_TEST in D2.FAMILIES and T3_HEADS is not None and T2_DESCRIPTIVE is not None and T4_STRATA is not None, 'константы теста не заданы (PREREG)'
    t00 = time.time()
    d, envs = S.load_new(mdir)
    hm = {h['model']: h for h in d['heads']}
    names_c, dropped = V.effective_crowd(hm)            # голова выбывает при чужой ревизии или версиях (как в OCDIV-01)
    res = dict(level=P.LEVEL, z=P.Z, band=P.BAND, B=B, family=FAMILY_TEST, crowd=CROWD, fixed_new=FIXED_NEW, t3_heads=list(T3_HEADS),
               t2_descriptive=T2_DESCRIPTIVE, t4_strata=T4_STRATA, head_errors=d.get('head_errors', []), keys_checked=d.get('keys_checked'),
               crowd_effective=names_c, crowd_dropped=dropped, cpu_models={nm: hm[nm].get('cpu_models') for nm in names_c}, envs={})
    boots, valid = {}, []
    for name in sorted(envs):
        env = envs[name]
        meta = env['meta']
        assert meta['family'] == FAMILY_TEST and int(meta['p']) == D2.PHASES[TEST_PHASE]['p'], f'среда {name} не из теста семейства {FAMILY_TEST}'
        env_c = dict(env, heads=[h for h in env['heads'] if h['model'] in names_c])
        o = off_of(meta)
        n_id = sum(p['range'] == 'ID' for p in env['problems'])
        r = env_analysis(env_c, SEED_CV2 + o, SEED_BOOT_TEST + o, SEED_NULL_TEST + o, SEED_NULL_BOOT_TEST + o, n_id, set(T3_HEADS), B, workers,
                         K_point=K_NULL_POINT, K_boot=K_NULL_BOOT, keep_boot=True)
        r['meta'] = {k: meta[k] for k in ('family', 'X', 'p', 'bound', 'max_new')}
        r['seeds'] = dict(cv=SEED_CV2 + o, boot=SEED_BOOT_TEST + o, null=SEED_NULL_TEST + o, null_boot=SEED_NULL_BOOT_TEST + o)
        if r['valid']:
            valid.append(name)
            b4 = r.pop('_boot_T4')
            boots[name] = {**r.pop('_boot'), 'T4': b4[1] if T4_STRATA else b4[0], 'T4 (другой нуль)': b4[0] if T4_STRATA else b4[1]}
            r['T4']['primary'] = 'strata' if T4_STRATA else 'plain'
        res['envs'][name] = r
        print(f"{name}: ID {r['n_id']}, OOD {r['n_ood']}, толпа {len(r['crowd'])} из {len(env_c['heads'])}, годна {r['valid']}, {round(time.time() - t00)} с", flush=True)
    m, n_env = len(valid), len(envs)
    method_ok = bool(m >= int(np.ceil(P.MIN_VALID_FRAC * n_env)) and n_env == 5)
    res['method'] = dict(ok=method_ok, n_envs=n_env, n_valid=m, valid=valid, fixed_in_all_valid=bool(all(res['envs'][n].get('fixed_in_crowd') for n in valid)),
                         crowd_effective=len(names_c))
    group = {n: envs[n]['meta']['X'] for n in valid}

    def point_of(n, key):
        e = res['envs'][n]
        if key == 'T4':
            return e['T4']['point_strata'] if T4_STRATA else e['T4']['point']
        if key == 'T4 (другой нуль)':
            return e['T4']['point'] if T4_STRATA else e['T4']['point_strata']
        return e['point'][key]

    def mean_entry(key, level, kind):
        use = [n for n in valid if np.isfinite(point_of(n, key))]
        if not use:
            return dict(delta=float('nan'), ci=[float('nan'), float('nan')], n_envs=0, kind=kind)
        pt = float(np.mean([point_of(n, key) for n in use]))
        with warnings.catch_warnings():
            warnings.simplefilter('ignore', RuntimeWarning)
            bt = np.nanmean(np.vstack([boots[n][key] for n in use]), 0)
        bt = bt[np.isfinite(bt)]
        iv, sd = P.m4(pt, bt, level)
        zp = pt / sd if sd > 0 else float('nan')
        return dict(delta=pt, ci=iv, boot_sd=sd, boot_shift=float(np.mean(bt) - pt), level=level, n_envs=len(use), n_boot_finite=int(len(bt)),
                    by_env={n: float(point_of(n, key)) for n in use}, z_point=zp, z_star=z_star2(kind, pt, sd), kind=kind)
    if m == 0:
        res['verdicts'] = {k: P.U for k in RULES2}
        json.dump(res, open(dst, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
        return res
    for k, kind in RULES2.items():
        e = mean_entry(k, P.LEVEL, kind)
        v = verdict2(kind, e['ci'])
        if kind in ('sign', 'pos') and e['n_envs'] >= 2:         # предохранитель «без одной среды» — как в OCPOST-01
            v, e['leave_one_range_out'] = P.A.range_guard(v, e['by_env'], group)
        e['verdict_rule'] = v
        e['sensitive_to_level'] = bool(v in ('подтверждено', 'опровергнуто') and np.isfinite(e['z_star']) and e['z_star'] < P.Z * Z_SENS)
        e['verdict'] = P.U if not method_ok else v
        res[k] = e
    if T2_DESCRIPTIVE and method_ok:
        res['T2']['verdict_rule_descr'] = res['T2']['verdict']
        res['T2']['verdict'] = 'описательно (мощность по пилоту < 0,2; PREREG)'
    for k, kind in (('D3', 'over'), ('AGREE − CONF', 'sign'), ('wc CONF', 'sign'), ('wc POST', 'over'), ('wc FIXED', 'over'), ('T4 (другой нуль)', 'pos')):
        res[f'descr_{k}'] = mean_entry(k, P.DESCR_LEVEL, kind)
    keys_parts = [k for k in res['envs'][valid[0]]['point'] if k.split(' ')[0] in ('T', 'C', 'ign', 'dec', 'ioi', 'brier')]
    res['parts_mean'] = {k: float(np.nanmean([res['envs'][n]['point'].get(k, np.nan) for n in valid])) for k in keys_parts}
    res['oracle_ood_mean'] = float(np.mean([res['envs'][n]['oracle_ood'] for n in valid]))
    for side in (True, False):
        us = [x for n in valid for x in res['envs'][n]['uncond_ood'] if x['same_vendor'] == side]
        res['uncond_' + ('same' if side else 'cross')] = {k: (float(np.mean([x[k] for x in us])) if us else None) for k in ('u', 'u перенос', 'u прочее', 'both_wrong')}
    res['ct_ood_by_head_mean'] = {nm: float(np.mean([res['envs'][n]['ct_ood_by_head'][nm] for n in valid if nm in res['envs'][n]['ct_ood_by_head']]))
                                  for nm in names_c}
    res['acc_by_head_mean'] = {nm: {r_: float(np.mean([res['envs'][n]['acc'][nm][r_] for n in valid if nm in res['envs'][n]['acc']])) for r_ in ('id', 'ood')}
                               for nm in names_c}
    res['repeat_check'] = repeat_check(os.path.join(ROOT, 'gha_out/ocdiv2_test_*/answers_*.json'), os.path.join(ROOT, 'gha_out/ocdiv2_rep_*/answers_*.json'))
    res['verdicts'] = {k: res[k]['verdict'] for k in RULES2}
    res['verdict'] = '; '.join(f'{k}: {v}' for k, v in res['verdicts'].items())
    res['seconds'] = round(time.time() - t00, 1)
    json.dump(res, open(dst, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print('вердикт:', res['verdict'])
    for k in RULES2:
        e = res[k]
        print(f"{k}: Δ {e['delta']:+.4f} M4 [{e['ci'][0]:+.4f}; {e['ci'][1]:+.4f}] ст. откл. {e.get('boot_sd', float('nan')):.4f} | z* {e.get('z_star', float('nan')):.1f}"
              + (' (чувствителен к уровню)' if e.get('sensitive_to_level') else ''))
    print('годных сред', m, 'из', n_env, '| толпа', len(names_c), '| выбыли', dropped, '| время', res['seconds'], 'с')
    return res


def main():
    a = sys.argv[1:]
    if a[0] == 'merge':
        merge(a[1], a[2], a[3], a[4:])
    elif a[0] == 'pilot':
        B = int(a[a.index('--boot') + 1]) if '--boot' in a else 200
        W = int(a[a.index('--workers') + 1]) if '--workers' in a else 1
        pilot(a[1], {'thousands': a[2], 'length': a[3]}, B, W, a[a.index('--test-phase') + 1] if '--test-phase' in a else 'test')
    elif a[0] == 'test':
        B = int(a[a.index('--boot') + 1]) if '--boot' in a else 10000
        W = int(a[a.index('--workers') + 1]) if '--workers' in a else 1
        test(a[1], a[2], B, W)


if __name__ == '__main__':
    main()
