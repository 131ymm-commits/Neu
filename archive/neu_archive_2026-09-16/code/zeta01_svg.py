"""ZETA-01 — рисунок для атласа: ζ-атлас реальных рядов (медиана и 5–95 % постериора, log-ось), опорные классы из SPEC-01.
Выход: zeta01_fig_inline.svg (CSS-переменные атласа) и zeta01_fig.svg (автономный, светлая палитра)."""
import json, numpy as np
r = json.load(open('/home/claude/zeta01_results.json')); ph = json.load(open('/home/claude/zeta01_posthoc.json'))
def row(name, items):   # items: список (ζ, [q5, q95]) или None
    return (name, items)
eeg_names = {'A_Z': 'ЭЭГ A (здоровые, глаза открыты)', 'B_O': 'ЭЭГ B (здоровые, глаза закрыты)', 'C_N': 'ЭЭГ C (интерикт., противопол.)', 'D_F': 'ЭЭГ D (интерикт., очаг)', 'E_S': 'ЭЭГ E (приступ)'}
def g(k): v = r[k]; return (v['zeta_median'], v['zeta_q']) if v.get('zeta_median') is not None else None
rows = [row('дипептид 400–700 K (SPEC-01, 6 прогонов)', [(4.8, [4.8, 15.0])]), row('LJ13 сосуществование (SPEC-01)', [(1.25, [0.96, 1.60])]),
        row('сон, 6 ночей (SPEC-01)', [(0.7, [0.29, 0.93])]), row('случайные обратимые цепи (нуль)', [(0.09, [0.05, 0.2])]), None,
        row('NGRIP δ¹⁸O 0–60 ka, m = 4', [g('NGRIP_d18O_20yr_m4')]), row('NGRIP δ¹⁸O 0–60 ka, m = 1', [g('NGRIP_d18O_20yr_m1')]),
        row('NGRIP 12–60 ka, m = 4 (пост-хок)', [(ph['NGRIP_12-60ka_m4']['zeta_median'], ph['NGRIP_12-60ka_m4']['zeta_q'])]),
        row('NGRIP 27–59 ka, m = 4 (пост-хок)', [(ph['NGRIP_27-59ka_m4']['zeta_median'], ph['NGRIP_27-59ka_m4']['zeta_q'])]),
        row('NGRIP 27–59 ka, фазовый суррогат', [(ph['NGRIP_27-59ka_phase_surrogate_m4']['zeta_median'], ph['NGRIP_27-59ka_phase_surrogate_m4']['zeta_q'])]), None]
for grp, nm in eeg_names.items(): rows.append(row(nm, [g(k) for k in r if k.startswith('EEG_' + grp)]))
rows += [None, row('планктон Бенинки (12 видов)', [g('plankton_Beninca_12sp')]), row('LR04 бентосный стек', [g('LR04_benthic_m4')]), row('EPICA дейтерий', [g('EPICA_deuterium_m4')]),
         row('солнечные пятна (контроль периодики)', [g('sunspots_monthly_m4')]), row('корь, Нью-Йорк', [g('measles_NY_weekly_m4')]), row('гейзер Старый Верный', [g('faithful_eruptions_m2')]),
         row('COVID приросты (DE, US, IT)', [g(f'COVID_{c}_daily_m4') for c in ('Germany', 'US', 'Italy')]), row('термоакустика перед Хопфом (3 ряда)', [g(f'thermoacoustic_{i}_m4') for i in (1, 2, 3)])]
X0, X1, W = 250, 730, 760; xmin, xmax = np.log10(0.05), np.log10(20); rh = 13; top = 34
H = top + rh * len(rows) + 30
def X(z): return X0 + (X1 - X0) * (np.log10(max(z, 0.05)) - xmin) / (xmax - xmin)
def build(css):
    C = (lambda v: f'var(--{v})') if css else (lambda v: dict(ink='#1B2530', ink2='#3b4a5a', ink3='#6b7a8a', grid='#E7EBF0', crit='#C0392B', fold='#2a78d6', cont='#199e70', osc='#d95926')[v])
    s = [f'<svg viewBox="0 0 {W} {H}" width="100%" role="img" aria-label="ζ-атлас реальных рядов: медиана и 5–95 % постериора">']
    # полосы классов
    s.append(f'<rect x="{X(0.05):.1f}" y="{top-6}" width="{X(0.9)-X(0.05):.1f}" height="{rh*len(rows)+6}" fill="{C("cont")}" opacity="0.07"/>')
    s.append(f'<rect x="{X(0.9):.1f}" y="{top-6}" width="{X(2)-X(0.9):.1f}" height="{rh*len(rows)+6}" fill="{C("fold")}" opacity="0.07"/>')
    s.append(f'<rect x="{X(2):.1f}" y="{top-6}" width="{X(20)-X(2):.1f}" height="{rh*len(rows)+6}" fill="{C("crit")}" opacity="0.07"/>')
    for lab, z in (('континуум', 0.21), ('иерархия', 1.34), ('выброс', 6.3)): s.append(f'<text x="{X(z):.1f}" y="{top-10}" font-size="10.5" fill="{C("ink3")}" text-anchor="middle">{lab}</text>')
    for t in (0.1, 0.3, 1, 3, 10):
        s.append(f'<line x1="{X(t):.1f}" y1="{top-6}" x2="{X(t):.1f}" y2="{top+rh*len(rows)}" stroke="{C("grid")}"/><text x="{X(t):.1f}" y="{top+rh*len(rows)+14}" font-size="10.5" fill="{C("ink3")}" text-anchor="middle">{t:g}</text>')
    s.append(f'<line x1="{X(1):.1f}" y1="{top-6}" x2="{X(1):.1f}" y2="{top+rh*len(rows)}" stroke="{C("ink3")}" stroke-dasharray="4 4"/>')
    s.append(f'<text x="{(X0+X1)/2:.1f}" y="{H-4}" font-size="11" fill="{C("ink2")}" text-anchor="middle">ζ = z₁ / z̄_rest (верхний реньевский лог-зазор к среднему остальных); отрезок — 5–95 % постериора</text>')
    for i, rw in enumerate(rows):
        y = top + rh * i + rh * 0.65
        if rw is None: continue
        name, items = rw
        s.append(f'<text x="{X0-8}" y="{y:.1f}" font-size="10.5" fill="{C("ink")}" text-anchor="end">{name}</text>')
        for it in items:
            if it is None: s.append(f'<text x="{X(0.06):.1f}" y="{y:.1f}" font-size="10" fill="{C("ink3")}">не разрешён</text>'); continue
            z, q = it; col = C('crit') if z >= 2 else (C('fold') if z >= 0.9 else C('cont'))
            if q: s.append(f'<line x1="{X(q[0]):.1f}" y1="{y-3.5:.1f}" x2="{X(q[1]):.1f}" y2="{y-3.5:.1f}" stroke="{col}" stroke-width="1.2" opacity="0.6"/>')
            s.append(f'<circle cx="{X(z):.1f}" cy="{y-3.5:.1f}" r="3.4" fill="{col}"><title>{name}: ζ = {z:.2f}</title></circle>')
    s.append('</svg>'); return ''.join(s)
open('/home/claude/zeta01_fig_inline.svg', 'w').write(build(True)); open('/home/claude/zeta01_fig.svg', 'w').write(build(False))
print('строк', len(rows), 'высота', H)
