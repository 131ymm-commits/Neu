"""PLAY-01: промпты голов (решение совета 24). Все игровые знания — в одном общем блоке COMMON, одинаковом для A, B, C, H, D.
Роли C (и D) отличаются только областью внимания. Цель одинакова у всех и не раскрывает формулу счёта.
Справочник рецептов и технологий собирается из kb.json (прототипы Factorio 2.0.77, kb.py). Хеши — prompt_hashes()."""
import hashlib, json, os
HERE = os.path.dirname(os.path.abspath(__file__))
KB = json.load(open(os.path.join(HERE, 'kb.json')))

MAX_ACTIONS = 40
NOTE_MAX = 600
PRED_ITEMS = 8


def _num(x):
    return ('%g' % x).replace('.', ',')


def kb_tables():
    rec = []
    for r in KB['recipes']:
        if r['name'] == 'firearm-magazine': continue
        ing = ' + '.join(f'{n} {a}' for n, a in r['ingredients'])
        out = ' + '.join(f'{n} {a}' for n, a in r['products'])
        src = 'старт' if r['enabled_at_start'] else r.get('unlocked_by', '?')
        where = '' if r['category'] == 'crafting' else f' [{r["category"]}: печь]'
        rec.append(f'- {out} ← {ing}; {_num(r["seconds"])} с; {src}{where}')
    ent = []
    for e in KB['entities']:
        bits = [e['size']]
        if 'mining_speed' in e: bits.append(f'добыча {_num(e["mining_speed"])}/с, площадь ' + {'1.98x1.98': '2×2', '4.98x4.98': '5×5'}.get(e['mining_area'], e['mining_area']))
        if 'crafting_speed' in e: bits.append(f'скорость крафта {_num(e["crafting_speed"])}')
        if 'energy_kw' in e and e['item'] != 'offshore-pump': bits.append(f'{_num(round(e["energy_kw"], 1))} кВт ' + ('топлива' if e.get('fuel') == 'burner' else 'электричества' if e.get('fuel') == 'electric' else ''))
        if 'max_output_kw' in e: bits.append(f'выдаёт до {_num(e["max_output_kw"])} кВт')
        if 'belt_items_per_s' in e: bits.append(f'{_num(e["belt_items_per_s"])} предм./с')
        if 'supply_area' in e: bits.append(f'питает {e["supply_area"]}, провод до {_num(e["wire_reach"])}')
        if 'pump_per_s' in e: bits.append(f'{_num(e["pump_per_s"])} воды/с, без питания')
        ent.append(f'- {e["item"]}: ' + ', '.join(bits))
    tech = []
    for t in KB['techs']:
        pre = ', '.join(t['prerequisites']) or '—'
        how = f'триггер: {t["trigger"]}' if 'trigger' in t else f'{t["units"]} × ({", ".join(t["packs"])}) по {_num(t["unit_seconds"])} с'
        tech.append(f'- {t["name"]}: требует {pre}; {how}; открывает {", ".join(t["unlocks"])}')
    fuels = ', '.join(f'{n} {_num(v)} МДж' for n, v in KB['fuels'])
    return '\n'.join(rec), '\n'.join(ent), '\n'.join(tech), fuels


def common(R, rmin, wmin):
    """R — число раундов, rmin и wmin — длина раунда и окна W в игровых минутах (строки)."""
    rec, ent, tech, fuels = kb_tables()
    return f"""Ты управляешь персонажем в Factorio 2.0 (базовая игра). Мирный режим: врагов нет, других игроков нет.

## Цель
Партия — {R} раундов по {rmin} игровой минуты. В начале каждого раунда ты видишь наблюдение и отдаёшь список действий на раунд.
После последнего раунда персонаж замирает (очередь ручного крафта отменяется), и фабрика {wmin} игровых минут работает сама.
Оценивается чистая ценность того, что фабрика за это время произведёт сама: больше и ценнее — лучше (переработанные предметы ценнее сырья), израсходованное фабрикой вычитается.
Инвентарь персонажа и сделанное руками в оценку не входят: ручная работа нужна, чтобы построить фабрику, которая потом работает без тебя.

## Мир
- x растёт на восток, y — на юг. Клетка 1×1, центр клетки — координаты с ,5. Постройки 2×2 стоят центром на углу клеток (целые x, y), 1×1 и 3×3 — на центре клетки; игра округляет место — фактическое место видно в результате действия.
- 60 тиков = 1 игровая секунда.

## Персонаж
- Бег: 0,15 клетки за тик (9 клеток/с) по прямой к цели, 8 направлений. Поиска пути нет: деревья, камни, вода и постройки преграждают путь; если за 30 тиков персонаж сдвинулся меньше чем на 0,05 клетки или 60 тиков не приближается к цели, ходьба кончается отказом «застрял». Обходи препятствия промежуточными точками или сруби их (mine).
- Ручная добыча: руда, уголь, камень — 1 предмет за 2 с (120 тиков); клетка руды — не дальше 2,7 клетки от персонажа. Деревья и камни на земле тоже добываются (дают wood, stone).
- Поставить постройку — не дальше 10 клеток. Положить/забрать предметы, сменить рецепт, повернуть — если постройка в досягаемости (около 10 клеток).
- Ручной крафт идёт в фоне по очереди: можно ходить и копать, пока крафтится. Недостающие промежуточные предметы (шестерни и т. п.) крафтятся сами, если хватает сырья. Рецепты категории «печь» руками не делаются.
- Инвентарь — 80 ячеек. Старт: 8 iron-plate, 1 wood, 1 burner-mining-drill, 1 stone-furnace.

## Механика
- burner-mining-drill (2×2) копает 2×2 клетки под собой, 0,25 руды/с, ест 150 кВт топлива. Добытое кладёт перед собой: бур в (X, Y) с dir=north кладёт в точку (X−0,5; Y−1,3) — печь 2×2 в (X, Y−2) или сундук на этой клетке принимает руду; dir=east → (X+1,3; Y−0,5); south → (X+0,5; Y+1,3); west → (X−1,3; Y+0,5). Если перед буром пусто, руда падает на землю. Бур на угле может кормить углём то, во что кладёт (в том числе другой бур).
- Топливо: {fuels}. 1 coal держит burner-mining-drill ≈ 27 с, stone-furnace ≈ 44 с. Командой insert топливо уходит в топливный слот, руда — во вход печи.
- stone-furnace (2×2) сама выбирает рецепт по входу: iron-ore → iron-plate и copper-ore → copper-plate за 3,2 с, 5 iron-plate → steel-plate за 16 с (после steel-processing). Готовое копится в выходе (забирай take или манипулятором).
- burner-inserter и inserter (1×1): берут предмет с соседней клетки со стороны dir и кладут на клетку с противоположной стороны (dir=north: берёт с (x, y−1), кладёт на (x, y+1)). burner-inserter сам заправляется топливом, которое переносит.
- transport-belt: dir — направление движения ленты.
- Электричество: offshore-pump (1×1, без питания) ставится на берег, dir — сторона воды; выход — на соседней клетке с противоположной стороны. pipe соединяется с соседними трубами и входами сам. boiler (3×2) с dir=north в (X, Y): вход воды слева и справа — клетки (X−2; Y+0,5) и (X+2; Y+0,5), выход пара сверху — клетка (X; Y−1,5). steam-engine (3×5) с dir=north в (X; Y−3,5) стыкуется с паровым выходом такого котла напрямую. 1 котёл питает 2 паровых двигателя. small-electric-pole питает квадрат 5×5 вокруг себя, столбы соединяются проводом сами до 7,5 клетки.
- Исследования: lab (электричество) + научные пакеты внутри; действие research ставит технологию в очередь. Первые технологии открываются сами (триггеры): steam-power — когда выплавлено 50 iron-plate, electronics — 10 copper-plate, automation-science-pack — когда скрафчена 1 lab.
- assembling-machine делает рецепт, заданный действием recipe; входы кладут манипуляторы или ты.

## Постройки
{ent}

## Рецепты (выход ← входы; время; «старт» — открыт сразу, иначе — технология)
{rec}

## Технологии
{tech}

## Действия
Ответ — список действий (не больше {MAX_ACTIONS}), они исполняются по порядку тиками игры. walk, mine, wait идут во времени; остальные мгновенны (1 тик). Недопустимое действие отклоняется с причиной, мир не меняет, но занимает место в списке. Что не успело к концу раунда — пропадает.
- {{"a":"walk","x":X,"y":Y}} — идти к точке.
- {{"a":"mine","x":X,"y":Y,"n":N}} — копать N предметов руды/угля/камня на клетке; на дереве или камне — срубить; на своей постройке — разобрать (вернётся в инвентарь вместе с содержимым).
- {{"a":"craft","recipe":"R","n":N}} — поставить ручной крафт в очередь.
- {{"a":"place","item":"I","x":X,"y":Y,"dir":"north|east|south|west"}}
- {{"a":"insert","item":"I","n":N,"x":X,"y":Y}} — положить из инвентаря в постройку (без n — всё).
- {{"a":"take","item":"I","n":N,"x":X,"y":Y}} — забрать из постройки (без n — всё).
- {{"a":"recipe","x":X,"y":Y,"recipe":"R"}} — рецепт сборочной машины.
- {{"a":"research","tech":"T"}}
- {{"a":"rotate","x":X,"y":Y}}
- {{"a":"wait","ticks":N}}

## Наблюдение (JSON)
tick, minutes; character (место, дальности); inventory; crafting_queue; research (current, progress, researched, available — с триггером или ценой); entities — твои постройки по удалённости (status, recipe, input/output, fuel, contents, mining); resources_within_48 — руды рядом: ближайшая клетка, запас и patch_near — клетки этой руды в радиусе 10 от ближайшей полосами [y, x_от, x_до] (центры клеток); resources_far — ближайшая клетка руд дальше; obstacles_near — деревья и камни в радиусе 12; water_nearest; last_actions — результаты действий прошлого раунда (ok, detail).

## Ответ
Строго JSON по схеме: actions — список действий; predict — что будет в конце этого раунда: inventory — до {PRED_ITEMS} предметов инвентаря с числом, buildings — сколько у тебя будет построек; note — заметка себе на следующий раунд (до {NOTE_MAX} знаков: план, что не вышло, что проверить). Инструменты не используй: только ответ по схеме."""


def memory_block(mem):
    if not mem:
        return '## Память\nЭто первый раунд: памяти нет.'
    return ('## Память (с прошлого раунда)\nИтоговый список действий прошлого раунда:\n' + json.dumps(mem['actions'], ensure_ascii=False)
            + '\nЗаметка:\n' + (mem.get('note') or '—') + '\nРезультаты этих действий — в наблюдении, поле last_actions.')


def obs_block(obs, rnd, R):
    return f'## Раунд {rnd} из {R}. Наблюдение\n' + json.dumps(obs, ensure_ascii=False, separators=(',', ':'))


SOLO = 'Ты играешь один. Реши, что делать в этом раунде.'
B_STEPS = [
    'Ты играешь один и готовишь решение в четыре шага: черновик, две правки, итог. Сейчас шаг 1 — черновик: реши, что делать в этом раунде.',
    'Шаг {k} из 4 — правка. Ниже твоё решение с прошлого шага. Проверь его по наблюдению и справочнику: координаты и досягаемость, наличие предметов в нужный момент, время раунда, порядок действий. Исправь ошибки и улучши. Верни полное решение.',
    'Шаг 4 из 4 — итог. Ниже твоё решение с прошлого шага. Сдай окончательное решение на этот раунд и заметку на следующий.',
]
ROLES = [
    ('logistics', 'логистика: перемещение предметов — ленты, манипуляторы, сундуки, загрузка и выгрузка построек, маршрут персонажа'),
    ('mining_energy', 'добыча и энергия: буры, печи, топливо, электричество'),
    ('research', 'исследования и производство: технологии, лаборатории, научные пакеты, сборочные машины'),
]
ROLE_TXT = ('Ты — одна из трёх голов команды, которая управляет одним персонажем. Все головы видят одно и то же наблюдение. '
            'Твоя область внимания — {area}. Предложи полное решение на этот раунд с упором на свою область; '
            'мозолистое тело сведёт три предложения в одно.')
CALLOSUM_TXT = ('Ты — мозолистое тело команды из трёх голов (логистика; добыча и энергия; исследования и производство), которая управляет одним персонажем. '
                'Ниже их предложения на этот раунд. Сведи их в одно решение: персонаж один, действия идут по очереди; '
                'возьми лучшее, устрани противоречия и ошибки. Сдай окончательное решение и заметку на следующий раунд.')


def prompt(common_txt, head_txt, obs, mem, rnd, R, extra=None):
    parts = [common_txt, '## Твоя роль\n' + head_txt, memory_block(mem), obs_block(obs, rnd, R)]
    if extra: parts.append(extra)
    return '\n\n'.join(parts)


ACTION_S = {'type': 'object', 'properties': {
    'a': {'type': 'string', 'enum': ['walk', 'mine', 'craft', 'place', 'insert', 'take', 'recipe', 'research', 'rotate', 'wait']},
    'x': {'type': 'number'}, 'y': {'type': 'number'}, 'n': {'type': 'integer'}, 'item': {'type': 'string'}, 'recipe': {'type': 'string'},
    'tech': {'type': 'string'}, 'dir': {'type': 'string', 'enum': ['north', 'east', 'south', 'west']}, 'ticks': {'type': 'integer'}},
    'required': ['a']}
SCHEMA = {'type': 'object', 'properties': {
    'actions': {'type': 'array', 'items': ACTION_S, 'maxItems': MAX_ACTIONS},
    'predict': {'type': 'object', 'properties': {'inventory': {'type': 'object', 'additionalProperties': {'type': 'integer'}},
                                                'buildings': {'type': 'integer'}}, 'required': ['inventory', 'buildings']},
    'note': {'type': 'string', 'maxLength': NOTE_MAX}},
    'required': ['actions', 'predict', 'note']}


def frozen_texts():
    """Всё, что замораживается до пилота: шаблоны и схема (значения R, длины раунда и W подставляются)."""
    return {'common_template': common('{R}', '{rmin}', '{wmin}'),
            'solo': SOLO, 'b_steps': B_STEPS, 'roles': ROLES, 'role_txt': ROLE_TXT, 'callosum': CALLOSUM_TXT,
            'schema': SCHEMA, 'max_actions': MAX_ACTIONS, 'note_max': NOTE_MAX, 'memory': memory_block({'actions': [], 'note': 'N'})}


def prompt_hashes():
    t = frozen_texts()
    return {k: hashlib.sha256(json.dumps(v, ensure_ascii=False, sort_keys=True).encode()).hexdigest()[:16] for k, v in t.items()} | \
           {'all': hashlib.sha256(json.dumps(t, ensure_ascii=False, sort_keys=True).encode()).hexdigest()[:16]}


if __name__ == '__main__':
    c = common(10, '3', '5')
    print(c)
    print(len(c), 'знаков')
    print(prompt_hashes())
