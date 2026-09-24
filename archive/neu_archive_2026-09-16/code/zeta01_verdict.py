"""ZETA-01 — вердикты по PREREG (P-Z1..P-Z3, K1..K3) из zeta01_results.json; сводная таблица классов."""
import json, numpy as np
r = json.load(open('/home/claude/zeta01_results.json'))
def cls(z):
    if z is None: return 'не разрешён'
    return 'выброс' if z >= 2 else ('иерархия' if z >= 0.9 else 'континуум')
rows = []
for k, v in r.items():
    if 'err' in v: rows.append((k, None, None, 'ошибка', v['err'][:60])); continue
    rows.append((k, v['zeta_median'], v['zeta_q'], v['dec'], cls(v['zeta_median'])))
print(f"{'ряд':26s} {'ζ':>6s} {'[5%,95%]':>14s} {'решение':>18s} класс")
for k, z, q, d, c in rows:
    print(f"{k:26s} {('%.2f' % z) if z is not None else '  —  ':>6s} {('[%.2f, %.2f]' % tuple(q)) if q else '':>14s} {d:>18s} {c}")
ng4, ng1 = r['NGRIP_d18O_20yr_m4'], r['NGRIP_d18O_20yr_m1']
eeg = {k: v for k, v in r.items() if k.startswith('EEG_')}
n_no = sum(v['dec'] == 'нет' for v in eeg.values()); n_z1 = sum((v['zeta_median'] or 9) < 1 for v in eeg.values()); n_lvl = sum(v['dec'] == 'уровень' for v in eeg.values())
pl = r['plankton_Beninca_12sp']; ss = r['sunspots_monthly_m4']
V = dict(
    PZ1=dict(ok=bool(ng4['dec'] == 'уровень' and ng4['zeta_median'] >= 2), dec_m4=ng4['dec'], zeta_m4=ng4['zeta_median'], zeta_q_m4=ng4['zeta_q'], dec_m1=ng1['dec'], zeta_m1=ng1['zeta_median'], zeta_q_m1=ng1['zeta_q']),
    PZ2=dict(ok=bool(n_no >= 20 and n_z1 >= 20), n_no=n_no, n_zeta_lt1=n_z1, n_level=n_lvl, n=len(eeg),
             zeta_by_set={g: [round(v['zeta_median'], 2) for k, v in eeg.items() if k.startswith('EEG_' + g)] for g in ('A_Z', 'B_O', 'C_N', 'D_F', 'E_S')}),
    PZ3=dict(ok=bool(pl['dec'] != 'отказ:не разрешён' and pl['dec'] != 'уровень' and pl['zeta_median'] is not None and 0.6 <= pl['zeta_median'] <= 1.6), dec=pl['dec'], zeta=pl['zeta_median'], zeta_q=pl['zeta_q'], m_median=pl['m_median']),
    K1=dict(hit=bool((ng4['dec'] == 'нет' or ng4['zeta_median'] < 1.5) and (ng1['dec'] == 'нет' or ng1['zeta_median'] < 1.5))),
    K2=dict(hit=bool(n_lvl >= 5), n_level=n_lvl), K3=dict(hit=bool(ss['dec'] == 'уровень'), dec=ss['dec'], zeta=ss['zeta_median']))
counts = {}
for k, z, q, d, c in rows: counts[c] = counts.get(c, 0) + 1
print('\nклассы по атласу:', counts, '| решений «уровень»:', sum(d == 'уровень' for *_, d, _ in rows))
print('\n== ВЕРДИКТЫ ==')
for k, v in V.items(): print(k, v)
json.dump(dict(table=[dict(name=k, zeta=z, zeta_q=q, dec=d, cls=c) for k, z, q, d, c in rows], verdicts=V, class_counts=counts), open('/home/claude/zeta01_summary.json', 'w'), indent=1, default=float)
