"""es_1 — S-10, корпус iglika88 (…/Spanish/Alice in Wonderland/aw sp full 1.txt), файл es_1_00.txt.
Текст извлечён корпусом из PDF; переводчик в корпусе не назван. UTF-8, CRLF.
Абзац — обычно одна строка, абзацы через пустую строку; у иллюстраций текст шёл узкой колонкой,
там строки короткие («saltó cerca de ella un Cone-» / «jo Blanco de ojos rosados.»).
Титула, оглавления, колонтитулов, сносок и послесловия нет: файл начинается заголовком главы I
и кончается последней фразой книги.

Что снимается и чинится:
* Заголовок главы: «I. EN LA MADRIGUERA DEL CONEJO» … «XII. LA DECLARACIÓN DE ALICIA» с начала строки;
  у главы III к названию в той же строке приклеена первая фраза («… LARGA HISTORIA El grupo que …»).
* Номера страниц 7…123 (кроме первых страниц глав II–XII: 14, 22, 31, …, 115) — в конце строки: отдельной
  строкой, через пробел после текста («y se las 7») или прямо за дефисом переноса («casti-18» / «go»).
  Других цифр в файле нет.
* Переносы PDF: в конце строки («mar-» / «garitas») и оставшиеся внутри строки после склейки
  («guir-nalda», «ti-rarse», «perdóne-me») — склеиваются. Настоящие дефисы оставлены: «lacayo-pez»,
  «lacayo-rana», «bebé-cerdito» и растяжки в песне о супе («¡Hermoooo-sa soooo-pa!», «noooo-che»).
* Хвост мышиной сказки (глава III) сужается до слогов без дефисов: «a muer-» / «te con» / «de» / «ne.’» —
  слово «condene» разбито на три строки; склеиваем «con» / «de» / «ne» -> «condene» (ровно 1 случай).
* Сбой распознавания в песне о супе (глава X): «¡Hermooo~-sa soooo-pa!» — повтор строки «¡Hermoooo-sa
  soooo-pa!», стоящей строкой выше; «~» на месте «o» -> «o» (ровно 1 случай).
Не тронуто (так в файле): в стихах главы X после «mientras que al búho le tocaba / sólo la fuente que contenía
el pastel.» идёт гибрид «Cuando terminaron de comérselo, al búho le tocaba / sólo la fuente que contenía
el pastel.», затем настоящее «Cuando terminaron de comérselo, el búho como regalo,» — похоже на ошибку набора
в самом издании (не на сбой извлечения), поэтому не удаляем."""
import re

ROMAN = ['I', 'II', 'III', 'IV', 'V', 'VI', 'VII', 'VIII', 'IX', 'X', 'XI', 'XII']
TITLES = ['EN LA MADRIGUERA DEL CONEJO', 'EL CHARCO DE LÁGRIMAS', 'UNA CARRERA LOCA Y UNA LARGA HISTORIA',
          'LA CASA DEL CONEJO', 'CONSEJOS DE UNA ORUGA', 'CERDO Y PIMIENTA', 'UNA MERIENDA DE LOCOS',
          'EL CROQUET DE LA REINA', 'LA HISTORIA DE LA FALSA TORTUGA', 'EL BAILE DE LA LANGOSTA',
          '¿QUIÉN ROBO LAS TARTAS?', 'LA DECLARACIÓN DE ALICIA']
PAGENUM = re.compile(r'[ \t]*(\d+)[ \t]*$', re.M)   # номер страницы в конце строки
# Настоящие дефисы (проверены по контексту): слуги-рыба и слуга-лягушка, младенец-поросёнок
REAL_HYPHEN = {'lacayo-pez', 'lacayo-rana', 'bebé-cerdito'}
ELONG = re.compile(r'(\w)\1\1$')               # «soooo-», «Hermoooo-»: растянутый слог в песне — дефис авторский


def _read(path):
    with open(path, encoding='utf-8') as f:
        return f.read().replace('\r\n', '\n').replace('\r', '\n')


def _drop_page_numbers(t):
    """Снимает номера страниц; проверяет, что это ровно страницы 7…123 без первых страниц глав."""
    nums = [int(n) for n in PAGENUM.findall(t)]
    steps = [b - a for a, b in zip(nums, nums[1:])]
    # подряд, с пропуском 11 ненумерованных первых страниц глав II–XII
    assert nums[0] == 7 and nums[-1] == 123 and set(steps) == {1, 2} and steps.count(2) == 11, \
        'es_1: номера страниц не 7…123'
    t = PAGENUM.sub('', t)
    assert not re.search(r'\d', t), 'es_1: осталась цифра'
    return t


def _dehyphen(t):
    """Склеивает переносы PDF, кроме настоящих дефисов."""
    def join(m):
        a, b = m.group(1), m.group(2)
        if f'{a}-{b}'.lower() in REAL_HYPHEN or ELONG.search(a):
            return f'{a}-{b}'
        return a + b
    t = re.sub(r'(\w+)-[ \t]*\n\s*(\w+)', join, t)   # перенос в конце строки (дальше могут быть пустые строки)
    t = re.sub(r'(\w+)-(\w+)', join, t)              # перенос, оставшийся внутри строки
    return t


def _clean(body):
    """Тело главы: переносы, пробелы по краям строк; абзацы через одну пустую строку."""
    t = _dehyphen(body)
    t = '\n'.join(ln.strip() for ln in t.split('\n'))
    return re.sub(r'\n{3,}', '\n\n', t).strip()


def _repairs(t):
    """Два однозначных сбоя вёрстки/распознавания (см. docstring модуля), каждый ровно один раз."""
    t, n = re.subn(r'\bcon[ \t]*\n\s*de[ \t]*\n\s*ne\.’', 'condene.’', t)   # хвост мыши: «con/de/ne»
    assert n == 1, f'es_1: «con/de/ne» найдено {n} раз'
    t, n = re.subn(r'Hermooo~-sa', 'Hermoooo-sa', t)                        # «~» вместо «o»
    assert n == 1 and '~' not in t, f'es_1: «Hermooo~-sa» найдено {n} раз'
    return t


def chapters(paths):
    t = _repairs(_drop_page_numbers(_read(paths[0])))
    heads = [re.compile(rf'^{r}\. {re.escape(title)}[ \t]*', re.M) for r, title in zip(ROMAN, TITLES)]
    found = [h.findall(t) for h in heads]
    assert all(len(f) == 1 for f in found), 'es_1: заголовок главы не найден или повторяется'
    spans = [h.search(t).span() for h in heads]
    assert spans[0][0] == 0 and spans == sorted(spans), 'es_1: заголовки не по порядку или текст до главы I'
    ends = [s for s, _ in spans[1:]] + [len(t)]
    out = [_clean(t[e0:e1]) for (_, e0), e1 in zip(spans, ends)]
    # Сверка границ по содержанию: первая и последняя фразы книги (как в английском)
    assert out[0].startswith('Alicia empezaba ya a cansarse de estar sentada con su hermana')
    assert out[-1].endswith('recordando su propia infancia y los felices días del verano.')
    return out
