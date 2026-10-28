# PRECOND-01: адресная сверка чисел REPORT_final.md с open_an.json, val_an.json, posthoc_an.json и final_facts.json (по образцу check_final_think.py).
# Каждое число строится из json в формате отчёта и ищется в тексте дословно.
import json, sys
o, v, ph, F = (json.load(open(f)) for f in ('open_an.json', 'val_an.json', 'posthoc_an.json', 'final_facts.json'))
T = open('REPORT_final.md', encoding='utf-8').read()
def r(x): s = f'{x:.3f}'.rstrip('0').rstrip('.') if isinstance(x, float) else str(x); return s.replace('-', '−').replace('.', ',')
def sg(x): return ('+' if x > 0 else '') + r(x)
def ci(c): return f'{r(c[0])} … {r(c[1])}'
def big(n): n = round(n); return f'{n:,}'.replace(',', ' ') if n >= 10000 else str(n)
def pp(p): return f'{p:.4f}'.replace('.', ',') if p < 0.01 else r(round(p, 3))
need = []
# открытие: вопрос 1, главные действия, взаимодействие, посредник, насыщение, потолок, победители
me = o['main_effects']
need += [f'p {r(o["Q1"]["p"])}', f'{big(o["permutations"])} перестановок', f'вызовов {sum(o["vote_status_totals"].values())}',
         f'«ок» {o["vote_status_totals"]["ok"]}, отказов {o["vote_status_totals"]["refused"]}']
assert not o['vote_status_nonok'] and o['n_tasks'] == 9 and not o['excluded_eps']
for f in sorted(me, key=lambda f: me[f]['effect_raw']):
    x = me[f]; need.append(f'| {f} | {sg(x["effect"])} | {ci(x["t"]["ci95"])} | {pp(x["p_fl"])} | {"да" if x["holm_reject"] else "нет"} | '
                          f'{"+" if x["out"] > 0 else "−"}{big(abs(x["out"]))} | {r(x["refusal_on"])} |')
assert [f for f in me if me[f]['holm_reject']] == ['REFUSE']
x = o['REFUSE_x_CLAIMS']; need += [f'{sg(x["effect"])} (p {r(x["p_fl"])})', f'{sg(x["effect"])}, ДИ {ci(x["t"]["ci95"])}, p {r(x["p_fl"])}']
md = o['mediator_descriptive']; need += [f'коэффициент ln(выход) {r(md["ln_out"])}', f'действие REFUSE {r(md["REFUSE"])}', f'падает до {r(md["REFUSE"])}']
pw = ph['power_posthoc']; need += [f'остаточный sd {r(pw["resid_sd"])}', f'в {r(pw["Q1"])} повторов', f'в {r(pw["REFUSE_fl"])}']
need += [f'линейный член {r(ph["linear"]["mean"])} (ДИ {ci(ph["linear"]["ci95"])})', f'k² {sg(ph["k2"]["mean"])} (ДИ {ci(ph["k2"]["ci95"])})']
assert ph['k2_equals_open_an'] and ph['saturation_by_prereg']
pairs = sorted(o['pairs_descriptive'].items(), key=lambda kv: -abs(kv[1]))[:2]
need += [f'{k.replace("×", " × ")} {sg(x)}' for k, x in pairs]
cd = o['conf_descriptive']; need += [f'{cd["n"]} голосов', f'средняя p_best {r(cd["mean_p"])}', f'в {r(cd["hit"])} голосов']
rd = o['refusal_decomposition']; need += [f'отказов {r(rd["share"])} голосов', f'у отказавшихся {r(rd["A0_regret_refused"])}', f'у ответивших {r(rd["answered_regret"])}',
                                         f'{sg(rd["contribution"])}']
c = o['ceiling']; need += [f'D_m = M0 − C63 на medium: {r(c["D_m"]["mean"])} (ДИ {ci(c["D_m"]["ci95"])})', f'D_h = H0 − H1 на high: {r(c["D_h"]["mean"])} (ДИ {ci(c["D_h"]["ci95"])})',
                           f'd = D_h − 0,5·D_m: {r(c["d"]["mean"])} (ДИ {ci(c["d"]["ci95"])})', f'«{c["outcome"]}»', f'H1 {r(c["H1_mean"])} < 0,1',
                           f'регрет {r(c["H1_mean"])}, «всё выключено» — {r(c["H0_mean"])}', f'на medium — {r(c["allon_medium_mean"])} и {r(c["M0_mean"])}']
assert c['outcome'] == 'гипотеза потолка не опровергнута' and c['D_m']['mean'] > 0
op = o['out_per_call']; need += [f'medium {big(op["medium64"])} токенов, high {big(op["high"])}']
w = o['winners']; need += [f'Регрет {r(w["cell_means"][w["obs_cell"]])}, лучший из 64', f'выигрыш на открытии, {r(w["gain_open"]["MODEL"])},',
                           f'{r(w["cell_means"]["C44"])}, пятое место из 64', f'на открытии — {r(w["gain_open"]["OBS"])}', f'p {r(w["selection_null_p"])}',
                           f'в {r(w["selection_null_p"])} перестановок', f'клеток — {r(o["mean_regret"]["all64"])}', f'A0 без вызовов — {r(o["mean_regret"]["A0_no_calls"])}']
assert w['obs_cell'] == 'C12' and w['model_cell'] is None and ph['rank_unrounded']['ANCHOR_C44'] == 5
need += [f'**{a}** — ' for a in ('OBS', 'MODEL', 'ANCHOR')] + [', '.join(w['arms']['OBS']), ', '.join(w['arms']['MODEL'])]
# ожидания: строки таблицы и исходы — по final_facts.json (правила закоммичены до правды проверки)
E = F['expectations']; word = {True: 'сбылось', False: 'не сбылось', None: 'не определено'}
rows = {ln.split('|')[1].strip(): ln for ln in T.splitlines() if ln.startswith('| E')}
bad = [k for k, x in E.items() if k not in rows or rows[k].split('|')[-2].strip().split(':')[0] != word[x['outcome']]]
miss = [n for n in need if n not in T] + [f'строка ожидания {k}: исход не совпал с final_facts.json' for k in bad]
print(f'проверено фраз: {len(need)}; не найдено: {len(miss)}')
[print('  НЕТ:', x) for x in miss]
sys.exit(1 if miss else 0)
