# THINK-01: анализ. Регрет, ничьи, большинство, A0, перестановочный тест и бутстреп — функции analyze.py SELECT-01 (sha256 06f4f5f8…).
#   python3 analyze_think.py <evals/stage.complete.jsonl> [--out json]   (правда — THINK_SECRET/truth, пулы — THINK_ROOT/pools)
# Руки (prompts_think.SPEC): B_blind ×12, C_N ×5, D_N ×5, U_N ×5, P_N ×5 — effort medium, большинство (у D_N среди неотказавшихся,
# все отказались → A0); H ×3 — ROLE на effort high: H_1 = вызов i = 0, H_3 = большинство трёх; H_c — ROLE_CONF на high, один вызов.
# Голос недействителен (сбой, номер вне 0..k−1) → не считается; нет ни одного допустимого голоса → r = 1 (у D_N → A0).
# Первичное семейство (Холм, α = 0,05, односторонне — у H_1 регрет меньше): H_1 − B_blind, H_1 − D_N.
# Засчитано = Холм отвергает + бюджет H_1 (вход+выход и выход, среднее на задачу) не больше, чем у соперника
#             + доля «потерян» (error) у вызовов i = 0 руки H и у соперника не больше 0,02 (иначе «не измерено»).
import argparse, collections, json, math, os, statistics as st, sys
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, os.path.join(HERE, '..', '2026-10-07_SELECT-01'))
from analyze import EPS, a0, auroc, boot_ci, perm_p, plurality, tiebreak  # noqa: E402,F401
D = os.environ.get('THINK_ROOT', HERE); SEC = os.environ.get('THINK_SECRET', '/root/think_secret')
FAMILY = (('H_1', 'B_blind'), ('H_1', 'D_N')); LOSS_BOUND = 0.02
r3 = lambda x: round(float(x), 3)
mean_ci = lambda d: dict(mean=r3(st.mean(d)), ci95=[r3(v) for v in boot_ci(d)], n=len(d))

if __name__ == '__main__':
    ap = argparse.ArgumentParser(); ap.add_argument('evals'); ap.add_argument('--out'); a = ap.parse_args()
    rec = {}
    for line in open(a.evals, encoding='utf-8'):
        e = json.loads(line); rec[(e['task'], e['arm'], int(e['i']))] = e          # дубли — последняя запись
    V = collections.defaultdict(list)
    for (t, arm, i), e in sorted(rec.items()): V[(t, arm)].append(e)
    tasks = sorted({t for t, _ in V}); R = {}; excl = []; lost = collections.Counter(); votes_n = collections.Counter()
    toks = collections.defaultdict(lambda: collections.Counter()); vote_rows = []; calib = []; refusal_rows = []
    for t in tasks:
        pool = json.load(open(f'{D}/pools/{t}.json')); tr = json.load(open(f'{SEC}/truth/{t}.json')); k = len(pool)
        orc, mean = max(tr), st.mean(tr)
        if orc - mean <= EPS['WH']: excl.append(t); continue
        reg = lambda i: (orc - tr[i]) / (orc - mean) if i is not None else 1.0
        ok = lambda e: isinstance(e.get('choice'), int) and 0 <= e['choice'] < k
        i0 = a0(pool, t); R[t] = dict(E=1.0, A0=reg(i0))
        for arm in ('B_blind', 'C_N', 'D_N', 'U_N', 'P_N', 'H', 'H_c'):
            es = V[(t, arm)]
            for e in es:
                votes_n[arm] += 1; lost[arm] += bool(e.get('error')); toks[arm].update(dict(inp=e.get('inp', 0), out=e.get('out', 0)))
                if ok(e) and e.get('out'): vote_rows.append((t, arm, reg(e['choice']), e['out']))
            good = [e['choice'] for e in es if ok(e)]
            if arm == 'D_N':
                R[t]['D_N'] = reg(plurality(good, t) if good else i0)
                refusal_rows.append((any(e.get('choice') == -1 for e in es), t))
            elif arm == 'H':
                h0 = [e for e in es if e['i'] == 0]
                R[t]['H_1'] = reg(h0[0]['choice']) if h0 and ok(h0[0]) else 1.0
                R[t]['H_3'] = reg(plurality(good, t)) if good else 1.0
                if h0:
                    toks['H_1'].update(dict(inp=h0[0].get('inp', 0), out=h0[0].get('out', 0))); votes_n['H_1'] += 1; lost['H_1'] += bool(h0[0].get('error'))
            elif arm == 'H_c':
                R[t]['H_c'] = reg(good[0]) if good else 1.0
                for e in es:
                    if ok(e) and isinstance(e.get('p_best'), (int, float)):
                        calib.append((min(1.0, max(0.0, float(e['p_best']))), float(tr[e['choice']] == orc), reg(e['choice'])))
            else:
                R[t][arm] = reg(plurality(good, t)) if good else 1.0
    T = sorted(R); n = len(T)
    per_task_tok = {arm: {kk: v / n for kk, v in c.items()} for arm, c in toks.items()}
    out = dict(n_tasks=n, excluded=excl, mean_regret={x: dict(mean=r3(st.mean(R[t][x] for t in T)), median=r3(st.median(R[t][x] for t in T)))
                                                  for x in ('E', 'A0', 'B_blind', 'C_N', 'D_N', 'U_N', 'P_N', 'H_1', 'H_3', 'H_c')},
               tokens_per_task={arm: {kk: round(v) for kk, v in c.items()} for arm, c in per_task_tok.items()},
               lost_share={arm: r3(lost[arm] / votes_n[arm]) for arm in votes_n}, primary={}, secondary={})
    tot = lambda arm: per_task_tok[arm].get('inp', 0) + per_task_tok[arm].get('out', 0)
    ps = []
    for x, y in FAMILY:
        d = [R[t][x] - R[t][y] for t in T]; p, how = perm_p(d)
        arm_y = y if y != 'H_1' else 'H'
        budget = bool(tot('H_1') <= tot(arm_y) and per_task_tok['H_1'].get('out', 0) <= per_task_tok[arm_y].get('out', 0))
        nm = bool(lost['H_1'] / max(1, votes_n['H_1']) > LOSS_BOUND or lost[arm_y] / max(1, votes_n[arm_y]) > LOSS_BOUND)
        out['primary'][f'{x} − {y}'] = dict(**mean_ci(d), p=p, method=how, budget_ok=budget, not_measured=nm,
                                            wins_losses_ties=[sum(v < 0 for v in d), sum(v > 0 for v in d), sum(v == 0 for v in d)])
        ps.append((p, f'{x} − {y}'))
    ps.sort(); m = len(ps)
    for j, (p, key) in enumerate(ps):
        rej = all(pp <= .05 / (m - jj) for jj, (pp, _) in enumerate(ps[:j + 1]))
        q = out['primary'][key]; q['holm_reject'] = rej; q['counts'] = bool(rej and q['budget_ok'] and not q['not_measured'])
    sec = out['secondary']
    sec['S1_system_of_deep_heads'] = {f'{x} − {y}': mean_ci([R[t][x] - R[t][y] for t in T])
                                      for x, y in (('H_3', 'H_1'), ('H_3', 'B_blind'), ('H_3', 'D_N'), ('H_1', 'C_N'))}
    sec['S5_select01_replication'] = {f'{x} − {y}': dict(**mean_ci([R[t][x] - R[t][y] for t in T]), p=perm_p([R[t][x] - R[t][y] for t in T])[0])
                                      for x, y in (('D_N', 'B_blind'), ('D_N', 'C_N'), ('D_N', 'A0'))}
    by_arm = collections.defaultdict(list)
    for t, arm, r_, o in vote_rows: by_arm[arm].append((r_, o))
    mech = dict(per_vote={arm: dict(mean_regret=r3(st.mean(r_ for r_, _ in v)), mean_out=round(st.mean(o for _, o in v)), n=len(v))
                          for arm, v in sorted(by_arm.items())},
                plurality_vs_C_N={f'{x} − C_N': mean_ci([R[t][x] - R[t]['C_N'] for t in T]) for x in ('D_N', 'U_N', 'P_N')})
    blocks = []                                         # регрет ~ [D_N] + [U_N] + [P_N] + ln(out), отклонения от средних задачи; база — C_N
    for t in T:
        rows = [(r_, math.log(o), float(arm == 'D_N'), float(arm == 'U_N'), float(arm == 'P_N'))
                for tt, arm, r_, o in vote_rows if tt == t and arm in ('C_N', 'D_N', 'U_N', 'P_N')]
        if len(rows) > 4:
            M = np.array(rows); blocks.append(M - M.mean(axis=0))
    fit = lambda bl: np.linalg.lstsq(np.vstack(bl)[:, 1:], np.vstack(bl)[:, 0], rcond=None)[0]
    b = fit(blocks); rng = np.random.default_rng(15102026)
    bs = np.array([fit([blocks[i] for i in rng.integers(0, len(blocks), len(blocks))]) for _ in range(2000)])
    names = ['ln_out', 'D_N', 'U_N', 'P_N']
    mech['equal_length_model'] = {nm: dict(coef=r3(b[j]), ci95=[r3(np.percentile(bs[:, j], 2.5)), r3(np.percentile(bs[:, j], 97.5))])
                                  for j, nm in enumerate(names)}
    sec['S2_mechanism'] = mech
    if calib:
        p_, c_ = np.array([x[0] for x in calib]), np.array([x[1] for x in calib]); bins = np.minimum((p_ * 5).astype(int), 4)
        ece = sum(abs(p_[bins == j].mean() - c_[bins == j].mean()) * (bins == j).sum() for j in range(5) if (bins == j).any()) / len(p_)
        sec['S3_self_assessment'] = dict(n=len(calib), mean_p_best=r3(p_.mean()), accuracy=r3(c_.mean()), brier=r3(((p_ - c_) ** 2).mean()),
                                         brier_constant_rate=r3(((c_.mean() - c_) ** 2).mean()), ece_5bins=r3(ece),
                                         auroc_p_best_correct=r3(auroc(list(p_), list(c_ > .5))),
                                         H_c_minus_H_1=mean_ci([R[t]['H_c'] - R[t]['H_1'] for t in T]))
    diff = {t: st.mean(r_ for tt, arm, r_, _ in vote_rows if tt == t and arm == 'C_N') for t in T if any(tt == t and arm == 'C_N' for tt, arm, *_ in vote_rows)}
    ref = [(f, t) for f, t in refusal_rows if t in diff]
    sec['S4_refusal_informativeness'] = dict(tasks_with_refusal=sum(f for f, _ in ref),
                                             auroc_refusal_vs_C_N_difficulty=r3(auroc([diff[t] for _, t in ref], [f for f, _ in ref])))
    out['per_task'] = {t: {k_: r3(v) for k_, v in R[t].items()} for t in T}
    print(json.dumps({k_: v for k_, v in out.items() if k_ != 'per_task'}, ensure_ascii=False, indent=1))
    if a.out: json.dump(out, open(a.out, 'w'), ensure_ascii=False, indent=1)
