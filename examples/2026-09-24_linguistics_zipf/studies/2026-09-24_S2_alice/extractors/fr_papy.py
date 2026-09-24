"""fr_papy — S-08, корпус iglika88 (…/French/Alice in Wonderland/aw fr full 1.txt), файл fr_papy_00.txt.
По метке корпуса — пер. Jacques Papy (2001); текст извлечён корпусом из PDF (вёрстка ebooksgratuits:
колонтитул «Alice au pays des merveilles – <глава>», номера страниц «– 5 –» … «– 178 –»). UTF-8, CRLF.
Абзац — одна строка (переносов внутри строк нет), абзацы через пустую строку.

Устройство файла и что с ним делается:
* ПЕРВЫЙ АБЗАЦ ГЛАВЫ I В ФАЙЛЕ ОТСУТСТВУЕТ: файл начинается с названия главы, слитого со вторым абзацем
  («Descente dans le terrier du lapin El e se demandait …»); абзаца «Alice commençait à se sentir très lasse …»
  (сестра, книжка без картинок и разговоров) нет нигде в файле. Не восстанавливаем — глава I начинается
  со слов «Elle se demandait».
* Номер страницы — отдельная строка «– N –», сразу за ней колонтитул «Alice au pays des merveil(l)es – <название>»,
  к которому в той же строке приклеено продолжение текста следующей страницы. Номер и колонтитул снимаются;
  если продолжение начинается со строчной буквы, это тот же абзац — склеиваем через пробел.
  Единственный перенос через страницу — «soixante-» / «quinze»: дефис настоящий, оставляем «soixante-quinze».
* Заголовок главы II–XII: «CHAPITRE N» (приклеен к колонтитулу или отдельной строкой), пустая строка, название.
  Главы I в файле без «CHAPITRE»: только название в начале файла.
* Сноски переводчика (15 штук) стоят внизу страницы перед строкой номера, текст сноски «N …» бывает приклеен
  к последней строке текста («… sous la 8 Voir l’expression …»). Тело сноски снимается от «N <начало>» до строки
  номера страницы; маркеры в тексте («Antipattes1», «chatte ? 2 »», «14 – Je …») — отдельно.
* Разрыв лигатур при извлечении из PDF: «ll» (иногда «ff») дано как «l »/«f »: «El e» = «Elle», «feuil es» =
  «feuilles», «s’en al a» = «s’en alla», «af ection» = «affection», «Bil» = «Bill». Чиним только однозначные
  случаи — см. _ligatures(); список правил проверен по всем парам «…l|f <слово>» в файле.
  В трёх местах главы XII вторая «l» потеряна без пробела: «La filette regarda …», «Ele vit que …»,
  в стихах «vous aviez été à ele,» — чиним словарём LOST_LL (проверено поиском форм с одной «l»,
  у которых форма с «ll» есть в тексте; «Sale serpent», «viles», «Filez» — настоящие слова).
После главы XII ничего нет: файл кончается последней фразой книги."""
import re

# Названия глав в колонтитулах (точное написание файла)
RUNNING = ['Descente dans le terrier du lapin', 'La mare de larmes',
           'Une course au “Caucus” et une longue histoire', 'Le lapin fait intervenir le petit Bill',
           'Les conseils de la Chenille', 'Porc et poivre', 'Un thé chez les fous',
           'Le terrain de croquet de la Reine', 'Histoire de la Simili-Tortue', 'La quadrille des homards',
           'Qui a dérobé les tartes ?', 'La déposition d’Alice']
# Названия глав II–XII под «CHAPITRE N» (как в файле: с маркером сноски 3 и разрывами «ll»)
TITLES = ['La mare de larmes', 'Une course au « Caucus »3 et une longue histoire',
          'Le lapin fait intervenir le petit Bil', 'Les conseils de la Chenil e', 'Porc et poivre',
          'Un thé chez les fous', 'Le terrain de croquet de la Reine', 'Histoire de la Simili-Tortue',
          'Le quadril e des homards', 'Qui a dérobé les tartes ?', 'La déposition d’Alice']
ROMAN = ['II', 'III', 'IV', 'V', 'VI', 'VII', 'VIII', 'IX', 'X', 'XI', 'XII']
# Сноски: номер и начало текста (по нему тело сноски отличается от маркера с тем же номером)
FOOTNOTES = [(1, 'En anglais : Antipathies.'), (2, 'En français, dans le texte original'),
             (3, 'En anglais, Caucus Race'), (4, 'Le texte original comporte un jeu de mots entre tale'),
             (5, 'Le texte original comporte un jeu de mots entre “I had not'), (6, 'Parodie d’un long poème'),
             (7, 'Le mot anglais employé est'), (8, 'Voir l’expression to grin'),
             (9, 'Parodie du poème écrit en 1849'), (10, 'Allusion à deux expressions anglaises'),
             (11, 'Parodie du poème de Jane Taylor'), (12, 'À l’époque de Lewis Carol'),
             (13, 'Allusion à la « Guerre des deux roses'), (14, 'Soupe à la Simili-Tortue :'),
             (15, 'Parodie d’un poème de Mary Howith')]
PAGE_LINE = r'\n[ \t]*– \d+ –[ \t]*\n'           # строка номера страницы
# Разрыв страницы: хвост строки, номер страницы, колонтитул; группа 2 — название главы в колонтитуле
PAGE = re.compile(r'[ \t]*\n\s*– (\d+) –[ \t]*\n\s*Alice au pays des merveil(?:l| )es [-–] ('
                  + '|'.join(map(re.escape, RUNNING)) + r')[ \t]*')
CHAP = re.compile(r'^CHAPITRE ([IVX]+)[ \t]*\n\s*\n(.+)\n', re.M)

# Разрыв лигатуры: основа на «l»/«f», пробел, хвост слова. Хвосты ниже самостоятельными словами в этом
# тексте не бывают (проверено по всем парам «…l|f <слово>» файла): «el e», «feuil es», «Naturel ement»,
# «al ait», «af ection», «Wil iam»… Настоящие сочетания («bel et bien», «il est», «tel qu», «mal à») не задеты.
TAILS = {'e', 'es', 'er', 'ée', 'ement', 'ette', 'eure', 'eur', 'eux', 'euses', 'ons', 'ez', 'ait', 'aient',
         'ère', 'èrent', 'eraient', 'oir', 'aire', 'ant', 'ants', 'ection', 'iam', 'aume', 'oux', 'ie', 'ure',
         'ongé', 'otter', 'ets', 'ir'}
# Хвост «a» (passé simple) — только после этих основ: «s’en al a», «s’éveil a», «brouil a» («Il a» не трогаем)
STEMS_A = {'al', 'éveil', 'brouil'}
# «ll» потеряна целиком, без пробела (глава XII; ровно 3 случая)
LOST_LL = {'filette': 'fillette', 'Ele': 'Elle', 'ele': 'elle'}
LIG = re.compile(r'(?<![^\W\d_])([^\W\d_]*[lf]) (?=([^\W\d_]+)(?![^\W\d_]))')


def _read(path):
    with open(path, encoding='utf-8') as f:
        return f.read().replace('\r\n', '\n').replace('\r', '\n')


def _drop_footnotes(t):
    """Снимает тела сносок: от «N <начало>» до строки номера страницы (сноски стоят внизу страницы)."""
    for n, start in FOOTNOTES:
        pat = re.compile(rf'(?<!\S){n} {re.escape(start)}.*?(?={PAGE_LINE})', re.S)
        found = pat.findall(t)
        assert len(found) == 1, f'fr_papy: сноска {n} найдена {len(found)} раз'
        t = pat.sub('', t)
    return t


def _join_pages(t):
    """Убирает номера страниц и колонтитулы, склеивая текст через границу страницы."""
    pages, heads = [], []

    def join(m):
        pages.append(int(m.group(1)))
        heads.append(RUNNING.index(m.group(2)))
        before, after = m.string[m.start() - 1], m.string[m.end():m.end() + 1]
        if after.islower():                   # продолжение того же абзаца
            return '' if before == '-' else ' '   # «soixante-» / «quinze»: дефис настоящий, оставляем
        return '\n\n'
    t = PAGE.sub(join, t)
    assert pages == list(range(5, 179)), 'fr_papy: номера страниц не 5…178 подряд'
    assert heads == sorted(heads) and set(heads) == set(range(12)), 'fr_papy: колонтитулы не по порядку глав'
    assert 'Alice au pays des merveil' not in t and not re.search(r'– \d+ –', t), 'fr_papy: остался колонтитул'
    return t


def _ligatures(t):
    """Чинит разорванные лигатуры «ll»/«ff»: основа + повтор последней буквы + хвост («el e» -> «elle»)."""
    def fix(m):
        stem, tail = m.group(1), m.group(2)
        if tail in TAILS or (tail == 'a' and stem in STEMS_A):
            return stem + stem[-1]            # пробел вместо второй «l»/«f» -> сама буква
        return m.group(0)
    t = LIG.sub(fix, t)
    # «ll» в конце слова: «c’est Bil , je pense» (имя ящерицы); пробел перед запятой — место второй «l»
    t = re.sub(r'\bBil\b(?: (?=,))?', 'Bill', t)
    assert not re.search(r'\b(?:[Ee]l|[Aa]l|merveil|feuil|oreil|bouteil)\b', t), 'fr_papy: остался разрыв «ll»'
    return t


def _clean(body, markers):
    """Тело главы: маркеры сносок, лигатуры, пробелы; абзацы через одну пустую строку."""
    def mark(m):
        markers.append(int(m.group(1)))
        return ''
    body = re.sub(r'[ \t]*(\d+)', mark, body)   # иных цифр в тексте глав нет (числа — словами)
    body = _ligatures(body)
    lines = [re.sub(r'[ \t]+', ' ', ln).strip() for ln in body.split('\n')]
    return re.sub(r'\n{3,}', '\n\n', '\n'.join(lines)).strip()


def chapters(paths):
    t = _join_pages(_drop_footnotes(_read(paths[0])))
    # Глава I: название в начале файла, приклеено к тексту (первый абзац главы в файле отсутствует)
    first = 'Descente dans le terrier du lapin '
    assert t.startswith(first), 'fr_papy: файл начинается не с названия главы I'
    t = t[len(first):]
    # Потерянная целиком «ll» (без пробела): ровно 3 однозначных случая, см. LOST_LL
    t, n = re.subn(r'\b(' + '|'.join(LOST_LL) + r')\b', lambda m: LOST_LL[m.group(1)], t)
    assert n == 3, f'fr_papy: потерянных «ll» {n}, ожидалось 3'
    heads = list(CHAP.finditer(t))
    assert [h.group(1) for h in heads] == ROMAN, f'fr_papy: заголовки {[h.group(1) for h in heads]}'
    assert [h.group(2).strip() for h in heads] == TITLES, 'fr_papy: названия глав не совпали'
    starts = [0] + [h.end() for h in heads]
    ends = [h.start() for h in heads] + [len(t)]
    markers = []
    res = [_clean(t[s:e], markers) for s, e in zip(starts, ends)]
    # Маркеры 1…15, кроме 3 (он в названии главы III, снят вместе с заголовком)
    assert markers == [n for n in range(1, 16) if n != 3], f'fr_papy: маркеры сносок {markers}'
    # Сверка границ по содержанию (события английских глав I и XII)
    assert res[0].startswith('Elle se demandait (dans la mesure où elle était capable de réfléchir')
    assert res[-1].endswith('en se rappelant sa propre enfance et les heureuses journées d’été.')
    return res
