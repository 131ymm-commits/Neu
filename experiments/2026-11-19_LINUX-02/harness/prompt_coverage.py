#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""LINUX-02: полнота поручений (исправление к ERRORS № 216). Механически: имя, которое обвязке пришлось дать самой
(kernel_shim.h, заглушки include/, kernel_helpers.c; глобальные имена — без отступа), стоит в исходнике модуля или в приложенных
заголовках (строки #include не считаются), но не определено
в приложенных заголовках и не названо в условиях поручения (текст поручения вне блоков кода), — пропуск.
Стандартные имена C (memcpy, size_t, …) пропуском не считаются.
  python3 harness/prompt_coverage.py [OUT.json] [--dir prompts/test]   — код выхода 1, если есть пропуски"""
import glob
import json
import os
import re
import sys

X = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import make_prompts as MP  # noqa: E402

ID = re.compile(r'\b[A-Za-z_][A-Za-z0-9_]*\b')
C_STD = set('''memcpy memmove memset memcmp memchr strlen strnlen strcmp strncmp strchr strrchr strcpy strncpy strcat strstr
sizeof NULL true false bool size_t ssize_t ptrdiff_t uintptr_t intptr_t int8_t int16_t int32_t int64_t uint8_t uint16_t uint32_t
uint64_t char short int long unsigned signed void const static inline extern struct union enum typedef return if else for while
do switch case default break continue goto volatile register restrict auto float double offsetof va_list va_start va_end va_arg
__func__ __VA_ARGS__ typeof __typeof__ __builtin_expect __attribute__ asm __asm__ errno'''.split())


def code_free(txt):
    return re.sub(r'```.*?```', ' ', txt, flags=re.S)


def strip_comments(src):
    src = re.sub(r'^[ \t]*#[ \t]*include[^\n]*', ' ', src, flags=re.M)      # пути заголовков — не имена
    return re.sub(r'//[^\n]*|/\*.*?\*/|\'(?:\\.|[^\\\'\n])+\'|"(?:\\.|[^"\\])*"', ' ', src, flags=re.S)


def shim_names():
    names = set()
    files = [os.path.join(X, 'harness', 'kernel_shim.h'), os.path.join(X, 'harness', 'kernel_helpers.c')]
    files += glob.glob(os.path.join(X, 'harness', 'include', '**', '*.h'), recursive=True)
    for f in files:
        s = strip_comments(open(f, encoding='utf-8').read())
        names |= set(re.findall(r'^[ \t]*#[ \t]*define[ \t]+([A-Za-z_][A-Za-z0-9_]*)', s, flags=re.M))
        names |= set(re.findall(r'\b([A-Za-z_][A-Za-z0-9_]*)[ \t]*\([^;{)]*\)\s*[;{]', s))   # прототипы и определения функций
        names |= set(re.findall(r'\btypedef\b[^;]*?\b([A-Za-z_][A-Za-z0-9_]*)[ \t]*;', s))
        names |= set(re.findall(r'^(?:static[ \t]+)?(?:const[ \t]+)?[A-Za-z_][A-Za-z0-9_ \t\*]*?\b([A-Za-z_][A-Za-z0-9_]*)[ \t]*(?:\[[^\]]*\])?[ \t]*=',
                                s, flags=re.M))
    return names - C_STD


def defined_in(src):
    s = strip_comments(src)
    d = set(re.findall(r'^[ \t]*#[ \t]*define[ \t]+([A-Za-z_][A-Za-z0-9_]*)', s, flags=re.M))
    d |= set(re.findall(r'\b([A-Za-z_][A-Za-z0-9_]*)[ \t]*\([^;{)]*\)\s*\{', s))   # в стиле ядра { — на новой строке
    d |= set(re.findall(r'\b(?:struct|union|enum)[ \t]+([A-Za-z_][A-Za-z0-9_]*)[ \t]*\{', s))
    d |= set(re.findall(r'\btypedef\b[^;]*?\b([A-Za-z_][A-Za-z0-9_]*)[ \t]*;', s))
    d |= set(re.findall(r'^[ \t]*([A-Z_][A-Z0-9_]*)[ \t]*(?:=[^,]*)?,', s, flags=re.M))   # члены enum
    return d


def gaps(m, prompt, shim=None):
    """Пропуски поручения prompt для модуля m: имена из обвязки, которые стоят в исходнике или заголовках и нигде не объяснены."""
    shim = shim_names() if shim is None else shim
    d = MP.MODS[m]
    text_ids = set(ID.findall(code_free(prompt)))
    src = MP.read(d['path'])
    hdrs = '\n'.join(MP.read(h) for h in d['headers'])
    used = set(ID.findall(strip_comments(src + '\n' + hdrs)))
    defined = defined_in(src + '\n' + hdrs)
    return sorted((used & shim) - defined - text_ids - C_STD), sorted((used & shim) - defined)


def main(a):
    pdir = a[a.index('--dir') + 1] if '--dir' in a else os.path.join(X, 'prompts')
    out = [x for i, x in enumerate(a) if not x.startswith('--') and (i == 0 or a[i - 1] != '--dir')]
    shim = shim_names()
    res, gaps_all = {}, 0
    for m in MP.MODS:
        prompt = open(os.path.join(pdir, f'{m}.md'), encoding='utf-8').read()
        g, used = gaps(m, prompt, shim)
        res[m] = dict(used_from_shim=used, gaps=g)
        gaps_all += len(g)
        print(m, '| имён из обвязки:', len(used), '| не объяснено в поручении:', len(g), g)
    if out:
        json.dump(dict(prompts_dir=os.path.relpath(pdir, X), modules=res), open(out[0], 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    return 1 if gaps_all else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
