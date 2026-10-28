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
need += [f'p {r(o["Q1"]["p"])}', f'{big(o["permutations"])} перестановок', f'Вызовов {sum(o["vote_status_totals"].values())}', f'Вызовов {sum(v["vote_status_totals"].values())}',
         f'«ок» {o["vote_status_totals"]["ok"]}, отказов {o["vote_status_totals"]["refused"]}']
assert not o['vote_status_nonok'] and o['n_tasks'] == 9 and not o['excluded_eps']
for f in sorted(me, key=lambda f: me[f]['effect_raw']):
    x = me[f]; need.append(f'| {f} | {sg(x["effect"])} | {ci(x["t"]["ci95"])} | {pp(x["p_fl"])} | {"да" if x["holm_reject"] else "нет"} | '
                          f'{"+" if x["out"] > 0 else "−"}{big(abs(x["out"]))} | {r(x["refusal_on"])} |')
assert [f for f in me if me[f]['holm_reject']] == ['REFUSE']
x = o['REFUSE_x_CLAIMS']; need += [f'{sg(x["effect"])} (p {r(x["p_fl"])})', f'{sg(x["effect"])}, ДИ {ci(x["t"]["ci95"])}, p {r(x["p_fl"])}']
md = o['mediator_descriptive']; need += [f'коэффициент ln(выход) {r(md["ln_out"])}', f'действие REFUSE {r(md["REFUSE"])}', f'коэффициент REFUSE равен {r(md["REFUSE"])}']
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
# проверка победителя: таблица рук, первичный тест, сжатие, отказы
assert v['n_tasks'] == 50 and not v['excluded_eps'] and not v['aliases'] and set(v['vote_status_totals']) == {'ok', 'refused'}
need += [f'«ок» {v["vote_status_totals"]["ok"]}, отказов {v["vote_status_totals"]["refused"]}']
for a in ('ANCHOR', 'MODEL', 'OBS'):
    row = f'| {", ".join(w["arms"][a])} | {r(v["mean_regret"][a])} | '
    row += '— | — | ' if a == 'ANCHOR' else f'{sg(v["vs_anchor"][a]["mean"])} | {ci(v["vs_anchor"][a]["ci95"])} | '
    need.append(row + f'{big(v["out_per_call"][a])} | {v["refusals"][a]} |')
need.append(f'| {r(v["A0_no_calls"])} |')
pr = v['primary']; d_ = pr['diff_obs_minus_model']; assert pr['outcome'] == 'не показано' and not any(v['degenerate_to_A0'].values())
need += [f'OBS − MODEL {sg(d_["mean"])}, ДИ {ci(d_["ci95"])}, df {d_["df"]}, односторонний p {r(round(d_["p_greater"], 3))}',
         f'OBS − MODEL {sg(d_["mean"])} (ДИ {ci(d_["ci95"])}; односторонний p {r(round(d_["p_greater"], 3))})',
         f'у OBS {r(v["gain_val"]["OBS"])}, у MODEL {r(v["gain_val"]["MODEL"])}', f'Сжатие OBS — {r(v["shrinkage"]["OBS"])}', f'Сжатие MODEL — {r(v["shrinkage"]["MODEL"])}',
         f'хуже опоры ANCHOR на {r(-v["vs_anchor"]["OBS"]["mean"])} (ДИ разности ANCHOR − OBS {ci(v["vs_anchor"]["OBS"]["ci95"])})',
         f'Нижняя граница ДИ ANCHOR − OBS — {r(v["vs_anchor"]["OBS"]["ci95"][0])}', f'Разница с опорой не показана: {r(v["vs_anchor"]["MODEL"]["mean"])} (ДИ {ci(v["vs_anchor"]["MODEL"]["ci95"])})',
         f'регрет {r(v["mean_regret"]["ANCHOR"])}, у MODEL {r(v["mean_regret"]["MODEL"])}, у OBS {r(v["mean_regret"]["OBS"])}',
         f'сбылось: {r(v["shrinkage"]["OBS"])}, выигрыш сменил знак', f'сбылось: точечно {sg(d_["mean"])}, тест не прошёл (p {r(round(d_["p_greater"], 3))})',
         f'не сбылось: {r(v["vs_anchor"]["OBS"]["ci95"][0])} |']
vr = ph['val_refusals']
need += [f'MODEL отказывается в {r(vr["MODEL"]["share"])} голосов, ANCHOR — в {r(vr["ANCHOR"]["share"])}',
         f'MODEL {sg(vr["MODEL"]["contribution"])}: {vr["MODEL"]["refused"]} отказа из {vr["MODEL"]["votes"]}, у каждого регрет A0 своей задачи, в среднем {r(vr["MODEL"]["A0_regret_refused"])}',
         f'ANCHOR оно даёт {sg(vr["ANCHOR"]["contribution"])}: {vr["ANCHOR"]["refused"]} отказов, в среднем {r(vr["ANCHOR"]["A0_regret_refused"])}',
         f'MODEL {r(vr["MODEL"]["answered_regret"])}, ANCHOR {r(vr["ANCHOR"]["answered_regret"])}, OBS {r(vr["OBS"]["answered_regret"])}',
         f'ANCHOR (без UNSURE) — {r(vr["ANCHOR"]["share"])}, MODEL (с UNSURE) — {r(vr["MODEL"]["share"])}']
orc = ph['open_refusals_by_cell']; ru, rn = orc['REFUSE=да, UNSURE=да'], orc['REFUSE=да, UNSURE=нет']
assert orc['REFUSE=нет, UNSURE=да']['refused'] == orc['REFUSE=нет, UNSURE=нет']['refused'] == 0 and ru['refused'] + rn['refused'] == o['vote_status_totals']['refused']
need += [f'{r(ru["share"])} голосов ({ru["refused"]} из {ru["votes"]})', f'без UNSURE — {r(rn["share"])} ({rn["refused"]} из {rn["votes"]})', f'у C44 — {ph["open_refusals_C44"]} из 9',
         f'из них {r(ru["share"])} с UNSURE и {r(rn["share"])} без него', f'({o["vote_status_totals"]["refused"]} отказов)']
need += [f'в {r(F["out_ratio_high_medium"])} раза больше: {big(op["high"])} против {big(op["medium64"])}']
assert vr['OBS']['refused'] == 0 and all(vr[a]['refused'] == v['refusals'][a] for a in vr)
need += [f'(0,118) лучше лучшей из 64 клеток на medium (0,218)'] if (r(c['H0_mean']), r(w['cell_means'][w['obs_cell']])) == ('0,118', '0,218') else ['H0 и OBS: числа не те']
# порядок этапов, вызовы, потоки — по final_facts.json
od = F['order']
for st_, name in (('open', 'открытие'), ('val', 'проверка')):
    x = od[st_]; assert x['evals_sha256'] == x['evals_sha_on_disk'] and x['salt_sha_published'] == x['salt_sha_prereg'] and x['commit_at'][:19] < x['push_time'][:19] < x['truth_first_mtime']
    need.append(f'| {name} | {x["commit"]}, {x["commit_at"][8:10]}.{x["commit_at"][5:7]} {x["commit_at"][11:19]} | {x["push_time"][11:]} | {x["truth_first_mtime"][11:19]} |')
    need.append(x['evals_sha256'][:8])
cm = F['commits']; need += [f'`winners.json`, {cm["winners.json"]["commit"]})'] + [f'({cm[k]["commit"]})' for k in ('run/val_eval_medium_jobs.jsonl', 'pools/WH_8359.json', 'final_facts_precond.py')]
need += [f'| {cm[k]["commit"]} |' for k in ('salts/open_salt.txt', 'salts/val_salt.txt')] + [f'| {cm[k]["commit"]} | ' for k in ('open_an.json', 'val_an.json')]
assert F['code_mismatch'] == ['checkin_precond.sh']
need += [f'из {F["code_files"]} файлов `prereg_hashes.json` (PREREG §10) sha256 на диске совпал у {F["code_files"] - len(F["code_mismatch"])}']
names = dict(open_exec='исполнитель, открытие', val_exec='исполнитель, проверка', open_eval_medium='оценщики, открытие', open_eval_high='оценщики, открытие', val_eval_medium='оценщики, проверка')
for g, x in F['calls'].items():
    assert list(x['finals']) == ['годный'] and x['models'] == ['claude-opus-5-5'] and x['cli'] == ['2.1.294'] and x['init_tools'] == [['StructuredOutput']] and x['mcp_servers'] == [[]] and x['started_unrecorded'] == 0
    need.append(f'| {names[g]} | {x["effort"][0]} | {x["finals"]["годный"]} | {x["attempts"]} | {x["no_answer_attempts"]} | {big(x["out_all"])} |')
need += [f'Выход всего — {big(F["out_total"])} токенов', F['calls']['val_exec']['binary_sha256'][0][:8], f'У всех {F["streams"]["совпал"]} записей']
assert F['streams'] == {'совпал': sum(x['attempts'] for x in F['calls'].values())}
# ожидания: строки таблицы и исходы — по final_facts.json (правила закоммичены до правды проверки)
E = F['expectations']; word = {True: 'сбылось', False: 'не сбылось', None: 'не определено'}
rows = {ln.split('|')[1].strip(): ln for ln in T.splitlines() if ln.startswith('| E')}
bad = [k for k, x in E.items() if k not in rows or rows[k].split('|')[-2].strip().split(':')[0] != word[x['outcome']]]
miss = [n for n in need if n not in T] + [f'строка ожидания {k}: исход не совпал с final_facts.json' for k in bad]
print(f'проверено фраз: {len(need)}; не найдено: {len(miss)}')
[print('  НЕТ:', x) for x in miss]
sys.exit(1 if miss else 0)
