#!/usr/bin/env python3
"""SCORE-02: обвязка. Головы — только через tools/run_sealed2.py в чистом контексте (как SCORE-01: HOME и рабочая папка вне git,
CLAUDE_CODE_DISABLE_GIT_INSTRUCTIONS=1). Промпт — рука LOG SCORE-01 (prompts_score.prompt_half, формат «в лучшей половине»), без изменений;
на задачу K вызовов одного промпта (id «задача|LOG|k»).
  python3 score02.py jobs <этап> <выборка> [K]          → задания: пилот — run/<этап>_jobs.jsonl, тест — jobs/<этап>_jobs.jsonl
  python3 score02.py truth <выборка>                    → truth/<выборка>.json: правда 8 кандидатов по R = 4000 и четвёрка лучших
  python3 score02.py metrics <этап> <выборка> <выгрузка> [K] [папка] → <папка, по умолчанию evals>/<этап>.json: меры вызовов и три
                                                        источника уверенности (сухой прогон пишет в dry/evals, не в evals)
Выборки:
  pilot — WH 7001–7012 и 7301–7308 (задачи и пулы SELECT-01; метки — четвёрка по R = 4000 из SCORE-01, truth/check_pilot.json; это
          пилотные задачи SCORE-01 и в тест не входят);
  main  — WH 8201–8300 (задачи и пулы THINK-01; соль — salts/main_salt.txt, новая);
  rep   — WH 8301–8359 (задачи и пулы PRECOND-01; соль — salts/rep_salt.txt, новая).
Порядок кандидатов — одна перестановка на задачу по sha256(сид|perm), как в SELECT-01 и SCORE-01; ничьи — по sha256(задача|кандидат).
Источники уверенности суждения «кандидат в лучшей половине» (по годным вызовам задачи; p = 0,5 — не сторона):
  single — каждый годный вызов отдельно (суждения всех вызовов задачи вместе): сторона p от 0,5, уверенность max(p, 1 − p);
  mean   — среднее p годных вызовов: сторона и уверенность по нему;
  agree  — сторона большинства годных вызовов (с p ≠ 0,5; ничья сторон — суждения нет), уверенность — доля вызовов на стороне большинства.
Мера различения — AUC второго рода: P(уверенность верного суждения > уверенности неверного), ничьи — ½."""
import bisect
import hashlib
import json
import math
import os
import random
import secrets
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
EXP = os.path.abspath(os.path.join(HERE, '..'))
SEL = os.path.join(EXP, '2026-10-07_SELECT-01')
SC1 = os.path.join(EXP, '2026-10-28_SCORE-01')
SRC = dict(pilot=SEL, main=os.path.join(EXP, '2026-10-15_THINK-01'), rep=os.path.join(EXP, '2026-10-21_PRECOND-01'))
IDS = dict(pilot=list(range(7001, 7013)) + list(range(7301, 7309)), main=list(range(8201, 8301)), rep=list(range(8301, 8360)))
sys.path.insert(0, SEL)
sys.path.insert(0, SC1)
import sim  # noqa: E402
import prompts_score as P  # noqa: E402

ARM = 'LOG'
K_DEFAULT = 5
R_BIG = 4000
P_FLOOR = 1e-6
hkey = lambda t, i: hashlib.sha256(f'{t}|{i}'.encode()).hexdigest()


def sample_tasks(name):
    return [f'WH_{s}' for s in IDS[name] if os.path.exists(os.path.join(SRC[name], 'pools', f'WH_{s}.json'))]


def src_of(t):
    s = int(t.split('_')[1])
    return next(SRC[k] for k, v in IDS.items() if s in v)


task = lambda t: json.load(open(os.path.join(src_of(t), 'tasks', f'{t}.json')))
pool = lambda t: json.load(open(os.path.join(src_of(t), 'pools', f'{t}.json')))


def perm(t, k=8):
    p = list(range(k))
    random.Random(int(hashlib.sha256(f'{task(t)["seed"]}|perm'.encode()).hexdigest()[:16], 16)).shuffle(p)
    return p


def salt(name):
    assert name in ('main', 'rep'), 'у пилота метки SCORE-01'
    p = os.path.join(HERE, 'salts', f'{name}_salt.txt')
    if not os.path.exists(p):
        os.makedirs(os.path.dirname(p), exist_ok=True)
        open(p, 'w').write(secrets.token_hex(32))
    return open(p).read().strip()


def cmd_jobs(stage, sample, K=K_DEFAULT):
    d = 'run' if stage.startswith(('pilot', 'dry')) else 'jobs'
    os.makedirs(os.path.join(HERE, d), exist_ok=True)
    ts = sample_tasks(sample)
    path = os.path.join(HERE, d, f'{stage}_jobs.jsonl')
    with open(path, 'w', encoding='utf-8') as fh:
        for t in ts:
            tk, pl, pm = task(t), pool(t), perm(t)
            shown = [pl[j] for j in pm]
            pr = P.prompt_half(ARM, sim.RULES['WH'](tk), shown)
            for k in range(int(K)):
                fh.write(json.dumps(dict(task=t, id=f'{t}|{ARM}|{k}', arm=ARM, prompt=pr, schema=P.SCHEMA_H), ensure_ascii=False) + '\n')
    print(path, len(ts) * int(K), 'заданий;', len(ts), 'задач; K =', K, '; хеши промпта:', P.hashes())


def cmd_truth(sample):
    """Правда — среднее итога по R = 4000 реализациям шума (sim.noise_seeds соли выборки; общие случайные числа для кандидатов),
    четвёрка лучших — по ней (ничьи по sha256). Как truth_check.py SCORE-01; первые 1000 реализаций — те же, что у sim.truth."""
    os.makedirs(os.path.join(HERE, 'truth'), exist_ok=True)
    s = salt(sample)
    out = {}
    for t in sample_tasks(sample):
        tk, pl = task(t), pool(t)
        seeds = sim.noise_seeds(s, tk['seed'], R_BIG)
        V = [[sim.SIM['WH'](tk, c['plan'], sim.NOISE['WH'](tk, z)) for z in seeds] for c in pl]
        m4 = [sum(v) / R_BIG for v in V]
        m1 = [round(sum(v[:1000]) / 1000, 2) for v in V]
        o4 = sorted(range(8), key=lambda i: (-m4[i], hkey(t, i)))
        o1 = sorted(range(8), key=lambda i: (-m1[i], hkey(t, i)))
        a, b = o4[3], o4[4]
        d = [x - y for x, y in zip(V[a], V[b])]
        md = sum(d) / R_BIG
        se = math.sqrt(sum((x - md) ** 2 for x in d) / (R_BIG - 1) / R_BIG)
        out[t] = dict(truth4000=m4, truth1000=m1, top4_4000=sorted(o4[:4]), top4_1000=sorted(o1[:4]), z45_4000=(m4[a] - m4[b]) / se if se > 0 else None)
    json.dump(dict(sample=sample, salt_sha256=hashlib.sha256(s.encode()).hexdigest(), R=R_BIG, tasks=out),
              open(os.path.join(HERE, 'truth', f'{sample}.json'), 'w'), indent=0)
    same = sum(1 for v in out.values() if v['top4_4000'] == v['top4_1000'])
    print(f'правда {sample}: задач {len(out)}; четвёрка по 4000 = по 1000 у {same}; z45 < 2 у {sum(1 for v in out.values() if v["z45_4000"] is not None and v["z45_4000"] < 2)}')


def labels_for(sample):
    if sample == 'pilot':
        tk = json.load(open(os.path.join(SC1, 'truth', 'check_pilot.json')))['tasks']
    else:
        tk = json.load(open(os.path.join(HERE, 'truth', f'{sample}.json')))['tasks']
    return {t: set(v['top4_4000']) for t, v in tk.items()}


def valid_half(res):
    p = (res or {}).get('p')
    if not isinstance(p, list) or len(p) != 8 or any(not isinstance(x, (int, float)) or math.isnan(x) or x < 0 or x > 1 for x in p):
        return None
    return [float(x) for x in p]


def auc(scores, labels):
    pos = [s for s, l in zip(scores, labels) if l]
    neg = sorted(s for s, l in zip(scores, labels) if not l)
    if not pos or not neg:
        return float('nan')
    tot = 0.0
    for s in pos:
        lo, hi = bisect.bisect_left(neg, s), bisect.bisect_right(neg, s)
        tot += lo + 0.5 * (hi - lo)
    return tot / (len(pos) * len(neg))


RND = 9   # уверенности и среднее p округляются до 1e−9: равные по смыслу значения (0,67 и 1 − 0,33; среднее пяти p) — одно число


def judgments(rows_t, lab, K):
    """Суждения задачи по трём источникам. rows_t — {k: p (в номерах пула) или None}; lab — четвёрка лучших.
    Возвращает {источник: [(уверенность, верно), …]} по кандидатам, у которых суждение есть, и cand — [(вызовов на верной
    стороне, вызовов с p ≠ 0,5), …] по кандидатам, у которых такой вызов есть (для разложения самообмана согласия, PREREG §8).
    Округление (LENSES-1, L2-5 и та же ошибка у одного вызова): без него 1 − 0,33 = 0,6699999999999999 ≠ 0,67, и AUC разрывает ничью."""
    ok = [rows_t[k] for k in range(K) if rows_t.get(k) is not None]
    out = dict(single=[], mean=[], agree=[], cand=[])
    if not ok:
        return out
    for i in range(8):
        y = i in lab
        for p in ok:
            if p[i] != 0.5:
                out['single'].append((round(max(p[i], 1 - p[i]), RND), (p[i] > 0.5) == y))
        m = round(sum(p[i] for p in ok) / len(ok), RND)
        if m != 0.5:
            out['mean'].append((round(max(m, 1 - m), RND), (m > 0.5) == y))
        up = sum(1 for p in ok if p[i] > 0.5)
        dn = sum(1 for p in ok if p[i] < 0.5)
        if up != dn:
            out['agree'].append((round(max(up, dn) / (up + dn), RND), (up > dn) == y))
        if up + dn:
            out['cand'].append((up if y else dn, up + dn))
    return out


def task_values(rows, lab, K):
    """Значения задачи: для каждого источника — список суждений; для мер калибровки — p суждения (уверенность со стороной)."""
    J = {}
    for t in sorted({r['task'] for r in rows.values()}):
        rt = {int(jid.split('|')[2]): r.get('p') for jid, r in rows.items() if r['task'] == t}
        J[t] = judgments(rt, lab[t], K)
    return J


def summarize(J):
    """Сводка по суждениям всех задач: AUC второго рода, уверенность, точность, самообман, Брайер суждения (по уверенности)."""
    out = {}
    for src in ('single', 'mean', 'agree'):
        allj = [j for t in J for j in J[t][src]]
        if not allj:
            continue
        conf = [c for c, _ in allj]
        cor = [1.0 if ok else 0.0 for _, ok in allj]
        out[src] = dict(n=len(allj), auc2=auc(conf, cor), conf=sum(conf) / len(conf), acc=sum(cor) / len(cor),
                        self_dec=sum(conf) / len(conf) - sum(cor) / len(cor),
                        brier=sum((c - o) ** 2 for c, o in zip(conf, cor)) / len(conf))
    return out


def cmd_metrics(stage, sample, export, K=K_DEFAULT, out_dir=None):
    K = int(K)
    out_dir = os.path.join(HERE, out_dir) if out_dir else os.path.join(HERE, 'evals')
    lab = labels_for(sample)
    rec = {}
    for r in map(json.loads, open(export, encoding='utf-8')):
        assert r['id'] not in rec, f'повтор id {r["id"]}'
        rec[r['id']] = r
    rows = {}
    for jid, r in rec.items():
        t = jid.split('|')[0]
        pm = perm(t)
        ps = valid_half(r.get('result'))
        row = dict(task=t, valid=ps is not None, error=r.get('error'), inp=r.get('inp', 0), out=r.get('out', 0), cost=r.get('cost_usd'), p=None)
        if ps is not None:
            pp = [0.0] * 8
            for i, x in enumerate(ps):
                pp[pm[i]] = x
            row['p'] = pp
            L = [int(i in lab[t]) for i in range(8)]
            acc = [1.0 if (x > 0.5) == bool(l) and x != 0.5 else (0.5 if x == 0.5 else 0.0) for x, l in zip(pp, L)]
            row.update(acc=sum(acc) / 8, conf=sum(max(x, 1 - x) for x in pp) / 8,
                       brier=sum((x - l) ** 2 for x, l in zip(pp, L)) / 8,
                       logloss=sum(-math.log(max(x if l else 1 - x, P_FLOOR)) for x, l in zip(pp, L)) / 8)
        rows[jid] = row
    J = task_values(rows, lab, K)
    summ = summarize(J)
    v = [r for r in rows.values() if r['valid']]
    calls = dict(n=len(rows), valid=len(v), out=sum(r['out'] for r in v) / max(1, len(v)),
                 cost=sum(r['cost'] or 0 for r in rows.values()), acc=sum(r['acc'] for r in v) / max(1, len(v)),
                 conf=sum(r['conf'] for r in v) / max(1, len(v)))
    calls['self_dec'] = calls['conf'] - calls['acc']
    os.makedirs(out_dir, exist_ok=True)
    json.dump(dict(stage=stage, sample=sample, K=K, rows=rows, judgments={t: {s: [[c, ok] for c, ok in J[t][s]] for s in J[t]} for t in J},
                   summary=summ, calls=calls), open(os.path.join(out_dir, f'{stage}.json'), 'w'), ensure_ascii=False, indent=0)
    print('вызовы:', {k: round(x, 4) if isinstance(x, float) else x for k, x in calls.items()})
    for s_, d in summ.items():
        print(s_, {k: round(x, 4) if isinstance(x, float) else x for k, x in d.items()})


if __name__ == '__main__':
    cmd, *args = sys.argv[1:]
    dict(jobs=cmd_jobs, truth=cmd_truth, metrics=cmd_metrics)[cmd](*args)
