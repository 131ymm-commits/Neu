# Исключения суждений по источникам (пилот) и X3 при равном покрытии: ничья сторон у agree и p = 0,5 у single — как ½ верного.
import sys
sys.path.insert(0, '/tmp/claude-0/-home-claude/8c9bf095-e181-55d3-b75e-353e8e0f2d42/scratchpad/lenses_score02')
import pilot_lib as PL
for m in ('opus', 'haiku'):
    calls = PL.load_calls(f'{PL.SP}/pilot_{m}_out.jsonl')
    n_c = n_tie = n_half = n_calls = 0
    acc_s = acc_a = 0.0; tie_single_acc = []; agree_def = []; single_def = []
    for t in calls:
        ok = [p for p in calls[t].values() if p is not None]
        for i in range(8):
            y = i in PL.lab[t]; n_c += 1
            up = sum(p[i] > 0.5 for p in ok); dn = sum(p[i] < 0.5 for p in ok)
            for p in ok:
                n_calls += 1
                if p[i] == 0.5: n_half += 1; acc_s += 0.5
                else: acc_s += float((p[i] > 0.5) == y); single_def.append(float((p[i] > 0.5) == y))
            if up == dn:
                n_tie += 1; acc_a += 0.5
                tie_single_acc += [float((p[i] > 0.5) == y) for p in ok if p[i] != 0.5]
            else:
                c = float((up > dn) == y); acc_a += c; agree_def.append(c)
    a_def = sum(agree_def) / len(agree_def); s_def = sum(single_def) / len(single_def)
    print(f'{m}: кандидатов {n_c}; ничьих сторон (нет суждения agree) {n_tie}; вызовов-суждений {n_calls}, из них p = 0,5: {n_half}')
    print(f'   X3 по определению PREREG: agree {a_def:.4f} − single {s_def:.4f} = {a_def - s_def:+.4f}')
    print(f'   X3 при равном покрытии (ничья и p = 0,5 — ½): agree {acc_a / n_c:.4f} − single {acc_s / n_calls:.4f} = {acc_a / n_c - acc_s / n_calls:+.4f}')
    if tie_single_acc:
        print(f'   точность одиночных суждений на кандидатах с ничьей сторон: {sum(tie_single_acc) / len(tie_single_acc):.3f} ({len(tie_single_acc)} суждений)')
