"""SORT-01 — прогон по PREREG (2026-09-15). (a) точный лифтированный путь (LIFT-01 A), L ∈ {128, 256}, c ∈ [2.0, 4.5] шаг 0.1;
(b) lifted_local (LIFE-02), L ∈ {64, 128}, s-сетка, c ∈ [1.0, 4.0] шаг 0.05; s_c — по схлопыванию окна (шаг 0.01 вокруг).
Контроль: p = 1/2 (обратимая). Числа — sort01_results.json."""
import numpy as np, json, time, warnings
from scipy.stats import spearmanr
from sort01_lib import analyze, lifted_local
from lift01c_lib import lifted_path
warnings.filterwarnings('ignore'); t0 = time.time(); OUT = '/home/claude/sort01_results.json'; res = dict(A={}, B={}, ctrl={}, verdict={})
def cf(L):
    k = np.pi / L; s = np.sin(k); pEP = s / (1 + s); lam = 1 - 2 / L; q = (1 - lam ** 2) / (2 * (1 - lam * np.cos(k))); return dict(c_EP=float(L * pEP), c_up=float(L * (1 - q)))
# ---------- (a)
for L in (128, 256):
    c_EP, c_up = cf(L)['c_EP'], cf(L)['c_up']; rows = []
    for c in np.round(np.arange(2.0, 4.5001, 0.1), 3):
        r = analyze(lifted_path(L, float(c / L)), L, nmax_cap=6000); r['c'] = float(c); r.pop('q_head', None); rows.append(r)
        print(f"a L={L} c={c:4.2f}: ρ={r['rho']:.5f} real={r['real_lead']} θ₊={r['theta']:.4f} n_max={r['n_max']} | рожд={r['born']} жизнь={r['n_life']} perm={r['permanent']} полупериод={r['half_period'] and round(r['half_period'],1)} | d2={r['d2']:+.1e} n*={r['nstar']} | a₊={r['a1']:.3f} n_b={r['late_birth_n']} [{time.time()-t0:.0f}s]", flush=True)
    res['A'][str(L)] = dict(L=L, c_EP=c_EP, c_up=c_up, rows=rows)
    rc = analyze(lifted_path(L, 0.5), L, nmax_cap=6000); rc.pop('q_head', None); res['ctrl'][str(L)] = rc
    print(f"контроль p=1/2 L={L}: рожд={rc['born']} a₊={rc['a1']:.4f} late={rc['late_birth_n']} d2={rc['d2']:+.2e} perm={rc['permanent']}", flush=True)
V = res['verdict']
def A_rows(L): return res['A'][str(L)]['rows']
def eval_a(L):
    c_EP, c_up = res['A'][str(L)]['c_EP'], res['A'][str(L)]['c_up']; rows = A_rows(L)
    below = [r for r in rows if r['c'] <= c_EP - 0.1]; above = [r for r in rows if c_EP + 0.05 <= r['c'] <= c_up]
    s1 = all((not r['permanent']) and r['born'] for r in below) and all(r['permanent'] for r in above) and len(above) > 0
    fr = [r['n_life'] / r['half_period'] for r in below if r['half_period']]; cs = [r['c'] for r in below if r['half_period']]
    s2 = dict(fracs=fr, spearman=float(spearmanr(cs, fr)[0]) if len(fr) > 2 else None); s2['ok'] = bool(all(0.2 <= f <= 1.0 for f in fr) and s2['spearman'] is not None and s2['spearman'] >= 0.95)
    d2ok = all(r['d2'] > 0 for r in rows); born_rows = [r for r in rows if r['born'] and r['nstar']]
    nst_sp = float(spearmanr([r['c'] for r in born_rows], [r['nstar'] for r in born_rows])[0]) if len(born_rows) > 2 else None
    s3 = dict(d2_all_pos=d2ok, nstar_spearman=nst_sp, ok=bool(d2ok and nst_sp is not None and nst_sp >= 0.95))
    over = [r for r in rows if c_up < r['c'] <= c_up + 0.5]; a_over = all(r['a1'] > 1 for r in over)
    ca_rows = [r for r in rows if r['c'] > c_up]; c_a = None
    for r0, r1 in zip(ca_rows[:-1], ca_rows[1:]):
        if r0['a1'] > 1 >= r1['a1']: c_a = r0['c'] + 0.1 * (r0['a1'] - 1) / (r0['a1'] - r1['a1']); break
    late = [r for r in rows if (not r['born']) and r['late_birth_n'] is not None]; nb_sp = float(spearmanr([r['c'] for r in late], [r['late_birth_n'] for r in late])[0]) if len(late) > 2 else None
    s4 = dict(a_over_ok=a_over, c_a=c_a, c_a_minus_c_up=(c_a - c_up) if c_a else None, nb_spearman=nb_sp, n_late=len(late))
    s4['ok'] = bool(a_over and c_a and 0.6 <= c_a - c_up <= 1.0 and nb_sp == 1.0)
    k1 = any(r['permanent'] and r['c'] <= c_EP - 0.1 for r in rows) or any((not r['permanent']) for r in above)
    a_at = [r for r in rows if abs(r['c'] - (c_up + 0.1)) < 0.06]; k4 = bool(a_at and a_at[0]['a1'] <= 1)
    return dict(S1=s1, S2=s2, S3=s3, S4=s4, K1=k1, K3=(not d2ok), K4=k4)
V['a'] = {str(L): eval_a(L) for L in (128, 256)}
V['PS1'] = all(V['a'][k]['S1'] for k in V['a']); V['PS2'] = all(V['a'][k]['S2']['ok'] for k in V['a']); V['PS3'] = all(V['a'][k]['S3']['ok'] for k in V['a']); V['PS4'] = all(V['a'][k]['S4']['ok'] for k in V['a'])
V['K1'] = any(V['a'][k]['K1'] for k in V['a']); V['K3'] = any(V['a'][k]['K3'] for k in V['a']); V['K4'] = any(V['a'][k]['K4'] for k in V['a'])
V['K0'] = any(res['ctrl'][k]['a1'] > 1 + 1e-9 or res['ctrl'][k]['late_birth_n'] is not None or res['ctrl'][k]['born'] for k in res['ctrl'])
json.dump(res, open(OUT, 'w'), default=float); print('вердикт (a):', json.dumps({k: V[k] for k in ('PS1', 'PS2', 'PS3', 'PS4', 'K0', 'K1', 'K3', 'K4')}), flush=True)
# ---------- (b)
def window(L, s, cs, cap):
    rows = [analyze(lifted_local(L, float(c / L), s), L, nmax_cap=cap) for c in cs]
    b = [c for c, r in zip(cs, rows) if r['born']]; cplx = [c for c, r in zip(cs, rows) if not r['real_lead']]
    gmax = max(-np.log(r['rho']) for r in rows); gd = -np.log(rows[0]['C1']); C1s = [r['C1'] for r in rows]
    return dict(s=s, c_lo=(min(b) if b else None), c_up=(max(b) if b else None), n_birth=len(b), c_last_complex=(max(cplx) if cplx else None), gap_max_L=float(gmax * L), gap_desc_L=float(gd * L),
                open_iff=bool((len(b) > 0) == (gmax > gd)), C1_dev=float(max(abs(x - (1 - 2 / L)) for x in C1s)),
                perm_cs=[c for c, r in zip(cs, rows) if r['permanent']], trans_cs=[c for c, r in zip(cs, rows) if r['born'] and not r['permanent']])
for L in (64, 128):
    cs = np.round(np.arange(1.0, 4.001, 0.05), 3); cap = 1500 if L == 64 else 3000; out = {}
    for s in (0.0, 0.1, 0.15, 0.2, 0.21, 0.22, 0.23, 0.24, 0.25, 0.3):
        w = window(L, s, cs, cap); out[str(s)] = w
        print(f"b L={L} s={s}: окно [{w['c_lo']}, {w['c_up']}] ({w['n_birth']} узлов) компл. до {w['c_last_complex']} max(−lnρ)L={w['gap_max_L']:.3f} vs {w['gap_desc_L']:.3f} open⇔gap {w['open_iff']} C1dev={w['C1_dev']:.1e} perm={w['perm_cs'][:5]} trans={w['trans_cs'][:3]}…{w['trans_cs'][-2:]} [{time.time()-t0:.0f}s]", flush=True)
    ss = sorted(float(k) for k in out); opened = [s for s in ss if out[str(s)]['n_birth'] > 0]; closed = [s for s in ss if out[str(s)]['n_birth'] == 0]
    s_c = (max(opened) + min([s for s in closed if s > max(opened)])) / 2 if opened and any(s > max(opened) for s in closed) else None
    res['B'][str(L)] = dict(L=L, windows=out, s_c=s_c, s_last_open=max(opened) if opened else None, s_first_closed=min([s for s in closed if s > max(opened)]) if opened and any(s > max(opened) for s in closed) else None)
    print(f"b L={L}: s_c ≈ {s_c} (последнее открытое {res['B'][str(L)]['s_last_open']}, первое закрытое {res['B'][str(L)]['s_first_closed']})", flush=True)
sc64, sc128 = res['B']['64']['s_c'], res['B']['128']['s_c']
V['PS5'] = dict(s_c64=sc64, s_c128=sc128, open_iff_all=all(w['open_iff'] for L in ('64', '128') for w in res['B'][L]['windows'].values()), C1_dev_max=max(w['C1_dev'] for L in ('64', '128') for w in res['B'][L]['windows'].values()))
V['PS5']['ok'] = bool(sc64 and sc128 and 0.20 <= sc64 <= 0.235 and 0.18 <= sc128 <= 0.23 and sc128 <= sc64 + 0.005 and V['PS5']['open_iff_all'] and V['PS5']['C1_dev_max'] < 1e-12)
V['K5'] = bool(sc64 is None or sc128 is None or not (0.15 <= sc64 <= 0.25) or sc128 > sc64 + 0.02)
def s6(L):
    w = res['B'][L]['windows']['0.1']; lc = w['c_last_complex']
    return bool(w['perm_cs'] and all(c > lc for c in w['perm_cs']) and all(c <= lc + 1e-9 for c in w['trans_cs']))
V['PS6'] = dict(ok64=s6('64'), ok128=s6('128')); V['PS6']['ok'] = V['PS6']['ok64'] and V['PS6']['ok128']
json.dump(res, open(OUT, 'w'), default=float); print('ВЕРДИКТ', json.dumps({k: V[k] for k in ('PS1', 'PS2', 'PS3', 'PS4', 'PS5', 'PS6', 'K0', 'K1', 'K3', 'K4', 'K5')}, default=float)); print('ГОТОВО', f'{time.time()-t0:.0f}s')
