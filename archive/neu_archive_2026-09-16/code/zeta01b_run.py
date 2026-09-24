"""ZETA-01b (P-U13) — классы ζ ZETA-01 при τ' = m·шаг на тех же 37 вложенных рядах; контроль подмены τ — телеграф (выброс) и hier2 (иерархия) при τ = 1 и 4. По PREREG 2026-09-09."""
import numpy as np, pandas as pd, json, os, sys, glob, time, warnings
warnings.filterwarnings('ignore'); sys.path.insert(0, '/home/claude')
from zeta01_lib import embed, zeta
from hor02_lib import telegraph, hier_telegraph
B = '/home/claude'; OUT = f'{B}/zeta01b_results.json'; res = json.load(open(OUT)) if os.path.exists(OUT) else {}; t0 = time.time()
z01 = json.load(open(f'{B}/zeta01_results.json'))
def cls(z): return None if z is None else ('выброс' if z >= 2 else ('иерархия' if z >= 0.9 else 'континуум'))
def run(name, F, tau_new, k, kind):
    if name in res: return
    r = zeta(F, tau_new, k, name=name + f' τ\'={tau_new}', verbose=True); r['kind'] = kind; r['tau_new'] = tau_new
    r['cls_new'] = ('отказ' if r['dec'].startswith('отказ:') else cls(r['zeta_median'])); old = z01.get(name); r['cls_old'] = (cls(old['zeta_median']) if old and old['zeta_median'] is not None else None); r['zeta_old'] = (old['zeta_median'] if old else None); r['tau_old'] = (old['tau'] if old else None)
    res[name] = r; json.dump(res, open(OUT, 'w'), default=float)
    print(f"      → {r['cls_old']} (ζ {None if r['zeta_old'] is None else round(r['zeta_old'], 2)}, τ={r['tau_old']}) → {r['cls_new']} [{time.time()-t0:.0f}s]", flush=True)
# контроль подмены τ
for s in range(5):
    rng = np.random.default_rng(1000 * 40 + s); x, _ = telegraph(8000, 40, rng)
    for tau in (1, 4): run(f'ctrl_tel40_s{s}_tau{tau}', embed(x, 4), tau, 30, 'ctrl_tel')
    rng = np.random.default_rng(7000000 + 1000 * 320 + s); x, _ = hier_telegraph(8000, 320, rng, amps=(0.5, 1.0, 2.0))
    for tau in (1, 4): run(f'ctrl_hier2_320_s{s}_tau{tau}', embed(x, 4), tau, 30, 'ctrl_hier2')
# ряды ZETA-01 (вложенные) при τ' = m·шаг
import xlrd
wb = xlrd.open_workbook(f'{B}/neu_archive/user_bundles/GICC05_NGRIP_60ka_20y_10sep2007_1.xls'); sh = wb.sheet_by_index(0); ages, d18 = [], []
for r_ in range(61, sh.nrows):
    a, d = sh.cell_value(r_, 0), sh.cell_value(r_, 2)
    if isinstance(a, float) and isinstance(d, float): ages.append(a); d18.append(d)
ages = np.array(ages); d18 = np.array(d18)[np.argsort(ages)]
run('NGRIP_d18O_20yr_m4', embed(d18, 4), 4, 30, 'emb'); run('NGRIP_d18O_20yr_m1', d18.reshape(-1, 1), 4, 30, 'raw')
for grp in ('A_Z', 'B_O', 'C_N', 'D_F', 'E_S'):
    files = sorted(glob.glob(f'{B}/EEG-Epilepsy-Datasets/bonn/{grp}/*.txt') + glob.glob(f'{B}/EEG-Epilepsy-Datasets/bonn/{grp}/*.TXT'))[:20]
    for i, fp in enumerate(files):
        if i % 4: continue
        run(f'EEG_{grp}_{os.path.basename(fp)[:4]}', embed(np.loadtxt(fp), 5, 2), 10, 30, 'emb')
df = pd.read_csv(f'{B}/RREEBES/Beninca_etal_2008_Nature/data/direct_from_Steve/interp_short_allsystem_newnames.csv'); num = df.select_dtypes(include=[np.number]); num = num.loc[:, num.std() > 0]
X = np.log1p(num.to_numpy(float)); X = X[:, ~np.isnan(X).any(0)]; run('plankton_Beninca_12sp', X, 4, 15, 'raw')
lr = np.loadtxt(f'{B}/pleistocene/orig/LR04/LR04/total.tab', skiprows=59, usecols=(0, 1), encoding='latin-1'); x = lr[np.argsort(lr[:, 0]), 1]; run('LR04_benthic_m4', embed(x[:3000], 4), 4, 30, 'emb')
def read_wdc(fp, col):
    out = []
    for line in open(fp, encoding='latin-1'):
        p = line.split()
        if len(p) < col + 1: continue
        try: out.append([float(v) for v in p[:col + 1]])
        except Exception: pass
    return np.array(out)
deu = read_wdc(f'{B}/pleistocene/orig/EPICA/edc3deuttemp2007.txt', 4); run('EPICA_deuterium_m4', embed(deu[:, 3], 4), 4, 30, 'emb')
s_ = pd.read_csv(f'{B}/Rdatasets/csv/datasets/sunspot.month.csv')['value'].to_numpy(float); run('sunspots_monthly_m4', embed(s_, 4, 3), 12, 30, 'emb')
m_ = pd.read_csv(f'{B}/blogR/data/measles_incidence.csv', skiprows=2, na_values='-'); col = [c for c in m_.columns if c.upper().startswith('NEW YORK')][0]; mx = m_[col].interpolate().to_numpy(float); run('measles_NY_weekly_m4', embed(np.log1p(mx), 4, 2), 8, 30, 'emb')
c = pd.read_csv(f'{B}/COVID-19/csse_covid_19_data/csse_covid_19_time_series/time_series_covid19_confirmed_global.csv')
for country in ('Germany', 'US', 'Italy'):
    row = c[(c['Country/Region'] == country) & (c['Province/State'].isna())].iloc[0, 4:].to_numpy(float); inc = np.maximum(np.diff(row), 0); run(f'COVID_{country}_daily_m4', embed(np.log1p(inc), 4), 4, 15, 'emb')
th = pd.read_csv(f'{B}/deep-early-warnings-pnas/test_empirical/thermoacoustic/data/processed_data/df_transitions.csv'); ycol = [cc for cc in th.columns if cc.lower().startswith('pressure')][0]
for tid in sorted(th['tsid'].unique())[:3]:
    xx = th[th['tsid'] == tid][ycol].to_numpy(float)[:20000]; run(f'thermoacoustic_{tid}_m4', embed(xx, 4, 2), 8, 30, 'emb')
# --- вердикты ---
emb = {k: v for k, v in res.items() if v.get('kind') == 'emb'}; eeg = {k: v for k, v in emb.items() if k.startswith('EEG')}
ctrl_tel = [v['cls_new'] for k, v in res.items() if v.get('kind') == 'ctrl_tel' and v['tau_new'] == 4]; ctrl_tel1 = [v['cls_new'] for k, v in res.items() if v.get('kind') == 'ctrl_tel' and v['tau_new'] == 1]
ctrl_h = [v['cls_new'] for k, v in res.items() if v.get('kind') == 'ctrl_hier2' and v['tau_new'] == 4]; ctrl_h1 = [v['cls_new'] for k, v in res.items() if v.get('kind') == 'ctrl_hier2' and v['tau_new'] == 1]
V = dict(K0=dict(tel_tau4=ctrl_tel, tel_tau1=ctrl_tel1, hier2_tau4=ctrl_h, hier2_tau1=ctrl_h1, ok=bool(sum(c == 'выброс' for c in ctrl_tel) >= 4 and sum(c == 'иерархия' for c in ctrl_h) >= 3)),
         PZ1=dict(hier_eeg_old=int(sum(v['cls_old'] == 'иерархия' for v in eeg.values())), hier_eeg_new=int(sum(v['cls_new'] == 'иерархия' for v in eeg.values())), n=len(eeg), cont_new=int(sum(v['cls_new'] == 'континуум' for v in eeg.values())), refuse_new=int(sum(v['cls_new'] == 'отказ' for v in eeg.values()))),
         PZ2=dict(outliers_new=[k for k, v in emb.items() if v['cls_new'] == 'выброс'], n=len(emb)), PZ3=dict(refusals=[k for k, v in emb.items() if v['cls_new'] == 'отказ'], n=len(emb)),
         transitions={k: (v['cls_old'], v['cls_new'], None if v['zeta_old'] is None else round(v['zeta_old'], 2), None if v['zeta_median'] is None else round(v['zeta_median'], 2)) for k, v in emb.items()},
         raw={k: (v['cls_old'], v['cls_new']) for k, v in res.items() if v.get('kind') == 'raw'})
V['PZ1']['H_ok'] = bool(V['PZ1']['hier_eeg_new'] >= 5); V['K1'] = dict(hit=bool(V['PZ1']['hier_eeg_new'] <= 3)); V['K2'] = dict(hit=bool(len(V['PZ2']['outliers_new']) > 0)); V['K3'] = dict(hit=bool(len(V['PZ3']['refusals']) > 10))
res['verdicts'] = V; json.dump(res, open(OUT, 'w'), default=float)
print('\n== ВЕРДИКТЫ ZETA-01b ==')
for k in ('K0', 'PZ1', 'PZ2', 'PZ3', 'K1', 'K2', 'K3', 'raw'): print(k, json.dumps(V[k], ensure_ascii=False, default=float)[:600])
for k, t in V['transitions'].items(): print('  %-24s %s → %s  (ζ %s → %s)'%(k, t[0], t[1], t[2], t[3]))
