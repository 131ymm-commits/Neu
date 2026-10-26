# THINK-01: производные числа итогового отчёта (обе выборки) — для ledger.py audit и check_final_think.py.
# Только арифметика над main_an.json, rep_an.json, *_facts.json и журналами повтора.
#   python3 final_facts_think.py  →  final_facts.json
import collections, glob, json
m, r = json.load(open('main_an.json')), json.load(open('rep_an.json'))
counts = {k: [m['primary'][k]['counts'], r['primary'][k]['counts']] for k in m['primary']}
pa = lambda a, arm: a['secondary']['S2_mechanism']['per_arm'][arm]['mean_out_all']
s4 = lambda a: a['secondary']['S4_refusal_informativeness']
expect = dict(                                    # PREREG §12: ключи и правила — как записаны до прогона
    P1=m['primary']['H_1 − B_blind']['counts'], P2=m['primary']['H_1 − D_N']['counts'],
    P3=all(counts['H_1 − B_blind']), P4=pa(m, 'D_N') > pa(m, 'U_N') and pa(r, 'D_N') > pa(r, 'U_N'),
    P5=abs(m['secondary']['S2_mechanism']['equal_length_model']['D_N']['coef']) < 0.1,
    P6=m['secondary']['S3_self_assessment']['mean_p_best'] > m['secondary']['S3_self_assessment']['accuracy_lenient'],
    P7=bool(s4(m)['measured'] and 0.4 <= s4(m)['auroc_refusal_vs_C_N_difficulty'] <= 0.6))
# чистота вызовов повтора: итоги и попытки по журналам задач, версии и модели
fin, att, na, models, cli, binsha, eff = collections.Counter(), collections.Counter(), 0, set(), set(), set(), collections.defaultdict(set)
for p in glob.glob('run/rep_eval_*_journal/WH_*.jsonl'):
    for line in open(p, encoding='utf-8'):
        x = json.loads(line); att[x['arm']] += 1; na += x['outcome'] == 'нет ответа'
        if x.get('final'): fin[x['final']] += 1
        models.update(x.get('model_usage_keys') or []); cli.add(x.get('cli_init_version')); binsha.add(x.get('binary_sha256')); eff[x['arm']].add(x.get('effort'))
# сегменты драйвера повтора по run_log: старт → пауза или готово
seg = {}
for b in ('exec', 'eval_medium', 'eval_high'):
    ev = [json.loads(l) for l in open(f'run/rep_{b}_journal/run_log.jsonl', encoding='utf-8')]
    s, out = None, []
    for e in ev:
        if e['event'] == 'старт':
            if s: out.append([s[:16], '—', 'оборван'])      # сегмент без записи о конце: процесс остановлен по PID
            s = e['at']
        elif e['event'] in ('пауза', 'готово') and s: out.append([s[:16], e['at'][:16], e['event']]); s = None
    seg[b] = out
facts = dict(established={k: v for k, v in counts.items()}, expectations=expect,
             rep_finals=dict(fin), rep_attempts=dict(att), rep_no_answer_attempts=na, rep_models=sorted(models), rep_cli=sorted(c for c in cli if c),
             rep_binary_sha256=sorted(b[:16] for b in binsha if b), rep_effort={k: sorted(v) for k, v in eff.items()}, rep_segments=seg)
json.dump(facts, open('final_facts.json', 'w'), ensure_ascii=False, indent=1); print(json.dumps(facts, ensure_ascii=False)[:3000])
