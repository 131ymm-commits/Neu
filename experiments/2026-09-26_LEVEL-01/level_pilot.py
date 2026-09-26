# LEVEL-01 пилот: рождение группового уровня у голов Claude в кольце. build | analyze <out.json>
import json, sys, math, statistics as st, random
sys.path.insert(0, '../2026-09-26_HIVE-01')
from hive_q import make
SEC = '/root/level_secret/pilot.json'
HEADS = [('A1', None), ('S1', 'sonnet'), ('H1', 'haiku'), ('A2', None), ('S2', 'sonnet'), ('H2', 'haiku')]  # кольцо: соседи i−1, i+1
ROUNDS, SHOCK = 6, 6  # раунды 0..5 со связью, раунд 6 — удар по голове 0, раунд 7 — наблюдение
NO = 'Не используй никакие инструменты и не открывай файлы: оценивай сам, опираясь только на текст ниже.'


def build():
    qs = [dict(make('COLLATZ', 94000 + i), id=f'CZ-{94000 + i}') for i in range(2)] + [dict(make('TWIN', 94100), id='TW-94100')]
    json.dump(qs, open(SEC, 'w'), ensure_ascii=False)
    pub = [dict(id=q['id'], text=q['text']) for q in qs]
    js = open('level_step.js').read().replace('const QS = null', 'const QS = ' + json.dumps(pub, ensure_ascii=False)).replace('const HEADS = null', 'const HEADS = ' + json.dumps(HEADS))
    js = js.replace('const NO = null', 'const NO = ' + json.dumps(NO, ensure_ascii=False)).replace('const ROUNDS = null', f'const ROUNDS = {ROUNDS}')
    open('pilot/level_pilot.js', 'w').write(js); print('вопросов', len(qs))


def analyze(path):
    qs = {q['id']: q for q in json.load(open(SEC))}; r = json.load(open(path))
    L = lambda x: math.log(max(float(x), 1e-9))
    out = {}
    for arm in ('RING', 'ISO'):
        for qid, q in qs.items():
            tr = r[arm][qid]  # список раундов: [{голова: estimate}]
            rows = []
            for t, R in enumerate(tr):
                v = [L(R[h]) for h in R if R[h] is not None]
                rows.append(dict(t=t, med=st.median(v), D=st.pvariance(v), err=abs(st.median(v) - math.log(q['truth']))))
            dmed = [abs(rows[t]['med'] - rows[t - 1]['med']) for t in range(1, ROUNDS)]
            dind = [abs(L(tr[t][h]) - L(tr[t - 1][h])) for t in range(1, ROUNDS) for h in tr[t] if tr[t][h] and tr[t - 1][h]]
            init = {h: tr[0][h] for h in tr[0]}
            res = dict(D0=rows[0]['D'], DT=rows[ROUNDS - 1]['D'], collapse=rows[ROUNDS - 1]['D'] / rows[0]['D'] if rows[0]['D'] else None,
                       macro_step=st.mean(dmed), micro_step=st.mean(dind), final_med=math.exp(rows[ROUNDS - 1]['med']), truth=q['truth'],
                       err0=rows[0]['err'], errT=rows[ROUNDS - 1]['err'], equals_initial_of=[h for h, v in init.items() if v and abs(L(v) - rows[ROUNDS - 1]['med']) < 1e-3])
            if arm == 'RING' and len(tr) > ROUNDS:
                res['after_shock'] = [math.exp(x['med']) for x in rows[ROUNDS - 1:]]
            out[f'{arm}:{qid}'] = res
            print(arm, qid, {k: (round(v, 4) if isinstance(v, float) else v) for k, v in res.items()})
    json.dump(out, open('pilot/analysis.json', 'w'), ensure_ascii=False, indent=1)


if __name__ == '__main__':
    build() if sys.argv[1] == 'build' else analyze(sys.argv[2])
