import json, numpy as np
s=open('/home/claude/atlas.html').read()
import re
i0=s.find('<section>\n  <div class="sechead">\n    <h2>Ручка ненормальности и транзиент по лагу</h2>')
if i0>0:
    j0=s.find('</section>\n\n',i0)+len('</section>\n\n'); s=s[:i0]+s[j0:]
    s=s.replace("""document.querySelectorAll('#knob01-hit circle').forEach(c=>{
  c.addEventListener('mousemove',e=>{ tt.innerHTML=`<b>${c.dataset.n}</b><br>${c.dataset.k} · ${c.dataset.v}`; tt.style.left=Math.min(e.clientX+14, innerWidth-260)+'px'; tt.style.top=(e.clientY+14)+'px'; tt.style.opacity=1; });
  c.addEventListener('mouseleave',()=>tt.style.opacity=0);
});
""",'')
    t0=s.find('    <div class="tile crit"><b>θ² · AUC 0.83 / 0.5 · 17/25 vs 0/14</b>'); t1=s.find('\n',t0)+1; s=s[:t0]+s[t1:]
    l0=s.find('      <li><b>Ручка, транзиент и свежие ряды (EST-02, KNOB-01, PERS-01, 2026-09-09)</b>'); l1=s.find('\n',l0)+1; s=s[:l0]+s[l1:]
K=json.load(open('/home/claude/knob01_results.json'))['verdicts']; c=K['curve']
P=json.load(open('/home/claude/pers01_results.json'))['verdicts']['r_medians']
W,H=760,300; ax0,ax1,ay0,ay1=56,340,24,240
def X(t): return ax0+t*(ax1-ax0)
def Y(v,lo,hi): return ay1-(v-lo)/(hi-lo)*(ay1-ay0)
sv=[f'<svg viewBox="0 0 {W} {H}" width="100%" role="img" aria-label="Ручка ненормальности и транзиент по лагу">']
for t in (0,0.2,0.4,0.6,0.8,1.0): sv.append(f'<line x1="{X(t):.1f}" y1="{ay0}" x2="{X(t):.1f}" y2="{ay1}" stroke="var(--grid)"/><text x="{X(t):.1f}" y="{ay1+14}" font-size="10.5" fill="var(--ink3)" text-anchor="middle">{t:g}</text>')
lo,hi=0.34,0.42
for v in (0.36,0.38,0.40,0.42): sv.append(f'<line x1="{ax0}" y1="{Y(v,lo,hi):.1f}" x2="{ax1}" y2="{Y(v,lo,hi):.1f}" stroke="var(--grid)"/><text x="{ax0-6}" y="{Y(v,lo,hi)+4:.1f}" font-size="10.5" fill="var(--ink3)" text-anchor="end">{v:.2f}</text>')
th=c['theta_rel']
sv.append('<path d="M '+' L '.join(f'{X(t):.1f} {Y(v,lo,hi):.1f}' for t,v in zip(th,c['w_median']))+'" fill="none" stroke="var(--crit)" stroke-width="2.2"/>')
sv.append('<path d="M '+' L '.join(f'{X(t):.1f} {Y(v,lo,hi):.1f}' for t,v in zip(th,c['rho_median']))+'" fill="none" stroke="var(--fold)" stroke-width="2.2"/>')
for t,v in zip(th,c['rho_median']): sv.append(f'<circle cx="{X(t):.1f}" cy="{Y(v,lo,hi):.1f}" r="3" fill="var(--fold)"/>')
for t,v in zip(th,c['frac_mean']): sv.append(f'<rect x="{X(t)-5:.1f}" y="{Y(v,0,0.02):.1f}" width="10" height="{ay1-Y(v,0,0.02):.1f}" fill="var(--osc)" opacity="0.45"/>')
sv.append(f'<text x="{ax0+6}" y="{ay0+10}" font-size="10.5" fill="var(--osc)">столбики — доля 2-разбиений с рождением (до 1.3 %)</text>')
sv.append(f'<text x="{ax0+6}" y="{Y(0.406,lo,hi)-6:.1f}" font-size="11" fill="var(--crit)">w — числовой радиус (не меняется)</text><text x="{ax0+6}" y="{Y(0.363,lo,hi)+14:.1f}" font-size="11" fill="var(--fold)">ρ — моды ускоряются, δ ∝ θ²</text>')
sv.append(f'<text x="{(ax0+ax1)/2:.0f}" y="{ay1+30}" font-size="12" fill="var(--ink2)" text-anchor="middle">ток θ/θ_max (200 цепей N = 6)</text>')
bx0,bx1=440,700
def BX(i): return bx0+i*(bx1-bx0)/3
def BY(v): return ay1-(np.log10(v)-np.log10(0.3))/(np.log10(1.6)-np.log10(0.3))*(ay1-ay0)
for v in (0.3,0.5,0.7,1.0,1.5): sv.append(f'<line x1="{bx0}" y1="{BY(v):.1f}" x2="{bx1}" y2="{BY(v):.1f}" stroke="var(--grid)"/><text x="{bx0-6}" y="{BY(v)+4:.1f}" font-size="10.5" fill="var(--ink3)" text-anchor="end">{v:g}</text>')
for i,l in enumerate((1,2,4,8)): sv.append(f'<text x="{BX(i):.1f}" y="{ay1+14}" font-size="10.5" fill="var(--ink3)" text-anchor="middle">{l}τ</text>')
sv.append(f'<line x1="{bx0}" y1="{BY(1.0):.1f}" x2="{bx1}" y2="{BY(1.0):.1f}" stroke="var(--ink3)" stroke-width="1.2" stroke-dasharray="4 4"/>')
cols=dict(dip='#8e44ad',lj13='#8e44ad',eeg='var(--cont)',tel='var(--fold)',real='#b7791f'); names=dict(dip='дипептид',lj13='LJ13',eeg='ЭЭГ (25)',tel='телеграф',real='реальные')
hit=[]
for g in ('lj13','dip','real','eeg','tel'):
    rs=P[g]; dash=' stroke-dasharray="5 3"' if g=='lj13' else ''
    sv.append('<path d="M '+' L '.join(f'{BX(i):.1f} {BY(v):.1f}' for i,v in enumerate(rs))+f'" fill="none" stroke="{cols[g]}" stroke-width="{2.4 if g=="eeg" else 1.8}"{dash}/>')
    for i,v in enumerate(rs): sv.append(f'<circle cx="{BX(i):.1f}" cy="{BY(v):.1f}" r="3" fill="{cols[g]}"/>'); hit.append(f'<circle cx="{BX(i):.1f}" cy="{BY(v):.1f}" r="8" fill="transparent" data-n="{names[g]}" data-k="лаг {2**i}τ" data-v="медиана r = {v:.2f}"/>')
    sv.append(f'<text x="{bx1+4}" y="{BY(rs[-1])+4:.1f}" font-size="10.5" fill="{cols[g]}">{names[g]}</text>')
J=json.load(open('/home/claude/pers01_results.json'))
for k in ('EEG_A_Z_Z013','EEG_D_F_F005','EEG_E_S_S001','EEG_C_N_N013','EEG_D_F_F001'):
    rs=[J[k]['lag'][s]['r'] for s in ('1','2','4','8')]; sv.append('<path d="M '+' L '.join(f'{BX(i):.1f} {BY(min(max(v,0.3),1.6)):.1f}' for i,v in enumerate(rs))+'" fill="none" stroke="var(--crit)" stroke-width="1.2" opacity="0.7"/>')
sv.append(f'<text x="{bx1}" y="{ay0+10}" font-size="10.5" fill="var(--crit)" text-anchor="end">красным — ЭЭГ с рождением по PCCA</text>')
sv.append(f'<text x="{(bx0+bx1)/2:.0f}" y="{ay1+30}" font-size="12" fill="var(--ink2)" text-anchor="middle">r(n) = ITS грубого / ITS тонкого по лагу</text>')
sv.append('<g id="knob01-hit">'+''.join(hit)+'</g></svg>')
svg=''.join(sv)
section='''<section>
  <div class="sechead">
    <h2>Ручка ненормальности и транзиент по лагу</h2>
    <p class="note">KNOB-01, PERS-01, EST-02 (2026-09-09). Слева: бездивергентный ток θ, добавленный к обратимой цепи, невидим любому двухсостоянному описанию на лаге τ (λ₂ всех 2-блочных лумпингов не меняются — точная лемма, 0 нарушений из 2200) и не меняет числовой радиус w, но ускоряет моды: ρ падает, запас δ растёт как θ²; рождение уровня при огрублении — обратная сторона «ускорения необратимостью». Производство энтропии рождений не предсказывает (AUC 0.5), ненормальность δ — предсказывает (0.83). Справа: рождённый огрублением уровень — транзиент по лагу: у обратимой динамики отношение грубой ITS к тонкой растёт с лагом снизу (LJ13 0.38 → 0.62, дипептид 0.86 → 0.97, 14/14), у ЭЭГ с рождением — падает от 1.3–1.5 до 0.5–0.9 (5/7 по кромке, 7/7 по знаку). Инверсии монотонности спектра вдоль цепи огрублений: 0/14 у молекулы и кластера, 17/25 у ЭЭГ. Множитель обратимости f = t_w/t_ρ воспроизведён на 107 свежих рядах (Спирмен 0.95, медиана отношения 1.000). Наведение — значения.</p>
  </div>
  <div class="card"><div id="knob01fig" style="width:100%">'''+svg+'''</div></div>
</section>

'''
marker='<section>\n  <div class="sechead">\n    <h2>Атлас шкал: рождение рекуррентности</h2>'
assert s.count(marker)==1; s=s.replace(marker, section+marker)
js='''document.querySelectorAll('#knob01-hit circle').forEach(c=>{
  c.addEventListener('mousemove',e=>{ tt.innerHTML=`<b>${c.dataset.n}</b><br>${c.dataset.k} · ${c.dataset.v}`; tt.style.left=Math.min(e.clientX+14, innerWidth-260)+'px'; tt.style.top=(e.clientY+14)+'px'; tt.style.opacity=1; });
  c.addEventListener('mouseleave',()=>tt.style.opacity=0);
});
</script>'''
assert s.count('});\n</script>')==1; s=s.replace('});\n</script>', '});\n'+js)
tile='''    <div class="tile crit"><b>θ² · AUC 0.83 / 0.5 · 17/25 vs 0/14</b><span>ток невидим двухсостоянному описанию (точная лемма), не меняет w и ускоряет моды — δ ∝ θ²; производство энтропии рождений не предсказывает, ненормальность — да; рождённый огрублением уровень — транзиент по лагу (ЭЭГ r 1.3–1.5 → 0.5–0.9, обратимые растут 14/14); инверсии спектра вдоль цепи огрублений 17/25 у ЭЭГ, 0/14 у молекулы и кластера; f = t_w/t_ρ на 107 свежих рядах — Спирмен 0.95 — EST-02 · KNOB-01 · PERS-01</span></div>
'''
tmarker='    <div class="tile crit"><b>W(A₀) · δ = 0 / 0.19</b>'
assert s.count(tmarker)==1; i=s.find(tmarker); j=s.find('\n',i)+1; s=s[:j]+tile+s[j:]
led='''      <li><b>Ручка, транзиент и свежие ряды (EST-02, KNOB-01, PERS-01, 2026-09-09)</b> — EST-02: f = t_w/t_ρ на 107 свежих рядах, Спирмен 0.95, в ×1.5 у 90 %, медиана отношения 1.000 (№105); KNOB-01: лемма ⟨A_θ g, g⟩ = ⟨S g, g⟩ (0 нарушений из 2200), w постоянен, ρ падает у 99 %, δ ∝ θ^2.00, AUC(δ) 0.83–0.84 против AUC(σ) 0.48–0.56, достижимость на 2-разбиениях 1.3 % (K1 по кромке), первая конструкция ручки вырождена и заменена до вердиктов (№106); PERS-01: инверсии 0/14 обратимых, 17/25 ЭЭГ, AUC(δ) 0.93; r(n) у рождённых ЭЭГ убывает 5/7 (7/7 по знаку), у обратимых растёт 14/14 (№107).</li>
'''
lmarker='      <li><b>Откуда берутся новые уровни (COG-01, 2026-09-09, в личине)</b>'
assert s.count(lmarker)==1; s=s.replace(lmarker, led+lmarker)
open('/home/claude/atlas.html','w').write(s); print('ok', len(s))
