# EVAL-01, основной прогон: выборка, задания судьям, анализ. Дизайн — совет 11 (ред. 3) + требования Левого (явная МДЭ, честный n) и Скептика
# (единая формула R для всех ветвей; правило стадии 2) + уступленное предложение Правого (дебаты как контроль). Правда — вне репозитория.
# Правки по рецензии ворот 2 (REVIEW_gate2.md, 28.09.2026): прямые пары только внутри одной задачи; MODSQ без сигнала длины; пропуски → 0,5 с флагом;
# вырождение по правилу §9; дисквалификация в вердиктах; Холм; критерий 1(а); таблица вторичных §8; единая ci(); бутстреп R без самопар.
#   python3 eval01_main.py build [--no-sc3] [--c2b] [--c3b]   → main/sample_key.json, main/jobs.json, main/pairs_key.json, main/eval01_main.js, main/eval01_dry.js
#   python3 eval01_main.py analyze main/out.json [--dry]       → main/analysis.json (или main/dry_analysis.json)
import json, os, sys, random, math, re, statistics as st, itertools
HERE = os.path.dirname(os.path.abspath(__file__)); D = os.path.join(HERE, 'main'); os.makedirs(D, exist_ok=True)
TRUTH = '/root/eval_secret/truth.json'; SEED = 2810
NO = 'Не используй никакие инструменты и не открывай файлы: суди сам, опираясь только на текст ниже.'
BIG = [('HIVE-01', 'TWIN'), ('HIVE-01', 'COLLATZ'), ('HIVE-01', 'SUB5'), ('LEVEL-04', 'MODSQ-link')]
SMALL = {('HIVE-01', 'COL3'): 5, ('HIVE-01', 'PART'): 4, ('DIV-01', 'TWIN'): 4}
DRY_PLAN = {('HIVE-01', 'TWIN'): (2, 1), ('HIVE-01', 'COLLATZ'): (1, 2), ('HIVE-01', 'SUB5'): (2, 0), ('LEVEL-04', 'MODSQ-link'): (1, 1)}  # (верных, неверных); у SUB5 все 16 неверных ушли в основную выборку
MODSQ = ('LEVEL-04', 'MODSQ-link')
ARMS1 = ['BLIND', 'RC1', 'RC2', 'RC3', 'ABSTAIN', 'C2', 'C3', 'NOANS', 'DEB_PRO', 'DEB_DEF']
PAIR_SAME, PAIR_DIFF = 50, 50   # верхние пределы числа прямых пар (одного класса / разных классов); берутся все доступные пары внутри одной задачи
# пороги и параметры анализа (фиксируются в PREREG)
LAM, CABST = 0.7, 0.15            # перекалибровка BLIND по сетке пилота (pilot/mde_pilot.json: лучший Брайер при воздержаниях ≤ 0,3)
MDE_BRIER, MDE_T, MDE_IOI = 0.05, 0.07, 0.10
R_RATIO, DISQ, AUC_DROP, ABST_MAX, NOANS_MARGIN, PAIR_AUC_DROP = 0.5, 0.20, 0.05, 0.5, 0.05, 0.03
ALPHA, DEGEN = 0.05, 8            # Холм по семейству первичных; вырождение — ≥ DEGEN из 10 троек сухого прогона
SEC = dict(council_vs_sc3=0.02, sc3_vs_rec=0.03, prompt_vs_rec=0.05, twin_cw=0.10, ioi_floor=0.3, ioi_band=0.10)  # пороги вторичных §8 и правила «разницы нет» §7
B, BSEED = 2000, 0
NOCM = ['HIVE-01/TWIN', 'HIVE-01/SUB5']   # разрез без COLLATZ/MODSQ (§8.8)
sys.path.insert(0, HERE)
from eval01_pilot import target_of, label, render, criterion, auc   # те же правила мишени и рендеринга, что в пилоте


def cell_of(it): return f"{it['source']}/{it['family']}"
def k_steps(it):  # требуемое число шагов K из текста задачи траектории («сделай ровно K шагов»)
    m = re.search(r'ровно (\d+) шаг', it['task']); return int(m.group(1)) if m else None
def full_chain(it): return it['answer'].get('n_values') == k_steps(it)


def build(no_sc3=False, c2b=False, c3b=False):
    items = [json.loads(l) for l in open(os.path.join(HERE, 'data', 'items_public.jsonl'))]; truth = json.load(open(TRUTH))
    pilot_ids = set(json.load(open(os.path.join(HERE, 'pilot', 'sample_key.json')))['ids'])
    rng = random.Random(SEED); cells = {}
    for it in items:
        if it['leak_note'] or it['id'] in pilot_ids: continue
        cells.setdefault((it['source'], it['family']), []).append(it)
    def take(key, n_good, n_bad, exclude=()):
        pool = [x for x in cells[key] if x['id'] not in exclude]; rng.shuffle(pool)
        if key == MODSQ: pool = [x for x in pool if full_chain(x)]   # рецензия 1.2: число выписанных значений N = K, иначе N — сигнал метки (у верных N = K всегда)
        good = [x for x in pool if label(x, truth)][:n_good]; bad = [x for x in pool if not label(x, truth)][:n_bad]
        assert len(good) == n_good and len(bad) == n_bad, (key, len(good), len(bad)); return good + bad
    sample = []
    for key in BIG: sample += take(key, 16, 16)
    for key, k in SMALL.items(): sample += take(key, k, k)
    used = {x['id'] for x in sample}
    dry = []
    for key, (g, b) in DRY_PLAN.items(): dry += take(key, g, b, exclude=used)
    rng.shuffle(sample); rng.shuffle(dry)
    aliases = {it['id']: f'm{i:03d}' for i, it in enumerate(sample)}; aliases.update({it['id']: f'd{i:03d}' for i, it in enumerate(dry)})
    key = dict(seed=SEED, ids=[it['id'] for it in sample], dry_ids=[it['id'] for it in dry], aliases=aliases,
               cells={aliases[it['id']]: cell_of(it) for it in sample + dry}, arms=dict(no_sc3=no_sc3, c2b=c2b, c3b=c3b), lam=LAM, c_abst=CABST,
               modsq_rule='неверные MODSQ-link только с n_values == K (K из текста задачи)')
    json.dump(key, open(os.path.join(D, 'sample_key.json'), 'w'), ensure_ascii=False, indent=1)
    arms = [a for a in ARMS1 if not (no_sc3 and a in ('RC2', 'RC3'))]
    arms = ['C2B' if (a == 'C2' and c2b) else 'C3B' if (a == 'C3' and c3b) else a for a in arms]
    def jobs_for(lst): return [dict(alias=aliases[it['id']], arm=arm, task=it['task'], answer=render(it, with_note=False), criterion=criterion(it)) for it in lst for arm in arms]
    jobs, djobs = jobs_for(sample), jobs_for(dry)
    # прямые пары BLIND: 4 больших клетки, только ответы на ОДНУ И ТУ ЖЕ задачу (рецензия 1.1), до PAIR_SAME пар одного класса + до PAIR_DIFF разных, оба порядка
    by_cell = {}
    for it in sample:
        if (it['source'], it['family']) in BIG: by_cell.setdefault(cell_of(it), []).append(it)
    same, diff = [], []
    for c, lst in sorted(by_cell.items()):
        for a, b in itertools.combinations(lst, 2):
            if a['task'] != b['task']: continue
            (same if label(a, truth) == label(b, truth) else diff).append((a, b))
    avail = dict(same=len(same), diff=len(diff))
    rng.shuffle(same); rng.shuffle(diff); chosen = same[:PAIR_SAME] + diff[:PAIR_DIFF]
    pairs = []
    for k, (a, b) in enumerate(chosen):
        assert a['task'] == b['task']; pid = f'p{k:03d}'
        pairs.append(dict(pid=pid, order='AB', task=a['task'], criterion=criterion(a), a=render(a, False), b=render(b, False)))
        pairs.append(dict(pid=pid, order='BA', task=a['task'], criterion=criterion(a), a=render(b, False), b=render(a, False)))
    n_same = sum(label(a, truth) == label(b, truth) for a, b in chosen)
    json.dump(dict(rule='пары только внутри одной задачи', available=avail, n_same=n_same, n_diff=len(chosen) - n_same,
                   pairs=[dict(pid=f'p{k:03d}', a=aliases[a['id']], b=aliases[b['id']], same=label(a, truth) == label(b, truth), cell=cell_of(a)) for k, (a, b) in enumerate(chosen)]),
              open(os.path.join(D, 'pairs_key.json'), 'w'), ensure_ascii=False, indent=1)
    json.dump(jobs, open(os.path.join(D, 'jobs.json'), 'w'), ensure_ascii=False); json.dump(djobs, open(os.path.join(D, 'jobs_dry.json'), 'w'), ensure_ascii=False)
    src = open(os.path.join(HERE, 'eval01_main_step.js')).read()
    mk = lambda J, P: src.replace('const JOBS = null', 'const JOBS = ' + json.dumps(J, ensure_ascii=False)).replace('const PAIRS = null', 'const PAIRS = ' + json.dumps(P, ensure_ascii=False)).replace('const NO = null', 'const NO = ' + json.dumps(NO, ensure_ascii=False))
    open(os.path.join(D, 'eval01_main.js'), 'w').write(mk(jobs, pairs))
    open(os.path.join(D, 'eval01_dry.js'), 'w').write(mk(djobs, []).replace("name: 'eval01-main'", "name: 'eval01-dry'"))
    n_arb = len(sample)
    print(f'выборка {len(sample)} (верных {sum(label(x, truth) for x in sample)}), сухой прогон {len(dry)}; ветви {arms}; '
          f'пары внутри задачи: доступно одного класса {avail["same"]}, разных {avail["diff"]}; взято {n_same} + {len(chosen) - n_same} = {len(chosen)} (×2 порядка = {len(pairs)} вызовов); '
          f'вызовов: основной {len(jobs)} + арбитры {n_arb} + пары {len(pairs)} = {len(jobs) + n_arb + len(pairs)}; сухой {len(djobs) + len(dry)}')


# ---------- анализ ----------
def clip(p): return min(1.0, max(0.0, float(p)))
def num(x):  # p_correct числом или числовой строкой; булево — не число
    if isinstance(x, bool): return None
    if isinstance(x, (int, float)): return float(x)
    if isinstance(x, str):
        try: return float(x.strip().replace(',', '.'))
        except ValueError: return None
    return None
def recal(p, lam=LAM, c=CABST): q = 0.5 + lam * (p - 0.5); return 0.5 if abs(q - 0.5) < c else q
def half_T(p, y): return 0.5 if p == 0.5 else float((p > 0.5) == y)
def ci(vals):  # единый 95 % перцентильный ИД: индексы [int(0,025·n), int(0,975·n) − 1] (n = 2000 → [50], [1949]); тот же helper в pilot/mde_pilot.py и pilot/r_pilot.py
    v = sorted(x for x in vals if x is not None); n = len(v)
    return [v[int(0.025 * n)], v[int(0.975 * n) - 1]] if n > 20 else None
def pboot(vals, null=0.0):  # двустороннее бутстреп-p против null: 2·min(доля ≤ null, доля ≥ null) с поправкой (k + 1)/(n + 1)
    v = [x for x in vals if x is not None]; n = len(v)
    if n <= 20: return None
    le = sum(x <= null for x in v); ge = sum(x >= null for x in v); return min(1.0, 2 * min(le + 1, ge + 1) / (n + 1))
def holm(ps, alpha=ALPHA):  # ps: {имя: p}; последовательное отклонение Холма при уровне alpha
    named = sorted((p, name) for name, p in ps.items() if p is not None); m = len(named); table = {}; go = True
    for i, (p, name) in enumerate(named):
        thr = alpha / (m - i); go = go and p <= thr; table[name] = dict(p=p, rank=i + 1, threshold=thr, reject=go)
    for name, p in ps.items():
        if p is None: table[name] = dict(p=None, rank=None, threshold=None, reject=False)
    return dict(alpha=alpha, m=m, table=table)
KEYS = ('T', 'C', 'brier', 'ioi', 'auc', 'abstain', 'conf_wrong')
def metrics(ps):  # ps: [(p, y)]
    if not ps: return None
    T = st.mean(half_T(p, y) for p, y in ps); C = st.mean(max(p, 1 - p) for p, _ in ps)
    return dict(n=len(ps), T=T, C=C, brier=st.mean((p - y) ** 2 for p, y in ps), ioi=(1 - T) + max(0, C - T), auc=auc(ps), abstain=st.mean(p == 0.5 for p, _ in ps),
                conf_wrong=(st.mean(p >= 0.8 for p, y in ps if not y) if any(not y for _, y in ps) else None))
def agg(ms):  # равновзвешенное среднее клеточных метрик
    ms = [m for m in ms if m]
    return {k: st.mean(m[k] for m in ms) for k in KEYS if all(m.get(k) is not None for m in ms)} if ms else None
def rstat(ps):  # единая формула для всех ветвей: pref = pA/(pA+pB) по всем парам внутри клетки; ps: [(p, y)] или [(p, y, псевдоним)] — пары одного псевдонима (самопары бутстрепа) пропускаются
    same, diffs, aucs = [], [], []
    for (pa, ya, *ia), (pb, yb, *ib) in itertools.combinations(ps, 2):
        if ia and ia == ib: continue
        pref = 0.5 if pa + pb == 0 else pa / (pa + pb)
        if ya == yb: same.append(abs(pref - 0.5))
        else:
            diffs.append(abs(pref - 0.5)); pc = pref if ya else 1 - pref; aucs.append(1.0 if pc > 0.5 else 0.5 if pc == 0.5 else 0.0)
    if not same or not diffs: return None
    ds, dd = st.mean(same), st.mean(diffs); return dict(D_same=ds, D_diff=dd, R=(ds / dd if dd > 0 else None), pair_auc=st.mean(aucs))


def arm_probs(out, aliases):
    """p по ветвям на элемент. Сырые ветви: BLIND, RECOMPUTE=RC1, RC2, RC3, ABSTAIN (can_verify=false→0,5), C2|C2B, C3|C3B, NOANS, DEBATE=DEB_ARB.
    Производные: BLIND_RECAL, SC3=среднее(RC1,RC2,RC3), COUNCIL=среднее(RC1,C2,C3). Пропуск (нет записи / p не число) → 0,5 с флагом (§9); производные считаются
    на подставленных значениях; imputed[ветвь] — число элементов, где хоть один компонент подставлен. Ветвь отсутствует целиком (нет ключа в out) → не анализируется."""
    c2 = 'C2B' if 'C2B' in out else 'C2'; c3 = 'C3B' if 'C3B' in out else 'C3'
    RAW = dict(BLIND='BLIND', RECOMPUTE='RC1', RC2='RC2', RC3='RC3', ABSTAIN='ABSTAIN', C2=c2, C3=c3, NOANS='NOANS', DEBATE='DEB_ARB')
    present = {arm: rk in out for arm, rk in RAW.items()}
    present['BLIND_RECAL'] = present['BLIND']; present['SC3'] = all(present[a] for a in ('RECOMPUTE', 'RC2', 'RC3')); present['COUNCIL'] = all(present[a] for a in ('RECOMPUTE', 'C2', 'C3'))
    missing = {rk: 0 for rk in RAW.values()}; imputed = {arm: 0 for arm in list(RAW) + ['BLIND_RECAL', 'SC3', 'COUNCIL']}
    P = {}
    for a in aliases:
        d, imp = {}, {}
        for arm, rk in RAW.items():
            if not present[arm]: d[arm] = None; imp[arm] = False; continue
            r = out[rk].get(a); p = num(r.get('p_correct')) if isinstance(r, dict) else None
            imp[arm] = p is None
            if p is None: missing[rk] += 1; imputed[arm] += 1; p = 0.5
            elif arm == 'ABSTAIN' and r.get('can_verify') is False: p = 0.5
            d[arm] = clip(p)
        for der, comps in (('BLIND_RECAL', ('BLIND',)), ('SC3', ('RECOMPUTE', 'RC2', 'RC3')), ('COUNCIL', ('RECOMPUTE', 'C2', 'C3'))):
            if not present[der]: d[der] = None; continue
            d[der] = recal(d['BLIND']) if der == 'BLIND_RECAL' else st.mean(d[c] for c in comps)
            if any(imp[c] for c in comps): imputed[der] += 1
        P[a] = d
    return P, present, dict(raw_keys=dict(C2=c2, C3=c3), missing=missing, imputed=imputed)


def analyze(path, dry=False):
    key = json.load(open(os.path.join(D, 'sample_key.json'))); truth = json.load(open(TRUTH))
    items = {it['id']: it for it in (json.loads(l) for l in open(os.path.join(HERE, 'data', 'items_public.jsonl')))}
    out = json.load(open(path)); out = out.get('out', out)
    ids = key['dry_ids'] if dry else key['ids']; al = key['aliases']; cells = key['cells']
    y = {al[i]: label(items[i], truth) for i in ids}
    aliases = [al[i] for i in ids]; P, present, miss = arm_probs(out, aliases)
    ARMS = [arm for arm in ('BLIND', 'BLIND_RECAL', 'RECOMPUTE', 'SC3', 'ABSTAIN', 'C2', 'C3', 'COUNCIL', 'NOANS', 'DEBATE') if present[arm]]
    big = [f'{s}/{f}' for s, f in BIG]
    by_cell = {}
    for a in aliases: by_cell.setdefault(cells[a], []).append(a)
    def cut(arm, al_list): return [(P[a][arm], y[a]) for a in al_list]
    def cut_r(arm, al_list): return [(P[a][arm], y[a], a) for a in al_list]
    def scopes(arm, sample):  # sample: {cell: [alias...]}; главный разрез = среднее по 4 большим клеткам, nocm = без COLLATZ/MODSQ, cells = по клеткам
        cm = {c: metrics(cut(arm, sample.get(c, []))) for c in big}
        return dict(main=agg([cm[c] for c in big]), nocm=agg([cm[c] for c in NOCM]), cells=cm)
    def R_mean(arm, sample):
        rs = [rstat(cut_r(arm, sample.get(c, []))) for c in big]; rs = [r for r in rs if r and r['R'] is not None]
        return st.mean(r['R'] for r in rs) if rs else None
    res = dict(n_items=len(aliases), arms_present=sorted(out.keys()), arms=ARMS, missing=miss['missing'], imputed=miss['imputed'], raw_keys=miss['raw_keys'],
               rule_missing='пропуск → p = 0,5 (с флагом), производные ветви на подставленных значениях; сравнения остаются парными')
    sc = {arm: scopes(arm, by_cell) for arm in ARMS}
    res['item_cut'] = {arm: metrics(cut(arm, aliases)) for arm in ARMS}
    res['main_cut'] = {arm: sc[arm]['main'] for arm in ARMS}
    res['no_cm_cut'] = {arm: sc[arm]['nocm'] for arm in ARMS}
    res['by_cell'] = {c: {arm: metrics(cut(arm, lst)) for arm in ARMS} for c, lst in by_cell.items()}
    res['R'] = {arm: {c: rstat(cut_r(arm, by_cell[c])) for c in big if c in by_cell} for arm in ARMS}
    res['R_main'] = {arm: R_mean(arm, by_cell) for arm in ARMS}
    res['pair_auc_main'] = {arm: (st.mean(r['pair_auc'] for r in res['R'][arm].values() if r) if any(res['R'][arm].values()) else None) for arm in ARMS}
    # бутстреп: элементы внутри клеток, парно по элементу (одна перевыборка для всех ветвей и для R)
    rng = random.Random(BSEED); boots = []; NB = B if not dry else 200
    for _ in range(NB):
        s = {c: [rng.choice(lst) for _ in lst] for c, lst in by_cell.items()}
        row = {arm: scopes(arm, s) for arm in ARMS}; row['R'] = {arm: R_mean(arm, s) for arm in ARMS}; boots.append(row)
    def val(row, arm, scope, k):
        m = row[arm][scope] if scope in ('main', 'nocm') else row[arm]['cells'].get(scope)
        return m.get(k) if m else None
    def ioi_verdict(d):  # §7: «разницы нет» — ИД содержит 0 и лежит внутри ±ioi_band; ИД без 0 — «разница»; иначе — «не разрешено»
        c = d['ci95']
        if not c: return None
        if c[0] > 0 or c[1] < 0: return 'разница'
        return 'разницы нет' if (c[0] >= -SEC['ioi_band'] and c[1] <= SEC['ioi_band']) else 'не разрешено'
    def diff(arm, ref, k, scope='main'):
        if arm not in sc or ref not in sc: return None
        pa, pr = val(sc, arm, scope, k), val(sc, ref, scope, k)
        if pa is None or pr is None: return None
        vals = [va - vr for b in boots for va, vr in [(val(b, arm, scope, k), val(b, ref, scope, k))] if va is not None and vr is not None]
        d = dict(point=pa - pr, ci95=ci(vals), p_boot=pboot(vals))
        if k == 'ioi': d['verdict'] = ioi_verdict(d)
        return d
    res['vs_recal'] = {arm: {k: diff(arm, 'BLIND_RECAL', k) for k in ('brier', 'ioi', 'auc')} for arm in ARMS if arm not in ('BLIND', 'BLIND_RECAL')}
    res['vs_raw_T'] = {arm: diff(arm, 'BLIND', 'T') for arm in ARMS if arm != 'BLIND'}
    def ratio(arm):  # R_ветви / R_BLIND; p — двустороннее бутстреп-p для log-отношения против log(R_RATIO) (отношение ≤ 0,5 ⇔ log-отношение ≤ log 0,5)
        if res['R_main'].get(arm) is None or not res['R_main'].get('BLIND'): return None
        vals = [b['R'][arm] / b['R']['BLIND'] for b in boots if b['R'].get(arm) is not None and b['R'].get('BLIND')]
        return dict(point=res['R_main'][arm] / res['R_main']['BLIND'], ci95=ci(vals), p_boot_vs_half=pboot([math.log(v) for v in vals if v > 0], math.log(R_RATIO)))
    res['R_ratio'] = {arm: ratio(arm) for arm in ARMS if arm != 'BLIND'}
    res['ioi_ratio_vs_recal'] = {}
    for arm in ARMS:
        if arm in ('BLIND', 'BLIND_RECAL') or not res['main_cut'].get(arm) or not res['main_cut'].get('BLIND_RECAL', {}).get('ioi'): continue
        vals = [b[arm]['main']['ioi'] / b['BLIND_RECAL']['main']['ioi'] for b in boots if b[arm]['main'] and b['BLIND_RECAL']['main'] and b['BLIND_RECAL']['main'].get('ioi', 0) > 0]
        res['ioi_ratio_vs_recal'][arm] = dict(point=res['main_cut'][arm]['ioi'] / res['main_cut']['BLIND_RECAL']['ioi'], ci95=ci(vals))
    # вторичные §8 — таблица pairwise (каждое число — из json)
    pw = {}
    def add(name, arm, ref, k, scope='main', **flags):
        d = diff(arm, ref, k, scope)
        if d is None: pw[name] = None; return
        e = dict(arm=arm, ref=ref, metric=k, scope=scope, **d)
        for fn, f in flags.items(): e[fn] = f(d)
        pw[name] = e
    lo = lambda d: d['ci95'] and d['ci95'][0] > 0; hi = lambda d: d['ci95'] and d['ci95'][1] < 0
    add('8.1 COUNCIL−BLIND_RECAL brier', 'COUNCIL', 'BLIND_RECAL', 'brier', better=lambda d: bool(hi(d)))
    add('8.1 COUNCIL−BLIND_RECAL ioi', 'COUNCIL', 'BLIND_RECAL', 'ioi')
    add('8.2 COUNCIL−SC3 brier', 'COUNCIL', 'SC3', 'brier', council_better_by_0_02=lambda d: d['point'] <= -SEC['council_vs_sc3'], ci_excl0=lambda d: bool(hi(d)))
    add('8.2 SC3−RECOMPUTE brier', 'SC3', 'RECOMPUTE', 'brier', close_within_0_03=lambda d: abs(d['point']) < SEC['sc3_vs_rec'])
    for arm in ('C2', 'C3'): add(f'8.3 {arm}−RECOMPUTE brier', arm, 'RECOMPUTE', 'brier', not_worse_by_0_05=lambda d: d['point'] <= SEC['prompt_vs_rec'])
    add('8.4 DEBATE−COUNCIL brier', 'DEBATE', 'COUNCIL', 'brier', debate_worse=lambda d: bool(lo(d)))
    add('8.4 DEBATE−COUNCIL ioi', 'DEBATE', 'COUNCIL', 'ioi')
    add('8.4 DEBATE−BLIND_RECAL brier', 'DEBATE', 'BLIND_RECAL', 'brier', debate_worse=lambda d: bool(lo(d)))
    add('8.4 DEBATE−BLIND_RECAL ioi', 'DEBATE', 'BLIND_RECAL', 'ioi')
    add('8.5 TWIN C3−RECOMPUTE conf_wrong', 'C3', 'RECOMPUTE', 'conf_wrong', scope='HIVE-01/TWIN', lower_by_0_10=lambda d: d['point'] <= -SEC['twin_cw'])
    for arm in ARMS:
        if arm not in ('BLIND', 'BLIND_RECAL'):
            add(f'8.8 noCM {arm}−BLIND_RECAL brier', arm, 'BLIND_RECAL', 'brier', scope='nocm'); add(f'8.8 noCM {arm}−BLIND_RECAL ioi', arm, 'BLIND_RECAL', 'ioi', scope='nocm')
    res['pairwise'] = pw
    res['ioi_floor'] = {}   # §8.6: COLLATZ и MODSQ-link — ни одна ветвь не даёт ИОИ ≤ 0,3 (с клеточным ИД)
    for c in ('HIVE-01/COLLATZ', 'LEVEL-04/MODSQ-link'):
        res['ioi_floor'][c] = {}
        for arm in ARMS:
            pt = val(sc, arm, c, 'ioi')
            if pt is None: continue
            vals = [val(b, arm, c, 'ioi') for b in boots]
            res['ioi_floor'][c][arm] = dict(ioi=pt, ci95=ci(vals), at_or_below_0_3=pt <= SEC['ioi_floor'])
    # прямые пары BLIND (§8.9): позиционный сдвиг с бутстреп-ИД по парам; pair-AUC по прямым парам против pair-AUC из p BLIND на тех же парах
    pkf = os.path.join(D, 'pairs_key.json'); pk = json.load(open(pkf))['pairs'] if os.path.exists(pkf) else []
    pr = out.get('PAIR') or {}; shifts, pauc, pauc_p, nmiss = [], [], [], 0
    for q in pk:
        ab, ba = pr.get(f"{q['pid']}:AB"), pr.get(f"{q['pid']}:BA")
        pa_, pb_ = (ab or {}).get('pref_a'), (ba or {}).get('pref_a')
        if num(pa_) is None or num(pb_) is None: nmiss += 1; continue
        a1, a2 = clip(num(pa_)), clip(num(pb_)); shifts.append((a1 + a2 - 1) / 2)
        if not q['same']:
            pc = (a1 + (1 - a2)) / 2; ya = y.get(q['a']); pc = pc if ya else 1 - pc; pauc.append(1.0 if pc > 0.5 else 0.5 if pc == 0.5 else 0.0)
            if 'BLIND' in ARMS and q['a'] in P and q['b'] in P:
                pa, pb = P[q['a']]['BLIND'], P[q['b']]['BLIND']; pref = 0.5 if pa + pb == 0 else pa / (pa + pb); pc2 = pref if ya else 1 - pref
                pauc_p.append(1.0 if pc2 > 0.5 else 0.5 if pc2 == 0.5 else 0.0)
    rng2 = random.Random(BSEED + 1); bshift, bauc = [], []
    for _ in range(NB):
        if shifts: bshift.append(st.mean(rng2.choice(shifts) for _ in shifts))
        if pauc: bauc.append(st.mean(rng2.choice(pauc) for _ in pauc))
    res['direct_pairs'] = dict(n=len(shifts), n_pairs_key=len(pk), missing_pairs=nmiss, n_diff=len(pauc),
                               shift_mean=(st.mean(shifts) if shifts else None), shift_ci95=ci(bshift), shift_abs_mean=(st.mean(abs(s) for s in shifts) if shifts else None),
                               pair_auc=(st.mean(pauc) if pauc else None), pair_auc_ci95=ci(bauc), pair_auc_from_p_same_pairs=(st.mean(pauc_p) if pauc_p else None))
    # сухой прогон: вырождение SC-3 и промптов совета по правилу §9 (сырые p, без подстановки)
    if dry:
        def rawp(rk, a):
            r = (out.get(rk) or {}).get(a); p = num(r.get('p_correct')) if isinstance(r, dict) else None; return clip(p) if p is not None else None
        trip = [(rawp('RC1', a), rawp('RC2', a), rawp('RC3', a)) for a in aliases]
        both = sum(1 for r1, r2, r3 in trip if None not in (r1, r2, r3) and abs(r2 - r1) < 0.05 and abs(r3 - r1) < 0.05)
        def near(rk):
            return sum(1 for a in aliases if rawp(rk, a) is not None and rawp('RC1', a) is not None and abs(rawp(rk, a) - rawp('RC1', a)) < 0.05)
        c2n, c3n = near(miss['raw_keys']['C2']), near(miss['raw_keys']['C3'])
        res['degeneracy'] = dict(n=len(aliases), sc3_rc2_rc1=sum(1 for r1, r2, _ in trip if None not in (r1, r2) and abs(r2 - r1) < 0.05),
                                 sc3_rc3_rc1=sum(1 for r1, _, r3 in trip if None not in (r1, r3) and abs(r3 - r1) < 0.05), sc3_both=both, c2_vs_rc1=c2n, c3_vs_rc1=c3n,
                                 drop_sc3=bool(present['SC3'] and both >= DEGEN), swap_c2=bool(present['C2'] and c2n >= DEGEN), swap_c3=bool(present['C3'] and c3n >= DEGEN),
                                 rule=f'≥ {DEGEN} из {len(aliases)} при |Δp| < 0,05 (для SC-3 — обе разности у одной тройки) → вырождено')
    # вердикты (§ PREREG)
    v = {}
    g = lambda d, k: (d or {}).get(k)
    def ci_excl0_neg(dd): return bool(dd and dd['ci95'] and dd['ci95'][1] < 0)
    def ci_excl0_pos(dd): return bool(dd and dd['ci95'] and dd['ci95'][0] > 0)
    dq = {arm: bool((res['item_cut'].get(arm) or {}).get('conf_wrong') is not None and res['item_cut'][arm]['conf_wrong'] > DISQ) for arm in ARMS}
    v['disqualified'] = dq; v['disqualified_rule'] = 'доля p ≥ 0,8 на неверных > 0,20 по всей выборке; применяется к ветви, не к её компонентам'
    # семейство Холма {P1′ (Брайер), P3 (ИОИ), P4 (log-отношение R у COUNCIL и ABSTAIN — p = max двух)}
    p1 = res['vs_recal'].get('RECOMPUTE', {}).get('brier'); t1 = res['vs_raw_T'].get('RECOMPUTE'); p3 = res['vs_recal'].get('ABSTAIN', {})
    p4c, p4a = res['R_ratio'].get('COUNCIL'), res['R_ratio'].get('ABSTAIN')
    # p двустороннее бутстреп; если точечная оценка не в предсказанную сторону (Брайер/ИОИ не ниже базы, отношение R не ≤ 0,5) — p := 1, чтобы Холм не «отклонял» в чужую сторону
    def dirp(d, key, ok): return None if not d or d.get(key) is None else (d[key] if ok else 1.0)
    p1p = dirp(p1, 'p_boot', bool(p1 and p1['point'] < 0)); p3p = dirp(p3.get('ioi'), 'p_boot', bool(p3.get('ioi') and p3['ioi']['point'] < 0))
    p4p = max(dirp(p4c, 'p_boot_vs_half', p4c['point'] <= R_RATIO), dirp(p4a, 'p_boot_vs_half', p4a['point'] <= R_RATIO)) if (p4c and p4a and p4c.get('p_boot_vs_half') is not None and p4a.get('p_boot_vs_half') is not None) else None
    v['holm'] = holm({'P1_brier': p1p, 'P3_ioi': p3p, 'P4_ratio': p4p}); H = v['holm']['table']
    v['holm']['rule'] = 'семейство {P1′ Брайер, P3 ИОИ, P4 log-отношение R (max p по COUNCIL и ABSTAIN)}; p двустороннее бутстреп, при точечной оценке не в предсказанную сторону p := 1; α = 0,05, первый шаг 0,05/3'
    ok1 = bool(p1 and t1 and p1['point'] <= -MDE_BRIER and ci_excl0_neg(p1) and t1['point'] >= MDE_T and ci_excl0_pos(t1))
    v['P1'] = dict(brier_diff=p1, T_diff=t1, ok_ci=ok1, holm_reject=H['P1_brier']['reject'], disqualified=dq.get('RECOMPUTE'), ok=ok1 and H['P1_brier']['reject'] and not dq.get('RECOMPUTE'))
    ab = res['main_cut'].get('ABSTAIN') or {}; bl = res['main_cut'].get('BLIND') or {}
    fail3 = (ab.get('abstain', 0) > ABST_MAX) or (bl.get('auc') is not None and ab.get('auc') is not None and ab['auc'] < bl['auc'] - AUC_DROP)
    ok3 = bool(not fail3 and p3.get('ioi') and p3['ioi']['point'] <= -MDE_IOI and ci_excl0_neg(p3['ioi']) and p3.get('brier') and ci_excl0_neg(p3['brier']))
    v['P3'] = dict(ioi_diff=p3.get('ioi'), brier_diff=p3.get('brier'), abstain=ab.get('abstain'), fail=fail3, ok_ci=ok3, holm_reject=H['P3_ioi']['reject'], disqualified=dq.get('ABSTAIN'),
                   ok=ok3 and H['P3_ioi']['reject'] and not dq.get('ABSTAIN'))
    def p4(arm):
        r = res['R_ratio'].get(arm); okr = bool(r and r['ci95'] and r['ci95'][1] <= R_RATIO)
        return dict(ratio=r, ok_ratio=okr, disqualified=dq.get(arm), ok=okr and not dq.get(arm))
    v['P4'] = {arm: p4(arm) for arm in ('COUNCIL', 'ABSTAIN', 'RECOMPUTE', 'DEBATE', 'SC3') if arm in ARMS}
    v['P4']['compound'] = dict(p_boot=p4p, holm_reject=H['P4_ratio']['reject'],
                               ok=bool(g(v['P4'].get('COUNCIL'), 'ok') and g(v['P4'].get('ABSTAIN'), 'ok') and 'RECOMPUTE' in v['P4'] and not v['P4']['RECOMPUTE']['ok_ratio'] and H['P4_ratio']['reject']),
                               rule='≤ 0,5 у COUNCIL и ABSTAIN (без дисквалификации), не у RECOMPUTE; p-значение = max(p COUNCIL, p ABSTAIN) проходит Холма')
    def c1a(arm):  # критерий 1(а) §6а
        r = res['R_ratio'].get(arm); okr = bool(r and r['ci95'] and r['ci95'][1] <= R_RATIO)
        pa, pb = res['pair_auc_main'].get(arm), res['pair_auc_main'].get('BLIND'); aa, abl = g(res['main_cut'].get(arm), 'auc'), g(res['main_cut'].get('BLIND'), 'auc')
        pair_ok = bool(pa is not None and pb is not None and pa >= pb - PAIR_AUC_DROP); auc_ok = bool(aa is not None and abl is not None and aa >= abl - PAIR_AUC_DROP)
        return dict(ratio=r, ratio_ok=okr, pair_auc=pa, pair_auc_blind=pb, pair_auc_ok=pair_ok, auc=aa, auc_blind=abl, auc_ok=auc_ok, disqualified=dq.get(arm), achieved=okr and pair_ok and auc_ok and not dq.get(arm))
    v['criterion1_a'] = {arm: c1a(arm) for arm in ('RECOMPUTE', 'SC3', 'ABSTAIN', 'COUNCIL', 'DEBATE') if arm in ARMS}
    def c1b(arm):  # критерий 1(б) §6б: верхняя граница ИД отношения ИОИ < 0,5 и Брайер лучше базы (ИД < 0) и T выше сырого BLIND (точечно), без дисквалификации
        r = res['ioi_ratio_vs_recal'].get(arm); okr = bool(r and r['ci95'] and r['ci95'][1] < 0.5)
        bok = ci_excl0_neg(res['vs_recal'].get(arm, {}).get('brier')); tok = bool(res['vs_raw_T'].get(arm) and res['vs_raw_T'][arm]['point'] > 0)
        return dict(ratio=r, ratio_ok=okr, brier_ok=bok, T_ok=tok, disqualified=dq.get(arm), achieved=okr and bok and tok and not dq.get(arm))
    v['criterion1_b'] = {arm: c1b(arm) for arm in ('RECOMPUTE', 'SC3', 'ABSTAIN', 'COUNCIL', 'DEBATE') if arm in ARMS}
    v['stage2_trigger'] = None
    cd = res['vs_recal'].get('COUNCIL', {}).get('brier')
    if cd and cd['ci95']:
        failed = cd['ci95'][0] > 0   # разность = COUNCIL − BLIND_RECAL; провал, если ИД целиком > 0 (Брайер: меньше — лучше)
        v['stage2_trigger'] = dict(council_brier_diff=cd, stage1_failed=failed, disqualified=dq.get('COUNCIL'), run_stage2=bool(not failed and not dq.get('COUNCIL')))
    v['noans_cells'] = {c: dict(noans_ioi=g(res['by_cell'][c].get('NOANS'), 'ioi'), rec_ioi=g(res['by_cell'][c].get('RECOMPUTE'), 'ioi'),
                                unverifiable=bool(g(res['by_cell'][c].get('NOANS'), 'ioi') is not None and g(res['by_cell'][c].get('RECOMPUTE'), 'ioi') is not None and res['by_cell'][c]['NOANS']['ioi'] <= res['by_cell'][c]['RECOMPUTE']['ioi'] + NOANS_MARGIN)) for c in big if c in res['by_cell']}
    res['verdicts'] = v
    dst = os.path.join(D, 'dry_analysis.json' if dry else 'analysis.json'); json.dump(res, open(dst, 'w'), ensure_ascii=False, indent=1)
    r3 = lambda x: None if x is None else round(x, 3)
    print(f"{'сухой прогон' if dry else 'основной'}: элементов {len(aliases)}; пропуски (сырые ветви) {res['missing']}; подставлено 0,5 (по ветвям анализа) {res['imputed']}")
    for arm in ARMS:
        m = res['main_cut'].get(arm); i = res['item_cut'].get(arm)
        if m: print(f"{arm:12s} главный разрез: T {m['T']:.3f} C {m['C']:.3f} Брайер {m['brier']:.3f} ИОИ {m['ioi']:.3f} AUC {r3(m.get('auc'))} возд. {m['abstain']:.2f} | по элементам: ИОИ {i['ioi']:.3f} Брайер {i['brier']:.3f} | R {r3(res['R_main'].get(arm))}")
    for k in ('P1', 'P3', 'stage2_trigger'): print(k, json.dumps(v[k], ensure_ascii=False)[:400])
    print('Холм', json.dumps(v['holm'], ensure_ascii=False))
    print('P4', {a: (d['ok'], d['ratio'] and (r3(d['ratio']['point']), d['ratio']['ci95'] and [r3(x) for x in d['ratio']['ci95']])) if a != 'compound' else d['ok'] for a, d in v['P4'].items()})
    print('критерий 1(а):', {a: d['achieved'] for a, d in v['criterion1_a'].items()})
    print('критерий 1(б) отношение ИОИ к перекалиброванному BLIND:', {a: (d['achieved'], d['ratio'] and (r3(d['ratio']['point']), d['ratio']['ci95'] and [r3(x) for x in d['ratio']['ci95']])) for a, d in v['criterion1_b'].items()})
    print('дисквалификация:', dq); print('прямые пары:', {k: (r3(x) if isinstance(x, float) else x) for k, x in res['direct_pairs'].items()})
    print('вторичные:', {k: (r3(e['point']), e['ci95'] and [r3(x) for x in e['ci95']], e.get('verdict')) for k, e in pw.items() if e and not k.startswith('8.8')})
    if dry: print('вырождение:', res['degeneracy'])
    return res


if __name__ == '__main__':
    if sys.argv[1] == 'build': build(no_sc3='--no-sc3' in sys.argv, c2b='--c2b' in sys.argv, c3b='--c3b' in sys.argv)
    else: analyze(sys.argv[2], dry='--dry' in sys.argv)
