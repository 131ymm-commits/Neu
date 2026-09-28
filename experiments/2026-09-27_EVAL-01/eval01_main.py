# EVAL-01, основной прогон: выборка, задания судьям, анализ. Дизайн — совет 11 (ред. 3) + требования Левого (явная МДЭ, честный n) и Скептика
# (единая формула R для всех ветвей; правило стадии 2) + уступленное предложение Правого (дебаты как контроль). Правда — вне репозитория.
#   python3 eval01_main.py build [--no-sc3] [--c2b] [--c3b]   → main/sample_key.json, main/jobs.json, main/pairs.json, main/eval01_main.js, main/eval01_dry.js
#   python3 eval01_main.py analyze main/out.json [--dry]       → main/analysis.json (или main/dry_analysis.json)
import json, os, sys, random, math, statistics as st, itertools
HERE = os.path.dirname(os.path.abspath(__file__)); D = os.path.join(HERE, 'main'); os.makedirs(D, exist_ok=True)
TRUTH = '/root/eval_secret/truth.json'; SEED = 2810
NO = 'Не используй никакие инструменты и не открывай файлы: суди сам, опираясь только на текст ниже.'
BIG = [('HIVE-01', 'TWIN'), ('HIVE-01', 'COLLATZ'), ('HIVE-01', 'SUB5'), ('LEVEL-04', 'MODSQ-link')]
SMALL = {('HIVE-01', 'COL3'): 5, ('HIVE-01', 'PART'): 4, ('DIV-01', 'TWIN'): 4}
DRY_PLAN = {('HIVE-01', 'TWIN'): (2, 1), ('HIVE-01', 'COLLATZ'): (1, 2), ('HIVE-01', 'SUB5'): (2, 0), ('LEVEL-04', 'MODSQ-link'): (1, 1)}  # (верных, неверных); у SUB5 все 16 неверных ушли в основную выборку
ARMS1 = ['BLIND', 'RC1', 'RC2', 'RC3', 'ABSTAIN', 'C2', 'C3', 'NOANS', 'DEB_PRO', 'DEB_DEF']
# пороги и параметры анализа (фиксируются в PREREG)
LAM, CABST = 0.7, 0.15            # перекалибровка BLIND по сетке пилота (pilot/mde_pilot.json: лучший Брайер при воздержаниях ≤ 0,3)
MDE_BRIER, MDE_T, MDE_IOI = 0.05, 0.07, 0.10
R_RATIO, DISQ, AUC_DROP, ABST_MAX, NOANS_MARGIN = 0.5, 0.20, 0.05, 0.5, 0.05
B, BSEED = 2000, 0
sys.path.insert(0, HERE)
from eval01_pilot import target_of, label, render, criterion, auc   # те же правила мишени и рендеринга, что в пилоте


def cell_of(it): return f"{it['source']}/{it['family']}"


def build(no_sc3=False, c2b=False, c3b=False):
    items = [json.loads(l) for l in open(os.path.join(HERE, 'data', 'items_public.jsonl'))]; truth = json.load(open(TRUTH))
    pilot_ids = set(json.load(open(os.path.join(HERE, 'pilot', 'sample_key.json')))['ids'])
    rng = random.Random(SEED); cells = {}
    for it in items:
        if it['leak_note'] or it['id'] in pilot_ids: continue
        cells.setdefault((it['source'], it['family']), []).append(it)
    def take(key, n_good, n_bad, exclude=()):
        pool = [x for x in cells[key] if x['id'] not in exclude]; rng.shuffle(pool)
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
               cells={aliases[it['id']]: cell_of(it) for it in sample + dry}, arms=dict(no_sc3=no_sc3, c2b=c2b, c3b=c3b), lam=LAM, c_abst=CABST)
    json.dump(key, open(os.path.join(D, 'sample_key.json'), 'w'), ensure_ascii=False, indent=1)
    arms = [a for a in ARMS1 if not (no_sc3 and a in ('RC2', 'RC3'))]
    arms = ['C2B' if (a == 'C2' and c2b) else 'C3B' if (a == 'C3' and c3b) else a for a in arms]
    def jobs_for(lst): return [dict(alias=aliases[it['id']], arm=arm, task=it['task'], answer=render(it, with_note=False), criterion=criterion(it)) for it in lst for arm in arms]
    jobs, djobs = jobs_for(sample), jobs_for(dry)
    # прямые пары BLIND: 4 больших клетки, 50 пар одного класса + 50 разных классов, оба порядка
    by_cell = {}
    for it in sample:
        if (it['source'], it['family']) in BIG: by_cell.setdefault(cell_of(it), []).append(it)
    same, diff = [], []
    for c, lst in sorted(by_cell.items()):
        for a, b in itertools.combinations(lst, 2): (same if label(a, truth) == label(b, truth) else diff).append((a, b))
    rng.shuffle(same); rng.shuffle(diff); chosen = same[:50] + diff[:50]
    pairs = []
    for k, (a, b) in enumerate(chosen):
        pid = f'p{k:03d}'
        pairs.append(dict(pid=pid, order='AB', task=a['task'], criterion=criterion(a), a=render(a, False), b=render(b, False)))
        pairs.append(dict(pid=pid, order='BA', task=a['task'], criterion=criterion(a), a=render(b, False), b=render(a, False)))
    json.dump(dict(pairs=[dict(pid=f'p{k:03d}', a=aliases[a['id']], b=aliases[b['id']], same=label(a, truth) == label(b, truth)) for k, (a, b) in enumerate(chosen)]), open(os.path.join(D, 'pairs_key.json'), 'w'), ensure_ascii=False, indent=1)
    json.dump(jobs, open(os.path.join(D, 'jobs.json'), 'w'), ensure_ascii=False); json.dump(djobs, open(os.path.join(D, 'jobs_dry.json'), 'w'), ensure_ascii=False)
    src = open(os.path.join(HERE, 'eval01_main_step.js')).read()
    mk = lambda J, P: src.replace('const JOBS = null', 'const JOBS = ' + json.dumps(J, ensure_ascii=False)).replace('const PAIRS = null', 'const PAIRS = ' + json.dumps(P, ensure_ascii=False)).replace('const NO = null', 'const NO = ' + json.dumps(NO, ensure_ascii=False))
    open(os.path.join(D, 'eval01_main.js'), 'w').write(mk(jobs, pairs))
    open(os.path.join(D, 'eval01_dry.js'), 'w').write(mk(djobs, []).replace("name: 'eval01-main'", "name: 'eval01-dry'"))
    n_arb = len(sample)
    print(f'выборка {len(sample)} (верных {sum(label(x, truth) for x in sample)}), сухой прогон {len(dry)}; ветви {arms}; вызовов: основной {len(jobs)} + арбитры {n_arb} + пары {len(pairs)} = {len(jobs) + n_arb + len(pairs)}; сухой {len(djobs) + len(dry)}')


# ---------- анализ ----------
def clip(p): return min(1.0, max(0.0, float(p)))
def recal(p, lam=LAM, c=CABST): q = 0.5 + lam * (p - 0.5); return 0.5 if abs(q - 0.5) < c else q
def half_T(p, y): return 0.5 if p == 0.5 else float((p > 0.5) == y)
def metrics(ps):  # ps: [(p, y)]
    if not ps: return None
    T = st.mean(half_T(p, y) for p, y in ps); C = st.mean(max(p, 1 - p) for p, _ in ps)
    return dict(n=len(ps), T=T, C=C, brier=st.mean((p - y) ** 2 for p, y in ps), ioi=(1 - T) + max(0, C - T), auc=auc(ps), abstain=st.mean(p == 0.5 for p, _ in ps),
                conf_wrong=(st.mean(p >= 0.8 for p, y in ps if not y) if any(not y for _, y in ps) else None))
def rstat(ps):  # единая формула для всех ветвей: pref = pA/(pA+pB) по всем парам внутри клетки
    same, diffs, aucs = [], [], []
    for (pa, ya), (pb, yb) in itertools.combinations(ps, 2):
        pref = 0.5 if pa + pb == 0 else pa / (pa + pb)
        if ya == yb: same.append(abs(pref - 0.5))
        else:
            diffs.append(abs(pref - 0.5)); pc = pref if ya else 1 - pref; aucs.append(1.0 if pc > 0.5 else 0.5 if pc == 0.5 else 0.0)
    if not same or not diffs: return None
    ds, dd = st.mean(same), st.mean(diffs); return dict(D_same=ds, D_diff=dd, R=(ds / dd if dd > 0 else None), pair_auc=st.mean(aucs))


def arm_probs(out, key, arms_used):
    """p по ветвям на элемент; производные ветви: RECOMPUTE=RC1, SC3=среднее RC*, COUNCIL=среднее(RC1, C2|C2B, C3|C3B), BLIND_RECAL, ABSTAIN (can_verify=false→0,5), DEBATE=DEB_ARB."""
    P = {}
    def get(arm, a):
        r = (out.get(arm) or {}).get(a)
        return clip(r['p_correct']) if r and isinstance(r.get('p_correct'), (int, float)) else None
    c2 = 'C2B' if 'C2B' in arms_used else 'C2'; c3 = 'C3B' if 'C3B' in arms_used else 'C3'
    for a in key['aliases'].values():
        d = {}
        d['BLIND'] = get('BLIND', a); d['BLIND_RECAL'] = recal(d['BLIND']) if d['BLIND'] is not None else None
        d['RECOMPUTE'] = get('RC1', a)
        rcs = [x for x in (get('RC1', a), get('RC2', a), get('RC3', a)) if x is not None]
        d['SC3'] = st.mean(rcs) if len(rcs) == 3 else None
        r = (out.get('ABSTAIN') or {}).get(a)
        d['ABSTAIN'] = (0.5 if (r.get('can_verify') is False) else clip(r['p_correct'])) if r and isinstance(r.get('p_correct'), (int, float)) else None
        d['C2'] = get(c2, a); d['C3'] = get(c3, a)
        cs = [x for x in (d['RECOMPUTE'], d['C2'], d['C3']) if x is not None]; d['COUNCIL'] = st.mean(cs) if len(cs) == 3 else None
        d['NOANS'] = get('NOANS', a); d['DEBATE'] = get('DEB_ARB', a)
        P[a] = d
    return P


def analyze(path, dry=False):
    key = json.load(open(os.path.join(D, 'sample_key.json'))); truth = json.load(open(TRUTH))
    items = {it['id']: it for it in (json.loads(l) for l in open(os.path.join(HERE, 'data', 'items_public.jsonl')))}
    out = json.load(open(path)); out = out.get('out', out)
    ids = key['dry_ids'] if dry else key['ids']; al = key['aliases']; cells = key['cells']
    y = {al[i]: label(items[i], truth) for i in ids}
    arms_used = sorted(out.keys()); P = arm_probs(out, key, arms_used)
    ARMS = ['BLIND', 'BLIND_RECAL', 'RECOMPUTE', 'SC3', 'ABSTAIN', 'C2', 'C3', 'COUNCIL', 'NOANS', 'DEBATE']
    big = [f'{s}/{f}' for s, f in BIG]; aliases = [al[i] for i in ids]
    by_cell = {}
    for a in aliases: by_cell.setdefault(cells[a], []).append(a)
    def cut(arm, al_list): return [(P[a][arm], y[a]) for a in al_list if P[a][arm] is not None]
    def main_cut(arm, sample=None):  # среднее по 4 большим клеткам (главный разрез), при бутстрепе sample — {cell: [alias...]}
        ms = [metrics(cut(arm, (sample or by_cell).get(c, []))) for c in big]; ms = [m for m in ms if m]
        return {k: st.mean(m[k] for m in ms) for k in ('T', 'C', 'brier', 'ioi', 'auc', 'abstain') if all(m[k] is not None for m in ms)} if ms else None
    res = dict(n_items=len(aliases), arms_present=arms_used, missing={arm: sum(P[a][arm] is None for a in aliases) for arm in ARMS})
    res['item_cut'] = {arm: metrics(cut(arm, aliases)) for arm in ARMS}
    res['main_cut'] = {arm: main_cut(arm) for arm in ARMS}
    res['by_cell'] = {c: {arm: metrics(cut(arm, lst)) for arm in ARMS} for c, lst in by_cell.items()}
    res['R'] = {arm: {c: rstat(cut(arm, by_cell[c])) for c in big if c in by_cell} for arm in ARMS}
    def R_mean(arm, sample=None):
        rs = [rstat(cut(arm, (sample or by_cell).get(c, []))) for c in big]; rs = [r for r in rs if r and r['R'] is not None]
        return st.mean(r['R'] for r in rs) if rs else None
    res['R_main'] = {arm: R_mean(arm) for arm in ARMS}
    # бутстреп: элементы внутри клеток, парно по элементу
    rng = random.Random(BSEED); boots = []
    for _ in range(B if not dry else 200):
        s = {c: [rng.choice(lst) for _ in lst] for c, lst in by_cell.items()}
        row = {}
        for arm in ARMS:
            m = main_cut(arm, s); row[arm] = m
        row['R'] = {arm: R_mean(arm, s) for arm in ARMS}
        boots.append(row)
    def ci(vals):
        v = sorted(x for x in vals if x is not None)
        return [v[int(0.025 * len(v))], v[min(len(v) - 1, int(0.975 * len(v)))]] if len(v) > 20 else None
    def diff(arm, ref, k):
        base = res['main_cut']
        if not base.get(arm) or not base.get(ref) or base[arm].get(k) is None or base[ref].get(k) is None: return None
        vals = [(b[arm][k] - b[ref][k]) for b in boots if b.get(arm) and b.get(ref) and b[arm].get(k) is not None and b[ref].get(k) is not None]
        return dict(point=base[arm][k] - base[ref][k], ci95=ci(vals))
    res['vs_recal'] = {arm: {k: diff(arm, 'BLIND_RECAL', k) for k in ('brier', 'ioi', 'auc')} for arm in ARMS if arm not in ('BLIND', 'BLIND_RECAL')}
    res['vs_raw_T'] = {arm: diff(arm, 'BLIND', 'T') for arm in ARMS if arm != 'BLIND'}
    def ratio(arm):
        if res['R_main'].get(arm) is None or not res['R_main'].get('BLIND'): return None
        vals = [b['R'][arm] / b['R']['BLIND'] for b in boots if b['R'].get(arm) is not None and b['R'].get('BLIND')]
        return dict(point=res['R_main'][arm] / res['R_main']['BLIND'], ci95=ci(vals))
    res['R_ratio'] = {arm: ratio(arm) for arm in ARMS if arm != 'BLIND'}
    res['ioi_ratio_vs_recal'] = {}
    for arm in ARMS:
        if arm in ('BLIND', 'BLIND_RECAL') or not res['main_cut'].get(arm): continue
        vals = [b[arm]['ioi'] / b['BLIND_RECAL']['ioi'] for b in boots if b.get(arm) and b.get('BLIND_RECAL') and b[arm].get('ioi') is not None and b['BLIND_RECAL'].get('ioi', 0) > 0]
        res['ioi_ratio_vs_recal'][arm] = dict(point=res['main_cut'][arm]['ioi'] / res['main_cut']['BLIND_RECAL']['ioi'], ci95=ci(vals))
    # прямые пары: позиционный сдвиг BLIND (описательно)
    pk = json.load(open(os.path.join(D, 'pairs_key.json')))['pairs'] if os.path.exists(os.path.join(D, 'pairs_key.json')) else []
    pr = out.get('PAIR') or {}; shifts = []; pauc = []
    for q in pk:
        ab, ba = pr.get(f"{q['pid']}:AB"), pr.get(f"{q['pid']}:BA")
        if not ab or not ba: continue
        a1, a2 = clip(ab['pref_a']), clip(ba['pref_a']); shifts.append((a1 + a2 - 1) / 2)
        if not q['same']:
            pc = (a1 + (1 - a2)) / 2; ya = y.get(q['a']); pc = pc if ya else 1 - pc; pauc.append(1.0 if pc > 0.5 else 0.5 if pc == 0.5 else 0.0)
    res['direct_pairs'] = dict(n=len(shifts), shift_mean=(st.mean(shifts) if shifts else None), shift_abs_mean=(st.mean(abs(s) for s in shifts) if shifts else None), pair_auc=(st.mean(pauc) if pauc else None))
    # сухой прогон: вырождение SC-3 и промптов совета
    if dry:
        def near(a1, a2): return sum(1 for a in aliases if P[a][a1] is not None and P[a][a2] is not None and abs(P[a][a1] - P[a][a2]) < 0.05)
        res['degeneracy'] = dict(sc3_rc2_rc1=sum(1 for a in aliases if (out.get('RC2') or {}).get(a) and P[a]['RECOMPUTE'] is not None and abs(clip(out['RC2'][a]['p_correct']) - P[a]['RECOMPUTE']) < 0.05),
                                 sc3_rc3_rc1=sum(1 for a in aliases if (out.get('RC3') or {}).get(a) and P[a]['RECOMPUTE'] is not None and abs(clip(out['RC3'][a]['p_correct']) - P[a]['RECOMPUTE']) < 0.05),
                                 c2_vs_rc1=near('C2', 'RECOMPUTE'), c3_vs_rc1=near('C3', 'RECOMPUTE'), n=len(aliases), rule='≥ 8 из 10 при |Δp| < 0,05 → вырождено')
    # вердикты (§ PREREG)
    v = {}
    g = lambda d, k: (d or {}).get(k)
    def ci_excl0_neg(dd): return dd and dd['ci95'] and dd['ci95'][1] < 0
    def ci_excl0_pos(dd): return dd and dd['ci95'] and dd['ci95'][0] > 0
    p1 = res['vs_recal'].get('RECOMPUTE', {}).get('brier'); t1 = res['vs_raw_T'].get('RECOMPUTE')
    v['P1'] = dict(brier_diff=p1, T_diff=t1, ok=bool(p1 and t1 and p1['point'] <= -MDE_BRIER and ci_excl0_neg(p1) and t1['point'] >= MDE_T and ci_excl0_pos(t1)))
    ab = res['main_cut'].get('ABSTAIN') or {}; bl = res['main_cut'].get('BLIND') or {}; p3 = res['vs_recal'].get('ABSTAIN', {})
    fail3 = (ab.get('abstain', 0) > ABST_MAX) or (bl.get('auc') is not None and ab.get('auc') is not None and ab['auc'] < bl['auc'] - AUC_DROP)
    v['P3'] = dict(ioi_diff=p3.get('ioi'), brier_diff=p3.get('brier'), abstain=ab.get('abstain'), fail=fail3,
                   ok=bool(not fail3 and p3.get('ioi') and p3['ioi']['point'] <= -MDE_IOI and ci_excl0_neg(p3['ioi']) and p3.get('brier') and ci_excl0_neg(p3['brier'])))
    v['P4'] = {arm: dict(ratio=res['R_ratio'].get(arm), ok=bool(res['R_ratio'].get(arm) and res['R_ratio'][arm]['ci95'] and res['R_ratio'][arm]['ci95'][1] <= R_RATIO)) for arm in ('COUNCIL', 'ABSTAIN', 'RECOMPUTE', 'DEBATE', 'SC3')}
    v['disqualified'] = {arm: bool((res['item_cut'].get(arm) or {}).get('conf_wrong') is not None and res['item_cut'][arm]['conf_wrong'] > DISQ) for arm in ARMS}
    v['stage2_trigger'] = None
    cd = res['vs_recal'].get('COUNCIL', {}).get('brier')
    if cd and cd['ci95']: v['stage2_trigger'] = dict(council_brier_diff=cd, stage1_failed=cd['ci95'][0] > 0, run_stage2=not (cd['ci95'][0] > 0))
    v['criterion1_b'] = {arm: dict(ratio=res['ioi_ratio_vs_recal'].get(arm), achieved=bool(res['ioi_ratio_vs_recal'].get(arm) and res['ioi_ratio_vs_recal'][arm]['ci95'] and res['ioi_ratio_vs_recal'][arm]['ci95'][1] < 0.5)) for arm in ('RECOMPUTE', 'SC3', 'ABSTAIN', 'COUNCIL', 'DEBATE')}
    v['noans_cells'] = {c: dict(noans_ioi=g(res['by_cell'][c].get('NOANS'), 'ioi'), rec_ioi=g(res['by_cell'][c].get('RECOMPUTE'), 'ioi'),
                                unverifiable=bool(g(res['by_cell'][c].get('NOANS'), 'ioi') is not None and g(res['by_cell'][c].get('RECOMPUTE'), 'ioi') is not None and res['by_cell'][c]['NOANS']['ioi'] <= res['by_cell'][c]['RECOMPUTE']['ioi'] + NOANS_MARGIN)) for c in big if c in res['by_cell']}
    res['verdicts'] = v
    dst = os.path.join(D, 'dry_analysis.json' if dry else 'analysis.json'); json.dump(res, open(dst, 'w'), ensure_ascii=False, indent=1)
    print(f"{'сухой прогон' if dry else 'основной'}: элементов {len(aliases)}; пропуски {res['missing']}")
    for arm in ARMS:
        m = res['main_cut'].get(arm); i = res['item_cut'].get(arm)
        if m: print(f"{arm:12s} главный разрез: T {m['T']:.3f} C {m['C']:.3f} Брайер {m['brier']:.3f} ИОИ {m['ioi']:.3f} AUC {m.get('auc') if m.get('auc') is None else round(m['auc'], 3)} возд. {m['abstain']:.2f} | по элементам: ИОИ {i['ioi']:.3f} Брайер {i['brier']:.3f} | R {res['R_main'].get(arm) and round(res['R_main'][arm], 3)}")
    for k, d in v.items():
        if k in ('P1', 'P3', 'stage2_trigger', 'direct'): print(k, json.dumps(d, ensure_ascii=False)[:400])
    print('P4', {a: (d['ok'], d['ratio'] and (round(d['ratio']['point'], 3), d['ratio']['ci95'] and [round(x, 3) for x in d['ratio']['ci95']])) for a, d in v['P4'].items()})
    print('критерий 1(б) отношение ИОИ к перекалиброванному BLIND:', {a: (d['achieved'], d['ratio'] and (round(d['ratio']['point'], 3), d['ratio']['ci95'] and [round(x, 3) for x in d['ratio']['ci95']])) for a, d in v['criterion1_b'].items()})
    print('дисквалификация:', v['disqualified']); print('прямые пары:', res['direct_pairs'])
    if dry: print('вырождение:', res['degeneracy'])
    return res


if __name__ == '__main__':
    if sys.argv[1] == 'build': build(no_sc3='--no-sc3' in sys.argv, c2b='--c2b' in sys.argv, c3b='--c3b' in sys.argv)
    else: analyze(sys.argv[2], dry='--dry' in sys.argv)
