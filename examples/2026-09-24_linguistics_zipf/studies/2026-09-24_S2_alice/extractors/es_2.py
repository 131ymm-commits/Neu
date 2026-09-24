"""es_2 — S-11, корпус iglika88 (…/Spanish/Alice in Wonderland/aw sp full 2.txt), файл es_2_00.txt.
Текст извлечён корпусом из PDF/EPUB; переводчик в корпусе не назван. UTF-8, CRLF.
Абзац — одна строка, абзацы через пустую строку; на границе страниц абзац бывает разорван на две строки
(«…que decía: «MERMELADA DE» / «NARANJA», …»), слова при этом целы. Колонтитулов, номеров страниц, сносок,
титула, оглавления и послесловия нет: файл начинается заголовком главы 1 и кончается последней фразой книги.
Заголовок главы: строка с арабским номером («1» … «12»), пустая строка, название — в одну строку,
у главы 3 в две («Una carrera en comité y un cuento» / «largo y con cola»); в названии главы 10
разорвана лигатура «ll» («La Cuadril a de la Langosta»; в тексте глав таких разрывов нет).
Перенос: единственный — в стихах главы 12 «vas a librar-» / «los por igual» -> «librarlos».
Дефис «peç-cedilla» (игра слов в главе 9) настоящий — не трогаем.
ПРОБЕЛ В ИСТОЧНИКЕ: в главе 3 НЕТ «мышиного хвоста» (стихов Fury/Mouse, «Fury said to a mouse…»): за строкой
«…que imaginó así:» в файле сразу идёт «—¡Tú no atiendes! —dijo severamente el Ratón…». В издании стихи, видимо,
были фигурным набором/картинкой и при извлечении пропали; в файле их нет нигде. Не восстанавливаем —
проверяем утверждением, чтобы пробел не остался незамеченным."""
import re

# Названия глав, как в файле (строки названия; у главы 3 — две)
TITLES = [['Descenso por la madriguera'], ['En un mar de lágrimas'],
          ['Una carrera en comité y un cuento', 'largo y con cola'], ['La habitación del Conejo Blanco'],
          ['El consejo de una Oruga'], ['Cerdo y pimienta'], ['Una merienda de locos'],
          ['El croquet de la Reina'], ['Historia de la Falsa Tortuga'], ['La Cuadril a de la Langosta'],
          ['¿Quién robó las tartas?'], ['La declaración de Alicia']]
NUM = re.compile(r'\d{1,2}')                   # строка номера главы


def _read(path):
    with open(path, encoding='utf-8') as f:
        return f.read().replace('\r\n', '\n').replace('\r', '\n')


def _clean(lines):
    """Тело главы: склеить перенос через строку, убрать лишние пробелы; абзацы через одну пустую строку."""
    t = '\n'.join(ln.strip() for ln in lines)
    t = re.sub(r'(\w)-\n\s*(?=[a-záéíóúñü])', r'\1', t)   # «librar-» / «los» -> «librarlos»
    t = re.sub(r'\n{3,}', '\n\n', t)
    assert not re.search(r'\d', t), 'es_2: цифры в тексте главы'
    return t.strip()


def chapters(paths):
    lines = _read(paths[0]).split('\n')
    heads = [i for i, ln in enumerate(lines) if NUM.fullmatch(ln.strip())]
    assert [int(lines[i]) for i in heads] == list(range(1, 13)), 'es_2: номера глав не 1…12'
    assert heads[0] == 0, 'es_2: перед главой 1 есть текст'
    bounds = heads + [len(lines)]
    out = []
    for k in range(12):
        i = bounds[k] + 1
        for title in TITLES[k]:              # строки названия, между ними пустые строки
            while not lines[i].strip():
                i += 1
            assert lines[i].strip() == title, f'es_2: название главы {k + 1}: {lines[i]!r}'
            i += 1
        out.append(_clean(lines[i:bounds[k + 1]]))
    # Пробел источника: стихов-«хвоста» в главе 3 нет (см. docstring) — фиксируем, что это именно так
    assert 'que imaginó así:\n\n—¡Tú no atiendes!' in out[2], 'es_2: изменилось место «мышиного хвоста»'
    # Сверка границ по содержанию: первая и последняя фразы книги (как в английском)
    assert out[0].startswith('Alicia empezaba a estar harta de seguir tanto rato sentada en la orilla')
    assert out[-1].endswith('al recordar su propia infancia y los felices días del verano.')
    return out
