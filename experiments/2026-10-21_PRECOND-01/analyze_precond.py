# PRECOND-01: анализ основного опыта (вариант A, совет 37; правила — PREREG-PRECOND-01.md).
#   python3 analyze_precond.py open evals/open.jsonl --out open_an.json   — открытие: вопросы 1–2, потолок, победители → winners.json
#   python3 analyze_precond.py val  evals/val.jsonl  --out val_an.json    — проверка победителя: первичный парный тест, сжатие
# Регрет голоса — нормированный, как в SELECT-01: (лучший − выбранный) / (лучший − средний по восьми). Отказ (choice = −1) → регрет
# выбора по заявке A0; сбой, пропуск и недопустимый номер → 1. Задача исключается, если лучший − средний ≤ EPS (150), как в THINK-01.
# Перестановки — внутри задач, Freedman–Lane для отдельных действий; ДИ — t по контрастам задач (df = задач − 1). Зерно и B — ниже.
import argparse, collections, json, math, os, statistics as st, sys
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); SEL = os.path.join(HERE, '..', '2026-10-07_SELECT-01')
sys.path.insert(0, SEL); sys.path.insert(0, HERE)
import harness_precond as HP, prompts_precond as PP  # noqa: E402
from analyze import EPS, a0  # noqa: E402
SEED, B = 27102026, 20000
CELLS = list(HP.CELLS); X = np.array([[1 if f in HP.CELLS[c] else -1 for f in PP.F] for c in CELLS], dtype=float)   # 64 × 8, ±1
ALLON = next(c for c in CELLS if sorted(HP.CELLS[c]) == sorted(PP.F)); ANCH = next(c for c in CELLS if sorted(HP.CELLS[c]) == sorted(HP.ANCHOR))
r3 = lambda x: None if x is None else round(float(x), 3)

# ---------- t-распределение без scipy: регуляризованная неполная бета (Numerical Recipes), обращение бисекцией ----------
def _betacf(a, b, x):
    qab, qap, qam, c, d = a + b, a + 1, a - 1, 1.0, 1 - (a + b) * x / (a + 1)
    d = 1 / (d if abs(d) > 1e-30 else 1e-30); h = d
    for m in range(1, 300):
        m2 = 2 * m; aa = m * (b - m) * x / ((qam + m2) * (a + m2))
        d = 1 + aa * d; d = 1 / (d if abs(d) > 1e-30 else 1e-30); c = 1 + aa / c if abs(1 + aa / c) > 1e-30 else 1e-30; h *= d * c
        aa = -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))
        d = 1 + aa * d; d = 1 / (d if abs(d) > 1e-30 else 1e-30); c = 1 + aa / c if abs(1 + aa / c) > 1e-30 else 1e-30; de = d * c; h *= de
        if abs(de - 1) < 1e-12: break
    return h
def _betai(a, b, x):
    if x <= 0 or x >= 1: return 0.0 if x <= 0 else 1.0
    bt = math.exp(math.lgamma(a + b) - math.lgamma(a) - math.lgamma(b) + a * math.log(x) + b * math.log(1 - x))
    return bt * _betacf(a, b, x) / a if x < (a + 1) / (a + b + 2) else 1 - bt * _betacf(b, a, 1 - x) / b
def t_cdf(t, df): p = 0.5 * _betai(df / 2, 0.5, df / (df + t * t)); return 1 - p if t > 0 else p
def t_ppf(q, df):
    lo, hi = -50.0, 50.0
    for _ in range(200):
        mid = (lo + hi) / 2
        if t_cdf(mid, df) < q: lo = mid
        else: hi = mid
    return (lo + hi) / 2
def t_ci(v):
    """Среднее и 95 % t-ДИ по задачам; p двусторонний и односторонний (среднее > 0)."""
    n = len(v); m = st.mean(v); s = st.stdev(v) if n > 1 else 0.0; se = s / math.sqrt(n) if n else float('nan'); q = t_ppf(0.975, n - 1)
    tt = m / se if se > 0 else float('inf') * (1 if m > 0 else -1 if m < 0 else 0)
    return dict(mean=r3(m), ci95=[r3(m - q * se), r3(m + q * se)], df=n - 1, p_two=r3(2 * (1 - t_cdf(abs(tt), n - 1))) if se > 0 else None,
                p_greater=round(1 - t_cdf(tt, n - 1), 6) if se > 0 else None, n=n)

def holm(ps):
    o = sorted(ps, key=lambda kv: kv[1]); m = len(o); rej, stop = {}, False
    for i, (k, p) in enumerate(o):
        stop = stop or p > 0.05 / (m - i); rej[k] = not stop
    return rej

# ---------- регреты ----------
def load(stage, evals):
    sec = HP.sec_for(stage); R, OUT, REF, PB, excl = {}, {}, {}, {}, []; STA, A0R = {}, {}
    rec = {}
    for e in map(json.loads, open(evals, encoding='utf-8')):
        k = (e['task'], e['arm'], int(e['i']))
        if k not in rec or (rec[k].get('error') and not e.get('error')): rec[k] = e
    for t in HP.tids(stage):
        p = f'{sec}/truth/{t}.json'
        if not os.path.exists(p): continue
        tr = json.load(open(p)); orc, mean = max(tr), st.mean(tr)
        if orc - mean <= EPS['WH']: excl.append(t); continue
        reg = lambda i: (orc - tr[i]) / (orc - mean); A0R[t] = reg(a0(HP.pool(t), t))      # Т7: опорная рука A0 без вызовов
        for (tt, a, i), e in rec.items():
            if tt != t: continue
            c = e['choice']; refused = c == -1; valid = isinstance(c, int) and 0 <= c < len(tr)
            R[(t, a, i)] = reg(c) if valid else (reg(a0(HP.pool(t), t)) if refused else 1.0)
            OUT[(t, a, i)] = e.get('out') or 0; REF[(t, a, i)] = refused
            STA[(t, a, i)] = 'ok' if valid else 'refused' if refused else 'error' if e.get('error') else 'invalid'   # К5
            if e.get('p_best') is not None and valid: PB[(t, a, i)] = (float(e['p_best']), float(tr[c] == orc))
    load.STA, load.A0R = STA, A0R
    return R, OUT, REF, PB, excl

def fl_p(Y, x, Xred, rng):
    """Freedman–Lane внутри задач: остатки сокращённой модели (Xred) переставляются в каждой задаче; статистика — Σ y·x / N."""
    T, K = Y.shape; N = T * K
    beta_red = (Y.reshape(-1) @ np.tile(Xred, (T, 1))) / N if Xred.shape[1] else np.zeros(0)   # столбцы ортогональны внутри задачи
    E = Y - (Xred @ beta_red if Xred.shape[1] else 0)
    obs = float((Y * x).sum() / N)
    stat = np.zeros(B)
    for t in range(T):
        P = rng.permuted(np.tile(np.arange(K), (B, 1)), axis=1)
        stat += E[t][P] @ x
    stat /= N; cnt = int((np.abs(stat) >= abs(obs) - 1e-12).sum())
    return obs, (cnt + 1) / (B + 1)

def open_stage(evals, key='open'):
    R, OUT, REF, PB, excl = load(key, evals)
    kids = np.random.SeedSequence(SEED).spawn(10)          # совет 38, К4: поток на тест — Q1, FL по восьми ингредиентам, REFUSE × CLAIMS
    rng_q1, rng_fl, rng_int = np.random.default_rng(kids[0]), [np.random.default_rng(k) for k in kids[1:9]], np.random.default_rng(kids[9])
    T = sorted({t for (t, a, i) in R}); out = dict(n_tasks=len(T), excluded_eps=excl, tasks=T, seed=SEED, permutations=B)
    get = lambda t, a: R.get((t, a, 0), 1.0)                                  # нет голоса — сбой → 1 (правило выше)
    Yraw = np.array([[get(t, c) for c in CELLS] for t in T]); Y = Yraw - Yraw.mean(axis=1, keepdims=True)
    N = Y.size
    # вопрос 1: разброс средних 64 сочетаний внутри задач (перестановка меток внутри задачи — точный нуль «ничто не действует»)
    S = float(((Y.mean(axis=0)) ** 2).sum())
    Pall = [rng_q1.permuted(np.tile(np.arange(len(CELLS)), (B, 1)), axis=1) for _ in T]
    Ss = (np.stack([Y[ti][Pall[ti]] for ti in range(len(T))]).mean(axis=0) ** 2).sum(axis=1)
    out['Q1'] = dict(stat=r3(S), p=round(float(((Ss >= S - 1e-12).sum() + 1) / (B + 1)), 6))
    # вопрос 2: главные действия (вкл − выкл = 2β), Freedman–Lane, Холм по восьми, t-ДИ по задачам
    eff, ps, raw = {}, [], {}
    for j, f in enumerate(PP.F):
        b, p = fl_p(Y, X[:, j], np.delete(X, j, axis=1), rng_fl[j]); raw[f] = 2 * b    # К2: решения — по неокруглённым
        per_task = [float(Yraw[ti][X[:, j] > 0].mean() - Yraw[ti][X[:, j] < 0].mean()) for ti in range(len(T))]
        eff[f] = dict(effect=r3(2 * b), effect_raw=float(2 * b), p_fl=round(p, 6), t=t_ci(per_task),   # effect_raw — для E2 (совет 38, Т2)
                      out=r3(np.mean([OUT.get((t, c, 0), 0) for t in T for c in CELLS if f in HP.CELLS[c]]) -
                             np.mean([OUT.get((t, c, 0), 0) for t in T for c in CELLS if f not in HP.CELLS[c]])),
                      refusal_on=r3(np.mean([REF.get((t, c, 0), False) for t in T for c in CELLS if f in HP.CELLS[c]])))
        ps.append((f, p))
    for f, rej in holm(ps).items(): eff[f]['holm_reject'] = rej
    out['main_effects'] = eff
    # REFUSE × CLAIMS — один заранее названный тест (сокращённая модель — восемь главных действий); прочие пары — описательно
    pair = lambda f, g: X[:, PP.F.index(f)] * X[:, PP.F.index(g)]
    b, p = fl_p(Y, pair('REFUSE', 'CLAIMS'), X, rng_int)
    out['REFUSE_x_CLAIMS'] = dict(effect=r3(2 * b), p_fl=round(p, 6),
                                  t=t_ci([float(Yraw[ti][pair('REFUSE', 'CLAIMS') > 0].mean() - Yraw[ti][pair('REFUSE', 'CLAIMS') < 0].mean()) for ti in range(len(T))]))
    out['pairs_descriptive'] = {f'{f}×{g}': r3(2 * (Y * pair(f, g)).sum() / N) for a_, f in enumerate(PP.F) for g in PP.F[a_ + 1:]}
    # посредник ln(выход) — описательно, не ковариата первичной проверки (совет 35)
    L = np.array([[math.log(max(OUT.get((t, c, 0), 1), 1)) for c in CELLS] for t in T]); L = L - L.mean(axis=1, keepdims=True)
    Z = np.column_stack([np.tile(X, (len(T), 1)), L.reshape(-1)]); coef = np.linalg.lstsq(Z, Y.reshape(-1), rcond=None)[0]
    out['mediator_descriptive'] = dict({f: r3(2 * coef[j]) for j, f in enumerate(PP.F)}, ln_out=r3(coef[-1]))
    # насыщение — описательно: регрет ~ k + k² внутри задач; насыщение (убывающая польза) ⇔ коэффициент при k² > 0
    k = np.array([len(HP.CELLS[c]) for c in CELLS], dtype=float); kc = k - k.mean(); k2 = kc ** 2 - (kc ** 2).mean()
    q2 = [float(np.linalg.lstsq(np.column_stack([kc, k2]), Y[ti], rcond=None)[0][1]) for ti in range(len(T))]
    out['saturation_descriptive'] = dict(k2=t_ci(q2), saturation=bool(st.mean(q2) > 0))
    # потолок (совет 37): D — «всё выключено» минус «всё включено» на своём уровне; d = D_h − 0,5·D_m; опровергнут, если среднее d ≥ 0
    Dm = [get(t, 'M0') - get(t, ALLON) for t in T]; Dh = [get(t, 'H0') - get(t, 'H1') for t in T]; d = [h - 0.5 * m for h, m in zip(Dh, Dm)]
    h1 = st.mean(get(t, 'H1') for t in T)
    out['ceiling'] = dict(D_m=t_ci(Dm), D_h=t_ci(Dh), d=t_ci(d), H1_mean=r3(h1), H0_mean=r3(st.mean(get(t, 'H0') for t in T)),
                          M0_mean=r3(st.mean(get(t, 'M0') for t in T)), allon_medium_mean=r3(st.mean(get(t, ALLON) for t in T)),
                          outcome='гипотеза потолка опровергнута' if st.mean(d) >= 0 else 'гипотеза потолка не опровергнута',
                          secondary='опровергнута по дополнительному критерию' if h1 >= 0.1 else 'не опровергнута по дополнительному критерию')
    # победители — только на этом этапе; правила записаны в PREREG
    means = {c: float(Yraw[:, ci].mean()) for ci, c in enumerate(CELLS)}
    obs_cell = min(CELLS, key=lambda c: (means[c], CELLS.index(c)))
    model = [f for f in PP.F if raw[f] < 0]
    model_cell = next((c for c in CELLS if sorted(HP.CELLS[c]) == sorted(model)), None)
    pred = lambda on: float(sum((raw[f] / 2) * (1 if f in on else -1) for f in PP.F))   # регрет относительно среднего по плану
    arms = dict(OBS=HP.CELLS[obs_cell], MODEL=model, ANCHOR=HP.ANCHOR)
    same = dict(model_eq_obs=sorted(model) == sorted(HP.CELLS[obs_cell]), obs_eq_anchor=obs_cell == ANCH, model_eq_anchor=sorted(model) == sorted(HP.ANCHOR))
    gain_open = dict(OBS=means[ANCH] - means[obs_cell],                                 # неокруглённые (К2); MODEL вне плана — по прогнозу (Т6)
                     MODEL=means[ANCH] - means[model_cell] if model_cell else pred(HP.ANCHOR) - pred(model))
    # описательно: перестановочный нуль инфляции отбора — выигрыш лучшего из 64 над опорой при перемешанных метках внутри задач
    g_obs = means[ANCH] - means[obs_cell]
    Mp = np.stack([Yraw[ti][Pall[ti]] for ti in range(len(T))]).mean(axis=0)          # B × 64
    a_i = CELLS.index(ANCH); g_null = Mp[:, a_i] - Mp.min(axis=1)
    out['winners'] = dict(arms=arms, obs_cell=obs_cell, model_cell=model_cell, coincide=same, gain_open={k: r3(v) for k, v in gain_open.items()},
                          gain_open_raw=gain_open, gain_open_model_from='наблюдение' if model_cell else 'прогноз модели главных действий (только описательно)',
                          selection_null_p=round(float(((g_null >= g_obs - 1e-12).sum() + 1) / (B + 1)), 6), cell_means={c: r3(v) for c, v in means.items()})
    # самооценка в клетках с CONF — описательно (средняя p_best и доля ровно лучших)
    pb = [v for (t, a, i), v in PB.items() if a in CELLS]
    out['conf_descriptive'] = dict(n=len(pb), mean_p=r3(st.mean(p for p, h in pb)) if pb else None, hit=r3(st.mean(h for p, h in pb)) if pb else None)
    out['mean_regret'] = dict(all64=r3(Yraw.mean()), anchor=r3(means[ANCH]), allon_medium=r3(means[ALLON]), A0_no_calls=r3(st.mean(load.A0R[t] for t in T)))
    # К5: пропуски и сбои по рукам (пропущенный голос тоже даёт регрет 1, но считается отдельно)
    arms_all = CELLS + list(HP.EXTRA); status = {}
    for a_ in arms_all:
        c_ = collections.Counter(load.STA.get((t, a_, 0), 'missing') for t in T); status[a_] = dict(c_)
    out['vote_status_totals'] = dict(sum((collections.Counter(v) for v in status.values()), collections.Counter()))
    out['vote_status_nonok'] = {a_: v for a_, v in status.items() if set(v) - {'ok', 'refused'}}
    # Т7: разложение действия отказа (описательно): доля отказов × (регрет A0 − регрет ответивших) в клетках с REFUSE
    on_ref = [(t, c) for t in T for c in CELLS if 'REFUSE' in HP.CELLS[c]]
    refd = [(t, c) for t, c in on_ref if load.STA.get((t, c, 0)) == 'refused']; ans = [(t, c) for t, c in on_ref if load.STA.get((t, c, 0)) == 'ok']
    share = len(refd) / len(on_ref) if on_ref else 0.0
    out['refusal_decomposition'] = dict(share=r3(share), A0_regret_refused=r3(st.mean(load.A0R[t] for t, c in refd)) if refd else None,
        answered_regret=r3(st.mean(R[(t, c, 0)] for t, c in ans)) if ans else None,
        contribution=r3(share * (st.mean(load.A0R[t] for t, c in refd) - st.mean(R[(t, c, 0)] for t, c in ans))) if refd and ans else None)
    out['out_per_call'] = dict(medium64=r3(np.mean([OUT.get((t, c, 0), 0) for t in T for c in CELLS])),
                               high=r3(np.mean([OUT.get((t, a, 0), 0) for t in T for a in ('H0', 'H1')])))
    w = dict(arms={}, aliases={})
    for a, on in arms.items():                                                  # совпавшие наборы не дублируются: один голос — одна рука
        dup = next((b_ for b_, o in w['arms'].items() if sorted(o) == sorted(on)), None)
        if dup: w['aliases'][a] = dup
        else: w['arms'][a] = on
    return out, w

def val_stage(evals, open_an, key='val'):
    R, OUT, REF, PB, excl = load(key, evals); W = json.load(open(f'{HP.D}/winners.json')); al = W.get('aliases', {})
    arm = lambda a: al.get(a, a)
    T = sorted({t for (t, a, i) in R}); out = dict(n_tasks=len(T), excluded_eps=excl, aliases=al)
    m = lambda t, a: st.mean(R.get((t, arm(a), i), 1.0) for i in range(HP.VOTES_VAL))
    per = {a: [m(t, a) for t in T] for a in ('OBS', 'MODEL', 'ANCHOR')}
    out['mean_regret'] = {a: r3(st.mean(v)) for a, v in per.items()}
    if arm('OBS') == arm('MODEL'):
        out['primary'] = dict(outcome='не проверено: победители совпали')
    else:
        r = t_ci([o - mo for o, mo in zip(per['OBS'], per['MODEL'])])            # > 0 — модель лучше
        out['primary'] = dict(diff_obs_minus_model=r, outcome='модель лучше' if r['p_greater'] is not None and r['p_greater'] < 0.05 else 'не показано')
    gv = {a: st.mean(per['ANCHOR']) - st.mean(per[a]) for a in ('OBS', 'MODEL')}
    go = open_an['winners']['gain_open_raw']
    out['gain_val'] = {a: r3(v) for a, v in gv.items()}
    out['shrinkage'] = {a: (r3(1 - gv[a] / go[a]) if go[a] is not None and go[a] > 0 else 'не определено: выигрыш на открытии ≤ 0') for a in ('OBS', 'MODEL')}
    out['vs_anchor'] = {a: t_ci([an - x for an, x in zip(per['ANCHOR'], per[a])]) for a in ('OBS', 'MODEL')}
    out['out_per_call'] = {a: r3(st.mean(OUT.get((t, arm(a), i), 0) for t in T for i in range(HP.VOTES_VAL))) for a in ('OBS', 'MODEL', 'ANCHOR')}
    out['refusals'] = {a: int(sum(REF.get((t, arm(a), i), False) for t in T for i in range(HP.VOTES_VAL))) for a in ('OBS', 'MODEL', 'ANCHOR')}
    out['degenerate_to_A0'] = {a: out['refusals'][a] >= 0.5 * len(T) * HP.VOTES_VAL for a in ('OBS', 'MODEL')}   # Т7: аварийное соглашение 50 %
    out['A0_no_calls'] = r3(st.mean(load.A0R[t] for t in T))
    out['shrinkage_model_note'] = open_an['winners']['gain_open_model_from']                                    # Т6
    out['vote_status_totals'] = dict(collections.Counter(load.STA.get((t, arm(a), i), 'missing') for t in T for a in ('OBS', 'MODEL', 'ANCHOR') for i in range(HP.VOTES_VAL)))
    return out

if __name__ == '__main__':
    ap = argparse.ArgumentParser(); ap.add_argument('stage', choices=['open', 'val']); ap.add_argument('evals'); ap.add_argument('--out', required=True)
    ap.add_argument('--key', help='ключ секрета и сидов этапа (по умолчанию — этап; dry — сухой прогон с PRECOND_SECRET)')
    ap.add_argument('--open-an', default=f'{HP.D}/open_an.json'); a = ap.parse_args(); key = a.key or a.stage
    if a.stage == 'open':
        res, w = open_stage(a.evals, key)
        json.dump(res, open(a.out, 'w'), ensure_ascii=False, indent=1); json.dump(w, open(f'{HP.D}/winners.json', 'w'), ensure_ascii=False, indent=1)
        print(json.dumps({k: res[k] for k in ('n_tasks', 'Q1', 'ceiling')}, ensure_ascii=False)); print('победители:', json.dumps(w, ensure_ascii=False))
    else:
        res = val_stage(a.evals, json.load(open(a.open_an)), key)
        json.dump(res, open(a.out, 'w'), ensure_ascii=False, indent=1); print(json.dumps(res, ensure_ascii=False)[:2000])
