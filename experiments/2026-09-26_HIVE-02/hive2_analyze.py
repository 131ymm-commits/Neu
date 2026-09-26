# HIVE-02: итоговая проверка и ход эволюции.
#   python3 hive2_analyze.py test <out.json>  -> run/results.json
import json, math, os, sys
from hive2_run import J, D, SECRET, final_of
from hive_core import score_q


def binom_p(k, n): return 1.0 if n == 0 else sum(math.comb(n, i) for i in range(k, n + 1)) / 2 ** n


def sign_test(d):
    w, l = sum(x < 0 for x in d), sum(x > 0 for x in d)
    return dict(wins=w, losses=l, n=w + l, p=binom_p(w, w + l))


def test(path):
    qs = J(f'{SECRET}/questions_full.json')['test']; out = J(path); J(f'{D}/raw_test.json', out)
    S, miss = {}, {}
    for k, o in out['out'].items():
        fin, _, m = final_of(o, [q['id'] for q in qs]); miss[k] = m
        S[k] = {q['id']: score_q(q['truth'], fin[q['id']]['estimate'], fin[q['id']]['lo'], fin[q['id']]['hi'])['interval_score'] for q in qs}
    ids = [q['id'] for q in qs]
    d = lambda a, b: [0.0 if (i in miss[a] or i in miss[b]) else S[a][i] - S[b][i] for i in ids]
    tests = {f'CHAMP_vs_{b}': sign_test(d('CHAMP', b)) for b in S if b != 'CHAMP'}
    if 'HIVE01_A' in S and 'HIVE01_B' in S:
        tests['CHAMP_vs_HIVE01_mean'] = sign_test([S['CHAMP'][i] - (S['HIVE01_A'][i] + S['HIVE01_B'][i]) / 2 for i in ids])
    gens = [dict(g=h['g'], mean=sum(h['IS'].values()) / len(h['IS']), best=min(h['IS'].values()), rank=h['rank']) for h in J(f'{D}/state.json')['history']]
    res = dict(tests=tests, mean_IS={k: sum(v.values()) / len(v) for k, v in S.items()}, per_question=S, generations=gens, plan=J(f'{D}/test_plan.json'))
    J(f'{D}/results.json', res); print(json.dumps(dict(tests=tests, mean_IS=res['mean_IS']), ensure_ascii=False, indent=1))


if __name__ == '__main__':
    test(sys.argv[2])
