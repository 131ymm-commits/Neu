# DIV-02: разделение труда. Цепочка голов (по 60 шагов) против одной головы и против самосогласования при равном бюджете.
#   build | analyze <out.json> | power
import json, sys, math, random, statistics as st
from hive_q import collatz_steps
from hive_core import score_q
SEC = '/root/div_secret/div02.json'; SEED = 92000
TIERS = [(10**12, 10**13), (10**15, 10**16), (10**18, 10**19)]; PER = 8
LINK_STEPS, MAX_LINKS, SC_MIN = 60, 12, 3
NO = 'Не используй никакие инструменты и не открывай файлы: считай сам, в уме, опираясь только на текст ниже.'


def build():
    rng = random.Random(SEED)
    qs = [dict(id=f'CZ{t}-{i}', tier=t, n=rng.randrange(*TIERS[t])) for t in range(3) for i in range(PER)]
    for q in qs: q['truth'] = collatz_steps(q['n'])
    json.dump(qs, open(SEC, 'w'))
    pub = [dict(id=q['id'], n=str(q['n'])) for q in qs]  # строкой: в JS числа > 2^53 теряют точность (найдено сухим прогоном)
    js = open('div02_step.js').read().replace('const QS = null', 'const QS = ' + json.dumps(pub)).replace('const NO = null', 'const NO = ' + json.dumps(NO, ensure_ascii=False))
    js = js.replace('LINK_STEPS = null', f'LINK_STEPS = {LINK_STEPS}').replace('MAX_LINKS = null', f'MAX_LINKS = {MAX_LINKS}').replace('SC_MIN = null', f'SC_MIN = {SC_MIN}')
    open('run/div02_run.js', 'w').write(js)
    print('чисел', len(qs), 'шаги правды', [q['truth'] for q in qs])


def sign(w, l):
    n = w + l
    return sum(math.comb(n, k) for k in range(w, n + 1)) / 2 ** n if n else 1.0


def analyze(path):
    qs = {q['id']: q for q in json.load(open(SEC))}; r = json.load(open(path))
    step = lambda v: v // 2 if v % 2 == 0 else 3 * v + 1
    rows = []
    for q in qs.values():
        c = r['chain'][q['id']]; s = r['solo'][q['id']] or {}; sc = [x for x in (r['sc'][q['id']] or []) if x]
        # цепочка: проверка звеньев кодом; если не дошла до 1 — остаток по модели 10,4·ln(v)
        v, links_ok, first_bad = q['n'], [], None
        for k, L in enumerate(c['links']):
            if not L or 'value' not in L: break
            for _ in range(L['steps_done']): v = step(v) if v != 1 else 1
            ok = str(v) == str(L['value']); links_ok.append(ok)
            if not ok and first_bad is None: first_bad = k + 1
            v = int(L['value']) if str(L['value']).isdigit() else v
        ch = c['steps'] if c['done'] else c['steps'] + round(10.4 * math.log(max(int(c['last']) if str(c.get('last', '1')).isdigit() else 2, 2)))
        sce = st.median(x['steps'] for x in sc) if sc else None
        rows.append(dict(id=q['id'], tier=q['tier'], truth=q['truth'], chain=ch, chain_done=c['done'], links=len(c['links']), first_bad_link=first_bad,
                         solo=s.get('steps'), sc=sce, sc_n=len(sc)))
    ex = lambda a, row: row[a] is not None and round(row[a]) == row['truth']
    def test(a, b):
        w = sum(ex(a, x) and not ex(b, x) for x in rows); l = sum(ex(b, x) and not ex(a, x) for x in rows)
        return dict(wins=w, losses=l, p=sign(w, l))
    res = dict(rows=rows, acc={a: sum(ex(a, x) for x in rows) for a in ('chain', 'solo', 'sc')},
               P1=test('chain', 'sc'), P2=test('chain', 'solo'),
               by_tier={t: {a: sum(ex(a, x) for x in rows if x['tier'] == t) for a in ('chain', 'solo', 'sc')} for t in range(3)})
    res['P1']['passed'] = res['P1']['p'] < 0.05; res['P2']['passed'] = res['P1']['passed'] and res['P2']['p'] < 0.05
    json.dump(res, open('run/results.json', 'w'), ensure_ascii=False, indent=1)
    print(json.dumps({k: res[k] for k in ('acc', 'P1', 'P2', 'by_tier')}, ensure_ascii=False))


def power(nsim=20000):
    rng = random.Random(1); out = {}
    for disc in (6, 8, 10, 12):          # число чисел, где руки расходятся (неничьи)
        for q in (0.8, 0.9, 1.0):
            hits = sum(sign(w := sum(rng.random() < q for _ in range(disc)), disc - w) < 0.05 for _ in range(nsim))
            out[f'неничьих {disc}, доля {q}'] = hits / nsim
    json.dump(out, open('power.json', 'w'), ensure_ascii=False, indent=1); print(out)


if __name__ == '__main__':
    c = sys.argv[1]
    build() if c == 'build' else analyze(sys.argv[2]) if c == 'analyze' else power()
