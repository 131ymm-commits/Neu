"""HOR-02 — фигура атласа: (a) медиана |β_loc| против N_c по семействам с пуассоновой кривой и полосой телеграфа; (b) спайк первого оборота против лог-зазора."""
import json, numpy as np
r = json.load(open('/home/claude/hor02_results.json')); V = r['verdicts']; sp = json.load(open('/home/claude/hor02_spikes.json'))
W, H = 760, 345
def px(x, x0, x1, X0, X1): return X0 + (np.log10(x) - np.log10(x0)) / (np.log10(x1) - np.log10(x0)) * (X1 - X0)
# --- панель (a): log-log, N_c 1.5…800, |β| 0.03…3
ax0, ax1, ay0, ay1 = 56, 440, 20, 250; nx0, nx1, by0, by1 = 1.5, 800, 0.03, 3.0
def PX(n): return px(n, nx0, nx1, ax0, ax1)
def PY(b): return ay1 - (np.log10(b) - np.log10(by0)) / (np.log10(by1) - np.log10(by0)) * (ay1 - ay0)
s = [f'<svg viewBox="0 0 {W} {H}" width="100%" role="img" aria-label="Рождение рекуррентности: ошибка верхней шкалы против числа оборотов и спайк против зазора">']
for n in (2, 5, 10, 20, 50, 100, 200, 500):
    s.append(f'<line x1="{PX(n):.1f}" y1="{ay0}" x2="{PX(n):.1f}" y2="{ay1}" stroke="var(--grid)"/><text x="{PX(n):.1f}" y="{ay1+14}" font-size="10.5" fill="var(--ink3)" text-anchor="middle">{n}</text>')
for b in (0.03, 0.1, 0.3, 1, 3):
    s.append(f'<line x1="{ax0}" y1="{PY(b):.1f}" x2="{ax1}" y2="{PY(b):.1f}" stroke="var(--grid)"/><text x="{ax0-6}" y="{PY(b)+4:.1f}" font-size="10.5" fill="var(--ink3)" text-anchor="end">{b:g}</text>')
s.append(f'<line x1="{ax0}" y1="{PY(0.3):.1f}" x2="{ax1}" y2="{PY(0.3):.1f}" stroke="var(--ink3)" stroke-width="1.2" stroke-dasharray="4 4"/>')
# полоса телеграфа 10–90 %
cv = [c for c in V['curves']['tel'] if c['lo'] >= 1.5]
top = ' '.join(f"{PX(c['center']):.1f},{PY(max(c['p90'], by0)):.1f}" for c in cv); bot = ' '.join(f"{PX(c['center']):.1f},{PY(max(c['p10'], by0)):.1f}" for c in reversed(cv))
s.append(f'<polygon points="{top} {bot}" fill="var(--fold)" opacity="0.13"/>')
# пуассонова кривая 0.95 N^-0.52
xs = np.geomspace(1.5, 800, 40); s.append('<path d="M ' + ' L '.join(f'{PX(x):.1f} {PY(0.95*x**-0.52):.1f}' for x in xs) + '" fill="none" stroke="var(--ink3)" stroke-width="1.2" stroke-dasharray="2 3"/>')
cols = dict(tel='var(--fold)', hier2='var(--osc)', dip='var(--crit)', lj13='#8e44ad', ar1='var(--ink3)', eeg='var(--cont)', real='#b7791f')
names = dict(tel='телеграф', hier2='иерархический телеграф', dip='дипептид', lj13='LJ13', ar1='AR(1)', eeg='ЭЭГ Бонна', real='реальные ряды')
def curve_group(g):
    E = [1.5, 3, 6, 12, 25, 50, 100, 200, 400, 1e9]; ps = [(p['nc_m'], p['beta']) for k, v in r.items() if v.get('group') == g for p in v['pairs']]
    out = []
    for a, b in zip(E[:-1], E[1:]):
        bs = [abs(be) for nc, be in ps if a <= nc < b]
        if len(bs) >= 3: out.append((float(np.sqrt(a * min(b, 800))), float(np.median(bs)), len(bs)))
    return out
hit = []
for g in ('tel', 'hier2', 'lj13', 'ar1', 'dip', 'eeg', 'real'):
    pts = [(c['center'], c['med_abs'], c['n']) for c in V['curves'][g] if c['lo'] >= 1.5] if g in V['curves'] else curve_group(g)
    if not pts: continue
    s.append('<path d="M ' + ' L '.join(f'{PX(x):.1f} {PY(max(y, by0)):.1f}' for x, y, _ in pts) + f'" fill="none" stroke="{cols[g]}" stroke-width="{2.2 if g in ("tel","real") else 1.6}"/>')
    for x, y, n in pts:
        s.append(f'<circle cx="{PX(x):.1f}" cy="{PY(max(y, by0)):.1f}" r="3.4" fill="{cols[g]}" stroke="var(--card)" stroke-width="1"/>'); hit.append(f'<circle cx="{PX(x):.1f}" cy="{PY(max(y, by0)):.1f}" r="9" fill="transparent" data-n="{names[g]}" data-k="N_c ≈ {x:.0f}" data-v="|β| {y:.2f} ({n} пар)"/>')
s.append(f'<text x="{(ax0+ax1)/2:.0f}" y="{ay1+30}" font-size="12" fill="var(--ink2)" text-anchor="middle">оборотов верхнего процесса в окне, N_c(m)</text>')
s.append(f'<text x="14" y="{(ay0+ay1)/2:.0f}" font-size="12" fill="var(--ink2)" text-anchor="middle" transform="rotate(-90 14 {(ay0+ay1)/2:.0f})">медиана |log₂ t₁(2m)/t₁(m)|</text>')
s.append(f'<text x="{PX(1.7):.0f}" y="{ay0+12}" font-size="11" fill="var(--ink3)">пунктир — Пуассон 0.95·N_c^−0.52; линия 0.3 — «сошлось»</text>')
# легенда — строкой под осями
lx = ax0; ly = ay1 + 52
for g in ('tel', 'hier2', 'dip', 'lj13', 'ar1', 'eeg', 'real'):
    s.append(f'<line x1="{lx}" y1="{ly}" x2="{lx+14}" y2="{ly}" stroke="{cols[g]}" stroke-width="2.4"/><text x="{lx+18}" y="{ly+4}" font-size="10.5" fill="var(--ink2)">{names[g]}</text>'); lx += 18 + 6.3 * len(names[g]) + 16
# --- панель (b): спайк против зазора
bx0, bx1 = 505, 740; gx0, gx1 = 0, 11
def BX(x): return bx0 + (x - gx0) / (gx1 - gx0) * (bx1 - bx0)
def BY(y): return ay1 - (y - gx0) / (gx1 - gx0) * (ay1 - ay0)
for v in (0, 2, 4, 6, 8, 10):
    s.append(f'<line x1="{BX(v):.1f}" y1="{ay0}" x2="{BX(v):.1f}" y2="{ay1}" stroke="var(--grid)"/><text x="{BX(v):.1f}" y="{ay1+14}" font-size="10.5" fill="var(--ink3)" text-anchor="middle">{v}</text>')
    s.append(f'<line x1="{bx0}" y1="{BY(v):.1f}" x2="{bx1}" y2="{BY(v):.1f}" stroke="var(--grid)"/><text x="{bx0-6}" y="{BY(v)+4:.1f}" font-size="10.5" fill="var(--ink3)" text-anchor="end">{v}</text>')
s.append(f'<line x1="{BX(0):.1f}" y1="{BY(0):.1f}" x2="{BX(10.5):.1f}" y2="{BY(10.5):.1f}" stroke="var(--ink3)" stroke-width="1.2" stroke-dasharray="4 4"/>')
rng = np.random.default_rng(0)
for g, k, beta, gap in sp:
    x = min(max(gap + rng.normal(0, 0.08), gx0), gx1); y = min(max(beta, gx0), gx1 - 0.1)
    s.append(f'<circle cx="{BX(x):.1f}" cy="{BY(y):.1f}" r="3.2" fill="{cols[g]}" opacity="0.75" stroke="var(--card)" stroke-width="0.8"/>'); hit.append(f'<circle cx="{BX(x):.1f}" cy="{BY(y):.1f}" r="8" fill="transparent" data-n="{k}" data-k="зазор {gap:.1f}" data-v="спайк {beta:.1f}"/>')
s.append(f'<text x="{(bx0+bx1)/2:.0f}" y="{ay1+30}" font-size="12" fill="var(--ink2)" text-anchor="middle">лог-зазор полного спектра log₂(t₁/t₂)</text>')
s.append(f'<text x="{bx0-40}" y="{(ay0+ay1)/2:.0f}" font-size="12" fill="var(--ink2)" text-anchor="middle" transform="rotate(-90 {bx0-40} {(ay0+ay1)/2:.0f})">спайк первого оборота, бит</text>')
s.append(f'<text x="{bx1-4}" y="{ay1-8}" font-size="11" fill="var(--ink3)" text-anchor="end">пунктир — спайк = зазор</text>')
s.append('<g id="hor02-hit">' + ''.join(hit) + '</g></svg>')
open('/home/claude/hor02_fig.svg', 'w').write(''.join(s)); print('ok', sum(len(x) for x in s))
