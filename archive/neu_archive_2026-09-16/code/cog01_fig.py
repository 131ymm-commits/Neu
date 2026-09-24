"""COG-01 — фигура атласа: запас рождения δ = w − ρ по сериям архива (полоса по группам) + вставка: доля цепей с рождением по N."""
import json, numpy as np
r = json.load(open('/home/claude/cog01_results.json')); A = r['archive']; R = r['random']
groups = [('dip', 'дипептид', '#8e44ad'), ('lj13', 'LJ13', '#8e44ad'), ('real', 'климат · эпидемии · планктон · сон', '#b7791f'), ('eeg', 'ЭЭГ Бонна', 'var(--cont)'), ('tel', 'телеграф (вложение)', 'var(--fold)')]
# термоакустика — отдельно из real
def gname(k, v):
    if v['group'] == 'real' and k.startswith('thermo'): return 'thermo'
    return v['group']
groups = [('dip', 'дипептид', '#8e44ad'), ('lj13', 'LJ13', '#8e44ad'), ('real', 'климат · эпидемии · сон', '#b7791f'), ('thermo', 'термоакустика', 'var(--osc)'), ('eeg', 'ЭЭГ Бонна', 'var(--cont)'), ('tel', 'телеграф (вложение m = 4)', 'var(--fold)')]
W, H = 760, 300; x0, x1 = 235, 500; y0 = 34; dy = 40
def PX(d): return x0 + (np.log10(max(d, 1e-4)) + 4) / (np.log10(0.3) + 4) * (x1 - x0)
s = [f'<svg viewBox="0 0 {W} {H}" width="100%" role="img" aria-label="Запас рождения уровня при огрублении по сериям архива">']
for d in (1e-4, 1e-3, 1e-2, 1e-1):
    s.append(f'<line x1="{PX(d):.1f}" y1="{y0-10}" x2="{PX(d):.1f}" y2="{y0+dy*len(groups)-12}" stroke="var(--grid)"/><text x="{PX(d):.1f}" y="{y0+dy*len(groups)}" font-size="10.5" fill="var(--ink3)" text-anchor="middle">{("≤ 0.0001" if d==1e-4 else f"{d:g}")}</text>')
rng = np.random.default_rng(0); hit = []
for gi, (g, lab, col) in enumerate(groups):
    y = y0 + gi * dy; vals = [(k, v) for k, v in A.items() if gname(k, v) == g]
    s.append(f'<text x="{x0-8}" y="{y+4}" font-size="11.5" fill="var(--ink2)" text-anchor="end">{lab} ({len(vals)})</text>')
    for k, v in vals:
        cx = PX(v['delta']); cy = y + rng.uniform(-9, 9); fill = col if not v['birth_pcca'] else 'var(--crit)'
        s.append(f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{4.2 if v["birth_pcca"] else 3.4}" fill="{fill}" opacity="0.85" stroke="var(--card)" stroke-width="0.8"/>')
        hit.append(f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="8" fill="transparent" data-n="{k}" data-k="δ = {v["delta"]:.3f} (w {v["w"]:.3f}, ρ {v["rho"]:.3f})" data-v="{"рождение по PCCA" if v["birth_pcca"] else "рождения по PCCA нет"}; запас по времени ×{(np.log(v["rho"])/np.log(v["w"]) if 0<v["w"]<1 else 1):.1f}"/>')
s.append(f'<text x="{(x0+x1)/2:.0f}" y="{y0+dy*len(groups)+16}" font-size="12" fill="var(--ink2)" text-anchor="middle">запас рождения δ = w − ρ (числовой радиус минус спектральный, дополнение к константам)</text>')
s.append(f'<text x="{x0}" y="{y0-20}" font-size="11" fill="var(--ink3)">красным — огрубление PCCA(2) родило уровень медленнее любой моды тонкой цепи</text>')
# вставка: случайные цепи
ix, iy = 528, 44; s.append(f'<text x="{ix}" y="{iy}" font-size="11" fill="var(--ink2)">случайные цепи, все 2-разбиения:</text>')
for i, N in enumerate((3, 4, 6)):
    v = R[f'nonrev_n{N}']; s.append(f'<text x="{ix}" y="{iy+16+i*15}" font-size="11" fill="var(--ink2)">N = {N}: рождение у {v["frac_chains_birth"]*100:.0f} %, AUC {v["auc_delta"]:.2f}</text>')
s.append(f'<text x="{ix}" y="{iy+16+3*15}" font-size="11" fill="var(--ink2)">обратимые: 0 из 8200</text>')
s.append(f'<text x="{ix}" y="{iy+16+5*15}" font-size="11" fill="var(--ink2)">f(EST-01) ≈ t_w/t_ρ, ρ_S = 0.87</text>')
s.append('<g id="cog01-hit">' + ''.join(hit) + '</g></svg>')
open('/home/claude/cog01_fig.svg', 'w').write(''.join(s)); print('ok', sum(len(x) for x in s))
