# PRECOND-01: «сто предусловий» оценщика как факторный план (обдумывание и решение автора — docs/2026-10-21_precond_100.md).
# Восемь ингредиентов, предусловие = набор включённых. Тексты собираются программой из фиксированных кусков — руками ничего
# не подгоняется. Задача, правила и кандидаты — как в SELECT-01 (prompts.cands_text, sim.RULES).
#   python3 prompts_precond.py check   — сбалансированность и ортогональность планов, длины, хеши кусков
import hashlib, itertools, json, os, sys
SEL = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '2026-10-07_SELECT-01'); sys.path.insert(0, SEL)
import prompts as P  # noqa: E402

F = ['REFUSE', 'UNSURE', 'ROLE', 'PROCEDURE', 'CHECK', 'CONF', 'CLAIMS', 'PADDING']      # F1 … F8
ROLE_LINES = P.ROLE.split('\n')
TXT = dict(
    HEAD_BASE='Ниже — задача планирования и {k} планов-кандидатов. Выбери план с наибольшим фактическим итогом.',
    ROLE=ROLE_LINES[0],                                    # роль — первая строка ROLE из SELECT-01 байт в байт
    PROCEDURE='\n'.join(ROLE_LINES[1:5]),                  # «Порядок работы» 1)–3) из ROLE SELECT-01 байт в байт
    UNSURE='Ошибиться здесь легко: кандидаты бывают близки по итогу, а разумная уверенность достижима не всегда.',
    CHECK='Твой выбор сверят с фактическим итогом, который посчитает симулятор.',
    PADDING='Кандидаты пронумерованы с нуля в том порядке, в каком перечислены ниже; порядок перечисления ничего не значит. Описание задачи и всех кандидатов полное.',
    NOTOOLS='Считай в уме; инструментов нет, код не запускай, файлы не открывай.',
    ANSWER='Верни choice — номер кандидата с наибольшим ожидаемым итогом.',
    REFUSE='Если ты не можешь отличить лучшего кандидата от остальных с разумной уверенностью — откажись: верни choice = -1 («не знаю»). '
           'Отказ не наказывается сам по себе.\nИначе верни choice — номер кандидата с наибольшим ожидаемым итогом.',
    CONF='Верни также p_best — твою вероятность от 0 до 1, что выбранный кандидат действительно лучший по фактическому итогу.',
)
assert TXT['REFUSE'] == P.ROLE_REFUSE.split('\n')[6] + '\n' + P.ROLE_REFUSE.split('\n')[7], 'добавка отказа не совпала с SELECT-01'
CONF_SCHEMA = {"type": "object", "properties": {"choice": {"type": "integer"}, "p_best": {"type": "number", "minimum": 0, "maximum": 1}},
               "required": ["choice", "p_best"]}

def compose(on, rules, pool):
    """on — множество включённых ингредиентов. Порядок кусков фиксирован."""
    head = [TXT['ROLE'] if 'ROLE' in on else TXT['HEAD_BASE'].format(k=len(pool))]
    body = [TXT[x] for x in ('PROCEDURE', 'UNSURE', 'CHECK', 'PADDING') if x in on] + [TXT['NOTOOLS']]
    tail = [TXT['REFUSE'] if 'REFUSE' in on else TXT['ANSWER']] + ([TXT['CONF']] if 'CONF' in on else [])
    text = '\n'.join(head + body + tail) + f'\n\n{rules}\n\n' + P.cands_text(pool, 'CLAIMS' in on)
    return text, (CONF_SCHEMA if 'CONF' in on else P.EVAL_SCHEMA)

def design(n):
    """Дробные планы 2^(8−p) в кодировке ±1. n = 16: разрешение IV (E=BCD, F=ACD, G=ABC, H=ABD);
    n = 64: разрешение V (G=ABCD, H=ABEF). Строка — список включённых ингредиентов."""
    base = 4 if n == 16 else 6
    rows = []
    for bits in itertools.product((-1, 1), repeat=base):
        x = dict(zip('ABCDEF'[:base], bits))
        if n == 16: x.update(E=x['B'] * x['C'] * x['D'], F=x['A'] * x['C'] * x['D'], G=x['A'] * x['B'] * x['C'], H=x['A'] * x['B'] * x['D'])
        else: x.update(G=x['A'] * x['B'] * x['C'] * x['D'], H=x['A'] * x['B'] * x['E'] * x['F'])
        rows.append([F[i] for i, k in enumerate('ABCDEFGH') if x[k] == 1])
    return rows

if __name__ == '__main__' and sys.argv[1:] == ['check']:
    for n in (16, 64):
        D = design(n); col = {f: [1 if f in r else -1 for r in D] for f in F}
        assert len({tuple(r) for r in D}) == n, 'повтор строк'
        assert all(sum(v) == 0 for v in col.values()), 'ингредиент не сбалансирован'
        assert all(sum(a * b for a, b in zip(col[f], col[g])) == 0 for f, g in itertools.combinations(F, 2)), 'столбцы не ортогональны'
        print(f'план {n}: строк {n}, каждый ингредиент включён в {n // 2}, столбцы попарно ортогональны')
    print('длины кусков:', {k: len(v) for k, v in TXT.items()})
    print(json.dumps({k: hashlib.sha256(v.encode()).hexdigest()[:12] for k, v in TXT.items()}, ensure_ascii=False))
