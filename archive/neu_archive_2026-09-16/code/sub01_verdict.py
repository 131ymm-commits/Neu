"""SUB-01 часть B — сводка и вердикты по PREREG."""
import json, numpy as np
from scipy.stats import spearmanr
d = {}
for p in (0, 1):
    try: d.update(json.load(open(f'/home/claude/sub01_morse_{p}.json')))
    except FileNotFoundError: pass
rows = sorted(d.values(), key=lambda r: r['rho']); rho = np.array([r['rho'] for r in rows])
Tf = np.array([r['Tf'] if r['Tf'] is not None else np.nan for r in rows]); Tm = np.array([r['Tm'] if r['Tm'] is not None else np.nan for r in rows])
W = Tm - Tf; Wrel = W / Tm
zeta = np.array([r['zeta']['zeta_median'] if r['zeta']['zeta_median'] is not None else np.nan for r in rows])
dec = [r['zeta']['dec'] for r in rows]; resolved = np.array([dd != 'отказ:не разрешён' for dd in dec])
kgs = np.array([r['k_gs'] if r['k_gs'] is not None else r['n_rec'] for r in rows], float)   # цензура: нижняя граница
nrec = np.array([r['n_rec'] for r in rows]); ico = np.array([r['ico_is_gs'] for r in rows]); frac_solid = np.array([r['frac_solid_coex'] for r in rows])
phi = [np.median(r['phi_int']) if r['phi_int'] else np.nan for r in rows]
print(f"ρ: {len(rows)} значений; икосаэдр — глобальный минимум на {ico.mean()*100:.0f} %; разрешённых ζ: {resolved.sum()}")
def sp(a, b, m=None):
    m = np.isfinite(a) & np.isfinite(b) if m is None else (m & np.isfinite(a) & np.isfinite(b))
    return (spearmanr(a[m], b[m]).statistic if m.sum() > 3 else np.nan), int(m.sum())
r_z, n_z = sp(zeta, rho, resolved); r_w, n_w = sp(Wrel, rho); r_k, n_k = sp(kgs, rho); r_tf, n_tf = sp(Tf, rho)
lo = rho <= 4.5; hi = rho >= 10.0; lo5 = rho <= 5.0
z_lo = np.nanmedian(zeta[lo & resolved]) if (lo & resolved).sum() else np.nan; z_hi = np.nanmedian(zeta[hi & resolved]) if (hi & resolved).sum() else np.nan
k_lo = np.median(kgs[lo5]); k_hi = np.median(kgs[hi]) if hi.sum() else np.nan
print(f"Спирмен: ζ~ρ {r_z:+.2f} (n={n_z}); W/T_m~ρ {r_w:+.2f} (n={n_w}); k_gs~ρ {r_k:+.2f} (n={n_k}); T_f~ρ {r_tf:+.2f} (n={n_tf})")
print(f"ζ медианы: ρ≤4.5 {z_lo:.2f} (n={(lo&resolved).sum()}), ρ≥10 {z_hi:.2f} (n={(hi&resolved).sum()}); k_gs медианы: ρ≤5 {k_lo:.1f}, ρ≥10 {k_hi:.1f}")
print("решения ζ по бинам ρ:")
for a, b in ((3, 5), (5, 7), (7, 9), (9, 11), (11, 14.01)):
    m = (rho >= a) & (rho < b); ds = [dec[i] for i in np.flatnonzero(m)]
    print(f"  ρ∈[{a},{b}): n={m.sum()} уровень {ds.count('уровень')} нет {ds.count('нет')} отказ {ds.count('отказ')} не разрешён {ds.count('отказ:не разрешён')} | ζ мед {np.nanmedian(zeta[m]):.2f} | W/T_m мед {np.nanmedian(Wrel[m]):+.3f} | T_f мед {np.nanmedian(Tf[m]):.3f} | k_gs мед {np.median(kgs[m]):.1f} | рекордов мед {np.median(nrec[m]):.0f} | тв.доля {np.median(frac_solid[m]):.2f}")
V = dict(PB1=dict(ok=bool(r_z <= -0.5 and z_lo >= 2 * z_hi), r=float(r_z), z_lo=float(z_lo), z_hi=float(z_hi), K1=bool(abs(r_z) < 0.3 and n_z >= 40), K4=bool(n_z < 40)),
         PB2=dict(ok=bool(r_w >= 0.5), r=float(r_w), K2=bool(r_w <= 0)), PB3=dict(ok=bool(k_hi > k_lo), k_lo=float(k_lo), k_hi=float(k_hi), K3=bool(k_hi <= k_lo)),
         PB4=dict(ok=bool(ico.mean() >= 0.9 and r_tf <= -0.5), ico=float(ico.mean()), r_tf=float(r_tf)))
json.dump(dict(rho=rho.tolist(), Tf=Tf.tolist(), Tm=Tm.tolist(), Wrel=Wrel.tolist(), zeta=zeta.tolist(), dec=dec, kgs=kgs.tolist(), nrec=nrec.tolist(), phi=[float(x) for x in phi], verdicts=V),
          open('/home/claude/sub01_summary.json', 'w'), indent=1, default=float)
print('\n== ВЕРДИКТЫ B ==')
for k, v in V.items(): print(k, v)
