#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""OCDIV-01 «ОЦЕНЩИК-РАЗНЫЕ-ГОЛОВЫ»: сборка ответов новых голов и разбор пилота (тест — после PREREG).
  python3 ocdiv.py merge  OUT_DIR SOURCE N JOB_DIR [JOB_DIR ...]   — answers.json вида ocshift_extract (среды источника + новые головы)
  python3 ocdiv.py pilot  RESULT.json NEW_DIR [--boot 200]           — пилот: годность, скорость, совпадение ошибок, оценщики, мощность
SOURCE — test (пять сред OCPOST-01) или pilot (десять сред OCSHIFT-01); N — сколько первых задач среды (0 — все).
Код счёта — зарегистрированный код прежних опытов: проверка метода и массивы — analyze_ocshift.prepare; оценщики — ocpost.post_stats
и analyze_ocshift.core (AGREE). Совпадение ошибок q(i, j) — HYPOTHESIS.md."""
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
S = P.S                                                     # analyze_ocshift

SRC = {'test': os.path.join(EXP, '2026-11-15_OCPOST-01/run/out/answers.json'),
       'pilot': os.path.join(EXP, '2026-11-15_OCSHIFT-01/run/out/answers.json')}
VENDOR = {'Qwen': 'Alibaba', 'HuggingFaceTB': 'Hugging Face', 'allenai': 'AI2', 'ibm-granite': 'IBM', 'tiiuae': 'TII',
          'TinyLlama': 'TinyLlama', 'LiquidAI': 'Liquid AI', 'bigscience': 'BigScience', 'EleutherAI': 'EleutherAI'}
PY_DISTINCT = ('pythia-1.4b@main', 'pythia-1.4b-deduped@main', 'pythia-2.8b@main', 'pythia-2.8b-deduped@main',
               'pythia-6.9b@main', 'pythia-6.9b-deduped@main')                     # Q-py: шесть разных моделей, без чекпойнтов
SEED_CV_P, SEED_BOOT_P = 7_620_000, 7_950_000               # части — правило OCSHIFT-01 (7 620 000 + 10·X + p); бутстреп пилота — новое зерно


def vendor(repo):
    return VENDOR.get(repo.split('/')[0], repo.split('/')[0])


# ───────────── сборка
def merge(out_dir, source, n, job_dirs):
    src = json.load(open(SRC[source], encoding='utf-8'))
    envs = []
    for e in src['envs']:
        if e.get('kind') == 'check':
            continue
        e = dict(e)
        e['problems'] = e['problems'][:n] if n else e['problems']
        envs.append(e)
    heads, errors = [], []
    for jd in job_dirs:
        for f in sorted(glob.glob(os.path.join(jd, 'answers_*.json'))):
            h = json.load(open(f, encoding='utf-8'))
            if 'error' in h or 'cols' not in h:
                errors.append(dict(model=h.get('model'), error=h.get('error', 'нет cols'), file=os.path.relpath(f, ROOT)))
                continue
            cols = {e['name']: {k: (v[:len(e['problems'])] if isinstance(v, list) else v) for k, v in h['cols'][e['name']].items()}
                    for e in envs if e['name'] in h['cols']}
            if len(cols) != len(envs):
                errors.append(dict(model=h['model'], error=f'сред {len(cols)} из {len(envs)}', file=os.path.relpath(f, ROOT)))
                continue
            heads.append(dict(model=h['repo'].split('/')[-1], repo=h['repo'], revision=h.get('commit') or h['revision'], vendor=vendor(h['repo']),
                              seconds_env=h.get('seconds_env'), n_tasks=sum(len(e['problems']) for e in envs), cols=cols))
    os.makedirs(out_dir, exist_ok=True)
    d = dict(mode=source, source_file=os.path.relpath(SRC[source], ROOT), n=n, envs=envs, heads=heads, head_errors=errors,
             info=dict(merged_by='ocdiv.py merge', when=time.strftime('%Y-%m-%d %H:%M UTC', time.gmtime())))
    for e in d['envs']:
        e['kind'] = 'test'                                  # S.load_new берёт все среды; метка — для ocpost.load_envs
    json.dump(d, open(os.path.join(out_dir, 'answers.json'), 'w', encoding='utf-8'), ensure_ascii=False)
    print(f'собрано: голов {len(heads)}, ошибок {len(errors)}, сред {len(envs)} → {out_dir}/answers.json')
    return d


def pythia_envs(source, n):
    """Ответы девяти Pythia на тех же задачах (первые n) — из сырого вывода источника."""
    src = json.load(open(SRC[source], encoding='utf-8'))
    out = {}
    for e in src['envs']:
        if e.get('kind') == 'check':
            continue
        k = n or len(e['problems'])
        heads = [dict(model=h['model'], revision=h['revision'], answer=h['cols'][e['name']]['answer'][:k],
                      correct=h['cols'][e['name']]['correct'][:k]) for h in src['heads'] if 'cols' in h]
        out[e['name']] = dict(problems=e['problems'][:k], heads=heads)
    return out


# ───────────── совпадение ошибок
def q_pair(a_i, a_j, s, idx=None):
    """q(i, j): среди задач, где у обеих голов ответ — число и обе ошиблись, доля задач с равными ответами. Возвращает (q, число)."""
    a_i, a_j, s = np.asarray(a_i, object), np.asarray(a_j, object), np.asarray(s, object)
    if idx is not None:
        a_i, a_j, s = a_i[idx], a_j[idx], s[idx]
    both = np.array([(x is not None) and (y is not None) and (x != t) and (y != t) for x, y, t in zip(a_i, a_j, s)], bool)
    m = int(both.sum())
    if m == 0:
        return float('nan'), 0
    same = np.array([x == y for x, y in zip(a_i[both], a_j[both])], bool)
    return float(same.mean()), m


def err_type(ans, a, b):
    """Тип ошибки сложения (описательно): потеря переноса в десятки/сотни, лишний перенос, прочее."""
    s = a + b
    d = ans - s
    if d in (-10, -100, -110):
        return 'потеря переноса'
    if d in (10, 100, 110):
        return 'лишний перенос'
    return 'прочее'


def q_crowd(heads_ans, labels, s, pairs, idx=None):
    vals = []
    for i, j in pairs:
        q, m = q_pair(heads_ans[labels[i]], heads_ans[labels[j]], s, idx)
        if m >= 1 and np.isfinite(q):
            vals.append((q, m))
    if not vals:
        return float('nan'), 0
    return float(np.mean([v[0] for v in vals])), int(sum(v[1] for v in vals))


# ───────────── пилот
def pilot(dst, new_dir, B=200):
    t0 = time.time()
    d, envs_new = S.load_new(new_dir)
    py = pythia_envs(d['mode'], d.get('n', 0))
    heads_meta = {h['model']: h for h in d['heads']}
    res = dict(source=d['mode'], n=d.get('n'), head_errors=d.get('head_errors', []), envs={}, heads={}, B=B)
    per_head = {h['model']: dict(repo=h['repo'], vendor=h['vendor'], revision=h['revision'], ok_envs=0, n_envs=0, acc_id=[], acc_ood=[], none=[],
                                 sec_per_task=float(np.sum(list((h.get('seconds_env') or {}).values()) or [0])) / max(h.get('n_tasks') or 1, 1))
                for h in d['heads']}
    for name, env in envs_new.items():
        meta = env['meta']
        off = 10 * meta['X'] + meta['p']
        st, info = S.prepare(env, SEED_CV_P + off)
        for k, nm in enumerate(info['names']):
            m = info['method'][nm]
            ph = per_head[env['heads'][k]['model']]
            ph['n_envs'] += 1
            ph['ok_envs'] += int(m['ok'])
            ph['acc_id'].append(m['id_correct'] / max(m['id_correct'] + m['id_wrong'], 1))
            ph['acc_ood'].append(m['ood_correct'] / max(m['ood_correct'] + m['ood_wrong'], 1))
            ph['none'].append(m['none_frac'])
        res['envs'][name] = dict(n=len(env['problems']), n_id=int(len(info['idi'])), method=info['method'])
    for nm, ph in per_head.items():
        for k in ('acc_id', 'acc_ood', 'none'):
            ph[k + '_mean'] = float(np.mean(ph[k])) if ph[k] else None
        ph['valid'] = bool(ph['n_envs'] and ph['ok_envs'] >= P.MIN_VALID_FRAC * ph['n_envs'] and ph['sec_per_task'] <= 1.5)
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
    res['crowd_ok'] = bool(len(per_v) >= 4)
    res['fixed_new'] = chosen[0] if chosen else None
    # совпадение ошибок: новые пары от разных производителей и пары шести разных Pythia; на тех же задачах
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
        qn, mn = q_crowd(new_ans, new_l, s, new_pairs)
        qp, mp_ = q_crowd(py_ans, py_l, s, py_pairs)
        g = np.random.default_rng(SEED_BOOT_P + 10 * env['meta']['X'] + env['meta']['p'])
        bt = []
        for _ in range(B):
            idx = g.choice(len(s), len(s))
            bt.append(q_crowd(new_ans, new_l, s, new_pairs, idx)[0] - q_crowd(py_ans, py_l, s, py_pairs, idx)[0])
        types = {}
        for nm in new_l:
            for a_, p in zip(new_ans[nm], env['problems']):
                if a_ is not None and a_ != p['sum']:
                    t = err_type(a_, p['a'], p['b'])
                    types[t] = types.get(t, 0) + 1
        acc_pair_new = float(np.mean([(per_head[new_l[i]]['acc_id_mean'] + per_head[new_l[j]]['acc_id_mean']) / 2 for i, j in new_pairs])) if new_pairs else None
        q_rows[name] = dict(q_new=qn, n_joint_new=mn, q_py=qp, n_joint_py=mp_, d1=qn - qp, d1_sd=float(np.nanstd(bt, ddof=1)),
                            n_pairs_new=len(new_pairs), n_pairs_py=len(py_pairs), err_types_new=types, acc_pair_new=acc_pair_new,
                            acc_py={nm: float(np.mean([x == t for x, t in zip(py_ans[nm], s)])) for nm in py_l})
    res['q'] = q_rows
    res['seconds'] = round(time.time() - t0, 1)
    json.dump(res, open(dst, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print('толпа:', chosen, '| производителей', len(per_v), '| FIXED-нов', res['fixed_new'])
    for name, r in q_rows.items():
        print(f"{name}: Q-нов {r['q_new']:.3f} ({r['n_joint_new']} общих ошибок) Q-py {r['q_py']:.3f} ({r['n_joint_py']}) D1 {r['d1']:+.3f} ± {r['d1_sd']:.3f}")
    return res


def main():
    a = sys.argv[1:]
    if a[0] == 'merge':
        merge(a[1], a[2], int(a[3]), a[4:])
    elif a[0] == 'pilot':
        B = int(a[a.index('--boot') + 1]) if '--boot' in a else 200
        pilot(a[1], a[2], B)


if __name__ == '__main__':
    main()
