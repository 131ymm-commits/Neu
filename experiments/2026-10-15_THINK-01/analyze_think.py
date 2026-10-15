# THINK-01: анализ (редакция 2 — после совета 34). Регрет, ничьи, большинство, A0, перестановочный тест и бутстреп — функции
# analyze.py SELECT-01 (sha256 06f4f5f8…).
#   python3 analyze_think.py <evals/stage.jsonl> --key <main|rep|dry> --seeds <seeds.json> [--out json]
# Соль — по ключу выборки (совет 34, Н8): main → /root/think_secret, rep → /root/think_secret_rep; dry — только явный THINK_SECRET.
# Записи: по (задача, рука, i) берётся первая несбойная, если все сбойные — первая сбойная (Н5, возражение Левого 2).
# Полнота (Н6): ожидаются все задачи сидов с пулом, по prompts_think.SPEC (36 вызовов). Пропущенный вызов = «потерян».
#   Анализ — по полным задачам; доля «потерян» считается по всем ожидаемым задачам.
# Руки: B_blind ×12, C_N ×5, D_N ×5, U_N ×5, P_N ×5 — effort medium; H ×3 (ROLE, high): H_1 = вызов i = 0, H_3 = большинство трёх;
#   H_c ×1 (ROLE_CONF, high). Свёртка — большинство допустимых голосов (номер 0..k−1); нет допустимых → r = 1;
#   у D_N — большинство среди неотказавшихся, нет таких → A0. Отказ (−1) у рук без варианта −1 — недопустимый голос.
# Первичное (Холм, α = 0,05, односторонне — у H_1 регрет меньше): P1 H_1 − B_blind, P2 H_1 − D_N.
#   Засчитано = Холм отвергает + средний на задачу выход (out, с размышлениями) H_1 ≤ соперника (Н4; равенство — засчитано)
#   + доля «потерян» у H_1 (вызовы i = 0) и у соперника ≤ 0,02 (иначе «не измерено»).
#   P1/P2 сравнивают глубину и ширину при не большем бюджете H_1; засчитанные опровергают гипотезу программы только против этих
#   двух систем; незасчитанные её не подтверждают (Н1). Прямая проверка — S1b.
# S1b (Н2): H_1 против свёртки первых m голосов руки (i < m) по правилу той же руки; m = ⌊13117 / выход голоса руки⌋ по
#   pilot_analysis.json: B_blind 5, C_N 3, U_N 3, P_N 3 (Холм внутри, двусторонне); D_N 2 — описательно. Ворота бюджета: средний
#   выход свёртки ≤ выхода H_1, иначе «бюджет не уравнен» — без теста. Кривая m = 1…5 — описательно.
#   При m = 1 свёртка B/C/U/P совпадает по правилу с H_1 (r = 1 при недопустимом голосе); у D_N — нет (отказ → A0) — возражение Левого 1.
# Н3: гипотеза программы опровергнута, если засчитаны P1 и P2 и S1b не в пользу системы ни для одной руки.
import argparse, collections, json, math, os, statistics as st, sys
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, os.path.join(HERE, '..', '2026-10-07_SELECT-01')); sys.path.insert(0, HERE)
from analyze import EPS, a0, auroc, boot_ci, perm_p, plurality  # noqa: E402
import prompts_think as PT  # noqa: E402
D = os.environ.get('THINK_ROOT', HERE); SECRETS = dict(main='/root/think_secret', rep='/root/think_secret_rep')
FAMILY = (('H_1', 'B_blind', 1), ('H_1', 'D_N', 2)); LOSS_BOUND = 0.02
S1B = dict(B_blind=5, C_N=3, U_N=3, P_N=3); S1B_DESC = dict(D_N=2)
r3 = lambda x: round(float(x), 3)
mean_ci = lambda d: dict(mean=r3(st.mean(d)), ci95=[r3(v) for v in boot_ci(d)], n=len(d))

def holm(ps):
    ps = sorted(ps); m = len(ps)
    return {key: all(pp <= .05 / (m - jj) for jj, (pp, _) in enumerate(ps[:j + 1])) for j, (p, key) in enumerate(ps)}

if __name__ == '__main__':
    ap = argparse.ArgumentParser(); ap.add_argument('evals'); ap.add_argument('--key', required=True); ap.add_argument('--seeds', required=True)
    ap.add_argument('--out'); a = ap.parse_args()
    env = os.environ.get('THINK_SECRET')
    if a.key in SECRETS:
        assert env in (None, SECRETS[a.key]), f'THINK_SECRET={env} не совпадает с выборкой {a.key}'; SEC = SECRETS[a.key]
    else:
        assert env, 'для сухого прогона нужен явный THINK_SECRET'; SEC = env
    rec = {}
    for line in open(a.evals, encoding='utf-8'):
        e = json.loads(line); k_ = (e['task'], e['arm'], int(e['i']))
        if k_ not in rec or (rec[k_].get('error') and not e.get('error')): rec[k_] = e
    expected = [f'WH_{s}' for s in json.load(open(f'{D}/{a.seeds}'))['WH'] if os.path.exists(f'{D}/pools/WH_{s}.json')]
    want = {(arm, i) for arm, n in PT.SPEC.items() for i in range(n)}
    have = collections.defaultdict(set)
    for (t, arm, i) in rec: have[t].add((arm, i))
    complete = [t for t in expected if have[t] >= want]
    lost = collections.Counter(); exp_n = collections.Counter()
    for t in expected:
        for arm, n in PT.SPEC.items():
            for i in range(n):
                e = rec.get((t, arm, i)); bad = e is None or bool(e.get('error'))
                exp_n[arm] += 1; lost[arm] += bad
                if arm == 'H' and i == 0: exp_n['H_1'] += 1; lost['H_1'] += bad
    R = {}; excl = []; toks = collections.defaultdict(collections.Counter); sub_out = collections.defaultdict(list)
    vote_rows = []; calls = collections.defaultdict(list); calib = []; invalid_p = 0; refusal_rows = []
    for t in complete:
        pool = json.load(open(f'{D}/pools/{t}.json')); tr = json.load(open(f'{SEC}/truth/{t}.json')); k = len(pool)
        orc, mean = max(tr), st.mean(tr)
        if orc - mean <= EPS['WH']: excl.append(t); continue
        reg = lambda i: (orc - tr[i]) / (orc - mean) if i is not None else 1.0
        ok = lambda e: isinstance(e.get('choice'), int) and 0 <= e['choice'] < k and not e.get('error')
        i0 = a0(pool, t); R[t] = dict(E=1.0, A0=reg(i0))
        def fold(arm, es):
            good = [e['choice'] for e in es if ok(e)]
            if arm == 'D_N': return reg(plurality(good, t) if good else i0)
            return reg(plurality(good, t)) if good else 1.0
        for arm, n in PT.SPEC.items():
            es = [rec[(t, arm, i)] for i in range(n)]
            for e in es:
                if not e.get('error'):
                    toks[arm].update(dict(inp=e.get('inp', 0), out=e.get('out', 0)))
                    calls[arm].append(dict(out=e.get('out', 0), refused=e.get('choice') == -1, valid=ok(e), reg=reg(e['choice']) if ok(e) else None, t=t))
                if ok(e) and e.get('out'): vote_rows.append((t, arm, reg(e['choice']), e['out']))
            if arm == 'H':
                R[t]['H_1'] = reg(es[0]['choice']) if ok(es[0]) else 1.0; R[t]['H_3'] = fold('H', es)
                toks['H_1'].update(dict(inp=es[0].get('inp', 0), out=es[0].get('out', 0)))
            elif arm == 'H_c':
                R[t]['H_c'] = fold('H_c', es)
                for e in es:
                    pb = e.get('p_best')
                    if ok(e) and isinstance(pb, (int, float)) and 0 <= pb <= 1:
                        calib.append((float(pb), float(orc - tr[e['choice']] <= EPS['WH']), float(tr[e['choice']] == orc)))
                    elif ok(e): invalid_p += 1
            else:
                R[t][arm] = fold(arm, es)
            if arm == 'D_N': refusal_rows.append((any(e.get('choice') == -1 for e in es), t))
            for m in range(1, 6):
                if arm in {**S1B, **S1B_DESC} and m <= n:
                    R[t][f'{arm}[:{m}]'] = fold(arm, es[:m]); sub_out[f'{arm}[:{m}]'].append(sum(e.get('out', 0) for e in es[:m]))
    T = sorted(R); n = len(T)
    ptok = {arm: {kk: v / max(1, n) for kk, v in c.items()} for arm, c in toks.items()}
    out = dict(n_expected=len(expected), n_complete=len(complete), incomplete=sorted(set(expected) - set(complete)), excluded_eps=excl, n_tasks=n,
               mean_regret={x: dict(mean=r3(st.mean(R[t][x] for t in T)), median=r3(st.median(R[t][x] for t in T)))
                            for x in ('E', 'A0', 'B_blind', 'C_N', 'D_N', 'U_N', 'P_N', 'H_1', 'H_3', 'H_c')},
               tokens_per_task={arm: {kk: round(v) for kk, v in c.items()} for arm, c in ptok.items()},
               lost_share={arm: r3(lost[arm] / exp_n[arm]) for arm in exp_n}, primary={}, secondary={})
    for x, y, seed in FAMILY:
        d = [R[t][x] - R[t][y] for t in T]; p, how = perm_p(d, seed=seed)
        out['primary'][f'{x} − {y}'] = dict(**mean_ci(d), p=p, method=how, p_reverse_descriptive=perm_p([-v for v in d], seed=seed + 100)[0],
                                            budget_ok=bool(ptok['H_1'].get('out', 0) <= ptok[y].get('out', 0)),
                                            out_H_1=round(ptok['H_1'].get('out', 0)), out_rival=round(ptok[y].get('out', 0)),
                                            not_measured=bool(lost['H_1'] / exp_n['H_1'] > LOSS_BOUND or lost[y] / exp_n[y] > LOSS_BOUND),
                                            wins_losses_ties=[sum(v < 0 for v in d), sum(v > 0 for v in d), sum(v == 0 for v in d)])
    for key, rej in holm([(q['p'], k_) for k_, q in out['primary'].items()]).items():
        q = out['primary'][key]; q['holm_reject'] = rej; q['counts'] = bool(rej and q['budget_ok'] and not q['not_measured'])
    s1b = {}; tested = []
    h1_out = ptok['H_1'].get('out', 0)
    for j, (arm, m) in enumerate(list(S1B.items()) + list(S1B_DESC.items())):
        key = f'{arm}[:{m}]'; d = [R[t]['H_1'] - R[t][key] for t in T]; so = st.mean(sub_out[key])
        q = dict(**mean_ci(d), m=m, out_subset=round(so), out_H_1=round(h1_out), budget_matched=bool(so <= h1_out), descriptive=arm in S1B_DESC)
        p_lo = perm_p(d, seed=11 + j)[0]; p_hi = perm_p([-v for v in d], seed=21 + j)[0]; q.update(p_H1_better=p_lo, p_system_better=p_hi, p_two=min(1.0, 2 * min(p_lo, p_hi)))
        if q['budget_matched'] and not q['descriptive']: tested.append((q['p_two'], key))
        s1b[key] = q
    hr = holm(tested)
    for key, q in s1b.items():
        if key in hr:
            q['holm_reject'] = hr[key]
            q['outcome'] = ('система лучше: подтверждение' if q['mean'] > 0 else 'H_1 лучше: опровержение') if hr[key] else 'не различимо'
        else:
            q['outcome'] = 'описательно' if q['descriptive'] else 'бюджет не уравнен: без теста'
    s1b['curve_m_1_5'] = {k_: dict(mean_regret=r3(st.mean(R[t][k_] for t in T)), out=round(st.mean(sub_out[k_]))) for k_ in sorted(sub_out)}
    out['secondary']['S1b_equal_budget_system'] = s1b
    p1, p2 = out['primary']['H_1 − B_blind']['counts'], out['primary']['H_1 − D_N']['counts']
    sys_better = any(q.get('outcome', '').startswith('система лучше') for q in s1b.values() if isinstance(q, dict))
    out['program_hypothesis'] = ('S1b в пользу системы' if sys_better else
                                 'опровергнута (Н3: P1 и P2 засчитаны, S1b не в пользу системы)' if p1 and p2 else 'не решено')
    out['secondary']['S1_system_of_deep_heads'] = {f'{x} − {y}': mean_ci([R[t][x] - R[t][y] for t in T])
                                                   for x, y in (('H_3', 'H_1'), ('H_3', 'B_blind'), ('H_3', 'D_N'), ('H_1', 'C_N'))}
    out['secondary']['S5_select01_replication'] = {f'{x} − {y}': dict(**mean_ci([R[t][x] - R[t][y] for t in T]), p=perm_p([R[t][x] - R[t][y] for t in T], seed=s)[0])
                                                   for (x, y), s in zip((('D_N', 'B_blind'), ('D_N', 'C_N'), ('D_N', 'A0')), (31, 32, 33))}
    per_arm = {}
    for arm, cs in sorted(calls.items()):
        v = [c for c in cs if c['valid']]
        per_arm[arm] = dict(mean_out_all=round(st.mean(c['out'] for c in cs)), mean_out_nonrefusal=round(st.mean(c['out'] for c in v)) if v else None,
                            refusal_share=r3(st.mean(c['refused'] for c in cs)), mean_vote_regret_valid=r3(st.mean(c['reg'] for c in v)) if v else None, calls=len(cs))
    mech = dict(per_arm=per_arm, note='P4: per_arm.<рука>.mean_out_all (все несбойные вызовы, отказы включены); модель — только неотказавшие голоса',
                plurality_vs_C_N={f'{x} − C_N': mean_ci([R[t][x] - R[t]['C_N'] for t in T]) for x in ('D_N', 'U_N', 'P_N')})
    blocks = []
    for t in T:
        rows = [(r_, math.log(o), float(arm == 'D_N'), float(arm == 'U_N'), float(arm == 'P_N')) for tt, arm, r_, o in vote_rows if tt == t and arm in ('C_N', 'D_N', 'U_N', 'P_N')]
        if len(rows) > 4:
            M = np.array(rows); blocks.append(M - M.mean(axis=0))
    if blocks:
        fit = lambda bl: np.linalg.lstsq(np.vstack(bl)[:, 1:], np.vstack(bl)[:, 0], rcond=None)[0]
        b = fit(blocks); rng = np.random.default_rng(15102026)
        bs = np.array([fit([blocks[i] for i in rng.integers(0, len(blocks), len(blocks))]) for _ in range(2000)])
        mech['equal_length_model'] = {nm: dict(coef=r3(b[j]), ci95=[r3(np.percentile(bs[:, j], 2.5)), r3(np.percentile(bs[:, j], 97.5))])
                                      for j, nm in enumerate(['ln_out', 'D_N', 'U_N', 'P_N'])}
    out['secondary']['S2_mechanism'] = mech
    if calib:
        p_, cl, cs_ = (np.array([x[j] for x in calib]) for j in range(3)); bins = np.minimum((p_ * 5).astype(int), 4)
        ece = sum(abs(p_[bins == j].mean() - cl[bins == j].mean()) * (bins == j).sum() for j in range(5) if (bins == j).any()) / len(p_)
        out['secondary']['S3_self_assessment'] = dict(n=len(calib), invalid_p_best=invalid_p, mean_p_best=r3(p_.mean()),
            accuracy_lenient=r3(cl.mean()), accuracy_strict=r3(cs_.mean()), brier=r3(((p_ - cl) ** 2).mean()), brier_constant_rate=r3(((cl.mean() - cl) ** 2).mean()),
            ece_5bins=r3(ece), auroc_p_best_correct=r3(auroc(list(p_), list(cl > .5))), H_c_minus_H_1=mean_ci([R[t]['H_c'] - R[t]['H_1'] for t in T]),
            note='точность (P6) — регрет выбора ≤ EPS в абсолютных единицах, любой из лучших (совет 34, Н10); strict — ровно лучший')
    diff = {t: st.mean(r_ for tt, arm, r_, _ in vote_rows if tt == t and arm == 'C_N') for t in T if any(tt == t and arm == 'C_N' for tt, arm, *_ in vote_rows)}
    ref = [(f, t) for f, t in refusal_rows if t in diff]; nref = sum(f for f, _ in ref)
    out['secondary']['S4_refusal_informativeness'] = dict(tasks_with_refusal=nref, measured=bool(5 <= nref <= len(ref) - 5),
        auroc_refusal_vs_C_N_difficulty=r3(auroc([diff[t] for _, t in ref], [f for f, _ in ref])) if 5 <= nref <= len(ref) - 5 else None,
        note='ничьи в AUROC — половина (analyze.auroc)')
    out['per_task'] = {t: {k_: r3(v) for k_, v in R[t].items()} for t in T}
    print(json.dumps({k_: v for k_, v in out.items() if k_ != 'per_task'}, ensure_ascii=False, indent=1))
    if a.out: json.dump(out, open(a.out, 'w'), ensure_ascii=False, indent=1)
