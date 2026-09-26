# HIVE-01: итоговый анализ (решение совета, заседание 5, с поправкой заседания 6).
#   python3 hive_analyze.py test <test_out.json>  -> run/results.json
#   python3 hive_analyze.py laws                  -> run/LAWS_BLIND.md (для слепой разметки человеком) и run/laws_key.json
#   python3 hive_analyze.py power                 -> power.json
import json, math, os, sys, random
from hive_core import score_q
from hive_run import J, SECRET, final_of

HERE = os.path.dirname(os.path.abspath(__file__)); D = os.path.join(HERE, 'run')
ALPHA = 0.05


def binom_p(k, n):  # точное одностороннее P(X ≥ k), X ~ Bin(n, 1/2)
    return 1.0 if n == 0 else sum(math.comb(n, i) for i in range(k, n + 1)) / 2 ** n


def k_threshold(n, alpha=ALPHA):
    for k in range(n + 1):
        if binom_p(k, n) <= alpha: return k
    return None


def sign_test(d):
    """H1: медиана d < 0 (меньший балл лучше). Ничьи (d = 0) отбрасываются."""
    wins, losses = sum(x < 0 for x in d), sum(x > 0 for x in d)
    n = wins + losses
    return dict(wins=wins, losses=losses, n=n, p=binom_p(wins, n), k_needed=k_threshold(n), median_d=sorted(d)[len(d) // 2] if d else None)


def fixed_sequence(tests, order=('P1', 'P3', 'P2')):
    """Фиксированная последовательность P1 → P3 → P2, каждый шаг при α = 0,05; следующий — только при успехе предыдущего."""
    out, go = {}, True
    for k in order:
        passed = go and tests[k]['p'] <= ALPHA
        out[k] = dict(**tests[k], tested=go, passed=bool(passed))
        go = passed
    return out


def score_hive(o, qs):
    fin, _ = final_of(o, [q['id'] for q in qs])
    return {q['id']: score_q(q['truth'], fin[q['id']]['estimate'], fin[q['id']]['lo'], fin[q['id']]['hi']) for q in qs}


def test(path, exclude=()):
    full = J(f'{SECRET}/questions_full.json')
    conf, ctrl = full['test_conf'], full['test_ctrl']
    out = J(path)['out']
    S = {k: score_hive(o, conf + ctrl) for k, o in out.items()}
    IS = lambda k, i: S[k][i]['interval_score']
    ids = [q['id'] for q in conf]
    selfs = [k for k in ('A', 'B') if k not in exclude]
    d1 = [sum(IS(k, i) for k in selfs) / len(selfs) - (IS('F1', i) + IS('F2', i)) / 2 for i in ids] if selfs else []
    d2 = [(IS('F1', i) + IS('F2', i)) / 2 - IS('S', i) for i in ids]
    d3 = [sum(IS(k, i) for k in selfs) / len(selfs) - IS('Fp', i) for i in ids] if selfs else []
    tests = dict(P1=sign_test(d1), P2=sign_test(d2), P3=sign_test(d3))
    mean = lambda k, qs: {m: sum(S[k][q['id']][m] for q in qs) / len(qs) for m in ('interval_score', 'ignorance', 'deception', 'width', 'covered')}
    res = dict(decision=fixed_sequence(tests), d1=d1, d2=d2, d3=d3,
               explore=dict(Fp_vs_F=sign_test([IS('Fp', i) - (IS('F1', i) + IS('F2', i)) / 2 for i in ids]),
                            A_vs_F=sign_test([IS('A', i) - (IS('F1', i) + IS('F2', i)) / 2 for i in ids]),
                            B_vs_F=sign_test([IS('B', i) - (IS('F1', i) + IS('F2', i)) / 2 for i in ids]),
                            F1_vs_F2_noise=sign_test([IS('F1', i) - IS('F2', i) for i in ids])),
               by_hive_conf={k: mean(k, conf) for k in S}, by_hive_collatz={k: mean(k, ctrl) for k in S},
               by_family={k: {f: mean(k, [q for q in conf if q['fam'] == f]) for f in ('COL3', 'PART', 'TWIN', 'SUB5')} for k in S},
               per_question={i: {k: IS(k, i) for k in S} for i in ids + [q['id'] for q in ctrl]}, excluded=list(exclude))
    return res


def generations():
    """Ход по поколениям (разведочно): средний балл каждого улья на каждом поколении."""
    out = {}
    for g in range(10):
        p = f'{D}/res{g}.json'
        if not os.path.exists(p): break
        r = J(p); out[g] = {k: v['IS'] for k, v in r.items()}
    return out


def laws():
    """Все принятые законы и личные правила — в случайном порядке, без улья и поколения — для слепой разметки человеком."""
    items = []
    for g in range(10):
        p = f'{D}/raw_leg{g}.json'
        if not os.path.exists(p): break
        L = J(p)['out']
        for k, x in L.items():
            for a in x['adopted']:
                if a['kind'] != 'протокол': items.append(dict(text=a['text'], hive=k, g=g, kind='закон'))
            for r in x.get('revisions') or []:
                for t in ((r or {}).get('r') or {}).get('personal') or []: items.append(dict(text=t, hive=k, g=g, kind='личное правило'))
    random.Random(2609281).shuffle(items)
    J(f'{D}/laws_key.json', items)
    L = ['# HIVE-01: слепая разметка законов', '', 'Для каждого пункта поставьте П (процедурный: о том, как работать и взаимодействовать) или С (предметный: числа, формулы, порядки величин, названия типов задач или приём счёта для конкретного типа задач). Ответ — строка из П и С по порядку.', '']
    L += [f'{i + 1}. {x["text"]}' for i, x in enumerate(items)]
    open(f'{D}/LAWS_BLIND.md', 'w').write('\n'.join(L) + '\n')
    print(len(items), 'пунктов для разметки')


def power(nsim=20000, seed=2609282):
    """Мощность знакового теста на 20 вопросах при вероятности выигрыша q (d < 0) на вопрос."""
    rng = random.Random(seed)
    out = {}
    for q in (0.6, 0.7, 0.75, 0.8, 0.9):
        hits = 0
        for _ in range(nsim):
            w = sum(rng.random() < q for _ in range(20)); hits += binom_p(w, 20) <= ALPHA
        out[str(q)] = hits / nsim
    return dict(n=20, alpha=ALPHA, k_needed_n20=k_threshold(20), thresholds={n: k_threshold(n) for n in range(1, 21)}, power_by_win_prob=out, nsim=nsim, seed=seed)


if __name__ == '__main__':
    cmd = sys.argv[1]
    if cmd == 'test':
        res = test(sys.argv[2]); res['generations'] = generations()
        lab = f'{D}/laws_labels.json'
        if os.path.exists(lab):  # пересчёт без ульев с предметными законами (правило совета)
            key, labels = J(f'{D}/laws_key.json'), J(lab)['labels']
            bad = sorted({x['hive'] for x, l in zip(key, labels) if l == 'С'})
            res['sensitivity_no_subject'] = test(sys.argv[2], exclude=bad) if bad else 'предметных законов нет'
        J(f'{D}/results.json', res); print(json.dumps(res['decision'], ensure_ascii=False, indent=1))
    elif cmd == 'laws': laws()
    elif cmd == 'power':
        p = power(); J(os.path.join(HERE, 'power.json'), p); print(json.dumps(p, ensure_ascii=False, indent=1))
