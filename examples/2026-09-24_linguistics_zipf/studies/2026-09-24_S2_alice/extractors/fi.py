"""fi — Project Gutenberg #46569, пер. Anni Swan (1906), latin-1, CRLF.
Главы озаглавлены только названием, без номера. Оглавление «SISÄLLYS:» в начале перечисляет 12 названий
(строки с отступом в 1 пробел); по нему ищем заголовки в теле: строка без отступа, равная названию
(в теле у главы 11 есть «?», которого нет в оглавлении, поэтому конечные знаки препинания не сравниваются).
Конец книги — строка «LOPPU»; после неё конец и лицензия PG. До главы 1 — титул и оглавление.
Удаляются курсив _…_ (бывает внутри слова: «kilpi_konnaksi_») и разделители «*   *   *».
Хвост Мыши (глава 3) набран фигурой с переносами слов по строкам («myö-/tä», «veruk-/keella»,
«lauta-/mies», «päi-/viltä»): такие переносы склеиваются. Других строк, кончающихся на «буква-», в тексте нет.
Стихи внутри глав остаются."""
import re

TOC = 'SISÄLLYS:'   # строка-заголовок оглавления
END = 'LOPPU'       # последняя строка книги


def key(s):
    """Название для сравнения: без пробелов по краям и конечных знаков препинания."""
    return s.strip().rstrip('?!.:')


def clean(lines):
    """Тело главы из строк: склеить переносы, убрать разделители и курсив; сжать пустые строки."""
    out = []
    for ln in lines:
        s = ln.rstrip()
        if re.fullmatch(r'\s*(\*\s*)+', s):             # типографский разделитель «*  *  *  *  *»
            continue
        out.append(s.replace('_', ''))                  # курсив PG: _lävitse_ -> lävitse
    text = '\n'.join(out)
    # перенос внутри слова в фигурном стихе: «myö-\n      tä» -> «myötä»
    text = re.sub(r'(?<=[^\W\d_])-\n[ \t]*(?=[^\W\d_])', '', text)
    text = re.sub(r'\n{3,}', '\n\n', text)              # не больше одной пустой строки подряд
    assert '[' not in text and ']' not in text, 'fi: осталась скобочная вставка'
    return text.strip()


def chapters(paths):
    lines = open(paths[0], encoding='latin-1').read().replace('\r\n', '\n').split('\n')
    # оглавление: первые 12 непустых строк после «SISÄLLYS:»
    t = lines.index(TOC)
    titles, i = [], t + 1
    while len(titles) < 12:
        if lines[i].strip():
            assert lines[i].startswith(' '), f'fi: строка оглавления без отступа: {lines[i]!r}'
            titles.append(key(lines[i]))
        i += 1
    # заголовки в теле: по порядку, каждый — строка без отступа, равная названию из оглавления
    heads = []
    for title in titles:
        while not (lines[i] and not lines[i][0].isspace() and key(lines[i]) == title):
            i += 1
        heads.append(i)
        i += 1
    end = [j for j, ln in enumerate(lines) if ln.strip() == END]
    assert len(end) == 1 and end[0] > heads[-1], 'fi: нет единственной строки LOPPU после главы 12'
    bounds = heads + end
    return [clean(lines[bounds[k] + 1:bounds[k + 1]]) for k in range(12)]
