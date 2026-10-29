#!/usr/bin/env python3
"""SCORE-02: сборка PREREG из prereg_template.md и файлов пилота (числа — командой, не перепечаткой): pilot_describe.json,
pilot_power.json, truth/truth_check.log, хеши промпта (prompts_score.hashes), предсказания и ожидания (analyze_score02.PRED, COMP),
правки по трём линзам — lenses/LENSES-1_fixes.md (если есть). Импорт ничего не пишет: всё — в main().
  python3 assemble_prereg_score02.py --status "черновик" --out DRAFT-PREREG-SCORE-02.md"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
f = lambda x, d=3: f'{x:.{d}f}'.replace('.', ',').replace('-', '−')
NAME = dict(single='один вызов (single)', mean='среднее p (mean)', agree='согласие (agree)')
MNAME = dict(auc2='AUC второго рода', acc='точность', conf='уверенность', self_dec='самообман', brier='Брайер')


def main():
    sys.path.insert(0, HERE)
    sys.path.insert(0, os.path.join(HERE, '..', '2026-10-28_SCORE-01'))
    import prompts_score as P
    from analyze_score02 import PRED, COMP
    a = sys.argv[1:]
    status = a[a.index('--status') + 1]
    out = a[a.index('--out') + 1]
    t = open(os.path.join(HERE, 'prereg_template.md'), encoding='utf-8').read()
    D = json.load(open(os.path.join(HERE, 'pilot_describe.json'), encoding='utf-8'))
    W = json.load(open(os.path.join(HERE, 'pilot_power.json'), encoding='utf-8'))
    H = P.hashes()
    rep = {}
    rep['STATUS'] = status
    rep['TRUTH'] = open(os.path.join(HERE, 'truth', 'truth_check.log'), encoding='utf-8').read().strip()
    rep['HASHES'] = f"ROLE_H {H['ROLE_H'][:8]}…, LOG_H {H['LOG_H'][:8]}…, schema_H {H['schema_H'][:8]}… (`python3 ../2026-10-28_SCORE-01/prompts_score.py hash`; совпадают с PREREG SCORE-01 §3)"
    rep['CTX_PILOT'] = '; '.join(
        f"{st} — флаг {'да' if v['ctx']['flag'] else 'нет'}, против линии среднее {f(v['ctx']['abs_mean'], 1)}, наибольший |остаток| {f(v['ctx']['abs_max'], 1)}, "
        f"внутри задачи наибольший |остаток| {f(v['ctx']['max_abs_resid'], 1)}" for st, v in D.items()) + '.'
    rows = ['| Модель | Источник | Суждений | AUC второго рода | Точность | Уверенность | Самообман | Брайер |', '|---|---|---|---|---|---|---|---|']
    for st, v in D.items():
        for s in ('single', 'mean', 'agree'):
            m = v['measures'][s]
            rows.append(f"| {st.split('_')[1]} | {NAME[s]} | {m['n']} | {f(m['auc2'])} | {f(m['acc'])} | {f(m['conf'])} | {f(m['self_dec'])} | {f(m['brier'])} |")
    rep['PILOT_TABLE'] = '\n'.join(rows)
    lv = ['| Модель | Уровень согласия (доля вызовов на стороне большинства) | Суждений | Точность |', '|---|---|---|---|']
    for st, v in D.items():
        for k, (n, c) in sorted(v['acc_by_agree'].items(), key=lambda x: float(x[0])):
            lv.append(f"| {st.split('_')[1]} | {f(float(k), 2)} | {n} | {f(c / n)} |")
    bins = ['| Модель | Уверенность одного вызова (корзина от) | Суждений | Точность |', '|---|---|---|---|']
    for st, v in D.items():
        for k, (n, c) in sorted(v['acc_by_conf_bin'].items(), key=lambda x: int(x[0])):
            bins.append(f"| {st.split('_')[1]} | {f(0.5 + int(k) / 10, 1)} | {n} | {f(c / n)} |")
    rep['PILOT_LEVELS'] = '\n'.join(lv) + '\n\n' + '\n'.join(bins)
    pl = []
    for c, parts in COMP.items():
        q = next(x for x in PRED if x['id'] == parts[0])
        pl.append(f"- **{c}** — части: **{parts[0]}** {q['text']} ({MNAME[q['measure']]}: {q['a']} − {q['b']} {'> 0' if q['dir'] > 0 else '< 0'}).")
    pl.append('- **Разведка (вне семьи, в реестр — только гипотезой):** ' + '; '.join(
        f"**{q['id']}** {q['text']} ({q['a']} − {q['b']} {'> 0' if q['dir'] > 0 else '< 0'})" for q in PRED if not q['family']) + '.')
    rep['PRED_LIST'] = '\n'.join(pl)
    ex = ['| | Модель | Предсказание | Вероятность |', '|---|---|---|---|']
    for q in PRED:
        ex.append(f"| {q['id']} | {q['model']} | {q['text']} | {f(q['expect'], 2)} |")
    rep['EXPECT_TABLE'] = '\n'.join(ex)
    pw = ['| | Модель | Мера | Контраст | Предсказание | Пилот: среднее [95 %] | SD бутстрепа | Основная (100): в точке / с неопред. | Повтор (59): в точке / с неопред. |',
          '|---|---|---|---|---|---|---|---|---|']
    for q in PRED:
        v = W['preds'][q['id']]
        pw.append(f"| {q['id']} | {q['model']} | {MNAME[q['measure']]} | {q['a']} − {q['b']} | {'> 0' if q['dir'] > 0 else '< 0'} | "
                  f"{f(v['pilot_mean'])} [{f(v['ci95_pilot'][0])}; {f(v['ci95_pilot'][1])}] | {f(v['pilot_sd_boot'])} | "
                  f"{f(v['power']['main']['point'], 3)} / {f(v['power']['main']['unc'], 3)} | {f(v['power']['rep']['point'], 3)} / {f(v['power']['rep']['unc'], 3)} |")
    rep['POWER_TABLE'] = '\n'.join(pw)
    cp = ['| Сводный | Части | Мощность «подтверждено в обеих» | Вес, бит: подтверждено в обеих / иначе |', '|---|---|---|---|']
    for c, v in W['comps'].items():
        cp.append(f"| {c} | {', '.join(v['parts'])} | {f(v['power_both'], 3)} | {f(v['bits_confirmed'], 2)} / {f(v['bits_not'], 2)} |")
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
    for k, v in rep.items():
        assert '{{' + k + '}}' in t, k
        t = t.replace('{{' + k + '}}', v)
    assert '{{' not in t, 'остались метки'
    open(os.path.join(HERE, out), 'w', encoding='utf-8').write(t)
    print('собрано:', out, len(t), 'знаков')


if __name__ == '__main__':
    main()
