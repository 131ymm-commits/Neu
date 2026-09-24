"""it — Project Gutenberg #28371, пер. Т. Пьетрокола-Россетти (1872), latin-1, CRLF.
Главы начинаются строкой «CAPITOLO I.» … «CAPITOLO XII.», за ней абзац-название («GIÙ NELLA CONIGLIERA.»).
Конец книги — строка «FINE.»; после неё выходные данные, «Nota del Trascrittore» и лицензия PG.
До главы I — титул, посвятительное стихотворение «In su' vespri giocondi…» и оглавление «INDICE»: всё отбрасывается.
Разметка PG: курсив _…_, строки «[Illustrazione]», разделители «*   *   *» — удаляются. Сносок нет.
Стихи внутри глав («Guglielmo, tu sei vecchio», колыбельная Герцогини, «Zuppa») остаются."""
import re

ROMAN = ['I', 'II', 'III', 'IV', 'V', 'VI', 'VII', 'VIII', 'IX', 'X', 'XI', 'XII']
HEAD = re.compile(r'^CAPITOLO ([IVXL]+)\.$')   # строка номера главы
END = 'FINE.'                                   # последняя строка книги


def clean(lines):
    """Тело главы из строк: убрать иллюстрации, разделители, курсив; сжать пустые строки."""
    out = []
    for ln in lines:
        s = ln.rstrip()
        if re.fullmatch(r'\s*\[Illustrazione\]', s):   # место картинки Тенниела
            continue
        if re.fullmatch(r'\s*(\*\s*)+', s):             # типографский разделитель «*  *  *  *  *»
            continue
        out.append(s.replace('_', ''))                  # курсив PG: _troppo_ -> troppo
    text = '\n'.join(out)
    text = re.sub(r'\n{3,}', '\n\n', text)              # не больше одной пустой строки подряд
    assert '[' not in text and ']' not in text, 'it: осталась скобочная вставка'
    return text.strip()


def chapters(paths):
    lines = open(paths[0], encoding='latin-1').read().replace('\r\n', '\n').split('\n')
    heads = [i for i, ln in enumerate(lines) if HEAD.match(ln.strip())]
    assert [HEAD.match(lines[i].strip()).group(1) for i in heads] == ROMAN, 'it: номера глав не I…XII'
    end = [i for i, ln in enumerate(lines) if ln.strip() == END]
    assert len(end) == 1 and end[0] > heads[-1], 'it: нет единственной строки FINE. после главы XII'
    bounds = heads + end
    out = []
    for k in range(12):
        i = bounds[k] + 1
        while not lines[i].strip():          # пустые строки между номером и названием
            i += 1
        while lines[i].strip():              # абзац-название главы (заголовок, не текст)
            i += 1
        out.append(clean(lines[i:bounds[k + 1]]))
    return out
