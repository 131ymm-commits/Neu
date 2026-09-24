"""eo — Project Gutenberg #17482, пер. E. L. Kearney (1910), UTF-8 с BOM, CRLF.
Главы начинаются строкой «ĈAPITRO I» … «ĈAPITRO XII» (с отступом), за ней абзац-название («MIRINDA FALEGO!»).
До главы I — титул, «ANTAŬPAROLO DE L' TRADUKINTO», оглавление «ENHAVO», список иллюстраций
и стихотворение «ANTAŬPAROLO DE LA AŬTORO» (пролог Кэрролла): всё отбрасывается.
Конец книги — перед заметкой корректоров «[En la libro mem, la piednotoj …]», за которой
собраны 14 сносок переводчика и лицензия PG: всё это отбрасывается.
В теле удаляются маркеры сносок «[1]»…«[14]», подписи «[Ilustraĵo: …]» (бывают в 2 строки),
вставка корректоров «[LA KUIRISTINO RIFUZAS ATESTI.]» в гл. XI, курсив _…_ и разделители «*   *   *». Стихи внутри глав (хвост Мыши, «Tvink'l», «Sup'») остаются.
Кроме сносок, у Кирни есть примечания, набранные прямо в тексте (без маркера). Удаляются два (NOTES ниже):
скобочное примечание в гл. X о том, как каламбур про whiting звучит «en la angla teksto», с пересказом
английского диалога (само место уже передано заменой каламбура выше), и пересчёт валюты «(250sd.)» в гл. XII."""
import re

ROMAN = ['I', 'II', 'III', 'IV', 'V', 'VI', 'VII', 'VIII', 'IX', 'X', 'XI', 'XII']
HEAD = re.compile(r'^ĈAPITRO ([IVXL]+)$')      # строка номера главы (строка оглавления «ĈAPITRO … PAĜO» не подходит)
END = '[En la libro mem'                        # начало заметки перед сносками — конец текста книги

# Примечания переводчика внутри текста глав: (номер главы, регулярное выражение, замена).
# Каждое должно найтись ровно один раз.
NOTES = [
    # гл. X: после своей замены каламбура («Ĉar ĝia lango estas ĉiam en la maro…») переводчик в скобках
    # объясняет английский оригинал: «(En la angla teksto li tute alie klarigis la nomon. … Jen la teksta
    # dialogo:— … Do, vi nun komprenas.")». Это примечание, а не текст книги: абзац целиком удаляется.
    (10, re.compile(r'\n\(En la angla teksto .*?Do, vi nun komprenas\."\)\n', re.S), '\n'),
    # гл. XII: «ses pencojn (250sd.)» — пересчёт в спесдеки (sd.), глосса переводчика (как «(12.5 sd.)» в его предисловии)
    (12, re.compile(r' \(250sd\.\)'), ''),
]


def clean(lines):
    """Тело главы из строк: убрать иллюстрации, сноски, разделители, курсив; сжать пустые строки."""
    text = '\n'.join(ln.rstrip() for ln in lines)
    text = re.sub(r'\[Ilustraĵo:[^\]]*\]', '', text)   # подпись к картинке, может занимать 2 строки
    text = re.sub(r'\[\d+\]', '', text)                  # маркер сноски: «tejlo,"[3]» -> «tejlo,"»
    # вставка корректоров PG в гл. XI: «vidu la ilustraĵon sur paĝo 120 [LA KUIRISTINO RIFUZAS ATESTI.])»;
    # фраза переводчика (у Кэрролла «look at the frontispiece») остаётся, название картинки в [] — нет
    text = re.sub(r' ?\[[A-ZĈĜĤĴŜŬ][A-ZĈĜĤĴŜŬ .,!?]*\]', '', text)
    text = text.replace('_', '')                         # курсив PG: _tre_ -> tre
    out = []
    for s in text.split('\n'):
        if re.fullmatch(r'\s*(\*\s*)+', s):              # типографский разделитель «*  *  *  *  *»
            continue
        out.append('' if not s.strip() else s)           # строка, где была только подпись, -> пустая
    text = '\n'.join(out)
    text = re.sub(r'\n{3,}', '\n\n', text)               # не больше одной пустой строки подряд
    assert '[' not in text and ']' not in text, 'eo: осталась скобочная вставка'
    return text.strip()


def chapters(paths):
    lines = open(paths[0], encoding='utf-8-sig').read().replace('\r\n', '\n').split('\n')
    heads = [i for i, ln in enumerate(lines) if HEAD.match(ln.strip())]
    assert [HEAD.match(lines[i].strip()).group(1) for i in heads] == ROMAN, 'eo: номера глав не I…XII'
    end = [i for i, ln in enumerate(lines) if ln.startswith(END)]
    assert len(end) == 1 and end[0] > heads[-1], 'eo: нет заметки о сносках после главы XII'
    bounds = heads + end
    out = []
    for k in range(12):
        i = bounds[k] + 1
        while not lines[i].strip():          # пустые строки между номером и названием
            i += 1
        while lines[i].strip():              # абзац-название главы (вместе с маркером сноски в нём)
            i += 1
        out.append(clean(lines[i:bounds[k + 1]]))
    for k, pat, repl in NOTES:               # примечания переводчика внутри текста
        out[k - 1], n = pat.subn(repl, out[k - 1])
        assert n == 1, f'eo: примечание в гл. {k} найдено {n} раз, нужно 1'
        out[k - 1] = re.sub(r'\n{3,}', '\n\n', out[k - 1])
    return out
