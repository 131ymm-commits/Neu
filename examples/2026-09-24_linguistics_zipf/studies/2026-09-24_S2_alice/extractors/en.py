"""en — S-05, Project Gutenberg #11 (Millennium Fulcrum Edition 3.0), файл en_00.txt.
UTF-8 с BOM, CRLF. Заголовок главы — одна строка «CHAPTER I. Down the Rabbit-Hole».
Книга лежит между «*** START OF THIS PROJECT GUTENBERG EBOOK …» и «*** END OF …»;
после END есть второй маркер «*** START: FULL LICENSE ***» — ищем именно «START OF».
Глава XII кончается строкой «THE END».
Удаляется: шапка/лицензия PG, титул, заголовки глав, «THE END», ряды звёздочек-разделителей,
курсив _…_, редакторская помета «[later editions continued as follows … ]» в главе X
(сами стихи позднейших изданий — текст Кэрролла, они оставлены; см. KEEP_LATER_EDITION_VERSES).
Квадратные скобки вида «[‘which certainly…’» — это круглые скобки оригинала, они остаются."""
import re

ROMAN = ['I', 'II', 'III', 'IV', 'V', 'VI', 'VII', 'VIII', 'IX', 'X', 'XI', 'XII']
# Названия глав — сверка заголовков по содержанию, а не только по номеру
TITLES = ['Down the Rabbit-Hole', 'The Pool of Tears', 'A Caucus-Race and a Long Tale',
          'The Rabbit Sends in a Little Bill', 'Advice from a Caterpillar', 'Pig and Pepper',
          'A Mad Tea-Party', 'The Queen’s Croquet-Ground', 'The Mock Turtle’s Story',
          'The Lobster Quadrille', 'Who Stole the Tarts?', 'Alice’s Evidence']
# В главе X два куска стихов (4 и 6 строк) добавлены Кэрроллом в изданиях с 1886 г.;
# PG помечает их «[later editions continued as follows … ]». Помета удаляется всегда,
# стихи оставляются (True) или вырезаются целиком (False).
KEEP_LATER_EDITION_VERSES = True
LATER = re.compile(r'\n[ \t]*\[later editions continued as follows\n(.*?)\]\n', re.S)
HEAD = re.compile(r'^CHAPTER ([IVX]+)\. (.+)$', re.M)


def _read(path):
    with open(path, 'rb') as f:
        t = f.read().decode('utf-8-sig')  # снимает BOM
    return t.replace('\r\n', '\n').replace('\r', '\n')


def _book(t):
    """Текст между маркерами PG START OF / END OF."""
    a = re.search(r'^\*\*\* START OF TH(IS|E) PROJECT GUTENBERG EBOOK .*$', t, re.M)
    b = re.search(r'^\*\*\* END OF TH(IS|E) PROJECT GUTENBERG EBOOK .*$', t, re.M)
    assert a and b and a.end() < b.start(), 'en: не найдены маркеры PG'
    return t[a.end():b.start()]


def _clean(body):
    """Снимает разметку PG внутри главы; абзацы разделены одной пустой строкой."""
    body, n = LATER.subn(lambda m: '\n' + (m.group(1) if KEEP_LATER_EDITION_VERSES else '') + '\n', body)
    out = []
    for line in body.split('\n'):
        s = line.strip()
        if s and set(s) <= {'*', ' '}:  # ряд звёздочек — типографский разделитель, не текст
            continue
        out.append(line.rstrip())
    t = '\n'.join(out).replace('_', '')  # _I_ — курсив PG; иных подчёркиваний в тексте нет
    t = re.sub(r'\n{3,}', '\n\n', t)
    return t.strip('\n'), n


def chapters(paths):
    t = _book(_read(paths[0]))
    heads = list(HEAD.finditer(t))
    assert [h.group(1) for h in heads] == ROMAN, f'en: заголовки {[h.group(1) for h in heads]}'
    assert [h.group(2).strip() for h in heads] == TITLES, 'en: названия глав не совпали'
    # Конец последней главы — строка «THE END» (после неё только колофон PG)
    fin = re.search(r'^[ \t]*THE END[ \t]*$', t[heads[-1].end():], re.M)
    assert fin, 'en: нет строки THE END'
    ends = [h.start() for h in heads[1:]] + [heads[-1].end() + fin.start()]
    res, glosses = [], 0
    for h, e in zip(heads, ends):
        c, n = _clean(t[h.end():e])
        res.append(c)
        glosses += n
    assert glosses == 2, f'en: помет «later editions» {glosses}, ожидалось 2'
    # Сверка границ по содержанию: первая и последняя фразы книги
    assert res[0].startswith('Alice was beginning to get very tired of sitting by her sister')
    assert res[-1].endswith('remembering her own child-life, and the happy summer days.')
    return res
