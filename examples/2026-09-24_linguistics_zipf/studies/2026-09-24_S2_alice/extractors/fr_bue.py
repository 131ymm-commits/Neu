"""fr_bue — S-07, Project Gutenberg #55456, Henri Bué (Londres, Macmillan 1869), файл fr_bue_00.txt.
UTF-8 с BOM, CRLF. Заголовок главы — две строки: «CHAPITRE PREMIER.» / «CHAPITRE II.» … «CHAPITRE XII.»
с начала строки и через пустую строку название прописными («AU FOND DU TERRIER.»).
До главы I: шапка PG, заметка «Au lecteur» (от оцифровщиков), титул, благодарность автора
«[L'Auteur désire …]», вступительное стихотворение «Notre barque glisse sur l'onde» и оглавление
«TABLE.» (там строки «  CHAPITRE.  PAGE.» с отступом — под шаблон заголовка не попадают).
Всё это отбрасывается: текст берётся только начиная с «CHAPITRE PREMIER.».
После главы XII: «FIN.», выходные данные типографии и «Liste des modifications» — отбрасываются
(исправления из списка уже внесены в текст PG).
Удаляется также: заголовки и названия глав, строки «[Illustration]», ряды звёздочек, курсив _…_.
Первое слово главы набрано прописными («ALICE, assise …») — так в оригинале, не трогаем."""
import re

ORD = ['PREMIER', 'II', 'III', 'IV', 'V', 'VI', 'VII', 'VIII', 'IX', 'X', 'XI', 'XII']
# Названия глав — сверка заголовков по содержанию
TITLES = ['AU FOND DU TERRIER.', 'LA MARE AUX LARMES.', 'LA COURSE COCASSE.',
          "L'HABITATION DU LAPIN BLANC.", "CONSEILS D'UNE CHENILLE.", 'PORC ET POIVRE.',
          'UN THÉ DE FOUS.', 'LE CROQUET DE LA REINE.', 'HISTOIRE DE LA FAUSSE-TORTUE.',
          'LE QUADRILLE DE HOMARDS.', 'QUI A VOLÉ LES TARTES?', "DÉPOSITION D'ALICE."]
# Заголовок: «CHAPITRE <номер>.» с начала строки, пустые строки, строка названия
HEAD = re.compile(r'^CHAPITRE (PREMIER|[IVX]+)\.[ \t]*\n\s*\n(.+)\n', re.M)


def _read(path):
    with open(path, 'rb') as f:
        t = f.read().decode('utf-8-sig')  # снимает BOM
    return t.replace('\r\n', '\n').replace('\r', '\n')


def _book(t):
    """Текст между маркерами PG START OF / END OF."""
    a = re.search(r'^\*\*\* START OF TH(IS|E) PROJECT GUTENBERG EBOOK .*$', t, re.M)
    b = re.search(r'^\*\*\* END OF TH(IS|E) PROJECT GUTENBERG EBOOK .*$', t, re.M)
    assert a and b and a.end() < b.start(), 'fr_bue: не найдены маркеры PG'
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
    t = '\n'.join(out).replace('_', '')  # _Poison_ — курсив PG; иных подчёркиваний в тексте нет
    assert '[' not in t and ']' not in t, 'fr_bue: осталась разметка'
    t = re.sub(r'\n{3,}', '\n\n', t)
    return t.strip('\n')


def chapters(paths):
    t = _book(_read(paths[0]))
    heads = list(HEAD.finditer(t))
    assert [h.group(1) for h in heads] == ORD, f'fr_bue: заголовки {[h.group(1) for h in heads]}'
    assert [h.group(2).strip() for h in heads] == TITLES, 'fr_bue: названия глав не совпали'
    # Конец последней главы — строка «FIN.» (после неё типография и список исправлений)
    fin = re.search(r'^FIN\.[ \t]*$', t[heads[-1].end():], re.M)
    assert fin, 'fr_bue: нет строки FIN.'
    ends = [h.start() for h in heads[1:]] + [heads[-1].end() + fin.start()]
    res = [_clean(t[h.end():e]) for h, e in zip(heads, ends)]
    # Сверка границ по содержанию: первая и последняя фразы книги (как в английском)
    assert res[0].startswith('ALICE, assise auprès de sa sœur sur le gazon, commençait à s')
    assert res[-1].endswith('propre enfance et les heureux jours d\'été.')
    return res
