# HIVE-01: геном улья, построение вызовов, приспособленность.
# Улей = законы (текст, препромпт каждой головы) + протокол: n голов (1–3), роли, пересмотр «Дельфи» (видят первые оценки других),
# итог — медиана или мозолистое тело. Потолок бюджета: не больше 4 вызовов на улей на пачку вопросов.
import json, math, random, statistics

ALPHA = 0.2  # интервал 80 %

SEED_LAWS = [
    'Сначала оценивай независимо, не подстраиваясь под чужие ответы.',
    'Всегда проверяй оценку вторым, другим способом и сравни результаты.',
    'Если два способа расходятся, расширь интервал так, чтобы он накрывал оба.',
    'Называй метод; каждая голова улья использует метод, отличный от методов других.',
    'Ищи самую сильную причину, почему оценка может быть неверной, и учитывай её в интервале.',
    'Для чисел, растущих экспоненциально, оценивай логарифм, а не само число.',
    'Не выдавай интервал уже, чем позволяет твоя реальная уверенность: промах хуже широкого интервала.',
    'Опирайся на известные асимптотики и точные значения для малых случаев, затем экстраполируй.',
    'Итог улья — медиана независимых оценок, а не мнение самого уверенного.',
    'Если задача похожа на хаотический процесс, честно давай широкий интервал вокруг типичного значения.',
    'Считай малые частные случаи точно, чтобы откалибровать общую формулу.',
    'Спорь с чужой оценкой только доводами о методе, а не авторитетом.',
]
ROLES = ['аналитик: оценивает через формулы и асимптотики', 'вычислитель: считает точно малые случаи и экстраполирует',
         'скептик: ищет, почему оценки других неверны, и расширяет интервал при сомнении', 'эмпирик: опирается на известные значения и аналогии']


def random_genome(rng, gid):
    n = rng.choice([1, 2, 3])
    delphi = n > 1 and rng.random() < 0.5
    agg = 'median' if n == 1 else rng.choice(['median', 'callosum'])
    while n * (1 + delphi) + (agg == 'callosum') > 4:
        delphi = False
    return dict(id=gid, laws=rng.sample(SEED_LAWS, rng.randint(2, 4)), n=n, roles=rng.sample(ROLES, n) if rng.random() < 0.6 else [None] * n,
                delphi=delphi, agg=agg, parent=None)


def cost(g):
    return g['n'] * (1 + g['delphi']) + (g['agg'] == 'callosum')


def score_q(t, est, lo, hi):
    """Интервальная оценка (Гнейтинг–Рафтери) в натуральных логарифмах для счётных величин. Меньше — лучше.
    незнание = |ln(est/t)|; самообман = штраф за промах интервала (2/α · расстояние до интервала); скромность = ширина."""
    L = lambda x: math.log(max(x, 1e-9))
    lt, llo, lhi, le = L(t), L(lo), L(hi), L(est)
    miss = (2 / ALPHA) * (max(0, llo - lt) + max(0, lt - lhi))
    return dict(ignorance=abs(le - lt), deception=miss, width=lhi - llo, interval_score=(lhi - llo) + miss, covered=llo <= lt <= lhi)


def aggregate_median(batches, ids):
    out = {}
    for i in ids:
        xs = [b[i] for b in batches if i in b]
        if not xs: continue
        g = lambda k: math.exp(statistics.median(math.log(max(x[k], 1e-9)) for x in xs))
        out[i] = dict(estimate=g('estimate'), lo=g('lo'), hi=g('hi'))
    return out


def fitness(final, qs):
    rows = []
    for q in qs:
        x = final.get(q['id'])
        if x is None:  # нет ответа — самый плохой разумный: оценка 1, интервал точка
            x = dict(estimate=1, lo=1, hi=1)
        rows.append(dict(id=q['id'], fam=q['fam'], **score_q(q['truth'], x['estimate'], x['lo'], x['hi'])))
    m = lambda k: sum(r[k] for r in rows) / len(rows)
    return dict(interval_score=m('interval_score'), ignorance=m('ignorance'), deception=m('deception'), width=m('width'),
                coverage=m('covered'), rows=rows)
