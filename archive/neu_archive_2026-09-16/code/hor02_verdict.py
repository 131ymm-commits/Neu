"""HOR-02 — вердикты по hor02_results.json (PREREG 2026-09-09 с поправками 1–3 до прогона; семейство hier2 — пост-хок, помечено)."""
import json, numpy as np
r = json.load(open('/home/claude/hor02_results.json')); r = {k: v for k, v in r.items() if 'error' not in v and k != 'verdicts'}
EDGES = [0.5, 1.5, 3, 6, 12, 25, 50, 100, 200, 400, 1e9]
def grp(g): return {k: v for k, v in r.items() if v.get('group') == g}
def resolved(v): return ('L' not in v) or (v['t1_full'] >= v['L'] / 8)
def pairs_of(d, only_resolved=True, key='pairs'):
    return [(p['nc_m'], p['nc_2m'], p['beta'], v.get('L'), k) for k, v in d.items() if (resolved(v) or not only_resolved) for p in v[key]]
def curve(pairs):
    out = []
    for a, b in zip(EDGES[:-1], EDGES[1:]):
        bs = [be for nc, _, be, _, _ in pairs if a <= nc < b]
        if len(bs) >= 3: out.append(dict(lo=a, hi=b, center=float(np.sqrt(a * min(b, 800))), n=len(bs), med_abs=float(np.median(np.abs(bs))), med=float(np.median(bs)), p10=float(np.percentile(np.abs(bs), 10)), p90=float(np.percentile(np.abs(bs), 90))))
    return out
def nstar(cv, thr=0.3):
    """первое падение медианы |β| ниже thr при N_c(m) ≥ 0.5 (лог-интерполяция между центрами бинов)"""
    pts = [(c['center'], c['med_abs']) for c in cv if c['lo'] >= 0.5]
    for i in range(1, len(pts)):
        (x0, y0), (x1, y1) = pts[i - 1], pts[i]
        if y0 >= thr > y1:
            return float(np.exp(np.log(x0) + (y0 - thr) / (y0 - y1) * (np.log(x1) - np.log(x0))))
    return None if not pts else (float('inf') if pts[-1][1] >= thr else 0.0)
def spike(d, L=None):
    return [p['beta'] for k, v in d.items() if resolved(v) and (L is None or v.get('L') == L) for p in v['pairs'] if p['nc_m'] < 2 <= p['nc_2m']]
tel, hier, hier2, ar1, dip, lj, real, eeg = grp('tel'), grp('hier'), grp('hier2'), grp('ar1'), grp('dip'), grp('lj13'), grp('real'), grp('eeg')
V = {}
# P-R0 — валидация счёта (L ≥ 40, разрешённые)
rat = [v['N_c_full'] / max(v['N_true_full'], 1) for v in tel.values() if v['L'] >= 40 and resolved(v)]
V['PR0'] = dict(ok=bool(0.7 <= np.median(rat) <= 1.5), median_ratio=float(np.median(rat)), n=len(rat), unresolved={str(L): sum(not resolved(v) for v in tel.values() if v['L'] == L) for L in sorted({v['L'] for v in tel.values()})})
# кривые
cv_tel = curve(pairs_of(tel)); cv_hier = curve(pairs_of(hier)); cv_hier2 = curve(pairs_of(hier2)); cv_dip = curve(pairs_of(dip)); cv_lj = curve(pairs_of(lj)); cv_ar1 = curve(pairs_of(ar1))
cv_tel_rev = curve(pairs_of(tel, key='pairs_rev'))
ns = dict(tel=nstar(cv_tel), hier=nstar(cv_hier), hier2=nstar(cv_hier2), dip=nstar(cv_dip), tel_rev=nstar(cv_tel_rev))
# LOO по сидам для телеграфа
loo = []
for s in range(10):
    sub = {k: v for k, v in tel.items() if v['seed'] != s}; loo.append(nstar(curve(pairs_of(sub))))
fams = [x for x in (ns['tel'], ns['hier2'] if hier2 else ns['hier'], ns['dip']) if x not in (None, 0.0, float('inf'))]
V['PR1'] = dict(nstar=ns, loo_tel=loo, ok=bool(all(5 <= x <= 60 for x in fams) and (max(fams) / min(fams) <= 2 if fams else False)), fams_used=('tel', 'hier2' if hier2 else 'hier', 'dip'))
V['K1'] = dict(hit=bool(any(not (5 <= x <= 60) for x in fams) or (fams and max(fams) / min(fams) > 2)))
# спайк первого оборота
sp = {}
for name, d in (('tel', tel), ('hier', hier), ('hier2', hier2), ('dip', dip)):
    allv = spike(d); sp[name] = dict(n=len(allv), median=float(np.median(allv)) if allv else None, byL={})
    for L in sorted({v.get('L') for v in d.values() if v.get('L')}):
        vv = spike(d, L); sp[name]['byL'][str(L)] = dict(n=len(vv), median=float(np.median(vv)) if vv else None)
# отношение спайков чистый/иерархический при L = 160…1280 (по L, где есть ≥ 3 пар у обоих)
def ratio_by_L(a, b):
    out = {}
    for L in ('160', '320', '640', '1280'):
        x, y = sp[a]['byL'].get(L), sp[b]['byL'].get(L)
        if x and y and x['n'] >= 3 and y['n'] >= 3 and y['median']: out[L] = x['median'] / y['median']
    return out
rat_h2 = ratio_by_L('tel', 'hier2') if hier2 else {}; rat_h = ratio_by_L('tel', 'hier')
def delta_L(fam):
    b = sp[fam]['byL']; hi = b.get('1280'); lo = next((b[L] for L in ('160', '320') if b.get(L) and b[L]['n'] >= 3), None)
    return (hi['median'] - lo['median']) if (hi and lo and hi['n'] >= 3) else None
med_ratio = float(np.median(list(rat_h2.values()))) if rat_h2 else None
V['PR2'] = dict(spikes=sp, ratio_tel_hier2_byL=rat_h2, ratio_tel_hier_byL=rat_h, median_ratio=med_ratio, delta_tel=delta_L('tel'), delta_hier2=delta_L('hier2') if hier2 else None,
                H_amp_ok=bool(med_ratio is not None and med_ratio <= 1.3 and (delta_L('tel') is None or delta_L('tel') <= 0.5)),
                Hprime_ok=bool(med_ratio is not None and med_ratio >= 1.5 and (delta_L('tel') is not None and delta_L('tel') >= 1.0)))
V['K2'] = dict(H_killed=bool(med_ratio is not None and med_ratio >= 1.5), Hprime_killed=bool(med_ratio is not None and med_ratio <= 1.2), not_established=bool(med_ratio is None or 1.2 < med_ratio < 1.5))
# K3 — дипептид в полосе телеграфа (|β| при N_c(m) ≥ 0.5, N_c ≤ 100)
band = {(c['lo'], c['hi']): (c['p10'], c['p90']) for c in cv_tel}
def in_band(pairs):
    inb, tot = 0, 0
    for nc, _, be, _, _ in pairs:
        if nc < 0.5 or nc > 100: continue
        for (a, b), (lo, hi) in band.items():
            if a <= nc < b: tot += 1; inb += (lo <= abs(be) <= hi); break
    return inb, tot
ib, tot = in_band(pairs_of(dip)); V['K3'] = dict(hit=bool(tot and ib / tot < 0.4), frac=(ib / tot if tot else None), n=tot, ok_PR2_band=bool(tot and ib / tot >= 0.6))
# вырожденный случай AR(1)
V['AR1'] = dict(curve=cv_ar1, all_nc_min=float(min(p[0] for p in pairs_of(ar1))), median_abs_beta=float(np.median([abs(p[2]) for p in pairs_of(ar1)])))
# P-R3 описательно: реальные ряды
def real_stats(d):
    ps = pairs_of(d, only_resolved=False); hi = [abs(be) for nc, _, be, _, _ in ps if nc >= 30]; lo = [abs(be) for nc, _, be, _, _ in ps if nc < 30]
    ibb, tt = in_band(ps)
    return dict(n_pairs=len(ps), frac_conv_nc_ge30=(float(np.mean([b < 0.3 for b in hi])) if hi else None), n_ge30=len(hi), frac_conv_nc_lt30=(float(np.mean([b < 0.3 for b in lo])) if lo else None), n_lt30=len(lo), in_band=(ibb / tt if tt else None), n_band=tt)
V['PR3'] = dict(real=real_stats(real), eeg=real_stats(eeg), lj13=real_stats(lj), dip=real_stats(dip))
V['curves'] = dict(tel=cv_tel, tel_rev=cv_tel_rev, hier=cv_hier, hier2=cv_hier2, dip=cv_dip, lj13=cv_lj, ar1=cv_ar1)
# фит |β| ≈ c / √N_c на телеграфе (бины N_c ≥ 1.5)
pts = [(c['center'], c['med_abs']) for c in cv_tel if c['lo'] >= 1.5]
if len(pts) >= 3:
    x = np.log([p[0] for p in pts]); y = np.log([p[1] for p in pts]); sl, ic = np.polyfit(x, y, 1); V['poisson_fit'] = dict(slope=float(sl), coef=float(np.exp(ic)), note='медиана |β_loc| ≈ coef · N_c^slope; пуассонов прогноз slope = −0.5')
r['verdicts'] = V; json.dump(r, open('/home/claude/hor02_results.json', 'w'), default=float)
print('== ВЕРДИКТЫ HOR-02 ==')
for k in ('PR0', 'PR1', 'K1', 'K2', 'K3', 'AR1', 'PR3', 'poisson_fit'):
    if k in V: print(k, json.dumps(V[k], ensure_ascii=False, default=float)[:900])
print('PR2 отношения tel/hier2 по L:', rat_h2, 'медиана', med_ratio, '| Δspike tel:', V['PR2']['delta_tel'], '| спайки:', {k: (v['n'], v['median']) for k, v in sp.items()})
for name, cv in V['curves'].items():
    print(name, ' '.join(f"[{c['lo']:.0f}-{c['hi']:.0f}):{c['med_abs']:.2f}({c['n']})" for c in cv))
