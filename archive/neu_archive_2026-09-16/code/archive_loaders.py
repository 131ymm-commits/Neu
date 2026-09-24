"""Загрузчики рядов архива (как в hor02_run.py), генератор (name, F, tau, k, group). Без побочных эффектов при импорте."""
import numpy as np, pandas as pd, os, glob
import scipy.io as sio
from zeta01_lib import embed
B = '/home/claude'
def series(groups=('real', 'eeg', 'insilico')):
    if 'real' in groups:
        import xlrd
        wb = xlrd.open_workbook(f'{B}/neu_archive/user_bundles/GICC05_NGRIP_60ka_20y_10sep2007_1.xls'); sh = wb.sheet_by_index(0); ages, d18 = [], []
        for r_ in range(61, sh.nrows):
            a, d = sh.cell_value(r_, 0), sh.cell_value(r_, 2)
            if isinstance(a, float) and isinstance(d, float): ages.append(a); d18.append(d)
        ages = np.array(ages); d18 = np.array(d18)[np.argsort(ages)]
        yield 'NGRIP_d18O_20yr_m4', embed(d18, 4), 1, 30, 'real'; yield 'NGRIP_d18O_20yr_m1', d18.reshape(-1, 1), 1, 30, 'real'
    if 'eeg' in groups:
        for grp in ('A_Z', 'B_O', 'C_N', 'D_F', 'E_S'):
            files = sorted(glob.glob(f'{B}/EEG-Epilepsy-Datasets/bonn/{grp}/*.txt') + glob.glob(f'{B}/EEG-Epilepsy-Datasets/bonn/{grp}/*.TXT'))[:20]
            for i, fp in enumerate(files):
                if i % 4: continue
                yield f'EEG_{grp}_{os.path.basename(fp)[:4]}', embed(np.loadtxt(fp), 5, 2), 2, 30, 'eeg'
    if 'real' in groups:
        df = pd.read_csv(f'{B}/RREEBES/Beninca_etal_2008_Nature/data/direct_from_Steve/interp_short_allsystem_newnames.csv'); num = df.select_dtypes(include=[np.number]); num = num.loc[:, num.std() > 0]
        X = np.log1p(num.to_numpy(float)); X = X[:, ~np.isnan(X).any(0)]; yield 'plankton_Beninca_12sp', X, 1, 15, 'real'
        lr = np.loadtxt(f'{B}/pleistocene/orig/LR04/LR04/total.tab', skiprows=59, usecols=(0, 1), encoding='latin-1'); x = lr[np.argsort(lr[:, 0]), 1]; yield 'LR04_benthic_m4', embed(x[:3000], 4), 1, 30, 'real'
        def read_wdc(fp, col):
            out = []
            for line in open(fp, encoding='latin-1'):
                p = line.split()
                if len(p) < col + 1: continue
                try: out.append([float(v) for v in p[:col + 1]])
                except Exception: pass
            return np.array(out)
        deu = read_wdc(f'{B}/pleistocene/orig/EPICA/edc3deuttemp2007.txt', 4); yield 'EPICA_deuterium_m4', embed(deu[:, 3], 4), 1, 30, 'real'
        s_ = pd.read_csv(f'{B}/Rdatasets/csv/datasets/sunspot.month.csv')['value'].to_numpy(float); yield 'sunspots_monthly_m4', embed(s_, 4, 3), 1, 30, 'real'
        m_ = pd.read_csv(f'{B}/blogR/data/measles_incidence.csv', skiprows=2, na_values='-'); col = [c for c in m_.columns if c.upper().startswith('NEW YORK')][0]; mx = m_[col].interpolate().to_numpy(float); yield 'measles_NY_weekly_m4', embed(np.log1p(mx), 4, 2), 1, 30, 'real'
        c = pd.read_csv(f'{B}/COVID-19/csse_covid_19_data/csse_covid_19_time_series/time_series_covid19_confirmed_global.csv')
        for country in ('Germany', 'US', 'Italy'):
            row = c[(c['Country/Region'] == country) & (c['Province/State'].isna())].iloc[0, 4:].to_numpy(float); inc = np.maximum(np.diff(row), 0); yield f'COVID_{country}_daily_m4', embed(np.log1p(inc), 4), 1, 15, 'real'
        th = pd.read_csv(f'{B}/deep-early-warnings-pnas/test_empirical/thermoacoustic/data/processed_data/df_transitions.csv'); ycol = [cc for cc in th.columns if cc.lower().startswith('pressure')][0]
        for tid in sorted(th['tsid'].unique())[:3]:
            xx = th[th['tsid'] == tid][ycol].to_numpy(float)[:20000]; yield f'thermoacoustic_{tid}_m4', embed(xx, 4, 2), 2, 30, 'real'
        for psg_p in sorted(glob.glob(f'{B}/combsleepnet/example_data/psg/*.mat')):
            psg = sio.loadmat(psg_p)['psg']; F = np.log10(np.mean(psg.astype(np.float64) ** 2, axis=2) + 1e-20); yield 'SLEEP_' + os.path.basename(psg_p).split('-')[0], F, 1, 15, 'real'
        from dust01_run_lib import load, std
        a2, d2, lc2 = load(f'{B}/ngrip2d/ngrip_ca_20yr_full.txt'); yield 'NGRIP_2D_20yr_W', std(np.column_stack([d2, lc2])), 1, 15, 'real'; mg = a2 >= 23000; yield 'NGRIP_2D_20yr_Wg', std(np.column_stack([d2[mg], lc2[mg]])), 1, 15, 'real'
    if 'insilico' in groups:
        for f in sorted(glob.glob(f'{B}/mol_ala2_m5_T*_s*.npz')):
            sc = np.load(f)['scal']; phi_, psi_ = sc[:, 0], sc[:, 1]; yield f'DIP_{os.path.basename(f)[13:-4]}', np.column_stack([np.cos(phi_), np.sin(phi_), np.cos(psi_), np.sin(psi_)]), 2, 100, 'dip'
        for fp in sorted(glob.glob(f'{B}/net01L_T*_s*.npz')):
            d = np.load(fp); yield 'LJ13_' + os.path.basename(fp)[7:-4], d['D'].astype(float), 2, 100, 'lj13'
