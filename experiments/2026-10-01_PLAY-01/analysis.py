"""PLAY-01: анализ по решению совета 24 (правило записано до пилота; меняется только через PREREG).
   python3 analysis.py <этап>          → runs/<этап>/analysis.json и сводка
   python3 analysis.py power           → таблица мощности (оценка Монте-Карло)
Главная мера T = log(1 + max(S_auto, 0)). Парные разности d_i = T_C − T_B по годным зёрнам. Перестановочный тест знаков
полным перебором 2^n, двусторонний, статистика Σd_i, |·| ≥ наблюдаемого с допуском 1e-12. Среднее геометрическое отношение
exp(mean d). 95% интервал — {δ0 : p(d − δ0) > 0,05} (предполагает симметрию d_i относительно δ)."""
import itertools, json, math, os, sys
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
TOL = 1e-12


def T(s): return math.log1p(max(float(s), 0.0))


def perm_p(d):
    d = np.asarray(d, float)
    n = len(d)
    if n == 0: return 1.0
    obs = abs(d.sum())
    signs = np.array(list(itertools.product((1, -1), repeat=n)))
    stats = np.abs(signs @ d)
    return float(np.mean(stats >= obs - TOL))


def ci_invert(d, alpha=0.05):
    """Интервал обращением теста: точки сетки δ0, где p(d − δ0) > alpha; границы уточняются бисекцией."""
    d = np.asarray(d, float)
    if len(d) == 0: return (None, None)
    m = d.mean()
    acc = lambda x: perm_p(d - x) > alpha
    span = max(1.0, 4 * (d.max() - d.min()))
    def edge(sign):
        lo, hi = m, m + sign * span           # lo — принят, hi — отвергнут
        while acc(hi): hi += sign * span
        for _ in range(60):
            mid = (lo + hi) / 2
            if acc(mid): lo = mid
            else: hi = mid
        return lo
    return (edge(-1), edge(1))


def pred_errors(hist):
    """Незнание и самообман предсказаний инвентаря и числа построек (на раунд; среднее по раундам).
    Для предмета: незнание = |п − ф| / max(п, ф, 1); самообман = max(0, п − ф) / max(п, ф, 1)."""
    ig, de, big, bde = [], [], [], []
    for h in hist:
        pr = h.get('predict') or {}
        inv = pr.get('inventory') or {}
        items = list(inv.items())[:8]
        if items:
            e = [(abs(v - h['inventory'].get(k, 0)), max(0, v - h['inventory'].get(k, 0)), max(v, h['inventory'].get(k, 0), 1)) for k, v in items if isinstance(v, (int, float))]
            if e:
                ig.append(np.mean([a / m for a, b, m in e])); de.append(np.mean([b / m for a, b, m in e]))
        if isinstance(pr.get('buildings'), (int, float)):
            p, f = pr['buildings'], h['buildings']
            big.append(abs(p - f) / max(p, f, 1)); bde.append(max(0, p - f) / max(p, f, 1))
    mean = lambda x: float(np.mean(x)) if x else None
    return dict(inv_ignorance=mean(ig), inv_deception=mean(de), bld_ignorance=mean(big), bld_deception=mean(bde), rounds=len(ig))


def act_key(a):
    """Ключ действия для сравнения планов: вид, предмет/рецепт/технология, координаты с точностью до клетки."""
    def r(v): return round(v) if isinstance(v, (int, float)) else None
    return (a.get('a'), a.get('item') or a.get('recipe') or a.get('tech'), r(a.get('x')), r(a.get('y')))


def role_similarity(stage, part='C', thr=0.8):
    """Открытый пункт 3а: доля пар ролей C (3 пары на раунд и зерно) с совпадающими планами — Жаккар множеств
    ключей действий ≥ thr. Больше половины — записать как слабость C (повтор PRED-01)."""
    base = os.path.join(HERE, 'runs', stage)
    st = json.load(open(os.path.join(base, 'state.json')))
    js, n = [], 0
    for k, dec in st['decisions'].items():
        for ck, d in dec.items():
            if not ck.startswith(part + '_'): continue
            roles = [set(map(act_key, (r or {}).get('actions') or [])) for r in d.get('roles') or []]
            for i in range(len(roles)):
                for j in range(i + 1, len(roles)):
                    a, b = roles[i], roles[j]
                    js.append(len(a & b) / len(a | b) if a | b else 1.0)
    return dict(pairs=len(js), share_same=float(np.mean([x >= thr for x in js])) if js else None,
                mean_jaccard=float(np.mean(js)) if js else None, thr=thr)


def analyse(stage):
    base = os.path.join(HERE, 'runs', stage)
    st = json.load(open(os.path.join(base, 'state.json')))
    sc = json.load(open(os.path.join(base, 'scores.json')))
    rp = json.load(open(os.path.join(base, 'replay.json'))) if os.path.exists(os.path.join(base, 'replay.json')) else {}
    cfg = st['cfg']; seeds, parts = cfg['seeds'], cfg['parts']
    ok = {}
    for ck, c in st['chains'].items():
        s = sc.get(ck)
        bal_rounds = [h['round'] for h in c['hist'] if h['balance'] or h['violations']]
        ok[ck] = dict(scored=s is not None, queue_empty=bool(s and s['queue_empty']), balance_rounds=bal_rounds,
                      window_balance=bool(s and not s['balance']), lua_match=bool(s and abs(s['s_auto'] - s['s_auto_lua']) < 1e-6),
                      replay=rp.get(ck, {}).get('match'))
        ok[ck]['pass'] = ok[ck]['scored'] and ok[ck]['queue_empty'] and not bal_rounds and ok[ck]['window_balance'] and ok[ck]['lua_match'] and ok[ck]['replay'] is not False
    per = {}
    for p in parts:
        rows = []
        for s in seeds:
            ck = f'{p}_s{s}'
            c = st['chains'][ck]; v = sc.get(ck, {})
            res = [r for h in c['hist'] for r in h['results'] if 'i' in r]
            rows.append(dict(seed=s, s_auto=v.get('s_auto'), s_prime=v.get('s_prime'), T=T(v.get('s_auto', 0)), T_prime=T(v.get('s_prime', 0)),
                             reject_rate=(sum(1 for r in res if not r['ok']) / len(res)) if res else None, head_failed=sum(h.get('head_failed', False) for h in c['hist']),
                             buildings=c['hist'][-1]['buildings'] if c['hist'] else 0, researched=v.get('totals', {}).get('researched'), check=ok[ck]['pass'],
                             **pred_errors(c['hist'])))
        per[p] = rows
    out = dict(stage=stage, cfg={k: v for k, v in cfg.items()}, checks=ok, per=per)
    if 'B' in parts and 'C' in parts:
        good = [s for s in seeds if ok[f'B_s{s}']['pass'] and ok[f'C_s{s}']['pass']]
        TB = {r['seed']: r for r in per['B']}; TC = {r['seed']: r for r in per['C']}
        floor = [s for s in good if TB[s]['s_auto'] <= 0 and TC[s]['s_auto'] <= 0]
        d = [TC[s]['T'] - TB[s]['T'] for s in good]
        dp = [TC[s]['T_prime'] - TB[s]['T_prime'] for s in good]
        n, k = len(good), len(floor)
        p = perm_p(d) if d else None
        gm = math.exp(float(np.mean(d))) if d else None
        lo, hi = ci_invert(d) if d else (None, None)
        harness_fail = sum(1 for p_ in ('B', 'C') for s in seeds if not ok[f'{p_}_s{s}']['pass'])
        gate_A = None
        if 'A' in parts and 'H' in parts:
            gA = [s for s in seeds if ok[f'A_s{s}']['pass'] and ok[f'H_s{s}']['pass']]
            TA = {r['seed']: r['T'] for r in per['A']}; TH = {r['seed']: r['T'] for r in per['H']}
            wins = sum(1 for s in gA if TA[s] > TH[s])            # ничья — невыигрыш A
            gate_A = dict(seeds=len(gA), wins=wins, pass_=wins >= len(gA) - 1 if len(gA) == len(seeds) else wins >= len(gA) - 1)
        gate_stock = (np.sign(np.mean(dp)) == np.sign(np.mean(d))) if d else None
        if harness_fail >= 2: verdict = 'не решено (обвязка)'
        elif k >= 2 or n - k < 6: verdict = 'не решено (пол)'
        else:
            verdict = 'не решено'
            if p < 0.05 and np.mean(d) > 0 and gm >= 2:
                if not gate_A['pass_']: verdict = 'не решено (мера)'
                elif not gate_stock: verdict = 'не решено (запасы)'
                else: verdict = 'сильнее (предварительно)'
            elif p < 0.05 and np.mean(d) < 0: verdict = 'C хуже B'
            if hi is not None and math.exp(hi) < 2: verdict += '; вдвое нет'
        out['test'] = dict(good_seeds=good, floor_seeds=floor, n=n, k=k, d=d, d_prime=dp, p=p, gm=gm,
                           ci=[math.exp(lo) if lo is not None else None, math.exp(hi) if hi is not None else None],
                           gate_A=gate_A, gate_stock=bool(gate_stock) if gate_stock is not None else None, harness_fail=harness_fail, verdict=verdict)
    out['role_similarity'] = {p: role_similarity(stage, p) for p in ('C', 'D') if p in parts}
    json.dump(out, open(os.path.join(base, 'analysis.json'), 'w'), ensure_ascii=False, indent=1)
    return out


def power(n=7, sims=4000, rng=np.random.default_rng(1)):
    """Мощность совместного правила «p < 0,05 и среднее геометрическое ≥ 2» (оценка Монте-Карло; d_i ~ N(log r, σ))."""
    signs = np.array(list(itertools.product((1, -1), repeat=n)))
    rows = []
    for r in (1.0, 1.5, 2.0, 3.0, 4.0):
        for sd in (0.5, 1.0, 2.0):
            d = rng.normal(math.log(r), sd, size=(sims, n))
            obs = np.abs(d.sum(1))
            p = (np.abs(d @ signs.T) >= obs[:, None] - TOL).mean(1)
            sig = p < 0.05
            joint = sig & (d.mean(1) > 0) & (np.exp(d.mean(1)) >= 2)
            rows.append(dict(ratio=r, sd=sd, p_lt_05=float(sig.mean()), joint=float(joint.mean())))
    return rows


if __name__ == '__main__':
    if sys.argv[1] == 'power':
        for r in power(): print(r)
    else:
        o = analyse(sys.argv[1])
        for p, rows in o['per'].items():
            print(p, ' '.join(f's{r["seed"]}:{(r["s_auto"] or 0):.0f}' for r in rows),
                  'отказы', ' '.join(f'{r["reject_rate"]:.2f}' if r['reject_rate'] is not None else '-' for r in rows))
        if 'test' in o: print(json.dumps(o['test'], ensure_ascii=False))
