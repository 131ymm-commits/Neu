"""HOR-03 — сертификаты чтения: P-U12 («сошлось, но не по Пуассону») на телеграфе со сменой пребывания на середине; P-U14 («скачок = зазор») на реальных рядах HOR-02. По PREREG 2026-09-09."""
import numpy as np, json, os, sys, time, warnings
warnings.filterwarnings('ignore'); sys.path.insert(0, '/home/claude')
from hor02_lib import analyze, telegraph
from zeta01_lib import embed
B = '/home/claude'; OUT = f'{B}/hor03_results.json'; res = json.load(open(OUT)) if os.path.exists(OUT) else {}; t0 = time.time()
def switch_telegraph(n, L1, L2, rng, noise=0.3):
    x1, s1 = telegraph(n // 2, L1, rng, noise=0.0); x2, s2 = telegraph(n - n // 2, L2, rng, noise=0.0)
    if s2[0] == s1[-1]: s2 = -s2; x2 = -x2   # непрерывность: начать вторую половину с противоположного состояния не обязательно, но избежать искусственного скачка
    s = np.concatenate([s1, s2]); return s + noise * rng.normal(size=n), s
n = 8000
for L1, L2 in ((40, 320), (320, 40)):
    for s in range(10):
        name = f'sw_{L1}to{L2}_s{s}'
        if name in res: continue
        rng = np.random.default_rng(300000 + 1000 * L1 + s); x, h = switch_telegraph(n, L1, L2, rng); Fe = embed(x, 4)
        r = analyze(Fe, 1, 30, hidden=h[:len(Fe)]); r['group'] = f'sw_{L1}to{L2}'; r['L1'] = L1; r['L2'] = L2; res[name] = r; json.dump(res, open(OUT, 'w'), default=float)
        print(f"{name:18s} t1 преф {[None if v is None else round(v, 1) for v in r['t1_prefix']]} суф {[None if v is None else round(v, 1) for v in r['t1_suffix']]} N_c преф {r['nc_prefix']} суф {r['nc_suffix']} [{time.time()-t0:.0f}s]", flush=True)
# --- вердикты ---
h2 = json.load(open(f'{B}/hor02_results.json'))
def frac_nonpoisson(d):
    vals = []
    for v in d.values():
        for p in v['pairs']:
            if p['nc_m'] >= 30 and not (p['nc_m'] < 2 <= p['nc_2m']): vals.append(abs(p['beta']) >= 0.3)
    return (float(np.mean(vals)) if vals else None), len(vals)
def global_betas(v):
    """глобальные наклоны HOR-01 по префиксам и суффиксам (ln t₁ по ln n)"""
    out = []
    for tv in (v['t1_prefix'], v['t1_suffix']):
        ok = [i for i, t in enumerate(tv) if t is not None and t > 0]
        out.append(float(np.polyfit(np.log([v['hs'][i] for i in ok]), np.log([tv[i] for i in ok]), 1)[0]) if len(ok) >= 3 else None)
    return out
def disagree(d):
    vals = []
    for v in d.values():
        bp, bs = global_betas(v)
        if bp is not None and bs is not None: vals.append(abs(bp - bs) >= 0.3)
    return (float(np.mean(vals)) if vals else None), len(vals)
V = {}
fams = {'sw_40to320': {k: v for k, v in res.items() if v.get('group') == 'sw_40to320'}, 'sw_320to40': {k: v for k, v in res.items() if v.get('group') == 'sw_320to40'},
        'stat_40': {k: v for k, v in h2.items() if isinstance(v, dict) and v.get('group') == 'tel' and v.get('L') == 40}, 'stat_320': {k: v for k, v in h2.items() if isinstance(v, dict) and v.get('group') == 'tel' and v.get('L') == 320}}
V['PU12a'] = {f: dict(zip(('frac', 'n'), frac_nonpoisson(d))) for f, d in fams.items()}
V['PU12b'] = {f: dict(zip(('frac', 'n'), disagree(d))) for f, d in fams.items()}
# leave-one-seed-out для долей
loo = {}
for f, d in fams.items():
    seeds = sorted({v.get('seed', int(k.split('_s')[-1])) for k, v in d.items()}); fr = []
    for s in seeds:
        sub = {k: v for k, v in d.items() if v.get('seed', int(k.split('_s')[-1])) != s}; fr.append(frac_nonpoisson(sub)[0])
    loo[f] = [x for x in fr if x is not None]
V['PU12a_loo'] = {f: (min(x), max(x)) for f, x in loo.items() if x}
sw_ok = all(V['PU12a'][f]['frac'] is not None and V['PU12a'][f]['frac'] >= 0.35 for f in ('sw_40to320', 'sw_320to40')); st_ok = all(V['PU12a'][f]['frac'] is not None and V['PU12a'][f]['frac'] <= 0.2 for f in ('stat_40', 'stat_320'))
V['PU12a']['ok'] = bool(sw_ok and st_ok); V['K1'] = dict(hit=bool(any(V['PU12a'][f]['frac'] is not None and V['PU12a'][f]['frac'] <= 0.2 for f in ('sw_40to320', 'sw_320to40')) or any(V['PU12a'][f]['frac'] is not None and V['PU12a'][f]['frac'] >= 0.35 for f in ('stat_40', 'stat_320'))))
V['PU12b']['ok'] = bool(all(V['PU12b'][f]['frac'] >= 0.8 for f in ('sw_40to320', 'sw_320to40')) and all(V['PU12b'][f]['frac'] <= 0.3 for f in ('stat_40', 'stat_320'))); V['K2'] = dict(hit=bool(any(V['PU12b'][f]['frac'] <= 0.5 for f in ('sw_40to320', 'sw_320to40'))))
# P-U14 — реальные ряды HOR-02
rows = []
for k, v in h2.items():
    if not isinstance(v, dict) or v.get('group') not in ('real', 'eeg') or not v.get('t2_full'): continue
    sp = [p['beta'] for p in v['pairs'] if p['nc_m'] < 2 <= p['nc_2m']]
    if not sp: continue
    gap = float(np.log2(v['t1_full'] / v['t2_full'])); rows.append(dict(name=k, group=v['group'], N_c_full=v['N_c_full'], spike=float(np.median(sp)), n_spikes=len(sp), gap=gap, diff=float(np.median(sp)) - gap))
res_rows = [r_ for r_ in rows if r_['N_c_full'] >= 10]; unres_rows = [r_ for r_ in rows if r_['N_c_full'] < 10]
fr14 = float(np.mean([abs(r_['diff']) <= 1.5 for r_ in res_rows])) if res_rows else None; fr14big = float(np.mean([abs(r_['diff']) > 3 for r_ in res_rows])) if res_rows else None
V['PU14'] = dict(n_resolved=len(res_rows), frac_within_1p5=fr14, frac_over_3=fr14big, ok=bool(fr14 is not None and fr14 >= 0.6), rows_resolved=res_rows, rows_unresolved=unres_rows); V['K3'] = dict(hit=bool(fr14 is not None and fr14 <= 0.4))
res['verdicts'] = V; json.dump(res, open(OUT, 'w'), default=float)
print('== ВЕРДИКТЫ HOR-03 ==')
for k in ('PU12a', 'PU12a_loo', 'K1', 'PU12b', 'K2', 'K3'): print(k, json.dumps(V[k], ensure_ascii=False, default=float))
print('PU14', json.dumps({k: v for k, v in V['PU14'].items() if not k.startswith('rows')}, ensure_ascii=False))
for r_ in res_rows + unres_rows: print('   %-24s %s N_c_full %3d спайк %5.2f (%d) зазор %5.2f  Δ %+5.2f'%(r_['name'], r_['group'], r_['N_c_full'], r_['spike'], r_['n_spikes'], r_['gap'], r_['diff']))
