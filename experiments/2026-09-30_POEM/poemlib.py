# «Арена стихов» (совет 18): замороженная библиотека примитивов для проверок check(poem) и для инструмента защитников.
# Описание прозой (его видят все роли):
#   lines(poem)      — список непустых строк (пробелы по краям обрезаны), в исходном порядке.
#   words(s)         — список слов строки или текста: нижний регистр, слово — непрерывная последовательность букв [а-яё]; всё остальное (пробел, дефис, знаки, цифры, латиница) разделяет слова.
#   letters(s)       — строка из всех русских букв s в нижнем регистре, по порядку (ё — отдельная буква, не е).
#   count(s, ch)     — сколько раз буква ch встречается в letters(s).
#   syl(s)           — число гласных букв (а е ё и о у ы э ю я) в s; это «слоги» Арены. Ударение и метр не учитываются.
#   tail(w)          — рифменный хвост слова: от последней гласной буквы до конца; если он короче 2 букв, берутся последние 2 буквы слова (слово из 1 буквы — само слово).
#   rhyme(a, b)      — True, если у последних слов строк a и b одинаковые хвосты tail и сами слова разные; у строки без слов рифмы нет.
#   last_k(w, k)     — последние k букв слова w.
#   first_letters(poem) — строка из первых букв (первая русская буква) каждой строки, в нижнем регистре.
#   last_word(s)     — последнее слово строки (words(s)[-1]) или пустая строка.
#   is_known(w)      — слово есть в словаре OpenCorpora (pymorphy3.word_is_known, словарь заморожен по версии).
#   repeats(poem)    — наибольшее число повторов одного слова во всём тексте.
import re
VOW = set('аеёиоуыэюя')
def lines(poem): return [x.strip() for x in str(poem).split('\n') if x.strip()]
def words(s): return re.findall(r'[а-яё]+', str(s).lower())
def letters(s): return ''.join(re.findall(r'[а-яё]', str(s).lower()))
def count(s, ch): return letters(s).count(str(ch).lower())
def syl(s): return sum(c in VOW for c in letters(s))
def tail(w):
    w = letters(w)
    if not w: return ''
    i = max((j for j, c in enumerate(w) if c in VOW), default=-1)
    t = w[i:] if i >= 0 else w
    return t if len(t) >= 2 else w[-2:]
def last_word(s):
    ws = words(s); return ws[-1] if ws else ''
def rhyme(a, b):
    x, y = last_word(a), last_word(b)
    return bool(x) and bool(y) and x != y and tail(x) == tail(y)
def last_k(w, k): return letters(w)[-k:] if k > 0 else ''
def first_letters(poem): return ''.join((letters(l)[:1]) for l in lines(poem))
_M = None
def is_known(w):
    global _M
    if _M is None:
        import pymorphy3; _M = pymorphy3.MorphAnalyzer()
    w = letters(w)
    return bool(w) and _M.word_is_known(w)
def repeats(poem):
    from collections import Counter
    c = Counter(words(poem)); return max(c.values()) if c else 0
LIB = dict(lines=lines, words=words, letters=letters, count=count, syl=syl, tail=tail, rhyme=rhyme, last_k=last_k,
           first_letters=first_letters, last_word=last_word, is_known=is_known, repeats=repeats)
def base_ok(poem, max_rep=3):
    """базовое условие всех заказов: все слова в словаре, одно слово не больше max_rep раз, есть хотя бы 2 строки"""
    ws = words(poem)
    bad = [w for w in ws if not is_known(w)]
    return (len(lines(poem)) >= 2 and not bad and repeats(poem) <= max_rep), bad
if __name__ == '__main__':   # инструмент защитников: python3 poemlib.py <функция> <файл со стихом> [аргументы]
    import sys, json
    fn = sys.argv[1]; txt = open(sys.argv[2]).read(); args = sys.argv[3:]
    if fn == 'report':
        L = lines(txt)
        print(json.dumps(dict(lines=[dict(n=i + 1, text=l, syl=syl(l), last=last_word(l), tail=tail(last_word(l)), first=letters(l)[:1]) for i, l in enumerate(L)],
                              unknown=[w for w in words(txt) if not is_known(w)], repeats=repeats(txt), first_letters=first_letters(txt), letters=len(letters(txt))), ensure_ascii=False, indent=1))
    else:
        f = LIB[fn]; print(json.dumps(f(txt, *[int(a) if a.lstrip('-').isdigit() else a for a in args]), ensure_ascii=False))
