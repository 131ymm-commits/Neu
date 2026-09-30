import sys, os; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from poemlib import *; from interp import run_check; from sandbox import run_check_py
D = os.path.dirname(os.path.abspath(__file__)); bad = 0
def eq(a, b, msg):
    global bad
    if a != b: bad += 1; print('ОШИБКА', msg, a, b)
P = "Мороз и солнце; день чудесный!\nЕщё ты дремлешь, друг прелестный —\nПора, красавица, проснись:\nОткрой сомкнуты негой взоры"
eq(len(lines(P)), 4, 'lines'); eq(syl(lines(P)[0]), 9, 'syl0'); eq(syl(lines(P)[3]), 9, 'syl3')
eq(rhyme(lines(P)[0], lines(P)[1]), True, 'rhyme чудесный/прелестный'); eq(tail('луна'), 'на', 'tail луна'); eq(tail('в'), 'в', 'tail в')
eq(tail('ёлка'), 'ка', 'tail ёлка'); eq(syl('в с к'), 0, 'syl0'); eq(first_letters(P), 'мепо', 'first'); eq(count('Ёжик, ежевика', 'е'), 2, 'count е'); eq(count('Ёжик, ежевика', 'ё'), 1, 'count ё')
eq(words('Сине-зелёный, 3 raz'), ['сине', 'зелёный'], 'words'); eq(rhyme('да', 'да'), False, 'rhyme same'); eq(last_k('морозы!', 3), 'озы', 'last_k')
eq(is_known('чудесный'), True, 'known'); eq(is_known('куздра'), False, 'unknown'); eq(repeats('а а а б'), 3, 'rep')
CHECKS = [
 "def check(poem):\n    L = lines(poem)\n    return len(L) == 4 and all(syl(x) == 9 for x in L[:1])",
 "def check(poem):\n    return first_letters(poem) == 'мепо' and count(poem, 'о') >= 5",
 "def check(poem):\n    L = lines(poem)\n    return rhyme(L[0], L[1]) and not rhyme(L[2], L[3]) and sum(syl(x) for x in L) == 35",
 "def check(poem):\n    return all(is_known(w) for w in words(poem)) and repeats(poem) <= 2 and len(letters(poem)) > 50",
]
for c in CHECKS:
    for poem in (P, P.replace('солнце', 'луна'), 'а\nб'):
        a = run_check(c, poem, LIB); b = run_check_py(c, poem, D)
        eq(a, b, 'интерпретатор против CPython: ' + c.splitlines()[-1][:60])
eq(run_check("def check(poem):\n    return poem == 'Мороз и солнце; день чудесный! Ещё ты дремлешь'", P, LIB)[0], 'reject', 'длинная константа')
eq(run_check("import os\ndef check(poem):\n    return True", P, LIB)[0], 'reject', 'import')
print('ошибок', bad)
