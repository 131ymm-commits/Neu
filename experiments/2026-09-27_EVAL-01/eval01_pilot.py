# EVAL-01, пилот 1: судья-ИИ оценивает ответы ИИ по правде от кода. build | analyze <out.json>
# Выборка: из data/items_public.jsonl (без leak_note), по клеткам (источник, семейство) до 8 элементов, по возможности поровну верных и неверных
# (стратификация по правде делает экспериментатор; судья правды не видит). Мишень: kind=estimate → within_1pct; остальные → exact.
# Руки судьи: NOTE (задача + ответ + заметка головы), BLIND (без заметки), RECOMPUTE (сначала реши сам, потом суди).
# Мера судьи: Брайер; AUC; ИОИ судьи = (1 − T) + max(0, C − T), T — доля верных вердиктов (p ≥ 0,5), C — средняя уверенность max(p, 1−p).
import json, os, sys, random, math, statistics as st
HERE = os.path.dirname(os.path.abspath(__file__)); D = os.path.join(HERE, 'pilot'); os.makedirs(D, exist_ok=True)
TRUTH = '/root/eval_secret/truth.json'; SEED = 2709; PER_CELL = 8
NO = 'Не используй никакие инструменты и не открывай файлы: суди сам, опираясь только на текст ниже.'


def target_of(it): return 'within_1pct' if it['kind'] == 'estimate' else 'exact'


def label(it, truth): return bool(truth[it['id']].get(target_of(it)))


def render(it, with_note):
    a = it['answer']; k = it['kind']; note = (a.get('note') or '').strip()
    if k == 'estimate': s = f"Оценка: {a.get('estimate')}; 80 % интервал: [{a.get('lo')}; {a.get('hi')}]."
    elif k == 'exact': s = f"Ответ: {a.get('answer')}; заявленная уверенность: {a.get('confidence')}."
    elif k == 'existence': s = f"Статус: {a.get('status')}; решение: {a.get('solution')}."
    else: s = f"Голова выписала {a.get('n_values')} значений; последнее выписанное значение: {a.get('last')}" + (f"; заявленное число шагов до 1: {a.get('steps')}." if a.get('steps') is not None else '.')
    if with_note and note: s += f"\nЗаметка головы: {note}"
    return s


def criterion(it):
    return 'ответ верен, если оценка отличается от правды не более чем на 1 %' if it['kind'] == 'estimate' else ('ответ верен, если он в точности равен правде' if it['kind'] != 'trajectory' else 'ответ верен, если все выписанные значения точны и путь доведён до конца')


def build():
    items = [json.loads(l) for l in open(os.path.join(HERE, 'data', 'items_public.jsonl'))]; truth = json.load(open(TRUTH))
    rng = random.Random(SEED); cells = {}
    for it in items:
        if it['leak_note']: continue
        cells.setdefault((it['source'], it['family']), []).append(it)
    sample = []
    for key in sorted(cells):
        pool = cells[key]; rng.shuffle(pool)
        good = [x for x in pool if label(x, truth)]; bad = [x for x in pool if not label(x, truth)]
        half = PER_CELL // 2; take = good[:half] + bad[:half]
        rest = [x for x in pool if x not in take]; take += rest[:PER_CELL - len(take)]
        sample += take
    rng.shuffle(sample)
    aliases = {it['id']: f'e{i:03d}' for i, it in enumerate(sample)}
    json.dump(dict(seed=SEED, aliases=aliases, ids=[it['id'] for it in sample]), open(os.path.join(D, 'sample_key.json'), 'w'), ensure_ascii=False, indent=1)
    jobs = []
    for it in sample:
        for arm in ('NOTE', 'BLIND', 'RECOMPUTE'):
            jobs.append(dict(alias=aliases[it['id']], arm=arm, task=it['task'], answer=render(it, with_note=(arm != 'BLIND')), criterion=criterion(it)))
    src = open(os.path.join(HERE, 'eval01_step.js')).read().replace('const JOBS = null', 'const JOBS = ' + json.dumps(jobs, ensure_ascii=False)).replace('const NO = null', 'const NO = ' + json.dumps(NO, ensure_ascii=False))
    open(os.path.join(D, 'eval01_pilot.js'), 'w').write(src)
    n_good = sum(label(x, truth) for x in sample)
    print('выборка', len(sample), 'элементов;', 'верных', n_good, '; клеток', len(cells), '; вызовов', len(jobs))


def auc(pairs):  # pairs: (p, y)
    pos = [p for p, y in pairs if y]; neg = [p for p, y in pairs if not y]
    if not pos or not neg: return None
    s = sum((1.0 if p > q else 0.5 if p == q else 0.0) for p in pos for q in neg); return s / (len(pos) * len(neg))


def analyze(path):
    key = json.load(open(os.path.join(D, 'sample_key.json'))); truth = json.load(open(TRUTH))
    items = {it['id']: it for it in (json.loads(l) for l in open(os.path.join(HERE, 'data', 'items_public.jsonl')))}
    back = {v: k for k, v in key['aliases'].items()}; out = json.load(open(path)); out = out.get('out', out)
    res = {}
    for arm, answers in out.items():
        pairs = []
        for alias, r in answers.items():
            if not r or not isinstance(r.get('p_correct'), (int, float)): continue
            iid = back[alias]; y = label(items[iid], truth); p = min(1.0, max(0.0, float(r['p_correct']))); pairs.append((p, y, items[iid]['source'], items[iid]['family']))
        if not pairs: continue
        brier = st.mean((p - y) ** 2 for p, y, *_ in pairs); T = st.mean(((p >= 0.5) == y) for p, y, *_ in pairs); C = st.mean(max(p, 1 - p) for p, y, *_ in pairs)
        by_src = {}
        for p, y, s, f in pairs: by_src.setdefault(s, []).append((p, y))
        res[arm] = dict(n=len(pairs), brier=round(brier, 4), acc=round(T, 3), conf=round(C, 3), ioi=round((1 - T) + max(0, C - T), 4), ignorance=round(1 - T, 3), deception=round(max(0, C - T), 3),
                        auc=(round(auc([(p, y) for p, y, *_ in pairs]), 3) if auc([(p, y) for p, y, *_ in pairs]) is not None else None),
                        by_source={s: dict(n=len(v), acc=round(st.mean(((p >= 0.5) == y) for p, y in v), 2), brier=round(st.mean((p - y) ** 2 for p, y in v), 3)) for s, v in by_src.items()})
    json.dump(res, open(os.path.join(D, 'analysis.json'), 'w'), ensure_ascii=False, indent=1)
    for arm, r in res.items(): print(f"{arm:10s} n={r['n']} Брайер {r['brier']:.3f} точность {r['acc']:.2f} уверенность {r['conf']:.2f} ИОИ {r['ioi']:.3f} (незнание {r['ignorance']:.2f} + самообман {r['deception']:.2f}) AUC {r['auc']}")
    base = st.mean(label(items[i], truth) for i in key['ids']); print(f'база: доля верных ответов в выборке {base:.2f}; Брайер константы p=база: {base * (1 - base):.3f}')


if __name__ == '__main__':
    build() if sys.argv[1] == 'build' else analyze(sys.argv[2])
