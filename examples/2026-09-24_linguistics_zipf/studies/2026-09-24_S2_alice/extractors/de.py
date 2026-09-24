"""de — S-06, Project Gutenberg #19778, Antonie Zimmermann (Leipzig 1869), файл de_00.txt.
ISO-8859-1 (latin-1), CRLF. Заголовок главы — две строки: «Erstes Kapitel» (у глав II–XII с точкой)
и через пустую строку название «Hinunter in den Kaninchenbau.».
До главы I: шапка PG, титул, вступительное стихотворение «O schöner, goldner Nachmittag»,
примечание автора о пародиях «[Der Verfasser wünscht …]» и оглавление «Inhalt.» — всё отбрасывается,
т. к. текст берётся только начиная с заголовка «Erstes Kapitel».
Удаляется: заголовки и названия глав, строки «[Illustration]», ряды звёздочек-разделителей,
курсив/разрядка _…_ и пометка антиквы =…= (разметка PG), шапка и лицензия PG."""
import re

ORD = ['Erstes', 'Zweites', 'Drittes', 'Viertes', 'Fünftes', 'Sechstes', 'Siebentes', 'Achtes',
       'Neuntes', 'Zehntes', 'Elftes', 'Zwölftes']
# Названия глав, как они стоят в заголовках (в оглавлении написание чуть иное)
TITLES = ['Hinunter in den Kaninchenbau.', 'Der Thränenpfuhl.', 'Caucus-Rennen und was daraus wird.',
          'Die Wohnung des Kaninchens.', 'Guter Rath von einer Raupe.', 'Ferkel und Pfeffer.',
          'Die tolle Theegesellschaft.', 'Das Croquetfeld der Königin.',
          'Die Geschichte der falschen Schildkröte.', 'Das Hummerballet.',
          'Wer hat die Kuchen gestohlen?', 'Alice ist die Klügste.']
# Заголовок: «<порядковое> Kapitel[.]», пустые строки, строка названия
HEAD = re.compile(r'^(%s) Kapitel\.?[ \t]*\n\s*\n(.+)\n' % '|'.join(ORD), re.M)


def _read(path):
    with open(path, 'rb') as f:
        t = f.read().decode('latin-1')
    return t.replace('\r\n', '\n').replace('\r', '\n')


def _book(t):
    """Текст между маркерами PG START OF / END OF."""
    a = re.search(r'^\*\*\* START OF TH(IS|E) PROJECT GUTENBERG EBOOK .*$', t, re.M)
    b = re.search(r'^\*\*\* END OF TH(IS|E) PROJECT GUTENBERG EBOOK .*$', t, re.M)
    assert a and b and a.end() < b.start(), 'de: не найдены маркеры PG'
    return t[a.end():b.start()]


def _clean(body):
    """Снимает разметку PG внутри главы; абзацы разделены одной пустой строкой."""
    out = []
    for line in body.split('\n'):
        s = line.strip()
        if s == '[Illustration]':
            continue
        if s and set(s) <= {'*', ' '}:  # ряд звёздочек — типографский разделитель, не текст
            continue
        out.append(line.rstrip())
    t = '\n'.join(out)
    t = re.sub(r'=([^=\n]+)=', r'\1', t)  # =Où est ma chatte?= — набор антиквой в оригинале
    t = t.replace('_', '')  # _sehr_ — курсив/разрядка PG; иных подчёркиваний в тексте нет
    assert '=' not in t and '[' not in t, 'de: осталась разметка'
    t = re.sub(r'\n{3,}', '\n\n', t)
    return t.strip('\n')


def chapters(paths):
    t = _book(_read(paths[0]))
    heads = list(HEAD.finditer(t))
    assert [h.group(1) for h in heads] == ORD, f'de: заголовки {[h.group(1) for h in heads]}'
    assert [h.group(2).strip() for h in heads] == TITLES, 'de: названия глав не совпали'
    # Конец последней главы — конец книги перед колофоном «End of Project Gutenberg's …»
    tail = t[heads[-1].end():]
    fin = re.search(r'^End of Project Gutenberg', tail, re.M)
    assert fin, 'de: нет колофона PG'
    ends = [h.start() for h in heads[1:]] + [heads[-1].end() + fin.start()]
    res = [_clean(t[h.end():e]) for h, e in zip(heads, ends)]
    # Сверка границ по содержанию: первая и последняя фразы книги (как в английском)
    assert res[0].startswith('Alice fing an sich zu langweilen; sie saß schon lange bei ihrer')
    assert res[-1].endswith('an ihr eigenes Kindesleben und\ndie glücklichen Sommertage.')
    return res
