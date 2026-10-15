# SELECT-01: оценка самооценки (вопрос автора 15.10.2026: «как оценить оценку»). Пост-хок после итогового отчёта
# и совета 33, описательно, вердикт не меняет.
# Отказ (choice = −1) — простейшая самооценка оценщика: «не уверен». Если она что-то значит, отказы должны приходиться
# на задачи, трудные по правде от кода. Трудность меряется не самой D_N, а чужими голосами: средний регрет отдельных
# голосов C_N (та же роль без права отказа) и B_blind. Конечный судья здесь — симулятор (правда от кода).
#   python3 selfassess_posthoc.py > selfassess_posthoc.json
# Правда: /root/select_secret*/truth; без них — пересчитать из salts/ (REPORT_final.md, «Соли и воспроизведение»)
# и задать SEC_MAIN, SEC_REP.
import collections, json, os, statistics as st, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from analyze import auroc, boot_ci, spearman  # noqa: E402
SEC = {'main': os.environ.get('SEC_MAIN', '/root/select_secret'), 'rep': os.environ.get('SEC_REP', '/root/select_secret_rep')}
r3 = lambda x: round(x, 3)
out = {'note': 'пост-хок после итогового отчёта и совета 33; описательно, вердикт не меняет'}
for S in ('main', 'rep'):
    pt = json.load(open(f'{S}_an_wh.json'))['per_task']
    votes = collections.defaultdict(dict)
    for line in open(f'evals/{S}_eval.complete.jsonl', encoding='utf-8'):
        e = json.loads(line); votes[(e['task'], e['arm'])][int(e['i'])] = e.get('choice')
    rows = []
    for t in sorted(pt):
        tr = json.load(open(f'{SEC[S]}/truth/{t}.json')); orc, mean = max(tr), st.mean(tr)
        vr = lambda arm: [(orc - tr[c]) / (orc - mean) for c in votes[(t, arm)].values() if isinstance(c, int) and 0 <= c < len(tr)]
        rows.append(dict(ref=sum(c == -1 for c in votes[(t, 'D_N')].values()), cn=st.mean(vr('C_N')), bb=st.mean(vr('B_blind')),
                         dn=st.mean(vr('D_N')) if vr('D_N') else None))
    yes = [r for r in rows if r['ref'] > 0]; no = [r for r in rows if r['ref'] == 0]
    grp = lambda g, k: r3(st.mean(r[k] for r in g))
    paired = lambda g: [r['dn'] - r['cn'] for r in g if r['dn'] is not None]
    out[S] = dict(
        tasks=len(rows), tasks_with_D_N_refusal=len(yes),
        difficulty_C_N_votes=dict(refusal_tasks=grp(yes, 'cn'), other_tasks=grp(no, 'cn'),
                                  auroc_refusal_vs_difficulty=r3(auroc([r['cn'] for r in rows], [r['ref'] > 0 for r in rows]))),
        difficulty_B_blind_votes=dict(refusal_tasks=grp(yes, 'bb'), other_tasks=grp(no, 'bb'),
                                      auroc_refusal_vs_difficulty=r3(auroc([r['bb'] for r in rows], [r['ref'] > 0 for r in rows]))),
        spearman_refusals_vs_C_N_difficulty=r3(spearman([r['ref'] for r in rows], [r['cn'] for r in rows])),
        D_N_answers_minus_C_N_votes=dict(
            refusal_tasks=dict(mean=r3(st.mean(paired(yes))), ci95=[r3(v) for v in boot_ci(paired(yes))]),
            other_tasks=dict(mean=r3(st.mean(paired(no))), ci95=[r3(v) for v in boot_ci(paired(no))])))
print(json.dumps(out, ensure_ascii=False, indent=1))
