#!/usr/bin/env python3
"""SCORE-02: сборка PREREG из prereg_template.md и файлов пилота (числа — командой, не перепечаткой): pilot_describe.json,
pilot_power.json, truth/truth_check.log, truth/pool_gaps.json, dry/check_expect.log, хеши промпта (prompts_score.hashes),
предсказания и ожидания (analyze_score02.PRED, COMP), правки по трём линзам — lenses/LENSES-1_fixes.md (если есть).
Импорт ничего не пишет: всё — в main().
  python3 assemble_prereg_score02.py --status "черновик" --out DRAFT-PREREG-SCORE-02.md"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
f = lambda x, d=3: f'{x:.{d}f}'.replace('.', ',').replace('-', '−')
NAME = dict(single='один вызов (single)', mean='среднее p (mean)', agree='согласие (agree)', single_c='один вызов, огрублённый (single_c)')
MNAME = dict(auc2='AUC второго рода', acc='точность', conf='уверенность', self_dec='самообман', brier='Брайер')
KIND = dict(family='семья', check='проверка', explore='разведка')
MODEL = dict(opus='Opus', haiku='Haiku')


def main():
    sys.path.insert(0, HERE)
    sys.path.insert(0, os.path.join(HERE, '..', '2026-10-28_SCORE-01'))
    import prompts_score as P
    from analyze_score02 import PRED, COMP, CONTROL
    a = sys.argv[1:]
    status = a[a.index('--status') + 1]
    out = a[a.index('--out') + 1]
    t = open(os.path.join(HERE, 'prereg_template.md'), encoding='utf-8').read()
    D = json.load(open(os.path.join(HERE, 'pilot_describe.json'), encoding='utf-8'))
    W = json.load(open(os.path.join(HERE, 'pilot_power.json'), encoding='utf-8'))
    G = json.load(open(os.path.join(HERE, 'truth', 'pool_gaps.json'), encoding='utf-8'))
    H = P.hashes()
    mdl = lambda st: MODEL[st.split('_')[1]]
    rep = {}
    rep['STATUS'] = status
    rep['TRUTH'] = open(os.path.join(HERE, 'truth', 'truth_check.log'), encoding='utf-8').read().strip()
    rep['HASHES'] = f"ROLE_H {H['ROLE_H'][:8]}…, LOG_H {H['LOG_H'][:8]}…, schema_H {H['schema_H'][:8]}… (`python3 ../2026-10-28_SCORE-01/prompts_score.py hash`; совпадают с PREREG SCORE-01 §3)"
    rep['CTX_PILOT'] = '; '.join(
        f"{st} — флаг {'да' if v['ctx']['flag'] else 'нет'}, против линии среднее {f(v['ctx']['abs_mean'], 1)}, наибольший |остаток| {f(v['ctx']['abs_max'], 1)}, "
        f"внутри задачи наибольший |остаток| {f(v['ctx']['max_abs_resid'], 1)}" for st, v in D.items()) + '.'
    rows = ['| Модель | Источник | Суждений | AUC второго рода | Точность | Уверенность | Самообман | Брайер | ИОИ = незнание + самообман⁺ |',
            '|---|---|---|---|---|---|---|---|---|']
    for st, v in D.items():
        for s in ('single', 'mean', 'agree'):
            m = v['measures'][s]
            rows.append(f"| {mdl(st)} | {NAME[s]} | {m['n']} | {f(m['auc2'])} | {f(m['acc'])} | {f(m['conf'])} | {f(m['self_dec'])} | {f(m['brier'])} | "
                        f"{f(m['ioi'])} = {f(m['ign'])} + {f(m['dec_pos'])} |")
        m = v['measures']['single_c']
        rows.append(f"| {mdl(st)} | {NAME['single_c']} | {m['n']} | {f(m['auc2'])} | — | — | — | — | — |")
    rep['PILOT_TABLE'] = '\n'.join(rows)
    lv = ['| Модель | Уровень согласия (доля вызовов на стороне большинства) | Суждений | Точность |', '|---|---|---|---|']
    for st, v in D.items():
        for k, (n, c) in sorted(v['acc_by_agree'].items(), key=lambda x: float(x[0])):
            lv.append(f"| {mdl(st)} | {f(float(k), 2)} | {n} | {f(c / n)} |")
    bins = ['| Модель | Уверенность одного вызова (корзина от) | Суждений | Точность |', '|---|---|---|---|']
    for st, v in D.items():
        for k, (n, c) in sorted(v['acc_by_conf_bin'].items(), key=lambda x: int(x[0])):
            bins.append(f"| {mdl(st)} | {f(0.5 + int(k) / 10, 1)} | {n} | {f(c / n)} |")
    cs = ['| Модель | Уровень согласия | Доля суждений согласия | Доля суждений одного вызова после огрубления |', '|---|---|---|---|']
    for st, v in D.items():
        for x in v['describe']['levels']:
            cs.append(f"| {mdl(st)} | {f(x['level'], 3)} | {f(x['agree_share'])} | {f(x['single_c_share'])} |")
    rep['PILOT_LEVELS'] = '\n'.join(lv) + '\n\n' + '\n'.join(bins) + '\n\n' + '\n'.join(cs)
    facts = []
    for st, v in D.items():
        u = v['unanimous']
        nu, na = sum(x[0] for x in u.values()), sum(x[1] for x in u.values())
        ex = v['describe']['excl']
        acc = {float(k): c / n for k, (n, c) in v['acc_by_agree'].items()}
        facts.append(f"- **{mdl(st)}:** единогласных суждений согласия — {nu} из {na} ({f(nu / na, 2)}), из них «5 из 5» — {u['5'][0]} из {u['5'][1]} суждений "
                     f"при пяти вызовах с p ≠ 0,5; точность единогласных {f(acc[1.0])}, суждений «4 из 5» (уровень 0,8) — {f(acc[0.8])}; исключено: "
                     f"p = 0,5 — {ex['half_calls']} из {ex['call_judgments']} вызовов-суждений, ничьих сторон — {ex['side_ties']} из {ex['cand_with_side']} кандидатов.")
    rep['PILOT_FACTS'] = '\n'.join(facts)
    o, h = D['pilot_opus'], D['pilot_haiku']
    rep['COARSE_OPUS'] = (f"AUC {f(o['measures']['single']['auc2'])} → {f(o['measures']['single_c']['auc2'])} (у Haiku {f(h['measures']['single']['auc2'])} → "
                          f"{f(h['measures']['single_c']['auc2'])})")
    rep['DECOMP'] = 'В пилоте: ' + '; '.join(
        f"{mdl(st)} — T = {f(v['describe']['decomp_x2']['T'])} при пороге {f(v['describe']['decomp_x2']['T_break'])} (приближение {f(v['describe']['decomp_x2']['approx'])}, "
        f"факт {f(v['describe']['decomp_x2']['x2'])})" for st, v in D.items()) + '.'
    rep['EXCL'] = 'в пилоте ' + '; '.join(
        f"{mdl(st)} — p = 0,5 у {v['describe']['excl']['half_calls']} из {v['describe']['excl']['call_judgments']} вызовов-суждений, ничьих сторон — "
        f"{v['describe']['excl']['side_ties']} из {v['describe']['excl']['cand_with_side']} кандидатов" for st, v in D.items()) + '.'
    rep['POOL_GAPS'] = (f"медиана отношения разрыва 4-го и 5-го кандидатов к размаху правды пула — {f(G['main_R4000']['median'])} (основная, R = 4000) и "
                        f"{f(G['rep_R4000']['median'])} (повтор) против {f(G['pilot_R1000']['median'])} в пилоте (правда пилота — по R = 1000; у основной и "
                        f"повтора по R = 1000 — {f(G['main_R1000']['median'])} и {f(G['rep_R1000']['median'])}; `truth/pool_gaps.log`).")
    def dry_summary(log, adir):
        """Итог сверки сухого прогона: число ожиданий и несовпадений; по каждому несовпадению — вид, ключ, ждал/вышло, для вердикта — интервал."""
        if not os.path.exists(log):
            return 'сверка — после сухого прогона.'
        lines = open(log, encoding='utf-8').read().strip().splitlines()
        miss, br = [], None
        for ln in lines:
            if ln.startswith('== ветка '):
                br = ln.split()[2].rstrip(':')
            elif ln.strip().startswith('НЕ СОВПАЛО: '):
                kind, rest = ln.strip()[len('НЕ СОВПАЛО: '):].split(' ', 1)
                k = rest.split(' — ')[0]
                got = rest.split('вышло «')[1].rstrip('»')
                txt = f"ветка {br}, {kind} {k}: «{got}»"
                if kind == 'verdicts':
                    R = json.load(open(os.path.join(adir, f'analysis_{br}.json'), encoding='utf-8'))
                    v, dx = R['verdicts'][k], R['describe'][k.split('|')[1]]['decomp_x2']
                    if 'mean' in v:
                        txt += f", {f(v['mean'])} [{f(v['ci95'][0])}; {f(v['ci95'][1])}]"
                    if k.startswith('X2'):
                        txt += f"; разложение этапа — T = {f(dx['T'])} при пороге {f(dx['T_break'])}, приближение {f(dx['approx'], 4)}, факт {f(dx['x2'], 4)}"
                miss.append(txt)
        return 'Итог сверки: ' + lines[-1].replace('итог: ', '') + '.' + (' Не совпало: ' + '; '.join(miss) + '.' if miss else '')
    C1 = json.load(open(os.path.join(HERE, '..', '2026-10-28_SCORE-01', 'calib_score01.json'), encoding='utf-8'))['expect_vs_power']
    sl = [k for k in C1 if not k.endswith('|all')]
    better = sum(1 for k in sl if C1[k]['brier_expect'] < C1[k]['brier_power'])
    rep['SC1_SLICES'] = (f"в {better} срезах из {len(sl)} (модель × выборка) Брайер ожиданий ниже Брайера мощности; у Opus в основной — "
                         f"{f(C1['main|opus']['brier_expect'], 4)} против {f(C1['main|opus']['brier_power'], 4)} (`../2026-10-28_SCORE-01/run/calib_score01.log`)")
    rep['X3_Z'] = f"{f(W['preds']['X3o']['z_pilot'], 2)} SD у Opus и {f(W['preds']['X3h']['z_pilot'], 2)} у Haiku (`pilot_power.json`, z_pilot)"
    rep['DRY_RESULT'] = dry_summary(os.path.join(HERE, 'dry', 'check_expect.log'), os.path.join(HERE, 'dry', 'run1'))
    rep['DRY2_RESULT'] = dry_summary(os.path.join(HERE, 'dry', 'check_expect2.log'), os.path.join(HERE, 'dry'))
    pl = []
    for c, parts in COMP.items():
        q = next(x for x in PRED if x['id'] == parts[0])
        note = ' Контроль для «установлено» у ' + ', '.join(k for k, v in CONTROL.items() if v == c) + '.' if c in CONTROL.values() else ''
        pl.append(f"- **{c}** — часть **{parts[0]}** {q['text']} ({MNAME[q['measure']]}: {q['a']} − {q['b']} {'> 0' if q['dir'] > 0 else '< 0'}).{note}")
    pl.append('- **Проверки (почти арифметика, §8; вердикт по букве, в калибровку, в реестр без веса):** ' + '; '.join(
        f"**{q['id']}** {q['text']} ({q['a']} − {q['b']} {'> 0' if q['dir'] > 0 else '< 0'})" for q in PRED if q['kind'] == 'check') + '.')
    pl.append('- **Разведка (вне семьи, в реестр — только гипотезой):** ' + '; '.join(
        f"**{q['id']}** {q['text']} ({q['a']} − {q['b']} {'> 0' if q['dir'] > 0 else '< 0'})" for q in PRED if q['kind'] == 'explore') + '.')
    rep['PRED_LIST'] = '\n'.join(pl)
    ex = ['| | Модель | Вид | Предсказание | Вероятность |', '|---|---|---|---|---|']
    for q in PRED:
        ex.append(f"| {q['id']} | {MODEL[q['model']]} | {KIND[q['kind']]} | {q['text']} | {f(q['expect'], 2)} |")
    rep['EXPECT_TABLE'] = '\n'.join(ex)
    pw = ['| | Модель | Вид | Мера | Контраст | Предсказание | Пилот: среднее [95 %] | SD бутстрепа | Основная (100): в точке / с неопред. | Повтор (59): в точке / с неопред. |',
          '|---|---|---|---|---|---|---|---|---|---|']
    for q in PRED:
        v = W['preds'][q['id']]
        pw.append(f"| {q['id']} | {MODEL[q['model']]} | {KIND[q['kind']]} | {MNAME[q['measure']]} | {q['a']} − {q['b']} | {'> 0' if q['dir'] > 0 else '< 0'} | "
                  f"{f(v['pilot_mean'])} [{f(v['ci95_pilot'][0])}; {f(v['ci95_pilot'][1])}] | {f(v['pilot_sd_boot'])} | "
                  f"{f(v['power']['main']['point'], 3)} / {f(v['power']['main']['unc'], 3)} | {f(v['power']['rep']['point'], 3)} / {f(v['power']['rep']['unc'], 3)} |")
    rep['POWER_TABLE'] = '\n'.join(pw)
    cp = ['| Сводный | Часть | «Подтверждено в обеих»: в точке / с неопред. | Вес, бит: подтверждено в обеих / другой исход по данным / технический |',
          '|---|---|---|---|']
    for c, v in W['comps'].items():
        cp.append(f"| {c} | {', '.join(v['parts'])} | {f(v['power_both_point'], 3)} / {f(v['power_both_unc'], 3)} | "
                  f"{f(v['bits_confirmed'], 2)} / {f(v['bits_not'], 2)} / {f(v['bits_technical'], 0)} |")
    rep['COMP_TABLE'] = '\n'.join(cp)
    nfam = sum(1 for q in PRED if q['family'])
    rep['N_FAMILY'] = str(nfam)
    rep['BONF'] = f(nfam * W['alpha'], 3)
    c_o = D['pilot_opus']['calls']['cost'] / D['pilot_opus']['calls']['n'] * 795
    c_h = D['pilot_haiku']['calls']['cost'] / D['pilot_haiku']['calls']['n'] * 795
    rep['COST_OPUS'], rep['COST_HAIKU'] = f(c_o, 0), f(c_h, 0)
    br = {}
    for nm, fn in (('пилота', 'run/pilot_jobs.jsonl'), ('основной выборки', 'jobs/main_jobs.jsonl'), ('повтора', 'jobs/rep_jobs.jsonl')):
        b = [len(json.loads(l)['prompt'].encode()) for l in open(os.path.join(HERE, fn), encoding='utf-8')]
        br[nm] = (min(b), max(b))
    L = json.load(open(os.path.join(HERE, '..', '2026-10-28_SCORE-01', 'run', 'pilot_ctx_line.json'), encoding='utf-8'))['line']['claude-opus-5-5']
    rep['BYTES'] = ('Байты промптов: ' + ', '.join(f'{k} {v[0]}–{v[1]}' for k, v in br.items())
                    + f" — внутри диапазона, по которому построена линия ({L['bytes_range'][0]}–{L['bytes_range'][1]}).")
    fx = os.path.join(HERE, 'lenses', 'LENSES-1_fixes.md')
    rep['LENSES'] = open(fx, encoding='utf-8').read().strip() if os.path.exists(fx) else 'проверка по трём линзам — после этого черновика.'
    fx2 = os.path.join(HERE, 'lenses', 'LENSES-2_fixes.md')
    rep['LENSES2'] = open(fx2, encoding='utf-8').read().strip() if os.path.exists(fx2) else 'узкая проверка правок — после этого черновика.'
    for k, v in rep.items():
        assert '{{' + k + '}}' in t, k
        t = t.replace('{{' + k + '}}', v)
    assert '{{' not in t, 'остались метки'
    open(os.path.join(HERE, out), 'w', encoding='utf-8').write(t)
    print('собрано:', out, len(t), 'знаков')


if __name__ == '__main__':
    main()
