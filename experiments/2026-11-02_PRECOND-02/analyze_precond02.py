# PRECOND-02: анализ повтора действия REFUSE (правила — PREREG-PRECOND-02.md).
#   python3 analyze_precond02.py interim evals/A.jsonl --out interim_an.json            — промежуточный анализ этапа A и решение
#   python3 analyze_precond02.py final evals/A.jsonl evals/B.jsonl --out final_an.json   — итог по задачам A и B
#   python3 analyze_precond02.py bounds                                                  — границы плана (для PREREG)
# Регрет голоса — как PRECOND-01 (PREREG-PRECOND-01 §4): (лучший − выбранный) / (лучший − средний по восьми); отказ (−1) → регрет
# выбора по заявке A0; сбой, пропуск и недопустимый номер → 1; задача исключается, если лучший − средний ≤ EPS (150).
# Мера руки на задаче — средний регрет её пяти голосов. Выигрыш задачи g = NOREF − ANCHOR (g > 0 ⇔ REFUSE помогает);
# действие REFUSE = ANCHOR − NOREF = −g (знак как у C-041, −0,089).
# Первичный тест — односторонний t по задачам (H1: среднее g > 0) в групповом последовательном плане с одним промежуточным
# анализом: граница эффективности — расход α по Lan–DeMets типа O'Brien–Fleming; граница бесполезности (среднее g ≤ 0 на
# промежуточном) — необязывающая, α её не учитывает. Номинальное p каждого анализа сравнивается с 1 − Φ(c) границы.
import argparse, collections, json, math, os, statistics as st, sys
HERE = os.path.dirname(os.path.abspath(__file__)); EXP = os.path.join(HERE, '..')
sys.path.insert(0, os.path.join(EXP, '2026-10-07_SELECT-01')); sys.path.insert(0, os.path.join(EXP, '2026-10-21_PRECOND-01')); sys.path.insert(0, HERE)
import harness_precond02 as HP  # noqa: E402
from analyze import EPS, a0  # noqa: E402
from analyze_precond import t_ci, t_cdf  # noqa: E402   — t по задачам и его CDF (неполная бета), как PRECOND-01
ALPHA, N1, NMAX = 0.05, None, None          # N1 и NMAX — из plan.json (фиксируется до генерации заданий теста)
r3 = lambda x: None if x is None else round(float(x), 3)

# ---------- нормальное распределение и границы Lan–DeMets (O'Brien–Fleming), один промежуточный анализ ----------
def Phi(z): return 0.5 * (1 + math.erf(z / math.sqrt(2)))
def Phi_inv(p):
    lo, hi = -40.0, 40.0
    for _ in range(200):
        mid = (lo + hi) / 2
        if Phi(mid) < p: lo = mid
        else: hi = mid
    return (lo + hi) / 2
def spend(t, alpha=ALPHA):       # односторонний расход OBF: α(t) = 2 − 2Φ(z_{1−α/2} / √t)
    return 2 - 2 * Phi(Phi_inv(1 - alpha / 2) / math.sqrt(t)) if t > 0 else 0.0
def cross2(c1, c2, rho, mu1=0.0, mu2=0.0, steps=40000):
    """P(Z1 < c1, Z2 ≥ c2) для двумерного нормального с корреляцией rho и средними mu1, mu2 (интеграл по z1, правило трапеций)."""
    lo = min(mu1, c1) - 12.0; h = (c1 - lo) / steps; s = 0.0; sq = math.sqrt(1 - rho * rho)
    for k in range(steps + 1):
        z = lo + k * h; w = 0.5 if k in (0, steps) else 1.0
        s += w * math.exp(-0.5 * (z - mu1) ** 2) / math.sqrt(2 * math.pi) * (1 - Phi((c2 - mu2 - rho * (z - mu1)) / sq))
    return s * h
def bounds(t1, alpha=ALPHA):
    """Границы z: c1 на промежуточном (доля информации t1), c2 на итоговом; P_0(Z1 ≥ c1) = α(t1), P_0(Z1 < c1, Z2 ≥ c2) = α − α(t1)."""
    a1 = spend(t1, alpha); c1 = Phi_inv(1 - a1); rho = math.sqrt(t1); lo, hi = 0.0, 10.0
    for _ in range(80):
        mid = (lo + hi) / 2
        if cross2(c1, mid, rho) > alpha - a1: lo = mid
        else: hi = mid
    c2 = (lo + hi) / 2
    return dict(t1=t1, alpha1=a1, c1=c1, c2=c2, p1_nominal=1 - Phi(c1), p2_nominal=1 - Phi(c2), alpha_check=a1 + cross2(c1, c2, rho))

def plan():
    return json.load(open(os.path.join(HP.D, 'plan.json')))

# ---------- регреты ----------
def load(stage, evals):
    sec = HP.sec_for(stage); rec, R, REF, OUT, INP, A0R, excl, STA = {}, {}, {}, {}, {}, {}, [], {}
    for e in map(json.loads, open(evals, encoding='utf-8')):
        k = (e['task'], e['arm'], int(e['i']))
        if k not in rec or (rec[k].get('error') and not e.get('error')): rec[k] = e
    miss = HP.missing_pools(stage) if stage != 'pilot' else set()     # совет 40, правка 3: без пула — только по закоммиченному списку
    for t in HP.tids(stage):
        p = f'{sec}/truth/{t}.json'
        if t in miss: continue
        assert os.path.exists(p), f'нет правды для {t}, хотя пул есть'
        tr = json.load(open(p)); orc, mean = max(tr), st.mean(tr)
        if orc - mean <= EPS['WH']: excl.append(t); continue
        reg = lambda i: (orc - tr[i]) / (orc - mean); A0R[t] = reg(a0(HP.pool(t), t))
        for a in HP.ARMS:
            for i in range(HP.VOTES):
                e = rec.get((t, a, i)); c = None if e is None or e.get('error') else e.get('choice')
                valid = isinstance(c, int) and 0 <= c < len(tr); refused = c == -1
                R[(t, a, i)] = reg(c) if valid else (A0R[t] if refused else 1.0)
                STA[(t, a, i)] = 'missing' if e is None else 'ok' if valid else 'refused' if refused else 'error' if e.get('error') else 'invalid'
                # совет 40, правка 4: у пропусков и сбоев нет ни выхода, ни входа — в длину и в проверку входа они не идут
                REF[(t, a, i)] = refused; got = STA[(t, a, i)] in ('ok', 'refused')
                OUT[(t, a, i)] = (e.get('out') or 0) if got else None; INP[(t, a, i)] = (e.get('inp') or 0) if got else None
    T = sorted({t for (t, a, i) in R})
    return dict(T=T, R=R, REF=REF, OUT=OUT, INP=INP, A0R=A0R, excl=excl, STA=STA)

def arm_mean(L, t, a): return st.mean(L['R'][(t, a, i)] for i in range(HP.VOTES))
def gains(L): return [arm_mean(L, t, 'NOREF') - arm_mean(L, t, 'ANCHOR') for t in L['T']]

def describe(L):
    T, out = L['T'], {}
    for a in HP.ARMS:
        ks = [(t, a, i) for t in T for i in range(HP.VOTES)]; rf = [k for k in ks if L['REF'][k]]; an = [k for k in ks if not L['REF'][k]]
        out[a] = dict(regret=r3(st.mean(arm_mean(L, t, a) for t in T)), refusals=len(rf), votes=len(ks), refusal_share=r3(len(rf) / len(ks)),
                      answered_regret=r3(st.mean(L['R'][k] for k in an)) if an else None,                    # условие после воздействия, описательно
                      refusal_contribution=r3(len(rf) / len(ks) * (st.mean(L['A0R'][k[0]] for k in rf) - st.mean(L['R'][k] for k in an))) if rf and an else 0.0,
                      out_per_call=r3(st.mean(L['OUT'][k] for k in ks if L['OUT'][k] is not None)), not_ok=sum(L['STA'][k] not in ('ok', 'refused') for k in ks))
    out['A0_no_calls'] = r3(st.mean(L['A0R'][t] for t in T))
    out['vote_status'] = dict(collections.Counter(L['STA'].values()))
    # чистота входа: у пяти голосов одной руки на одной задаче промпт один, вход первого запроса должен совпадать
    # (снимок git менял его от вызова к вызову — ERRORS № 118); здесь — вход из выгрузки драйвера (inp итоговой записи)
    spans = [max(v) - min(v) for t in T for a in HP.ARMS for v in [[L['INP'][(t, a, i)] for i in range(HP.VOTES) if L['INP'][(t, a, i)] is not None]] if len(v) > 1]
    # порог — по пилоту (чистый контекст: размах 2–28 токенов — путь рабочей папки); снимок git добавлял около +400 (PRECOND-01) и +700…+1900 (SCORE-01)
    out['input_span'] = dict(max=max(spans), share_over_30=r3(sum(s > 30 for s in spans) / len(spans)),
                             flag=bool(max(spans) > 100 or sum(s > 30 for s in spans) / len(spans) > 0.05))
    return out

def test(g, p_nominal):
    r = t_ci(g); p = r['p_greater']
    return dict(gain=r, effect_REFUSE=r3(-r['mean']), effect_ci95=[r3(-r['ci95'][1]), r3(-r['ci95'][0])], p_one_sided=p, p_nominal_bound=round(p_nominal, 6),
                reject=bool(p is not None and p <= p_nominal))

def interim(evA, key='A'):
    HP.verify_hashes(key); pl = plan(); L = load(key, evA); g = gains(L); n1 = len(g); b = bounds(n1 / pl['n_max'])
    out = dict(stage=key, n_tasks=n1, excluded_eps=L['excl'], plan=pl, bounds={k: round(v, 6) for k, v in b.items()}, primary=test(g, b['p1_nominal']),
               describe=describe(L))
    # Т1 PRECOND-01: если выпало больше 20 % задач этапа, этап «не определён» — промежуточный анализ не останавливает, план идёт дальше.
    # Совет 40, правка 1: исключённые по EPS от рук не зависят — их нет в знаменателе; выпавшие — задачи без пула или без голосов
    out['defined'] = n1 >= 0.8 * (len(HP.tids(key)) - len(L['excl']))
    if out['defined'] and out['primary']['reject']: out['decision'] = 'остановить: эффективность'
    elif out['defined'] and st.mean(g) <= 0: out['decision'] = 'остановить: бесполезность'          # необязывающая граница, правило заранее
    else: out['decision'] = 'продолжить'
    return out

def final(evA, evB, keyA='A', keyB='B'):
    HP.verify_hashes(keyB); pl = plan(); LA, LB = load(keyA, evA), load(keyB, evB); gA, gB = gains(LA), gains(LB); g = gA + gB
    ia = json.load(open(os.path.join(HP.D, 'interim_an.json')))
    c1 = ia['bounds']['c1']; a1 = ia['bounds']['alpha1']; n1 = ia['n_tasks']; rho = math.sqrt(n1 / len(g)); lo, hi = 0.0, 10.0
    for _ in range(80):                                     # итоговая граница при фактической доле информации n1 / n (весь остаток α)
        mid = (lo + hi) / 2
        if cross2(c1, mid, rho) > ALPHA - a1: lo = mid
        else: hi = mid
    c2 = (lo + hi) / 2
    L = dict(T=LA['T'] + LB['T'], R={**LA['R'], **LB['R']}, REF={**LA['REF'], **LB['REF']}, OUT={**LA['OUT'], **LB['OUT']}, INP={**LA['INP'], **LB['INP']},
             A0R={**LA['A0R'], **LB['A0R']}, excl=LA['excl'] + LB['excl'], STA={**LA['STA'], **LB['STA']})
    out = dict(n_tasks=len(g), n_A=len(gA), n_B=len(gB), excluded_eps=L['excl'], final_bound=dict(c2=round(c2, 6), p2_nominal=round(1 - Phi(c2), 6), rho=round(rho, 6)),
               primary=test(g, 1 - Phi(c2)), stage_B_only=t_ci(gB), describe=describe(L), interim_decision=ia['decision'])
    # оценка при последовательном плане смещена мало, если остановки на промежуточном не было; пометка — в отчёте
    return out

if __name__ == '__main__':
    ap = argparse.ArgumentParser(); ap.add_argument('stage', choices=['interim', 'final', 'bounds']); ap.add_argument('evals', nargs='*')
    ap.add_argument('--out'); ap.add_argument('--keys', default='A,B'); a = ap.parse_args(); kA, kB = a.keys.split(',')
    if a.stage == 'bounds':
        pl = plan(); print(json.dumps(dict(plan=pl, bounds=bounds(pl['n1'] / pl['n_max'])), ensure_ascii=False, indent=1))
    elif a.stage == 'interim':
        res = interim(a.evals[0], kA); json.dump(res, open(a.out, 'w'), ensure_ascii=False, indent=1)
        print(json.dumps({k: res[k] for k in ('n_tasks', 'primary', 'decision')}, ensure_ascii=False))
    else:
        res = final(a.evals[0], a.evals[1], kA, kB); json.dump(res, open(a.out, 'w'), ensure_ascii=False, indent=1)
        print(json.dumps({k: res[k] for k in ('n_tasks', 'primary', 'final_bound')}, ensure_ascii=False))
