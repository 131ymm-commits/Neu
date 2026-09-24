"""ZETA-01 — ζ-атлас реальных рядов: спектральный отпечаток (SPEC-01) на NGRIP, ЭЭГ Бонна, планктоне, LR04/EPICA, сосне, кори, гейзере, COVID,
термоакустике, AMOC, сне (перенос). По PREREG (2026-09-08)."""
import numpy as np, pandas as pd, json, os, sys, glob, time, warnings
warnings.filterwarnings('ignore'); sys.path.insert(0, '/home/claude')
from mol_levels_lib import microstates
from deeptime.markov import TransitionCountEstimator
from deeptime.markov.msm import BayesianMSM, MaximumLikelihoodMSM
B = '/home/claude'; OUT = f'{B}/zeta01_results.json'; res = json.load(open(OUT)) if os.path.exists(OUT) else {}; t0 = time.time()

def embed(x, m=4, step=1):
    x = np.asarray(x, float); n = len(x) - (m - 1) * step
    return np.column_stack([x[i * step: i * step + n] for i in range(m)])

def spacing_stats(ts, tau):
    r = ts[ts > tau]
    if len(r) < 4: return None
    s = np.log(r[:-1] / r[1:]); k = np.arange(1, len(s) + 1); z = k * s
    return dict(p1=float(np.exp(-z[0] / z[1:].mean())), z1_rest=float(z[0] / z[1:].mean()), m=len(s), z=[float(v) for v in z[:6]])

def zeta(F, tau, k, ns=200, name=''):
    lab = microstates(F, k, seed=0)
    c = TransitionCountEstimator(lagtime=tau, count_mode='effective').fit_fetch(lab.astype(int)).submodel_largest()
    msm = MaximumLikelihoodMSM(reversible=True).fit(c).fetch_model(); post = BayesianMSM(n_samples=ns, reversible=True).fit(msm).fetch_model()
    ml = spacing_stats(np.sort(msm.timescales(14))[::-1], tau); ps, zr, ms = [], [], []
    for mm in post.samples:
        st = spacing_stats(np.sort(mm.timescales(14))[::-1], tau)
        if st is None: ms.append(0); continue
        ps.append(st['p1']); zr.append(st['z1_rest']); ms.append(st['m'])
    unresolved = np.mean(np.array(ms) < 3) > 0.5; PL = float(np.mean(np.array(ps) <= 0.05)) if ps else 0.0
    dec = 'отказ:не разрешён' if unresolved else ('уровень' if PL >= 0.95 else ('нет' if PL <= 0.05 else 'отказ'))
    r = dict(n=int(len(F)), k=k, tau=tau, n_states=int(c.n_states), its_ml=[float(x) for x in np.sort(msm.timescales(14))[::-1][:6]], z_ml=(ml['z'] if ml else None),
             p1_ml=(ml['p1'] if ml else None), PL=PL, zeta_median=(float(np.median(zr)) if zr else None), zeta_q=([float(x) for x in np.quantile(zr, [0.05, 0.95])] if zr else None), m_median=float(np.median(ms)), dec=dec)
    res[name] = r; json.dump(res, open(OUT, 'w'), indent=1, default=float)
    print(f"{name:26s} n={r['n']:6d} k={k} τ={tau} | ITS {np.round(r['its_ml'][:5], 1)} | z {None if not r['z_ml'] else np.round(r['z_ml'][:4], 2)} | ζ {r['zeta_median']} [{None if not r['zeta_q'] else np.round(r['zeta_q'], 2)}] P_L {PL:.2f} → {dec} [{time.time()-t0:.0f}s]", flush=True)
    return r

def run(name, F, tau, k):
    if name in res: print('пропуск', name); return
    try: zeta(F, tau, k, name=name)
    except Exception as e: res[name] = dict(err=str(e)[:200]); json.dump(res, open(OUT, 'w'), indent=1); print(name, 'ошибка', str(e)[:120], flush=True)

# 1. NGRIP δ18O, GICC05 20-летнее разрешение, 60 ka (вложение m=4)
import xlrd
wb = xlrd.open_workbook(f'{B}/neu_archive/user_bundles/GICC05_NGRIP_60ka_20y_10sep2007_1.xls'); sh = wb.sheet_by_index(0); ages, d18 = [], []
for r in range(61, sh.nrows):
    a, d = sh.cell_value(r, 0), sh.cell_value(r, 2)
    if isinstance(a, float) and isinstance(d, float): ages.append(a); d18.append(d)
ages = np.array(ages); d18 = np.array(d18); o = np.argsort(ages); d18 = d18[o]   # по времени
run('NGRIP_d18O_20yr_m4', embed(d18, 4), 1, 30)
run('NGRIP_d18O_20yr_m1', d18.reshape(-1, 1), 1, 30)
# 2. ЭЭГ Бонна: пять наборов, по 20 сегментов (4097 отсчётов, 173.6 Гц), вложение m=5 с шагом 2; τ = 2 отсчёта
for grp in ('A_Z', 'B_O', 'C_N', 'D_F', 'E_S'):
    files = sorted(glob.glob(f'{B}/EEG-Epilepsy-Datasets/bonn/{grp}/*.txt') + glob.glob(f'{B}/EEG-Epilepsy-Datasets/bonn/{grp}/*.TXT'))[:20]
    for i, fp in enumerate(files[:20]):
        if i % 4: continue          # 5 сегментов на набор
        x = np.loadtxt(fp); run(f'EEG_{grp}_{os.path.basename(fp)[:4]}', embed(x, 5, 2), 2, 30)
# 3. Планктон Бенинки (692 × виды)
df = pd.read_csv(f'{B}/RREEBES/Beninca_etal_2008_Nature/data/direct_from_Steve/interp_short_allsystem_newnames.csv')
num = df.select_dtypes(include=[np.number]); num = num.loc[:, num.std() > 0]
X = np.log1p(num.to_numpy(float)); X = X[:, ~np.isnan(X).any(0)]
run('plankton_Beninca_12sp', X, 1, 30)
# 4. LR04 бентосный стек (5.3 Myr), EPICA дейтерий (800 kyr)
lr = np.loadtxt(f'{B}/pleistocene/orig/LR04/LR04/total.tab', skiprows=59, usecols=(0, 1), encoding='latin-1'); x = lr[np.argsort(lr[:, 0]), 1]
run('LR04_benthic_m4', embed(x[:3000], 4), 1, 30)
def read_wdc(fp, col):
    out = []
    for line in open(fp, encoding='latin-1'):
        p = line.split()
        if len(p) < col + 1: continue
        try: out.append([float(v) for v in p[:col + 1]])
        except Exception: pass
    return np.array(out)
try:
    deu = read_wdc(f'{B}/pleistocene/orig/EPICA/edc3deuttemp2007.txt', 4); xd = deu[:, 3] if deu.shape[1] > 3 else deu[:, -1]
    run('EPICA_deuterium_m4', embed(xd, 4), 1, 30)
except Exception as e: print('EPICA ошибка', e)
# 5. Солнечные пятна (месячные), корь (недельная, Англия/США), гейзер, COVID (Германия/США дневные приросты), термоакустика
s = pd.read_csv(f'{B}/Rdatasets/csv/datasets/sunspot.month.csv')['value'].to_numpy(float); run('sunspots_monthly_m4', embed(s, 4, 3), 1, 30)
try:
    m = pd.read_csv(f'{B}/blogR/data/measles_incidence.csv', skiprows=2, na_values='-'); col = [c for c in m.columns if c.upper().startswith('NEW YORK')][0]
    mx = m[col].interpolate().to_numpy(float); run('measles_NY_weekly_m4', embed(np.log1p(mx), 4, 2), 1, 30)
except Exception as e: print('корь ошибка', e)
fa = pd.read_csv(f'{B}/Rdatasets/csv/datasets/faithful.csv')['eruptions'].to_numpy(float); run('faithful_eruptions_m2', embed(fa, 2), 1, 8)
try:
    c = pd.read_csv(f'{B}/COVID-19/csse_covid_19_data/csse_covid_19_time_series/time_series_covid19_confirmed_global.csv')
    for country in ('Germany', 'US', 'Italy'):
        row = c[(c['Country/Region'] == country) & (c['Province/State'].isna())].iloc[0, 4:].to_numpy(float); inc = np.diff(row); inc = np.maximum(inc, 0)
        run(f'COVID_{country}_daily_m4', embed(np.log1p(inc), 4), 1, 30)
except Exception as e: print('COVID ошибка', e)
try:
    th = pd.read_csv(f'{B}/deep-early-warnings-pnas/test_empirical/thermoacoustic/data/processed_data/df_transitions.csv')
    print('термоакустика колонки:', list(th.columns)[:8], len(th))
    ycol = [cc for cc in th.columns if cc.lower().startswith('pressure')]; ycol = ycol[0] if ycol else th.columns[1]   # исправлено: раньше брался столбец 'transition time' (константа) → n_states = 1
    for tid in sorted(th['tsid'].unique())[:3] if 'tsid' in th.columns else [None]:
        sub = th[th['tsid'] == tid] if tid is not None else th; x = sub[ycol].to_numpy(float)[:20000]
        run(f'thermoacoustic_{tid}_m4', embed(x, 4, 2), 2, 30)
except Exception as e: print('термоакустика ошибка', e)
# 6. Сон — перенос из SPEC-01 (6 ночей: «нет» 6/6, ζ 0.29–0.93)
print('готово', time.time() - t0)
