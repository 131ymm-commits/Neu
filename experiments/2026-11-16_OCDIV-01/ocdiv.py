#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""OCDIV-01 «ОЦЕНЩИК-РАЗНЫЕ-ГОЛОВЫ»: сборка ответов новых голов и разбор пилота (тест — после PREREG).
  python3 ocdiv.py merge  OUT_DIR SOURCE N PICK JOB_DIR [JOB_DIR ...]   — answers.json вида ocshift_extract (среды источника + новые головы)
  python3 ocdiv.py pilot  RESULT.json NEW_DIR [--boot 200] [--no-power] — пилот: годность, скорость, совпадение ошибок, оценщики, мощность
  python3 ocdiv.py test   RESULT.json NEW_DIR [--boot 10000] [--workers W] — тест: D1–D5 и N на пяти средах OCPOST-01 (константы — PREREG)
SOURCE — test (пять сред OCPOST-01) или pilot (десять сред OCSHIFT-01); N — размер выборки задач среды (0 — все);
PICK — first (первые N: пилот 1, выборка смещена — ERRORS № 175) или random (N случайных, зерно ocdiv_extract.SEED_PICK + 10·X + p).
Голова может прийти несколькими файлами (задания по частям сред): сборка сводит их и сверяет ревизию и номера задач.
Код счёта — зарегистрированный код прежних опытов: проверка метода и массивы — analyze_ocshift.prepare; оценщики — ocpost.post_stats
и analyze_ocshift.core (AGREE). Совпадение ошибок q(i, j) — HYPOTHESIS.md.
После ERRORS № 175 (пилот 2):
  - проверка метода в пилоте — в масштабе теста: порог 20 пересчитан на число задач ID среды пилота (prepare_scaled);
  - ст. откл. пилота пересчитывается на тест по числу задач своего диапазона (ID — D2, D4, N; OOD — D3, D5; все задачи — D1);
  - D1 ещё и с поправкой на точность: МНК по парам обеих толп q = α + β·acc_pair + δ·[пара разнородной толпы], статистика δ."""
import glob
import itertools
import json
import os
import sys
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
EXP = os.path.dirname(HERE)
ROOT = os.path.dirname(EXP)
sys.path.insert(0, os.path.join(EXP, '2026-11-15_OCPOST-01'))
sys.path.insert(0, HERE)
import ocpost as P  # noqa: E402
import ocdiv_extract as DX  # noqa: E402   выборка задач — одна функция pick_idx; torch здесь не нужен
S = P.S                                                     # analyze_ocshift

SRC = DX.SRC
VENDOR = {'Qwen': 'Alibaba', 'HuggingFaceTB': 'Hugging Face', 'allenai': 'AI2', 'ibm-granite': 'IBM', 'tiiuae': 'TII',
          'TinyLlama': 'TinyLlama', 'LiquidAI': 'Liquid AI', 'bigscience': 'BigScience', 'EleutherAI': 'EleutherAI'}
PY_DISTINCT = ('pythia-1.4b@main', 'pythia-1.4b-deduped@main', 'pythia-2.8b@main', 'pythia-2.8b-deduped@main',
               'pythia-6.9b@main', 'pythia-6.9b-deduped@main')                     # Q-py: шесть разных моделей, без чекпойнтов
SEED_CV_P, SEED_BOOT_P = 7_620_000, 7_950_000               # части — правило OCSHIFT-01 (7 620 000 + 10·X + p); бутстреп пилота — новое зерно
MAX_SEC_PER_TASK = 1.5                                      # HYPOTHESIS: время на раннере
RULES_D = {'D2': (('wc CONF', None), 'sign', 'ID'), 'D3': (('C FIXED', 'T FIXED'), 'equiv_out', 'OOD'), 'D4': (('wc POST', None), 'equiv', 'ID'),
           'D5': (('ioi AGREE', 'ioi CONF (core)'), 'sign', 'OOD'), 'N': (('wc FIXED', None), 'equiv', 'ID')}


def vendor(repo):
    return VENDOR.get(repo.split('/')[0], repo.split('/')[0])


def src_envs(source, n, pick):
    """Среды источника (без блока сверки) с выборкой задач pick_idx; номера задач — в поле idx."""
    src = json.load(open(SRC[source], encoding='utf-8'))
    out = []
    for e in src['envs']:
        if e.get('kind') == 'check':
            continue
        idx = DX.pick_idx(e, n, pick)
        out.append((e, idx))
    return src, out


def range_counts(source, n=0, pick='first'):
    """Среднее по средам число задач ID и OOD (строение сред; ответы и правда не читаются)."""
    _, envs = src_envs(source, n, pick)
    out = {r: float(np.mean([sum(e['problems'][i]['range'] == r for i in idx) for e, idx in envs])) for r in ('ID', 'OOD')}
    out['all'] = out['ID'] + out['OOD']
    return out


# ───────────── сборка
def merge(out_dir, source, n, job_dirs, pick='first'):
    src, pairs = src_envs(source, n, pick)
    envs = []
    for e, idx in pairs:
        e = dict(e)
        e['problems'] = [e['problems'][i] for i in idx]
        e['idx'] = idx
        envs.append(e)
    per, errors = {}, []
    for jd in job_dirs:
        for f in sorted(glob.glob(os.path.join(jd, 'answers_*.json'))):
            h = json.load(open(f, encoding='utf-8'))
            rel = os.path.relpath(f, ROOT)
            if 'error' in h or 'cols' not in h:
                errors.append(dict(model=h.get('model'), error=h.get('error', 'нет cols'), file=rel))
                continue
            rev = h.get('commit') or h['revision']
            r = per.setdefault(h['repo'], dict(commit=rev, cols={}, seconds_env={}, files=[]))
            if rev != r['commit']:
                errors.append(dict(model=h['repo'], error=f'ревизия {rev} не равна {r["commit"]} в другом файле той же головы', file=rel))
                continue
            h_idx = {x['name']: x.get('idx') for x in h.get('envs', [])}
            for e in envs:
                if e['name'] not in h['cols']:
                    continue
                hi = h_idx.get(e['name'])
                ok = (hi is None and pick == 'first') or (hi is not None and hi[:len(e['idx'])] == e['idx'] and (pick == 'first' or len(hi) == len(e['idx'])))
                if not ok:
                    errors.append(dict(model=h['repo'], error=f"номера задач среды {e['name']} не совпали с выборкой {pick}", file=rel))
                    continue
                if e['name'] in r['cols']:
                    errors.append(dict(model=h['repo'], error=f"среда {e['name']} пришла дважды", file=rel))
                    continue
                r['cols'][e['name']] = {k: (v[:len(e['problems'])] if isinstance(v, list) else v) for k, v in h['cols'][e['name']].items()}
                r['seconds_env'][e['name']] = (h.get('seconds_env') or {}).get(e['name'])
            r['files'].append(rel)
    heads = []
    for repo, r in per.items():
        if len(r['cols']) != len(envs):
            errors.append(dict(model=repo, error=f"сред {len(r['cols'])} из {len(envs)}", file=', '.join(r['files'])))
            continue
        heads.append(dict(model=repo.split('/')[-1], repo=repo, revision=r['commit'], vendor=vendor(repo), seconds_env=r['seconds_env'],
                          n_tasks=sum(len(e['problems']) for e in envs), files=r['files'], cols={e['name']: r['cols'][e['name']] for e in envs}))
    os.makedirs(out_dir, exist_ok=True)
    d = dict(mode=source, source_file=os.path.relpath(SRC[source], ROOT), n=n, pick=pick, envs=envs, heads=heads, head_errors=errors,
             info=dict(merged_by='ocdiv.py merge', when=time.strftime('%Y-%m-%d %H:%M UTC', time.gmtime())))
    for e in d['envs']:
        e['kind'] = 'test'                                  # S.load_new берёт все среды; метка — для ocpost.load_envs
    json.dump(d, open(os.path.join(out_dir, 'answers.json'), 'w', encoding='utf-8'), ensure_ascii=False)
    print(f'собрано: голов {len(heads)}, ошибок {len(errors)}, сред {len(envs)}, выборка {pick} {n} → {out_dir}/answers.json')
    for x in errors:
        print('  ошибка:', x)
    return d


def pythia_envs(source, n, pick='first'):
    """Ответы девяти Pythia на тех же задачах (та же выборка pick_idx) — из сырого вывода источника."""
    src, pairs = src_envs(source, n, pick)
    out = {}
    for e, idx in pairs:
        heads = [dict(model=h['model'], revision=h['revision'], answer=[h['cols'][e['name']]['answer'][i] for i in idx],
                      correct=[h['cols'][e['name']]['correct'][i] for i in idx]) for h in src['heads'] if 'cols' in h]
        out[e['name']] = dict(problems=[e['problems'][i] for i in idx], heads=heads)
    return out


def prepare_scaled(env, seed, n_id_test):
    """analyze_ocshift.prepare с порогом проверки метода в масштабе теста: 20 · (задач ID в среде) / (задач ID в среде теста), вверх, не больше 20."""
    n_id = sum(p['range'] == 'ID' for p in env['problems'])
    old = S.MIN_EACH
    thr = min(old, max(1, int(np.ceil(old * n_id / n_id_test))))
    S.MIN_EACH = thr
    try:
        st, info = S.prepare(env, seed)
    finally:
        S.MIN_EACH = old
    info['min_each'] = thr
    return st, info


# ───────────── совпадение ошибок
def encode(ans_map, s):
    """Ответы и правда → целые коды (равенство сохраняется, длинные числа не переполняют int64); нет числа — код −1 и маска False."""
    code = {}

    def c(x):
        return code.setdefault(x, len(code))
    s_ = np.array([c(t) for t in s], np.int64)
    out = {nm: (np.array([-1 if x is None else c(x) for x in a], np.int64), np.array([x is not None for x in a], bool)) for nm, a in ans_map.items()}
    return out, s_


def pair_stats(enc, s_, labels, pairs, idx=None):
    """По парам (i, j): q — среди задач, где у обеих ответ — число и обе ошиблись, доля равных ответов; m — число таких задач;
    acc — доля верных ответов головы на тех же задачах (нет числа — неверно). idx — задачи (с повторами в бутстрепе), None — все."""
    s = s_ if idx is None else s_[idx]
    arr = {nm: ((enc[nm][0], enc[nm][1]) if idx is None else (enc[nm][0][idx], enc[nm][1][idx])) for nm in labels}
    acc = {nm: float(np.mean(arr[nm][1] & (arr[nm][0] == s))) for nm in labels}
    out = []
    for i, j in pairs:
        (ai, vi), (aj, vj) = arr[labels[i]], arr[labels[j]]
        both = vi & vj & (ai != s) & (aj != s)
        m = int(both.sum())
        q = float((ai[both] == aj[both]).mean()) if m else float('nan')
        out.append(dict(i=labels[i], j=labels[j], q=q, m=m, acc_i=acc[labels[i]], acc_j=acc[labels[j]], acc_pair=(acc[labels[i]] + acc[labels[j]]) / 2))
    return out


def q_of(ps):
    """Q толпы — среднее q по парам с хотя бы одной общей ошибкой; второе число — сумма общих ошибок."""
    v = [r['q'] for r in ps if r['m'] >= 1 and np.isfinite(r['q'])]
    return (float(np.mean(v)) if v else float('nan')), int(sum(r['m'] for r in ps))


def adj_of(ps_new, ps_py):
    """D1 с поправкой на точность: МНК по парам обеих толп q = α + β·acc_pair + δ·[пара разнородной толпы]. Возвращает (δ, β, α)."""
    a = [(r['q'], r['acc_pair'], 1.0) for r in ps_new if r['m'] >= 1 and np.isfinite(r['q'])]
    b = [(r['q'], r['acc_pair'], 0.0) for r in ps_py if r['m'] >= 1 and np.isfinite(r['q'])]
    if len(a) < 2 or len(b) < 2:
        return float('nan'), float('nan'), float('nan')
    y, x, g = (np.array(v, float) for v in zip(*(a + b)))
    coef = np.linalg.lstsq(np.column_stack([np.ones_like(x), x, g]), y, rcond=None)[0]
    return float(coef[2]), float(coef[1]), float(coef[0])


def agree_conf(st, fit, cols):
    """ИОИ AGREE и CONF вне диапазона тем же путём, что analyze_ocshift.core (Q.scores, T.calibrate, select, meas), — только два
    оценщика, чтобы в бутстрепе не считать остальные шесть. Ключи CONF — с пометкой (core): post_stats считает CONF своим путём."""
    keep = st['keep']
    cs = st['corr'][keep]
    sc = S.Q.scores(st['ag'], st['corr'], st['logp'], keep, fit, st['fam'], ('AGREE', 'CONF'))
    y_c = cs[:, cols].astype(float)
    out = {}
    for e, nm in (('AGREE', 'AGREE'), ('CONF', 'CONF (core)')):
        t, c, _ = S.select(S.T.calibrate(sc[e], cs, fit, cols), y_c)
        for k, v in S.meas(t, c).items():
            out[f'{k} {nm}'] = v
        out[f'ign {nm}'] = 1 - out[f'T {nm}']
        out[f'dec {nm}'] = max(0.0, out[f'C {nm}'] - out[f'T {nm}'])
    return out


def stats_div(st, fit, cols, fx):
    """Все числа одной выборки: ocpost.post_stats (CONF, POST-CV, ONE-BEST, FIXED, POST-IN, SHIFT, wc) и agree_conf (AGREE, CONF (core))."""
    r = P.post_stats(st, fit, cols, fx)
    r.update(agree_conf(st, fit, cols))
    return r


def err_type(ans, a, b):
    """Тип ошибки сложения (описательно): потеря переноса в десятки/сотни, лишний перенос, прочее."""
    d = ans - (a + b)
    if d in (-10, -100, -110):
        return 'потеря переноса'
    if d in (10, 100, 110):
        return 'лишний перенос'
    return 'прочее'


P_PASS_FIXED = 0.95                                         # FIXED-нов: вероятность пройти проверку метода в среде теста — не ниже


def p_pass_env(acc, none_ok, n_id):
    """Вероятность пройти проверку метода в среде теста с n_id задачами ID, если точность головы на ID равна acc (биномиально):
    не меньше 20 верных и 20 неверных; доля ответов без числа — как в пилотной среде (none_ok)."""
    from scipy.stats import binom
    n = int(round(n_id))
    return float(none_ok) * float(binom.cdf(n - S.MIN_EACH, n, 1 - acc) - binom.cdf(S.MIN_EACH - 1, n, 1 - acc))


def p_at_least(ps, k):
    """P(не меньше k успехов) для независимых испытаний с вероятностями ps (распределение Пуассона — биномиальное, динамикой)."""
    dist = np.zeros(len(ps) + 1)
    dist[0] = 1.0
    for p in ps:
        dist[1:] = dist[1:] * (1 - p) + dist[:-1] * p
        dist[0] *= (1 - p)
    return float(dist[k:].sum())


def agg_power(points, sds, n_pilot, n_test, kind, m_test=5):
    """Мощность среднего по m_test средам теста: τ — разброс точек между средами пилота сверх шума, s — ст. откл. среды на тесте."""
    x, sp = np.asarray(points, float), np.asarray(sds, float)
    ok = np.isfinite(x) & np.isfinite(sp)
    x, sp = x[ok], sp[ok]
    if len(x) < 2:
        return None
    s_test = float(np.sqrt(np.mean(sp ** 2)) * np.sqrt(n_pilot / n_test))
    tau = float(np.sqrt(max(0.0, x.var(ddof=1) - np.mean(sp ** 2))))
    conf, ref_ = power_rule(kind, float(x.mean()), tau, s_test, m_test)
    return dict(kind=kind, n_envs=int(len(x)), mu=float(x.mean()), tau=tau, s_pilot_rms=float(np.sqrt(np.mean(sp ** 2))), n_pilot=n_pilot,
                n_test=n_test, s_test=s_test, power_confirm=conf, power_refute=ref_)


# ───────────── пилот
def pilot(dst, new_dir, B=200, power=True):
    t0 = time.time()
    d, envs_new = S.load_new(new_dir)
    pick = d.get('pick', 'first')
    py = pythia_envs(d['mode'], d.get('n', 0), pick)
    n_test = range_counts('test')                           # строение сред теста: число задач ID и OOD
    res = dict(source=d['mode'], n=d.get('n'), pick=pick, n_range_test=n_test, head_errors=d.get('head_errors', []), envs={}, heads={}, B=B)
    per_head = {h['model']: dict(repo=h['repo'], vendor=h['vendor'], revision=h['revision'], ok_envs=0, ok_envs_literal=0, n_envs=0,
                                 acc_id=[], acc_ood=[], none=[],
                                 sec_per_task=float(np.sum([v or 0 for v in (h.get('seconds_env') or {}).values()])) / max(h.get('n_tasks') or 1, 1))
                for h in d['heads']}
    for name, env in envs_new.items():
        meta = env['meta']
        off = 10 * meta['X'] + meta['p']
        st, info = prepare_scaled(env, SEED_CV_P + off, n_test['ID'])
        for k, nm in enumerate(info['names']):
            m = info['method'][nm]
            ph = per_head[env['heads'][k]['model']]
            ph['n_envs'] += 1
            ph['ok_envs'] += int(m['ok'])
            ph['ok_envs_literal'] += int(min(m['id_correct'], m['id_wrong']) >= S.MIN_EACH and m['none_frac'] <= S.MAX_NONE)
            ph['acc_id'].append(m['id_correct'] / max(m['id_correct'] + m['id_wrong'], 1))
            ph['acc_ood'].append(m['ood_correct'] / max(m['ood_correct'] + m['ood_wrong'], 1))
            ph['none'].append(m['none_frac'])
            ph.setdefault('p_pass_env', {})[name] = p_pass_env(ph['acc_id'][-1], m['none_frac'] <= S.MAX_NONE, n_test['ID'])
        res['envs'][name] = dict(n=len(env['problems']), n_id=int(len(info['idi'])), n_ood=int(len(info['ood'])), min_each=info['min_each'],
                                 method=info['method'])
    for nm, ph in per_head.items():
        for k in ('acc_id', 'acc_ood', 'none'):
            ph[k + '_mean'] = float(np.mean(ph[k])) if ph[k] else None
        ph['fast'] = bool(ph['sec_per_task'] <= MAX_SEC_PER_TASK)
        ph['valid'] = bool(ph['n_envs'] and ph['ok_envs'] >= P.MIN_VALID_FRAC * ph['n_envs'] and ph['fast'])
        ph['valid_literal'] = bool(ph['n_envs'] and ph['ok_envs_literal'] >= P.MIN_VALID_FRAC * ph['n_envs'] and ph['fast'])
    res['heads'] = per_head
    # отбор по HYPOTHESIS: не больше двух на производителя, не меньше четырёх производителей, до девяти — по точности на ID пилота
    cand = sorted([nm for nm, ph in per_head.items() if ph['valid']], key=lambda nm: -per_head[nm]['acc_id_mean'])
    chosen, per_v = [], {}
    for nm in cand:
        v = per_head[nm]['vendor']
        if per_v.get(v, 0) < 2 and len(chosen) < 9:
            chosen.append(nm)
            per_v[v] = per_v.get(v, 0) + 1
    res['crowd'] = chosen
    res['vendors'] = sorted(per_v)
    res['crowd_ok'] = bool(len(per_v) >= 4 and len(chosen) >= S.MIN_HEADS)
    for nm, ph in per_head.items():
        ph['p_pass'] = float(np.mean(list(ph['p_pass_env'].values()))) if ph.get('p_pass_env') else 0.0
    # FIXED-нов (уточнение до данных пилота 2, DECISIONS 16.11): наибольшая точность на ID пилота среди голов толпы, у которых
    # вероятность пройти проверку метода в среде теста не ниже P_PASS_FIXED; если таких нет — голова толпы с наибольшей такой вероятностью
    safe = [nm for nm in chosen if per_head[nm]['p_pass'] >= P_PASS_FIXED]
    res['fixed_new'] = (safe[0] if safe else max(chosen, key=lambda nm: per_head[nm]['p_pass'])) if chosen else None
    res['fixed_new_by_hypothesis'] = chosen[0] if chosen else None
    # вероятность, что опыт определён: среда годна, если проверку проходят не меньше шести голов толпы (по каждой пилотной среде —
    # свои вероятности голов, затем среднее); опыт — не меньше четырёх годных сред из пяти (среды теста независимы)
    if chosen:
        pv = [p_at_least([per_head[nm]['p_pass_env'][name] for nm in chosen], S.MIN_HEADS) for name in envs_new]
        p_env = float(np.mean(pv))
        p_fx = float(np.mean([per_head[res['fixed_new']]['p_pass_env'][name] for name in envs_new]))
        res['p_defined'] = dict(p_env_valid=p_env, p_env_valid_by_env=dict(zip(envs_new, pv)), p_defined=p_at_least([p_env] * 5, 4),
                                p_fixed_pass=p_fx, p_fixed_in_all_valid=p_fx ** 5,
                                note='приближение: точность головы в среде теста (p = 2) — как в пилотной среде (p = 0, 1); головы независимы при данной среде')
    # совпадение ошибок: пары разнородной толпы от разных производителей и пары шести разных Pythia; на тех же задачах
    q_rows = {}
    for name, env in envs_new.items():
        s = [p['sum'] for p in env['problems']]
        assert [(p['a'], p['b']) for p in env['problems']] == [(p['a'], p['b']) for p in py[name]['problems']], 'задачи не совпали с Pythia'
        new_ans = {h['model']: [r['answer'] for r in h['rows']] for h in env['heads'] if h['model'] in chosen}
        py_ans = {f"{h['model']}@{h['revision']}": h['answer'] for h in py[name]['heads']}
        new_l = [nm for nm in chosen if nm in new_ans]
        new_pairs = [(i, j) for i, j in itertools.combinations(range(len(new_l)), 2) if per_head[new_l[i]]['vendor'] != per_head[new_l[j]]['vendor']]
        py_l = [nm for nm in PY_DISTINCT if nm in py_ans]
        py_pairs = list(itertools.combinations(range(len(py_l)), 2))
        enc, s_ = encode({**new_ans, **py_ans}, s)
        psn, psp = pair_stats(enc, s_, new_l, new_pairs), pair_stats(enc, s_, py_l, py_pairs)
        (qn, mn), (qp, mp_) = q_of(psn), q_of(psp)
        dl, beta, alpha = adj_of(psn, psp)
        g = np.random.default_rng(SEED_BOOT_P + 10 * env['meta']['X'] + env['meta']['p'])
        bt, bta = [], []
        for _ in range(B):
            idx = g.choice(len(s), len(s))
            a_, b_ = pair_stats(enc, s_, new_l, new_pairs, idx), pair_stats(enc, s_, py_l, py_pairs, idx)
            bt.append(q_of(a_)[0] - q_of(b_)[0])
            bta.append(adj_of(a_, b_)[0])
        types = {}
        for nm in new_l:
            for a_, p in zip(new_ans[nm], env['problems']):
                if a_ is not None and a_ != p['sum']:
                    t = err_type(a_, p['a'], p['b'])
                    types[t] = types.get(t, 0) + 1
        q_rows[name] = dict(q_new=qn, n_joint_new=mn, q_py=qp, n_joint_py=mp_, d1=qn - qp, d1_sd=float(np.nanstd(bt, ddof=1)),
                            d1_adj=dl, d1_adj_sd=float(np.nanstd(bta, ddof=1)), adj_beta=beta, adj_alpha=alpha,
                            pairs=[dict(r, kind='нов') for r in psn] + [dict(r, kind='py') for r in psp],
                            n_pairs_new=len(new_pairs), n_pairs_py=len(py_pairs), err_types_new=types,
                            acc_new={nm: float(np.mean(enc[nm][1] & (enc[nm][0] == s_))) for nm in new_l},
                            acc_py={nm: float(np.mean(enc[nm][1] & (enc[nm][0] == s_))) for nm in py_l})
    res['q'] = q_rows
    if power and chosen and res['crowd_ok']:
        n_all = float(np.mean([len(env['problems']) for env in envs_new.values()]))
        res['power_d1'] = {k: agg_power([q_rows[n][k] for n in q_rows], [q_rows[n][k + '_sd'] for n in q_rows], n_all, n_test['all'], 'sign')
                           for k in ('d1', 'd1_adj')}
        res['power'] = crowd_power(envs_new, chosen, res['fixed_new'], B, n_test)
    res['seconds'] = round(time.time() - t0, 1)
    json.dump(res, open(dst, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print('годны:', cand, '| толпа:', chosen, '| производителей', len(per_v), '| FIXED-нов', res['fixed_new'], '| толпа годна', res['crowd_ok'])
    for name, r in q_rows.items():
        print(f"{name}: Q-нов {r['q_new']:.3f} ({r['n_joint_new']} общих ошибок) Q-py {r['q_py']:.3f} ({r['n_joint_py']}) "
              f"D1 {r['d1']:+.3f} ± {r['d1_sd']:.3f} | с поправкой {r['d1_adj']:+.3f} ± {r['d1_adj_sd']:.3f}")
    return res


def power_rule(kind, mu, tau, s, m, z=P.Z, band=P.BAND):
    """Мощность для среднего по m средам: точка ~ N(mu, (tau² + s²)/m), полуширина M4 = z·s/√m. equiv_out — D3: «подтверждено»,
    если интервал целиком вне полосы; «опровергнуто» — целиком внутри (правило P3/N с переставленными исходами)."""
    from scipy.stats import norm
    if kind in ('sign', 'equiv'):
        return P.power_one(kind, mu, tau, s, m, z)
    se, h = np.sqrt((tau ** 2 + s ** 2) / m), z * s / np.sqrt(m)
    out_ = float(norm.sf((band + h - mu) / se) + norm.cdf((-band - h - mu) / se))
    inside = 0.0 if h >= band else float(norm.cdf((band - h - mu) / se) - norm.cdf((-band + h - mu) / se))
    return out_, inside


def crowd_power(envs_new, chosen, fixed_new, B, n_test, m_test=5):
    """Точки и ст. откл. повторов D2–D5 и N на пилотных средах для толпы chosen (FIXED — fixed_new), мощность на тесте:
    ст. откл. среды пересчитывается на тест по числу задач диапазона правила, τ — разброс между пилотными средами."""
    g0 = {}
    for name, env in envs_new.items():
        env_c = dict(env, heads=[h for h in env['heads'] if h['model'] in chosen])
        off = 10 * env['meta']['X'] + env['meta']['p']
        st, info = prepare_scaled(env_c, SEED_CV_P + off, n_test['ID'])
        names = [info['names'][k] for k in info['keep']]
        if not info['valid']:
            g0[name] = dict(valid=False, keep=names, min_each=info['min_each'])
            continue
        fx = next((i for i, nm in enumerate(names) if nm.split('@')[0] == fixed_new), None)
        pt = stats_div(st, info['idi'], info['ood'], fx)
        g = np.random.default_rng(SEED_BOOT_P + 1000 + off)
        reps = [stats_div(st, g.choice(info['idi'], len(info['idi'])), g.choice(info['ood'], len(info['ood'])), fx) for _ in range(B)]
        row = dict(valid=True, n=len(env['problems']), n_id=int(len(info['idi'])), n_ood=int(len(info['ood'])), keep=names,
                   min_each=info['min_each'], fixed_in_crowd=fx is not None, rules={})
        for k, (pair, kind, rng) in RULES_D.items():
            v = [P.val(r, pair) for r in reps]
            row['rules'][k] = dict(point=float(P.val(pt, pair)), sd=float(np.nanstd(v, ddof=1)))
        g0[name] = row
    pw = {}
    valid = [n for n, r in g0.items() if r.get('valid')]
    for k, (pair, kind, rng) in RULES_D.items():
        key = 'n_id' if rng == 'ID' else 'n_ood'
        n_p = float(np.mean([g0[n][key] for n in valid])) if valid else 0.0
        r = agg_power([g0[n]['rules'][k]['point'] for n in valid], [g0[n]['rules'][k]['sd'] for n in valid], n_p, n_test[rng], kind, m_test)
        if r:
            pw[k] = dict(r, range=rng)
    return dict(envs=g0, rules=pw, n_test=n_test, m_test=m_test, n_valid_envs=len(valid))


# ───────────── тест (после PREREG)
# Константы теста задаются по пилоту 2 до регистрации (PREREG-OCDIV-01.md); пока они None, тест не запускается.
CROWD = None              # {имя модели: 'repo@commit'} — разнородная толпа
FIXED_NEW = None          # имя модели FIXED-нов
D1_RULE = None            # 'raw' — Q-нов − Q-py; 'adj' — δ с поправкой на точность; 'both' — вердикт, только если обе статистики согласны
D5_DESCRIPTIVE = None     # True — D5 описательно (мощность по пилоту < 0,2; HYPOTHESIS)
SEED_BOOT_T, SEED_Q_T = 7_980_000, 7_985_000                # бутстреп теста: оценщики и совпадение ошибок (+ 10·X + p)
PY_TEST_DIR = os.path.join(EXP, '2026-11-15_OCPOST-01/run/out')   # девять Pythia на средах теста (сырой вывод OCPOST-01)
PY_FIXED = 'pythia-2.8b-deduped'                            # FIXED однородной толпы — как в OCPOST-01 (описательно)
DESCR_T = {'POST-CV − SHIFT': ('ioi POST-CV', 'ioi SHIFT'), 'POST-CV − CONF': ('ioi POST-CV', 'ioi CONF'),
           'самообман CONF вне диапазона': ('dec CONF', None), 'самообман POST-CV вне диапазона': ('dec POST-CV', None),
           'самообман FIXED вне диапазона': ('dec FIXED', None), 'самообман AGREE вне диапазона': ('dec AGREE', None),
           'незнание AGREE − CONF': ('ign AGREE', 'ign CONF (core)'), 'самообман AGREE − CONF': ('dec AGREE', 'dec CONF (core)'),
           'CONF: post_stats − core': ('ioi CONF', 'ioi CONF (core)')}
UD1 = 'не решено (сырая D1 и D1 с поправкой на точность расходятся)'
DESCR_KEYS = ('T', 'C', 'ioi', 'ign', 'dec', 'brier')
DESCR_EST = ('CONF', 'POST-CV', 'ONE-BEST', 'FIXED', 'SHIFT', 'AGREE')


def _rep_div(fc):
    W = P._W
    r = stats_div(W['st'], fc[0], fc[1], W['fx'])
    return [r[k] for k in W['keys']]


def verdict_d(kind, iv):
    """Вердикт правила по интервалу M4: sign и equiv — ocpost.verdict; equiv_out (D3) — «подтверждено», если интервал целиком вне
    полосы ±BAND (со знаком), «опровергнуто», если целиком внутри."""
    if kind in ('sign', 'equiv'):
        return P.verdict(kind, iv)
    lo, hi = iv
    if hi < -P.BAND or lo > P.BAND:
        return 'подтверждено'
    return 'опровергнуто' if (lo >= -P.BAND and hi <= P.BAND) else 'не решено'


def crowd_point(env, fixed_model, seed):
    """Описательно, только точка: оценщики толпы из всех голов среды env; FIXED — fixed_model (по имени модели)."""
    st, info = S.prepare(env, seed)
    names = [info['names'][k] for k in info['keep']]
    out = dict(n_heads=len(env['heads']), crowd=names, valid=info['valid'])
    if not info['valid']:
        return out
    fx = next((i for i, nm in enumerate(names) if nm.split('@')[0] == fixed_model), None)
    r = stats_div(st, info['idi'], info['ood'], fx)
    out['stats'] = {f'{k} {e}': r.get(f'{k} {e}') for e in DESCR_EST for k in DESCR_KEYS}
    out['stats'].update({k: r[k] for k in ('wc CONF', 'wc POST', 'wc FIXED', 'wc ONE-BEST')})
    cs = st['corr'][info['keep']]
    out['oracle_ood'] = float(cs[:, info['ood']].any(0).mean())
    out['acc'] = {names[k]: dict(id=float(cs[k, info['idi']].mean()), ood=float(cs[k, info['ood']].mean())) for k in range(len(names))}
    return out


def test(dst, new_dir, B=10000, workers=1):
    assert CROWD and FIXED_NEW and D1_RULE in ('raw', 'adj', 'both') and D5_DESCRIPTIVE is not None, 'константы теста не заданы (PREREG)'
    t00 = time.time()
    d, envs_new = S.load_new(new_dir)
    _, envs_py = S.load_new(PY_TEST_DIR)
    envs_py = {k: v for k, v in envs_py.items() if v['meta'].get('kind') == 'test'}
    hm = {h['model']: h for h in d['heads']}
    rev = {nm: (f"{hm[nm]['repo']}@{hm[nm]['revision']}" if nm in hm else None) for nm in CROWD}
    res = dict(level=P.LEVEL, z=P.Z, band=P.BAND, B=B, crowd=CROWD, fixed_new=FIXED_NEW, d1_rule=D1_RULE, d5_descriptive=D5_DESCRIPTIVE,
               head_errors=d.get('head_errors', []), revisions=rev, revisions_ok=bool(all(rev[nm] == CROWD[nm] for nm in CROWD)), envs={})
    names_c = list(CROWD)
    new_pairs = [(i, j) for i, j in itertools.combinations(range(len(names_c)), 2)
                 if vendor(CROWD[names_c[i]].split('@')[0]) != vendor(CROWD[names_c[j]].split('@')[0])]
    py_l = list(PY_DISTINCT)
    py_pairs = list(itertools.combinations(range(len(py_l)), 2))
    pts, boots, valid = {}, {}, []
    for name in sorted(envs_new):
        t0 = time.time()
        env, pe = envs_new[name], envs_py[name]
        meta = env['meta']
        off = 10 * meta['X'] + meta['p']
        assert [(p['a'], p['b']) for p in env['problems']] == [(p['a'], p['b']) for p in pe['problems']], 'задачи не совпали с Pythia'
        env_c = dict(env, heads=[h for h in env['heads'] if h['model'] in CROWD])
        st, info = S.prepare(env_c, SEED_CV_P + off)
        r = dict(meta=meta, n_id=int(len(info['idi'])), n_ood=int(len(info['ood'])), method=info['method'], crowd=[info['names'][k] for k in info['keep']],
                 valid=info['valid'], n_crowd_heads=len(env_c['heads']), seed_cv=SEED_CV_P + off, seed_boot=SEED_BOOT_T + off, seed_q=SEED_Q_T + off)
        # D1: все задачи среды, все головы толпы и шесть разных Pythia; бутстреп по задачам, одинаковый для всех голов
        s = [p['sum'] for p in env['problems']]
        new_ans = {h['model']: [x['answer'] for x in h['rows']] for h in env_c['heads']}
        py_ans = {f"{h['model']}@{h['revision']}": [x['answer'] for x in h['rows']] for h in pe['heads']}
        enc, s_ = encode({**new_ans, **py_ans}, s)
        psn, psp = pair_stats(enc, s_, names_c, new_pairs), pair_stats(enc, s_, py_l, py_pairs)
        cross = pair_stats(enc, s_, names_c + py_l, [(i, len(names_c) + j) for i in range(len(names_c)) for j in range(len(py_l))])
        qn, qp = q_of(psn), q_of(psp)
        dl, beta, alpha = adj_of(psn, psp)
        g = np.random.default_rng(SEED_Q_T + off)
        bq = np.empty((B, 2))
        for b in range(B):
            idx = g.choice(len(s), len(s))
            a_, b_ = pair_stats(enc, s_, names_c, new_pairs, idx), pair_stats(enc, s_, py_l, py_pairs, idx)
            bq[b] = (q_of(a_)[0] - q_of(b_)[0], adj_of(a_, b_)[0])
        types = {'нов': {}, 'py': {}}
        for kind_, mp_, labs in (('нов', new_ans, names_c), ('py', py_ans, py_l)):
            for nm in labs:
                for a_, p in zip(mp_[nm], env['problems']):
                    if a_ is not None and a_ != p['sum']:
                        t = err_type(a_, p['a'], p['b'])
                        types[kind_][t] = types[kind_].get(t, 0) + 1
        r['q'] = dict(q_new=qn[0], n_joint_new=qn[1], q_py=qp[0], n_joint_py=qp[1], d1=qn[0] - qp[0], d1_adj=dl, adj_beta=beta, adj_alpha=alpha,
                      q_cross_descr=q_of(cross)[0], err_types=types, pairs=[dict(x, kind='нов') for x in psn] + [dict(x, kind='py') for x in psp],
                      acc={nm: float(np.mean(enc[nm][1] & (enc[nm][0] == s_))) for nm in names_c + py_l})
        if info['valid']:
            valid.append(name)
            names = [info['names'][k] for k in info['keep']]
            fx = next((i for i, nm in enumerate(names) if nm.split('@')[0] == FIXED_NEW), None)
            r['fixed_in_crowd'] = fx is not None
            pt = stats_div(st, info['idi'], info['ood'], fx)
            keys = sorted(pt)
            gb = np.random.default_rng(SEED_BOOT_T + off)
            draws = [(gb.choice(info['idi'], len(info['idi'])), gb.choice(info['ood'], len(info['ood']))) for _ in range(B)]
            bt = np.array(P._pmap(_rep_div, draws, dict(st=st, keys=keys, fx=fx), workers), float).T
            pt['d1'], pt['d1_adj'] = r['q']['d1'], r['q']['d1_adj']
            pts[name] = pt
            boots[name] = {**{k: bt[j] for j, k in enumerate(keys)}, 'd1': bq[:, 0], 'd1_adj': bq[:, 1]}
            cs = st['corr'][info['keep']]
            r['oracle_ood'] = float(cs[:, info['ood']].any(0).mean())
            r['one_best_is_fixed'] = bool(pt.get('one_best_is_fixed'))
            r['rules_env'] = {k: dict(point=float(P.val(pt, pr)), sd=float(np.std(P.val(boots[name], pr), ddof=1)))
                              for k, (pr, kind, rng) in RULES_D.items()}
            r['rules_env']['D1'] = dict(point=r['q']['d1'], sd=float(np.std(bq[:, 0], ddof=1)), adj=dl, adj_sd=float(np.std(bq[:, 1], ddof=1)))
        # описательно: оценщики однородной (девять Pythia) и смешанной толпы — только точка
        r['descr_py'] = crowd_point(pe, PY_FIXED, SEED_CV_P + off)
        r['descr_mix'] = crowd_point(dict(env, heads=pe['heads'] + env_c['heads']), FIXED_NEW, SEED_CV_P + off)
        r['seconds'] = round(time.time() - t0, 1)
        res['envs'][name] = r
        print(f"{name}: ID {r['n_id']}, OOD {r['n_ood']}, толпа {len(r['crowd'])} из {r['n_crowd_heads']}, годна {r['valid']}, "
              f"Q-нов {qn[0]:.3f} Q-py {qp[0]:.3f}, {r['seconds']} с", flush=True)
    m = len(valid)
    n_env = len(envs_new)
    method_ok = bool(m >= int(np.ceil(P.MIN_VALID_FRAC * n_env)) and m >= 1 and res['revisions_ok'] and n_env == 5)
    fixed_ok = bool(all(res['envs'][n].get('fixed_in_crowd') for n in valid))
    res['method'] = dict(ok=method_ok, n_envs=n_env, n_valid=m, valid=valid, fixed_in_all_valid=fixed_ok, revisions_ok=res['revisions_ok'])
    if m == 0:
        res['verdicts'] = {k: P.U for k in ('D1',) + tuple(RULES_D)}
        json.dump(res, open(dst, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
        return res
    group = {n: envs_new[n]['meta'].get('X', n) for n in valid}

    def mean_entry(pair, level):
        pt = float(np.mean([P.val(pts[n], pair) for n in valid]))
        bt = np.mean([P.val(boots[n], pair) for n in valid], 0)
        iv, sd = P.m4(pt, bt, level)
        return dict(delta=pt, ci=iv, boot_sd=sd, boot_shift=float(np.mean(bt) - pt), level=level, by_env={n: float(P.val(pts[n], pair)) for n in valid})
    for k, (pair, kind, rng) in (('D1', (('d1', None), 'sign', 'all')), ('D1 adj', (('d1_adj', None), 'sign', 'all')), *RULES_D.items()):
        e = mean_entry(pair, P.LEVEL)
        v = verdict_d(kind, e['ci'])
        if kind == 'sign':                                          # предохранитель «без одного диапазона» — как в OCPOST-01
            v, e['leave_one_range_out'] = A_range_guard(v, e['by_env'], group)
        e['verdict_rule'] = v
        e['kind'], e['range'] = kind, rng
        res[k] = e
    for k in ('D1', 'D1 adj') + tuple(RULES_D):
        e = res[k]
        e['verdict'] = P.U if not method_ok else (P.UF if (k in ('D3', 'N') and not fixed_ok) else e['verdict_rule'])
    vr, va = res['D1']['verdict'], res['D1 adj']['verdict']
    res['D1']['verdict_raw'] = vr
    if method_ok:
        res['D1']['verdict'] = {'raw': vr, 'adj': va, 'both': (vr if vr == va else UD1)}[D1_RULE]
    if res['N']['verdict'] == 'опровергнуто' and res['D4']['verdict'] != P.U:
        res['D4']['verdict_before_N'] = res['D4']['verdict']
        res['D4']['verdict'] = P.UN
    if D5_DESCRIPTIVE:
        res['D5']['verdict_rule_descr'] = res['D5']['verdict']
        res['D5']['verdict'] = 'описательно (мощность по пилоту < 0,2; PREREG)'
    res['D3']['sign'] = 'C > T (завышение заявки)' if res['D3']['delta'] > 0 else 'C < T (занижение заявки)'
    for k, pair in DESCR_T.items():
        if all(np.isfinite(P.val(pts[n], pair)) for n in valid):
            res[f'descr_{k}'] = mean_entry(pair, P.DESCR_LEVEL)
    res['verdicts'] = {k: res[k]['verdict'] for k in ('D1',) + tuple(RULES_D)}
    res['verdict'] = '; '.join(f'{k}: {v}' for k, v in res['verdicts'].items())
    res['seconds'] = round(time.time() - t00, 1)
    json.dump(res, open(dst, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print('вердикт:', res['verdict'])
    for k in ('D1', 'D1 adj') + tuple(RULES_D):
        e = res[k]
        print(f"{k}: Δ {e['delta']:+.4f} M4 [{e['ci'][0]:+.4f}; {e['ci'][1]:+.4f}] ст. откл. {e['boot_sd']:.4f}"
              + (f" | без диапазона: {e['leave_one_range_out']['holds']}" if 'leave_one_range_out' in e else ''))
    print('годных сред', m, 'из', n_env, '| время', res['seconds'], 'с')
    return res


def A_range_guard(v, by_env, group):
    """Предохранитель «без одного диапазона» — функция analyze_ocshift_test.range_guard, как в OCPOST-01 (импорт через ocpost)."""
    return P.A.range_guard(v, by_env, group)


def main():
    a = sys.argv[1:]
    if a[0] == 'merge':
        merge(a[1], a[2], int(a[3]), a[5:], pick=a[4])
    elif a[0] == 'pilot':
        B = int(a[a.index('--boot') + 1]) if '--boot' in a else 200
        pilot(a[1], a[2], B, power='--no-power' not in a)
    elif a[0] == 'test':
        B = int(a[a.index('--boot') + 1]) if '--boot' in a else 10000
        W = int(a[a.index('--workers') + 1]) if '--workers' in a else 1
        test(a[1], a[2], B, W)


if __name__ == '__main__':
    main()
