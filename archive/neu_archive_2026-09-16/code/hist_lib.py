"""HIST-arc library: Maddison takeoff detector + route certificate (step vs ramp, frozen recipe) + Polity/BMR democracy births."""
import numpy as np, pandas as pd, pyreadr, sys
sys.path.insert(0, "/home/claude")
from pythia001_lib import fit_step, fit_ramp

def load_maddison():
    d = pyreadr.read_r('/home/claude/maddison/data/maddison.rda'); d = d[list(d.keys())[0]]
    return d.dropna(subset=['gdppc'])

def annual_series(df, code):
    s = df[df.countrycode == code].sort_values('year'); y = s['year'].values; v = np.log(s['gdppc'].values)
    # keep the trailing annual stretch
    i0 = 0
    for i in range(len(y) - 1, 0, -1):
        if y[i] - y[i - 1] > 1: i0 = i; break
    return y[i0:].astype(int), v[i0:]

def smoothed_growth(y, v, w=25):
    g = 100 * np.diff(v); yg = y[1:]
    k = np.ones(w) / w; gs = np.convolve(g, k, 'valid'); ys = yg[w // 2: w // 2 + len(gs)]
    return ys, gs

def takeoff(y, v, thr=0.75, pre=50, post=50, w=25):
    ys, gs = smoothed_growth(y, v, w)
    for i in range(len(ys)):
        if gs[i] >= thr and ys[i] - ys[0] >= pre and i + post < len(gs) and np.median(gs[i:i + post]) >= thr:
            return int(ys[i]), ys, gs
    return None, ys, gs

def route(ys, gs, t, half=100):
    m = (ys >= t - half) & (ys <= t + half); x = ys[m].astype(float); z = gs[m]
    if len(z) < 40: return None
    bs, ks, ss = fit_step(x, z); br, kr, sr = fit_ramp(x, z)
    d = br - bs
    return dict(dbic=float(d), label=("ступень" if d >= 6 else ("плавный" if d <= -6 else "неразличимо")), n=int(len(z)), k_step_year=float(x[ks]))

def load_polity():
    p = pyreadr.read_r('/home/claude/democracyData/data/polity5.rda'); p = p[list(p.keys())[0]]
    return p

def democracy_birth_polity(p, iso_ccode_map=None, thr=6, hold=20):
    """First year of polity2 >= thr sustained for `hold` consecutive years; per polity country name/scode."""
    out = {}
    for sc, s in p.groupby('scode'):
        s = s.sort_values('year'); yy = s['year'].values.astype(int); pol = s['polity2'].values
        ok = pol >= thr
        for i in range(len(yy)):
            if ok[i] and i + hold <= len(yy) and np.all(ok[i:i + hold]) and np.all(np.diff(yy[i:i + hold]) == 1):
                out[sc] = int(yy[i]); break
    return out

def load_bmr():
    b = pd.read_csv('/home/claude/Dem-Data-Collection/Boix-Miller-Rosato Dichotomous Coding of Democracy, 1800-2020/democracy-v4.0.csv')
    return b

def spells(b):
    """Democratic spells per country: list of (start, end_inclusive, ended_by_breakdown) from BMR 'democracy' (1/0/NaN)."""
    out = {}
    for c, s in b.groupby('abbreviation'):
        s = s.sort_values('year'); yy = s['year'].values.astype(int); d = s['democracy'].values
        sp = []; i = 0; n = len(yy)
        while i < n:
            if d[i] == 1:
                j = i
                while j + 1 < n and d[j + 1] == 1 and yy[j + 1] == yy[j] + 1: j += 1
                ended = (j + 1 < n and d[j + 1] == 0 and yy[j + 1] == yy[j] + 1)
                sp.append((int(yy[i]), int(yy[j]), bool(ended))); i = j + 1
            else: i += 1
        out[c] = sp
    return out

def sustained_birth(sp, hold=20):
    for a, e, ended in sp:
        if e - a + 1 >= hold: return a
    return None
