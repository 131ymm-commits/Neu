"""HOR-02 — рождение рекуррентности: прогон. Стадия 1 — синтетика (телеграфы по L × 10 сидов, иерархические, AR(1)), стадия 2 — in silico (дипептид, LJ13),
стадия 3 — реальные ряды HOR-01 (описательно). По PREREG 2026-09-09 с поправками 1–3 до прогона."""
import numpy as np, pandas as pd, json, os, sys, glob, time, warnings
warnings.filterwarnings('ignore'); sys.path.insert(0, '/home/claude')
import scipy.io as sio
from hor02_lib import analyze, telegraph, hier_telegraph
from zeta01_lib import embed
B = '/home/claude'; OUT = f'{B}/hor02_results_hier2.json'; res = json.load(open(OUT)) if os.path.exists(OUT) else {}; t0 = time.time()
def run(name, F, tau, k, group, hidden=None, meta=None):
    if name in res: return
    r = analyze(F, tau, k, hidden=hidden); r['group'] = group
    if meta: r.update(meta)
    res[name] = r; json.dump(res, open(OUT, 'w'), default=float)
    if 'error' in r: print(name, 'ОШИБКА', r['error'], flush=True); return
    print(f"{name:26s} [{group}] t1 преф {[None if v is None else round(v, 1) for v in r['t1_prefix']]} N_c преф {r['nc_prefix']} N_true {r['ntrue_prefix']} t1_full {r['t1_full']:.0f} | пары {[(p['side'], p['nc_m'], round(p['beta'], 2)) for p in r['pairs']]} [{time.time()-t0:.0f}s]", flush=True)
n = 8000; Ls = [10, 20, 40, 80, 160, 320, 640, 1280, 2560]; Lh = [80, 160, 320, 640, 1280, 2560]
stage = sys.argv[1] if len(sys.argv) > 1 else 'all'
if stage in ('all', 'synth'):
    for L in Ls:
        for s in range(10):
            rng = np.random.default_rng(1000 * L + s); x, h = telegraph(n, L, rng); Fe = embed(x, 4)
            run(f'tel_L{L}_s{s}', Fe, 1, 30, 'tel', hidden=h[:len(Fe)], meta=dict(L=L, seed=s))
    for L in Lh:
        for s in range(10):
            rng = np.random.default_rng(7000000 + 1000 * L + s); x, h = hier_telegraph(n, L, rng); Fe = embed(x, 4)
            run(f'hier_L{L}_s{s}', Fe, 1, 30, 'hier', hidden=h[:len(Fe)], meta=dict(L=L, seed=s))
    for s in range(10):
        rng = np.random.default_rng(90000 + s); x = np.zeros(n); phi = np.exp(-1 / 10)
        for i in range(1, n): x[i] = phi * x[i - 1] + rng.normal() * np.sqrt(1 - phi ** 2)
        run(f'ar1_s{s}', embed(x, 4), 1, 30, 'ar1', meta=dict(seed=s))
if stage == 'hier2':
    # добавлено ПОСЛЕ прогона семейства 1/1/1: то семейство вырождено по наблюдению (верхнее состояние не читается из x) и по замороженному правилу
    # «t1_full < L/8» исключается целиком; hier2 — амплитуды 0.5/1/2, те же L и сиды; помечено как пост-хок семейство в вердиктах
    for L in Lh:
        for s in range(10):
            rng = np.random.default_rng(7000000 + 1000 * L + s); x, h = hier_telegraph(n, L, rng, amps=(0.5, 1.0, 2.0)); Fe = embed(x, 4)
            run(f'hier2_L{L}_s{s}', Fe, 1, 30, 'hier2', hidden=h[:len(Fe)], meta=dict(L=L, seed=s))
if stage in ('all', 'insilico'):
    for f in sorted(glob.glob(f'{B}/mol_ala2_m5_T*_s*.npz')):
        sc = np.load(f)['scal']; phi_, psi_ = sc[:, 0], sc[:, 1]; F = np.column_stack([np.cos(phi_), np.sin(phi_), np.cos(psi_), np.sin(psi_)])
        run(f'DIP_{os.path.basename(f)[13:-4]}', F, 2, 100, 'dip')
    for fp in sorted(glob.glob(f'{B}/net01L_T*_s*.npz')):
        d = np.load(fp); run('LJ13_' + os.path.basename(fp)[7:-4], d['D'].astype(float), 2, 100, 'lj13')
if stage in ('all', 'real'):
    import xlrd
    wb = xlrd.open_workbook(f'{B}/neu_archive/user_bundles/GICC05_NGRIP_60ka_20y_10sep2007_1.xls'); sh = wb.sheet_by_index(0); ages, d18 = [], []
    for r_ in range(61, sh.nrows):
        a, d = sh.cell_value(r_, 0), sh.cell_value(r_, 2)
        if isinstance(a, float) and isinstance(d, float): ages.append(a); d18.append(d)
    ages = np.array(ages); d18 = np.array(d18)[np.argsort(ages)]
    run('NGRIP_d18O_20yr_m4', embed(d18, 4), 1, 30, 'real'); run('NGRIP_d18O_20yr_m1', d18.reshape(-1, 1), 1, 30, 'real')
    for grp in ('A_Z', 'B_O', 'C_N', 'D_F', 'E_S'):
        files = sorted(glob.glob(f'{B}/EEG-Epilepsy-Datasets/bonn/{grp}/*.txt') + glob.glob(f'{B}/EEG-Epilepsy-Datasets/bonn/{grp}/*.TXT'))[:20]
        for i, fp in enumerate(files):
            if i % 4: continue
            run(f'EEG_{grp}_{os.path.basename(fp)[:4]}', embed(np.loadtxt(fp), 5, 2), 2, 30, 'eeg')
    df = pd.read_csv(f'{B}/RREEBES/Beninca_etal_2008_Nature/data/direct_from_Steve/interp_short_allsystem_newnames.csv'); num = df.select_dtypes(include=[np.number]); num = num.loc[:, num.std() > 0]
    X = np.log1p(num.to_numpy(float)); X = X[:, ~np.isnan(X).any(0)]; run('plankton_Beninca_12sp', X, 1, 15, 'real')
    lr = np.loadtxt(f'{B}/pleistocene/orig/LR04/LR04/total.tab', skiprows=59, usecols=(0, 1), encoding='latin-1'); x = lr[np.argsort(lr[:, 0]), 1]; run('LR04_benthic_m4', embed(x[:3000], 4), 1, 30, 'real')
    def read_wdc(fp, col):
        out = []
        for line in open(fp, encoding='latin-1'):
            p = line.split()
            if len(p) < col + 1: continue
            try: out.append([float(v) for v in p[:col + 1]])
            except Exception: pass
        return np.array(out)
    deu = read_wdc(f'{B}/pleistocene/orig/EPICA/edc3deuttemp2007.txt', 4); run('EPICA_deuterium_m4', embed(deu[:, 3], 4), 1, 30, 'real')
    s_ = pd.read_csv(f'{B}/Rdatasets/csv/datasets/sunspot.month.csv')['value'].to_numpy(float); run('sunspots_monthly_m4', embed(s_, 4, 3), 1, 30, 'real')
    m_ = pd.read_csv(f'{B}/blogR/data/measles_incidence.csv', skiprows=2, na_values='-'); col = [c for c in m_.columns if c.upper().startswith('NEW YORK')][0]; mx = m_[col].interpolate().to_numpy(float); run('measles_NY_weekly_m4', embed(np.log1p(mx), 4, 2), 1, 30, 'real')
    c = pd.read_csv(f'{B}/COVID-19/csse_covid_19_data/csse_covid_19_time_series/time_series_covid19_confirmed_global.csv')
    for country in ('Germany', 'US', 'Italy'):
        row = c[(c['Country/Region'] == country) & (c['Province/State'].isna())].iloc[0, 4:].to_numpy(float); inc = np.maximum(np.diff(row), 0); run(f'COVID_{country}_daily_m4', embed(np.log1p(inc), 4), 1, 15, 'real')
    th = pd.read_csv(f'{B}/deep-early-warnings-pnas/test_empirical/thermoacoustic/data/processed_data/df_transitions.csv'); ycol = [cc for cc in th.columns if cc.lower().startswith('pressure')][0]
    for tid in sorted(th['tsid'].unique())[:3]:
        xx = th[th['tsid'] == tid][ycol].to_numpy(float)[:20000]; run(f'thermoacoustic_{tid}_m4', embed(xx, 4, 2), 2, 30, 'real')
    for psg_p in sorted(glob.glob(f'{B}/combsleepnet/example_data/psg/*.mat')):
        psg = sio.loadmat(psg_p)['psg']; F = np.log10(np.mean(psg.astype(np.float64) ** 2, axis=2) + 1e-20); run('SLEEP_' + os.path.basename(psg_p).split('-')[0], F, 1, 15, 'real')
    from dust01_run_lib import load, std
    a2, d2, lc2 = load(f'{B}/ngrip2d/ngrip_ca_20yr_full.txt'); run('NGRIP_2D_20yr_W', std(np.column_stack([d2, lc2])), 1, 15, 'real'); mg = a2 >= 23000; run('NGRIP_2D_20yr_Wg', std(np.column_stack([d2[mg], lc2[mg]])), 1, 15, 'real')
print('ГОТОВО', stage, f'{time.time()-t0:.0f}s', flush=True)
