# DIV-01, пилот: расходятся ли ошибки у разных моделей Claude сильнее, чем у копий одной модели (урок PRED-01, docs/prior_art/README.md, пункт 2).
# Вопросы — семейства без точного счёта в уме (TWIN, COLLATZ), зёрна 90000+, в тест не войдут. Правда — /root/div_secret.
#   build | analyze <out.json>
import json, sys, math, itertools, statistics as st
from hive_q import make
from hive_core import score_q
SEC = '/root/div_secret/pilot.json'
HEADS = {'K1': None, 'K2': None, 'K3': None, 'SON': 'sonnet', 'HAI': 'haiku'}  # K — копии модели по умолчанию
ASK = 'Для каждого вопроса нужна оценка, точный подсчёт не требуется. Для каждого ID верни: estimate — лучшая оценка (число); lo и hi — границы интервала, в который правильный ответ попадает с вероятностью 80 %; note — метод одной фразой.'
NO = 'Не используй никакие инструменты и не открывай файлы: оценивай сам, опираясь только на текст ниже.'


def build():
    qs = [dict(make(f, 90000 + i), id=f'{f}-{90000 + i}') for f in ('TWIN', 'COLLATZ') for i in range(6)]
    json.dump(qs, open(SEC, 'w'), ensure_ascii=False)
    prompt = NO + '\n\nВопросы:\n' + '\n'.join(f"[{q['id']}] {q['text']}" for q in qs) + '\n\n' + ASK
    ids = [q['id'] for q in qs]
    js = f'''export const meta = {{ name: 'div-pilot', description: 'DIV-01 пилот: пять голов (три копии модели по умолчанию, sonnet, haiku) оценивают одни и те же вопросы', phases: [{{ title: 'Ответы' }}] }}
const PROMPT = {json.dumps(prompt, ensure_ascii=False)}
const IDS = {json.dumps(ids)}
const HEADS = {json.dumps(HEADS)}
const SCHEMA = {{ type: 'object', properties: {{ items: {{ type: 'array', items: {{ type: 'object', properties: {{ id: {{ type: 'string' }}, estimate: {{ type: 'number' }}, lo: {{ type: 'number' }}, hi: {{ type: 'number' }}, note: {{ type: 'string' }} }}, required: ['id', 'estimate', 'lo', 'hi', 'note'] }} }} }}, required: ['items'] }}
const ok = r => r && IDS.every(i => (r.items || []).some(x => x.id === i))
const out = {{}}, errors = {{}}
await parallel(Object.entries(HEADS).map(([nm, m]) => async () => {{
  for (let a = 0; a < 2; a++) {{
    try {{ const r = await agent(PROMPT, {{ label: `${{nm}}${{a ? '#retry' : ''}}`, phase: 'Ответы', schema: SCHEMA, ...(m ? {{ model: m }} : {{}}) }}); if (ok(r)) {{ out[nm] = r; return }} errors[nm] = 'формат' }} catch (e) {{ errors[nm] = String(e) }}
  }}
}}))
return {{ out, errors }}
'''
    open('pilot/div_pilot.js', 'w').write(js); print('вопросов', len(qs))


def analyze(path):
    qs = {q['id']: q for q in json.load(open(SEC))}; r = json.load(open(path)); out = r.get('out', r)
    err, IS = {}, {}
    for h, o in out.items():
        m = {x['id']: x for x in o['items']}
        err[h] = {i: math.log(max(m[i]['estimate'], 1e-9) / q['truth']) for i, q in qs.items()}
        IS[h] = st.mean(score_q(q['truth'], m[i]['estimate'], min(m[i]['lo'], m[i]['estimate']), max(m[i]['hi'], m[i]['estimate']))['interval_score'] for i, q in qs.items())
    print('ошибки/головы:', r.get('errors'))
    print('интервальный балл:', {h: round(v, 4) for h, v in IS.items()})
    for fam in ('TWIN', 'COLLATZ'):
        ids = [i for i in qs if i.startswith(fam)]
        print(fam)
        for a, b in itertools.combinations(err, 2):
            x, y = [err[a][i] for i in ids], [err[b][i] for i in ids]
            same = sum(abs(p - q) < 1e-9 for p, q in zip(x, y))
            c = st.correlation(x, y) if st.pstdev(x) > 0 and st.pstdev(y) > 0 else float('nan')
            print(f'  {a}-{b}: корреляция ошибок {c:+.2f}, одинаковых оценок {same}/{len(ids)}')


if __name__ == '__main__':
    build() if sys.argv[1] == 'build' else analyze(sys.argv[2])
