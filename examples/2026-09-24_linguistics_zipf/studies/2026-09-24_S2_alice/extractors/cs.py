"""cs — S-16, Jaroslav Skoumal (пер.), «Alenka v kraji divů», репозиторий books-are-next
(carroll-alenka-v-kraji-divu, content/*.md). 12 файлов cs_00.md … cs_11.md — по одному на главу, UTF-8, LF.
Устройство файла: YAML-шапка «---» / «title: <название главы>» / «contentType: prose» / «---»,
дальше текст, разбитый на блоки <section> … </section>; иллюстрации — строки «![alenka_002](./resources/…)».
Заголовков «#» в теле нет: название главы есть только в шапке (сверяется с TITLES и отбрасывается).
Разметка markdown в тексте:
- курсив _…_, в том числе с «лишними» подчёркиваниями («hodinky__,_», «ó myši!__)_»), и жирный **…**
  (надписи «**VYPIJ MĚ**») — снимаются все «_» и «**»: других подчёркиваний и звёздочек в тексте нет;
- стихи оформлены цитатой «> » с жёстким переносом «  » (два пробела в конце строки) и отступами;
- хвост Мыши (глава III) набран «фигурой» — строки с большими отступами в отдельных <section>.
Отступы фигур набраны неразрывными пробелами (U+00A0, только в стихах и хвосте Мыши). Отступы и концевые
пробелы снимаются, серия пробелов внутри строки («věz, <30 пар U+00A0 и пробела> jak je zvykem»)
сжимается в один пробел;
строки стихов и хвоста остаются отдельными строками.
Стихи и песни внутри глав (в т. ч. «Sbor:» — «CHORUS.» у Кэрролла) остаются. Сносок и примечаний в файлах нет."""
import re

# Названия глав из YAML-шапок — сверка порядка файлов по содержанию (соответствуют главам I–XII)
TITLES = ['Dolů králičí dírou', 'Kaluž slz', 'Kuriální závod a sáhodlouhý obrázek',
          'O tom, jak Vilík komínem vylít', 'Houseňákova rada', 'Vepř a pepř', 'Bláznivá svačina',
          'Královnino kroketové hřiště', 'Paželví povídka', 'Humří čtverylka', 'Kdo ukradl vdolky',
          'Alenčino svědectví']
# YAML-шапка в начале файла
FRONT = re.compile(r'\A---\ntitle: (.+)\ncontentType: prose\n---\n')
IMAGE = re.compile(r'^!\[[^\]]*\]\([^)]*\)$')   # строка-иллюстрация
SECTION = re.compile(r'^</?section>$')           # разметка блоков


def _read(path):
    with open(path, 'rb') as f:
        t = f.read().decode('utf-8')
    return t.replace('\r\n', '\n').replace('\r', '\n')


def _chapter(t, title):
    """Тело одной главы из md-файла: без шапки, секций, иллюстраций и разметки markdown."""
    m = FRONT.match(t)
    assert m, 'cs: нет YAML-шапки'
    assert m.group(1).strip() == title, f'cs: глава {m.group(1)!r}, ожидалась {title!r}'
    out = []
    for line in t[m.end():].split('\n'):
        s = line.strip()
        if SECTION.match(s) or IMAGE.match(s):
            continue
        if s.startswith('>'):            # цитата-стих: «> строка»; пустая «>» — пустая строка
            s = s[1:].strip()
        # strip снимает отступы фигур (в т. ч. U+00A0) и «  »-переносы markdown; серии пробелов внутри -> один
        out.append(re.sub(r'[ \t\xa0]{2,}', ' ', s))
    text = '\n'.join(out)
    text = text.replace('**', '').replace('_', '')   # жирный и курсив markdown
    assert not re.search(r'[*_#<>\[\]\\`]|!\[|&\w+;', text), 'cs: осталась разметка'
    text = re.sub(r'\n{3,}', '\n\n', text)           # не больше одной пустой строки подряд
    return text.strip()


def chapters(paths):
    assert len(paths) == 12, f'cs: файлов {len(paths)}, нужно 12'
    res = [_chapter(_read(p), title) for p, title in zip(paths, TITLES)]
    # Сверка границ по содержанию: первая и последняя фразы книги (как в английском)
    assert res[0].startswith('Alenku už mrzelo sedět na břehu vedle cesty'), 'cs: начало главы I'
    assert res[-1].endswith('při vzpomínce na své dětství a na blahé letní dny.'), 'cs: конец главы XII'
    return res
